# 🔒 Segurança — PesquisAI

## Reportando Vulnerabilidades

O PesquisAI é um software educacional e de pesquisa. Levamos a segurança a sério.

Se você encontrar uma vulnerabilidade de segurança, **por favor, não abra uma issue pública**. Em vez disso:

1. Envie um e-mail para **gustavo.braga@ufv.br** com:
   - Descrição detalhada da vulnerabilidade
   - Passos para reproduzir
   - Possível impacto
   - Sugestão de correção (se aplicável)

2. Aguarde o retorno antes de divulgar publicamente.

## Práticas de Segurança

### API Keys

- O PesquisAI **não envia** suas API keys para servidores externos.
- As keys são criptografadas (AES-128-CBC + HMAC-SHA256) e armazenadas no seu Google Drive em:
  - `PesquisAI/backups/keys_store.json` — chaves criptografadas
  - `PesquisAI/backups/keys_encryption_key.bin` — chave de criptografia (arquivo SEPARADO)
- **🔒 Defesa em profundidade:** um invasor precisa de AMBOS os arquivos para obter as keys.
- **⚠️ Recomendação:** proteja sua conta Google com autenticação de dois fatores.

### Dados

- Todo processamento ocorre **localmente** na sua sessão do Google Colab.
- Nenhum dado é enviado para servidores do desenvolvedor.
- Arquivos gerados ficam exclusivamente na sua pasta `PesquisAI/` no Drive.

### LGPD (Lei nº 13.709/2018)

O PesquisAI segue princípios de *Privacy by Design*:
- **Minimização**: apenas dados necessários à tarefa são processados
- **Retenção**: você controla o que é salvo e por quanto tempo
- **Transparência**: você vê exatamente quais arquivos são lidos/gravados

## Boas Práticas para Usuários

1. 🔑 **Não compartilhe** chaves de API ou tokens
2. 🗑️ **Remova** os arquivos `keys_store.json` e `keys_encryption_key.bin` do Drive quando não for mais necessário
3. 🔐 **Use senha forte** na sua conta Google
4. 👁️ **Revise** os arquivos gerados antes de compartilhá-los
5. 🔄 **Mantenha** o repositório atualizado

## Dependências

Manter as dependências atualizadas é essencial. Use:

```bash
pip install --upgrade google-api-python-client google-auth-httplib2 google-auth-oauthlib
```

---

## v0.6.0 — Hardening (21/08/2026)

Auditoria integral aplicada (detalhes em `docs/SECURITY_AUDIT_2026-08-21.md`):

- **CORS removido** + **token de sessão** obrigatório em `/api/*` (`X-UFVAI-Token`, injetado no HTML do wrapper).
- Sanitização de comandos valida **cada segmento após `&&`**.
- `opencode_auth.json` cifrado no Drive; chaves mascaradas nos GETs; sem nomes de env secrets nas respostas.
- ThreadingHTTPServer · cap 10 MB · rate limit 120/min/IP · headers seguros · anti-traversal no restore/backup.
- Bind local padrão `127.0.0.1` (Colab mantém `0.0.0.0`) — override `UFVAI_BIND_HOST`.
- `--yolo`: mantido por padrão; desligue com `PESQUISAI_YOLO=0`.

### Variáveis de ambiente de segurança/privacidade

| Variável | Padrão | Efeito |
|---|---|---|
| `UFVAI_TELEMETRY` | `1` | `0` desliga telemetria globalmente |
| `UFVAI_GA_MEASUREMENT_ID` / `UFVAI_GA_API_SECRET` | vazias | Sem elas, nada é enviado |
| `PESQUISAI_YOLO` | `1` | `0` exige aprovação manual das ações do agente |
| `UFVAI_BIND_HOST` | auto | Força host do wrapper |
| `PESQUISAI_TTYD_CRED` | vazio | `user:senha` para credenciais básicas no ttyd |

Reporte vulnerabilidades conforme a seção acima.

