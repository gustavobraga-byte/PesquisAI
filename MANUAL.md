# 📘 Manual do UFVAI

> **Agente de Pesquisa Científica de Alta Performance · v0.6.17 · Setembro 2026**
> Registro SisPPG/UFV nº 10356285004 · Universidade Federal de Viçosa

---

## 🤔 O que é Inteligência Artificial Agentica? Uma Explicação Completa

### Para entender o que é uma IA Agentica, vamos começar pelo que ela NÃO é.

Quando você usa um ChatGPT, Gemini, Claude ou qualquer IA "convencional", você interage com um sistema de **pergunta-e-resposta**. Você faz uma pergunta, ele te dá uma resposta. Fim.

Mas imagine que você precisa fazer algo mais complexo. Algo como:

> "Eu quero fazer um artigo sobre desigualdade de renda no Brasil nos últimos 10 anos. Preciso que você:
> 1. Busque os dados do PNAD Contínua no IBGE
> 2. Limpe e organize esses dados
> 3. Calcule o índice de Gini por região
> 4. Faça uma regressão econométrica para ver os fatores associados
> 5. Busque a literatura acadêmica sobre o tema
> 6. Escreva o artigo completo em estrutura IMRaD
> 7. Formate tudo em ABNT
> 8. Gere os gráficos e tabelas
> 9. Salve tudo na minha pasta do Drive"

Uma **IA tradicional** (como ChatGPT) **não consegue fazer isso**. Ela pode te ajudar em partes isoladas. Ela pode te explicar como calcular o Gini. Ela pode te ajudar a escrever um parágrafo. Mas ela **não executa a tarefa toda de ponta a ponta**.

Ela tem problemas fundamentais para esse tipo de trabalho:

❌ **Ela não acessa fontes reais em tempo real** — seu conhecimento está "congelado" em uma data de corte. Ela não sabe o que aconteceu depois dessa data.

❌ **Ela inventa coisas quando não sabe** — se você pedir um dado que ela não tem, ela pode "inventar" um número que parece razoável, citando uma fonte que não existe ou um artigo que nunca foi publicado. No ambiente acadêmico, isso é **catastrófico**.

❌ **Ela não executa passos múltiplos autonomamente** — ela pode te dar um código de regressão, mas ela não vai rodar esse código, interpretar os resultados, e então escrever a seção de resultados baseada neles. Ela para no meio do caminho.

❌ **Ela não lembra instruções complexas ao longo do tempo** — se você der 10 instruções diferentes, ela provavelmente esquecerá metade delas no meio do processo.

---

## ✅ Então o que é uma IA Agentica?

Uma **IA Agentica** é um sistema de inteligência artificial projetado para **executar tarefas completas de ponta a ponta**, de forma autônoma, seguindo regras rigorosas, e acessando fontes de informação reais do mundo exterior.

Pense nela como um **assistente de pesquisa altamente treinado, metodológico, e completamente honesto**.

### As 5 características que definem uma IA Agentica:

#### 1. 🔗 Acesso a ferramentas e fontes externas ("Skills")

Uma IA Agentica não está "presa" dentro do seu conhecimento pré-treinado. Ela pode **conectar-se a sistemas externos** para buscar informações reais.

No caso do **UFVAI**, essas conexões são chamadas de **Skills**:

| Skill | O que ela acessa |
|-------|------------------|
| `ibge-br` | Todos os bancos de dados públicos do IBGE (Censo, PNAD, PIB, etc.) |
| `opendatasus` | Todos os dados de saúde pública do Brasil (DataSUS, SINAN, SUS) |
| `dados-brasil` | Conjunto amplo de indicadores e datasets oficiais brasileiros (BCB, TSE, INPE, etc.) |
| `agrobr` | Dados do agronegócio brasileiro, produção agrícola e CAR |
| `BR-DWGD` | Dados climáticos gradeados do Brasil (normais climatológicas, ETo, precipitação) |
| `analise-qualitativa` | Análise qualitativa e de conteúdo (categorização, Reinert, similitude) — substitui NVivo/Iramuteq |
| `citation-management` | Validação de referências e DOIs (obrigatória para toda citação) |
| `memorial-ufv` / `pdf-to-memorial-rsc` | Memorial RSC-PCCTAE a partir do Relatório Detalhado UFV |
| `grant-finder` | Editais de fomento à pesquisa (Brasil e internacional) |
| `ufv-abnt` | Normas de formatação acadêmica da UFV e ABNT |
| K-Dense Scientific Skills (pacote `scientific`) | 140+ ferramentas de pesquisa científica: revisão sistemática, busca de literatura, análise estatística, visualização |

**Isso é revolucionário:** quando o UFVAI precisa de um dado sobre desemprego no Brasil, ele **não inventa**. Ele **acessa diretamente o IBGE** e traz o dado REAL, com fonte, ano, e nota metodológica.

#### 2. 📋 Planejamento e execução de múltiplos passos

Uma IA Agentica não funciona por "pergunta-resposta". Ela funciona por **plano de ação**.

Quando você pede para ela fazer um artigo sobre desigualdade de renda, ela não simplesmente começa a escrever. Ela primeiro **planeja**:

```
PLANO DE AÇÃO PARA ESTA TAREFA:
=================================

FASE 1 — COMPREENSÃO
   → Entender o escopo: desigualdade de renda no Brasil, últimos 10 anos
   → Identificar fontes relevantes: IBGE PNAD Contínua

FASE 2 — COLETA DE DADOS
   → Acessar skill ibge-br
   → Buscar PNAD Contínua 2013-2023
   → Extrair variáveis de renda, região, escolaridade

FASE 3 — TRATAMENTO E ANÁLISE
   → Limpar e organizar o dataset
   → Calcular índice de Gini por ano e por região
   → Rodar regressão econométrica (Mínimos Quadrados Ordinários)
   → Interpretar os coeficientes e níveis de significância

FASE 4 — REVISÃO DE LITERATURA
   → Acessar skills de busca acadêmica
   → Identificar artigos relevantes sobre desigualdade no Brasil
   → Sintetizar os achados da literatura

FASE 5 — REDAÇÃO E FORMATAÇÃO
   → Escrever artigo em estrutura IMRaD
   → Inserir os resultados da análise econométrica
   → Formatar referências em ABNT
   → Gerar tabelas e figuras

FASE 6 — ENTREGA
   → Salvar artigo em .md e .pdf
   → Salvar dataset e outputs de regressão
   → Incluir links para todos os arquivos gerados
```

E então ela **executa cada passo**, um após o outro, sem que você precise supervisionar cada etapa.

#### 3. 🛡️ Conjunto de regras não negociáveis ("Guardrails")

A característica **mais importante** de uma IA Agentica para uso acadêmico é que ela opera sob **regras que não podem ser quebradas**.

No caso do **UFVAI**, essas regras são:

| Regra | O que significa na prática |
|-------|-----------------------------|
| **Política de Zero-Fabricação** | Se o UFVAI não encontrar um dado, ele **NÃO inventa**. Ele diz explicitamente: *"Não foram encontrados dados suficientes nas fontes disponíveis para embasar esta afirmação."* |
| **Transparência total sobre fontes** | Toda afirmação factual vem acompanhada de **fonte, ano de referência, e nota metodológica** quando aplicável. |
| **Marcadores de nível de evidência** | O UFVAI usa marcadores explícitos: `[DADO CONFIRMADO]`, `[ESTIMATIVA FUNDAMENTADA]`, `[SEM DADOS SUFICIENTES]`. |
| **Dados nacionais primeiro** | Para qualquer afirmação sobre o Brasil, ele consulta `ibge-br` ou `opendatasus` **antes** de qualquer outra fonte. |
| **Não substitui julgamento crítico** | O UFVAI é **ferramenta auxiliar**, não substituto do pesquisador. Ele **nunca** toma decisões ou afirma verdades absolutas em nome do usuário. |

Essas regras são **codificadas no sistema**. Elas não são "sugestões" ou "instruções que podem ser esquecidas". Elas são **guardrails** que o agente não pode transgredir.

#### 4. 🧠 Memória e contexto ao longo da tarefa

Uma IA Agentica mantém o **contexto completo da tarefa** ao longo de toda a execução.

Se você pedir:

> "Faça um artigo sobre PIB dos estados brasileiros. Depois gere um mapa. Depois escreva a conclusão."

O agente lembra:
- Qual o tema do artigo
- Quais dados foram usados
- Quais resultados foram encontrados
- Quais instruções você deu

Ela não "esquece" o que estava fazendo no meio do caminho.

#### 5. 📤 Entrega tangível e rastreável

No final, uma IA Agentica entrega **resultados concretos**, não apenas texto.

No caso do UFVAI:
- Artigos salvos em `.md` e `.pdf`
- Datasets limpos organizados
- Outputs de análises estatísticas
- Gráficos e tabelas
- Tudo salvo em localização conhecida (sua pasta `PesquisAI` no seu Google Drive)


---

## 🚀 O que é o UFVAI?

> **Nota sobre a marca:** o projeto nasceu como *PesquisAI* e, desde a v0.6.0/v0.6.4 (agosto/2026), chama-se **UFVAI**. Identificadores técnicos foram preservados por compatibilidade: pasta `PesquisAI` no Google Drive, variável `PESQUISAI_OBSIDIAN_VAULT`, tags `pesquisai/*`, pacote Python `pesquisai` e comandos `ufvai`/`pesquisa`.

O **UFVAI** é uma **Inteligência Artificial Agentica especializada em pesquisa científica brasileira**.

Ele foi construído para resolver um problema específico: **como usar IA no ambiente acadêmico sem comprometer a integridade científica, sem inventar dados, e com acesso a fontes oficiais brasileiras** — no Colab **ou 100% offline na sua máquina**.

### O que torna o UFVAI único?

Existem outras IAs Agenticas no mercado. Mas o UFVAI é diferente porque:

| Característica | Explicação |
|----------------|------------|
| **Especializado no Brasil** | A maioria das IAs agenticas são treinadas para dados americanos ou europeus. O UFVAI tem **conexões diretas com IBGE, DataSUS, e normas ABNT/UFV**. |
| **Foco em integridade científica** | A regra número um do UFVAI é **não inventar nada**. Tudo vem com fonte. Se não tem dado, ele diz que não tem. Referências passam por validação (`citation-management`) antes de serem entregues. |
| **100% gratuito e aberto** | Roda no **Google Colab** (infraestrutura gratuita) ou **offline via pacote .deb** na sua máquina Linux, e todo o código é aberto. |
| **Salva tudo no seu Drive (ou disco local)** | Nada fica "preso" na plataforma. Todos os arquivos gerados vão para **seu Google Drive**, na pasta `PesquisAI`, ou para `~/PesquisAI` no modo offline. |
| **Habilidades específicas para academia** | Formatação ABNT, estrutura IMRaD, busca de literatura, memorial RSC-PCCTAE, editais de fomento — tudo integrado. |
| **Privacidade por padrão (LGPD)** | Telemetria **opt-in** (só envia se você aceitar), contato opcional, consentimento explícito em tela de Termos. |

---

## 💡 Coisas que SOMENTE uma IA Agentica pode fazer

Vamos ser muito claros: **não são perguntas e respostas**. São **tarefas completas** que envolvem múltiplos passos, acesso a fontes externas, execução de código, e entrega de resultados concretos.

Aqui estão exemplos do que o UFVAI pode fazer **que nenhuma IA tradicional conseguiria**:

---

### 📝 Exemplo 1: Revisão Sistemática Completa

**Tarefa:**
> "Faça uma revisão sistemática sobre 'Efeitos do PRONAF na agricultura familiar brasileira' seguindo as diretrizes PRISMA."

**O que o UFVAI faz (autonomamente):**

1. **Compreende o protocolo PRISMA** e estrutura a revisão de acordo
2. **Define critérios de inclusão/exclusão** explicitamente
3. **Busca nas bases acadêmicas** (via skills científicas) artigos relevantes
4. **Acessa dados do IBGE** sobre agricultura familiar para contextualização
5. **Acessa dados oficiais do PRONAF** (se disponíveis via fontes públicas)
6. **Sintetiza os achados** por categorias temáticas
7. **Identifica lacunas** na literatura
8. **Escreve o artigo completo** da revisão sistemática
9. **Formata tudo** conforme normas de periódicos
10. **Salva** na sua pasta do Drive

**O que uma IA tradicional faria:**
> Escreveria um texto genérico sobre o tema, provavelmente inventando alguns artigos e autores, sem acesso a dados reais do IBGE ou do PRONAF.

---

### 📊 Exemplo 2: Busca, Limpeza e Análise de Dados Públicos

**Tarefa:**
> "Busque os dados do PNAD Contínua dos últimos 5 anos sobre renda domiciliar per capita. Limpe esses dados, calcule o índice de Gini por região, e faça uma análise descritiva comparando as regiões brasileiras."

**O que o UFVAI faz (autonomamente):**

1. **Acessa diretamente o IBGE** via skill `ibge-br`
2. **Baixa os microdados** do PNAD Contínua (se disponível) ou os dados agregados
3. **Identifica as variáveis relevantes**: renda domiciliar, região, fatores associados
4. **Limpa e organiza o dataset**: trata missing values, recodifica variáveis, cria variáveis derivadas
5. **Calcula índices de desigualdade**: Gini, razão 90/10, Theil
6. **Faz análise por região**: compara Norte, Nordeste, Sudeste, Sul, Centro-Oeste
7. **Gera tabelas descritivas** com médias, medianas, desvios padrão
8. **Gera visualizações**: gráficos de evolução temporal, boxplots por região
9. **Escreve um relatório completo** da análise, interpretando os resultados
10. **Salva tudo**: dataset limpo, outputs das análises, relatório, gráficos

**O que uma IA tradicional faria:**
> Poderia te explicar como calcular o Gini. Poderia te dar um código de exemplo. Mas **não acessaria o IBGE**, **não baixaria os dados reais**, **não rodaria a análise**, e **não interpretaria resultados concretos**.

---

### 📈 Exemplo 3: Estatística Econométrica Complexa

**Tarefa:**
> "Teste a hipótese de que o acesso a crédito rural está associado a maior produtividade na agricultura familiar. Use dados do Censo Agropecuário. Especifique o modelo, justifique a escolha dos métodos, e interpreta todos os coeficientes e níveis de significância."

**O que o UFVAI faz (autonomamente):**

1. **Formula a estratégia de identificação econométrica**
2. **Discute potencialidade de vieses**: endogeneidade, variáveis omitidas, causalidade vs correlação
3. **Acessa os dados do Censo Agropecuário** via IBGE
4. **Constrói as variáveis** de interesse: acesso a crédito (dummy), produtividade (valor da produção por área), controles (tamanho da propriedade, região, tecnologia)
5. **Especifica os modelos**:
   - MQO (Mínimos Quadrados Ordinários) como benchmark
   - Modelos com variáveis instrumentais (se possível) para lidar com endogeneidade
   - Efeitos fixos por estado/região
6. **Rodar todas as regressões**
7. **Interpreta coeficiente por coeficiente**:
   - Magnitude econômica (não apenas estatística)
   - Níveis de significância (p-valores, estrelas)
   - Intervalos de confiança
   - Sinais esperados vs obtidos
8. **Discute limitações**: o que os resultados não dizem, quais vieses permanecem
9. **Escreve uma seção completa de resultados** como em um artigo
10. **Salva outputs das regressões**, tabelas de resultados, e relatório

**O que uma IA tradicional faria:**
> Poderia te explicar o que é MQO. Poderia te dar um código de regressão. Poderia te dizer como interpretar coeficientes **em geral**. Mas **não rodaria regressões em dados reais do IBGE**, **não interpretaria coeficientes específicos da sua pesquisa**, e **não discutiria limitações contextuais do seu problema**.

---

### 🎤 Exemplo 4: Apresentação para Congresso

**Tarefa:**
> "Transforme este artigo sobre 'Desenvolvimento rural no Vale do Rio Doce' em uma apresentação para congresso. Faça slides claros, use os dados do artigo, destaque os principais resultados, e deixe pronto para apresentar."

**O que o UFVAI faz (autonomamente):**

1. **Identifica os pontos-chave** do artigo:
   - Pergunta de pesquisa
   - Metodologia
   - Principais resultados
   - Contribuição
   - Conclusões

2. **Estrutura a apresentação** seguindo boas práticas de congresso:
   - Slide de título e autores
   - Introdução/pergunta de pesquisa
   - Revisão breve da literatura
   - Dados e metodologia
   - Principais resultados (3-4 slides)
   - Discussão e contribuição
   - Conclusões
   - Referências

3. **Puxa os dados concretos** do artigo: números, coeficientes, níveis de significância

4. **Escreve o conteúdo de cada slide** de forma concisa (não parágrafos longos)

5. **Adiciona notas do orador** para cada slide: o que falar, detalhes adicionais

6. **Formata** de forma adequada para apresentação

7. **Salva** na sua pasta

**O que uma IA tradicional faria:**
> Poderia te dar uma estrutura genérica de slides de congresso. Poderia te ajudar a reescrever alguns parágrafos em bullet points. Mas **não extrairia os números e resultados específicos do SEU artigo**, **não contextualizaria para o SEU tema**, e **não lembraria as particularidades dos SEUS resultados**.

---

### 📋 Exemplo 5: Relatório de Extensão Rural

**Tarefa:**
> "Elabore um relatório de atividades de extensão rural sobre 'Uso de agrotóxicos na comunidade de X'. O relatório precisa de: introdução com dados de base (IBGE/DataSUS sobre intoxicações), metodologia das atividades aplicadas, resultados alcançados, discussão, conclusões e recomendações. Formate adequadamente para relatórios de extensão."

**O que o UFVAI faz (autonomamente):**

1. **Acessa dados de base contextualizadores**:
   - Dados do DataSUS sobre intoxicações por agrotóxicos na região/estado
   - Dados do IBGE sobre agricultura na região
   - Literatura sobre uso de agrotóxicos e extensão rural

2. **Estrutura o relatório** conforme normas de relatórios de extensão

3. **Escreve cada seção**:
   - **Introdução**: contextualiza o problema com DADOS REAIS de intoxicações
   - **Metodologia**: descreve as atividades de extensão (você fornece, ele estrutura)
   - **Resultados**: organiza o que foi alcançado de forma clara
   - **Discussão**: relaciona os resultados com a literatura
   - **Conclusões e recomendações**: de forma prática e acionável

4. **Integra os dados públicos** como contextualização

5. **Formata** adequadamente para relatórios técnicos

6. **Salva** na sua pasta

**O que uma IA tradicional faria:**
> Poderia te dar uma estrutura genérica de relatório de extensão. Poderia te ajudar a escrever textos sobre agrotóxicos em geral. Mas **não acessaria o DataSUS para dados de intoxicação REAIS na sua região**, **não integraria esses dados no SEU relatório**, e **não contextualizaria especificamente para a SUA realidade**.

---

## 🎯 Por que isso é importante para você, pesquisador(a)?

Se você trabalha com **economia, extensão rural, ciências agrárias, desenvolvimento rural, ou qualquer área que usa dados públicos brasileiros**, o UFVAI representa uma mudança de paradigma.

### Antes do UFVAI (e IAs tradicionais):

```
VOCÊ PRECISA:

1. ABRIR O SITE DO IBGE
   → Procurar a base certa
   → Entender a estrutura
   → Baixar os arquivos
   → Descompactar
   → Abrir no Excel/R/Python

2. LIMPAR OS DADOS
   → Horas de trabalho
   → Tratar missing values
   → Recodificar variáveis
   → Juntar bases diferentes

3. BUSCAR LITERATURA
   → Google Scholar, SciELO, Periódicos CAPES
   → Ler dezenas de artigos
   → Organizar referências
   → Formatar em ABNT

4. ESCREVER
   → Estruturar o artigo
   → Inserir os resultados
   → Formatar tudo
   → Corrigir referências

TEMPO TOTAL: dias ou semanas de trabalho
```

### Com o UFVAI (IA Agentica):

```
VOCÊ DIZ:
"Busque os dados do PNAD no IBGE, limpe, analise, busque literatura, e escreva o artigo em ABNT."

O PESQUISAI FAZ:
→ Acessa IBGE diretamente
→ Baixa e limpa os dados
→ Roda as análises
→ Busca a literatura
→ Escreve e formata
→ Salva tudo no seu Drive

TEMPO TOTAL: você monitora, ele executa.
```

### Mas... (é importante dizer)

O UFVAI **NÃO substitui o pesquisador**. Ele **amplifica** o pesquisador.

| O UFVAI faz | O PESQUISADOR(A) faz |
|------------------|----------------------|
| Buscar dados em fontes públicas | Definir a PERGUNTA DE PESQUISA |
| Limpar e organizar dados | Definir a ESTRATÉGIA DE IDENTIFICAÇÃO |
| Executar análises estatísticas | INTERPRETAR resultados à luz da teoria |
| Estruturar textos conforme normas | FAZER A CONTRIBUIÇÃO CIENTÍFICA |
| Formatar em ABNT | Avaliar CRITICAMENTE tudo |
| Salvar arquivos organizados | Tomar DECISÕES |

O UFVAI é uma **ferramenta de amplificação**. Ele tira de você o trabalho repetitivo, burocrático, mecânico — para que você possa se concentrar no que realmente importa: **o pensamento científico**.

---

## ⚠️ Princípios Fundamentais do UFVAI

| Princípio | Descrição |
|-----------|-----------|
| **Integridade Científica** | Nunca inventa dados, estatísticas, autores, DOIs ou citações |
| **Transparência Total** | Sempre informa a fonte e o ano de todo dado |
| **Política Zero-Fabricação** | Se não encontrar, DECLARA que não encontrou. Não inventa. |
| **Dados Nacionais Primeiro** | Para o Brasil: IBGE/DataSUS têm prioridade sobre qualquer outra fonte |
| **Honestidade sobre Incertezas** | Usa marcadores: `[DADO CONFIRMADO]`, `[ESTIMATIVA FUNDAMENTADA]`, `[SEM DADOS SUFICIENTES]` |
| **Não Substitui Julgamento Crítico** | É ferramenta, não pesquisador. SEMPRE revise os resultados. |

---

## Sumário

1. [Primeiros Passos](#1-primeiros-passos)
2. [Skills Disponíveis](#2-skills-disponíveis)
3. [Fluxo de Trabalho](#3-fluxo-de-trabalho)
4. [Exemplos Práticos](#4-exemplos-práticos)
5. [Backup e Restauração](#5-backup-e-restauração)
6. [Limitações Importantes](#6-limitações-importantes)
7. [Troubleshooting](#7-troubleshooting)
8. [Citação do UFVAI](#8-citação-do-ufvai)
9. [Declaração de Uso de IA](#9-declaração-de-uso-de-inteligência-artificial-ia)
10. [Disclaimer](#10-disclaimer-do-ufvai--termos-de-uso-e-isenção-de-responsabilidade)
11. [Memória Persistente](#11--memória-persistente-minha-memória--desde-a-v0518)
12. [Histórico de Versões](#12-histórico-de-versões)

---

## 1. Primeiros Passos

### 1.1 Dois modos de uso (v0.6.x)

| Modo | Onde roda | Como iniciar |
|------|-----------|--------------|
| **Colab (nuvem)** | Google Colab, gratuito | Notebook `PesquisAI.ipynb` |
| **Offline (.deb)** | Sua máquina Linux | Pacote `pesquisai_<versão>_amd64.deb` |

### 1.2 Abrindo no Colab

1. **Upload** do arquivo `PesquisAI.ipynb` para o seu Google Drive
2. Clique duas vezes para abrir no **Google Colab**
3. No menu superior: **Ambiente de execução → Executar tudo** (ou `Ctrl + F9`)

### 1.3 Primeira Execução — painel da logomarca (v0.6.7+)

Desde a v0.6.7, o carregamento acontece dentro de **um único painel visual no tema da logomarca oficial** (papel off-white, wordmark "**UFV**" azul-marinho + "**AI**" dourado), que nasce já na clonagem do repositório e percorre todas as etapas sem reiniciar:

![Painel de carregamento do UFVAI no Google Colab](manual-figuras/boot-colab-real.jpeg)
*Figura 1 — Painel de carregamento real no Google Colab: barra dourada de progresso e checkpoints linha a linha ("Preparando…", "Montando Google Drive…").*

As mensagens aparecem **abaixo da barra**, linha a linha (spinner dourado na etapa ativa, ✓ verde na concluída, ✕ em falhas sem abortar o boot), com percentual sempre crescente. Ao final, o próprio painel exibe a logomarca e o botão de lançamento:

![Estado final do painel: UFVAI pronto + botão de lançamento](manual-figuras/boot-pronto.png)
*Figura 2 — Representação do estado final do painel: 100%, "UFVAI pronto!" e botão dourado "ABRIR O UFVAI".*

**Autorize o Google Drive:**
1. Clique no link que aparecerá
2. Logue com sua conta Google
3. Clique em **Permitir**
4. Copie o código e cole no campo do Colab
5. Pressione `Enter`

### 1.4 Tudo Pronto!

Quando terminar, o próprio painel finaliza em 100% exibindo a **logomarca oficial** e um **botão em pílula dourada**:

```
🚀 ABRIR O UFVAI →
```

**Clique no botão** para abrir a interface visual. Durante a conexão com o terminal, um **splash de inicialização** é exibido:

![Splash de inicialização do terminal](manual-figuras/splash-terminal-real.jpeg)
*Figura 3 — Splash real de conexão: logomarca UFVAI, spinner dourado e status "Iniciando terminal…".*

### 1.5 O aceite obrigatório (Termos de Uso) — a primeira tela

> **Sem o aceite, o UFVAI não abre.** A tela de Termos de Uso é a **única tela de abertura** do aplicativo — não existe modal intermediário nem forma de pular.

![Tela de Termos de Uso e aceite](manual-figuras/tela-termos-real.jpeg)
*Figura 4 — Tela real de Termos de Uso (v2.1): aceite obrigatório + e-mail de ativação + telemetria opt-out.*

O que você vê e o que cada elemento significa:

| Elemento | Obrigatório? | O que faz |
|----------|--------------|-----------|
| ☑️ **"Li e aceito os Termos de Uso e a Licença MIT"** | **SIM — sem marcar, o botão de aceite fica desabilitado** | Consentimento com o contrato de uso (Termos v2.1), a Licença MIT e as políticas de integridade (Portaria CNPq nº 2.664/2026, POSIC UFV) |
| ✉️ **Campo de e-mail (obrigatório)** | **SIM — sem um e-mail válido, o aceite é recusado** | E-mail de ativação/contato do UFVAI (LGPD art. 7º V — execução do serviço). Gravado no SEU ambiente (`backups/ufvai_consentimento.json`, no Colab: no seu Drive) com resumo SHA-256; **nunca** enviado ao Google Analytics; eliminável a qualquer momento (LGPD art. 18 — será re-solicitado na próxima abertura) |
| ☑️ **"Estatísticas anônimas de uso"** *(já marcada)* | Não — desmarque para desligar | Telemetria **ativa por padrão (opt-out)**: contadores anônimos via GA4, **sem cookies**, sem conteúdo e sem dados pessoais (base legítimo interesse, LGPD art. 7º IX); desligável a qualquer momento desmarcando aqui ou com `UFVAI_TELEMETRY=0` (art. 18 §2º) |
| **Botão "Não aceitar / Decline"** | — | Encerra sem abrir o aplicativo |
| **Botão "Aceitar e começar / Accept"** | — | Registra o consentimento+e-mail e abre o UFVAI |

**Pontos importantes:**

- O resumo do aceite é exibido **nos 5 idiomas** da interface (pt/en/es/fr/zh);
- Os links **Licença MIT + Notice**, **Termos completos v2.1** e **Privacidade · LGPD** permitem ler o texto integral antes de aceitar;
- Nenhuma chave de API ou conteúdo do seu vault é enviado a terceiros pela telemetria — ela é **anônima, sem cookies e desligável**;
- **Reaberturas:** seu perfil persistente pré-preenche e-mail e preferências — basta clicar em Aceitar; se você já aceitou **esta mesma versão** dos Termos, a tela nem aparece;
- Quando a versão dos Termos muda, o UFVAI solicita **re-consentimento** na próxima abertura — seu aceite anterior não é reutilizado silenciosamente;
- O consentimento fica registrado localmente (`~/.config/ufvai_consent.json`) e o perfil persistente no SEU Drive/máquina (`backups/ufvai_consentimento.json`), nunca em servidores do desenvolvedor.

### 1.6 A interface de trabalho

Após o aceite, você acessa a interface com **terminal interativo do agente**, painel de sessão e botões de backup:

![Interface de trabalho do UFVAI](manual-figuras/interface-trabalho.png)
*Figura 5 — Interface de trabalho: terminal do agente (esquerda), contexto da sessão (direita), backup/restauração/Drive (topo) e conexão com provedor de IA (rodapé).*

> **Arquitetura em uma figura:** o agente combina uma camada de orquestração (políticas de integridade e marcadores de proveniência), skills de dados/scientíficas/normalização, fontes oficiais (IBGE/SIDRA, DataSUS, OpenAlex, PubMed…) e memória persistente em vault Obsidian.

![Arquitetura em camadas do UFVAI](manual-figuras/arquitetura.png)
*Figura 6 — Arquitetura em camadas do agente (fonte: artigo do projeto).*

### 1.7 Instalando offline (.deb)

Para usar **sem internet e sem Colab** (requisito de privacidade máxima — nada sai da sua máquina):

```bash
sudo dpkg -i pesquisai_0.6.17-offline_amd64.deb   # ou versão mais recente
ufvai                                       # abre a interface (UI 8001 · terminal 8000)
```

- Configurações ficam em `~/PesquisAI/config/ufvai.env`
- Modelo de linguagem via **Ollama local** (`http://localhost:11434/v1`)
- Sem credenciais de nuvem, a telemetria fica inerte por padrão (nada é enviado)
- Atalhos: `ufvai` (e alias compatível `pesquisa`)

---

## 2. Skills Disponíveis

O UFVAI utiliza **skills** (módulos especializados) para acessar dados e ferramentas.

### 2.1 Dados Brasileiros (Prioridade Máxima)

| Skill | Fonte | O que faz |
|-------|-------|-----------|
| `ibge-br` | IBGE | Censo, PNAD, PIB, dados demográficos, socioeconômicos |
| `opendatasus` | DataSUS | Epidemiologia, SUS, mortalidade, SINAN, notificações |
| `dados-brasil` | Fontes oficiais BR | Conjunto amplo de indicadores e datasets brasileiros (BCB, TSE, INPE, ANP...) |
| `agrobr` | CONAB/ComexStat/SICAR | Dados do agronegócio, produção agropecuária, crédito rural, CAR |
| `BR-DWGD` | Xavier et al. | Dados climáticos gradeados diários do Brasil — normais climatológicas, ETo |

> **Regra de Ouro:** Para qualquer afirmação sobre o Brasil, o UFVAI consulta `ibge-br` ou `opendatasus` ANTES de responder.

### 2.2 Pesquisa Científica

| Skill | Fonte | O que faz |
|-------|-------|-----------|
| `scientific` (pacote K-Dense) | 140+ subskills | Estrutura IMRaD, revisão sistemática, busca de literatura, formatação APA/Vancouver, estatística com report APA, visualização científica |
| `citation-management` | OpenAlex/PubMed/Crossref | **Validação obrigatória de referências e DOIs** antes de qualquer citação |
| `paper-lookup` / `literature-review` | 11 APIs acadêmicas | Busca de papers, preprints, textos completos open access |

### 2.3 Análise Qualitativa e de Dados

| Skill | Fonte | O que faz |
|-------|-------|-----------|
| `analise-qualitativa` | Métodos clássicos e avançados | Análise de conteúdo, método Reinert, análise de similitude, codificação qualitativa, modelagem de tópicos — substitui NVivo e Iramuteq |
| `statistical-analysis` / `exploratory-data-analysis` | Python científico | Testes estatísticos com report APA, EDA em 200+ formatos |

### 2.4 Normas Acadêmicas e Documentos UFV

| Skill | Norma | O que faz |
|-------|-------|-----------|
| `ufv-abnt` | ABNT + UFV | Formatação de trabalhos acadêmicos conforme normas da UFV e ABNT |
| `pdf-to-memorial-rsc` / `memorial-ufv` | RSC-PCCTAE/UFV | Geração do Memorial a partir do Relatório Detalhado RSC emitido pelo sistema oficial da UFV (.md/.docx formatado) |
| `grant-finder` | Fomento BR/internacional | Busca de editais e oportunidades de financiamento |

### 2.5 Utilidades

| Skill | O que faz |
|-------|-----------|
| `docx`, `pdf`, `pptx`, `xlsx` | Geração e manipulação de documentos Office e PDFs |
| `obsidian-memory` | Infraestrutura da memória persistente ("Minha memória") |
| `pyzotero` | Integração com Zotero |
| `markitdown` | Conversão de arquivos para Markdown |

---

## 3. Fluxo de Trabalho

Todo ciclo de pesquisa no UFVAI segue **6 etapas obrigatórias**:

```
┌─────────────────────────────────────────────────────────┐
│  1. COMPREENSÃO       Analise o escopo e a pergunta     │
│                       de pesquisa antes de qualquer ação │
├─────────────────────────────────────────────────────────┤
│  2. COLETA DE DADOS   Acione as skills relevantes:      │
│                       K-Dense → literatura acadêmica    │
│                       ibge-br → dados BR gerais         │
│                       opendatasus → dados de saúde BR   │
│                       dados-brasil → indicadores BR     │
│                       agrobr → dados do agronegócio     │
│                       qualitativa → análise qualitativa │
├─────────────────────────────────────────────────────────┤
│  3. VALIDAÇÃO         Verifique consistência entre      │
│                       fontes. Aponte divergências.      │
├─────────────────────────────────────────────────────────┤
│  4. SÍNTESE           Cruze dados nacionais com         │
│                       literatura internacional.         │
├─────────────────────────────────────────────────────────┤
│  5. REDAÇÃO           Escreva com linguagem científica  │
│                       precisa. Cite todas as fontes.    │
├─────────────────────────────────────────────────────────┤
│  6. ENTREGA           Inclua link dos arquivos gerados  │
│                       ao final de toda resposta.        │
│                       Caso gere .md, também salve .pdf  │
└─────────────────────────────────────────────────────────┘
```

---

## 4. Exemplos Práticos

### Exemplo 1: Consulta Rápida de Dados

**Pergunta:**
> "Qual a população do Brasil em 2022?"

**O que o UFVAI faz:**
1. Aciona a skill `ibge-br`
2. Busca o dado no Censo mais recente
3. Retorna com fonte, ano e nota metodológica

**Resposta Esperada:**
```
A população residente no Brasil em 2022 era de aproximadamente 203,1 milhões de pessoas, 
de acordo com o Censo Demográfico de 2022 do IBGE.

Fonte: IBGE, Censo Demográfico 2022
[DADO CONFIRMADO]
```

### Exemplo 2: Dados de Saúde

**Pergunta:**
> "Quantos casos de dengue foram notificados no Brasil em 2024?"

**O que o UFVAI faz:**
1. Aciona a skill `opendatasus`
2. Consulta o SINAN (Sistema de Informação de Agravos de Notificação)
3. Se não encontrar, declara explicitamente

**Resposta (se dados disponíveis):**
```
No ano de 2024, foram notificados X casos de dengue no Brasil, 
conforme dados do SINAN/DataSUS.

Fonte: Ministério da Saúde, SINAN, 2024
[DADO CONFIRMADO]
```

**Resposta (se dados NÃO disponíveis):**
```
[SEM DADOS SUFICIENTES] — As skills não retornaram dados 
de notificações de dengue para o ano de 2024 no momento.

Recomenda-se consultar diretamente o painel oficial do Ministério da Saúde 
em https://www.gov.br/saude/pt-br/assuntos/saude-de-a-a-z/d/dengue
```

### Exemplo 3: Redação Acadêmica

**Pergunta:**
> "Escreva a seção de Introdução de um artigo sobre obesidade infantil no Brasil."

**O que o UFVAI faz:**
1. Aciona skills K-Dense para estrutura IMRaD
2. Consulta `ibge-br` para dados demográficos
3. Consulta `opendatasus` para dados de saúde
4. Integra literatura científica
5. Escreve com citações

**Resposta Esperada:**
```
## Introdução

A obesidade infantil representa um dos principais desafios de saúde pública 
no século XXI (OMS, 2023). No Brasil, a prevalência de sobrepeso e obesidade 
em crianças e adolescentes vem aumentando de forma preocupante nas últimas 
décadas (IBGE, 2022).

Conforme dados do IBGE (Pesquisa Nacional de Saúde, 2019-2020), aproximadamente 
X% das crianças brasileiras apresentavam excesso de peso, enquanto Y% eram 
classificadas como obesas. Esses números representam um aumento significativo 
em relação à década anterior.

O Sistema Único de Saúde (SUS) registrou Z internações hospitalares por 
complicações relacionadas à obesidade em menores de 18 anos em 2023 (DataSUS, 2024). 
Esses dados evidenciam a urgência de políticas públicas efetivas para prevenção 
e controle desse agravo.

### Referências
- IBGE. Pesquisa Nacional de Saúde, 2019-2020.
- OMS. Relatório Global sobre Obesidade, 2023.
- Ministério da Saúde, DataSUS, 2024.

[📄 Arquivo Gerado](introducao_obesidade.md) - Arquivo na pasta "PesquisAI" no seu Drive
[📄 Arquivo Gerado](introducao_obesidade.pdf) - Versão PDF
```

---

## 5. Backup e Restauração

### 5.1 Salvando sua Sessão

No topo da interface do UFVAI, há 3 botões importantes:

| Botão | O que faz |
|-------|-----------|
| 💾 **Salvar backup** | Exporta a sessão atual para um arquivo JSON no Drive |
| 🔄 **Restaurar** | Abre uma lista de backups anteriores para restaurar |
| 📁 **Drive** | Abre a pasta do projeto no Google Drive |

### 5.2 Fazendo Backup

1. Clique em **💾 Salvar backup**
2. O arquivo é salvo automaticamente em:
   ```
   Meu Drive/PesquisAI/backups/backup_abc123_14-35-22_22-05-2026.json
   ```
3. Formato do nome: `backup_<id_sessão>_HH-MM-SS_DD-MM-AAAA.json`

### 5.3 Restaurando Backup

1. Clique em **🔄 Restaurar**
2. Uma lista de backups aparecerá (mais recentes primeiro)
3. Clique no backup que deseja restaurar
4. Confirme a restauração
5. Atualize a página para acessar a sessão restaurada

> **Dica:** Use o menu `Ctrl + P` → `switch session` para alternar entre sessões.

---

## 6. Limitações Importantes

### 6.1 O que o UFVAI NÃO faz

| Limitação | Explicação |
|-----------|------------|
| **Não substitui pesquisador humano** | Todo resultado deve ser revisado criticamente |
| **Não acessa bases pagas** | Apenas dados públicos via skills |
| **Não faz coleta primária** | Não realiza entrevistas, experimentos ou surveys — não se realiza pesquisa de campo com ele |
| **Não garante tempo real** | Dados dependem da disponibilidade das APIs das skills; offline, só trabalha com arquivos fornecidos pelo usuário |
| **Não emite parecer** | Não substitui revisão por pares nem parecer médico, jurídico ou de comitê de ética (CEP/CONEP) |
| **Memória persistente entre sessões** | O UFVAI mantém um vault no Google Drive (ou `~/PesquisAI` offline) com daily notes, referências, hipóteses e logs de sessão. Consulte a Seção 11. |

### 6.2 Escopo de Diretórios

| Modo | Diretórios permitidos |
|------|----------------------|
| **Colab** | `/content/drive/My Drive/PesquisAI/` (exclusivo) |
| **Offline (.deb)** | `~/PesquisAI/` (vault, config e entregáveis) |

Todos os arquivos gerados são salvos **exclusivamente** nesses locais — nunca fora deles.

### 6.3 Saída Comunicacional Textual

- O agente **não exibe imagens/gráficos inline no chat** — figuras são salvas como arquivos
- Toda comunicação via texto; arquivos entregues com caminho completo ao final da resposta

---

## 7. Troubleshooting

### Problema 1: "Não consigo autorizar o Drive"

**Solução:**
1. Verifique se está logado na **mesma conta** Google do Colab
2. Tente abrir em uma **janela anônima**
3. Limpe os cookies do navegador

### Problema 2: "O botão não abre"

**Solução:**
1. Verifique se o pop-up não foi bloqueado pelo navegador
2. Clique com o botão direito → "Abrir em nova aba"
3. Desative extensões de bloqueador de pop-up

### Problema 3: "Dados não encontrados"

**Solução:**
- Isso é **comportamento esperado**. O UFVAI **não inventa dados**.
- Verifique o ano solicitado (talvez os dados ainda não sejam públicos)
- Consulte diretamente a fonte oficial mencionada na resposta

### Problema 4: "Sessão expirou"

**Solução:**
- Sessões do Colab expiram após ~30 minutos de inatividade
- Se você tiver backup, pode restaurar:
  1. Execute tudo novamente
  2. Clique em **🔄 Restaurar**
  3. Selecione seu backup mais recente

### Problema 5: "Backup não aparece"

**Solução:**
1. Verifique a pasta `Meu Drive/PesquisAI/backups/`
2. Os arquivos são salvos em ordem cronológica inversa (mais recente primeiro)
3. Verifique se você está na **mesma conta Google**

### Problema 6: Erro de indentação ou Python

**Solução:**
- Isso geralmente acontece durante atualizações
- Verifique se você tem a **versão mais recente** do repositório
- Tente baixar novamente o notebook do GitHub

### Problema 7 (.deb): "localhost:8001 recusa conexão"

**Solução (corrigido na v0.6.3+):**
1. Atualize para a versão mais recente do pacote (≥ 0.6.8-2)
2. Verifique se o processo está vivo: `cat ~/PesquisAI/pesquisai.pid`
3. Reinicie com `ufvai` — o servidor agora é **persistente** (não morre ao fim do boot)
4. Teste também `http://[::1]:8001` (dual-stack IPv4+IPv6)

### Problema 8 (.deb): "Não consigo digitar no terminal"

**Solução:** use versão ≥ 0.6.2 (flag `--writable` restaurada). Versões antigas abriam o ttyd em modo leitura.

### Problema 9 (.deb): "O app não abre sozinho"

**Solução:**
- O launcher (v0.6.2+) espera a porta subir e abre como **app separado** (Chrome --app → Chromium → Firefox → xdg-open)
- Para abrir manualmente: execute `ufvai` de novo (reabre a UI se já estiver rodando)
- Kill-switch: `UFVAI_NO_OPEN=1` desabilita a abertura automática

### Problema 10 (.deb): "Instalação reclama de python3-pip"

**Solução:**
```bash
sudo apt install python3-pip        # resolve o Depends
sudo dpkg -i pesquisai_0.6.17-offline_amd64.deb
```
Ou, em último caso: `sudo dpkg -i --force-depends pesquisai_*.deb` (o pip já estar presente é suficiente).

> ⚠️ Use apenas pacotes oficiais publicados no repositório GitHub. O `.deb` 0.6.5-1 e o 0.6.8-1 foram **vetados** (launcher regressivo) — instale ≥ 0.6.8-2.

---

## 8. 📎 Citação do UFVAI

### Como citar o UFVAI em trabalhos acadêmicos

**Referência ABNT NBR 6023:2018 (Software/Ferramenta):**

```
BRAGA, Gustavo Bastos. UFVAI: agente de inteligência artificial para pesquisa
científica. Versão 0.6.17. Viçosa: Universidade Federal de Viçosa, 2026.
Disponível em: https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/.
Acesso em: DD mês. AAAA.

Projeto registrado no SisPPG/UFV sob nº 10356285004.
Verificar autenticidade em: http://sisppg.ufv.br
```

**Formato simplificado (nota de rodapé):**

```
UFVAI, versão 0.6.17, desenvolvido por Gustavo Bastos Braga (UFV, 2026). Disponível em:
https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/.
```

### Exemplos de uso em diferentes situações

**1. No corpo do texto (ABNT — sistema autor-data):**

> Para a análise dos dados demográficos, utilizou-se o agente de pesquisa **UFVAI** (BRAGA, 2026), que integra consultas automatizadas às bases do IBGE e do DataSUS.

**2. Em seção de Materiais e Métodos:**

> O processamento e a organização dos dados foram realizados com o auxílio do **UFVAI** (BRAGA, 2026), um agente de inteligência artificial especializado em pesquisa científica com acesso às bases de dados oficiais brasileiras (IBGE e DataSUS), executado via Google Colaboratory. Todas as informações geradas pela ferramenta foram posteriormente revisadas e validadas pelos autores.

**3. Em seção de Agradecimentos:**

> Os autores agradecem ao desenvolvedor Gustavo Bastos Braga (UFV) pela disponibilização do agente **UFVAI**, utilizado como ferramenta auxiliar na coleta e organização de dados das bases públicas consultadas neste trabalho.

**4. Em nota de rodapé na primeira menção:**

> \* **UFVAI** é um agente de inteligência artificial de código aberto desenvolvido na Universidade Federal de Viçosa (UFV), especializado em pesquisa científica com acesso às bases oficiais do IBGE e DataSUS. Disponível em: https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/.

### Metadados para gerenciadores de referência

| Campo | Valor |
|---|---|
| **Tipo** | Software / Computer Program |
| **Autor** | Braga, Gustavo Bastos |
| **Título** | UFVAI: agente de inteligência artificial para pesquisa científica |
| **Versão** | 0.6.17 |
| **Ano** | 2026 |
| **Instituição** | Universidade Federal de Viçosa (UFV) |
| **URL** | https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/ |
| **Repositório** | https://github.com/gustavobraga-byte/PesquisAI |
| **Licença** | MIT |
| **Linguagem** | Python 3.10+ |
| **Plataforma** | Google Colaboratory |

### BibTeX (para usuários LaTeX):

```bibtex
@software{braga2026ufvai,
author = {Gustavo Bastos Braga},
title = {{UFVAI}: Agente de Intelig{\^e}ncia Artificial para Pesquisa Cient{\'\i}fica},
year = {2026},
version = {0.6.17},
institution = {Universidade Federal de Vi{\c{c}}osa (UFV)},
url = {https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/},
note = {Acessado em: DD m{\^e}s AAAA}
}
```

---

## 9. 🤖 Declaração de Uso de Inteligência Artificial (IA)

### Modelos para Inclusão em Trabalhos Acadêmicos

> **Importante:** As declarações abaixo são sugestões elaboradas conforme as diretrizes do **Committee on Publication Ethics (COPE)**, da **CAPES**, e de periódicos científicos como **Nature, Science, Elsevier e Springer**. Sempre verifique as políticas específicas do periódico ou da instituição para a qual você está submetendo o trabalho.

### Tabela Rápida: Qual modelo usar?

| Situação | Modelo Recomendado |
|---|---|
| Monografia, Dissertação ou Tese (UFV/ABNT) | Modelo A — Declaração Padrão Acadêmica |
| Artigo para periódico (seção de Métodos) | Modelo B — Materiais e Métodos |
| Artigo para periódico (seção de Agradecimentos) | Modelo C — Agradecimentos |
| Uso apenas para busca de dados (IBGE/DataSUS) | Modelo D — Auxílio com Dados |
| Uso para estruturação e formatação (ABNT/UFV) | Modelo E — Formatação e Estrutura |
| Resumo expandido para congresso | Modelo F — Declaração Curta |

### Modelo A — Declaração Padrão Acadêmica (TCC, Dissertação, Tese)

> **Recomendado para:** Trabalhos de conclusão de curso, dissertações e teses formatadas conforme normas UFV/ABNT. Inserir como seção própria após a Conclusão, antes das Referências.

```
DECLARAÇÃO DE USO DE INTELIGÊNCIA ARTIFICIAL

Durante a elaboração deste trabalho, foi utilizada a ferramenta UFVAI (BRAGA, 2026),
um agente de inteligência artificial de código aberto especializado em pesquisa
científica, desenvolvido na Universidade Federal de Viçosa (UFV). A ferramenta foi
empregada como auxílio nas seguintes etapas:

a) Consulta e extração de dados das bases oficiais do IBGE e DataSUS;
b) Organização e estruturação do referencial teórico conforme normas ABNT;
c) Revisão da formatação das referências bibliográficas;
d) [ESPECIFICAR OUTRAS ETAPAS, SE APLICÁVEL].

Declaro que todas as informações geradas pela ferramenta foram criteriosamente
revisadas, validadas à luz das fontes originais e editadas por mim. A ferramenta
foi utilizada exclusivamente como instrumento auxiliar, jamais como substituta
do trabalho intelectual de pesquisa, análise e redação. Assumo integral
responsabilidade pelo conteúdo final deste trabalho, incluindo a acurácia de
todos os dados, citações, análises e conclusões aqui apresentados.

A ferramenta UFVAI não foi listada como autora ou coautora deste trabalho,
em conformidade com os critérios de autoria do International Committee of
Medical Journal Editors (ICMJE) e com as diretrizes do Committee on Publication
Ethics (COPE).

Referência da ferramenta:
BRAGA, Gustavo Bastos. UFVAI: agente de inteligência artificial para
pesquisa científica. Versão 0.6.17. Viçosa: UFV, 2026. Disponível em:
https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/.
Registro SisPPG/UFV nº 10356285004 — http://sisppg.ufv.br
```

### Modelo B — Materiais e Métodos (Artigo Científico)

> **Recomendado para:** Artigos submetidos a periódicos que exigem menção de ferramentas na seção de Métodos.

```
O processamento e a organização dos dados foram realizados com o auxílio do
UFVAI (Braga, 2026), um agente de inteligência artificial especializado em
pesquisa científica, executado via Google Colaboratory, com acesso programático
às bases de dados do Instituto Brasileiro de Geografia e Estatística (IBGE) e
do Departamento de Informática do Sistema Único de Saúde (DataSUS). Todas as
informações extraídas pela ferramenta foram verificadas individualmente contra
suas fontes primárias originais e validadas pelos autores. A ferramenta não foi
utilizada para a redação de seções interpretativas (Discussão e Conclusão), que
permaneceram como trabalho intelectual exclusivo dos autores.
```

### Modelo C — Agradecimentos (Artigo Científico)

> **Recomendado para:** Periódicos que preferem a menção de ferramentas de IA na seção de Agradecimentos (ex.: política atual da Nature, Science).

```
Os autores declaram que, durante a elaboração deste trabalho, utilizaram o
UFVAI (Braga, 2026) como ferramenta auxiliar para [ESPECIFICAR: consulta a
bases de dados públicos / formatação de referências / revisão de normalização
documental]. Todo o conteúdo gerado pela ferramenta foi revisado e validado
pelos autores, que assumem total responsabilidade pela integridade e precisão
do manuscrito.
```

### Modelo D — Uso Específico para Coleta de Dados

> **Recomendado para:** Trabalhos onde o UFVAI foi usado basicamente para buscar dados no IBGE ou DataSUS.

```
Os dados demográficos e socioeconômicos utilizados neste estudo foram obtidos
por meio do UFVAI (Braga, 2026), um agente de IA que realiza consultas
automatizadas às APIs oficiais do IBGE (SIDRA) e do DataSUS. Todas as
extrações foram conferidas diretamente nas plataformas oficiais das respectivas
instituições. A ferramenta atuou exclusivamente como intermediadora na consulta,
não tendo qualquer participação na análise, interpretação ou redação dos
resultados.
```

### Modelo E — Uso para Formatação e Normalização

> **Recomendado para:** Trabalhos onde o UFVAI foi usado prioritariamente para formatação ABNT/UFV.

```
A formatação deste trabalho conforme as normas da Associação Brasileira de
Normas Técnicas (ABNT) e da Universidade Federal de Viçosa (UFV) foi realizada
com o auxílio do UFVAI (Braga, 2026), ferramenta de IA especializada que
incorpora o módulo UFV-ABNT para normalização documental. A adequação final às
normas foi verificada manualmente pelo autor.
```

### Modelo F — Declaração Curta (Resumo Expandido / Congresso)

> **Recomendado para:** Resumos expandidos submetidos a congressos, onde o espaço é limitado.

```
Declaramos o uso do UFVAI (Braga, 2026), agente de IA para pesquisa
científica, como ferramenta auxiliar na [ESPECIFICAR ETAPAS]. Todos os
conteúdos gerados foram revisados e validados pelos autores.
```

### Perguntas Frequentes sobre Declaração de Uso de IA

**Preciso mesmo declarar? Não é só uma ferramenta, como o Excel ou o Google Scholar?**

Sim. Ferramentas de IA generativa diferem de ferramentas convencionais porque produzem conteúdo original (texto, análise, interpretação) de forma autônoma. O COPE, a CAPES e os principais periódicos internacionais exigem transparência sobre seu uso. Além disso, declarar o uso de IA demonstra **integridade acadêmica** e protege você contra alegações de má conduta.

**Declarar o uso de IA pode desvalorizar meu trabalho?**

Não. Pelo contrário: a transparência é valorizada pela comunidade científica. Utilizar ferramentas modernas e declará-las adequadamente demonstra rigor metodológico. O problema não é usar IA — é **não declarar** seu uso.

**Posso usar o UFVAI para escrever seções inteiras?**

O UFVAI pode auxiliar na estruturação e redação de seções mais objetivas (Métodos, parte dos Resultados descritivos), mas as seções que envolvem interpretação e juízo crítico (Discussão, Conclusão) devem permanecer como trabalho intelectual do pesquisador. A ferramenta é um **copiloto**, não um **substituto**.

**O UFVAI pode ser considerado autor do meu trabalho?**

**Não.** Ferramentas de IA não atendem aos critérios de autoria do ICMJE (não podem assumir responsabilidade pelo conteúdo, aprovar versão final, ou responder por integridade do trabalho). O UFVAI deve ser citado como ferramenta, nunca como autor.

### Referências para Fundamentação

- COMMITTEE ON PUBLICATION ETHICS (COPE). **Authorship and AI tools**: COPE position statement. 2023. Disponível em: https://publicationethics.org/cope-position-statements/ai-author
- INTERNATIONAL COMMITTEE OF MEDICAL JOURNAL EDITORS (ICMJE). **Recommendations for the Conduct, Reporting, Editing, and Publication of Scholarly Work in Medical Journals**. 2024. Disponível em: https://www.icmje.org/recommendations/
- NATURE PORTFOLIO. **Editorial policies: Artificial Intelligence (AI)**. 2024. Disponível em: https://www.nature.com/nature-portfolio/editorial-policies/ai
- ELSEVIER. **The use of AI and AI-assisted technologies in writing for Elsevier**. 2024. Disponível em: https://www.elsevier.com/about/policies-and-standards/the-use-of-generative-ai-and-ai-assisted-technologies-in-writing-for-elsevier
- CAPES. **Orientações sobre integridade científica e uso de IA**. 2024.

---

## 10. ⚖️ Disclaimer do UFVAI — Termos de Uso e Isenção de Responsabilidade

> **Versão 0.6.8 — Agosto de 2026 · Termos de Uso v3**
> **ATENÇÃO: Leia atentamente este documento antes de utilizar o UFVAI. O uso da ferramenta implica a aceitação integral dos termos aqui dispostos.**

### 10.1 Natureza da Ferramenta

O **UFVAI** é um agente de inteligência artificial desenvolvido como ferramenta de apoio à pesquisa científica. Ele opera sobre **Modelos de Linguagem de Grande Porte (LLMs)** e integra-se a bases de dados públicos brasileiros por meio de módulos especializados (*skills*).

O UFVAI é um **software experimental, de código aberto, fornecido "como está" (*as is*)**, sem garantias de qualquer natureza — expressas ou implícitas — quanto ao seu funcionamento ininterrupto, precisão dos resultados ou adequação a qualquer finalidade específica.

### 10.2 Validação Humana Obrigatória

**Risco de Alucinação de IA:** Modelos de Linguagem de Grande Porte (LLMs), incluindo aqueles que alimentam o UFVAI, são suscetíveis ao fenômeno conhecido como **"alucinação"** — a geração de informações factualmente incorretas, dados inexistentes, referências fictícias ou afirmações plausíveis, porém falsas.

**É responsabilidade exclusiva e intransferível do usuário:**

- Revisar criteriosamente **todos** os dados, análises, textos e referências gerados pela ferramenta;
- Validar cada informação factual contra suas fontes primárias originais;
- Verificar a existência e a correção de toda citação bibliográfica sugerida;
- Confirmar a acurácia de todos os dados estatísticos antes de utilizá-los em qualquer publicação, relatório, decisão acadêmica, profissional ou política;
- Avaliar criticamente a qualidade metodológica das análises propostas pela ferramenta.

> **O UFVAI é um copiloto, não um piloto automático. O pesquisador humano é — e sempre será — o responsável último pela integridade do trabalho científico.**

### 10.3 Limitação de Responsabilidade

O desenvolvedor (Gustavo Bastos Braga) e a Universidade Federal de Viçosa (UFV) **não se responsabilizam** por:

| Item | Descrição |
|---|---|
| **Erros factuais** | Dados incorretos, incompletos ou desatualizados gerados pela ferramenta |
| **Decisões equivocadas** | Quaisquer decisões acadêmicas, profissionais, clínicas, políticas ou financeiras tomadas com base nos outputs do UFVAI |
| **Perdas e danos** | Danos diretos, indiretos, incidentais, especiais ou consequenciais decorrentes do uso ou da impossibilidade de uso da ferramenta |
| **Violação de direitos** | Eventual reprodução não intencional de material protegido por direitos autorais nos outputs gerados |
| **Indisponibilidade** | Interrupções no serviço causadas por falhas nas APIs de terceiros (Google Colab, IBGE, DataSUS, provedores de LLM), manutenção de servidores ou outros fatores técnicos |

O UFVAI depende de serviços de terceiros sobre os quais o desenvolvedor **não possui controle**: Google Colaboratory, APIs do IBGE e DataSUS, provedores de LLM e GitHub. Interrupções, alterações de política ou descontinuação de qualquer desses serviços podem afetar o funcionamento do UFVAI sem aviso prévio.

### 10.4 Uso Acadêmico e Publicações

Trabalhos acadêmicos que utilizarem o UFVAI em qualquer etapa da pesquisa (coleta de dados, análise, redação, formatação) **devem declarar explicitamente** o uso da ferramenta, conforme orientações do Committee on Publication Ethics (COPE), da CAPES e de periódicos científicos. Consulte a **Seção 9** para modelos prontos de declaração.

O UFVAI **não pode** ser listado como autor ou coautor de trabalhos acadêmicos, por não atender aos critérios de autoria do ICMJE.

### 10.5 Conformidade com a LGPD (Lei nº 13.709/2018)

O UFVAI foi projetado seguindo os princípios de ***Privacy by Design***, com bases legais declaradas — **consentimento (art. 7º I)** para o contrato de uso, **execução do serviço (art. 7º V)** para o e-mail de ativação e **legítimo interesse (art. 7º IX, sem cookies)** para a telemetria anônima opt-out — e respeito integral aos **direitos do titular (art. 18)**:

| Princípio da LGPD | Como o UFVAI aplica |
|---|---|
| **Segurança** | O app não armazena dados do usuário em servidores próprios. Todo processamento ocorre na sessão local do Google Colab — ou 100% na sua máquina, no modo offline (.deb). |
| **Retenção** | Os arquivos são salvos exclusivamente na conta Google Drive do usuário (ou em `~/PesquisAI` offline). Nenhum dado é retido pelo desenvolvedor. |
| **Finalidade** | Os dados são acessados exclusivamente para cumprir a tarefa de pesquisa solicitada pelo usuário; o e-mail serve apenas à ativação/contato sobre a ferramenta. |
| **Necessidade** | Apenas os dados estritamente necessários à pesquisa são processados. |
| **Transparência** | O usuário tem visibilidade total dos arquivos lidos e gravados na pasta `/PesquisAI/` do seu Drive. |
| **Autodeterminação** | Tela de **Termos de Uso v2.1**: aceite obrigatório + **e-mail de ativação obrigatório** (art. 7º V) + telemetria **ativa por padrão com direito de oposição** (opt-out, art. 7º IX e art. 18 §2º). |

#### Telemetria opt-out (Termos v2.1) — os 2 requisitos

A telemetria anônima vem **ativa por padrão** e só envia quando **os dois requisitos estão ativos simultaneamente**:

1. **Credenciais configuradas** pelo administrador (`UFVAI_GA_MEASUREMENT_ID` + `UFVAI_GA_API_SECRET`);
2. **Sem oposição do usuário** — caixa de telemetria marcada na tela de Termos (desmarcar registra a oposição) **e** kill-switch desligado (`UFVAI_TELEMETRY ≠ 0`).

Sem qualquer um deles, **nada é enviado**. Desde a v2.1 dos Termos o canal client-side envia apenas o `page_view` padrão, **sem cookie `_ga`** e sem evento customizado; o Google Analytics nunca recebe conteúdo das suas pesquisas, API keys ou dados pessoais, com `anonymize_ip`. E-mails **nunca** vão para o GA4.

#### E-mail de ativação obrigatório (v0.6.9 → v0.6.10: + campo Nome e IP na planilha)

- O campo de e-mail na tela de Termos é **obrigatório** para aceitar os Termos (finalidade: ativação/contato sobre o UFVAI — art. 7º V); sem um e-mail válido, o aceite é recusado;
- Gravação no SEU ambiente: `backups/ufvai_consentimento.json` (no Colab: no seu Drive; offline: `~/PesquisAI/backups/`) com resumo SHA-256 — permite pré-preencher a tela nas reaberturas;
- **Eliminação a qualquer momento** (LGPD art. 18): via opção de eliminação de contato da interface (`POST /api/contact/delete`); nesse caso o e-mail será novamente solicitado na próxima abertura;
- Painel **📊 Telemetria (Admin)** na barra superior permite ao mantenedor configurar o canal de recebimento (ex.: planilha Google via Apps Script) sem editar arquivos.

**Recomendações de Proteção de Dados:**

- **Não submeta dados pessoais sensíveis** (registros médicos, dados bancários, documentos de identificação) a menos que estejam previamente anonimizados — o agente interrompe gravações com dados sensíveis detectados;
- **Não compartilhe** o acesso à sua pasta `/PesquisAI/` com terceiros não autorizados;
- **Revise** os arquivos gerados antes de compartilhá-los, removendo eventuais informações sensíveis.

### 10.6 Direitos Autorais e Licenciamento

O código do UFVAI é distribuído sob a **Licença MIT**. O conteúdo gerado pelo UFVAI pertence ao usuário que o gerou, ressalvadas as seguintes condições:

- O usuário é responsável por verificar a originalidade do conteúdo e a ausência de plágio;
- Dados extraídos de fontes públicas (IBGE, DataSUS) devem ser atribuídos às suas respectivas fontes;
- O uso de conteúdo gerado por IA em publicações deve seguir as políticas do periódico ou instituição de destino.

### 10.7 Usos Não Permitidos

É expressamente vedado o uso do UFVAI para:

- Gerar, distribuir ou facilitar conteúdo ilegal, difamatório, fraudulento ou que viole direitos de terceiros;
- Disseminar desinformação científica deliberada;
- Burlar sistemas de verificação de originalidade ou integridade acadêmica;
- Substituir, sem a devida declaração, o trabalho intelectual que deveria ser realizado pelo pesquisador;
- Qualquer finalidade que viole a legislação brasileira ou internacional aplicável.

### 10.8 Aceitação dos Termos

Ao utilizar o UFVAI, você declara que:

- [x] Leu e compreendeu integralmente este Disclaimer;
- [x] Tem ciência dos riscos inerentes ao uso de inteligência artificial generativa;
- [x] Assume total responsabilidade pela validação dos resultados gerados;
- [x] Compromete-se a declarar o uso da ferramenta em publicações acadêmicas;
- [x] Isenta o desenvolvedor e a UFV de responsabilidade por quaisquer consequências decorrentes do uso da ferramenta.

> *O UFVAI é oferecido de boa-fé, com o propósito de impulsionar a pesquisa científica brasileira. Use com responsabilidade, senso crítico e integridade acadêmica.*

---

---

## 11. 🧠 Memória Persistente ("Minha memória") — desde a v0.5.1.8

A partir da versão **v0.5.1.8**, o UFVAI conta com **memória persistente entre sessões** — um vault em Markdown armazenado no seu Google Drive (Colab) ou em `~/PesquisAI/vault` (offline).

### 11.1 O que é o Vault?

O vault é uma pasta (`vault/`) dentro de `Meu Drive/PesquisAI/` que funciona como um **segundo cérebro** do agente. Ele mantém:

```
vault/
├── daily/          → Notas diárias (YYYY-MM-DD.md)
├── research/       → Projetos de pesquisa
├── literature/     → Revisões de literatura
├── methodology/    → Métodos analíticos
├── hypothesis/     → Hipóteses (H1, H2, …)
├── reference/      → Citações com DOI e BibTeX
├── sessions/       → Logs de sessão
├── moc/            → Maps of Content (índices)
├── inbox/          → Capturas rápidas
└── datasource/     → Fontes de dados consultadas
```

### 11.2 O que o UFVAI salva AUTOMATICAMENTE

O agente **não espera você pedir** — ele salva proativamente:

| Momento | O que é salvo |
|---------|--------------|
| **Início de cada sessão** | Nota diária com a atividade do dia |
| **Antes de buscar dados** (IBGE, DataSUS, etc.) | Registro da consulta (fonte, período, filtros) |
| **Ao encontrar paper relevante** | Nota com DOI, BibTeX e resumo |
| **Ao formular hipótese** | H₀, H₁, variáveis e plano de teste |
| **Ao adotar método analítico** | Pressupostos, comandos e limitações |
| **Ao final de cada sessão** | Log completo com interações e skills usadas |
| **Ao gerar figura/tabela** | Arquivo salvo em `assets/` e referenciado na nota |

### 11.3 Interface "Minha memória"

Na interface do UFVAI, clique no botão 🧠 para abrir o modal de memória. Você pode:

- **Preview** → Visualizar notas formatadas com Markdown e wikilinks
- **Editar** → Editar notas diretamente no navegador
- **Dividido** → Ver preview e edição lado a lado
- **Buscar** → Pesquisar texto em todas as notas do vault (busca textual BM25)

> A primeira abertura carrega o último daily note automaticamente. Reaberturas dentro de 5s são instantâneas (cache local). As notas da memória são sempre gravadas em **PT-BR** para indexação consistente.

### 11.4 Otimizações de Performance

| Otimização | O que faz | Benefício |
|------------|-----------|-----------|
| **Cache de 5s** | Armazena status + árvore de notas no frontend | 2ª abertura = instantânea |
| **Rota unificada** | Status + árvore chegam em 1 única chamada HTTP | 50% menos conexões |

### 11.5 Internacionalização (i18n) — 5 idiomas

O UFVAI suporta **5 idiomas** (chinês adicionado na v0.6.0):

| Idioma | Arquivo |
|--------|---------|
| Português (Brasil) — padrão | `agents/AGENTS.pt.md` |
| English (US) | `agents/AGENTS.en.md` |
| Español | `agents/AGENTS.es.md` |
| Français | `agents/AGENTS.fr.md` |
| 简体中文 (Chinês) | `agents/AGENTS.zh.md` |

Desde a v0.6.1, o **idioma do sistema é detectado automaticamente** na primeira execução (`$LANG`, `navigator.language`) e a preferência é persistida. Para alterar, use o seletor de idioma na interface ou defina `PESQUISAI_LANG=en_US`.

## 12. Histórico de Versões

Resumo das versões da série 0.6.x (detalhes completos no `CHANGELOG.md` do repositório):

| Versão | Data | Destaques |
|--------|------|-----------|
| **0.6.17** | 01-02/09/2026 | ⚡ **Memória abre instantânea via menu**: singleton `_get_memory()` em RAM (índice BM25 construído 1×), rebuild em background (stale-while-revalidate), warm-up no boot, árvore em RAM, cache frontend 120 s + prefetch |
| **0.6.16** | 01/09/2026 | 🐛 Retorno registra **1 linha apenas no clique** na planilha (removidos heartbeats automáticos duplicados; guard `_heartbeatSent`) |
| **0.6.15** | 01/09/2026 | 🐛 Prompt inicial respeita o idioma detectado do sistema/navegador (`_ensure_lang_initialized()` + auto-sync frontend) |
| **0.6.14** | 01/09/2026 | 🐛 IP real via ipify client-side (proxy Colab não injeta XFF) + todo acesso logado na planilha (heartbeat automático) |
| **0.6.13** | 01/09/2026 | 🐛 IP real do cliente (cadeia X-Forwarded-For direita→esquerda, saltando privados) + fallback perfil persistente no heartbeat |
| **0.6.12** | 01/09/2026 | 🐛 Preview da memória responsivo em mobile (min-height fix) |
| **0.6.11** | 01/09/2026 | 🐛 Hotfix `isoformat` no cache BM25 (search.py + models.py) |
| **0.6.10** | 01/09/2026 | Memória BM25 com cache em disco + paginação; Termos v6 com campo **Nome** ao lado do e-mail e **IP** capturado (planilha 8 cols + flag `usuario_ativo` por acesso); memória responsiva mobile; bump version |
| **0.6.9** | 25/08/2026 | Termos v2.1: telemetria opt-out sem cookies (art. 7º IX); e-mail de ativação obrigatório (art. 7º V); perfil persistente em `backups/` com pré-preenchimento/pulo da tela; botão 📘 Manual + rota `/api/manual`; tela de Termos responsiva; logs do Colab fora do Drive (`/tmp/ufvai-logs/`); correção DebugView (`debug_mode`) |
| **0.6.8** | 24/08/2026 | Canal de contato via planilha Google + Apps Script (`UFVAI_CONTACT_ENDPOINT`); rebuild `.deb` 0.6.8-2 com launcher estável |
| **0.6.7** | 23/08/2026 | Painel de boot contínuo no tema da logomarca (Colab); botão final com logo embutida; URL de contato configurável pelo painel Admin |
| **0.6.6** | 22/08/2026 | Favicon UFVAI (incl. Colab); contato opt-in LGPD na tela de Termos (Termos v3); `POST /api/contact/delete`; registro voluntário com webhook Google Sheets |
| **0.6.5** | — | ⛔ **VETADA** (launcher regressivo) — substituída pela 0.6.6 |
| **0.6.4** | 22/08/2026 | Marca UFVAI completa; temas do terminal (escuro dourado/claro papel); logo oficial na abertura; Termos v2 (CNPq 2.664/2026, POSIC UFV); painel 📊 Telemetria Admin |
| **0.6.3** | 22/08/2026 | Servidor persistente offline (fim do "conexão recusada"); dual-stack IPv4+IPv6; ícone UFVAI no dock |
| **0.6.2** | 22/08/2026 | Terminal gravável restaurado (`--writable`); launcher app-mode com curl-wait; `UFVAI_TELEMETRY_DEBUG=1` |
| **0.6.1** | 22/08/2026 | Idioma do sistema detectado; troca de idioma robusta; auto-open offline (`UFVAI_NO_OPEN=1`) |
| **0.6.0** | 21/08/2026 | Rebrand visual PesquisAI→UFVAI; hardening de segurança (CORS removido, token de sessão); telemetria opt-in GA4; 中文 zh_CN |

> Séries anteriores (0.5.x): memória persistente Obsidian, editor de memória no botão 🧠, skill Memorial UFV, backup/restauração de sessão.

---

## Apêndice: Marcadores de Evidência

O UFVAI usa estes marcadores para indicar o nível de confiança:

| Marcador | Significado |
|----------|-------------|
| `[DADO CONFIRMADO]` | Extraído diretamente de fonte primária via skill |
| `[ESTIMATIVA FUNDAMENTADA]` | Inferido de dados disponíveis, com metodologia explícita |
| `[SEM DADOS SUFICIENTES]` | Skills não retornaram informação confiável |

---

## Contato e Suporte

- **Criador:** Gustavo Bastos Braga (UFV)
- **Email:** gustavo.braga@ufv.br
- **GitHub:** https://github.com/gustavobraga-byte/PesquisAI

> **Aviso:** Este é um ambiente experimental. A responsabilidade pelo uso dos dados é do usuário.

---

*Documentação atualizada: Setembro 2026*  
*UFVAI v0.6.17 · Registro SisPPG/UFV nº 10356285004*
