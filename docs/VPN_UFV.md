# 🛡 VPN da UFV no UFVAI (Colab) — guia completo

> **Desde a v0.7.11.** Permite que o servidor do Colab acesse a **rede da UFV**
> pela VPN institucional, sem precisar de `sudo`, `CAP_NET_ADMIN` ou
> `/dev/net/tun` no contêiner.

---

## 1. Para que serve

- Acessar **sistemas internos** da UFV (`sistemas.ufv.br`, `portal.ufv.br` etc.).
- Acessar **periódicos e bases** cujo conteúdo é liberado por IP institucional
  (ex.: CAPES Periódicos), quando a UFV roteia esse acesso pela VPN.
- Fazer o agente UFVAI consultar esses recursos **de dentro do Colab**.

> ℹ️ **Padrão: o OpenCode inteiro dentro da VPN (split tunnel).** Ao conectar,
> o UFVAI já marca **“Usar a VPN em todo o UFVAI”**: o serviço do OpenCode
> (agente, ferramentas, `bash`, `curl`) e o terminal passam a rodar **dentro**
> do namespace — a rede da UFV sai por `tun0` e a internet comum (LLM, GitHub,
> PyPI) continua pelo Colab via `tap0`. O **kernel do notebook** e o **wrapper**
> (porta 8001) continuam fora — o Colab não permite rotear o contêiner raiz sem
> `CAP_NET_ADMIN`. O **túnel total** (`redirect-gateway def1`, todo o tráfego
> pela UFV) é opcional (checkbox “Túnel total”): medido em 07/11/2026, a UFV
> **bloqueia a saída externa** nesse modo — só serve para modelos/serviços
> internos da UFV.

---

## 2. O que você precisa

| Item | Detalhe |
|---|---|
| Vínculo com a UFV | Aluno(a), servidor(a) ou colaborador(a) com acesso ao portal da VPN |
| Credenciais | **CPF** + **senha da VPN** (as mesmas de `vpn.ufvnet.ufv.br`) |
| Perfil `.ovpn` | Baixado automaticamente de `https://vpn.ufvnet.ufv.br/configs/UFV-linux.ovpn` |
| Runtime | Colab padrão (o UFVAI instala `openvpn` e `slirp4netns` via `apt` na primeira conexão) |

> 🔴 **1 dispositivo por CPF.** A UFV permite **uma** sessão VPN por CPF.
> Conectar o Colab pode **desconectar o seu computador**. Se isso acontecer,
> basta reconectar no computador depois de desconectar o Colab.

---

## 3. Como usar (interface)

1. Abra o UFVAI. **Depois dos Termos** (nome/e-mail + aceite) e **antes** do
   onboarding do provedor, aparece a tela **“Você é aluno(a) da UFV?”**.
2. Clique em **“Sim, sou aluno(a) da UFV”**.
3. No painel **VPN da UFV**, informe:
   - **CPF** (o campo formata automaticamente);
   - **Senha da VPN**;
   - opcionalmente, **“Lembrar neste Drive (cifrado)”**.
4. Clique em **Conectar**. O status passa por *Conectando…* até
   **Conectado à VPN da UFV**.
5. Clique em **Testar acesso** para conferir `https://sistemas.ufv.br/`.
6. Para encerrar, clique em **Desconectar**.

> Se você clicou em **“Não”**, a pergunta não volta a aparecer. O botão
> **🛡 VPN** na barra superior (ou no menu ☰ do celular) reabre o painel a
> qualquer momento.

---

## 3-A. Modo total — todo o UFVAI na VPN (PADRÃO = split + serviço no netns)

A opção **“Usar a VPN em todo o UFVAI (terminal + OpenCode)”** já vem
**marcada**. É o modo recomendado: o OpenCode acessa a **intranet/modelos
locais** pelo túnel (`tun0`) e a **internet comum (LLM, buscas, `pip`,
`curl`)** continua pelo Colab. Desmarque se quiser só o proxy SOCKS5, sem
mover o serviço.

O que acontece:

1. A VPN conecta em **split tunnel** (padrão; `redirect-gateway def1` só se
   “Túnel total” estiver marcado).
2. O UFVAI cria o namespace com **mount namespace + `/etc/resolv.conf` próprio**
   (`unshare -Urnm`), para o DNS interno funcionar.
3. O **serviço do OpenCode** e o **ttyd/tmux/TUI** passam a rodar **dentro** do
   namespace.
4. O host publica a porta 8000 **e a porta do serviço do OpenCode** via
   `slirp4netns`; o iframe continua em `localhost:8000` e o wrapper/CLI do
   host continuam alcançando o serviço (que agora escuta em `0.0.0.0` dentro
   do namespace).
5. O agente, as ferramentas (`bash`, `curl`, Python) e o terminal usam a VPN.

O que **não** passa pela VPN:

- O **wrapper** (porta 8001) e o **kernel do notebook** (células Python)
  continuam no namespace do Colab.
- O Google Drive e o proxy do Colab continuam fora.

> ⚠️ **Isso reinicia o terminal e o serviço do OpenCode.** A conversa é
> recarregada do banco (mesma sessão), mas a conexão cai por alguns segundos.
> Para voltar ao normal, clique em **Desconectar** (o UFVAI restaura o
> terminal/serviço no host).

> **Limitação honesta:** o contêiner inteiro do Colab não pode ser roteado
> sem `CAP_NET_ADMIN` no namespace raiz. O modo total cobre a pilha do UFVAI
> (agente + terminal + ferramentas), que é o que importa para o modelo local.
> Para túnel total do sistema, seria necessário uma VM/container próprio com
> TUN.

## 3-B. Modelo local da UFV (OpenCode)

Se o modelo (Ollama/vLLM) só existe na intranet:

1. Abra **🛡 VPN → Detalhes técnicos → Modelo/serviço na rede da UFV**.
2. Informe o **host interno** (ex.: `10.0.0.10`), a **porta remota**
   (ex.: `11434`) e a **porta local** (ex.: `11435`).
3. Clique em **Encaminhar**. O UFVAI cria
   `127.0.0.1:11435` → `10.0.0.10:11434` dentro do túnel.
4. No OpenCode, configure o provedor OpenAI-compatible com
   `baseURL = http://127.0.0.1:11435/v1`.

O encaminhamento usa o DNS da VPN para nomes internos e **não exige** o modo
total — é a opção mais leve se você só precisa do modelo.

## 4. Como usar (linha de comando)

```bash
# diagnóstico do ambiente
python -m pesquisai.vpn status

# baixar/atualizar o perfil oficial
python -m pesquisai.vpn profile --force

# conectar (a senha é lida do argumento; evite histórico do shell)
python -m pesquisai.vpn connect --cpf 00000000000 --password '••••••'

# testar um sistema interno pelo proxy
curl --socks5-hostname 127.0.0.1:1081 https://sistemas.ufv.br/

# desconectar
python -m pesquisai.vpn disconnect
```

Para fazer **um comando específico** usar a VPN:

```bash
ALL_PROXY=socks5h://127.0.0.1:1081 curl https://sistemas.ufv.br/
# ou
curl --socks5-hostname 127.0.0.1:1081 https://portal.ufv.br/
```

> `socks5h` faz a resolução DNS **dentro** do túnel (necessário para nomes
> internos como `sistemas.ufv.br`). `socks5` resolveria no cliente e falharia.

---

## 5. API (para integrações)

| Método | Rota | Corpo | Retorno |
|---|---|---|---|
| GET | `/api/vpn` | — | status, capacidades, perfil, `should_ask` |
| POST | `/api/vpn/connect` | `{cpf, password, remember, use_saved}` | estado (conexão em background) |
| POST | `/api/vpn/disconnect` | `{}` | estado |
| POST | `/api/vpn/profile` | `{force}` ou `{content}` | metadados do perfil |
| POST | `/api/vpn/test` | `{url?}` | teste interno/público |
| POST | `/api/vpn/forget` | `{}` | apaga credenciais |
| POST | `/api/vpn/answer` | `{choice: "ufv"\|"no"}` | grava a decisão da tela inicial |

Todas exigem o token de sessão do wrapper (mesmo esquema das demais rotas
`/api/*`).

---

## 6. Segurança e privacidade

- A **senha nunca** é escrita em log, `state.json` ou linha de comando do
  OpenVPN: ela vai por um arquivo `auth` com permissão `0600`, apagado ao
  desconectar.
- **“Lembrar”** grava CPF e senha **cifrados** (Fernet) no `keys_store.json`
  do Drive, com prefixo `vpn_ufv_`. Essas chaves são **filtradas** de
  `/api/apikey` e nunca aparecem na interface.
- Logs passam por `_redact()`: CPF vira `***.***.***-**` e `password=` vira
  `<oculto>`.
- O perfil `.ovpn` é público, mas é gravado com `0600`.
- **Você é responsável** pelo uso: siga as regras da UFV/DTI, da CAPES
  Periódicos e dos contratos de cada base. Não compartilhe suas credenciais.

---

## 7. Como funciona por dentro

```
Colab (namespace raiz, sem NET_ADMIN)
  UFVAI ──► 127.0.0.1:1081 (slirp hostfwd)
                 │
     ┌───────────┼──────── user+net namespace (unshare -Urn) ────────┐
     │  slirp4netns: tap0 10.0.2.100, gw 10.0.2.2                   │
     │        │                                                     │
     │        ├── UDP 1195 ──► vpn.ufvnet.ufv.br (OpenVPN)          │
     │        │                        │                            │
     │        └── tun0 ◄───────────────┘  split (UFV) / total opcional │
     │  SOCKS5 0.0.0.0:1080 ──► hosts da UFV via tun0               │
     └──────────────────────────────────────────────────────────────┘
```

1. `unshare -Urnm` cria os namespaces de **mount + rede**; dentro dele o
   UFVAI é root e tem `CAP_NET_ADMIN`.
2. Um `/etc/resolv.conf` próprio é bind-montado (DNS da VPN + públicos), para
   o OpenCode/terminal resolverem nomes internos.
3. `slirp4netns --configure` cria `tap0` e o NAT em espaço de usuário.
4. O OpenVPN roda com o perfil reescrito para **fixar o IP** do servidor
   (o DNS do namespace não resolve `vpn.ufvnet.ufv.br`). Só recebe
   `redirect-gateway def1` se “Túnel total” estiver marcado (padrão: split).
5. O SOCKS5 em Python puro (stdlib) roda dentro do namespace; o
   `slirp4netns add_hostfwd` o publica em `127.0.0.1:1081`.
6. O proxy resolve nomes pelo **DNS empurrado pela VPN**, depois por
   `1.1.1.1`/`8.8.8.8`, depois pelo resolver do sistema.

### Modo direto

Em um Linux normal com `/dev/net/tun` e `CAP_NET_ADMIN` (ex.: o `.deb` em uma
máquina pessoal), o módulo usa o **modo direto**: o OpenVPN roda no namespace
principal e as rotas valem para o sistema. Nesse caso o SOCKS5 é opcional.

---

## 8. Diagnóstico e problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| “CPF ou senha recusados” | Credencial errada ou senha do e-mail em vez da VPN | Confira no portal `vpn.ufvnet.ufv.br`; a senha é a da VPN |
| “Tempo esgotado aguardando a VPN” | UDP 1195 bloqueado ou rede instável | Rode `python -m pesquisai.vpn status` e veja o log; tente de novo |
| “O proxy SOCKS5 não abriu” | `slirp4netns` ausente/versão antiga | `sudo apt-get install -y slirp4netns` (o UFVAI tenta sozinho) |
| “Não foi possível criar o namespace” | `unshare` indisponível | `sudo apt-get install -y util-linux` |
| Teste interno falha, público passa | DNS interno não empurrado | Desconecte/reconecte; veja `dns` nos detalhes técnicos |
| “A conexão caiu” | Processo do OpenVPN morreu | Clique em **Conectar** de novo |
| Teste mostra `www.ufv.br: 000` e “Resolving timed out” | O DNS do namespace não resolve | A 0.7.11 usa **10.0.2.3** (DNS do slirp) para nomes públicos; `sistemas.ufv.br` exige o DNS empurrado pela VPN (veja `DNS` nos detalhes e `dhcp-option DNS` no log) |
| `IP pela VPN: —` / `www.ufv.br: 000` | Proxy sem DNS ou VPN sem rota | Confira `TUN`, `DNS` e o log; em túnel total, 1.1.1.1 pode ser bloqueado — o fallback 10.0.2.3 resolve públicos |

Logs:

- `~/.config/ufvai/vpn/openvpn.log` — handshake, rotas, erros.
- `~/.config/ufvai/vpn/socks.log` — proxy.
- `~/.config/ufvai/vpn/slirp.log` — NAT.
- `~/.config/ufvai/vpn/state.json` — estado (sem senha).

No painel, abra **Detalhes técnicos** para ver modo, TUN, rotas, DNS e as
últimas linhas do log.

---

## 9. Testes

```bash
python -m pytest tests/test_v0711_vpn.py -q -o addopts=""
```

31 testes offline: parsing/validação do perfil, máscara de CPF, redaction,
decisão da tela inicial, credenciais cifradas, handshake SOCKS5 + relay local,
capacidades, formato do status, bind `0.0.0.0`/porta publicada do serviço,
padrão split tunnel e modo total aceitando split.

O teste **real** com a UFV depende das suas credenciais e não é automatizado.
A prova de conceito feita no Colab mostrou:

- UDP 1195 alcança `vpn.ufvnet.ufv.br` e o TLS completa;
- credenciais falsas retornam `AUTH_FAILED` (comportamento esperado);
- o caminho `netns → slirp → SOCKS5 → 127.0.0.1:1081` devolveu **HTTP 200**
  para `https://www.ufv.br/`.

---

## 10. Limitações

- **1 dispositivo por CPF** (regra da UFV).
- **Split tunnel**: só a rede da UFV; o resto do Colab não passa pela VPN.
- **Sem túnel transparente** no Colab (impossível sem `NET_ADMIN` no
  namespace raiz). Use o proxy.
- **Credenciais na nuvem**: a VM do Colab é do Google. Se isso for um
  problema para você, **não marque “lembrar”** e desconecte ao terminar.
- **Não substitui** a VPN do seu computador para uso pessoal; é uma conexão
  adicional, sujeita ao limite de dispositivos.

---

## 11. Referências

- Tutorial oficial UFV (Ubuntu): <https://vpn.ufvnet.ufv.br/linux_ubuntu.html>
- Perfil oficial: <https://vpn.ufvnet.ufv.br/configs/UFV-linux.ovpn>
- DTI/UFV — acesso remoto: <https://www1.dti.ufv.br/acesso-remoto-vpn/>
- `slirp4netns`: <https://github.com/rootless-containers/slirp4netns>
- OpenVPN 2.6: <https://openvpn.net/community-resources/reference-manual-for-openvpn-2-6/>
