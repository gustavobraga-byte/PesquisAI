# 📊 Telemetria do UFVAI — Como Funciona

> **Resumo em uma frase:** a telemetria é **ativa por padrão sem cookies (opt-out, LGPD art. 7º, IX)** desde v0.6.9 (antes opt-in), envia **apenas contadores anônimos de eventos** via Google Analytics 4 Measurement Protocol, **nunca envia conteúdo, nome, e-mail ou IP**, e pode ser desligada a qualquer momento.

---

## 0. Guia do ADMINISTRADOR — ativar a telemetria passo a passo (v0.6.4)

> **Para quem é esta seção:** você (admin/produtor do UFVAI) quer saber **quantas instalações estão
> em uso, quais versões/idiomas e quais funcionalidades são mais usadas** — sem identificar pessoas
> (LGPD-safe). Siga os 8 passos abaixo.

### Passo 1 — Criar a propriedade GA4
1. Acesse <https://analytics.google.com> com sua conta Google;
2. **Admin (⚙️) → Criar → Propriedade**; nome sugerido: `UFVAI Telemetria`;
   fuso horário `Brasília`, moeda `Real (R$)`;
3. Em "Detalhes da empresa", setor `Educação`, tamanho qualquer → **Criar**.

### Passo 2 — Criar o fluxo de dados Measurement Protocol
1. Na propriedade: **Admin → Fluxos de dados → Adicionar fluxo → Web**;
2. URL: `https://localhost` (é apenas um rótulo — o envio é server-side, sem site);
3. Anote o **ID de medição** (`G-XXXXXXXXXX`) exibido no fluxo criado.

### Passo 3 — Gerar o segredo do Measurement Protocol
1. No mesmo fluxo: **Eventos de Measurement Protocol → Configurar → Criar**;
2. Apelido: `ufvai-mp`;
3. Copie o **segredo** (`api_secret`). Guarde os dois valores.

### Passo 4 — Configurar no modo OFFLINE (.deb)
Crie o arquivo que o launcher carrega antes de iniciar:
```bash
mkdir -p ~/PesquisAI/config
cat > ~/PesquisAI/config/ufvai.env <<'EOF'
export UFVAI_GA_MEASUREMENT_ID=G-XXXXXXXXXX
export UFVAI_GA_API_SECRET=SEU_SEGREDO_AQUI
EOF
chmod 600 ~/PesquisAI/config/ufvai.env
```
Reinicie o UFVAI (`pesquisai` ou `~/PesquisAI/start.sh`).

### Passo 5 — Configurar no COLAB
Defina as variáveis no kernel ANTES de executar `launch()`:
```python
import os
os.environ["UFVAI_GA_MEASUREMENT_ID"] = "G-XXXXXXXXXX"
os.environ["UFVAI_GA_API_SECRET"] = "SEU_SEGREDO_AQUI"
```

### Passo 6 — Validar em tempo real (DebugView)
1. No GA4 deixe aberto: **Admin → DebugView**;
2. Rode o UFVAI com `export UFVAI_TELEMETRY_DEBUG=1` e aceite os Termos marcando o opt-in;
3. Os eventos (`terms_accepted`, `app_started`, `lang_changed`…) aparecem ao vivo.
Sem a flag DEBUG, os eventos vão para **Relatórios → Tempo real** (até alguns minutos de atraso).

### Passo 7 — O que o admin vê (e o que NÃO vê)

| O admin VÊ | O admin NUNCA vê |
|---|---|
| **Quantas instalações ativas** (1 UUID anônimo ≈ 1 máquina/sessão) | Nome ou conta Google |
| Versão, idioma, Colab × offline | Conteúdo de prompts/notas/vault |
| Funcionalidades usadas (backup, provedores, temas…) | Arquivos, projetos ou caminhos |
| Contagem de eventos por dia/evento | IP completo vinculado à identidade |
| E-mails **somente** via opt-in de contato (Passo 9) — nunca pelo GA4 | E-mail no GA4 (proibido pelos Termos do Google) |

### Passo 8 — Conformidade LGPD (resumo operacional)
- **Base legal (v0.6.10 — desde v0.6.9):** **legítimo interesse (art. 7º, IX)** — contadores anônimos sem cookies,
  ativa por padrão, com direito de oposição a qualquer momento (art. 18, §2º) via caixa da tela de
  Termos ou `UFVAI_TELEMETRY=0`; até a v0.6.8 era consentimento opt-in (art. 7º, I);
- **Identificador:** UUID aleatório gerado localmente (`~/.config/ufvai_cid`), sem tabela de ligação
  a identidades — tratado como dado pessoal por cautela (pseudonimização não afasta a LGPD);
- **Transferência internacional:** Google Analytics (arts. 33–36) — declarada nos Termos v2.0 §5
  e PRIVACY.md; sujeita aos termos do Google;
- **Direitos do titular:** art. 18 atendido via gustavo.braga@ufv.br / DPO UFV (ver PRIVACY.md);
- **Registro das operações:** mantenha este documento + changelog como registro simples (art. 37);
- **Minimização:** só contadores categóricos — nada de conteúdo, caminhos ou identificadores reais.

### Passo 9 — E-mail de contato opt-in (v0.6.6) — para o DESENVOLVEDOR

A telemetria existe para VOCÊ (desenvolvedor/mantenedor) acompanhar adoção — nunca para vigiar o
usuário. Desde a v0.6.6, a tela de Termos oferece um campo **opcional** de e-mail:

| O que acontece | Onde | Base |
|---|---|---|
| Usuário digita o e-mail e clica "Aceitar" | `~/.config/ufvai_profile.json` (chmod 600, com SHA-256 + carimbo) na máquina dele | Consentimento explícito — LGPD art. 7º I |
| Evento `contact_optin` (contador SEM conteúdo) | GA4 — quantos usuários autorizaram contato | Termos do GA4 permitem; nenhum dado pessoal sai |
| O endereço em si chega até você | SOMENTE se você configurar a **URL de contato** (painel 📊 Telemetria desde a v0.6.7, ou `UFVAI_CONTACT_ENDPOINT`). POST JSON: `{product, email, name, email_sha256, ip, environment, app_version, sent_at, flag}` (`flag=novo_contato|usuario_ativo`) | Consentimento com finalidade declarada |

⚠️ **Nunca** envie o e-mail (bruto ou com hash) para o Google Analytics — viola os Termos do
Google e pode derrubar sua propriedade. O canal do e-mail é separado do canal analítico.

#### Opção A (recomendada) — Planilha + Apps Script (Google · grátis · ~3 min)

Os endereços caem numa **planilha sua no Google Drive** — mesmo ecossistema do Colab, zero
servidor, zero custo, dado sob controle do titular (LGPD-friendly).

1. Abra a planilha de contatos do projeto (ID atual `1TWVuKtAp…` — planilha v0.6.10+ com 8 colunas `Data/hora · E-mail · Nome · SHA-256 · Ambiente · Versão · Flag · IP`; se usar outra, crie em [sheets.new](https://sheets.new));
2. Menu **Extensões → Apps Script**, apague tudo e cole o arquivo pronto
   **`docs/APPS_SCRIPT_PLANILHA_CONTATO.gs`** (v0.6.10+, 8 colunas; cria sozinho a aba
   **"Contatos UFVAI"** com cabeçalho: Data/hora · E-mail · Nome · SHA-256 · Ambiente · Versão · Flag[novo_contato|usuario_ativo] · IP — com migração automática de planilhas antigas de 6 colunas — sem tocar nas outras abas).

   *(Para outra planilha: troque `SHEET_ID` no topo do script pelo trecho
   entre `/d/` e `/edit` na URL dela.)*
3. **Implantar → Nova implantação → tipo "App da Web"** → *Executar como:* **Eu**;
   *Quem pode acessar:* **Qualquer pessoa** → **Implantar** (na 1ª vez o Google pedirá
   autorização OAuth da SUA conta — normal) → copie a URL terminada em `/exec`;
4. Cole a URL no painel 📊 Telemetria (Admin) → campo **"✉️ URL de contato"** → Salvar.
   Alternativa por arquivo: `export UFVAI_CONTACT_ENDPOINT="https://script.google.com/macros/s/…/exec"`
   no `~/PesquisAI/config/ufvai.env` (offline) ou nas variáveis do ambiente Colab.
5. Teste: `curl -X POST -H "Content-Type: application/json" -d '{"email":"teste@teste"}' "<sua_url>/exec"` — deve surgir uma linha na planilha.

> 💡 Para receber um **e-mail** a cada novo contato sem abrir a planilha: dentro do Apps Script,
> adicione `MailApp.sendEmail("gustavo.braga@ufv.br", "Novo contato UFVAI", d.email);`
> antes do `return` (cota gratuita do Gmail: ~100 e-mails/dia).

#### Opção B (avançada) — servidor open-source próprio (self-hosted)

Se preferir não depender de nuvem nenhuma: qualquer serviço open-source que aceite webhook
HTTP serve — ex.: **Gotify** ou **ntfy** auto-hospedados (notificação no celular), ou um
Flask/FastAPI seu gravando em SQLite. Basta expor uma URL HTTPS que responda ao POST JSON e
colá-la no painel, igual à Opção A. Requer manutenção própria (VPS/domínio/TLS) — por isso a
Opção A segue sendo a recomendada para uso pessoal.

Configuração pela UI (v0.6.7): painel **📊 Telemetria (Admin)** → campo "✉️ URL de contato".
Deixar vazio = usuários NÃO são encaminhados (fica só o contador anônimo `contact_optin` no GA4).

O usuário pode revogar a qualquer momento: apagando o campo na tela de Termos, removendo
`~/.config/ufvai_profile.json` ou chamando `POST /api/contact/delete` (LGPD art. 18, VI).

> 💡 **Dica de leitura dos relatórios:** em *Explorar → Exploração de forma livre*, use o dimensão
> `client_id` (como "ID do usuário") para contar instalações distintas e cruzar com eventos —
> cada `app_started` novo de um client_id ainda não visto = nova instalação ativa.

---

## 1. Visão geral

| Aspecto | Como é |
|---|---|
| **Padrão (v0.6.10)** | ✅ **Ativa por padrão (opt-out)** — contadores anônimos, sem cookies; o usuário pode se opor a qualquer momento (`UFVAI_TELEMETRY=0` ou desmarcar a caixa na tela de Termos) — LGPD art. 7º IX + art. 18 §2º |
| **Canais (v0.6.10)** | 🖥️ **gtag.js client-side** (`page_view` padrão, SEM cookie `_ga`, gate: aceite dos Termos v2.1 e não-oposição) + 📡 **Measurement Protocol server-side** (eventos do app) |
| **Configuração pela UI** | Painel **📊 Telemetria (Admin)** na barra superior — cola ID + Secret + URL de contato (v0.6.7) sem editar arquivos (grava `~/.config/ufvai_telemetry.json`, chmod 600) |
| **Consentimento/oposição** | Caixa de telemetria na tela de Termos (marcada = ativa); desmarcá-la ou `UFVAI_TELEMETRY=0` desliga (opt-out) |
| **Tecnologia** | GA4 **Measurement Protocol** (envio *server-side*, sem cookies no navegador) |
| **Conteúdo enviado** | Nome do evento + parâmetros não-pessoais (tabela §3); client-side limitado ao `page_view` padrão (evento custom `ufvai_session` removido na v0.6.9; v0.6.10 adiciona `name`+`ip` e flag por acesso) |
| **O que NUNCA vai** | Prompts, respostas da IA, notas do vault, caminhos de arquivo, chaves de API, e-mails, IDs de conta Google |
| **Identificador** | UUID aleatório gerado localmente (`~/.config/ufvai_cid`) — não é vinculado a ninguém |
| **Kill-switch global** | `export UFVAI_TELEMETRY=0` desliga mesmo com consentimento ativo |
| **Código** | `pesquisai/telemetry.py` (~140 linhas, sem dependências externas) |

---

## 2. Fluxo completo (da instalação ao envio)

```
┌───────────────────────────────────────────────────────────────┐
│ 1ª execução no Colab                                          │
│   └─ launch() gera token de sessão e injeta o wrapper HTML    │
│      └─ Tela de Termos aparece (overlay bloqueante)           │
│                                                               │
│ Usuário marca:                                                │
│   [ ] Li e aceito os Termos (obrigatório p/ usar a UI)        │
│   [x] Opcional: permitir estatísticas anônimas  ← CONSENTIMENTO│
│   [Aceitar e começar]                                         │
│                                                               │
│ Navegador → POST /api/consent {accepted:true, analytics:true} │
│   ├─ Servidor grava ~/.config/ufvai_consent.json              │
│   │    {"accepted": true, "analytics": true, "version":...}   │
│   └─ telemetry.set_consent(True)                              │
└───────────────────────────────────────────────────────────────┘
                          │
                          ▼  (a partir daqui, eventos podem fluir)
┌───────────────────────────────────────────────────────────────┐
│ Acontecimento no app (ex.: usuário salva um backup)           │
│   └─ handler chama _tel_event("backup_created", {})           │
│      └─ telemetry.event():                                    │
│          1. enabled()?                                        │
│             ├─ UFVAI_TELEMETRY=0?  → descarta                 │
│             ├─ sem GA config?      → descarta                 │
│             └─ sem consentimento?  → descarta                 │
│          2. Monta payload JSON mínimo                         │
│          3. Thread daemon → POST HTTPS (timeout 3 s)          │
│             para google-analytics.com/mp/collect              │
│          Qualquer erro = silêncio total (o app nunca quebra)  │
└───────────────────────────────────────────────────────────────┘
```

---

## 3. Eventos coletados e seus parâmetros

Todos os valores são categóricos/anônimos:

| Evento | Quando | Parâmetros |
|---|---|---|
| `app_started` | `launch()` conclui | `version`, `lang` (idioma), `colab` (true/false) |
| `terms_accepted` | aceite dos Termos | `analytics` (true/false — se o próprio opt-in foi marcado) |
| `provider_saved` | chave de provedor salva | `provider` (nome curto: `openai`, `gemini`…) |
| `provider_deleted` | chave removida | `provider` |
| `backup_created` | backup de sessão gravado no Drive | — |
| `session_restored` | sessão importada/restaurada | — |
| `lang_changed` | idioma trocado na UI | `lang` |
| `theme_changed` | tema claro/escuro | `theme` |
| `memory_note_saved` / `_created` / `_deleted` | operações na memória Obsidian | — |

> 🔍 **Auditoria:** cada chamada está visível com grep —
> `grep -rn "_tel_event" pesquisai/launch_app.py`

---

## 4. As duas condições (todas obrigatórias para enviar)

```python
def enabled() -> bool:
    if kill_switch_active():   return False   # UFVAI_TELEMETRY=0 (oposição do usuário)
    if not configured():       return False   # faltam UFVAI_GA_* no ambiente
    return consented()                        # ~/.config/ufvai_consent.json.analytics == true
```

> **v0.6.9:** o antigo item "consentimento opt-in" tornou-se **não-oposição** — a caixa de
> telemetria vem marcada (ativa por padrão, base legítimo interesse art. 7º IX, sem cookies);
> desmarcá-la registra a oposição (art. 18 §2º) e desliga imediatamente.

1. **Sem kill-switch / sem oposição** — `UFVAI_TELEMETRY=0` ou desmarcar a caixa vencem tudo.
2. **Com configuração do mantenedor** — o dono do projeto precisa definir as variáveis de ambiente:
   - `UFVAI_GA_MEASUREMENT_ID` (ex.: `G-XXXXXXXXXX`)
   - `UFVAI_GA_API_SECRET` (gerado no GA4: Admin → Data Streams → Measurement Protocol API secrets)
   
   Sem elas, a telemetria fica **inativa mesmo com consentimento** (privacidade por padrão em implantações terceiras).

   **Como definir no modo offline (.deb) — v0.6.2+:** crie o arquivo `~/PesquisAI/config/ufvai.env` (o launcher carrega-o antes de iniciar):
   ```bash
   mkdir -p ~/PesquisAI/config
   cat > ~/PesquisAI/config/ufvai.env <<'EOF'
   export UFVAI_GA_MEASUREMENT_ID=G-XXXXXXXXXX
   export UFVAI_GA_API_SECRET=SEU_SEGREDO_AQUI
   EOF
   chmod 600 ~/PesquisAI/config/ufvai.env
   ```
3. ~~Com consentimento do usuário~~ — **(v0.6.9) incorporado ao item 1:** a caixa de telemetria
   vem **marcada** (opt-out); desmarcá-la registra a oposição e desliga (`consented() == False`).

### Testando (DebugView — v0.6.2+ · parâmetro corrigido na v0.6.9)
1. No GA4: **Admin → DebugView** (deixe a página aberta).
2. Ative o modo debug e reinicie: `export UFVAI_TELEMETRY_DEBUG=1` antes de iniciar o UFVAI.
3. Os eventos (`terms_accepted`, `app_started`, `lang_changed`…) aparecem em tempo real no DebugView; **não gravam relatórios**. Sem a flag, os eventos vão para Relatórios → Tempo real (até alguns minutos de atraso).

> ⚠️ v0.6.9 corrige um bug da v0.6.2: o modo debug usava o parâmetro de URL `&debug_view=1`
> (ignorado pelo GA4); agora envia `"debug_mode": 1` nos params do evento, como exige o
> Measurement Protocol.

> ⚠️ O Measurement Protocol exige internet. No modo 100% offline os eventos são descartados silenciosamente (thread daemon, timeout de 3 s).

---

## 5. Dois canais, uma única condição de aceite (v0.6.4 · revisado v0.6.9)

Desde a v0.6.4 o UFVAI usa **canal duplo**, condicionado à mesma tela de Termos. Desde a **v0.6.10** (v0.6.9 já tinha opt-out)
o canal client-side é limitado ao `page_view` padrão (**sem** evento custom e **sem** cookie `_ga`):

| Canal | O que envia | Quando dispara |
|---|---|---|
| 🖥️ **gtag.js client-side** (`G-CMVTFP2M6F`) | Apenas `page_view` padrão — **sem cookie `_ga`** (`analytics_storage:'denied'`) e **sem** `ufvai_session` (removido na v0.6.9; v0.6.10 adiciona `name`+`ip` e flag por acesso) | Após aceite dos Termos (versão vigente) **sem** oposição à telemetria; recarregar mantém o estado salvo |
| 📡 **MP server-side** (mesmo ID) | Eventos de aplicação (`app_started`, backups, provedores…) via Python | A cada evento, se `enabled()` |

O gtag usa `anonymize_ip:true`. Com oposição registrada (caixa desmarcada), **nenhum script do
googletagmanager é carregado** — não há requisição, nem cookie, nem ping.

---

## 6. Histórico — por que também existe Measurement Protocol (server-side)?

> A v0.6.0 usava apenas MP (sem cookies no navegador). Com o painel Admin da v0.6.4 o projeto
> passou a operar os dois canais; a comparação abaixo permanece válida para entender as escolhas:

| Critério | MP server-side (escolhido) | gtag client-side |
|---|---|---|
| Cookies no navegador | **Nenhum** (_cid é UUID local) | Cookies `_ga` |
| Banner LGPD necessário | Consentimento já coberto pela tela de Termos | Banner dedicado recomendado |
| Bloqueadores de anúncios | Não interferem | Podem bloquear o script |
| Página carregada dentro do iframe Colab | Irrelevante (envio vem do Python) | Comportamento varia |
| Dados técnicos do browser (resolução etc.) | **Não coleta** | Coleta por padrão |
| Esforço de manutenção | 1 módulo Python | Snippet + CSP + testes de UI |

Trade-off honesto: perdemos métricas de *sessão/navegador* (tempo na página etc.). Ganhamos privacidade máxima e zero impacto no carregamento da UI. Métricas de audiência do **site** continuam podendo usar GA4 web à parte.

---

## 6. Como desligar (usuário)

1. **Na origem:** recusar o checkbox "estatísticas anônimas" na tela de Termos;
2. **Depois:** apagar `~/.config/ufvai_consent.json` ou regravar `"analytics": false`;
3. **Global/imediato:** `export UFVAI_TELEMETRY=0` (funciona até com consentimento ativo);
4. **Rede:** bloquear o domínio `www.google-analytics.com` — o módulo falha silenciosamente.

## 7. Como verificar (transparência)

```bash
# Estado atual do consentimento
cat ~/.config/ufvai_consent.json

# ID anônimo desta máquina
cat ~/.config/ufvai_cid

# Todos os pontos de coleta no código
grep -rn "_tel_event\|telemetry" pesquisai/ --include="*.py"
```

---

## 8. Garantias de projeto (resumo normativo, v0.6.9+ opt-out)

- ✅ Oposição fácil a qualquer momento — telemetria **ativa por padrão sem cookies** (LGPD art. 7º, IX + art. 18, §2º); ativação exige nome+e-mail+IP (art. 7º, V, Termos v2.2)
- ✅ Minimização de dados (nenhum dado pessoal/conteúdo trafega)
- ✅ Finalidade declarada (métricas agregadas de uso das funcionalidades)
- ✅ Revogação fácil a qualquer momento
- ✅ Fail-safe: telemetria nunca afeta funcionamento, performance perceptível ou estabilidade
- ❌ Não usa cookies de rastreamento, fingerprinting ou publicidade

*Dúvidas ou sugestões: abra uma issue em github.com/gustavobraga-byte/PesquisAI.*
