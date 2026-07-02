# 🔄 Workflow PesquisAI ↔ Obsidian

> **Versão:** 0.5.0
> **Status:** Documentação operacional
> **Audiência:** usuários finais do PesquisAI

Este documento descreve o **workflow recomendado** para uso do
PesquisAI com Obsidian em diferentes cenários.

---

## 0. Onde tudo fica salvo

> **REGRA:** todos os artefatos (vault, notas, backups, logs) ficam
> **no Google Drive** do usuário. **Nunca** no Colab efêmero.

| Onde | O quê |
|---|---|
| **Colab** (sessão atual) | apenas: o índice BM25 em RAM, o código Python rodando |
| **Google Drive** (`/content/drive/My Drive/PesquisAI/vault/`) | vault, notas, backups, audit log |
| **Obsidian local** (se o usuário instalou) | cópia sincronizada via Remotely Save ou git |
| **Múltiplos dispositivos** (mobile, tablet) | sincronizados via plugin Sync do Obsidian |

Quando a sessão do Colab termina:

1. O índice BM25 em RAM é **perdido** (reconstruído na próxima sessão)
2. Tudo que está no Drive é **preservado**
3. Na próxima sessão, o PesquisAI detecta o vault e reconstrói o índice

---

## 1. Cenário 1: TCC / Dissertação / Tese (longo prazo)

**Duração típica:** 6-18 meses
**Volume esperado:** 50-300 notas

### 1.1. Setup inicial

```bash
# 1. Inicialize o vault
./scripts/init_vault.sh

# 2. Crie o MOC do projeto
mem.create_note(
    "moc/pnae-tcc.md",
    title="PNAE e Capacidade Estadual — TCC",
    template="project-moc",
    tags=("pesquisai/moc",),
    context={"project": "pnae-tcc", "scope": "TCC de Graduação"},
)
```

### 1.2. Workflow diário

```
┌──────────────────────────────────────────────────┐
│ Manhã (5 min)                                    │
│   1. Abrir o Obsidian                            │
│   2. Editar a daily de hoje                      │
│   3. Listar as 3 ações mais importantes         │
└──────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────┐
│ PesquisAI (interativo)                           │
│   - Pesquisar literatura existente              │
│   - Coletar dados do IBGE / DataSUS              │
│   - Analisar com Python                          │
│   - Pedir para salvar achados no vault           │
└──────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────────────────┐
│ Fim do dia (10 min)                              │
│   1. Revisar a daily                            │
│   2. Adicionar insights                          │
│   3. Mover capturas do inbox para a pasta certa │
│   4. Sincronizar o vault (sync_drive)            │
└──────────────────────────────────────────────────┘
```

### 1.3. A cada 2 semanas (revisão)

```
┌──────────────────────────────────────────────────┐
│ Revisão quinzenal                                │
│   1. Abrir o MOC do projeto                     │
│   2. Verificar gaps na revisão de literatura    │
│   3. Verificar status das hipóteses             │
│   4. Atualizar cronograma                        │
└──────────────────────────────────────────────────┘
```

### 1.4. Comandos úteis

```python
# Ver o que foi feito nas últimas 5 sessões
for s in mem.search("pnae", tags=["pesquisai/session"], limit=5):
    print(s.note.path, s.note.metadata.updated)

# Encontrar papers que ainda não foram lidos
unread = [n for n in mem.by_tag("pesquisai/literature")
          if n.metadata.status == "draft"]
print(f"{len(unread)} papers a revisar")
```

---

## 2. Cenário 2: Artigo científico (médio prazo)

**Duração típica:** 2-6 meses
**Volume esperado:** 20-50 notas

### 2.1. Setup

```bash
# MOC do artigo
mem.create_note(
    "moc/artigo-pnae-2026.md",
    title="Artigo PNAE-MG 2026",
    template="project-moc",
    context={"project": "artigo-pnae-2026", "scope": "Artigo para revista X"},
)
```

### 2.2. Workflow IMRaD (adaptado)

| Etapa IMRaD | Notas criadas | Onde |
|---|---|---|
| Introdução | `research/intro.md` | Pesquisa iterativa |
| Métodos | `methodology/<metodo>.md` | Reutilizável |
| Resultados | `research/resultados.md` | Append-only |
| Discussão | `research/discussao.md` | Iterativo |
| Conclusão | `research/conclusao.md` | Última |
| Anexo | `reference/<citekey>.md` | Por citação |

### 2.3. Rastreabilidade

Cada nota de seção do artigo é linkada ao MOC:

```yaml
# research/resultados.md
---
project: artigo-pnae-2026  # mesmo valor em todos os arquivos
---
```

No MOC:

```dataview
LIST
FROM "research"
WHERE project = "artigo-pnae-2026"
SORT file.mtime DESC
```

---

## 3. Cenário 3: Trabalho de extensão / relatório técnico

**Duração típica:** 1-3 meses
**Volume esperado:** 10-30 notas

### 3.1. Setup

```bash
# MOC do projeto
mem.create_note(
    "moc/extensao-agrotoxicos.md",
    title="Relatório de Extensão — Agrotóxicos",
    template="project-moc",
    context={"project": "extensao-agrotoxicos", "scope": "Relatório de Extensão"},
)
```

### 3.2. Workflow

```
1. Capturar cada atividade no inbox
2. Mover para a pasta apropriada semanalmente
3. Consolidar em relatório final via Dataview
```

```dataview
TABLE
  atividade AS "Atividade",
  local AS "Local",
  participantes AS "Público"
FROM "extensao"
WHERE project = "extensao-agrotoxicos"
SORT file.ctime ASC
```

---

## 4. Cenário 4: Estudos exploratórios (curto prazo)

**Duração típica:** 1-4 semanas
**Volume esperado:** 5-15 notas

### 4.1. Workflow mínimo

```python
# 1. Inbox: capturar tudo
mem.create_note("inbox/2026-06-29.md", title="Captura 2026-06-29")

# 2. Pesquisa: criar nota de revisão
mem.create_note("research/exploratoria-x.md", template="research")

# 3. Fonte: anotar
mem.create_note("datasource/fonte-x.md", template="data-source")

# 4. Triage: decidir se vira TCC / artigo / extensão
```

---

## 5. Boas práticas

### 5.1. Naming

- ✅ `pesquisai/2026-06-29.md` (em `daily/`)
- ✅ `pesquisai/santos-2024-pnae-mg.md` (em `literature/`)
- ✅ `pesquisai/H1-pnae-capacidade.md` (em `hypothesis/`)
- ❌ `pesquisai/nota_final_versão_3.md` (vago)
- ❌ `pesquisai/SEM TÍTULO.md` (sem slug)

### 5.2. Tags

- **1-3 tags por nota** é o ideal
- Tags aninhadas são permitidas (`pesquisai/area/educacao`)
- Use a taxonomia `pesquisai/*` como prefixo sempre

### 5.3. Wikilinks

- Use nomes **canônicos** (sem acentos, sem variação de caixa)
- Use `[[nota|apelido]]` para tornar a leitura fluente
- Use `[[nota#seção]]` para apontar para uma seção específica

### 5.4. Backlinks

- Toda nota importante deve ter **pelo menos 1 backlink**
- O MOC raiz é o agregador universal
- Notas "órfãs" (sem backlinks) são candidatas a deletar/mover

### 5.5. Backups

- O PesquisAI faz backup local antes de sync destrutivo
- O Drive mantém o histórico de versões (Google Drive)
- Opcional: sync via git (mantém histórico completo)

---

## 6. Comandos rápidos (cheat-sheet)

| Comando | Efeito |
|---|---|
| `mem.search("X")` | Busca textual no vault |
| `mem.by_tag("pesquisai/ibge")` | Notas com tag específica |
| `mem.recent_daily_notes(3)` | Últimas 3 dailies |
| `mem.tags_summary()` | Contagem por tag |
| `mem.stats()` | Estatísticas gerais |
| `mem.start_session()` | Inicia log de sessão |
| `mem.create_note(...)` | Cria nota de template |
| `mem.update_note(...)` | Anexa/substitui conteúdo |
| `mem.end_session(...)` | Grava log de sessão |
| `mem.sync_drive(...)` | Espelha para outra pasta |
| `mem.sync_git(...)` | Sincroniza via git |
| `mem.context_brief()` | Resumo para o prompt |

---

## 7. Integração com skills existentes

| Skill PesquisAI | Como interage com o vault |
|---|---|
| `ibge-br` | Salva datasets em `datasource/ibge-...` |
| `opendatasus` | Salva indicadores em `datasource/datasus-...` |
| `agrobr` | Salva em `datasource/agro-...` |
| `dados-brasil` | Salva em `datasource/...` |
| `citation-management` | Salva refs em `reference/<citekey>.md` |
| `qualitativa` | Salva análises em `research/qualitativa-...` |
| `UFV-ABNT` | Formata notas em `research/` |
| `scientific` | Estrutura notas via template `research` |
| `grant-finder` | Salva editais em `inbox/edital-<id>.md` |

---

*PesquisAI · workflow Obsidian · v0.5.0 · 2026-06-29*  
*Compatível com PesquisAI ≥ v0.4.2.3*
