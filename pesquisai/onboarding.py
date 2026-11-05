"""pesquisai/onboarding.py — v0.7.10: primeiro uso guiado por provedor.

Objetivo: um usuário que abre o UFVAI pela primeira vez (ou que ainda não tem
nenhuma chave salva) escolhe o provedor numa tela única, recebe o tutorial do
provedor e cola a chave — sem passar pela lista de 15 provedores.

Regras de integridade (valem para este módulo):

* Nenhuma função aqui inventa chave, cota ou modelo: o identificador do modelo
  do Google é um **padrão configurável** (``GOOGLE_DEFAULT_MODEL``) e, quando o
  catálogo do motor está disponível, ele é conferido contra a lista real.
* A chave nunca é registrada em log nem devolvida inteira por API; só
  ``mask_key()``.
* Funções puras (sem rede e sem disco) para poderem ser testadas sem runtime.

O módulo não importa ``launch_app`` para evitar ciclo: o handler HTTP é quem
salva/criptografa e reinicia o serviço.
"""

from __future__ import annotations

import os
from typing import Any, Iterable, Mapping

# ── Provedores oferecidos no onboarding ────────────────────────────────────
# `prefixes` serve só para reconhecer o que o usuário colou; a validação real
# é feita pelo provedor na primeira chamada.
PROVIDERS: dict[str, dict[str, Any]] = {
    "google": {
        "id": "google",
        "label": "Google Gemini",
        "env": "GOOGLE_GENERATIVE_AI_API_KEY",
        "prefixes": ("AIza",),
        "url": "https://aistudio.google.com/api-keys",
        "url_label": "aistudio.google.com/api-keys",
        "paid": False,
        "recommended": True,
        "tagline": "Grátis no Google AI Studio · recomendado",
        "model": "google/gemini-flash-lite-latest",
    },
    "nvidia": {
        "id": "nvidia",
        "label": "NVIDIA NIM",
        "env": "NVIDIA_API_KEY",
        "prefixes": ("nvapi-",),
        "url": "https://build.nvidia.com/",
        "url_label": "build.nvidia.com",
        "paid": False,
        "recommended": False,
        "tagline": "Grátis com conta NVIDIA · modelos nvidia/*",
        "model": "",
    },
    "openrouter": {
        "id": "openrouter",
        "label": "OpenRouter",
        "env": "OPENROUTER_API_KEY",
        "prefixes": ("sk-or-",),
        "url": "https://openrouter.ai/keys",
        "url_label": "openrouter.ai/keys",
        "paid": False,
        "recommended": False,
        "tagline": "Grátis nos modelos :free",
        "model": "openrouter/free",
    },
    "opencode_go": {
        "id": "opencode_go",
        "label": "OpenCode Go",
        "env": "OPENCODE_API_KEY",
        "prefixes": ("sk-",),
        "url": "https://opencode.ai/go",
        "url_label": "opencode.ai/go",
        "paid": True,
        "recommended": False,
        "tagline": "Plano pago",
        "model": "",
    },
}

ONBOARDING_ORDER: tuple[str, ...] = ("google", "nvidia", "openrouter", "opencode_go")

# Modelo padrão quando existe chave do Google. Pedido do autor (v0.7.10):
# "se o usuário tem uma key do google o modelo padrão é o gemini 3.5 flash".
# O id pode ser trocado por `UFVAI_GOOGLE_MODEL` sem mexer no código.
GOOGLE_DEFAULT_MODEL: str = "google/gemini-flash-lite-latest"

# v0.7.10: o modelo padrão é "Gemini Flash-Lite Latest · high". O sufixo `#high`
# é um VARIANTE do motor (esforço de raciocínio) — o `model` raiz não guarda
# variante (doc V2 de modelos), então ele vai no modelo do AGENTE UFVAI.
GOOGLE_DEFAULT_VARIANT: str = "high"

# Ordem de preferência caso o catálogo do motor não tenha o modelo acima.
GOOGLE_MODEL_FALLBACKS: tuple[str, ...] = (
    "google/gemini-flash-lite-latest",
    "google/gemini-3.1-flash-lite",
    "google/gemini-3.5-flash-lite",
    "google/gemini-3.5-flash",
    "google/gemini-3-flash",
    "google/gemini-2.5-flash",
)

CHAVES_DOC_URL = (
    "https://github.com/gustavobraga-byte/PesquisAI/blob/main/docs/CHAVES_API.md"
)
GUIDE_DOC_URL = (
    "https://github.com/gustavobraga-byte/PesquisAI/blob/main/docs/chaves-api-tutorial.html"
)


# ── Utilidades puras ───────────────────────────────────────────────────────

def normalize_key(raw: str | None) -> str:
    """Limpa o que vem da área de transferência.

    Colar de um site costuma trazer espaço, quebra de linha e aspas. Nada
    disso faz parte da chave e só geraria um 401 confuso.
    """
    text = str(raw or "")
    for ch in ("\u00a0", "\u200b", "\ufeff"):
        text = text.replace(ch, "")
    return text.strip().strip('"').strip("'").strip()


def provider_ids() -> tuple[str, ...]:
    return ONBOARDING_ORDER


def get_provider(provider_id: str) -> dict[str, Any] | None:
    return PROVIDERS.get((provider_id or "").strip().lower())


def is_supported(provider_id: str) -> bool:
    return get_provider(provider_id) is not None


def detect_provider(key: str) -> str:
    """Descobre o provedor pelo prefixo da chave.

    Devolve ``""`` quando ambíguo (ex.: ``sk-`` pode ser OpenAI, DeepSeek ou
    OpenCode Go) — nesse caso o onboarding pede a escolha explícita.
    """
    k = normalize_key(key)
    if not k:
        return ""
    # OpenRouter antes de qualquer prefixo genérico de "sk-".
    if k.startswith("sk-or-"):
        return "openrouter"
    for pid in ONBOARDING_ORDER:
        if pid == "opencode_go":
            continue
        for prefix in PROVIDERS[pid]["prefixes"]:
            if k.startswith(prefix):
                return pid
    return ""


def validate_key_format(provider_id: str, key: str) -> tuple[bool, str]:
    """Validação *de formato* (barata). A validação real é no provedor."""
    prov = get_provider(provider_id)
    if prov is None:
        return False, "Provedor não suportado."
    k = normalize_key(key)
    if not k:
        return False, "Cole a chave para continuar."
    if len(k) < 20:
        return False, "A chave parece incompleta (menos de 20 caracteres)."
    prefixes = tuple(prov["prefixes"])
    if provider_id != "opencode_go" and not k.startswith(prefixes):
        shown = " ou ".join(f"“{p}”" for p in prefixes)
        return False, f"A chave de {prov['label']} deve começar com {shown}."
    return True, ""


def mask_key(key: str) -> str:
    """``sk-or-…7f2a`` — nunca devolve a chave inteira."""
    k = normalize_key(key)
    if not k:
        return ""
    if len(k) <= 12:
        return k[:3] + "…"
    return f"{k[:6]}…{k[-4:]}"


def store_keys(store: Mapping[str, Any] | None) -> dict[str, str]:
    """Remove metadados ``_env_*`` e entradas vazias do store."""
    out: dict[str, str] = {}
    for k, v in dict(store or {}).items():
        if str(k).startswith("_env_"):
            continue
        if isinstance(v, str) and v.strip():
            out[str(k)] = v
    return out


def has_any_key(
    store: Mapping[str, Any] | None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """True se existe **qualquer** chave utilizável (store ou ambiente)."""
    if store_keys(store):
        return True
    env = env or {}
    for prov in PROVIDERS.values():
        if str(env.get(prov["env"], "") or "").strip():
            return True
    # Chaves de provedores fora do onboarding também contam.
    for var in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY"):
        if str(env.get(var, "") or "").strip():
            return True
    return False


def needs_onboarding(
    store: Mapping[str, Any] | None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """A tela aparece sempre que **não há chave** — inclusive para quem já usa.

    Não usamos flag de "já viu": a condição é objetiva. Assim o usuário antigo
    que perdeu a chave (trocou de conta Google, apagou o store) volta a ver o
    guia em vez de cair num terminal sem provedor.
    """
    if str(os.environ.get("UFVAI_SKIP_ONBOARDING", "") or "").strip() in ("1", "true", "yes"):
        return False
    return not has_any_key(store, env)


def google_key_present(env: Mapping[str, str] | None = None) -> bool:
    env = env or {}
    return bool(
        str(env.get(PROVIDERS["google"]["env"], "") or "").strip()
        or str(env.get("GEMINI_API_KEY", "") or "").strip()
    )


def google_model() -> str:
    """Modelo padrão do Google (respeita ``UFVAI_GOOGLE_MODEL``)."""
    override = str(os.environ.get("UFVAI_GOOGLE_MODEL", "") or "").strip()
    if override:
        return override if "/" in override else f"google/{override}"
    return GOOGLE_DEFAULT_MODEL


def google_variant() -> str:
    """Variante (esforço) do modelo Google. Padrão: ``high``."""
    override = str(os.environ.get("UFVAI_GOOGLE_VARIANT", "") or "").strip()
    return override if override else GOOGLE_DEFAULT_VARIANT


def google_model_selector(variant: str | None = None) -> str:
    """``google/modelo#high`` — referência com variante (agente/comando)."""
    base = google_model().split("#", 1)[0]
    var = google_variant() if variant is None else str(variant or "").strip()
    return f"{base}#{var}" if var else base


def google_model_from_catalog(lines: Iterable[str]) -> str:
    """Escolhe o primeiro modelo do Google disponível no catálogo do motor.

    Recebe a saída de ``opencode models`` (uma linha por modelo). Se nenhum
    candidato aparecer — catálogo vazio, sem rede ou nome novo — devolve o
    padrão configurado. Nunca inventa um identificador: só devolve algo que
    esteja na lista ou o padrão declarado.
    """
    available = {str(l or "").strip() for l in lines if str(l or "").strip()}
    for candidate in (google_model(), *GOOGLE_MODEL_FALLBACKS):
        if candidate in available:
            return candidate
    return google_model()


def default_model_for(provider_id: str, catalog: Iterable[str] | None = None) -> str:
    """Modelo a gravar como padrão ao conectar o provedor (``""`` = não mexer)."""
    prov = get_provider(provider_id)
    if prov is None:
        return ""
    if provider_id == "google":
        return google_model_from_catalog(catalog or ())
    return str(prov.get("model") or "")


def merge_model(
    existing: Mapping[str, Any] | None,
    model_id: str,
    variant: str = "",
    agent: str = "UFVAI",
) -> dict[str, Any]:
    """Copia a configuração e define o modelo — preserva todo o resto.

    v0.7.10: o ``model`` raiz fica SEM variante (limite do motor V2) e a
    variante (ex.: ``high``) é gravada no modelo do agente ``UFVAI``, que é
    quem aparece no seletor da TUI ("… · high").
    """
    mid = str(model_id or "").strip()
    if not mid:
        raise ValueError("model_id vazio")
    base, _, inline = mid.partition("#")
    var = str(variant or inline or "").strip()
    merged = dict(existing or {})
    merged["model"] = base
    if var and agent:
        agents = dict(merged.get("agents") or {})
        entry = dict(agents.get(agent) or {})
        entry["model"] = f"{base}#{var}"
        agents[agent] = entry
        merged["agents"] = agents
    return merged


def providers_public() -> list[dict[str, Any]]:
    """Lista para a UI (sem segredo, sem função)."""
    out: list[dict[str, Any]] = []
    for pid in ONBOARDING_ORDER:
        prov = PROVIDERS[pid]
        out.append({
            "id": pid,
            "label": prov["label"],
            "env": prov["env"],
            "url": prov["url"],
            "url_label": prov["url_label"],
            "paid": bool(prov["paid"]),
            "recommended": bool(prov["recommended"]),
            "tagline": prov["tagline"],
            "model": default_model_for(pid),
        })
    return out


def onboarding_state(
    store: Mapping[str, Any] | None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Payload do ``GET /api/onboarding``."""
    return {
        "needs": needs_onboarding(store, env),
        "has_key": has_any_key(store, env),
        "google_model": google_model(),
        "providers": providers_public(),
        "docs": CHAVES_DOC_URL,
        "guide": GUIDE_DOC_URL,
    }
