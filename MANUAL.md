# 📘 Manual do PesquisAI

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

No caso do **PesquisAI**, essas conexões são chamadas de **Skills**:

| Skill | O que ela acessa |
|-------|------------------|
| `ibge-br` | Todos os bancos de dados públicos do IBGE (Censo, PNAD, PIB, etc.) |
| `opendatasus` | Todos os dados de saúde pública do Brasil (DataSUS, SINAN, SUS) |
| K-Dense Scientific Skills | Ferramentas de pesquisa científica, estrutura de artigos, busca de literatura |
| `UFV-ABNT` | Normas de formatação acadêmica da UFV e ABNT |

**Isso é revolucionário:** quando o PesquisAI precisa de um dado sobre desemprego no Brasil, ele **não inventa**. Ele **acessa diretamente o IBGE** e traz o dado REAL, com fonte, ano, e nota metodológica.

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

No caso do **PesquisAI**, essas regras são:

| Regra | O que significa na prática |
|-------|-----------------------------|
| **Política de Zero-Fabricação** | Se o PesquisAI não encontrar um dado, ele **NÃO inventa**. Ele diz explicitamente: *"Não foram encontrados dados suficientes nas fontes disponíveis para embasar esta afirmação."* |
| **Transparência total sobre fontes** | Toda afirmação factual vem acompanhada de **fonte, ano de referência, e nota metodológica** quando aplicável. |
| **Marcadores de nível de evidência** | O PesquisAI usa marcadores explícitos: `[DADO CONFIRMADO]`, `[ESTIMATIVA FUNDAMENTADA]`, `[SEM DADOS SUFICIENTES]`. |
| **Dados nacionais primeiro** | Para qualquer afirmação sobre o Brasil, ele consulta `ibge-br` ou `opendatasus` **antes** de qualquer outra fonte. |
| **Não substitui julgamento crítico** | O PesquisAI é **ferramenta auxiliar**, não substituto do pesquisador. Ele **nunca** toma decisões ou afirma verdades absolutas em nome do usuário. |

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

No caso do PesquisAI:
- Artigos salvos em `.md` e `.pdf`
- Datasets limpos organizados
- Outputs de análises estatísticas
- Gráficos e tabelas
- Tudo salvo em localização conhecida (sua pasta `PesquisAI` no seu Google Drive)


---

## 🚀 O que é o PesquisAI?

O **PesquisAI** é uma **Inteligência Artificial Agentica especializada em pesquisa científica brasileira**.

Ele foi construído para resolver um problema específico: **como usar IA no ambiente acadêmico sem comprometer a integridade científica, sem inventar dados, e com acesso a fontes oficiais brasileiras**.

### O que torna o PesquisAI único?

Existem outras IAs Agenticas no mercado. Mas o PesquisAI é diferente porque:

| Característica | Explicação |
|----------------|------------|
| **Especializado no Brasil** | A maioria das IAs agenticas são treinadas para dados americanos ou europeus. O PesquisAI tem **conexões diretas com IBGE, DataSUS, e normas ABNT/UFV**. |
| **Foco em integridade científica** | A regra número um do PesquisAI é **não inventar nada**. Tudo vem com fonte. Se não tem dado, ele diz que não tem. |
| **100% gratuito e aberto** | O PesquisAI roda no **Google Colab** (infraestrutura gratuita do Google) e todo o código é aberto. |
| **Salva tudo no seu Drive** | Nada fica "preso" na plataforma. Todos os arquivos gerados vão para **seu Google Drive**, na pasta `PesquisAI`. |
| **Habilidades específicas para academia** | Formatação ABNT, estrutura IMRaD, busca de literatura, normais de congressos — tudo integrado. |

---

## 💡 Coisas que SOMENTE uma IA Agentica pode fazer

Vamos ser muito claros: **não são perguntas e respostas**. São **tarefas completas** que envolvem múltiplos passos, acesso a fontes externas, execução de código, e entrega de resultados concretos.

Aqui estão exemplos do que o PesquisAI pode fazer **que nenhuma IA tradicional conseguiria**:

---

### 📝 Exemplo 1: Revisão Sistemática Completa

**Tarefa:**
> "Faça uma revisão sistemática sobre 'Efeitos do PRONAF na agricultura familiar brasileira' seguindo as diretrizes PRISMA."

**O que o PesquisAI faz (autonomamente):**

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

**O que o PesquisAI faz (autonomamente):**

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

**O que o PesquisAI faz (autonomamente):**

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

**O que o PesquisAI faz (autonomamente):**

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

**O que o PesquisAI faz (autonomamente):**

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

Se você trabalha com **economia, extensão rural, ciências agrárias, desenvolvimento rural, ou qualquer área que usa dados públicos brasileiros**, o PesquisAI representa uma mudança de paradigma.

### Antes do PesquisAI (e IAs tradicionais):

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

### Com o PesquisAI (IA Agentica):

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

O PesquisAI **NÃO substitui o pesquisador**. Ele **amplifica** o pesquisador.

| O PesquisAI faz | O PESQUISADOR(A) faz |
|------------------|----------------------|
| Buscar dados em fontes públicas | Definir a PERGUNTA DE PESQUISA |
| Limpar e organizar dados | Definir a ESTRATÉGIA DE IDENTIFICAÇÃO |
| Executar análises estatísticas | INTERPRETAR resultados à luz da teoria |
| Estruturar textos conforme normas | FAZER A CONTRIBUIÇÃO CIENTÍFICA |
| Formatar em ABNT | Avaliar CRITICAMENTE tudo |
| Salvar arquivos organizados | Tomar DECISÕES |

O PesquisAI é uma **ferramenta de amplificação**. Ele tira de você o trabalho repetitivo, burocrático, mecânico — para que você possa se concentrar no que realmente importa: **o pensamento científico**.

---

## ⚠️ Princípios Fundamentais do PesquisAI

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
6. [Princípios e Limitações](#6-princípios-e-limitações)
7. [Troubleshooting](#7-troubleshooting)

---

## 1. Primeiros Passos

---

## 2. Primeiros Passos

### 2.1 Abrindo no Colab

1. **Upload** do arquivo `PesquisAI_Colab.ipynb` para o seu Google Drive
2. Clique duas vezes para abrir no **Google Colab**
3. No menu superior: **Ambiente de execução → Executar tudo** (ou `Ctrl + F9`)

### 2.2 Primeira Execução

Você verá esta sequência:

```
⏳ Carregando o PesquisAI...
📥 Baixando arquivos...
Carregando o PesquisAI...

==================================================
  🧑‍🔬  INICIANDO PESQUISAI
==================================================
```

**Autorize o Google Drive:**
1. Clique no link que aparecerá
2. Logue com sua conta Google
3. Clique em **Permitir**
4. Copie o código e cole no campo do Colab
5. Pressione `Enter`

### 2.3 Aguardando Carregamento

Durante a instalação, aparecerão **piadas científicas** para entreter enquanto você espera (demora em torno de 2 a 3 minutos para iniciar):

```
🧬 Se a evolução dependesse dessa velocidade, ainda seríamos amebas.
💻 Mais lento que bubble sort em 1 milhão de elementos.
🌌 O universo tem 13.8 bilhões de anos. Esse processo parece mais velho.
...
```

### 2.4 Tudo Pronto!

Quando terminar, você verá:

```
✨ PesquisAI pronto!
```

E logo depois, um **botão gigante**:

```
🚀 ABRIR O PESQUISAI →
```

**Clique no botão** para abrir a interface visual.

---

## 3. Skills Disponíveis

O PesquisAI utiliza **skills** (módulos especializados) para acessar dados e ferramentas.

### 3.1 Dados Brasileiros (Prioridade Máxima)

| Skill | Fonte | O que faz |
|-------|-------|-----------|
| `ibge-br` | IBGE | Censo, PNAD, PIB, dados demográficos, socioeconômicos |
| `opendatasus` | DataSUS | Epidemiologia, SUS, mortalidade, SINAN, notificações |

> **Regra de Ouro:** Para qualquer afirmação sobre o Brasil, o PesquisAI consulta `ibge-br` ou `opendatasus` ANTES de responder.

### 3.2 Pesquisa Científica

| Skill | Fonte | O que faz |
|-------|-------|-----------|
| K-Dense | Scientific Agent Skills | Estrutura IMRaD, revisão sistemática, busca de literatura, formatação APA/Vancouver |

### 3.3 Normas Acadêmicas

| Skill | Norma | O que faz |
|-------|-------|-----------|
| `UFV-ABNT` | ABNT + UFV | Formatação de trabalhos acadêmicos conforme normas da UFV e ABNT |

---

## 4. Fluxo de Trabalho

Todo ciclo de pesquisa no PesquisAI segue **6 etapas obrigatórias**:

```
┌─────────────────────────────────────────────────────────┐
│  1. COMPREENSÃO       Analise o escopo e a pergunta     │
│                       de pesquisa antes de qualquer ação │
├─────────────────────────────────────────────────────────┤
│  2. COLETA DE DADOS   Acione as skills relevantes:      │
│                       K-Dense → literatura acadêmica    │
│                       ibge-br → dados BR gerais         │
│                       opendatasus → dados de saúde BR   │
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

## 5. Exemplos Práticos

### Exemplo 1: Consulta Rápida de Dados

**Pergunta:**
> "Qual a população do Brasil em 2022?"

**O que o PesquisAI faz:**
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

**O que o PesquisAI faz:**
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

**O que o PesquisAI faz:**
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

## 6. Backup e Restauração

### 6.1 Salvando sua Sessão

No topo da interface do PesquisAI, há 3 botões importantes:

| Botão | O que faz |
|-------|-----------|
| 💾 **Salvar backup** | Exporta a sessão atual para um arquivo JSON no Drive |
| 🔄 **Restaurar** | Abre uma lista de backups anteriores para restaurar |
| 📁 **Drive** | Abre a pasta do PesquisAI no Google Drive |

### 6.2 Fazendo Backup

1. Clique em **💾 Salvar backup**
2. O arquivo é salvo automaticamente em:
   ```
   Meu Drive/PesquisAI/backups/backup_abc123_14-35-22_22-05-2026.json
   ```
3. Formato do nome: `backup_<id_sessão>_HH-MM-SS_DD-MM-AAAA.json`

### 6.3 Restaurando Backup

1. Clique em **🔄 Restaurar**
2. Uma lista de backups aparecerá (mais recentes primeiro)
3. Clique no backup que deseja restaurar
4. Confirme a restauração
5. Atualize a página para acessar a sessão restaurada

> **Dica:** Use o menu `Ctrl + P` → `switch session` para alternar entre sessões.

---

## 7. Limitações Importantes

### 7.1 O que o PesquisAI NÃO faz

| Limitação | Explicação |
|-----------|------------|
| **Não substitui pesquisador humano** | Todo resultado deve ser revisado criticamente |
| **Não acessa bases pagas** | Apenas dados públicos via skills |
| **Não faz coleta primária** | Não realiza entrevistas, experimentos ou surveys |
| **Não garante tempo real** | Dados dependem da disponibilidade das APIs das skills |
| **Sem memória entre sessões** | Cada conversa começa com contexto limpo |

### 7.2 Diretório Único

O **único diretório acessível** é:
```
/content/drive/My Drive/PesquisAI/
```

Todos os arquivos gerados são salvos **exclusivamente** nesta pasta.

### 7.3 Ambiente 100% Remoto

- Nenhuma interface gráfica disponível
- Todo comunicação via texto
- Arquivos salvos no Google Drive

---

## 8. Troubleshooting

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
- Isso é **comportamento esperado**. O PesquisAI **não inventa dados**.
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

---

## Apêndice: Marcadores de Evidência

O PesquisAI usa estes marcadores para indicar o nível de confiança:

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

*Documentação atualizada: Maio 2026*  
*PesquisAI v1.0*
