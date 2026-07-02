"""
builtin_templates.py — Templates embutidos no módulo autopilot.

Estes templates garantem que o PesquisAI possa criar notas **mesmo
sem a skill obsidian-memory estar clonada**. Quando a skill está
instalada (em ``~/.agents/skills/obsidian-memory/templates/``), os
templates da skill têm prioridade (podem ser customizados pelo
usuário). Estes são o fallback.

Templates incluídos:
- inbox (captura rápida — default do autopilot)
- research (projeto de pesquisa)
- daily (nota diária)
- session (log de sessão)
- literature (revisão de paper)
"""

from __future__ import annotations

# Dicionário nome → conteúdo Markdown
BUILTIN_TEMPLATES: dict[str, str] = {
    "inbox": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/inbox
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

> **Capturado em:** {{date}}
> **Origem:** autopilot

{{body}}
""",

    "inbox-note": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/inbox
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

{{body}}
""",

    "research": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/research
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

> **Data de início:** {{date}}

## Pergunta de pesquisa

{{research_question}}

## Objetivos

- [ ]

## Resultados

{{body}}

## Próximos passos

- [ ]

## Referências

-
""",

    "research-note": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/research
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

## Pergunta de pesquisa

{{research_question}}

## Resultados

{{body}}

## Próximos passos

- [ ]
""",

    "daily": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/daily
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: ""
---

# {{title}}

## 🎯 Foco do dia

- [ ]

## 📥 Inbox

-

## 💡 Insights

{{body}}

## 📌 Próximos passos

- [ ]
""",

    "daily-note": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/daily
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: ""
---

# {{title}}

## 🎯 Foco do dia

- [ ]

## 💡 Insights

{{body}}

## 📌 Próximos passos

- [ ]
""",

    "session": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/session
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: ""
---

# {{title}}

## Resumo

{{body}}

## Skills usadas

-

## Arquivos gerados

-
""",

    "session-log": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/session
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: ""
---

# {{title}}

## Resumo

{{body}}
""",

    "literature": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/literature
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

## Resumo

{{body}}

## Pontos fortes

-

## Limitações

-

## Conexões

-
""",

    "literature-note": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/literature
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

## Resumo

{{body}}
""",

    "methodology": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/methodology
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

## Quando usar

## Procedimento

{{body}}

## Limitações

-
""",

    "datasource": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/datasource
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

## Identificação

{{body}}

## Cuidados metodológicos

-
""",

    "hypothesis": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/hypothesis
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

## Enunciado

{{body}}

## Predições

-

## Status

- [ ] Formulada
- [ ] Testada
""",

    "reference": """---
title: "{{title}}"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/reference
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}}

{{body}}
""",

    "moc": """---
title: "{{title}} — MOC"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/moc
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}} — Map of Content

## Visão geral

{{body}}

## Notas do projeto

```dataview
LIST
FROM ""
WHERE project = "{{project}}"
SORT file.mtime DESC
```
""",

    "project-moc": """---
title: "{{title}} — MOC"
created: {{date}}
updated: {{date}}
tags:
  - pesquisai/moc
  - pesquisai/draft
author: ""
created_by: pesquisai
status: draft
source: ""
project: "{{project}}"
---

# {{title}} — Map of Content

## Visão geral

{{body}}
""",
}


def get_builtin_template(name: str) -> str | None:
    """Retorna o conteúdo de um template embutido, ou None se não existir."""
    return BUILTIN_TEMPLATES.get(name) or BUILTIN_TEMPLATES.get(f"{name}-note")
