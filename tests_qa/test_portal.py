import hashlib, importlib, os, re, sqlite3, sys, time
import pytest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "portal"))

@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTAL_DB", str(tmp_path / "p.db")); monkeypatch.setenv("PORTAL_INSECURE_COOKIES", "1")
    import portal_app as portal; importlib.reload(portal); portal._hits.clear(); portal.init_db()
    return portal, portal.create_app()

def tok(c, path="/join/"):
    return re.search(r'name=csrf value="([0-9a-f]+)"', c.get(path).get_data(as_text=True)).group(1)

def signup(c, email="a@x.com", pw="correct horse 1"):
    return c.post("/join/signup", data={"csrf": tok(c), "email": email, "password": pw})

def test_open_signup_no_approval_and_dashboard(env):
    _, app = env; c = app.test_client()
    assert signup(c).status_code == 302
    assert "a@x.com" in c.get("/join/me").get_data(as_text=True)

def test_bad_inputs_and_duplicate(env):
    _, app = env; c = app.test_client()
    assert signup(c, "nope").status_code == 400
    assert signup(c, pw="short").status_code == 400
    assert signup(c).status_code == 302
    assert signup(app.test_client()).status_code == 409

def test_csrf_required(env):
    _, app = env
    assert app.test_client().post("/join/signup", data={"email": "a@x.com", "password": "correct horse 1"}).status_code == 400

def test_password_is_hashed_not_stored(env):
    portal, app = env; signup(app.test_client())
    pw = sqlite3.connect(os.environ["PORTAL_DB"]).execute("select pw from members").fetchone()[0]
    assert pw.startswith("scrypt$") and "correct horse" not in pw

def test_login_wrong_password(env):
    _, app = env; signup(app.test_client()); c = app.test_client()
    assert c.post("/join/login", data={"csrf": tok(c), "email": "a@x.com", "password": "wrong wrong 1"}).status_code == 401

def _admin(portal, app):
    con = sqlite3.connect(os.environ["PORTAL_DB"])
    con.execute("insert into members(email,pw,created,is_admin) values('boss@x.com',?,?,1)", (portal.hash_pw("boss password 1"), int(time.time()))); con.commit()
    c = app.test_client(); c.post("/join/login", data={"csrf": tok(c), "email": "boss@x.com", "password": "boss password 1"}); return c

def test_admin_page_hidden_from_members_and_visitors(env):
    portal, app = env; c = app.test_client(); signup(c)
    assert c.get("/join/admin").status_code == 404 and app.test_client().get("/join/admin").status_code == 404

def test_owner_can_suspend_member_who_then_cannot_log_in_and_status_api_says_so(env):
    portal, app = env; m = app.test_client(); signup(m)
    t, h = portal.make_token()
    sqlite3.connect(os.environ["PORTAL_DB"]).execute("update members set token_hash=? where email='a@x.com'", (h,)).connection.commit()
    assert m.get("/join/api/status", headers={"X-QA-Token": t}).get_json()["status"] == "active"
    adm = _admin(portal, app); mid = sqlite3.connect(os.environ["PORTAL_DB"]).execute("select id from members where email='a@x.com'").fetchone()[0]
    assert adm.post(f"/join/admin/{mid}/suspend", data={"csrf": tok(adm, "/join/admin")}).status_code == 302
    assert app.test_client().get("/join/api/status", headers={"X-QA-Token": t}).get_json()["status"] == "suspended"
    assert m.get("/join/me").status_code == 302                                   # existing session ends
    c = app.test_client(); assert c.post("/join/login", data={"csrf": tok(c), "email": "a@x.com", "password": "correct horse 1"}).status_code == 403
    adm.post(f"/join/admin/{mid}/activate", data={"csrf": tok(adm, "/join/admin")})
    c = app.test_client(); assert c.post("/join/login", data={"csrf": tok(c), "email": "a@x.com", "password": "correct horse 1"}).status_code == 302

def test_remove_wipes_data_and_blocks_resignup(env):
    portal, app = env; m = app.test_client(); signup(m)
    m.post("/join/me/instance", data={"csrf": tok(m, "/join/me"), "url": "https://my.vm.example"})
    adm = _admin(portal, app); mid = sqlite3.connect(os.environ["PORTAL_DB"]).execute("select id from members where email='a@x.com'").fetchone()[0]
    adm.post(f"/join/admin/{mid}/remove", data={"csrf": tok(adm, "/join/admin")})
    row = sqlite3.connect(os.environ["PORTAL_DB"]).execute("select status,instance_url,token_hash from members where id=?", (mid,)).fetchone()
    assert row == ("removed", None, None)
    assert signup(app.test_client()).status_code == 409
    adm.post(f"/join/admin/{mid}/activate", data={"csrf": tok(adm, "/join/admin")})   # a removed member cannot be re-activated by accident
    assert sqlite3.connect(os.environ["PORTAL_DB"]).execute("select status from members where id=?", (mid,)).fetchone()[0] == "removed"

def test_instance_url_must_be_https_and_clean(env):
    portal, _ = env
    assert portal.valid_instance_url("https://a.b.com") == "https://a.b.com"
    for bad in ("http://a.b.com", "javascript:alert(1)", "https://u:p@a.b.com", "ftp://x", "", "https://"):
        assert portal.valid_instance_url(bad) is None

def test_token_shown_once_and_stored_hashed(env):
    portal, app = env; c = app.test_client(); signup(c)
    html = c.post("/join/me/token", data={"csrf": tok(c, "/join/me")}).get_data(as_text=True)
    t = re.search(r"<code>([\w-]+)</code>", html).group(1)
    stored = sqlite3.connect(os.environ["PORTAL_DB"]).execute("select token_hash from members").fetchone()[0]
    assert stored == hashlib.sha256(t.encode()).hexdigest() and t not in stored

def test_html_in_email_is_escaped_on_admin_page(env):
    portal, app = env
    con = sqlite3.connect(os.environ["PORTAL_DB"]); con.execute("insert into members(email,pw,created) values(?,?,?)", ("<b>x</b>@a.com", "x", 1)); con.commit()
    html = _admin(portal, app).get("/join/admin").get_data(as_text=True)
    assert "<b>x</b>" not in html and "&lt;b&gt;" in html

def test_rate_limit_on_login(env):
    _, app = env; c = app.test_client(); t = tok(c); codes = []
    for _ in range(13): codes.append(c.post("/join/login", data={"csrf": t, "email": "a@x.com", "password": "x"}).status_code)
    assert 429 in codes
