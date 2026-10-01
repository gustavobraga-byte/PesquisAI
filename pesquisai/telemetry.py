"""
telemetry.py — Telemetria anônima opt-in do UFVAI/PesquisAI (v0.6.0).

Princípios:
  1. OPT-IN explícito: nada é enviado sem consentimento gravado em
     ~/.config/ufvai_consent.json (tela de Termos de Uso → checkbox próprio).
  2. ZERO conteúdo: apenas contadores de eventos e metadados não-pessoais
     (versão, idioma, provedor). Nunca caminhos, notas, chaves ou prompts.
  3. Fail-safe total: qualquer erro é silencioso; envio roda em thread
     daemon com timeout curto — nunca bloqueia nem quebra o app.
  4. Kill-switch: UFVAI_TELEMETRY=0 desliga globalmente.

Configuração do produtor (dono do projeto):
  UFVAI_GA_MEASUREMENT_ID  — ID GA4 (G-XXXXXXX)
  UFVAI_GA_API_SECRET      — segredo do Measurement Protocol

Sem essas variáveis a telemetria fica inativa mesmo com consentimento.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import time
import urllib.request
import uuid

try:
    from .__version__ import __version__ as _APP_VERSION  # v0.6.7: payload de contato carrega a versão
except Exception:
    _APP_VERSION = "unknown"

_CID_FILE = os.path.expanduser("~/.config/ufvai_cid")
_CONSENT_FILE = os.path.expanduser("~/.config/ufvai_consent.json")
_ADMIN_CFG_FILE = os.path.expanduser("~/.config/ufvai_telemetry.json")  # v0.6.4
_PROFILE_FILE = os.path.expanduser("~/.config/ufvai_profile.json")     # v0.6.6
_MP_URL = "https://www.google-analytics.com/mp/collect"

# v0.6.9-P03: Canal único — webhook UFVAI_CONTACT_ENDPOINT.
# Google Forms NÃO funciona em fluxo automatizado (reCAPTCHA bloqueia).
# URL do Forms para envio manual (exibir na UI, não usado pelo código):
_FORM_VIEW_URL = ("https://docs.google.com/forms/d/e/"
    "1FAIpQLSd773cm2qDkwpXzbz50IVhGSG7rpC527taTYGsdUes0Lh1s2A/viewform")
# Webhook do desenvolvedor (Apps Script → Planilha). Ver scripts/webhook-contatos.gs
# v0.6.10 (01/09): endpoint atualizado (solicitação usuário)
# v0.6.20 (01/10): nova implantação do Apps Script (nova URL /exec)
_DEFAULT_CONTACT_ENDPOINT = "https://script.google.com/macros/s/AKfycby1zrMKMbySw-eZ6v-9W8G-6GRXcyyO77YYMKSG7vZfGF34mqWF-02XgBVs4FHPtmQ6/exec"

_FALSEY = ("0", "false", "off", "no")

# v0.6.6: validação simples de e-mail (local-part@domínio.tld)
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]{2,}$")

# v0.6.9-P03: domínios temporários / descartáveis bloqueados
_BLOCKED_DOMAINS = frozenset({
    "guerrillamail.com", "guerrillamail.de", "guerrillamail.biz",
    "tempmail.com", "throwaway.email", "temp-mail.org",
    "fakeinbox.com", "sharklasers.com", "guerrillamailblock.com",
    "grr.la", "dispostable.com", "yopmail.com", "yopmail.fr",
    "mailinator.com", "trashmail.com", "trashmail.net",
    "10minutemail.com", "discard.email", "discardmail.com",
    "mailexpire.com", "maildrop.cc", "mailnesia.com",
    "tempail.com", "tempr.email", "tempomail.fr",
})


def _email_domain_valid(addr: str) -> bool:
    """v0.6.9-P03: valida se o domínio do e-mail existe e aceita mail.

    1) Verifica se o domínio está na lista de bloqueados (temporários).
    2) Tenta resolver MX records via socket.getaddrinfo (stdlib, sem deps).
    3) Se nenhum MX encontrar, tenta resolver A/AAAA (alguns domínios
       aceitam mail sem MX explícito — ex.: domínios pequenos).
    """
    import socket
    domain = addr.split("@")[-1].strip().lower()
    if not domain:
        return False
    # Lista negra de domínios temporários
    if domain in _BLOCKED_DOMAINS:
        return False
    # MX records
    try:
        results = socket.getaddrinfo(domain, "smtp", socket.AF_INET, socket.SOCK_STREAM)
        if results:
            return True
    except (socket.gaierror, OSError):
        pass
    # Fallback: tenta MX via gethostbyname_ex (mais compatível)
    try:
        import subprocess
        out = subprocess.run(
            ["nslookup", "-type=mx", domain],
            capture_output=True, text=True, timeout=3
        )
        if "mail exchanger" in out.stdout.lower() or "mx" in out.stdout.lower():
            return True
    except Exception:
        pass
    # Último recurso: tenta conectar na porta 25 (SMTP)
    try:
        s = socket.create_connection((domain, 25), timeout=3)
        s.close()
        return True
    except (socket.timeout, OSError):
        pass
    return False


def _admin_local_config() -> tuple[str, str]:
    """(v0.6.4) Credenciais salvas via painel Admin da UI (~/.config/ufvai_telemetry.json)."""
    try:
        with open(_ADMIN_CFG_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return str(d.get("measurement_id", "")).strip(), str(d.get("api_secret", "")).strip()
    except Exception:
        return "", ""


def _ga_config() -> tuple[str, str]:
    """Retorna (measurement_id, api_secret).

    Prioridade v0.6.4: variáveis de ambiente > arquivo local do painel Admin.
    """
    mid = os.environ.get("UFVAI_GA_MEASUREMENT_ID", "").strip()
    sec = os.environ.get("UFVAI_GA_API_SECRET", "").strip()
    if mid and sec:
        return mid, sec
    lmid, lsec = _admin_local_config()
    return (mid or lmid).strip(), (sec or lsec).strip()


def save_admin_config(
    measurement_id: str | None = None,
    api_secret: str | None = None,
    contact_endpoint: str | None = None,
) -> tuple[bool, str]:
    """Salva a configuração do painel Admin da UI.

    (v0.6.4) Credenciais GA4; (v0.6.7) também grava ``contact_endpoint``
    (canal HTTPS que recebe o e-mail de contato opt-in — ex.: Apps Script
    → Planilha Google).

    Semântica por parâmetro:
      • ``None`` ou ``""``  → NÃO altera o que já está salvo;
      • texto               → valida e define.
      • Exceção: ``contact_endpoint=""`` LIMPA o canal (remoção).
    Cada campo é independente — dá para atualizar só o canal de contato
    sem redigitar as credenciais GA4 (que nunca são devolvidas pela API).
    Arquivo local com permissão 600. Retorna (ok, mensagem).
    """
    try:
        # Base = configuração existente (edição parcial de campos)
        base: dict = {}
        try:
            with open(_ADMIN_CFG_FILE, encoding="utf-8") as f:
                base = json.load(f)
        except Exception:
            base = {}

        # ── GA4: só toca se pelo menos um campo veio preenchido ──
        new_mid = str(measurement_id).strip() if measurement_id else str(base.get("measurement_id", ""))
        new_sec = str(api_secret).strip() if api_secret else str(base.get("api_secret", ""))
        ga_touched = bool(measurement_id or api_secret)
        if ga_touched:
            if not re.fullmatch(r"G-[A-Z0-9]{6,12}", new_mid):
                return False, "ID de medição inválido ou ausente (formato esperado: G-XXXXXXXXXX)."
            if len(new_sec) < 8:
                return False, "API Secret ausente ou muito curto — cole-o novamente."
            base["measurement_id"] = new_mid
            base["api_secret"] = new_sec
            os.environ["UFVAI_GA_MEASUREMENT_ID"] = new_mid
            os.environ["UFVAI_GA_API_SECRET"] = new_sec

        # ── v0.6.7 canal de contato (HTTPS; localhost liberado p/ teste) ──
        cmsg = ""
        if contact_endpoint is not None:
            curl = str(contact_endpoint).strip()
            if curl and not (curl.startswith("https://") or curl.startswith("http://localhost")):
                return False, "URL de contato inválida (use https://…)."
            base["contact_endpoint"] = curl
            if curl:
                os.environ["UFVAI_CONTACT_ENDPOINT"] = curl
                cmsg = " Canal de contato ativo."
            else:
                os.environ.pop("UFVAI_CONTACT_ENDPOINT", None)
                cmsg = " Canal de contato removido."

        if not ga_touched and contact_endpoint is None:
            return False, "Nada a salvar."

        base["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        os.makedirs(os.path.dirname(_ADMIN_CFG_FILE), exist_ok=True)
        with open(_ADMIN_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(base, f)
        os.chmod(_ADMIN_CFG_FILE, 0o600)
        return True, ("Configuração salva." if not ga_touched else
                      "Configuração salva. A coleta inicia quando o usuário aceitar "
                      "o opt-in nos Termos.") + cmsg
    except Exception as e:
        return False, f"Falha ao salvar: {e}"


def masked_state() -> dict:
    """(v0.6.4) Estado para exibição no painel Admin — NUNCA expõe o secret."""
    mid, sec = _ga_config()
    consent = read_consent()
    st = {
        "configured": configured(),
        "measurement_id": (mid[:2] + "***" + mid[-7:]) if mid else "",
        "api_secret_set": bool(sec),
        "source": ("env" if os.environ.get("UFVAI_GA_MEASUREMENT_ID") else ("file" if mid else "none")),
        "consent_accepted": bool(consent.get("accepted")),
        "consent_analytics": bool(consent.get("analytics")),
        "kill_switch": kill_switch_active(),
        "enabled": enabled(),
    }
    st.update(contact_status())  # v0.6.6: has_email / email_masked / endpoint_set
    # v0.6.7: URL de contato EFETIVA (env > arquivo) visível SÓ ao admin — é a
    # URL dele; o API secret continua nunca retornado. Usada p/ preencher o
    # campo do painel ("o que está no campo é o que será salvo").
    st["contact_endpoint_url"] = _contact_endpoint()
    return st


# ─────────────────────────────────────────────────────────────────────────────
# v0.6.6 — Contato opt-in (e-mail do usuário)
#
# LGPD: o e-mail SÓ é coletado com consentimento livre, informado e inequívoco
# (art. 7º I), finalidade específica documentada (contato/novidades do UFVAI),
# campo opcional e direito de eliminação a qualquer momento (art. 18).
# O e-mail NUNCA vai para o Google Analytics — os Termos do GA4 proíbem PII
# (mesmo com hash). Para o desenvolvedor saber que houve opt-in, o GA4 recebe
# apenas um CONTADOR anônimo ("contact_optin", sem conteúdo). O endereço em si
# fica no arquivo local abaixo e, se o desenvolvedor configurar o próprio
# endpoint HTTPS (UFVAI_CONTACT_ENDPOINT, ex.: Apps Script), é enviado para lá.
# ─────────────────────────────────────────────────────────────────────────────


def _contact_endpoint() -> str:
    """(v0.6.7) Endpoint HTTPS do desenvolvedor que recebe o contato opt-in.

    Prioridade: variável de ambiente UFVAI_CONTACT_ENDPOINT > painel Admin
    (~/.config/ufvai_telemetry.json, chave contact_endpoint).
    """
    url = os.environ.get("UFVAI_CONTACT_ENDPOINT", "").strip()
    if url:
        return url
    try:
        with open(_ADMIN_CFG_FILE, encoding="utf-8") as f:
            url = str(json.load(f).get("contact_endpoint", "") or "").strip()
            if url:
                return url
    except Exception:
        pass
    return _DEFAULT_CONTACT_ENDPOINT


def contact_status() -> dict:
    """Estado mascarado do contato — nunca expõe o e-mail completo."""
    prof = _read_profile()
    email = str(prof.get("email", ""))
    name = str(prof.get("name", "") or prof.get("nome", ""))
    masked = ""
    if email and "@" in email:
        loc, _, dom = email.partition("@")
        masked = (loc[:2] + "***@" + dom) if len(loc) > 2 else "***@" + dom
    # nome mascarado: primeiras 2 letras + ***
    name_masked = ""
    if name:
        parts = name.strip().split()
        if len(parts) >= 2:
            name_masked = parts[0][:2] + "*** " + parts[-1][:1] + "***"
        else:
            name_masked = name[:2] + "***"
    curl = _contact_endpoint()
    return {
        "has_email": bool(email),
        "email_masked": masked,
        "has_name": bool(name),
        "name_masked": name_masked,
        "name": name,  # v0.6.10: expõe nome mascarado? aqui nome completo só para /api/consent autenticado
        "contact_endpoint_set": bool(curl),
        "contact_endpoint_source": ("env" if os.environ.get("UFVAI_CONTACT_ENDPOINT", "").strip()
                                    else ("file" if curl else "")),
    }


def _persisted_profile_path() -> str | None:
    """v0.6.13: caminho do perfil PERSISTENTE (backups/ufvai_consentimento.json).

    Espelha a lógica de launch_app._consent_backup_file(): no Colab o
    arquivo vive no Google Drive (sobrevive ao reset da VM); offline vive
    em ~/PesquisAI/backups/. Retorna None em caso de falha.
    """
    try:
        base = ("/content/drive/My Drive/PesquisAI"
                if os.path.isdir("/content/drive/My Drive")
                else os.path.expanduser("~/PesquisAI"))
        return os.path.join(base, "backups", "ufvai_consentimento.json")
    except Exception:
        return None


def _read_profile() -> dict:
    """Perfil de contato persistente.

    v0.6.13: o ~/.config é efêmero no Colab (reset da VM apaga). Se o
    arquivo local não tiver e-mail (usuário já registrado REVISITANDO uma
    sessão nova), cai no backup persistente do Drive — corrige o heartbeat
    ``/api/access`` (flag "usuario_ativo") que ficava sem e-mail e pulava
    a gravação na planilha em toda revisita.
    """
    prof: dict = {}
    try:
        with open(_PROFILE_FILE, encoding="utf-8") as f:
            prof = json.load(f) or {}
    except Exception:
        prof = {}
    if not prof.get("email"):
        try:
            bpath = _persisted_profile_path()
            if bpath and os.path.isfile(bpath):
                with open(bpath, encoding="utf-8") as f:
                    backup = json.load(f) or {}
                if backup.get("email"):
                    prof.setdefault("email", str(backup.get("email", "")).lower())
                    prof.setdefault("email_sha256", str(backup.get("email_sha256", "")))
                    if not prof.get("name"):
                        prof["name"] = str(backup.get("name", "") or backup.get("nome", ""))
        except Exception:
            pass
    return prof


def _valid_name(name: str) -> bool:
    """v0.6.10: valida nome — 2–100 chars, letras/espaços acentuados."""
    n = str(name or "").strip()
    if len(n) < 2 or len(n) > 100:
        return False
    # permite letras (incl. acentos), espaços, hífen, apóstrofo
    return bool(re.fullmatch(r"[A-Za-zÀ-ÿÀ-ÿ\s'\-]{2,100}", n))


def save_contact(email: str, name: str | None = None, ip: str | None = None) -> tuple[bool, str]:
    """Grava o e-mail+nome localmente (chmod 600) com hash SHA-256 e encaminha ao
    endpoint do desenvolvedor, se configurado. Dispara contador anônimo no GA4.

    v0.6.10: ``name`` é armazenado no perfil e enviado à planilha ao lado do
    e-mail (mesmo consentimento art. 7º V). ``ip`` é efêmero — vai só ao webhook,
    não persiste no arquivo local.

    Retorna (ok, mensagem).
    """
    addr = str(email or "").strip().lower()
    if not addr:
        return False, "E-mail vazio."
    if not _EMAIL_RE.fullmatch(addr) or len(addr) > 254:
        return False, "E-mail inválido."
    # v0.6.9-P03: valida domínio (MX records + blacklist temporários)
    if not _email_domain_valid(addr):
        return False, "E-mail inválido ou domínio não aceita mensagens."
    # v0.6.10: nome opcional mas, se fornecido, deve ser válido; para ativação
    # nova passamos a exigir nome (validado no handler)
    cname = str(name or "").strip() if name is not None else ""
    if name is not None and name != "":
        if not _valid_name(cname):
            return False, "Nome inválido — use 2 a 100 letras."
    sha = hashlib.sha256(addr.encode("utf-8")).hexdigest()
    # v0.6.20-fix: dedupe ANTES de gravar — lê o perfil PERSISTENTE (local +
    # backup do Drive). Se o e-mail já está registrado, é RE-CONSENTIMENTO
    # (re-aceite dos Termos, re-execução da célula, overlay esporádico) e NÃO
    # um contato novo: a planilha não recebe linha "novo_contato" — apenas o
    # heartbeat "usuario_ativo" do clique "Continuar" registra o acesso.
    # E-mail diferente (ou ausente) = contato novo de verdade → registra.
    _already_registered = False
    try:
        _prev = _read_profile()
        _already_registered = (bool(_prev.get("email"))
                               and str(_prev.get("email", "")).strip().lower() == addr)
    except Exception:
        _already_registered = False
    # v0.6.20-fix (segunda rodada): a planilha do desenvolvedor recebe
    # EXATAMENTE UMA linha por ativação/retorno — o heartbeat "usuario_ativo"
    # (com IP) disparado pelo clique do botão Continuar/ABRIR via /api/access
    # → notify_active_user(). Aqui NÃO há mais forward "novo_contato": o
    # primeiro aceite grava apenas o perfil local/Drive; a linha única só é
    # escrita quando o usuário clica no botão.
    try:
        os.makedirs(os.path.dirname(_PROFILE_FILE), exist_ok=True)
        # preserva campos antigos se já existirem (ex.: ip não persiste)
        existing = {}
        try:
            with open(_PROFILE_FILE, "r", encoding="utf-8") as rf:
                existing = json.load(rf)
        except Exception:
            existing = {}
        # atualiza com novos dados
        payload_local = {
            "email": addr,
            "email_sha256": sha,
            "name": cname or str(existing.get("name", "") or existing.get("nome", "")),
            "purpose": "contato/novidades UFVAI (consentimento art. 7º V)",
            "consent_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        # normaliza chave legado 'nome' → 'name'
        if "nome" in existing and not payload_local.get("name"):
            payload_local["name"] = str(existing.get("nome", ""))
        with open(_PROFILE_FILE, "w", encoding="utf-8") as f:
            json.dump(payload_local, f, ensure_ascii=False)
        os.chmod(_PROFILE_FILE, 0o600)
    except Exception as e:
        return False, f"Falha ao salvar contato: {e}"
    _contato_log("contato salvo localmente (%s · %s) · ga4_configurada=%s · endpoint=%s · ip=%s"
                 % (addr.split("@")[1] if "@" in addr else "?",
                    (cname[:20] + "…") if cname else "sem-nome",
                    "sim" if configured() else "nao",
                    "sim" if _contact_endpoint() else "NAO CONFIGURADO",
                    ip or "—"))
    if _already_registered:
        # v0.6.20-fix: re-consentimento — sem linha "novo_contato" na planilha
        # e sem contador GA4 repetido; o perfil local/Drive é atualizado acima
        # (mantendo aceite/versão dos Termos em dia) e o acesso será registrado
        # pelo clique "Continuar" (flag "usuario_ativo").
        _contato_log("re-consentimento SKIP: e-mail já registrado — sem linha "
                     "'novo_contato' (só o 'usuario_ativo' do botão)")
        return True, "Contato atualizado com sucesso."
    # Contador ANÔNIMO para o GA4 (sem nenhum dado derivado do e-mail/nome/ip)
    event("contact_optin")
    # v0.6.20-fix: NÃO há forward "novo_contato" ao endpoint — a planilha do
    # desenvolvedor recebe a linha ÚNICA "usuario_ativo" (e-mail · nome · IP)
    # somente no clique do botão Continuar/ABRIR (/api/access →
    # notify_active_user()). Isso elimina a duplicação na planilha.
    _contato_log("primeiro aceite: perfil gravado localmente — planilha aguarda "
                 "'usuario_ativo' do clique do botão (linha única)")
    return True, "Contato registrado com sucesso."


def clear_contact() -> None:
    """Elimina o e-mail local (direito de eliminação, LGPD art. 18 VI)."""
    try:
        os.remove(_PROFILE_FILE)
    except Exception:
        pass
    # v0.6.20-fix: elimina TAMBÉM o perfil persistente (Drive/offline) — sem
    # isso, após a eliminação, o re-aceite dos Termos seria tratado como
    # re-consentimento (sem linha "novo_contato") e o e-mail eliminado voltaria
    # a pré-preencher a tela. Eliminação = eliminar em todos os cantos.
    try:
        bpath = _persisted_profile_path()
        if bpath and os.path.isfile(bpath):
            os.remove(bpath)
    except Exception:
        pass


def _contato_log(msg: str) -> None:
    """v0.6.9-offline: auditoria local do fluxo de contato — sem isso um
    envio fire-and-forget é indistinguível de uma falha silenciosa."""
    try:
        d = os.path.expanduser("~/PesquisAI/logs")
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".w")
            open(probe, "w").close()
            os.remove(probe)
        except Exception:
            d = "/tmp/PesquisAI/logs"
            os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "contato.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg + "\n")
    except Exception:
        pass


# v0.6.9-P03: Canal 3 (gspread → planilha world-writable) REMOVIDO.
# Google Forms (POST) NÃO funciona em fluxo automatizado (reCAPTCHA).
# Canal único: webhook UFVAI_CONTACT_ENDPOINT (Apps Script → Planilha).
# Link manual do Forms disponível na UI para envio opcional pelo usuário.


def _forward_contact(addr: str, sha: str, kind: str = "novo_contato", name: str = "", ip: str = "") -> None:
    """Envia o contato opt-in via webhook (único canal automático).

    O Google Forms tem reCAPTCHA que bloqueia submissões programáticas,
    então NÃO pode ser usado no fluxo automatizado (tela de abertura).
    O webhook (UFVAI_CONTACT_ENDPOINT) é o único canal confiável.

    ``kind`` distingue o tipo de registro gravado na planilha:
      • "usuario_ativo" — ÚNICO tipo enviado (v0.6.20): cada ativação/retorno
        grava 1 linha com e-mail + nome + IP, disparada pelo clique do botão
        (Continuar/ABRIR → /api/access → notify_active_user()).
      • "novo_contato" — legado (primeiro aceite da tela de Termos); SEM uso
        desde a v0.6.20: o aceite grava apenas o perfil local/Drive, sem
        linha na planilha, eliminando a duplicação de registro.

    v0.6.10: ``name`` e ``ip`` são enviados juntos (nome ao lado do e-mail;
    IP capturado do X-Forwarded-For/remote_addr). O IP é coletado com
    finalidade de segurança/métrica de ativação (art. 7º V) e NUNCA vai ao GA4.

    Fire-and-forget. Se o endpoint não estiver configurado, o contato
    fica salvo localmente e o log registra que nenhum envio remoto
    ocorreu (o desenvolvedor deve configurar o endpoint para receber).
    """
    url = _contact_endpoint()
    _contato_log("forward iniciado (kind=%s · nome=%s · ip=%s) * endpoint=" % (kind, (name[:12] + "…") if name else "—", ip or "—") +
                 (url[:60] + "..." if len(url) > 60 else (url or "<VAZIO>")))
    if url:
        try:
            # tenta obter nome/ip do perfil se não vieram nos args
            if not name or not ip:
                try:
                    prof = _read_profile()
                    if not name:
                        name = str(prof.get("name", "") or prof.get("nome", ""))
                except Exception:
                    pass
            payload = {
                "product": "ufvai",
                "email": addr,
                "email_sha256": sha,
                "name": str(name or "").strip(),
                "ip": str(ip or "").strip(),
                "environment": "colab" if os.path.isdir("/content") else "local",
                "app_version": _APP_VERSION,
                "sent_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "flag": kind,
            }
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            resp = urllib.request.urlopen(req, timeout=8)
            body = resp.read(64)
            _contato_log("forward OK * http=%s * resp=%s" % (getattr(resp, "status", "?"), body[:40]))
            return
        except Exception as e:
            _contato_log("forward FALHOU * %s: %s" % (type(e).__name__, str(e)[:120]))
    else:
        _contato_log("forward PENDENTE: UFVAI_CONTACT_ENDPOINT nao configurado. "
                     "Contato salvo localmente. Configure o webhook para receber.")


def _tel_log(msg: str) -> None:
    """v0.6.9-offline: auditoria da telemetria (logs/telemetria.log).
    O event() era totalmente silencioso — impossível distinguir
    'sem credenciais' de 'falha de rede'."""
    try:
        d = os.path.expanduser("~/PesquisAI/logs")
        try:
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".w")
            open(probe, "w").close()
            os.remove(probe)
        except Exception:
            d = "/tmp/PesquisAI/logs"
            os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "telemetria.log"), "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + msg + "\n")
    except Exception:
        pass


def kill_switch_active() -> bool:
    """True se UFVAI_TELEMETRY=0/false/off."""
    return os.environ.get("UFVAI_TELEMETRY", "1").strip().lower() in _FALSEY


def configured() -> bool:
    """True se as credenciais GA4 estão presentes no ambiente."""
    mid, sec = _ga_config()
    return bool(mid and sec)


def consented() -> bool:
    """True se o usuário aceitou estatísticas anônimas na tela de Termos."""
    try:
        with open(_CONSENT_FILE, encoding="utf-8") as f:
            return bool(json.load(f).get("analytics"))
    except Exception:
        return False


def enabled() -> bool:
    """Telemetria ativa = configurada E consentida E sem kill-switch."""
    if kill_switch_active():
        return False
    if not configured():
        return False
    return consented()


def read_consent() -> dict:
    """Lê o estado atual do consentimento (para exibição/debug)."""
    try:
        with open(_CONSENT_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"accepted": False, "analytics": False}


def set_consent(analytics: bool) -> None:
    """Grava o consentimento de telemetria (chamado por /api/consent)."""
    try:
        state = read_consent() or {}
        state["analytics"] = bool(analytics)
        state["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        os.makedirs(os.path.dirname(_CONSENT_FILE), exist_ok=True)
        with open(_CONSENT_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception:
        pass


def _client_id() -> str:
    """UUID anônimo estável por máquina (não é identidade pessoal)."""
    try:
        if os.path.exists(_CID_FILE):
            cid = open(_CID_FILE, encoding="utf-8").read().strip()
            if cid:
                return cid
    except Exception:
        pass
    cid = str(uuid.uuid4())
    try:
        os.makedirs(os.path.dirname(_CID_FILE), exist_ok=True)
        with open(_CID_FILE, "w", encoding="utf-8") as f:
            f.write(cid)
    except Exception:
        pass
    return cid


def event(name: str, params: dict | None = None) -> None:
    """Dispara um evento anônimo via GA4 Measurement Protocol.

    Fire-and-forget: nunca levanta, nunca bloqueia. Silencioso se
    desabilitado (sem consent/config/kill-switch).
    """
    try:
        if not enabled():
            why = []
            if kill_switch_active():
                why.append("kill-switch UFVAI_TELEMETRY=0")
            else:
                if not configured():
                    why.append("credenciais ausentes (defina UFVAI_GA_MEASUREMENT_ID e UFVAI_GA_API_SECRET em ~/PesquisAI/config/ufvai.env)")
                if not consented():
                    why.append("sem consentimento (caixa GA4 desmarcada)")
            _tel_log("evento '%s' SUPRIMIDO: %s" % (name, "; ".join(why) or "?"))
            return
        mid, sec = _ga_config()
        _tel_log("evento '%s' → GA4 %s (debug=%s)" % (
            name, mid,
            "sim" if os.environ.get("UFVAI_TELEMETRY_DEBUG", "").strip().lower() in ("1", "true", "yes", "on") else "nao"))
        payload = {
            "client_id": _client_id(),
            "non_personalized_ads": True,
            "events": [{"name": str(name)[:40], "params": {**(params or {})}}],
        }
        data = json.dumps(payload).encode("utf-8")
        url = f"{_MP_URL}?measurement_id={mid}&api_secret={sec}"
        # v0.6.2: UFVAI_TELEMETRY_DEBUG=1 → envia para o DebugView do GA4
        # (visível em tempo real em Admin → DebugView), sem gravar relatórios.
        # v0.6.9: CORREÇÃO — o parâmetro correto do Measurement Protocol é o
        # campo "debug_mode":1 no EVENTO (não "&debug_view=1" na URL, que o
        # GA4 ignorava silenciosamente e os eventos nunca apareciam no DebugView).
        if os.environ.get("UFVAI_TELEMETRY_DEBUG", "").strip().lower() in ("1", "true", "yes", "on"):
            payload["events"][0]["params"]["debug_mode"] = 1

        def _send() -> None:
            try:
                req = urllib.request.Request(
                    url,
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                resp = urllib.request.urlopen(req, timeout=3)
                resp.read(16)
                _tel_log("evento '%s' ENVIADO http=%s" % (name, getattr(resp, "status", "?")))
            except Exception as e:
                _tel_log("evento '%s' FALHOU · %s: %s" % (name, type(e).__name__, str(e)[:120]))

        threading.Thread(target=_send, daemon=True).start()
    except Exception:
        pass


def notify_active_user(ip: str | None = None) -> None:
    """v0.6.9: heartbeat — registra cada NOVO ACESSO de usuário já ativo.

    Na reabertura (perfil persistente existente + mesma versão dos Termos),
    a UI mostra a tela "Bem-vindo de volta" e, ao confirmar, chama este
    heartbeat: o webhook recebe o e-mail + horário do acesso + flag
    "usuario_ativo". v0.6.20: este é o ÚNICO registro que a planilha recebe
    — o primeiro aceite também chega aqui (perfil já gravado por
    save_contact), garantindo exatamente 1 linha por ativação.

    v0.6.10: ``ip`` capturado da requisição (X-Forwarded-For) é encaminhado
    junto ao webhook para métrica de ativação geográfica/segurança.

    LGPD: finalidade já consentida (art. 7º V — ativação/contato sobre o
    produto); o e-mail/nome/ip NUNCA vão ao GA4 — apenas ao endpoint do
    desenvolvedor (UFVAI_CONTACT_ENDPOINT), como no aceite original.

    Fire-and-forget; sem perfil salvo ou sem endpoint → no-op silencioso
    (apenas auditoria local).
    """
    try:
        prof = _read_profile()
        addr = str(prof.get("email", ""))
        name = str(prof.get("name", "") or prof.get("nome", ""))
        if not addr:
            _contato_log("heartbeat SKIP: sem e-mail salvo (primeiro acesso?)")
            return
        threading.Thread(
            target=_forward_contact,
            args=(addr, str(prof.get("email_sha256", "")), "usuario_ativo", name, ip or ""),
            daemon=True,
        ).start()
    except Exception as e:
        _contato_log("heartbeat FALHOU: %s" % type(e).__name__)


def publish_backend_url(url: str) -> None:
    """v0.6.11: anuncia a URL pública do backend no webhook (descoberta do app).

    Chamado pelo launch() do Colab após obter o proxyPort: o Apps Script
    (v0.6.11+) guarda como "último backend" deste usuário (chave = sha do
    e-mail) e o app Android (variante cloud) busca via
    ``GET ?action=backend&email_sha256=...`` — zero colagem de URL.
    Também grava linha de auditoria na planilha (flag "backend_online").

    LGPD: mesma finalidade consentida do contato (art. 7º V); só vai ao
    endpoint do desenvolvedor, nunca ao GA4. Fire-and-forget; sem perfil
    ou sem endpoint → no-op (apenas auditoria local).
    """
    try:
        u = str(url or "").strip().rstrip("/") + "/"
        if not (u.startswith("https://") or u.startswith("http://")):
            return
        prof = _read_profile()
        addr = str(prof.get("email", "")).strip().lower()
        if not addr:
            _contato_log("backend_online SKIP: sem e-mail salvo")
            return
        sha = str(prof.get("email_sha256", "")
                  or hashlib.sha256(addr.encode("utf-8")).hexdigest())
        name = str(prof.get("name", "") or prof.get("nome", ""))
        endpoint = _contact_endpoint()
        if not endpoint:
            _contato_log("backend_online PENDENTE: endpoint não configurado")
            return
        payload = {
            "product": "ufvai",
            "email": addr,
            "email_sha256": sha,
            "name": name,
            "ip": "",
            "environment": "colab" if os.path.isdir("/content") else "local",
            "app_version": _APP_VERSION,
            "sent_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "flag": "backend_online",
            "backend_url": u,
        }

        def _post() -> None:
            try:
                req = urllib.request.Request(
                    endpoint,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                resp = urllib.request.urlopen(req, timeout=8)
                try:
                    resp.read(64)
                except Exception:
                    pass
                _contato_log("backend_online OK * %s" % (u[:60],))
            except Exception as e:
                _contato_log("backend_online FALHOU * %s: %s"
                             % (type(e).__name__, str(e)[:100]))

        threading.Thread(target=_post, daemon=True).start()
    except Exception as e:
        try:
            _contato_log("backend_online FALHOU: %s" % type(e).__name__)
        except Exception:
            pass
