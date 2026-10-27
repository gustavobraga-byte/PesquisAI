# UFVAI Drive Guard (v0.7.7)

Plugin do servidor **UFVAI V2** (OpenCode 2.x) que impede o agente UFVAI de
acessar a pasta **“My Drive”** do Google Drive — **exceto**
`My Drive/PesquisAI` e todas as suas subpastas. A regra vale **inclusive com
`--auto`** (auto-aprovação de permissões).

## O que é bloqueado

| Caminho | Resultado |
|---|---|
| `/content/drive/My Drive` (raiz) | ❌ bloqueado |
| `/content/drive/My Drive/Artigo.docx` | ❌ bloqueado |
| `/content/drive/My Drive/PesquisAI` e subpastas | ✅ permitido |
| `/content/drive/MyDrive/...` (no Colab é o **mesmo** diretório de `My Drive`) | mesma regra: só `MyDrive/PesquisAI` é liberado |
| `../` a partir de `PesquisAI/` que escape para a raiz | ❌ bloqueado |
| `~/PesquisAI` (offline, fora do Drive) | ✅ não é afetado |

## Como o bloqueio é feito (três camadas)

1. **Regras declarativas no `opencode.json`** — `permissions` com `deny` para
   `external_directory`, `read` e `edit` em `/content/drive` e
   `/content/drive/*`, seguidas de `allow` apenas para
   `/content/drive/My Drive/PesquisAI` e descendentes. Regra `deny` é final no
   motor: o `--auto` não a converte em aprovação.
2. **`permission.evaluate`** (`index.js`) — reescreve para `deny` qualquer
   decisão que sobrevenha para `read`, `edit`, `external_directory`, `shell`,
   `glob` ou `grep` apontando para fora de `PesquisAI`.
3. **`tool.execute.before`** (`index.js`) — inspeciona a entrada de cada
   ferramenta e lança erro **antes** de qualquer acesso ao disco.

## Limites conhecidos

- O `shell` é analisado por heurística (tokens, aspas, `..`, symlinks). Um
  comando deliberadamente ofuscado (ex.: base64 montado em tempo de execução)
  pode escapar da análise textual; as camadas 1 e 2 continuam valendo para as
  ferramentas nativas de arquivo, e o comando é registrado no log.
- O plugin governa **as ferramentas do agente**. O próprio aplicativo UFVAI
  (servidor Python da interface) continua acessando o Drive para gravar a
  memória e os backups — por desenho.

## Configuração

```jsonc
{
  "plugins": [
    {
      "package": "/caminho/para/ufvai-drive-guard",
      "options": {
        "mount": "/content/drive",
        "allowed": "/content/drive/My Drive/PesquisAI"
      }
    }
  ]
}
```

Equivalentes por ambiente: `UFVAI_DRIVE_GUARD_ROOT`,
`UFVAI_DRIVE_GUARD_ALLOWED`, `UFVAI_DRIVE_GUARD_LOG`.

## Auditoria

Toda tentativa bloqueada é acrescentada em
`~/.local/state/ufvai/drive-guard.log` (uma linha por evento, ISO-8601).
