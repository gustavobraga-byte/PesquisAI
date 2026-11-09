

<div align="center">

![UFVAI](assets/logo.svg#gh-light-mode-only)
![UFVAI](assets/logo.svg#gh-dark-mode-only)

# UFVAI — Inteligência que acelera a ciência

**Agente de IA para pesquisa científica · Universidade Federal de Viçosa**

[![Site oficial](https://img.shields.io/badge/🌐_Site-ufvaisite-2E3242?style=for-the-badge)](https://der.ufv.br/ufvai/)
[![Abrir no Colab](https://img.shields.io/badge/▶️_Começar_agora-Google_Colab-brightgreen?style=for-the-badge)](https://colab.research.google.com/github/gustavobraga-byte/versaoteste/blob/main/PesquisAI.ipynb)
[![Apresentação](https://img.shields.io/badge/📊_Slides-ver_apresentação-C9A227?style=for-the-badge)](https://der.ufv.br/ufvai/#apresentacao)

[![Versão](https://img.shields.io/badge/versão-0.7.11-orange.svg)]() [![Licença MIT](https://img.shields.io/badge/licença-MIT-blue.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/) [![SisPPG/UFV](https://img.shields.io/badge/SisPPG-10356285004-blue.svg)](http://sisppg.ufv.br) [![LGPD](https://img.shields.io/badge/LGPD-conforme-success.svg)](PRIVACY.md)

> Consulta dados oficiais do Brasil e literatura validada, cita cada fonte e declara honestamente quando não há evidência suficiente.

[🌐 Site](https://der.ufv.br/ufvai/) · [📓 Colab](https://colab.research.google.com/github/gustavobraga-byte/versaoteste/blob/main/PesquisAI.ipynb) · [📘 Manual](MANUAL.md) · [📜 Termos v3](docs/TERMS_OF_USE.md) · [🔒 Privacidade v1.1](PRIVACY.md) · [📊 Telemetria](TELEMETRY.md) · [📝 Changelog](CHANGELOG.md)

</div>

---

## 📑 Sumário

- [Por que o UFVAI?](#-por-que-o-ufvai)
- [Capacidades](#-capacidades)
- [Início rápido](#-início-rápido)
- [Offline (.deb Linux)](#-offline-deb-linux)
- [Skills](#️-skills)
- [Novidades](#-novidades)
- [Arquitetura](#️-arquitetura)
- [Privacidade e Termos](#-privacidade-e-termos)
- [Citação](#-citação)
- [Idiomas](#-idiomas)
- [Estrutura do repositório](#-estrutura-do-repositório)
- [Contribuir](#-contribuir)
- [Contato](#-contato)

---

## 🧠 Por que o UFVAI?

O **UFVAI** (marca) roda sobre o motor **PesquisAI** (este código, arquitetura OpenCode) e atua como um **pesquisador sênior remoto**: metódico, transparente sobre incertezas e comprometido com a integridade científica.

| Princípio | Como funciona |
|---|---|
| 🚫 **Zero fabricação** | Nada de dados, DOIs ou autores inventados. Sem evidência → `[SEM DADOS SUFICIENTES]` |
| 🏷️ **Evidência marcada** | Toda afirmação quantitativa porta `[DADO CONFIRMADO]` · `[ESTIMATIVA FUNDAMENTADA]` · `[SEM DADOS SUFICIENTES]` |
| 📚 **Referência validada** | Toda referência exige DOI/ISBN/ISSN/URL oficial e passa por `citation-management` |
| 🧾 **Trilha auditável** | Parâmetros, código e proveniência salvos na *Minha memória* (vault Obsidian no seu Drive) |
| ⚖️ **ABNT por padrão** | Normalização UFV/ABNT NBR 14724 · 6023 · 10520 (APA/Vancouver sob pedido) |

> 🚨 **Atenção:** ferramenta de apoio — **não substitui** revisão por pares nem o julgamento humano. Sempre revise. Sugira a [Declaração de Uso de IA](declaracao_uso_ia.md) nas entregas finais.

📖 **Conheça em 2 minutos:** [site oficial](https://der.ufv.br/ufvai/) (demonstração animada do boot → Termos → tela principal) · [slides](https://der.ufv.br/ufvai/#apresentacao) · [vídeo tutorial](https://www.youtube.com/watch?v=8e8spp_7Gq4).

---

## ✨ Capacidades

| Área | O que faz |
|------|-----------|
| 📊 **Dados IBGE/SIDRA** | Censo, PNAD, PIB, PAM/LSPA — demografia, território, economia |
| 🏥 **DataSUS** | Mortalidade, internações, vacinação, SRAG, SINAN (139 datasets) |
| 🌾 **Agro & Ambiente** | CONAB, preços Cepea, CAR/SICAR, PRODES/DETER, queimadas INPE, crédito rural |
| 🇧🇷 **Dados Brasil** | BCB, TSE, Transparência, INEP, ANA, ANP e dezenas de APIs oficiais |
| 🌦️ **Clima BR-DWGD** | Normais climatológicas e séries municipais gradeadas 0,1° |
| 📚 **Literatura** | Meta-busca em 7 bases (PubMed, SciELO, LILACS, BDTD, OpenAlex, arXiv, bioRxiv/medRxiv) com deduplicação por DOI |
| 🧪 **Métodos** | EDA, estatística com laudo APA, poder amostral, ML, qualitativa (Reinert/AFC/CHD) |
| ✍️ **Escrita** | IMRAD, revisão sistemática, memorial RSC-PCCTAE UFV, documentos CEP/UFV |
| 📐 **ABNT/UFV** | Capa, citações, referências, sumário no padrão UFV |
| 🧠 **Memória** | Vault Obsidian no seu Drive — notas, hipóteses, referências, MOCs |

---

## 🚀 Início rápido

### Opção 1 — Google Colab (recomendada, ~2 min)

1. Clique em **Começar agora** (badge no topo) ou acesse o [notebook](https://colab.research.google.com/github/gustavobraga-byte/versaoteste/blob/main/PesquisAI.ipynb);
2. No Colab: **Ambiente de execução → Executar tudo** (`Ctrl+F9`);
3. Aguarde a tela com a logomarca do UFVAI (~2 min) e clique em **ABRIR O UFVAI**;
4. Na primeira vez: aceite os **Termos v2.2** informando **nome + e-mail** (LGPD art. 7º, V). Nas próximas: **"Bem-vindo de volta"** → *Continuar* (registra 1 linha `usuario_ativo` por clique).

### Opção 2 — Local (`uv`, desenvolvedores)

```bash
git clone https://github.com/gustavobraga-byte/versaoteste.git
cd PesquisAI
uv sync
# consulte o MANUAL.md para detalhes
```

---

## 📴 Offline (.deb Linux)

Funciona **100% offline** em Debian/Ubuntu com LLM local (Ollama). Ideal para sigilo ou sem internet.

```bash
# amd64 (x86_64)
wget https://github.com/gustavobraga-byte/versaoteste/raw/main/debs/pesquisai_0.7.11-web2_amd64.deb -O /tmp/pesquisai.deb && \
sudo apt install /tmp/pesquisai.deb -y && rm /tmp/pesquisai.deb

ufvai --doctor          # confere Python, ttyd, motor e portas
ufvai --engine-install  # instala o motor OpenCode 2.x (sem sudo)
ufvai                   # abre a interface em http://localhost:8001
```

> ℹ️ **`.deb` 0.7.11 (06/11/2026):** empacotado a partir da árvore **0.7.11** e validado
> contra o **OpenCode 2.2.5** (motor V2). Há pacotes **amd64** e **arm64**; o ttyd vai
> embutido e as dependências Python vêm do `apt` (sem `pip` no postinst). O motor
> **não** é embutido (~240 MB) — instale com `ufvai --engine-install`.



| Requisito | Especificação |
|-----------|---------------|
| **SO** | Debian 11+ / Ubuntu 22.04+ (amd64 ou arm64) |
| **Python** | 3.10+ (`python3`, `python3-cryptography`, `python3-requests`, `python3-bs4`, `python3-yaml`) |
| **Motor** | OpenCode V2 (2.2.x; validado em 2.2.5) |
| **RAM** | 4 GB mín. · 8 GB+ recomendado (16 GB+ p/ contexto 262k) |
| **Disco** | 500 MB livres (+ ~250 MB do motor) |
| **Portas** | `8000` (terminal) · `8001` (interface) · `11434` (Ollama) |

```bash
# LLM local (exemplo 262k)
curl -fsSL https://ollama.com/install.sh | sh
ollama pull qwen3:4b-instruct-2507-q4_K_M   # 262k nativo, ~2,5 GB
```

> 📖 Guia completo, solução de problemas e modelos recomendados: [`debs/README.md`](debs/README.md).

---

## 🛠️ Skills

O agente opera por *skills* — cada uma conecta a uma fonte ou capacidade.

| Skill | Descrição |
|-------|-----------|
| `ibge-br` | IBGE/SIDRA, malhas, CNAE |
| `opendatasus` | OpenDataSUS/SUS (139 datasets) |
| `dados-brasil` | BCB, TSE, Transparência, INEP, ANA… |
| `agrobr` | Agro brasileiro (38+ fontes) |
| `BR-DWGD` | Clima gradeado BR |
| `ufv-abnt` | Normalização ABNT/UFV |
| `analise-qualitativa` | Conteúdo/Reinert/codificação |
| `citation-management` | Validação DOI/ISBN (obrigatória) |
| `meta-search-br` | Meta-busca 7 bases acadêmicas |
| `memorial-ufv` / `pdf-to-memorial-rsc` | Memorial RSC-PCCTAE |
| `cep-ufv` | Pacote documental CEP/UFV |
| `grant-finder` | Editais BR + internacionais |
| `obsidian-memory` | Minha memória (vault Obsidian) |
| `scientific` | Pacote K-Dense (140+ subskills) |

---

## 🆕 Novidades

**v0.7.11 — 🛡 VPN da UFV no Colab (OpenVPN em namespace isolado)** — o servidor do Colab passa a alcançar a rede da UFV pela VPN institucional sem `CAP_NET_ADMIN`: **OpenVPN dentro de user+net namespace** + `slirp4netns` + **proxy SOCKS5 local** (`socks5h://127.0.0.1:1081`). Na abertura, a tela **“Você é aluno(a) da UFV?”** leva ao painel de **CPF + senha** do portal `vpn.ufvnet.ufv.br`; a senha nunca vai para logs e, se “lembrar”, fica **cifrada no Drive**. Split tunnel (só a rede da UFV), aviso de **1 dispositivo por CPF** e teste de acesso interno (`sistemas.ufv.br`). **Modo total** opcional: com `redirect-gateway`, o serviço do OpenCode + terminal rodam dentro do namespace e todo o agente sai pela UFV; **encaminhador de porta** para um modelo local (Ollama/vLLM) da intranet (`127.0.0.1:11435` → `10.0.0.10:11434`). No onboarding, **Google Gemini** entra no seletor **🎛️ Modelo gratuito padrão** e uma opção **“Outro provedor”** lista **OpenAI, Anthropic, Groq, Mistral, DeepSeek, Together, Fireworks, xAI e Cohere** para colar a própria chave. A pergunta da VPN vem **antes** do provedor/chave. Guia: [`docs/VPN_UFV.md`](docs/VPN_UFV.md).

**v0.7.10 — 🧭 Onboarding de primeiro uso (provedor + chave)** — sem chave, depois dos Termos o usuário escolhe **já tenho** ou **não tenho / não sei**; opções **Google Gemini (recomendado)**, **NVIDIA**, **OpenRouter** e **OpenCode Go (pago)** com tutorial, link e campo de colar; chave do Google → `GOOGLE_GENERATIVE_AI_API_KEY` e modelo padrão **Gemini Flash-Lite Latest · high**; plugin de **retry automático** em 429 (espera ~62 s).


<details>
<summary>Histórico completo (0.7.x → 0.6.0)</summary>

| Versão | Data | Destaques |
|--------|------|-----------|
| **0.7.11** | 06/11/2026 | 🛡 **VPN da UFV no Colab** — OpenVPN em **namespace isolado** (`unshare -Urn` + `slirp4netns`) + **SOCKS5** em `127.0.0.1:1081`; tela inicial **“Você é aluno(a) da UFV?”** e painel **CPF/senha**; credenciais cifradas opcionais; split tunnel e aviso de 1 dispositivo por CPF (`GET /api/vpn`, `POST /api/vpn/*`) |
| **0.7.10** | 05/11/2026 | 🧭 **Onboarding de primeiro uso** — depois dos Termos, o usuário sem chave escolhe **"já tenho provedor"** ou **"não tenho / não sei"**; as opções trazem **Google Gemini (recomendado, grátis)**, **NVIDIA**, **OpenRouter** e **OpenCode Go (pago)**, cada uma com tutorial, link e campo para colar a chave; chave do Google vira `GOOGLE_GENERATIVE_AI_API_KEY` e o padrão é o **Gemini Flash-Lite Latest · high** (`GET /api/onboarding`, `POST /api/onboarding/key`) |
| **0.7.9** | 04/11/2026 | 🔑 **Chaves de API e free tier** — o modal de Provedores mostra **como obter chave gratuita** (OpenRouter `:free` e NVIDIA) quando não há nenhuma salva; **seletor de gratuitos** e **modelo padrão** (`/api/free_models`, `/api/default_model`); aviso de responsabilidade na abertura ([`docs/CHAVES_API.md`](docs/CHAVES_API.md) · [guia visual em HTML](docs/chaves-api-tutorial.html)) · 💾 **⚙ Autosave** com intervalo (1–60 min) e escopo (ativa / todas / escolhidas) |
| **0.7.8** | 29/10/2026 | 🔑 **Chaves do Drive no serviço do motor (OpenCode v2.2)** — `ensure_service_project_dir()` injeta as chaves no `env` do `opencode serve` e no boot; **auto-cura** reinicia o serviço nascido sem chaves; salvar/remover chave reergue o serviço já atualizado; `scripts/diag_keys_v22.py` · ⌨️ **Ctrl+C copia / Ctrl+V cola** no terminal (ttyd + xterm.js), com arrasto→seleção sob *mouse reporting* |
| **0.7.7** | 27/10/2026 | 🔒 **Drive Guard** — o agente não acessa mais “My Drive” fora de `My Drive/PesquisAI` (nem com `--auto`): regras `permissions` com `deny` **final** + hooks `permission.evaluate` e `tool.execute.before`; alias `MyDrive`, `..`, `file://`, `~` e comandos de shell resolvidos; falha fechada em referência ofuscada; auditoria em `~/.local/state/ufvai/drive-guard.log` |
| **0.7.6** | 24/10/2026 | 🏷️ **Rebrand do agente: opencode → ufvai** — as Diretrizes (`AGENTS.md` + `agents/*` nos 5 idiomas + **novo** `agents/UFVAI.md`) agora se referem ao motor como **UFVAI** em todos os caminhos e comandos (`~/.config/ufvai/`, `ufvai.json`, `~/.local/share/ufvai/`, `ufvai auth export`); novo `scripts/ufvai-alias.sh` cria os symlinks e o comando `ufvai` por cima do motor físico, sem tocar no runtime (banco/crédenciais intactos) |
| **0.7.5** | 23/10/2026 | 🪟 **Telas de abertura e retomada uma vez por sessão** — a marca "já mostrei" passou a ser gravada em **três camadas** (sessionStorage + localStorage com 12 h + cookie de sessão), **antes** de exibir; recargas internas não a consomem e o botão **↻** reoferece a pergunta · 🧊 **`Cache-Control: no-store`** no HTML (o navegador não reutiliza o JS antigo) |
| **0.7.4** | 23/10/2026 | 💾 **Autosave de todas as conversas** — por padrão grava **só a sessão ativa** (e só quando ela muda); o botão **"Todas as conversas"** no rodapé liga o modo completo, em que **cada conversa** viva que tenha conteúdo novo recebe o seu próprio arquivo (`backups/autosave/sessions/<id>.json`) e todas aparecem no modal **Restaurar** · 🔓 **Free tier do Zen na restauração** (id da sessão no formato nativo) · 🪟 **Telas de abertura uma vez por entrada** |
| **0.7.3** | 23/10/2026 | 🔓 **Free tier do OpenCode Zen na restauração corrigido** — a causa era o **formato do id** da sessão importada (`ses_` + 16 hex): o gateway do Zen recusava com **403** `OpenCode's free tier can only be used from within OpenCode` em **qualquer modelo gratuito** (confirmado por reprodução controlada); agora o id nasce no **formato nativo** (`ses_` + 12 hex + 14 base62) e a sessão restaurada é **ajustada ao contexto do modelo** (`fit` na resposta do `/api/restore`) · 🪟 **Telas de Termos / "Bem-vindo de volta" uma vez por entrada** (a detecção de idioma e o fim da restauração não reabrem mais a tela de e-mail) |
| **0.7.3** | 22/10/2026 | 📦 **Pacote `pesquisai` instalado no ambiente** (o boot do Colab faz `pip install -e` e prova a API do autopilot a partir de um CWD neutro) · ⏱️ Autosave a cada **1 minuto** · 🗂️ **Fallback das 3 últimas interações** (`autosave_4..6` preservam o backup da conversa anterior) · 🔄 **Retomada uma vez na entrada, sem loop** (máquina de estados em `sessionStorage`) · 🔧 Autosave na sessão do **terminal** e chave estável (o `id` é re-gerado a cada reinício) |
| **0.7.2** | 22/10/2026 | 🔄 **Retomada do autosave uma única vez por aba** (flag `sessionStorage`; fim do laço restore → reload → pergunta) · 📅 **Calendário do "Restaurar" corrigido** (chips dos meses com backup, contagem nos dias, tooltip, item sem data visível) |
| **0.7.1** | 22/10/2026 | 🔧 Retomada do autosave corrigida na entrada · 💾 Autosave sem duplicata (3 slots = 3 versões distintas) · 🗑 Botão de apagar backup · 🔁 Fallback na retomada (até 3 autosaves) |
| **0.7.0** | 21/10/2026 | 🏷️ Marca **UFVAI** na tela de nova sessão · 🇨🇳 Chinês também troca o terminal · 🎨 Manual e Diretrizes no tema claro · 📱 "Idioma" fora do sanduíche · ⏱️ Autosave a cada 3 min + menu "Restaurar" com calendário |
| **0.6.21** | 13/10/2026 | 🔧 Motor **OpenCode V2**  · 🍪 aviso de cookies de terceiros **só quando o bloqueio é detectado**  |
| **0.6.20** | 01/10/2026 | Boot simplificado (ipynb: clone + run + keep-alive subprocesso) + botão SAIR com confirmação (runtime.unassign) |
| **0.6.19** | 29/09/2026 | Menu mobile sem SVG + hamburger à direita no mobile (fix `.sep` `flex:1`) + teste de cascata + docs em paridade (§2.1.0) |
| **0.6.18** | 19/09/2026 | Skills personalizadas (`backups/skills-personalizadas/`) |
| **0.6.17** | 01/09/2026 | Memória instantânea (singleton + warm-up + prefetch) |
| **0.6.16** | 01/09/2026 | Retorno = 1 linha apenas no clique |
| **0.6.15** | 01/09/2026 | Prompt inicial respeita idioma detectado |
| **0.6.14** | 01/09/2026 | IP real (ipify) + todo acesso logado |
| **0.6.13** | 01/09/2026 | IP real + heartbeat revisita |
| **0.6.12** | 01/09/2026 | Preview da memória no mobile |
| **0.6.11** | 01/09/2026 | Hotfix isoformat cache BM25 |
| **0.6.10** | 01/09/2026 | Nome+IP, planilha 8 cols, cache BM25, mobile |
| **0.6.9** | 25/08/2026 | Termos v2.1, e-mail obrigatório, opt-out, .deb |
| **0.6.8** | 24/08/2026 | Contato via planilha + Apps Script |
| **0.6.7** | 23/08/2026 | Painel de boot temático + contato configurável |
| **0.6.6** | 22/08/2026 | Favicon, contato opt-in, Sheets |
| **0.6.5** | — | ⛔ VETADA (launcher regressivo) |
| **0.6.4** | 22/08/2026 | Marca UFVAI, temas, logo, Termos v2 |
| **0.6.0** | 21/08/2026 | Rebrand, segurança, telemetria opt-in, zh_CN |

</details>

Histórico detalhado: [`CHANGELOG.md`](CHANGELOG.md) · Novidades do site: [ufvaisite/#novidades](https://der.ufv.br/ufvai/#novidades).

---

## ⚙️ Arquitetura

```
Google Colab (ou .deb offline)
└── ttyd :8000 (terminal web)
    └── opencode (runtime do agente)
        ├── ibge-br · opendatasus · dados-brasil · agrobr · BR-DWGD
        ├── citation-management · meta-search-br · grant-finder
        ├── ufv-abnt · analise-qualitativa · scientific
        ├── memorial-ufv · cep-ufv · pyzotero · markitdown
        └── obsidian-memory ← Minha memória (vault no seu Drive)
```

Interface web `:8001` (Colab) com tela de Termos v2.2 (nome+e-mail+IP, opt-out) e painel Admin/Telemetria. Offline: `~/PesquisAI/vault/` · `~/PesquisAI/backups/` · `~/PesquisAI/config/ufvai.env`.

---

## 🔒 Privacidade e Termos

- **Ativação:** nome + e-mail obrigatórios (LGPD art. 7º, V) + IP de registro — elimináveis a qualquer tempo (art. 18, VI). Planilha 8 colunas; retorno = 1 linha `usuario_ativo` por clique.
- **Telemetria:** ativa por padrão **sem cookies** (art. 7º, IX, opt-out) — só contadores anônimos GA4; nunca nome/e-mail/IP/conteúdo. Desligue com `UFVAI_TELEMETRY=0` ou desmarcando a caixa.
- **Documentos vigentes:** [Termos v2.2](docs/TERMS_OF_USE.md) · [Privacidade v1.1](PRIVACY.md) · [Telemetria](TELEMETRY.md) · [Licença MIT + NOTICE marca](LICENSE).
- O aceite é registrado localmente; nada da Minha memória sai do seu Drive/máquina (exceto prompts ao provedor de LLM escolhido, sob os termos dele).

---

## 📚 Citação

**ABNT NBR 6023:**

```
BRAGA, Gustavo Bastos. UFVAI: agente de inteligência artificial para pesquisa
científica. Versão 0.7.11. Viçosa: Universidade Federal de Viçosa, 2026.
Disponível em: https://colab.research.google.com/github/gustavobraga-byte/versaoteste/.
Acesso em: DD mês. AAAA.

Projeto registrado no SisPPG/UFV sob nº 10356285004.
Verificar autenticidade em: http://sisppg.ufv.br
```

**BibTeX:**

```bibtex
@software{braga2026ufvai,
  author       = {Gustavo Bastos Braga},
  title        = {{UFVAI}: Agente de Intelig{\^e}ncia Artificial
                  para Pesquisa Cient{\'\i}fica},
  year         = {2026},
  version      = {0.7.11},
  institution  = {Universidade Federal de Vi{\c{c}}osa (UFV)},
  url          = {https://colab.research.google.com/github/gustavobraga-byte/versaoteste/}
}
```

Site para divulgar: `https://der.ufv.br/ufvai/`. Modelos de declaração de IA: [`declaracao_uso_ia.md`](declaracao_uso_ia.md). Como citar dados: [`citacao_pesquisai.md`](citacao_pesquisai.md).

---

## 🌐 Idiomas

🇧🇷 pt_BR · 🇺🇸 en_US · 🇪🇸 es_ES · 🇫🇷 fr_FR · 🇨🇳 zh_CN — interface, Termos e diretrizes (`AGENTS.md` + `agents/` em 5 idiomas).

---

## 🗂️ Estrutura do repositório

```
├── PesquisAI.ipynb          # entrada Colab (boot + Termos v2.2 + citação)
├── main.py / pesquisai/     # motor (launch_app, wrapper v041, telemetry, obsidian-memory)
├── assets/                  # logo oficial, ícones, favicons
├── docs/TERMS_OF_USE.md     # Termos v2.2 (nome+e-mail+IP, opt-out)
├── PRIVACY.md               # Privacidade v1.1
├── TELEMETRY.md             # Telemetria GA4 (2 canais, opt-out)
├── MANUAL.md                # Manual completo
├── CHANGELOG.md             # Histórico 0.6.x
├── debs/                    # pacote offline + README
├── i18n/ · agents/ · tests/ · scripts/
└── LICENSE                  # MIT + NOTICE marca UFVAI
```

> 🧹 **Limpeza 10/09/2026:** removidos `__pycache__`/`*.pyc` e `debs/*.bak*` (11 backups); `debs/legado/` preservado como histórico; **não publicar** `IntructionsCEO_paperclip.md` (uso interno) — ver `docs/FILE_AUDIT_2026-08-22.md`.

---

## 🗺️ Roadmap

| Fase | Período | Foco |
|------|---------|------|
| **1 — Base sólida** | Meses 1–3 | CLI, testes, CI/CD, instalação local |
| **2 — Expansão de dados** | Meses 4–7 | IPEA, INEP, Sucupira/CAPES, plugins |
| **3 — Interface** | Meses 8–11 | Editor de artigos, copilot web |
| **4 — Ecossistema** | Meses 12–18 | API pública, SaaS, integração institucional |

---

## 🤝 Contribuir

Contribuições são bem-vindas — especialmente novas skills de dados públicos brasileiros.

```bash
git clone https://github.com/SEU_USUARIO/PesquisAI.git
git checkout -b feature/nova-skill
# desenvolva, teste (pytest) e abra um Pull Request
```

Leia o [`AGENTS.md`](AGENTS.md). Ideias: IPEA, INEP, ANEEL, ANS, IBICT, SciELO/BDTD, traduções, casos de uso.

---

## 📬 Contato

Desenvolvido por **Gustavo Bastos Braga** — Universidade Federal de Viçosa (DER/UFV).

- ✉️ gustavo.braga@ufv.br
- 🐙 [@gustavobraga-byte](https://github.com/gustavobraga-byte)
- 🌐 [Site oficial](https://der.ufv.br/ufvai/)

---

<div align="center">

Feito com 💙 para impulsionar a ciência brasileira · UFVAI v0.7.11 · SisPPG/UFV nº 10356285004

</div>
