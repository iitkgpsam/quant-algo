"""The strategy panel door: a signed-in owner reaches a strategy's loopback panel, nothing else does."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
from flask import Flask

from utils.strategy_panel_port import panel_port_for_file

PORT = 5197


def _file(tmp_path, text):
    p = tmp_path / "s.py"
    p.write_text(text, encoding="utf-8")
    return str(p)


def test_header_parsing(tmp_path):
    assert panel_port_for_file(_file(tmp_path, "# openalgo-panel-port: 5157\nx = 1\n")) == 5157
    assert panel_port_for_file(_file(tmp_path, "# openalgo-panel-port: 8765\n")) is None      # outside the panel range
    assert panel_port_for_file(_file(tmp_path, "# openalgo-panel-port: 5000\n")) is None
    assert panel_port_for_file(_file(tmp_path, "x = 1\n" * 70 + "# openalgo-panel-port: 5157\n")) is None  # beyond line 60
    assert panel_port_for_file(_file(tmp_path, "print('no header')\n")) is None
    assert panel_port_for_file(str(tmp_path / "missing.py")) is None
    assert panel_port_for_file(None) is None


class _Upstream(BaseHTTPRequestHandler):
    body_seen = b""
    header_seen = ""
    ctype = "application/json"

    def _send(self, data, ctype=None):
        self.send_response(200)
        self.send_header("Content-Type", ctype or type(self).ctype)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/":
            self._send(b"<html>panel</html>", "text/html; charset=utf-8")
        else:
            self._send(json.dumps({"path": self.path}).encode())

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        type(self).body_seen = self.rfile.read(n)
        type(self).header_seen = self.headers.get("X-QA-Panel", "")
        self._send(b'{"ok": true}')

    def log_message(self, *a):
        pass


@pytest.fixture()
def upstream():
    srv = HTTPServer(("127.0.0.1", PORT), _Upstream)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield _Upstream
    srv.shutdown()
    srv.server_close()


@pytest.fixture()
def client(monkeypatch, tmp_path):
    import blueprints.strategy_panel as sp
    import utils.session as us

    monkeypatch.setattr(us, "is_session_valid", lambda: True)
    state = {"running": True, "owner": "me", "file": _file(tmp_path, f"# openalgo-panel-port: {PORT}\n")}

    def fake_resolve(strategy_id, user_id):
        if strategy_id != "abc":
            return None, ("nope", 404)
        if user_id != state["owner"]:
            return None, ("nope", 403)
        return {"file_path": state["file"], "is_running": state["running"]}, None

    monkeypatch.setattr(sp, "_resolve", fake_resolve)
    app = Flask(__name__)
    app.secret_key = "x"
    app.register_blueprint(sp.strategy_panel_bp)
    c = app.test_client()
    with c.session_transaction() as s:
        s["user"] = "me"
    c.state = state
    return c


def test_owner_reaches_page_and_state(client, upstream):
    r = client.get("/python/abc/panel/")
    assert r.status_code == 200 and b"panel" in r.data and r.headers["Cache-Control"] == "no-store"
    r = client.get("/python/abc/panel/api/state")
    assert r.status_code == 200 and r.get_json() == {"path": "/api/state"}


def test_command_needs_header_and_is_forwarded(client, upstream):
    assert client.post("/python/abc/panel/api/cmd", json={"cmd": "pause"}).status_code == 403
    r = client.post("/python/abc/panel/api/cmd", json={"cmd": "pause"}, headers={"X-QA-Panel": "1"})
    assert r.status_code == 200 and json.loads(upstream.body_seen) == {"cmd": "pause"}
    assert upstream.header_seen == "1"                                       # the strategy's own channel needs the header too


def test_only_the_three_fixed_paths(client, upstream):
    for path in ("api/other", "../x", "static/a.js", "api/cmd/extra"):
        assert client.get(f"/python/abc/panel/{path}").status_code in (404, 405)
    assert client.get("/python/abc/panel/api/cmd").status_code == 404           # GET on the command path
    assert client.post("/python/abc/panel/api/state", headers={"X-QA-Panel": "1"}).status_code == 404


def test_not_running_and_no_panel_and_other_owner(client, upstream):
    client.state["running"] = False
    assert client.get("/python/abc/panel/").status_code == 503
    client.state["running"] = True
    client.state["owner"] = "someone-else"
    assert client.get("/python/abc/panel/").status_code == 403
    assert client.get("/python/zzz/panel/").status_code == 403
    client.state["owner"] = "me"
    with open(client.state["file"], "w", encoding="utf-8") as f:
        f.write("print('no header')\n")
    assert client.get("/python/abc/panel/").status_code == 404


def test_upstream_down_gives_a_plain_page(client):
    r = client.get("/python/abc/panel/")
    assert r.status_code == 502 and b"did not answer" in r.data


def test_oversized_command_and_odd_content_type_refused(client, upstream):
    big = client.post("/python/abc/panel/api/cmd", data=b"x" * 5000, headers={"X-QA-Panel": "1", "Content-Type": "application/json"})
    assert big.status_code == 413
    upstream.ctype = "application/octet-stream"
    try:
        assert client.get("/python/abc/panel/api/state").status_code == 502
    finally:
        upstream.ctype = "application/json"


def test_signed_out_visitor_is_refused(monkeypatch, client, upstream):
    import utils.session as us

    monkeypatch.setattr(us, "is_session_valid", lambda: False)
    r = client.get("/python/abc/panel/api/state", headers={"Accept": "application/json"})
    assert r.status_code == 401
