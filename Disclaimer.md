# 🔍 PesquisAI

<p align="left">
  <img src="https://img.shields.io/github/license/gustavobraga-byte/PesquisAI?style=flat-square" alt="License">
  <img src="https://img.shields.io/github/stars/gustavobraga-byte/PesquisAI?style=flat-square" alt="Stars">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square" alt="Python Version">
  <img src="https://img.shields.io/badge/LGPD-Conforme-success?style=flat-square" alt="LGPD Compliance">
</p>

O **PesquisAI** é um assistente inteligente desenvolvido para otimizar o fluxo de pesquisas, análise de dados e geração de relatórios estruturados. Integrado diretamente ao ambiente do Google Drive, o sistema centraliza todas as operações em um diretório seguro, garantindo organização e rastreabilidade dos arquivos gerados.

---

## 🚀 Funcionalidades

* **Organização Centralizada:** Leitura e escrita restritas à pasta exclusiva do projeto no Google Drive.
* **Processamento Inteligente:** Análise de documentos e geração de relatórios automatizados via IA.
* **Rastreabilidade:** Geração automática de links de acesso para cada novo arquivo exportado.

## 📁 Estrutura de Diretórios

Para o funcionamento correto do ecossistema, o app opera estritamente sob o seguinte caminho:
* **Diretório Base:** `/content/drive/My Drive/PesquisAI/`

> ⚠️ **Nota:** Todos os arquivos permanentes criados pelo sistema serão salvos exclusivamente nesta pasta. 
---

## ⚖️ Disclaimer (Aviso de Isenção de Responsabilidade)

O uso do **PesquisAI** implica a aceitação dos seguintes termos:

1. **Validação Humana Obrigatória:** Este aplicativo utiliza Modelos de Linguagem de Grande Porte (LLMs). Embora a IA seja altamente capaz, ela está sujeita a "alucinações" (geração de dados incorretos ou falsos). **É responsabilidade exclusiva do usuário revisar, validar e homologar todos os dados, códigos e relatórios gerados antes de tomadas de decisão.**
2. **Uso de Ferramentas de Terceiros:** O app depende de APIs externas (como Google Drive API e provedores de IA). Interrupções nesses serviços podem afetar temporariamente a performance da ferramenta.
3. **Responsabilidade por Execução:** Os desenvolvedores não se responsabilizam por quaisquer perdas financeiras, erros de pesquisa ou decisões estratégicas equivocadas baseadas nos outputs gerados por este software.

---

## 🔒 Conformidade com a LGPD (Privacidade e Dados)

O **PesquisAI** foi projetado seguindo os princípios de *Privacy by Design*, alinhando-se à **Lei Geral de Proteção de Dados (Lei nº 13.709/2018)**:

| Princípio da LGPD | Como o PesquisAI Aplica |
| :--- | :--- |
| **Segurança e Retenção** | O app **não armazena** seus dados em servidores próprios. Todo o processamento ocorre na sessão local do colab e os dados são salvos diretamente na sua conta privada do Google Drive. |
| **Finalidade e Necessidade** | Os dados e arquivos acessados pelo app servem exclusivamente para o propósito da pesquisa solicitada pelo usuário no momento da execução. |
| **Transparência** | O usuário tem total controle e visibilidade dos arquivos que estão sendo lidos e gravados na pasta dedicada `/PesquisAI/`. |

### 💡 Recomendações Importantes ao Usuário:
* **Dados Pessoais Sensíveis:** Evite submeter documentos que contenham dados pessoais altamente sensíveis (como registros médicos, dados bancários ou senhas) se o modelo de IA utilizado for de nuvem pública, a menos que você tenha uma camada de anonimização prévia.
* **Controle de Acesso:** Não compartilhe o acesso à sua pasta `/PesquisAI/` com terceiros não autorizados, pois ela contém o histórico das suas interações e relatórios gerados.
