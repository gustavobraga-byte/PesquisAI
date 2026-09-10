# 🔒 Privacidade no UFVAI

**Versão:** 1.1 · **Data:** 10/09/2026 · Substitui v1.0 (21/08/2026) · Aplica-se ao UFVAI/PesquisAI v0.6.10+ (Termos v2.2, `terms_version=6`)

## Princípio central

> **Seus dados de pesquisa são seus.** O UFVAI processa notas, relatórios e o vault Obsidian
> **localmente na sua sessão (Colab ou máquina)** e no seu próprio Google Drive. O agente não
> envia conteúdo da memória para serviços externos.

## O que fica no SEU ambiente (nunca sai)

- Todo o vault Obsidian (`My Drive/PesquisAI/vault/`) — notas, hipóteses, referências;
- Prompts enviados ao agente e respostas geradas;
- Relatórios, figuras, datasets produzidos;
- Chaves de API — armazenadas **cifradas com Fernet (AES-CBC+HMAC)** em `backups/keys_store.json`;
  a chave de criptografia fica em arquivo separado (`keys_encryption_key.bin`).

⚠️ Ressalva honesta: quando você usa um provedor de IA (OpenAI, Google, Anthropic…), os prompts
daquela conversa trafegam para aquele provedor sob os termos **dele**. Isso é inerente ao uso de
LLMs em nuvem e não é controlado pelo UFVAI.

## O que pode sair do seu ambiente

| Dado | Destino | Quando | Como desligar |
|---|---|---|---|
| Contadores anônimos de uso (`page_view` padrão; **sem cookie `_ga`** desde v2.1) | Google Analytics 4 (dois canais: página + eventos do app, mesmo ID) | Ativa por padrão (opt-out, LGPD art. 7º IX); desligue a qualquer momento | `UFVAI_TELEMETRY=0` · desmarcar telemetria na tela de Termos · ver `TELEMETRY.md` |
| Requisições a APIs públicas de dados (IBGE/SIDRA, NASA POWER, etc.) | Órgãos/fonte correspondentes | Quando uma skill consulta dados | Inerente à funcionalidade |
| Chamadas ao LLM do provedor escolhido | Provedor configurado por você | A cada interação com o agente | Não usar o provedor |

A telemetria **não inclui**: prompts, respostas, nomes de arquivos/projetos, conteúdo de notas,
endereços de e-mail, identificadores de conta. Desde a v2.1 dos Termos **nenhum cookie `_ga` é
criado** (o gtag roda com `analytics_storage:'denied'` e só envia o `page_view` padrão).
Detalhamento completo: [`TELEMETRY.md`](TELEMETRY.md). O e-mail de **ativação obrigatória**
(v0.6.10 — nome+e-mail obrigatórios, IP capturado; v0.6.9 apenas e-mail; antes opcional na v0.6.6) segue regras próprias — ver seção abaixo;
ele também **nunca** vai para o Google Analytics e pode ser eliminado a qualquer momento
(LGPD art. 18).

## Termos de Uso

Na primeira abertura da interface é exibida a tela de aceite dos Termos de Uso (com link para a
licença MIT). O aceite é registrado localmente (`~/.config/ufvai_consent.json`) e a telemetria,
se você autorizar, também.

## E-mail, nome e IP de contato (v0.6.10+ — obrigatórios para ativação, Termos v2.2)

A tela de Termos exige **nome + e-mail** para ativação. Regras (corrige a v1.0, que descrevia campo opcional):

- **Base legal:** execução do serviço (**LGPD art. 7º, V**) — contato sobre segurança, atualizações e suporte do UFVAI;
- **IP:** capturado no navegador via `api.ipify.org` (fallback `ipinfo.io`) e registrado junto ao contato para segurança/auditoria; nunca vai ao Google Analytics;
- **Finalidade:** exclusivamente contato sobre o UFVAI;
- **Onde fica:** `~/.config/ufvai_profile.json` (chmod 600, com hash SHA-256 + carimbo) + backup persistente `backups/ufvai_consentimento.json` (Drive no Colab · `~/PesquisAI/backups/` offline);
- **Planilha do projeto:** 8 colunas `Data/hora · E-mail · Nome · SHA-256 · Ambiente · Versão · Flag[novo_contato|usuario_ativo] · IP` via webhook `UFVAI_CONTACT_ENDPOINT` (Apps Script `docs/APPS_SCRIPT_PLANILHA_CONTATO.gs` v0.6.10+). Desde v0.6.16, cada retorno gera exatamente 1 linha `usuario_ativo` apenas no clique "Continuar";
- **Google Analytics NUNCA recebe** nome, e-mail ou IP — ao GA4 vão apenas contadores anônimos (ver `TELEMETRY.md`);
- **Eliminação (art. 18, VI):** apague os campos na tela de Termos e salve, remova `~/.config/ufvai_profile.json` + backup, ou chame `DELETE /api/contact/delete` / `POST /api/consent` com eliminação.

## Seus direitos (LGPD)

A telemetria, quando ativa, trata dados pessoais em sentido amplo (o `client_id` aleatório pode,
em tese, ser reidentificado quando combinado a outros dados — por isso tratamos como dado pessoal
e usamos consentimento como base legal). Você tem, nos termos do **art. 18 da LGPD**:

1. Confirmação da existência de tratamento;
2. Acesso aos dados transmitidos (visível no próprio GA4/administração);
3. Correção de dados incompletos ou inexatos;
4. Anonimização, bloqueio ou eliminação de dados desnecessários;
5. Portabilidade;
6. Informação sobre compartilhamento (Google Analytics — transferência internacional, arts. 33–36);
7. Informação sobre a possibilidade de **não consentir** e suas consequências (nenhuma: o app
   funciona integralmente sem telemetria);
8. **Revogação do consentimento** a qualquer momento (`UFVAI_TELEMETRY=0` ou apagar
   `~/.config/ufvai_consent.json` e `~/.config/ufvai_cid`);
9. Oposição ao tratamento.

**Como exercer:** escreva para gustavo.braga@ufv.br (resposta imediata em formato simplificado; 
completa em até 15 dias, art. 19) ou acione o Encarregado institucional da UFV:
https://dgi.ufv.br/privacidade/. Dados que permanecem 100% no seu Drive estão sob seu controle
direto (exclusão, exportação) a qualquer momento.

**Registro das operações:** o mantenedor mantém registro simples das operações de telemetria
(eventos enviados, finalidade estatística, prazo de retenção do GA4), conforme art. 37 da LGPD.
