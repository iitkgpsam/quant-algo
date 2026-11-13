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

LOGO = ('<svg viewBox="0 0 512 512" width="40" height="40" aria-hidden="true"><rect width="512" height="512" rx="96" fill="#0b1f3a"/>'
        '<path d="M96 352 L192 240 L272 300 L416 140" fill="none" stroke="#22c55e" stroke-width="36" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="416" cy="140" r="26" fill="#22c55e"/><text x="256" y="452" font-family="Arial,sans-serif" font-weight="700" font-size="76" fill="#fff" text-anchor="middle">QA</text></svg>')
CSS = """
:root{--bg:#f4f6fa;--card:#fff;--ink:#0f172a;--muted:#5b6478;--line:#e3e7ef;--brand:#0b1f3a;--accent:#16a34a;--accent-ink:#fff;--warn:#b45309;--bad:#b91c1c;--field:#fff;--shadow:0 10px 30px rgba(11,31,58,.08)}
@media (prefers-color-scheme:dark){:root{--bg:#0a1220;--card:#101a2e;--ink:#e8edf7;--muted:#9aa6bd;--line:#1f2b44;--brand:#e8edf7;--accent:#22c55e;--accent-ink:#04200f;--warn:#f59e0b;--bad:#f87171;--field:#0b1424;--shadow:none}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:radial-gradient(900px 420px at 50% -120px,rgba(34,197,94,.14),transparent),var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;min-height:100vh;display:flex;flex-direction:column}
a{color:inherit}header,main,footer{width:100%;max-width:460px;margin:0 auto;padding:0 20px}
header{display:flex;align-items:center;gap:12px;padding-top:28px}header b{font-size:1.25rem;letter-spacing:.02em;color:var(--brand)}
.hero{padding:26px 0 8px}.hero h1{margin:0 0 8px;font-size:1.75rem;line-height:1.2;color:var(--brand)}.hero p{margin:0;color:var(--muted)}
.card{background:var(--card);border:1px solid var(--line);border-radius:18px;padding:20px;margin:18px 0;box-shadow:var(--shadow)}
.tabr{position:absolute;left:0;top:0;width:1px;min-height:0;height:1px;padding:0;border:0;opacity:0;pointer-events:none}.tabs{display:grid;grid-template-columns:1fr 1fr;background:var(--bg);border-radius:12px;padding:4px;margin-bottom:16px}
.tabs label{text-align:center;padding:10px;border-radius:9px;font-weight:600;color:var(--muted);cursor:pointer}
#t-signup:checked~.tabs label[for=t-signup],#t-login:checked~.tabs label[for=t-login]{background:var(--card);color:var(--ink);box-shadow:0 1px 4px rgba(0,0,0,.12)}
.pane{display:none}#t-signup:checked~.panes .p-signup,#t-login:checked~.panes .p-login{display:block}
.tabr:focus-visible~.tabs{outline:2px solid var(--accent);outline-offset:2px}
label.f{display:block;font-size:.85rem;font-weight:600;color:var(--muted);margin:14px 0 6px}
.pw{position:relative}.pw button{position:absolute;right:6px;top:50%;transform:translateY(-50%);margin:0;width:auto;min-height:36px;padding:0 10px;background:none;border:0;color:var(--muted);font-weight:600;font-size:.85rem}
input{width:100%;min-height:48px;padding:12px 14px;font:inherit;color:var(--ink);background:var(--field);border:1px solid var(--line);border-radius:12px}
input:focus{outline:2px solid var(--accent);outline-offset:1px;border-color:transparent}
button,.btn{display:inline-flex;align-items:center;justify-content:center;width:100%;min-height:48px;margin-top:18px;padding:0 18px;font:inherit;font-weight:700;color:var(--accent-ink);background:var(--accent);border:0;border-radius:12px;cursor:pointer;text-decoration:none}
button:hover,.btn:hover{filter:brightness(1.07)}button.ghost,.btn.ghost{background:transparent;color:var(--ink);border:1px solid var(--line)}
.msg{padding:12px 14px;border-radius:12px;margin:18px 0 0;font-size:.95rem;border:1px solid}.msg.err{color:var(--bad);border-color:currentColor;background:rgba(185,28,28,.07)}.msg.ok{color:var(--accent);border-color:currentColor;background:rgba(34,197,94,.09)}
.trust{list-style:none;margin:6px 0 0;padding:0;display:grid;gap:12px}.trust li{display:flex;gap:12px;align-items:flex-start;color:var(--muted);font-size:.93rem}
.trust i{flex:none;width:28px;height:28px;border-radius:9px;background:rgba(34,197,94,.14);color:var(--accent);display:grid;place-items:center;font-style:normal;font-weight:700}
.badge{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.8rem;font-weight:700;border:1px solid var(--line);color:var(--muted)}
.badge.active{color:var(--accent);border-color:var(--accent)}.badge.suspended{color:var(--warn);border-color:var(--warn)}.badge.removed{color:var(--bad);border-color:var(--bad)}
h2{margin:0 0 4px;font-size:1.15rem;color:var(--brand)}h3{margin:0 0 6px;font-size:1rem}p.s{margin:4px 0 0;color:var(--muted);font-size:.93rem}
code{display:inline-block;max-width:100%;background:var(--bg);border:1px solid var(--line);padding:6px 8px;border-radius:8px;font-size:.85rem;white-space:pre-wrap;word-break:break-all}
details summary{cursor:pointer;font-weight:600}.row{display:flex;gap:8px}.row form{flex:1}.row button{margin-top:8px}
.who{display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap}
table{width:100%;border-collapse:collapse;font-size:.92rem}td,th{text-align:left;padding:10px 6px;border-bottom:1px solid var(--line);vertical-align:middle}th{color:var(--muted);font-weight:600;font-size:.8rem}
td form{display:inline}td button{width:auto;min-height:36px;margin:2px 4px 2px 0;padding:0 12px;font-size:.85rem}button.warn{background:var(--warn);color:#fff}button.danger{background:var(--bad);color:#fff}
@media (max-width:560px){table,thead,tbody,tr,td{display:block}thead{display:none}tr{padding:10px 0;border-bottom:1px solid var(--line)}td{border:0;padding:3px 0}}
footer{padding:8px 20px 28px;margin-top:auto;color:var(--muted);font-size:.82rem;text-align:center}footer a{text-decoration:underline}
@media (min-width:760px){header,main,footer{max-width:520px}.hero h1{font-size:2rem}}
"""
PAGE = """<!doctype html><html lang=en><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><meta name=color-scheme content="light dark">
<title>QUANT ALGO</title><link rel=icon href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'%3E%3Crect width='512' height='512' rx='96' fill='%230b1f3a'/%3E%3Cpath d='M96 352 L192 240 L272 300 L416 140' fill='none' stroke='%2322c55e' stroke-width='36' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<style>{{css}}</style><header>{{logo|safe}}<b>QUANT ALGO</b></header>
<main>{% if hero %}<section class=hero><h1>Algo trading on your own terms.</h1><p>Create your account, connect your own broker, practise in Analyzer mode, then trade. Your server. Your keys. Your data.</p></section>{% endif %}
{% if msg %}<div class="msg {{cls}}" role=alert>{{msg}}</div>{% endif %}{{body|safe}}</main>
<footer>QUANT ALGO &middot; <a href="https://github.com/iitkgpsam/quant-algo" rel=noopener>Source (AGPL-3.0)</a> &middot; Based on <a href="https://github.com/marketcalls/openalgo" rel=noopener>OpenAlgo</a></footer>
<script>document.querySelectorAll('[data-show]').forEach(function(b){b.addEventListener('click',function(){var i=document.getElementById(b.dataset.show);var h=i.type==='password';i.type=h?'text':'password';b.textContent=h?'Hide':'Show'})});
document.querySelectorAll('[data-confirm]').forEach(function(f){f.addEventListener('submit',function(e){if(!confirm(f.dataset.confirm))e.preventDefault()})})</script>"""

def page(body: str, msg: str = "", cls: str = "err", status: int = 200, hero: bool = False):
    return render_template_string(PAGE, css=CSS, logo=LOGO, body=body, msg=msg, cls=cls, hero=hero), status

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

    def forms(c: str, tab: str = "signup") -> str:
        def pw(i: str, name: str, ph: str, auto: str, extra: str = "") -> str:
            return (f'<div class=pw><input id="{i}" name={name} type=password placeholder="{ph}" autocomplete="{auto}" {extra} required>'
                    f'<button type=button data-show="{i}" aria-label="Show password">Show</button></div>')
        sg, lg = ("checked", "") if tab == "signup" else ("", "checked")
        return (f'<div class=card><input class=tabr type=radio name=tab id=t-signup {sg}><input class=tabr type=radio name=tab id=t-login {lg}>'
                '<div class=tabs><label for=t-signup>Create account</label><label for=t-login>Log in</label></div><div class=panes>'
                f'<div class="pane p-signup"><form method=post action="{PREFIX}/signup"><input type=hidden name=csrf value="{c}">'
                '<label class=f for=se>Email</label><input id=se name=email type=email inputmode=email autocomplete=email placeholder="you@example.com" required>'
                '<label class=f for=sp>Password</label>' + pw("sp", "password", "At least 10 characters", "new-password", "minlength=10") +
                '<button>Create my account</button></form></div>'
                f'<div class="pane p-login"><form method=post action="{PREFIX}/login"><input type=hidden name=csrf value="{c}">'
                '<label class=f for=le>Email</label><input id=le name=email type=email inputmode=email autocomplete=email placeholder="you@example.com" required>'
                '<label class=f for=lp>Password</label>' + pw("lp", "password", "Your password", "current-password") +
                '<button>Log in</button></form></div></div></div>'
                '<div class=card><ul class=trust>'
                '<li><i>&#10003;</i><span><b>Your keys stay yours.</b> Broker keys, orders and data live only on your own server.</span></li>'
                '<li><i>&#10003;</i><span><b>Practise first.</b> Analyzer mode lets you paper trade before any real order.</span></li>'
                '<li><i>&#10003;</i><span><b>Private.</b> This site keeps only your email, status and instance address.</span></li></ul></div>')

    @bp.get("/")
    def home():
        m = me()
        return redirect(f"{PREFIX}/me") if m else page(forms(csrf()), hero=True)

    @bp.post("/signup")
    def signup():
        if not csrf_ok(): abort(400)
        if limited("s:" + (request.remote_addr or "")): return page(forms(csrf()), "Too many attempts. Wait a minute.", status=429, hero=True)
        email, pw = request.form.get("email", "").strip().lower(), request.form.get("password", "")
        if not EMAIL_RE.match(email): return page(forms(csrf()), "Enter a valid email.", status=400, hero=True)
        if len(pw) < 10 or len(pw) > 200: return page(forms(csrf()), "Password must be 10 to 200 characters.", status=400, hero=True)
        try:
            db().execute("INSERT INTO members(email,pw,created) VALUES(?,?,?)", (email, hash_pw(pw), int(time.time()))); db().commit()
        except sqlite3.IntegrityError:
            return page(forms(csrf(), "login"), "That email cannot be used. Log in if you already have an account.", status=409, hero=True)
        row = db().execute("SELECT id FROM members WHERE email=?", (email,)).fetchone()
        session.clear(); session["uid"] = row["id"]; csrf()
        return redirect(f"{PREFIX}/me")

    @bp.post("/login")
    def login():
        if not csrf_ok(): abort(400)
        if limited("l:" + (request.remote_addr or "")): return page(forms(csrf(), "login"), "Too many attempts. Wait a minute.", status=429, hero=True)
        email, pw = request.form.get("email", "").strip().lower(), request.form.get("password", "")
        m = db().execute("SELECT * FROM members WHERE email=?", (email,)).fetchone()
        ok = bool(m) and check_pw(pw, m["pw"])
        if not ok: return page(forms(csrf(), "login"), "Wrong email or password.", status=401, hero=True)
        if m["status"] != "active":
            return page("<div class=card><h2>Access stopped</h2><p class=s>The platform owner has stopped your access through this website. Your own server and data are not affected.</p></div>", status=403)
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
        hello = f'<section class=hero><h1>Welcome</h1><div class=who><span>{esc(m["email"])}</span><span class="badge {esc(m["status"])}">{esc(m["status"])}</span></div></section>'
        inst = (f'<div class=card><h2>Your instance</h2><p class=s>{esc(url)}</p><a class=btn href="{esc(url)}" rel="noopener noreferrer">Open my instance</a></div>'
                if url else '<div class=card><h2>Your instance</h2><p class=s>You have not registered a server yet. Follow the steps below.</p></div>')
        steps = ('<div class=card><h2>Set up your own server</h2><p class=s>Your instance runs on your own VM, with your own broker. On a fresh Debian or Ubuntu VM with ports 80 and 443 open, '
                 'and your web address pointing at it, run:</p><p><code>sudo QA_DOMAIN=your.address bash install-on-vm.sh</code></p>'
                 f'<form method=post action="{PREFIX}/me/instance"><input type=hidden name=csrf value="{c}"><label class=f for=iu>Your instance address</label>'
                 '<input id=iu name=url type=url inputmode=url placeholder="https://your.address" required><button>Save address</button></form></div>')
        tok = (f'<div class=card><details><summary>Instance token (optional)</summary><p class=s>Lets your instance check that your access here is active. Shown once.</p>'
               f'<form method=post action="{PREFIX}/me/token"><input type=hidden name=csrf value="{c}"><button class=ghost>Create new token</button></form></details></div>')
        out = f'<div class=card><form method=post action="{PREFIX}/logout"><input type=hidden name=csrf value="{c}"><button class=ghost style="margin-top:0">Log out</button></form></div>'
        return page(hello + inst + steps + tok + out)

    @bp.post("/me/instance")
    def set_instance():
        m = me()
        if not m or not csrf_ok(): abort(400)
        u = valid_instance_url(request.form.get("url", ""))
        if not u: return page(f"<div class=card><a class='btn ghost' style='margin-top:0' href='{PREFIX}/me'>Back</a></div>", "Enter a full https:// address.", status=400)
        db().execute("UPDATE members SET instance_url=? WHERE id=?", (u, m["id"])); db().commit()
        return redirect(f"{PREFIX}/me")

    @bp.post("/me/token")
    def new_token():
        m = me()
        if not m or not csrf_ok(): abort(400)
        t, h = make_token()
        db().execute("UPDATE members SET token_hash=? WHERE id=?", (h, m["id"])); db().commit()
        return page(f"<div class=card><h2>Your token</h2><p class=s>Copy it now. It is not shown again.</p><p><code>{esc(t)}</code></p><a class='btn ghost' href='{PREFIX}/me'>Back</a></div>", "Token created.", "ok")

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
        def btn(r, a):
            cls = {"suspend": "warn", "remove": "danger", "activate": ""}[a]
            ask = {"suspend": "Suspend this person? They will lose access through this website.", "remove": "Remove this person? Their address is wiped and the email is blocked from signing up again.", "activate": ""}[a]
            conf = f' data-confirm="{ask}"' if ask else ""
            return f'<form method=post action="{PREFIX}/admin/{r["id"]}/{a}"{conf}><input type=hidden name=csrf value="{c}"><button class="{cls}">{a.title()}</button></form>'
        tr = "".join(
            f"<tr><td><b>{esc(r['email'])}</b></td><td><span class='badge {esc(r['status'])}'>{esc(r['status'])}</span></td><td>{esc(time.strftime('%d %b %Y', time.gmtime(r['created'])))}</td><td>"
            + "".join(btn(r, a) for a in (("suspend", "remove") if r["status"] == "active" else ("activate", "remove") if r["status"] == "suspended" else ()))
            + "</td></tr>" for r in rows)
        empty = "<p class=s>No one has joined yet.</p>" if not rows else ""
        return page(f"<section class=hero><h1>Members</h1><p>{len(rows)} in total</p></section><div class=card>{empty}<table><thead><tr><th>Email</th><th>Status</th><th>Joined</th><th></th></tr></thead><tbody>{tr}</tbody></table></div>"
                    "<div class=card><p class=s>You see emails and status only. You cannot see anyone's broker, keys, data or trades.</p></div>"
                    f'<div class=card><form method=post action="{PREFIX}/logout"><input type=hidden name=csrf value="{c}"><button class=ghost style="margin-top:0">Log out</button></form></div>')

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
