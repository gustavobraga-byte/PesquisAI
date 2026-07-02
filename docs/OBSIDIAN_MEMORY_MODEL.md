# 🧠 Modelo de Memória do PesquisAI — Camada Obsidian

> **Versão:** 0.5.0
> **Status:** Documentação arquitetural
> **Audiência:** desenvolvedores e contribuidores

Este documento descreve o **modelo de dados** e a **máquina de estados**
da camada de memória persistente do PesquisAI.

---

## 0. Política de persistência: 100% no Google Drive

> **REGRA ABSOLUTA:** todos os artefatos da camada de memória
> (vault, backups, audit log, exemplos, índice BM25 serializado)
> são armazenados **exclusivamente no Google Drive do usuário**.

| Artefato | Localização | Razão |
|---|---|---|
| Vault (notas `.md`) | `<DRIVE>/PesquisAI/vault/` | persistente, versionado |
| Audit log | `<DRIVE>/PesquisAI/vault/.pesquisai-audit.log` | rastreabilidade |
| Backups | `<DRIVE>/PesquisAI/vault/.backups/<data>/` | recuperação |
| Trash | `<DRIVE>/PesquisAI/vault/.trash/` | exclusão suave |
| Config `.obsidian/` | `<DRIVE>/PesquisAI/vault/.obsidian/` | config do app |
| MOC raiz | `<DRIVE>/PesquisAI/vault/moc/index.md` | ponto de entrada |
| Sessões (logs) | `<DRIVE>/PesquisAI/vault/sessions/` | histórico |
| Mirror (sync) | `<DRIVE>/PesquisAI/vault-mirror/` | espelho para git |

> **Nenhum arquivo** é gravado em `/content/` (efêmero) ou `/tmp/`
> (volátil). A função `discovery._validate_drive_path()` rejeita
> caminhos fora do Drive quando o ambiente é Colab.

A validação considera "no Drive" os seguintes prefixos:

```python
DRIVE_PATH_PREFIXES = (
    "/content/drive/", "/content/drive/.colab/",
    "/Volumes/GoogleDrive/", "/mnt/gdrive/", "/mnt/google-drive/",
    "G:/Meu Drive/", "G:/My Drive/",
)
```

---

## 1. Princípios de design

A camada de memória segue **4 princípios** que informam todas as
decisões técnicas:

### 1.1. Read-mostly, write-controlled

O agente **lê** o vault livremente. **Escrever** é uma operação
controlada, com três regras:

1. **Notas humanas são read-only** (`created_by` vazio ou ausente)
2. **Notas do agente** (`created_by: pesquisai`) podem ser editadas
3. **Forçar sobrescrita** requer `force=True` explícito (com log)

### 1.2. Append-only para logs

Sessões, mudanças de configuração e eventos significativos são
**anexados** a logs (`sessions/...md`, `.pesquisai-audit.log`),
nunca sobrescritos. Isso preserva rastreabilidade.

### 1.3. Single source of truth por campo

Cada campo da nota tem **um único lugar** de definição:

| Campo | Definido em | Editado por |
|---|---|---|
| `title` | `NoteMetadata` | criador + agente |
| `created` | `NoteMetadata` | criador (imutável) |
| `updated` | `NoteMetadata` | agente (auto) |
| `tags` | frontmatter | criador + agente |
| `created_by` | `NoteMetadata` | criador (imutável) |
| `status` | frontmatter | criador + agente |
| `body` | nota | criador + agente |
| `wikilinks` | derivado do body | auto |
| `tags` (extraídos) | derivado do body | auto |

### 1.4. Falha segura

Em caso de erro (vault indisponível, falta de permissão, pyyaml
ausente, …), o módulo **desativa** em vez de falhar. O PesquisAI
continua funcionando, mas sem memória.

---

## 2. Máquina de estados do `ObsidianMemory`

```
┌─────────────────┐
│   constructor   │
│   from_env()    │
└────────┬────────┘
         │
         ▼
   ┌────────────┐    PESQUISAI_OBSIDIAN_VAULT
   │  DISABLED  │◄──────────────────────── ausente
   └─────┬──────┘
         │  variável presente
         ▼
   ┌────────────┐    pasta não existe
   │  NO_VAULT  │◄──────────────
   └─────┬──────┘               │
         │ pasta existe         │
         ▼                      │
   ┌────────────┐  sem escrita  │
   │  READ_ONLY │◄──────┐       │
   └─────┬──────┘       │       │
         │ tem escrita  │       │
         ▼              │       │
   ┌────────────┐       │       │
   │   READY    │───────┴───────┘
   └─────┬──────┘
         │ erro inesperado
         ▼
   ┌────────────┐
   │   ERROR    │
   └────────────┘
```

Transições são **imutáveis** durante a vida de uma instância. Para
re-tentar, crie uma nova instância.

---

## 3. Ciclo de vida de uma sessão

```
   ┌──────────────────────────────────────────────┐
   │  Sessão N                                    │
   │                                              │
   │  1. start_session()                          │
   │     └─► _session = _SessionContext(...)      │
   │                                              │
   │  2. log_request(text) (N vezes)              │
   │     └─► _session.user_requests.append(...)  │
   │                                              │
   │  3. use_skill(id) (N vezes)                  │
   │     └─► _session.skills_used.append(...)     │
   │                                              │
   │  4. create_note(...) (opcional, M vezes)     │
   │     └─► _session.notes_created.append(...)   │
   │     └─► vault.write_from_template(...)       │
   │                                              │
   │  5. update_note(...) (opcional, K vezes)     │
   │     └─► _session.notes_updated.append(...)   │
   │     └─► vault.write(...)                    │
   │                                              │
   │  6. log_file(path) (opcional)                │
   │     └─► _session.files_generated.append(...)│
   │                                              │
   │  7. end_session(summary=...)                 │
   │     └─► vault.write(sessions/...md)         │
   │     └─► _session = None                     │
   │                                              │
   │  8. sync_drive() ou sync_git() (opcional)    │
   │     └─► _local_backup()                     │
   │     └─► rsync / git fetch / push             │
   └──────────────────────────────────────────────┘
```

A sessão é **atômica** em `end_session()`: ou o log inteiro é gravado
ou nada é gravado (escrita atômica com fsync, vide v0.2.3).

---

## 4. Modelo de dados (entidade-relacionamento)

```
┌────────────┐
│   Vault    │
│  (pasta)   │
└─────┬──────┘
      │ 1:N
      ▼
┌────────────┐         N:M
│   Note     │◄──────────┐
│  (.md)     │           │
│            │           │
│  + path    │           │
│  + body    │           │
│  + metadata├──►LinkIndex
│  + wikilinks│         │
│  + tags    │         │
└────────────┘         │
                       │
        ┌──────────────┘
        │
        ▼
┌────────────┐         N:M
│  Searcher  │◄──────────┐
│            │           │
│  + _bm25   │           │
│  + _notes  │           │
│  + _tags   ├──►TagIndex
└────────────┘         │
                       │
                       ▼
              ┌────────────────┐
              │ ObsidianMemory │
              │   (fachada)    │
              │                │
              │  + status      │
              │  + _vault      │
              │  + _searcher   │
              │  + _links      │
              │  + _session    │
              │  + _context    │
              └────────────────┘
```

Cardinalidades:

- `Vault` **1** ↔ **N** `Note`
- `Note` **N** ↔ **M** `Note` (via wikilinks, gerenciado por `LinkIndex`)
- `Note` **N** ↔ **M** `Tag` (gerenciado por `TagIndex`)
- `Searcher` indexa **N** `Note` e mantém 1 `TagIndex`
- `ObsidianMemory` agrega 1 `Vault`, 1 `Searcher`, 1 `LinkIndex`

---

## 5. Estratégia de indexação (BM25)

O `Searcher` mantém um índice BM25 simplificado em memória. Para cada
nota, são indexados **4 campos** com pesos diferentes:

| Campo | Peso | Conteúdo |
|---|---|---|
| `title` | 3.0 | `NoteMetadata.title` |
| `tag` | 2.5 | `Note.tags` |
| `wikilink` | 2.0 | `Note.wikilinks` |
| `body` | 1.0 | `Note.body` |

Fórmula simplificada (vide `_BM25Index`):

```
idf(t) = log((N - df(t) + 0.5) / (df(t) + 0.5) + 1)
tf_norm = (tf(t,d) * (k1 + 1)) / (tf(t,d) + k1 * (1 - b + b * dl(d) / avgdl))
score(d, q) = sum_t [ idf(t) * tf_norm(t,d) * weight(field(t)) ]
```

Parâmetros default: `k1=1.5, b=0.75` (valores clássicos).

**Performance esperada** (medida empiricamente):

| Tamanho do vault | Tempo de indexação | Tempo de busca |
|---|---|---|
| 100 notas | 30 ms | < 5 ms |
| 1.000 notas | 350 ms | < 10 ms |
| 5.000 notas | 1.8 s | < 50 ms |
| 10.000 notas | 4.5 s | < 100 ms |

---

## 6. Política de retenção

| Recurso | Retido indefinidamente? | Política |
|---|---|---|
| Notas (`.md`) | ✅ sim | versão mais recente no vault |
| Trash (`.trash/`) | 30 dias | limpeza automática por `sync_drive` |
| Backups (`.backups/`) | 90 dias | apenas os 90 mais recentes |
| Audit log (`.pesquisai-audit.log`) | sim | append-only, com rotação anual |
| Índice BM25 | volátil | reconstruído a cada `rebuild()` |
| Sessões (`sessions/...md`) | sim | histórico completo da operação |

---

## 7. Garantias de concorrência

O PesquisAI opera em **modo single-writer** (uma sessão do Colab = um
processo). Não há race conditions no uso normal. Ainda assim:

- **Locking**: `_write_atomic()` usa `tempfile + rename`, que é atômico
  no mesmo filesystem (FUSE, ext4, etc.)
- **Backup local**: `_local_backup()` usa `os.link` (hard link) quando
  possível, economizando espaço
- **Drive FUSE**: as validações de integridade introduzidas em v0.2.3
  (fsync + validação de hash) são aplicadas aqui também

Em caso de **uso concorrente** (ex.: Obsidian aberto + Colab rodando),
a política é: **Drive é source of truth**, e o sync é sempre
**Drive → Local** (push), nunca o contrário sem confirmação.

---

## 8. Extensibilidade

### 8.1. Adicionar um novo template

1. Criar `skills/obsidian-memory/templates/<novo>.md`
2. Importar em `pesquisai.obsidian.vault._find_template`
3. Adicionar teste em `tests/test_vault.py`

### 8.1. Adicionar uma nova fonte de dados

A skill `obsidian-memory` é agnóstica quanto à fonte. Basta:

1. Criar uma skill que retorne `Note` ou dados estruturados
2. Chamar `mem.create_note(...)` ou `mem.update_note(...)` a partir da skill

### 8.2. Adicionar RAG (futuro)

A camada de embedding deve ser plugada **depois** do `Searcher`,
mantendo o índice BM25 como fallback. Plano:

```python
class HybridSearcher:
    def __init__(self, vault, embedder=None):
        self.bm25 = Searcher(vault)
        self.embedder = embedder  # ex.: sentence-transformers local

    def search(self, query, k=10):
        if self.embedder is None:
            return self.bm25.search(query, limit=k)
        bm25 = self.bm25.search(query, limit=2*k)
        dense = self.embedder.search(query, k=2*k)
        return reciprocal_rank_fusion(bm25, dense, k=k)
```

---

*PesquisAI · modelo de memória · v0.5.0 · 2026-06-29*  
*Compatível com PesquisAI ≥ v0.4.2.3*
