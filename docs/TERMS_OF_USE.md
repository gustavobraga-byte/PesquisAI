# Termos de Uso — UFVAI

**Versão:** 2.2 · **Data:** 10/09/2026 · Substitui a versão 2.1 (25/08/2026)

> **Resumo em uma frase:** o UFVAI é um software livre (licença MIT) de apoio à pesquisa científica,
> fornecido "como está", sem garantias; você é responsável pelo uso que faz das saídas geradas, pelas
> suas chaves de API e pelo cumprimento das normas de integridade acadêmica aplicáveis — a ativação
> exige **nome + e-mail** de contato (elimináveis a qualquer tempo, LGPD art. 7º, V) com registro de IP,
> e a telemetria anônima vem **ativa por padrão**, sem cookies, podendo ser desligada a qualquer momento (opt-out, art. 7º, IX).
>
> **Versão técnica correspondente:** `terms_version=6` (v0.6.10+). Re-consentimento exigido a cada mudança relevante.

Ao instalar, acessar ou utilizar o UFVAI ("o Software"), você declara ter lido e aceito estes Termos de
Uso, a Licença MIT ([`LICENSE`](../LICENSE)) e o Aviso de Privacidade ([`PRIVACY.md`](../PRIVACY.md)).
O aceite é registrado localmente no seu computador (`~/.config/ufvai_consent.json`). Se não concordar,
não utilize o Software.

---

## 1. Definições

- **UFVAI:** agente de IA para pesquisa científica desenvolvido no Departamento de Economia Rural
  (DER) da Universidade Federal de Viçosa (UFV); distribuído como código-fonte (GitHub) e pacote `.deb`.
- **Usuário:** pessoa que instala/executa o Software em seu próprio ambiente (Google Colab, máquina
  local ou servidor próprio). O UFVAI não presta serviço hospedado — **os dados ficam no SEU ambiente**.
- **Provedores de terceiros:** serviços externos opcionais configurados por você (LLMs como OpenAI,
  Anthropic, Google/Ollama; Google Drive; APIs públicas de dados como IBGE/SIDRA e NASA POWER).
- **Telemetria:** contadores anônimos de eventos enviados via Google Analytics 4 Measurement Protocol,
 ativa por padrão (opt-out), **sem cookies** nem identificadores pessoais (ver §7).

## 2. Natureza do instrumento: licença × termos

- A **Licença MIT** rege o **código-fonte** (uso, cópia, modificação, distribuição).
- Estes **Termos de Uso** regem a **relação de uso do programa e dos recursos acessórios**
  (telemetria, marca, suporte, conduta esperada). Nada aqui restringe direitos que a MIT confere
  sobre o código; naquilo que os documentos se sobrepuserem, prevalece a MIT quanto ao código.

## 3. Integridade acadêmica e uso responsável de IA

O UFVAI destina-se a **apoiar** a pesquisa científica — jamais a substituir o julgamento humano.

3.1. **Validação humana obrigatória.** Saídas de IA podem conter erros, omissões e "alucinações"
(inclusive citações e dados inexistentes). Você deve verificar toda afirmação factual, dado numérico
e referência antes de usar.

3.2. **Declaração de uso de IA.** Conforme a **Política de Integridade na Atividade Científica do
CNPq (Portaria CNPq nº 2.664/2026)**, o uso de inteligência artificial generativa em qualquer fase
da atividade científica deve ser **declarado**, indicando a ferramenta e a finalidade; é vedado
apresentar conteúdo gerado por IA como autoria humana, e a responsabilidade pelo conteúdo final é
integralmente do pesquisador. Recomenda-se incluir Declaração de Uso de IA em teses, dissertações,
TCCs, artigos e relatórios produzidos com apoio do UFVAI.

3.3. **Normas institucionais.** Usuários vinculados à UFV devem observar também a **Política de
Segurança da Informação e da Comunicação (POSIC-UFV — Resolução Consu/UFV nº 12/2024)**, o
**Código de Ética da UFV (Resolução Consu/UFV nº 04/2024)** e as normas da pós-graduação aplicáveis.

3.4. **Pesquisa com seres humanos.** O UFVAI não substitui aprovação ética: pesquisas envolvendo
seres humanos exigem apreciação por CEP/CONEP (Plataforma Brasil) antes da coleta de dados.

3.5. **Usos vedados.** É proibido usar o Software para: (a) produzir e apresentar trabalho acadêmico
sem revisão humana declarada; (b) violar direitos autorais ou políticas editoriais; (c) atividades
ilícitas; (d) processar dados pessoais sensíveis sem amparo legal; (e) tentar burlar mecanismos de
segurança, consentimento ou licenciamento do próprio Software.

## 4. Responsabilidades do usuário

- **Chaves de API** são suas e de sua inteira responsabilidade; o UFVAI as armazena cifradas
  (Fernet/AES-CBC+HMAC) no seu Google Drive, mas a guarda da sua conta Google é sua.
- **Conteúdo gerado:** o uso de material produzido com apoio do agente deve respeitar direitos
  autorais, políticas dos provedores de IA e legislação aplicável (incluindo LGPD).
- **Ambiente e custos:** consumo de cotas/créditos dos provedores configurados por você; execução
  em ambiente sob seu controle.

## 5. Serviços de terceiros e transferência internacional

Funcionalidades dependem de serviços externos (Google Colab/Drive, provedores de LLM, Google
Analytics, APIs de dados públicos). O uso desses serviços está sujeito aos respectivos termos e
políticas de privacidade. Quando acionados, dados podem ser transferidos para servidores no
exterior (LGPD, arts. 33–36), hipótese declarada no [`PRIVACY.md`](../PRIVACY.md).

## 6. Sem garantias · Limitação de responsabilidade

O Software é fornecido "COMO ESTÁ", SEM GARANTIA DE QUALQUER TIPO, expressa ou implícita
(inclusive adequação a finalidade específica e não violação), conforme a Licença MIT. Em nenhuma
hipótese os autores serão responsáveis por danos decorrentes do uso do Software, em especial por
decisões tomadas com base em saídas de IA não revisadas por humanos. Tratando-se de relação de
consumo, eventuais cláusulas excludentes serão interpretadas nos limites do CDC (art. 51).

## 7. Ativação (nome+e-mail+IP) e telemetria anônima

**7.1. Nome + e-mail obrigatórios para ativação (v0.6.10+).** Para aceitar estes Termos e ativar
o Software você deve informar **nome e e-mail válidos**, usados exclusivamente para contato sobre
o UFVAI (segurança, atualizações e suporte — base legal: **execução do serviço, LGPD art. 7º, V**).
O IP público de ativação/retorno é capturado via `api.ipify.org` (fallback `ipinfo.io`) para
registro de segurança — nunca para rastreamento. Os dados são guardados no SEU ambiente
(`backups/ufvai_consentimento.json`, com resumo SHA-256 do e-mail) e encaminhados à planilha
de contatos do projeto em 8 colunas (`Data/hora · E-mail · Nome · SHA-256 · Ambiente · Versão ·
Flag[novo_contato|usuario_ativo] · IP`) somente mediante este aceite. Podem ser **eliminados a
qualquer momento** (LGPD art. 18, VI) pela opção de eliminação de contato da interface ou
`DELETE /api/contact/delete`; nesses casos serão novamente solicitados na próxima abertura.
Desde a v0.6.16 cada retorno gera **exatamente 1 linha** `usuario_ativo`, apenas no clique em
"Continuar" (sem disparos automáticos).

**7.2. Telemetria anônima — ativa por padrão (opt-out).** Desde a versão 2.1, a telemetria envia
exclusivamente contadores anônimos de uso (page_view padrão do Google Analytics 4, **sem cookies**
`_ga`, sem qualquer conteúdo pessoal ou identificador direto) e vem **ativa por padrão**, com base no
**legítimo interesse do controlador (LGPD art. 7º, IX)** — melhoria e segurança do Software. Você pode
**opôr-se a qualquer momento**: desmarcando a caixa de telemetria na tela de Termos, definindo
`UFVAI_TELEMETRY=0` ou limpando `~/.config/ufvai_consent.json` (direito de oposição, LGPD art. 18,
§2º). Detalhes: [`TELEMETRY.md`](../TELEMETRY.md) e [`PRIVACY.md`](../PRIVACY.md).

## 8. Alterações dos termos

Versões atualizadas serão publicadas no repositório oficial e sinalizadas na interface (nova tela
de aceite quando a mudança for relevante). O uso continuado após a publicação implica ciência da
versão vigente.

## 9. Cessação

Você pode cessar o uso e remover o Software a qualquer tempo (desinstalação + exclusão de
`~/PesquisAI/` e `~/.config/opencode/`). O mantenedor pode descontinuar funcionalidades acessórias
(ex.: endpoint de telemetria) sem prejuízo da licença do código.

## 10. Legislação e foro

Estes Termos são regidos pelas leis da República Federativa do Brasil, em especial a LGPD
(Lei nº 13.709/2018), o Marco Civil da Internet (Lei nº 12.965/2014) e o Marco Civil das Ciências,
Tecnologias e Inovação (Lei nº 13.243/2016). Fica eleito o foro da **Comarca de Viçosa/MG** para
dirimir controvérsias, salvo competência funcional diversa, respeitada a regra de domicílio do
consumidor quando aplicável (CDC, art. 101, I).

## 11. Contato e titular de dados (LGPD)

- **Mantenedor:** Prof. Gustavo Bastos Braga — DER/UFV · gustavo.braga@ufv.br
- **Encarregado (DPO) da UFV:** canal institucional em https://dgi.ufv.br/privacidade/
- Direitos do titular (LGPD, art. 18): confirmação de tratamento, acesso, correção, anonimização,
  portabilidade, informação sobre compartilhamento, informação sobre a possibilidade de não
  consentir, revogação do consentimento e oposição — exercíveis pelo contato acima, com resposta
  imediata (simplificada) ou em até 15 dias (declaração completa).

---

*UFVAI · Universidade Federal de Viçosa — DER · contato: gustavo.braga@ufv.br*
*Referências normativas citadas: Portaria CNPq nº 2.664/2026 (DOU 06/03/2026) · Resolução Consu/UFV nº 12/2024 (POSIC) · Resolução Consu/UFV nº 04/2024 (Código de Ética UFV) · Lei nº 13.709/2018 (LGPD).*
