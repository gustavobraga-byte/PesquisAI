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
| `pesquisai_0.5.1.9_amd64.deb` | 0.5.1.10 | ~865 KB | Pacote DEB para sistemas Debian/Ubuntu amd64 |

---

## 🐧 Instalação no Linux (Debian/Ubuntu)

### Método 1: Instalação via Terminal em Comando Único (Recomendado)

O comando abaixo baixa o arquivo `.deb` temporariamente, instala usando o `apt` (que já resolve dependências automaticamente) e remove o instalador ao terminar:

```bash
wget https://github.com/gustavobraga-byte/PesquisAI/raw/main/debs/pesquisai_0.5.1.9.deb -O /tmp/pesquisai.deb && \
sudo apt install /tmp/pesquisai.deb -y && \
rm /tmp/pesquisai.deb

```

Alternativamente, usando `curl`:

```bash
curl -L https://github.com/gustavobraga-byte/PesquisAI/raw/main/debs/pesquisai_0.5.1.9.deb -o /tmp/pesquisai.deb && \
sudo apt install /tmp/pesquisai.deb -y && \
rm /tmp/pesquisai.deb

```

---

### Método 2: Instalação Manual via `apt`

O uso do `apt` para instalar pacotes locais `.deb` é o padrão moderno no Linux, pois ele resolve todas as dependências do sistema em um único passo.

```bash
# 1. Baixe o pacote direto do repositório
wget https://github.com/gustavobraga-byte/PesquisAI/raw/main/debs/pesquisai_0.5.1.9.deb

# 2. Instale o pacote local
sudo apt install ./pesquisai_0.5.1.9.deb -y

# 3. Execute o PesquisAI
pesquisai

```

---

### Método 3: Instalação Clássica via `dpkg`

Caso precise usar obrigatoriamente o `dpkg`:

```bash
# 1. Baixe o pacote
wget https://github.com/gustavobraga-byte/PesquisAI/raw/main/debs/pesquisai_0.5.1.9.deb

# 2. Instale o pacote
sudo dpkg -i pesquisai_0.5.1.9.deb

# 3. Corrija possíveis dependências ausentes
sudo apt-get install -f -y

# 4. Execute
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
wget -qO /tmp/pesquisai.deb https://github.com/gustavobraga-byte/PesquisAI/debs/pesquisai_0.5.1.9_amd64.deb && \
  sudo dpkg -i /tmp/pesquisai.deb && \
  sudo apt-get install -f -y && \
  rm /tmp/pesquisai.deb
```

---

## 🛠️ Requisitos do Sistema

### Linux

- **Sistema Operacional:** Debian 10+, Ubuntu 18.04+, ou derivados
- **Arquitetura:** amd64 (x86_64)
- **Memória RAM:** Mínimo 4 GB (recomendado 8 GB+) (Para uso com llm na núvem, para llm locais necessário GPU)
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

# Ou iniciar com interface gráfica 
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

Para utilizar o **PesquisAI** em ambientes **completamente offline** (sem acesso à internet), é obrigatório configurar um **LLM (Large Language Model) local**. O PesquisAI é um agente inteligente construído sobre o **opencode** – portanto, todas as configurações abaixo se aplicam tanto ao PesquisAI quanto a qualquer outra ferramenta baseada no opencode.

### Requisitos para LLM Local

- **Hardware adequado:**  
  - Mínimo recomendado: 32 GB de RAM e, se possível, uma GPU com suporte a CUDA (acelera significativamente a inferência).  
  - Para modelos com janela de 256k tokens, o consumo de memória pode ser elevado – considere pelo menos 32 GB de RAM e, para modelos maiores, 48 GB de VRAM.

- **Armazenamento:**  
  - Espaço livre variando de 4 GB a 30+ GB, dependendo do modelo escolhido.

- **Ollama:**  
  - Ferramenta indispensável para executar modelos de linguagem localmente. Ela gerencia o download, o cache e a execução dos modelos.

### Instalando o Ollama

```bash
# No Linux (Ubuntu/Debian)
curl -fsSL https://ollama.com/install.sh | sh

# Inicie o serviço do Ollama
sudo systemctl start ollama
sudo systemctl enable ollama
```


---

### 📦 Modelos Recomendados para Janela de 256k

O PesquisAI exige uma janela de contexto de **256 mil tokens** para processar grandes volumes de informação. Abaixo estão os três modelos mais recomendados para essa finalidade, todos com suporte nativo ou testado para essa capacidade:

| Modelo | Parâmetros | Contexto | Comando para baixar via Ollama |
|--------|------------|----------|--------------------------------|
| **Kimi K2.6** (Moonshot AI) | – | 256k nativo | `ollama pull kimi/kimi2.6` |
| **Mistral Small 3** (Mistral AI) | 24B | 256k nativo | `ollama pull mistral-small:24b` |
| **Qwen 2.5** (Alibaba) | 7B, 14B, 32B, 72B | 128k nativo (estendível para 256k com `num_ctx`) | `ollama pull qwen2.5:7b` |



**Qual escolher?**

- **Kimi K2.6:** Melhor opção para raciocínio profundo e processamento de documentos longos. Possui visão-linguagem integrada e é open-weight.
- **Mistral Small 3 (24B):** Excelente equilíbrio entre qualidade e consumo de VRAM (~14 GB em Q4). Ideal para quem precisa de alta performance com hardware razoável.
- **Qwen 2.5 (7B ou 32B):** A opção mais flexível. O modelo de 7B cabe em GPUs com 6 GB de VRAM (com quantização), enquanto o de 32B entrega qualidade superior, mas exige mais memória.

---

### Baixando os Modelos via Ollama

Escolha um dos modelos acima e faça o download:

```bash
# Opção 1: Kimi K2.6
ollama pull kimi/kimi2.6

# Opção 2: Mistral Small 3 (24B)
ollama pull mistral-small:24b

# Opção 3: Qwen 2.5 (7B - recomendado para hardware limitado)
ollama pull qwen2.5:7b

# Opção 4: Qwen 2.5 (32B - melhor qualidade)
ollama pull qwen2.5:32b
```

### Configurando o PesquisAI para usar o Modelo Local

Após ter o Ollama em execução e o modelo baixado, configure o PesquisAI para utilizá‑lo.

#### 1. Inicie o servidor Ollama (se ainda não estiver rodando)

```bash
ollama serve
```

#### 2. Configurar via Arquivo de Configuração (persistente)

Edite o arquivo de configuração do PesquisAI ( em  `~/.config/opencode/opencode.json`):

```json
{
  "$schema": "https://opencode.ai",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": {
        "baseURL": "http://localhost:11434/v1"
      },
      "models": {
        "mistral-small:24b": {
          "name": "mistral-small:24b",
          "contextWindow": 256000
        }
      }
    }
  }
}
```


> **Atenção:** O parâmetro `contextWindow` define quantos tokens o modelo pode processar por requisição. O PesquisAI respeitará esse limite ao enviar prompts.

### Testando a Configuração

Verifique se o Ollama está respondendo e se o modelo suporta o contexto desejado:

```bash
# Listar modelos disponíveis
curl http://localhost:11434/api/tags

# Testar geração com contexto estendido (exemplo com Qwen 2.5)
curl http://localhost:11434/api/generate -d '{
  "model": "qwen2.5:7b",
  "prompt": "Explique o conceito de contexto em LLMs.",
  "options": {
    "num_ctx": 256000
  },
  "stream": false
}'
```

Se a resposta for bem‑sucedida, o PesquisAI estará pronto para operar offline.

### Dicas para um bom desempenho com 256k

- **Kimi K2.6:** Ótimo para tarefas que exigem interpretação de longos documentos e multimídia, mas verifique a disponibilidade do modelo no Ollama (caso não esteja, utilize via Hugging Face + llama.cpp).
- **Mistral Small 3:** Oferece a melhor relação qualidade/VRAM. Com quantização Q4, roda em GPUs com ~14 GB.
- **Qwen 2.5 (7B):** A opção mais acessível – com quantização Q4, cabe em GPUs com 6 GB de VRAM e ainda entrega resultados surpreendentes para 256k.
- **Memória:** Para 256k, o uso de VRAM pode ultrapassar 8 GB – monitore com `nvidia-smi` (Linux) ou `task manager` (Windows).
- **Tempo de inferência:** Contextos longos tornam a geração mais lenta. Considere usar `num_predict` limitado (ex.: 4096 tokens de saída) para evitar tempos excessivos.
- **Alternativa para hardware limitado:** Se você não tiver GPU, utilize a versão CPU dos modelos (será mais lenta, mas funcional) ou opte pelo Qwen 2.5 7B, que é o mais leve entre os recomendados.

---

Agora você tem um guia completo para rodar o PesquisAI (e, por extensão, qualquer agente baseado em opencode) **totalmente offline**, utilizando os modelos mais modernos e com suporte garantido à janela de 256k tokens. 🚀
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
científica. Versão Offline 0.5.1.9 (Linux). Viçosa: Universidade Federal de Viçosa, 2026.

Projeto registrado no SisPPG/UFV sob nº 10356285004.
Disponível em: https://github.com/gustavobraga-byte/PesquisAI/
```

**BibTeX:**
```bibtex
@software{braga2026pesquisai_offline,
  author = {Gustavo Bastos Braga},
  title = {{PesquisAI}: Versão Offline — Agente de Inteligência Artificial para Pesquisa Científica},
  year = {2026},
  version = {0.5.1.9},
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
