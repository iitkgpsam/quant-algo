"""QUANT ALGO member portal. Open sign-up, owner-only Suspend / Remove, nothing else.
It stores an email, a password hash, a status and the member's own instance address. It never sees a broker key,
a token, a position or a trade: those live only on the member's own instance."""
from __future__ import annotations
import getpass, hashlib, hmac, os, re, secrets, sqlite3, sys, time
from urllib.parse import urlparse
from flask import Flask, Blueprint, abort, g, jsonify, redirect, render_template_string, request, session

PREFIX = os.environ.get("PORTAL_PREFIX", "/join")
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[^@\s]{2,}$")
STATUSES = ("active", "suspended", "removed")
_hits: dict = {}

def _db_path() -> str:
    return os.environ.get("PORTAL_DB", "/data/portal.db")

def db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(_db_path(), timeout=10)
        g.db.row_factory = sqlite3.Row
    return g.db

def init_db(path: str | None = None) -> None:
    con = sqlite3.connect(path or _db_path())
    con.executescript("""CREATE TABLE IF NOT EXISTS members(
        id INTEGER PRIMARY KEY, email TEXT UNIQUE NOT NULL, pw TEXT NOT NULL, created INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'active', is_admin INTEGER NOT NULL DEFAULT 0,
        token_hash TEXT, instance_url TEXT, last_login INTEGER);""")
    con.commit(); con.close()

def hash_pw(pw: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"

def check_pw(pw: str, stored: str) -> bool:
    try:
        _, salt, h = stored.split("$")
        return hmac.compare_digest(hash_pw(pw, bytes.fromhex(salt)), stored)
    except ValueError:
        return False

def limited(key: str, per_min: int = 10) -> bool:
    now = time.time(); q = [t for t in _hits.get(key, []) if now - t < 60]
    q.append(now); _hits[key] = q
    return len(q) > per_min

def valid_instance_url(u: str) -> str | None:
    p = urlparse(u.strip())
    if p.scheme != "https" or not p.hostname or p.username or p.password or len(u) > 200:
        return None
    return f"https://{p.netloc}"

def make_token() -> tuple[str, str]:
    t = secrets.token_urlsafe(32)
    return t, hashlib.sha256(t.encode()).hexdigest()

CSS = "body{font:16px system-ui;max-width:640px;margin:2rem auto;padding:0 1rem;color:#111}input,button{font:inherit;padding:.5rem;margin:.25rem 0}input{width:100%;box-sizing:border-box}button{cursor:pointer}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #ddd;padding:.4rem;text-align:left}.err{color:#b00}.ok{color:#070}code{background:#eee;padding:.1rem .3rem}"
PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>QUANT ALGO</title><style>{{css}}</style>
<h1>QUANT ALGO</h1>{% if msg %}<p class="{{cls}}">{{msg}}</p>{% endif %}{{body|safe}}"""

def page(body: str, msg: str = "", cls: str = "err", status: int = 200):
    return render_template_string(PAGE, css=CSS, body=body, msg=msg, cls=cls), status

def csrf() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]

def csrf_ok() -> bool:
    return hmac.compare_digest(request.form.get("csrf", ""), session.get("csrf", "x"))

def me():
    uid = session.get("uid")
    if not uid:
        return None
    m = db().execute("SELECT * FROM members WHERE id=?", (uid,)).fetchone()
    if not m or m["status"] != "active":
        session.clear(); return None
    return m

def esc(s) -> str:
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))

def create_app() -> Flask:
    app = Flask(__name__)
    os.makedirs(os.path.dirname(_db_path()) or '.', exist_ok=True)
    init_db()
    app.secret_key = os.environ.get("PORTAL_SECRET") or secrets.token_hex(32)
    app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=os.environ.get("PORTAL_INSECURE_COOKIES") != "1", MAX_CONTENT_LENGTH=16384)
    bp = Blueprint("portal", __name__, url_prefix=PREFIX)

    @app.teardown_appcontext
    def _close(_):
        con = g.pop("db", None)
        if con: con.close()

    def forms(c: str) -> str:
        return (f'<h2>Create account</h2><form method=post action="{PREFIX}/signup"><input type=hidden name=csrf value="{c}">'
                '<input name=email type=email placeholder="Your email" required><input name=password type=password placeholder="Password (10+ characters)" minlength=10 required>'
                '<button>Create account</button></form><h2>Log in</h2>'
                f'<form method=post action="{PREFIX}/login"><input type=hidden name=csrf value="{c}">'
                '<input name=email type=email placeholder="Email" required><input name=password type=password placeholder="Password" required><button>Log in</button></form>'
                "<p>Your broker account, keys, data and trades stay on your own instance. This site only keeps your email, status and instance address.</p>")

    @bp.get("/")
    def home():
        m = me()
        return redirect(f"{PREFIX}/me") if m else page(forms(csrf()))

    @bp.post("/signup")
    def signup():
        if not csrf_ok(): abort(400)
        if limited("s:" + (request.remote_addr or "")): return page(forms(csrf()), "Too many attempts. Wait a minute.", status=429)
        email, pw = request.form.get("email", "").strip().lower(), request.form.get("password", "")
        if not EMAIL_RE.match(email): return page(forms(csrf()), "Enter a valid email.", status=400)
        if len(pw) < 10 or len(pw) > 200: return page(forms(csrf()), "Password must be 10 to 200 characters.", status=400)
        try:
            db().execute("INSERT INTO members(email,pw,created) VALUES(?,?,?)", (email, hash_pw(pw), int(time.time()))); db().commit()
        except sqlite3.IntegrityError:
            return page(forms(csrf()), "That email cannot be used. Log in if you already have an account.", status=409)
        row = db().execute("SELECT id FROM members WHERE email=?", (email,)).fetchone()
        session.clear(); session["uid"] = row["id"]; csrf()
        return redirect(f"{PREFIX}/me")

    @bp.post("/login")
    def login():
        if not csrf_ok(): abort(400)
        if limited("l:" + (request.remote_addr or "")): return page(forms(csrf()), "Too many attempts. Wait a minute.", status=429)
        email, pw = request.form.get("email", "").strip().lower(), request.form.get("password", "")
        m = db().execute("SELECT * FROM members WHERE email=?", (email,)).fetchone()
        ok = bool(m) and check_pw(pw, m["pw"])
        if not ok: return page(forms(csrf()), "Wrong email or password.", status=401)
        if m["status"] != "active":
            return page("", "Your access through this website has been stopped by the platform owner.", status=403)
        session.clear(); session["uid"] = m["id"]; csrf()
        db().execute("UPDATE members SET last_login=? WHERE id=?", (int(time.time()), m["id"])); db().commit()
        return redirect(f"{PREFIX}/me")

    @bp.post("/logout")
    def logout():
        if csrf_ok(): session.clear()
        return redirect(f"{PREFIX}/")

    @bp.get("/me")
    def dash():
        m = me()
        if not m: return redirect(f"{PREFIX}/")
        c, url = csrf(), m["instance_url"]
        open_btn = f'<p><a href="{esc(url)}" rel="noopener noreferrer"><b>Open my instance</b></a> ({esc(url)})</p>' if url else "<p>No instance registered yet.</p>"
        body = (f"<p>Signed in as <b>{esc(m['email'])}</b> &middot; status <b>{esc(m['status'])}</b></p>{open_btn}"
                f'<h3>Register your own instance</h3><p>Install on your own server, then enter its https address:<br><code>sudo QA_DOMAIN=your.domain bash install-on-vm.sh</code></p>'
                f'<form method=post action="{PREFIX}/me/instance"><input type=hidden name=csrf value="{c}"><input name=url placeholder="https://your-instance-address" required><button>Save address</button></form>'
                f'<h3>Instance token</h3><p>Optional: lets your instance check that your access here is active. Shown once.</p>'
                f'<form method=post action="{PREFIX}/me/token"><input type=hidden name=csrf value="{c}"><button>Create new token</button></form>'
                f'<form method=post action="{PREFIX}/logout"><input type=hidden name=csrf value="{c}"><button>Log out</button></form>')
        return page(body)

    @bp.post("/me/instance")
    def set_instance():
        m = me()
        if not m or not csrf_ok(): abort(400)
        u = valid_instance_url(request.form.get("url", ""))
        if not u: return page("<p><a href='%s/me'>Back</a></p>" % PREFIX, "Enter a full https:// address.", status=400)
        db().execute("UPDATE members SET instance_url=? WHERE id=?", (u, m["id"])); db().commit()
        return redirect(f"{PREFIX}/me")

    @bp.post("/me/token")
    def new_token():
        m = me()
        if not m or not csrf_ok(): abort(400)
        t, h = make_token()
        db().execute("UPDATE members SET token_hash=? WHERE id=?", (h, m["id"])); db().commit()
        return page(f"<p>Your token (copy it now, it is not shown again):</p><p><code>{esc(t)}</code></p><p><a href='{PREFIX}/me'>Back</a></p>", "Token created.", "ok")

    @bp.get("/api/status")
    def api_status():
        if limited("a:" + (request.remote_addr or ""), 120): return jsonify(status="rate_limited"), 429
        t = request.headers.get("X-QA-Token", "")
        m = db().execute("SELECT status FROM members WHERE token_hash=?", (hashlib.sha256(t.encode()).hexdigest(),)).fetchone() if t else None
        return jsonify(status=m["status"] if m else "unknown")

    def admin_only():
        m = me()
        if not m or not m["is_admin"]: abort(404)
        return m

    @bp.get("/admin")
    def admin():
        admin_only(); c = csrf()
        rows = db().execute("SELECT * FROM members WHERE is_admin=0 ORDER BY id DESC").fetchall()
        tr = "".join(
            f"<tr><td>{esc(r['email'])}</td><td>{esc(r['status'])}</td><td>{esc(time.strftime('%Y-%m-%d', time.gmtime(r['created'])))}</td><td>"
            + "".join(f'<form method=post action="{PREFIX}/admin/{r["id"]}/{a}" style="display:inline"><input type=hidden name=csrf value="{c}"><button>{a.title()}</button></form>'
                      for a in (("suspend", "remove") if r["status"] == "active" else ("activate", "remove") if r["status"] == "suspended" else ()))
            + "</td></tr>" for r in rows)
        return page(f"<h2>Members ({len(rows)})</h2><table><tr><th>Email</th><th>Status</th><th>Joined</th><th></th></tr>{tr}</table>"
                    "<p>You see emails and status only. You cannot see anyone's broker, keys, data or trades.</p>"
                    f'<form method=post action="{PREFIX}/logout"><input type=hidden name=csrf value="{c}"><button>Log out</button></form>')

    @bp.post("/admin/<int:mid>/<action>")
    def admin_act(mid: int, action: str):
        admin_only()
        if not csrf_ok() or action not in ("suspend", "activate", "remove"): abort(400)
        new = {"suspend": "suspended", "activate": "active", "remove": "removed"}[action]
        if action == "remove":   # tombstone keeps the email blocked from signing up again; personal fields are wiped
            db().execute("UPDATE members SET status='removed', instance_url=NULL, token_hash=NULL WHERE id=? AND is_admin=0", (mid,))
        else:
            db().execute("UPDATE members SET status=? WHERE id=? AND is_admin=0 AND status!='removed'", (new, mid))
        db().commit()
        return redirect(f"{PREFIX}/admin")

    @app.get("/healthz")
    def health(): return "ok"
    app.register_blueprint(bp)
    return app

def cli() -> None:
    init_db()
    if len(sys.argv) == 3 and sys.argv[1] == "create-admin":
        pw = getpass.getpass("Admin password (12+ characters): ")
        if len(pw) < 12: sys.exit("too short")
        con = sqlite3.connect(_db_path())
        con.execute("INSERT INTO members(email,pw,created,is_admin) VALUES(?,?,?,1) ON CONFLICT(email) DO UPDATE SET pw=excluded.pw,is_admin=1,status='active'",
                    (sys.argv[2].strip().lower(), hash_pw(pw), int(time.time()))); con.commit(); print("admin ready")
    else:
        sys.exit("usage: portal_app.py create-admin EMAIL")

if __name__ == "__main__":
    cli()
