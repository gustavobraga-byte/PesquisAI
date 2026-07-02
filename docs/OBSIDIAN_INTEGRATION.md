# 🧠 Integração PesquisAI ↔ Obsidian — Guia Completo

> **Versão:** 0.5.0
> **Status:** Documentação oficial
> **Audiência:** pesquisadores, desenvolvedores, contribuidores

Este guia mostra como instalar, configurar e usar a integração
PesquisAI ↔ Obsidian como "segundo cérebro" do agente.

---

## 0. REGRA DE OURO: 100% no Google Drive do usuário

> **TUDO** — o vault do Obsidian, os backups, o log de auditoria,
> os exemplos e os arquivos gerados — **deve permanecer no Google
> Drive do usuário**. **Nenhum byte** deve ser escrito em
> `/content/` (efêmero no Colab) ou em `/tmp/` (perdido ao fim da
> sessão do Colab).

### Por quê?

O Colab é um ambiente **efêmero**:

- `/content/` é recriado a cada nova sessão
- `/tmp/` é perdido quando a sessão termina (≈ 90 min de inatividade)
- O Google Drive é **montado** em `/content/drive/My Drive/` (FUSE)
- O Drive é **persistente**, **versionado** (histórico de versões
  integrado) e **compartilhável** (compartilhe com colaboradores)

### Como o PesquisAI garante isso

A função `discovery.get_default_vault_path()` valida que o caminho
está dentro do Google Drive:

```python
DRIVE_PATH_PREFIXES = (
    "/content/drive/",                 # Colab FUSE mount (padrão)
    "/content/drive/.colab/",          # Colab alternate
    "/Volumes/GoogleDrive/",           # macOS
    "/mnt/gdrive/",                    # Linux
    "/mnt/google-drive/",              # Linux GNOME
    "G:/Meu Drive/",                   # Windows (PT)
    "G:/My Drive/",                    # Windows (EN)
)
```

Se o caminho configurado **não** está no Drive, e estamos no Colab,
o módulo **se recusa a operar** (retorna `None` da detecção, fazendo
o PesquisAI funcionar sem memória em vez de gravar em lugar inseguro).

### Caminho padrão sugerido

```
/content/drive/My Drive/PesquisAI/vault/
```

Este é o caminho criado automaticamente por `init_vault.sh` e
detectado automaticamente por `get_default_vault_path()`.

### O que NUNCA fazer

| ❌ Não fazer | ✅ Fazer |
|---|---|
| Salvar vault em `/content/pesquisai-vault/` | Salvar em `/content/drive/My Drive/PesquisAI/vault/` |
| Salvar vault em `/tmp/vault/` | Salvar no Drive |
| Salvar backups em `/content/backups/` | Salvar em `<vault>/.backups/` (que está no Drive) |
| Usar vault em outro Cloud (Dropbox) | Usar o Google Drive do usuário |
| Compartilhar vault via link efêmero | Compartilhar a pasta do Drive |

### Validação automática

Toda inicialização do PesquisAI executa (silenciosamente):

```python
if not is_available():  # discovery.is_available()
    # Módulo desativado — PesquisAI funciona sem memória
    logger.info("Vault não encontrado no Drive — módulo desativado")
else:
    # Vault OK — agente lê e grava
    ...
```

### Se o usuário não está no Colab

- O PesquisAI **aceita** caminhos fora do Drive (uso local)
- Recomendado: `~/Obsidian/PesquisAI/` (convenção desktop)
- O vault ainda é versionado via git ou Remotely Save

---

## 1. Visão geral

A integração resolve a maior limitação declarada no `AGENTS.md`:

> *"Sem memória entre sessões: o contexto é reiniciado a cada conversa."*

Com ela, o PesquisAI passa a ter:

- **Memória persistente** entre sessões (notas no vault)
- **Continuidade de projetos** (acompanhamento de TCCs, artigos)
- **Busca textual offline** (BM25 local, sem API paga)
- **Backlinks e wikilinks** (grafo de conhecimento nativo do Obsidian)
- **Tags padronizadas** (`pesquisai/*`)
- **Templates versionados** (10 templates oficiais)
- **MOCs (Maps of Content)** auto-montados
- **Sincronização** com Google Drive / git / dispositivos móveis

A integração **NÃO** introduz regressões em:

- Política de zero-fabricação
- Verificação obrigatória de citações
- Não simulação de coleta primária
- Dados nacionais (IBGE/DataSUS) com prioridade
- Marcadores de evidência

---

## 2. Instalação passo a passo

### 2.1. No Colab (uso padrão)

```python
# 1. Defina a variável de ambiente ANTES de importar o PesquisAI
import os
os.environ["PESQUISAI_OBSIDIAN_VAULT"] = (
    "/content/drive/My Drive/PesquisAI/vault"
)

# 2. Crie a estrutura do vault (uma única vez)
!bash /content/drive/My\ Drive/PesquisAI/obsidian-integration/scripts/init_vault.sh

# 3. Importe o PesquisAI normalmente
from main import run
run()
```

### 2.2. Em instalação local (CLI / Docker)

```bash
# 1. Clone o repositório
git clone https://github.com/gustavobraga-byte/PesquisAI.git
cd PesquisAI

# 2. Defina a variável
export PESQUISAI_OBSIDIAN_VAULT="$HOME/Documents/PesquisAI/vault"

# 3. Crie a estrutura
./scripts/init_vault.sh

# 4. Instale as dependências
pip install -e ".[obsidian]"

# 5. Rode os testes (opcional)
pytest skills/obsidian-memory/tests/ -v

# 6. Inicie o PesquisAI
python main.py
```

---

## 3. Configuração do Obsidian (no desktop)

### 3.1. Criar/abrir o vault

1. Abra o Obsidian
2. **Create new vault** → aponte para a pasta criada pelo `init_vault.sh`
3. O Obsidian vai detectar a estrutura e mostrar a daily de hoje

### 3.2. Instalar plugins recomendados

Rode no terminal:

```bash
./scripts/install_plugin.sh
```

Ou instale manualmente:

- [Dataview](https://github.com/blacksmithgu/obsidian-dataview) — queries YAML
- [Templater](https://github.com/SilentVoid13/Templater) — templates com lógica
- [Remotely Save](https://github.com/remotely-save/remotely-save) — sync com Drive
- [Obsidian Git](https://github.com/denolehov/obsidian-git) — sync via git
- [Calendar](https://github.com/liamcain/obsidian-calendar-plugin) — daily visual
- [Tag Wrangler](https://github.com/pjeby/tag-wrangler) — gestão de tags
- [Mind Map](https://github.com/lynchjames/obsidian-mind-map-plugin) — grafo visual

### 3.3. Configurar sync

**Opção A — Remotely Save (recomendado para Colab):**

1. Settings → Community plugins → Remotely Save → Options
2. Service: **Google Drive**
3. Authorization: siga o wizard
4. Sync interval: 5 min

**Opção B — Obsidian Git (recomendado para dev):**

1. Settings → Community plugins → Obsidian Git → Options
2. Configure remote (GitHub, GitLab, Bitbucket…)
3. Auto-push interval: 10 min
4. Auto-pull interval: 5 min

---

## 4. Uso dentro do agente

A skill `obsidian-memory` ativa o segundo cérebro automaticamente
quando `PESQUISAI_OBSIDIAN_VAULT` está definida. O agente:

| Momento | O que o agente faz |
|---|---|
| Início da sessão | Carrega daily notes + MOC raiz no contexto |
| Durante a sessão | `mem.search(...)` para recall de notas |
| | `mem.create_note(...)` para rascunhos |
| | `mem.use_skill(...)` para tracking |
| Fim da sessão | `mem.end_session(...)` grava log |
| | `mem.sync_drive(...)` espelha para o mirror |

### 4.1. Uso programático

```python
from pesquisai.obsidian import (
    ObsidianMemory,
    ObsidianMemoryStatus,
    Note,
)

mem = ObsidianMemory.from_env()
print(f"Status: {mem.status.value}")  # ready | no_vault | disabled | ...

if mem.enabled:
    # 1. Carregar contexto
    for daily in mem.recent_daily_notes(limit=3):
        mem.add_to_context(daily)

    # 2. Iniciar sessão
    sid = mem.start_session()
    mem.log_request(user_input)
    mem.use_skill("ibge-br")

    # 3. Buscar informação prévia
    results = mem.search("diabetes", tags=["pesquisai/ibge"], limit=5)
    for r in results:
        print(f"{r.score:.2f} {r.note.path}: {r.snippet[:80]}…")

    # 4. Criar nota de pesquisa
    note = mem.create_note(
        "research/diabetes.md",
        title="Prevalência de Diabetes no Brasil",
        template="research",
        tags=("pesquisai/ibge", "pesquisai/datasus"),
        context={"research_question": "Qual a tendência 2010-2024?"},
    )

    # 5. Atualizar nota (anexando resultados)
    body = """
    ## 7. Resultados preliminares
    - Prevalência em 2023: 10,2% (VIGITEL)
    - Tendência: crescimento de 2,3 pp desde 2014
    [DADO CONFIRMADO]
    """
    mem.update_note(note, append=body)

    # 6. Encerrar sessão
    mem.end_session(
        summary="Levantamento inicial da prevalência de diabetes",
        tokens_in=4231,
        tokens_out=6872,
    )
```

### 4.2. Uso conversacional (sem código)

O usuário pode pedir em linguagem natural:

> *"Salve isso no meu vault como nota de revisão"*
> *"Qual minha última daily?"*
> *"Liste os papers que já revisei sobre diabetes"*
> *"Crie um MOC para o meu projeto do PNAE"*
> *"Sincronize o vault com o Drive"*

A skill reconhece essas intenções e chama os métodos apropriados.

---

## 5. Segurança e ética

### 5.1. Quem pode escrever?

| Autor da nota | Pode o agente ler? | Pode o agente escrever? |
|---|---|---|
| Humano (created_by vazio) | ✅ sim | ❌ não (read-only) |
| PesquisAI (created_by=pesquisai) | ✅ sim | ✅ sim |
| PesquisAI + edição humana | ✅ sim | ✅ sim (com cuidado) |

A regra é simples: **notas humanas são intocáveis**.

Para forçar sobrescrita, use `vault.write(note, force=True)` —
isso é logado em `.pesquisai-audit.log`.

### 5.2. Auditoria

Toda escrita é registrada em `<vault>/.pesquisai-audit.log`:

```
2026-06-29T15:30:22  write  research/diabetes.md
2026-06-29T15:30:25  update  sessions/2026-06-29-host-153022.md
2026-06-29T15:30:26  delete  research/old-note.md
```

### 5.3. Backup automático

- **Backups locais** são criados em `<vault>/.backups/<data>/` antes
  de operações destrutivas (`sync_git`, `delete`)
- **Backups no Drive** (mirror) ficam em uma pasta separada
- **Integração com git**: cada sync é um commit

### 5.4. Privacidade (LGPD)

- O vault é **local** (sua pasta) — o PesquisAI não envia nada para
  servidores externos além das APIs já documentadas
- Se você usar sync via Google Drive, os termos do Google se aplicam
- Para máxima privacidade, use git bare + repositório privado

---

## 6. Troubleshooting

| Problema | Solução |
|---|---|
| `VaultNotFoundError` | Rode `init_vault.sh` ou defina a variável |
| `PermissionError` em nota humana | Use `force=True` apenas se tiver certeza |
| Busca não retorna resultados | Rode `mem._searcher.rebuild()` para reindexar |
| Sincronização lenta | Use `git` em vez de `drive` para vaults grandes |
| Wikilink não resolve | Cheque a capitalização e acentos; use o `LinkIndex` |
| Daily note de hoje não existe | O PesquisAI cria automaticamente no início da sessão |
| Markdown quebra nos templates | Use o frontmatter gerado, não edite à mão |

---

## 7. Roadmap

- [ ] **v0.5.1** — RAG leve (BM25 + embeddings locais)
- [ ] **v0.5.2** — Plugin nativo do Obsidian ("PesquisAI Sync")
- [ ] **v0.5.3** — Comentários inline do agente nas notas humanas
- [ ] **v0.6.0** — Suporte a múltiplos vaults (1 por projeto)
- [ ] **v0.6.1** — Web clipper integrado (pesquisa → nota)
- [ ] **v0.7.0** — Versionamento semântico de notas (snapshot por tag)

---

## 8. Referências

- [Obsidian Help](https://help.obsidian.md/) — documentação oficial
- [Dataview](https://blacksmithgu.github.io/obsidian-dataview/) — query language
- [K-Dense open-notebook](https://github.com/K-Dense-AI/scientific-agent-skills) — referência conceitual
- [Andy Matuschak — Evergreen Notes](https://notes.andymatuschak.org/) — modelo de notas atômicas
- [Tiago Forte — Building a Second Brain](https://www.buildingasecondbrain.com/) — metodologia

---

*PesquisAI · integração Obsidian · v0.5.0 · 2026-06-29*  
*Compatível com PesquisAI ≥ v0.4.2.3*
