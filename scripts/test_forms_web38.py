#!/usr/bin/env python3
"""test_forms_web38.py — formulários da ferramenta "question" (v0.7.11-web38).

Sobe um servidor que imita os endpoints /form do motor, aponta o webapi para
ele e valida pending_forms(), form_reply() e as rotas do gateway. Também
confere os ganchos no frontend (app.js / index.html).

Roda: python3 scripts/test_forms_web38.py
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pesquisai.webapi as w          # noqa: E402
import pesquisai.webui_server as s    # noqa: E402

SID = "ses_test"
STATE = {
    "forms": [
        {
            "id": "frm_1",
            "sessionID": SID,
            "title": "Pergunta do agente",
            "metadata": {"kind": "question"},
            "fields": [
                {
                    "key": "modo",
                    "type": "multiselect",
                    "options": [{"value": "a", "label": "A"}, {"value": "b", "label": "B"}],
                    "custom": True,
                }
            ],
        }
    ],
    "replies": [],
}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return

    def _j(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == f"/api/session/{SID}/form":
            self._j(200, {"data": STATE["forms"]})
        else:
            self._j(404, {"error": "not found"})

    def do_POST(self):
        p = urlparse(self.path).path
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if p.startswith(f"/api/session/{SID}/form/") and p.endswith("/reply"):
            fid = p.split("/")[-2]
            ans = body.get("answer") or {}
            for f in STATE["forms"]:
                if f["id"] == fid:
                    for fld in f["fields"]:
                        if fld["type"] == "multiselect" and not isinstance(ans.get(fld["key"]), list):
                            self._j(400, {"_tag": "FormInvalidAnswerError", "message": "Expected string array"})
                            return
            STATE["replies"].append((fid, ans))
            STATE["forms"] = [f for f in STATE["forms"] if f["id"] != fid]
            self.send_response(204)
            self.end_headers()
            return
        self._j(404, {"error": "not found"})


srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
w.engine = lambda: ("127.0.0.1", port, "x")

ok = total = 0


def check(name, cond):
    global ok, total
    total += 1
    print(("✓" if cond else "✗") + "  " + name)
    if cond:
        ok += 1


forms = w.pending_forms(SID)
check("pending_forms lista o formulário", len(forms) == 1 and forms[0]["title"] == "Pergunta do agente")
check("campo multiselect presente", bool(forms) and forms[0]["fields"][0]["key"] == "modo")
r = w.form_reply(SID, forms[0]["id"], {"modo": ["a"]})
check("form_reply aceita array", r.get("ok") is True)
check("form some após responder", len(w.pending_forms(SID)) == 0)

STATE["forms"] = [{
    "id": "frm_2", "sessionID": SID, "title": "T2",
    "fields": [{"key": "q", "type": "multiselect", "options": [{"value": "x", "label": "X"}]}],
}]
st, body = s._handle_api("GET", f"/api/ufvai/sessions/{SID}/form", {}, {})
check("gateway GET /form", st == 200 and len(body.get("forms") or []) == 1)
st2, body2 = s._handle_api("POST", f"/api/ufvai/sessions/{SID}/form", {}, {"formID": "frm_2", "answer": {"q": ["x"]}})
check("gateway POST /form", st2 == 200 and body2.get("ok") is True)

app = (ROOT / "pesquisai" / "webui" / "app.js").read_text(encoding="utf-8")
html = (ROOT / "pesquisai" / "webui" / "index.html").read_text(encoding="utf-8")
for fn in ["function renderForm", "function loadForms", "function replyForm"]:
    check(f"app.js contém {fn}", fn in app)
check("app.js trata form.created", "case 'form.created'" in app)
check("index.html tem #forms", 'id="forms"' in html)
check("multiselect envia array", "answers[key] = [value]" in app)

srv.shutdown()
print(f"\n{ok}/{total} verificações passaram")
sys.exit(0 if ok == total else 1)
