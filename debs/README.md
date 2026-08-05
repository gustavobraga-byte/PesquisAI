# 🔬 PesquisAI - Versão Offline

> **Versão:** 0.5.1.10 (Linux)
> **Data:** 2026
> **Status:** ✅ Versão Offline Estável
> **Licença:** MIT
> **Autor:** Gustavo Bastos Braga (UFV)
> **SisPPG/UFV:** 10356285004

## 📢 Visão Geral

A **versão offline do PesquisAI** permite executar o agente de pesquisa científica diretamente em sua máquina local, sem depender do Google Colab ou de conexão com internet para funcionamento básico. Esta versão é ideal para ambientes com restrições de conectividade ou para usuários que preferem processar dados localmente.

### 🚨 Requisitos Críticos para Offline Total

Para utilizar o PesquisAI em **ambiente completamente offline**, você precisará:

1. **Liberar portas no firewall:** As portas **8000** e **8001** são obrigatórias
2. **Configurar um LLM local (Ollama):** Necessário para processamento offline sem APIs externas

### Principais Características

- ✅ Funcionamento totalmente offline após instalação (com LLM local)
- ✅ Acesso direto às APIs do IBGE, DataSUS e outras fontes brasileiras
- ✅ Todos os recursos do PesquisAI em um único pacote
- ✅ Integração com memória persistente (vault Obsidian)
- ✅ Servidor web integrado para interface visual
- ✅ Interface responsiva com suporte a temas
- ✅ Suporte a LLMs locais via Ollama

> **Nota:** A versão offline deste README é exclusivamente para sistemas Linux (Debian/Ubuntu).

---

## 📦 Pacote Disponível

A versão offline está disponível no seguinte formato:

### Linux (.deb)

| Arquivo | Versão | Tamanho | Descrição |
|---------|--------|---------|-----------|
| `pesquisai_0.5.1.10-1_amd64.deb` | 0.5.1.10 | ~865 KB | Pacote DEB para sistemas Debian/Ubuntu amd64 |

---

## 🐧 Instalação no Linux (Debian/Ubuntu)

### Método 1: Instalação via Terminal (Recomendado)

Você pode instalar o PesquisAI diretamente do GitHub com um único comando:

```bash
# Instale o PesquisAI baixando e instalando diretamente do GitHub
wget -qO - https://github.com/gustavobraga-byte/PesquisAI/releases/latest/download/pesquisai_0.5.1.10-1_amd64.deb | \
  sudo dpkg -i - && \
  sudo apt-get install -f -y
```

Alternativamente, você também pode usar o `curl`:

```bash
# Usando curl
curl -L https://github.com/gustavobraga-byte/PesquisAI/releases/latest/download/pesquisai_0.5.1.10-1_amd64.deb | \
  sudo dpkg -i - && \
  sudo apt-get install -f -y
```

### Método 2: Via dpkg (Download Manual)

```bash
# Baixe o pacote diretamente do GitHub Releases
wget https://github.com/gustavobraga-byte/PesquisAI/releases/latest/download/pesquisai_0.5.1.10-1_amd64.deb

# Instale o pacote
sudo dpkg -i pesquisai_0.5.1.10-1_amd64.deb

# Resolva dependências (se houver)
sudo apt-get install -f

# Execute o PesquisAI
pesquisai
```

### Método 3: Via apt (Instalação Manual)

```bash
# Baixe o pacote
wget https://github.com/gustavobraga-byte/PesquisAI/releases/latest/download/pesquisai_0.5.1.10-1_amd64.deb

# Instale o pacote
sudo apt install ./pesquisai_0.5.1.10-1_amd64.deb

# Execute
pesquisai
```

### Verificando a Instalação

```bash
# Verifique a versão instalada
pesquisai --version

# Listar arquivos instalados
dpkg -L pesquisai

# Verificar status do serviço (se aplicável)
systemctl status pesquisai
```

### Atualização via Terminal

```bash
# Atualize o PesquisAI baixando a última versão
wget -qO /tmp/pesquisai.deb https://github.com/gustavobraga-byte/PesquisAI/releases/latest/download/pesquisai_0.5.1.10-1_amd64.deb && \
  sudo dpkg -i /tmp/pesquisai.deb && \
  sudo apt-get install -f -y && \
  rm /tmp/pesquisai.deb
```

---

## 🛠️ Requisitos do Sistema

### Linux

- **Sistema Operacional:** Debian 10+, Ubuntu 18.04+, ou derivados
- **Arquitetura:** amd64 (x86_64)
- **Memória RAM:** Mínimo 4 GB (recomendado 8 GB+)
- **Armazenamento:** Mínimo 500 MB de espaço livre
- **Python:** 3.10+ (instalado automaticamente como dependência)
- **Portas de Rede:** As portas **8000** e **8001** devem estar liberadas no firewall

---

## 📂 Estrutura de Diretórios

Após a instalação, os arquivos do PesquisAI serão organizados da seguinte forma:

```
/usr/bin/pesquisai                     # Executável principal
/opt/pesquisai/                        # Diretório de instalação
├── bin/                               # Arquivos binários
├── lib/                               # Bibliotecas e dependências
├── share/pesquisai/                   # Arquivos compartilhados
│   ├── skills/                        # Skills integradas
│   ├── templates/                     # Templates de documentos
│   └── assets/                        # Recursos estáticos
/var/lib/pesquisai/                    # Dados do usuário (configurações)
└── vault/                             # Memória persistente (Obsidian)
/var/log/pesquisai/                    # Logs do sistema
```

---

## 🚀 Primeiros Passos

### Iniciando o PesquisAI

```bash
# Iniciar via terminal
pesquisai

# Ou iniciar com interface gráfica (se disponível)
pesquisai --gui

# Executar como serviço (opcional)
sudo systemctl start pesquisai
```

### Primeira Configuração

1. **Liberação de Portas:**
   
   O PesquisAI requer que as **portas 8000 e 8001** estejam liberadas no firewall:
   
   ```bash
   # Em sistemas com ufw:
   sudo ufw allow 8000/tcp
   sudo ufw allow 8001/tcp
   
   # Verifique se as portas estão abertas:
   sudo netstat -tlnp | grep -E '8000|8001'
   # ou
   sudo ss -tlnp | grep -E '8000|8001'
   ```

2. **Configuração de APIs (Opcional):**
   - Para acesso a bases de dados premium, configure as chaves de API
   - Acesse `Configurações → Provedores de IA` na interface

3. **Configuração do Vault:**
   - O sistema criará automaticamente uma pasta `vault/` para memória persistente
   - O vault será criado em `/var/lib/pesquisai/vault/`

4. **Configuração de Diretórios:**
   - Os arquivos gerados serão salvos no diretório configurado
   - Ajuste as preferências em `Configurações → Diretórios`

### Acessando a Interface

Após iniciar o PesquisAI, acesse a interface web através do navegador:

- **Interface Web:** http://localhost:8000
- **TTYD Terminal:** http://localhost:8001

---

## 🧠 Recursos Principais

### Skills Integradas

| Skill | Funcionalidade |
|-------|----------------|
| `ibge-br` | Acesso aos dados do IBGE (Censo, PNAD, PIB) |
| `opendatasus` | Dados de saúde pública (SINAN, SUS, mortalidade) |
| `dados-brasil` | Indicadores oficiais brasileiros |
| `agrobr` | Dados do agronegócio e CAR |
| `qualitativa` | Análise qualitativa e de conteúdo |
| `UFV-ABNT` | Formatação conforme normas UFV/ABNT |
| `citation-management` | Gerenciamento de referências bibliográficas |

### Memória Persistente

A versão offline inclui suporte completo ao sistema de memória persistente do PesquisAI:

- 📝 **Daily Notes:** Registro diário de atividades
- 📚 **Literature Notes:** Organização de revisões bibliográficas
- 🎯 **Hipóteses:** Gestão de hipóteses de pesquisa
- 🔗 **Backlinks e Wikilinks:** Conexões entre notas
- 🔍 **Busca BM25:** Busca eficiente no conteúdo
- 🗺️ **MOCs (Maps of Content):** Índices organizacionais

---

## 🔧 Solução de Problemas

### Problemas Comuns no Linux

#### 1. Erro de permissões

```bash
# Certifique-se de ter permissões de administrador
sudo pesquisai
```

#### 2. Portas bloqueadas (8000/8001)

```bash
# Verifique se as portas estão em uso
sudo lsof -i :8000
sudo lsof -i :8001

# Libere as portas no firewall
sudo ufw allow 8000/tcp
sudo ufw allow 8001/tcp
```

#### 3. Dependências faltando

```bash
# Corrija dependências automaticamente
sudo apt-get install -f
```

#### 4. Erro de bibliotecas compartilhadas

```bash
# Atualize o cache de bibliotecas
sudo ldconfig
```

#### 5. Erro de inicialização do servidor web

```bash
# Verifique os logs
tail -f /var/log/pesquisai/error.log

# Reinicie o serviço
sudo systemctl restart pesquisai
```

### Arquivo de Log de Erros

Em caso de problemas, consulte os logs:

- **Logs principais:** `/var/log/pesquisai/error.log`
- **Logs de aplicação:** `/var/lib/pesquisai/logs/`

---

## 🔒 Configurações de Rede

### Portas Necessárias

| Porta | Serviço | Descrição |
|-------|---------|-----------|
| 8000 | Interface Web | Acesso à interface gráfica do PesquisAI |
| 8001 | TTYD Terminal | Terminal integrado para comunicação com o agente |

#### Verificando portas liberadas

```bash
# Verifique se as portas estão abertas
sudo netstat -tlnp | grep -E '8000|8001'

# Ou use ss
sudo ss -tlnp | grep -E '8000|8001'
```

#### Configurando firewall

```bash
# Para sistemas com ufw
sudo ufw allow 8000/tcp
sudo ufw allow 8001/tcp

# Para sistemas com firewalld
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=8001/tcp
sudo firewall-cmd --reload
```

---

## 🤖 Funcionamento Totalmente Offline com LLM Local

Para utilizar o PesquisAI em ambientes **completamente offline** (sem acesso à internet), é necessário configurar um **LLM (Large Language Model) local**. Isso permite que o agente funcione sem depender de APIs externas como OpenAI, Anthropic ou Google.

### Requisitos para LLM Local

- **Hardware adequado:** Recomendado mínimo 16 GB de RAM e GPU compatível com CUDA (não obrigatório, mas acelera significativamente)
- **Armazenamento:** Espaço suficiente para armazenar os modelos (varia de 4 GB a 30+ GB dependendo do modelo)
- **Ollama:** Ferramenta para execução de modelos de linguagem localmente

### Instalando o Ollama

```bash
# No Linux (Ubuntu/Debian)
curl -fsSL https://ollama.com/install.sh | sh

# Inicie o serviço do Ollama
sudo systemctl start ollama
sudo systemctl enable ollama
```

### Modelos Recomendados

| Modelo | Tamanho | RAM Mínima | Qualidade | Uso Recomendado |
|--------|---------|------------|-----------|-----------------|
| `llama3:8b` | ~5 GB | 8 GB | Boa | Consultas rápidas |
| `llama3.1:70b` | ~40 GB | 32 GB | Excelente | Análise complexa |
| `phi3:mini` | ~2 GB | 4 GB | Regular | Ambientes restritos |
| `gemma2:9b` | ~6 GB | 8 GB | Boa | Balanceado |

### Baixando um Modelo via Ollama

```bash
# Exemplo: baixar o Llama 3 8B
ollama pull llama3:8b

# Exemplo: baixar o Gemma 2 9B
ollama pull gemma2:9b

# Exemplo: baixar o Phi-3 mini (muito pequeno)
ollama pull phi3:mini
```

### Configurando o PesquisAI para usar LLM Local

Para configurar o PesquisAI para usar um LLM local via Ollama, siga estes passos:

1. **Inicie o servidor Ollama:**
   ```bash
   ollama serve
   ```

2. **Configurar o PesquisAI via Interface:**
   - Acesse `Configurações → Provedores de IA`
   - Selecione "Ollama (Local)" na lista de provedores
   - Insira o nome do modelo (ex: `llama3:8b`)
   - Salve a configuração

3. **Configurar via Linha de Comando:**
   ```bash
   # Configure a variável de ambiente
   export OLLAMA_BASE_URL="http://localhost:11434"
   export OLLAMA_MODEL="llama3:8b"
   
   # Inicie o PesquisAI
   pesquisai --provider ollama --model llama3:8b
   ```

4. **Testar a Configuração:**
   ```bash
   # Verifique se o Ollama está rodando
   curl http://localhost:11434/api/tags
   
   # Teste o modelo
   curl http://localhost:11434/api/generate -d '{
     "model": "llama3:8b",
     "prompt": "Qual é a capital do Brasil?",
     "stream": false
   }'
   ```

### Configuração Avançada via Arquivo

Você também pode configurar o LLM local editando o arquivo de configuração:

```bash
# Local do arquivo de configuração
/etc/pesquisai/config.json
```

Conteúdo do arquivo de configuração:
```json
{
  "provider": "ollama",
  "ollama": {
    "base_url": "http://localhost:11434",
    "model": "llama3:8b",
    "temperature": 0.7,
    "max_tokens": 4096
  },
  "offline_mode": true
}
```

### Portas Adicionais para LLM Local

Além das portas 8000 e 8001, se estiver utilizando um LLM local via Ollama, você precisará liberar a porta:

| Porta | Serviço | Descrição |
|-------|---------|-----------|
| 8000 | Interface Web | Acesso à interface gráfica do PesquisAI |
| 8001 | TTYD Terminal | Terminal integrado para comunicação com o agente |
| 11434 | Ollama API | API local para comunicação com modelos de linguagem |

```bash
# Libere todas as portas necessárias
sudo ufw allow 8000/tcp
sudo ufw allow 8001/tcp
sudo ufw allow 11434/tcp
```

---

## 📚 Documentação Adicional

Para informações detalhadas sobre funcionalidades, consulte:

- **[`MANUAL.md`](../../MANUAL.md)** - Manual completo do PesquisAI
- **[`CHANGELOG.md`](../../CHANGELOG.md)** - Histórico de alterações
- **[`INTEGRITY.md`](../../docs/INTEGRITY.md)** - Princípios de integridade científica

---

## ⚠️ Limitações Importantes

- **Coleta primária:** O PesquisAI NÃO realiza coleta primária (entrevistas, experimentos, surveys)
- **Dados inventados:** NUNCA inventa dados ou estatísticas
- **Validação:** Toda fonte deve ser validada via `citation-management`
- **Dados sensíveis:** Não processe dados pessoais sem anonimização

---

## 📄 Citação

Se você utilizar o PesquisAI em seu trabalho, por favor cite:

```
BRAGA, Gustavo Bastos. PesquisAI: agente de inteligência artificial para pesquisa
científica. Versão Offline 0.5.1.10 (Linux). Viçosa: Universidade Federal de Viçosa, 2026.

Projeto registrado no SisPPG/UFV sob nº 10356285004.
Disponível em: https://github.com/gustavobraga-byte/PesquisAI/
```

**BibTeX:**
```bibtex
@software{braga2026pesquisai_offline,
  author = {Gustavo Bastos Braga},
  title = {{PesquisAI}: Versão Offline — Agente de Inteligência Artificial para Pesquisa Científica},
  year = {2026},
  version = {0.5.1.10},
  institution = {Universidade Federal de Viçosa (UFV)},
  url = {https://github.com/gustavobraga-byte/PesquisAI},
  note = {SisPPG/UFV nº 10356285004}
}
```

---

## 🆘 Suporte e Contato

- **Repositório GitHub:** https://github.com/gustavobraga-byte/PesquisAI
- **Issues:** https://github.com/gustavobraga-byte/PesquisAI/issues
- **E-mail:** gustavo.braga@ufv.br
- **Instituição:** Universidade Federal de Viçosa (UFV)

---

## 📜 Licença

Este software é distribuído sob a **Licença MIT**.

```
MIT License

Copyright (c) 2026 Gustavo Bastos Braga

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

> **⚠️ Aviso de Responsabilidade:** O PesquisAI é um agente de IA experimental. Embora inclua verificações de integridade científica, **sempre valide os resultados independentemente**. O PesquisAI não se substitui ao pesquisador, apenas o amplia. Consulte o [`DISCLAIMER.md`](../DISCLAIMER.md) completo.
