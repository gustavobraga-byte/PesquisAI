"""test_attach_api.py — como o motor aceita anexos de arquivo.

Testa três formatos de anexo no `POST /api/session/{id}/prompt`:
  1. `source: {type:"inline"}` com `uri` = data URI (base64)
  2. `source: {type:"uri", uri}` apontando para um arquivo do projeto
  3. `source: {type:"uri"}` + `uri` = caminho do arquivo
Também testa `variant` no POST de modelo e o `POST /api/session/{id}/background`.
"""

import base64, json, urllib.request, urllib.error
from pathlib import Path

SERVICE = json.loads(Path("/root/.local/state/opencode/service.json").read_text())
PW = SERVICE["password"]
BASE = "http://127.0.0.1:49374"


def call(method, path, body=None, timeout=30):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": "Basic " + base64.b64encode(f"opencode:{PW}".encode()).decode(),
                 "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            return r.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw.decode(errors="replace")[:400]
    except Exception as e:
        return 0, str(e)


def main():
    st, data = call("POST", "/api/session", {"title": "teste-anexo", "location": {"directory": "/tmp/opencode"}})
    sid = (data.get("data") or {}).get("id")
    print("sessão:", st, sid)
    if not sid:
        print(data)
        return

    sample = Path("/tmp/opencode/anexo-prova.txt")
    sample.write_text("linha 1 do anexo\nlinha 2 do anexo\n", encoding="utf-8")
    data_uri = "data:text/plain;base64," + base64.b64encode(sample.read_bytes()).decode()

    casos = [
        ("inline + data URI", {"text": "Leia o anexo e diga a primeira linha.",
                               "files": [{"uri": data_uri, "source": {"type": "inline"}, "name": "anexo-prova.txt"}]}),
        ("uri + caminho local", {"text": "Leia o arquivo anexado.",
                                 "files": [{"uri": str(sample), "source": {"type": "uri", "uri": str(sample)},
                                            "name": "anexo-prova.txt"}]}),
        ("só uri (sem source)", {"text": "Leia o arquivo.",
                                  "files": [{"uri": str(sample), "name": "anexo-prova.txt"}]}),
    ]
    for nome, body in casos:
        st, data = call("POST", f"/api/session/{sid}/prompt", body)
        print(f"\n--- {nome}: HTTP {st}")
        print("   ", json.dumps(data, ensure_ascii=False)[:400])

    print("\n--- modelo com variant:", call("POST", f"/api/session/{sid}/model",
                                             {"model": {"id": "gemini-flash-lite-latest", "providerID": "google", "variant": "high"}})[0])
    print("--- background:", call("POST", f"/api/session/{sid}/background", {})[0])
    print("--- compact:", call("POST", f"/api/session/{sid}/compact", {})[0])
    print("--- fork:", call("POST", f"/api/session/{sid}/fork", {})[0])
    print("--- context:", call("GET", f"/api/session/{sid}/context")[0])
    print("--- skill:", json.dumps(call("GET", "/api/skill")[1], ensure_ascii=False)[:300])
    print("--- command:", json.dumps(call("GET", "/api/command")[1], ensure_ascii=False)[:400])
    print("--- fs/find:", json.dumps(call("GET", "/api/fs/find?query=anexo&type=file&limit=5")[1], ensure_ascii=False)[:400])
    print("--- fs/list:", json.dumps(call("GET", "/api/fs/list?path=/tmp/opencode")[1], ensure_ascii=False)[:400])
    print("--- background body:", json.dumps(call("GET", f"/api/session/{sid}")[1].get("data", {}).get("background"), ensure_ascii=False)[:200])


main()
