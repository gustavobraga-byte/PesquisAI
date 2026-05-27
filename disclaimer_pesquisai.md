# ⚖️ Disclaimer do PesquisAI — Termos de Uso e Isenção de Responsabilidade

> **Versão 1.0 — Maio de 2026**

**ATENÇÃO: Leia atentamente este documento antes de utilizar o PesquisAI. O uso da ferramenta implica a aceitação integral dos termos aqui dispostos.**

---

## 1. Natureza da Ferramenta

O **PesquisAI** é um agente de inteligência artificial desenvolvido como ferramenta de apoio à pesquisa científica. Ele opera sobre **Modelos de Linguagem de Grande Porte (LLMs)** e integra-se a bases de dados públicos brasileiros por meio de módulos especializados (*skills*).

O PesquisAI é um **software experimental, de código aberto, fornecido "como está" (*as is*)**, sem garantias de qualquer natureza — expressas ou implícitas — quanto ao seu funcionamento ininterrupto, precisão dos resultados ou adequação a qualquer finalidade específica.

---

## 2. Validação Humana Obrigatória

### 2.1 Risco de Alucinação de IA

Modelos de Linguagem de Grande Porte (LLMs), incluindo aqueles que alimentam o PesquisAI, são suscetíveis ao fenômeno conhecido como **"alucinação"** — a geração de informações factualmente incorretas, dados inexistentes, referências fictícias ou afirmações plausíveis, porém falsas.

### 2.2 Dever do Usuário

**É responsabilidade exclusiva e intransferível do usuário:**

- Revisar criteriosamente **todos** os dados, análises, textos e referências gerados pela ferramenta;
- Validar cada informação factual contra suas fontes primárias originais;
- Verificar a existência e a correção de toda citação bibliográfica sugerida;
- Confirmar a acurácia de todos os dados estatísticos antes de utilizá-los em qualquer publicação, relatório, decisão acadêmica, profissional ou política;
- Avaliar criticamente a qualidade metodológica das análises propostas pela ferramenta.

> **O PesquisAI é um copiloto, não um piloto automático. O pesquisador humano é — e sempre será — o responsável último pela integridade do trabalho científico.**

---

## 3. Limitação de Responsabilidade

### 3.1 Dos Desenvolvedores

O desenvolvedor (Gustavo Bastos Braga) e a Universidade Federal de Viçosa (UFV) **não se responsabilizam** por:

| Item | Descrição |
|---|---|
| **Erros factuais** | Dados incorretos, incompletos ou desatualizados gerados pela ferramenta |
| **Decisões equivocadas** | Quaisquer decisões acadêmicas, profissionais, clínicas, políticas ou financeiras tomadas com base nos outputs do PesquisAI |
| **Perdas e danos** | Danos diretos, indiretos, incidentais, especiais ou consequenciais decorrentes do uso ou da impossibilidade de uso da ferramenta |
| **Violação de direitos** | Eventual reprodução não intencional de material protegido por direitos autorais nos outputs gerados |
| **Indisponibilidade** | Interrupções no serviço causadas por falhas nas APIs de terceiros (Google Colab, IBGE, DataSUS, provedores de LLM), manutenção de servidores ou outros fatores técnicos |

### 3.2 Dos Provedores Terceiros

O PesquisAI depende de serviços de terceiros sobre os quais o desenvolvedor **não possui controle**:

- **Google Colaboratory** — ambiente de execução
- **APIs do IBGE e DataSUS** — fontes de dados públicos
- **Provedores de LLM** — motor de inteligência artificial
- **GitHub** — hospedagem do código-fonte

Interrupções, alterações de política ou descontinuação de qualquer desses serviços podem afetar o funcionamento do PesquisAI sem aviso prévio.

---

## 4. Uso Acadêmico e Publicações

### 4.1 Transparência Obrigatória

Trabalhos acadêmicos que utilizarem o PesquisAI em qualquer etapa da pesquisa (coleta de dados, análise, redação, formatação) **devem declarar explicitamente** o uso da ferramenta, conforme orientações do Committee on Publication Ethics (COPE), da CAPES e de periódicos científicos.

> Consulte o documento **"Declaração de Uso de IA"** disponível na pasta `PesquisAI` para modelos prontos de declaração.

### 4.2 Autoria

O PesquisAI **não pode** ser listado como autor ou coautor de trabalhos acadêmicos, por não atender aos critérios de autoria do International Committee of Medical Journal Editors (ICMJE):

- Não pode assumir responsabilidade pelo conteúdo publicado;
- Não pode aprovar a versão final do manuscrito;
- Não pode responder por aspectos de integridade e precisão do trabalho.

---

## 5. Conformidade com a LGPD (Lei nº 13.709/2018)

O PesquisAI foi projetado seguindo os princípios de ***Privacy by Design***:

| Princípio da LGPD | Como o PesquisAI aplica |
|---|---|
| **Segurança** | O app não armazena dados do usuário em servidores próprios. Todo processamento ocorre na sessão local do Google Colab. |
| **Retenção** | Os arquivos são salvos exclusivamente na conta Google Drive do usuário. Nenhum dado é retido pelo desenvolvedor. |
| **Finalidade** | Os dados são acessados exclusivamente para cumprir a tarefa de pesquisa solicitada pelo usuário. |
| **Necessidade** | Apenas os dados estritamente necessários à pesquisa são processados. |
| **Transparência** | O usuário tem visibilidade total dos arquivos lidos e gravados na pasta `/PesquisAI/` do seu Drive. |

### 5.1 Recomendações de Proteção de Dados

- **Não submeta dados pessoais sensíveis** (registros médicos, dados bancários, documentos de identificação) a menos que estejam previamente anonimizados;
- **Não compartilhe** o acesso à sua pasta `/PesquisAI/` com terceiros não autorizados;
- **Revise** os arquivos gerados antes de compartilhá-los, removendo eventuais informações sensíveis que possam ter sido incluídas inadvertidamente.

---

## 6. Direitos Autorais e Licenciamento

### 6.1 Código-Fonte

O código do PesquisAI é distribuído sob a **Licença MIT**, que permite uso, cópia, modificação, fusão, publicação, distribuição, sublicenciamento e venda do software, desde que o aviso de copyright e a declaração de permissão sejam incluídos em todas as cópias ou partes substanciais do software.

### 6.2 Conteúdo Gerado

O conteúdo gerado pelo PesquisAI (textos, análises, gráficos) pertence ao usuário que o gerou, ressalvadas as seguintes condições:

- O usuário é responsável por verificar a originalidade do conteúdo e a ausência de plágio;
- Dados extraídos de fontes públicas (IBGE, DataSUS) devem ser atribuídos às suas respectivas fontes conforme as políticas de citação de cada instituição;
- O uso de conteúdo gerado por IA em publicações deve seguir as políticas do periódico ou instituição de destino.

---

## 7. Ambiente de Execução e Armazenamento

### 7.1 Google Colaboratory

O PesquisAI é executado no ambiente do **Google Colaboratory**, e está sujeito aos Termos de Serviço e Políticas de Privacidade do Google. Consulte:

- [Termos de Serviço do Google Colab](https://research.google.com/colaboratory/terms.html)
- [Política de Privacidade do Google](https://policies.google.com/privacy)

### 7.2 Sessões Efêmeras

As sessões do Google Colab são temporárias (tipicamente expiram após ~30 minutos de inatividade). O PesquisAI oferece mecanismo de **backup** para preservar o contexto da sessão, mas **não garante** que nenhuma informação seja perdida entre sessões.

---

## 8. Usos Não Permitidos

É expressamente vedado o uso do PesquisAI para:

- Gerar, distribuir ou facilitar conteúdo ilegal, difamatório, fraudulento ou que viole direitos de terceiros;
- Disseminar desinformação científica deliberada;
- Burlar sistemas de verificação de originalidade ou integridade acadêmica;
- Substituir, sem a devida declaração, o trabalho intelectual que deveria ser realizado pelo pesquisador;
- Qualquer finalidade que viole a legislação brasileira ou internacional aplicável.

---

## 9. Atualizações e Modificações

O desenvolvedor reserva-se o direito de modificar este Disclaimer a qualquer momento. As alterações entrarão em vigor imediatamente após a publicação da versão atualizada no repositório oficial. Recomenda-se que o usuário revise periodicamente os termos.

---

## 10. Aceitação dos Termos

Ao utilizar o PesquisAI, você declara que:

- [x] Leu e compreendeu integralmente este Disclaimer;
- [x] Tem ciência dos riscos inerentes ao uso de inteligência artificial generativa;
- [x] Assume total responsabilidade pela validação dos resultados gerados;
- [x] Compromete-se a declarar o uso da ferramenta em publicações acadêmicas;
- [x] Isenta o desenvolvedor e a UFV de responsabilidade por quaisquer consequências decorrentes do uso da ferramenta.

---

> *O PesquisAI é oferecido de boa-fé, com o propósito de impulsionar a pesquisa científica brasileira. Use com responsabilidade, senso crítico e integridade acadêmica.*

---

**Desenvolvido por Gustavo Bastos Braga**  
Universidade Federal de Viçosa (UFV)  
Contato: gustavo.braga@ufv.br  
Repositório: https://github.com/gustavobraga-byte/PesquisAI

---

*PesquisAI · v1.0 · Licenciado sob MIT · Documento atualizado em Maio de 2026*