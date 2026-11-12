#!/usr/bin/env python3
"""Owner-only approval tool: approve a member (issue a signed, expiring token) and remove one (revoke it).
Runs on YOUR server (qa1). The private key never leaves it. Needs: apt-get install -y python3-cryptography
  sudo python3 qa_license.py init
  sudo python3 qa_license.py issue --member alice --days 30 [--index NIFTY|SENSEX|*]
  sudo python3 qa_license.py revoke --member alice          (or --id <token id>)
  sudo python3 qa_license.py list
Revocations are published at https://<your domain>/qa-revoked.json (served by Caddy from the same folder).
Honest limit: this controls the strategy file you distribute. It cannot stop someone running open-source
platform code on their own server, and a member who edits their copy of the file can remove the check."""
import argparse, base64, json, os, sys, time, uuid

DIR = os.environ.get("QA_LICENSE_DIR", "/data/qa1/license")
b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()
unb64 = lambda s: base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

def _crypto():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        from cryptography.hazmat.primitives import serialization
        return Ed25519PrivateKey, serialization
    except ImportError:
        sys.exit("python3-cryptography is missing: sudo apt-get install -y python3-cryptography")

def _path(n): return os.path.join(DIR, n)
def _load(n, default):
    try:
        with open(_path(n), encoding="utf-8") as f: return json.load(f)
    except (OSError, ValueError): return default
def _save(n, data):
    os.makedirs(DIR, exist_ok=True)
    tmp = _path(n) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f: json.dump(data, f)
    os.replace(tmp, _path(n)); os.chmod(_path(n), 0o644 if n == "revoked.json" else 0o600)

def _priv():
    Priv, ser = _crypto()
    try:
        with open(_path("private.pem"), "rb") as f: return ser.load_pem_private_key(f.read(), None), ser
    except OSError: sys.exit("not initialised: run  init  first")

def cmd_init(a):
    Priv, ser = _crypto()
    os.makedirs(DIR, exist_ok=True)
    if os.path.exists(_path("private.pem")):
        print("already initialised (private key kept)")
    else:
        k = Priv.generate()
        pem = k.private_bytes(ser.Encoding.PEM, ser.PrivateFormat.PKCS8, ser.NoEncryption())
        fd = os.open(_path("private.pem"), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as f: f.write(pem)
        _save("revoked.json", {"revoked": [], "updated": int(time.time())})
    k, ser = _priv()
    pub = k.public_key().public_bytes(ser.Encoding.Raw, ser.PublicFormat.Raw)
    print("PUBLIC KEY (put this in LICENSE_PUBKEY inside the strategy file you send out):\n" + b64(pub))

def cmd_issue(a):
    k, _ = _priv()
    payload = {"v": 1, "id": uuid.uuid4().hex[:12], "member": a.member, "index": a.index, "iat": int(time.time()),
               "exp": int(time.time() + a.days * 86400)}
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    token = b64(raw) + "." + b64(k.sign(raw))
    issued = _load("issued.json", []); issued.append(payload); _save("issued.json", issued)
    print(f"APPROVED {a.member} until {time.strftime('%Y-%m-%d', time.gmtime(payload['exp']))} (id {payload['id']})")
    print("Give this token to the member (they paste it into LICENSE_TOKEN):\n" + token)

def cmd_revoke(a):
    issued = _load("issued.json", [])
    ids = [i["id"] for i in issued if (a.id and i["id"] == a.id) or (a.member and i["member"] == a.member)]
    if not ids: sys.exit("no such member / id")
    r = _load("revoked.json", {"revoked": []})
    r["revoked"] = sorted(set(r["revoked"]) | set(ids)); r["updated"] = int(time.time())
    _save("revoked.json", r)
    print(f"REMOVED: revoked {len(ids)} token(s). Their strategy stops within ~10 minutes of its next check.")

def cmd_list(a):
    rev = set(_load("revoked.json", {"revoked": []})["revoked"]); now = time.time()
    for i in _load("issued.json", []):
        st = "REMOVED" if i["id"] in rev else "EXPIRED" if i["exp"] < now else "APPROVED"
        print(f"{st:9} {i['member']:16} {i['index']:7} id={i['id']} expires={time.strftime('%Y-%m-%d', time.gmtime(i['exp']))}")

if __name__ == "__main__":
    p = argparse.ArgumentParser(); s = p.add_subparsers(dest="c", required=True)
    s.add_parser("init").set_defaults(f=cmd_init); s.add_parser("list").set_defaults(f=cmd_list)
    i = s.add_parser("issue"); i.add_argument("--member", required=True); i.add_argument("--days", type=int, default=30)
    i.add_argument("--index", default="*", choices=["*", "NIFTY", "SENSEX"]); i.set_defaults(f=cmd_issue)
    r = s.add_parser("revoke"); r.add_argument("--member"); r.add_argument("--id"); r.set_defaults(f=cmd_revoke)
    a = p.parse_args(); a.f(a)
