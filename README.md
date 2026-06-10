# 🔬 PesquisAI — Agente de IA para Pesquisadores Científicos

 [![Abrir no Colab](https://img.shields.io/badge/Clique_aqui-Comece_a_usar-brightgreen?style=for-the-badge)](https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/blob/main/PesquisAI.ipynb)


> Ecossistema de agentes de IA para acelerar a pesquisa científica.

[![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/blob/main/PesquisAI.ipynb)
[![Licença MIT](https://img.shields.io/badge/licença-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Status](https://img.shields.io/badge/status-em%20desenvolvimento-yellow.svg)]()
[![SisPPG/UFV](https://img.shields.io/badge/SisPPG-10356285004-blue.svg)](http://sisppg.ufv.br)

O **PesquisAI** é um agente de Inteligência Artificial construído sobre a arquitetura **OpenCode**, projetado especificamente para pesquisadores, acadêmicos e cientistas. Ele automatiza etapas que vão do levantamento bibliográfico à estruturação de artigos, integrando fontes de dados públicos do Brasil.

---
## 🤯 PesquisAI: A ferramenta que seu orientador não te contou! (Só não esqueça de fazer o double-check 😅) 

## ✨ O que ele faz

| Capacidade | Descrição |
|---|---|
| 📊 **Dados IBGE** | Consulta e extração de dados estatísticos, demográficos e socioeconômicos |
| 🏥 **Dados DataSUS** | Acesso e análise de dados públicos de saúde via OpenDataSUS |
| 🌾 **Dados Agro & Ambientais** | Acesso a dados do agronegócio brasileiro e cadastro ambiental rural |
| 🇧🇷 **Dados Brasil** | Conjunto amplo de indicadores e datasets oficiais brasileiros |
| 📚 **Pesquisa científica** | Mineração de textos, revisão bibliográfica e suporte metodológico |
| ✍️ **Redação acadêmica** | Auxílio na estruturação e revisão de artigos científicos |
| 🔬 **Análise qualitativa** | Análise de conteúdo com métodos clássicos e avançados (Reinert, similitude, codificação) |
| 📐 **Normas ABNT/UFV** | Formatação e normalização de trabalhos acadêmicos |

---

## 🚀 Início rápido

### Opção 1 — Google Colab (sem instalação)

A forma mais rápida. Nenhuma configuração necessária:

1. Clique no badge do Colab acima
2. No menu, vá em **Ambiente de execução → Executar tudo** (ou `Ctrl+F9`)
3. Aguarde ~2 minutos para o ambiente carregar
4. Role até a última célula e clique em **🤖 Abrir o PesquisAI**



---

## 🛠️ Skills disponíveis

O PesquisAI opera por módulos especializados (*skills*). Cada skill conecta o agente a uma fonte de dados ou capacidade específica:

### `skill-ibge` · [@gustavobraga-byte](https://github.com/gustavobraga-byte)
Consulta automatizada à API do IBGE. Suporta dados do Censo, PNAD, PIB municipal, índices de preços e indicadores demográficos.

### `skill-datasus` · [@gustavobraga-byte](https://github.com/gustavobraga-byte)
Integração com o OpenDataSUS para coleta e análise de dados de saúde pública: mortalidade, internações, cobertura vacinal e outros.

### `skill-UFV-ABNT` · [@gustavobraga-byte](https://github.com/gustavobraga-byte)
Formatação e normalização de trabalhos acadêmicos conforme as normas da Universidade Federal de Viçosa (UFV) e da ABNT.

### `skill-analise-qualitativa` · [@gustavobraga-byte](https://github.com/gustavobraga-byte)
Possibilita uma análise qualititativa e de conteúdo completa, substituindo sofwares especializados como NVivo e Iramuteq executando metódos clássicos e avançados (por exemplo, análise fatorial, análise de similitude, codificação qualitativa, método de Reinert, ...).

### `scientific-skills` · [@K-Dense-AI](https://github.com/K-Dense-AI)
Ferramentas focadas em pesquisa acadêmica: mineração de textos científicos, revisão bibliográfica e suporte metodológico.

### `skill-dados-brasil` · [@gustavobraga-byte](https://github.com/gustavobraga-byte)
Conjunto amplo de indicadores e datasets oficiais brasileiros, complementando as bases do IBGE e DataSUS com outras fontes nacionais.

### `skill-agrobr` · [@gustavobraga-byte](https://github.com/gustavobraga-byte)
Dados do agronegócio brasileiro: produção agrícola, pecuária, comércio internacional do setor e cadastro ambiental rural (CAR).

---

## 🗺️ Roadmap

| Fase | Período | Foco |
|---|---|---|
| **1 — Base sólida** | Meses 1–3 | CLI, testes, CI/CD, instalação local |
| **2 — Expansão de dados** | Meses 4–7 | Inserir novas habilidades: IPEA, INEP, Sucupira/CAPES, plugins,... |
| **3 — Interface** | Meses 8–11 | Aprimorar interface web, editor de artigos, possibilidade de copilot |
| **4 — Ecossistema** | Meses 12–18 | API pública, versão SaaS, integração institucional |

---

## 🤝 Como contribuir

Contribuições são bem-vindas — especialmente novas skills para fontes de dados públicos brasileiros.

```bash
# 1. Faça um fork e clone o seu fork
git clone https://github.com/SEU_USUARIO/PesquisAI.git

# 2. Crie uma branch para sua contribuição
git checkout -b feature/skill-exemple
# 3. Desenvolva, teste e abra um Pull Request
```

Consulte o arquivo [`AGENTS.md`](AGENTS.md) para entender a arquitetura das skills e os padrões de desenvolvimento esperados.

**Ideias de contribuição:**
- Skills para novas fontes (IPEA, INEP, ANEEL, ANS, IBICT...)
- Melhorias na skill científica (suporte a mais bases como Scielo, BDTD)
- Traduções da documentação
- Casos de uso e exemplos de pesquisa

---

## ⚙️ Arquitetura

O PesquisAI usa o **ttyd** para renderizar um terminal Linux interativo via navegador dentro do proxy do Google Colab, com o ecossistema OpenCode injetado como ambiente isolado:

```
Google Colab
└── ttyd (terminal web na porta 8000)
    └── opencode (runtime do agente)
        ├── skill-ibge
        ├── skill-datasus
        ├── skill-dados-brasil
        ├── skill-agrobr
        ├── ufv-abnt
        ├── skill-analise-qualitativa
        ├── scientific-skills
        └── pesquisai (instruções do agente)
```

As dependências são gerenciadas pelo [uv (Astral)](https://github.com/astral-sh/uv) para instalação ultrarrápida e ambientes reproduzíveis.

---

## Declaração de Limitações

O PesquisAI:
- **Não substitui** a revisão por pares nem o julgamento de um pesquisador humano.
- **Não acessa** bases de dados pagas sem integração configurada.
- **Não realiza** coleta primária de dados (entrevistas, experimentos, surveys).
- **Não garante** atualização em tempo real; a disponibilidade dos dados depende das APIs externas.
- 🚨 **ATENÇÃO:** Sempre revise e confirme a precisão de todas as informações geradas por esta IA antes de utilizá-las em decisões ou projetos críticos.

---
---

## Citação

**ABNT NBR 6023:2018:**

```
BRAGA, Gustavo Bastos. PesquisAI: agente de inteligência artificial para pesquisa
científica. Versão 0.2. Viçosa: Universidade Federal de Viçosa, 2026.
Disponível em: https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/.
Acesso em: DD mês. AAAA.

Projeto registrado no SisPPG/UFV sob nº 10356285004.
Verificar autenticidade em: http://sisppg.ufv.br
```

**BibTeX:**

```bibtex
@software{braga2026pesquisai,
  author       = {Gustavo Bastos Braga},
  title        = {{PesquisAI}: Agente de Intelig{\^e}ncia Artificial
                  para Pesquisa Cient{\'\i}fica},
  year         = {2026},
  version      = {0.2},
  institution  = {Universidade Federal de Vi{\c{c}}osa (UFV)},
  url          = {https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/}
}
```

---

## Declaração de Uso de IA

O uso do PesquisAI em trabalhos acadêmicos **deve ser declarado** conforme diretrizes do COPE, CAPES e principais periódicos. Consulte o arquivo [`declaracao_uso_ia.md`](declaracao_uso_ia.md) para modelos prontos (ABNT, ICMJE, Nature, Science, Elsevier, Springer).

---

## Disclaimer

O PesquisAI é um **software experimental fornecido "como está"**, sem garantias. LLMs podem **alucinar** — é responsabilidade exclusiva do usuário validar todos os dados, análises e referências gerados. Consulte o [`disclaimer_pesquisai.md`](disclaimer_pesquisai.md) para os termos completos.


---
## 📬 Contato

Desenvolvido por **Gustavo Bastos Braga** na Universidade Federal de Viçosa (UFV).

- ✉️ gustavo.braga@ufv.br
- 🐙 [@gustavobraga-byte](https://github.com/gustavobraga-byte)

---

Feito com 💙 para impulsionar a ciência brasileira.
