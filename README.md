# 🔬 PesquisAI — Agente de IA para Pesquisadores Científicos

 [![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/blob/main/PesquisAI.ipynb)


O **PesquisAI** é um ecossistema de agentes de Inteligência Artificial baseado na arquitetura **OpenCode**. Ele foi projetado especificamente para automatizar, acelerar e otimizar o fluxo de trabalho de pesquisadores, acadêmicos e cientistas brasileiros, cobrindo etapas que vão desde o levantamento bibliográfico até a estruturação e submissão de artigos científicos.

---

## 🚀 Como Executar Grátis (Sem Instalação)

A forma mais rápida de testar o PesquisAI é através do Google Colab. Você não precisa instalar nada na sua máquina:

1. Clique no botão abaixo para abrir o notebook oficial:
   [![Abrir no Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/gustavobraga-byte/PesquisAI/blob/main/PesquisAI.ipynb)
2. No menu superior do Colab, clique em **Ambiente de execução** ➡️ **Executar tudo** (ou use o atalho `Ctrl + F9`).
3. Aguarde cerca de **2 minutos** para o download do ambiente.
4. Role até a última célula do notebook e clique no botão azul **🤖 Abrir o PesquisAI**.

---

## 🛠️ Skills Integradas (Habilidades do Agente)

O PesquisAI opera através de módulos especializados (*skills*) focados no cenário científico e de dados do Brasil:

*   **📊 Skill-IBGE (`gustavobraga-byte`)**: Consulta automatizada e extração de dados estatísticos, demográficos e socioeconômicos do Instituto Brasileiro de Geografia e Estatística.
*   **🏥 Skill-DataSus (`gustavobraga-byte`)**: Integração com a base de dados do OpenDataSUS para coleta e análise de dados públicos de saúde.
*   **📚 Scientific-Skills (`K-Dense-AI`)**: Ferramentas focadas em pesquisa acadêmica, mineração de textos científicos, revisão bibliográfica e suporte metodológico.

---

## ⚙️ Estrutura da Arquitetura

O projeto utiliza o **ttyd** para renderizar um terminal Linux interativo via navegador web dentro do proxy do Google Colab, injetando as variáveis do ecossistema OpenCode:

```bash
# O ambiente instala dependências via uv (Astral) de forma ultrarrápida:
curl -LsSf https://astral.sh | sh

# Inicializa o ecossistema isolado
ttyd -p 8000 bash -i -c "opencode; exec bash"
```

---

## 🤝 Como Contribuir

Contribuições são extremamente bem-vindas! Se você deseja criar uma nova *skill* de dados públicos (ex: IPEA, INEP) ou melhorar a inteligência do agente científico:

1. Faça um **Fork** do projeto.
2. Crie uma branch para sua modificação (`git checkout -b feature/NovaSkill`).
3. Envie o **Pull Request** para análise.

---

## 📬 Contato e Suporte

*   **Autor:** Gustavo Bastos Braga — Universidade Federal de Viçosa (UFV)
*   **E-mail:** [gustavo.braga@ufv.br](mailto:gustavo.braga@ufv.br)
*   **GitHub:** [@gustavobraga-byte](https://github.com)

---
<p align="center">Desenvolvido com 💙 para impulsionar a comunidade científica brasileira.</p>
