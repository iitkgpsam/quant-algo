#!/usr/bin/env python3
"""Idempotent .env preparation. usage: envfix.py <env_file> <sample_file> <domain>
- creates the file from the sample if missing/empty
- replaces ONLY secrets that are still placeholders (existing secrets are never rewritten)
- (re)applies the host/network settings the Caddy-fronted container needs."""
import os, re, secrets, sys
path, sample, domain = sys.argv[1:4]
if not os.path.isfile(path) or os.path.getsize(path) == 0:
    open(path, "w").write(open(sample).read())
txt = open(path).read()

def get(k):
    m = re.search(rf"^{k}\s*=\s*['\"]?([^'\"\n#]*)", txt, re.M)
    return m.group(1).strip() if m else None

def setv(k, v):
    global txt
    line = f"{k} = '{v}'"
    if re.search(rf"^{k}\s*=", txt, re.M):
        txt = re.sub(rf"^{k}\s*=.*$", lambda _: line, txt, count=1, flags=re.M)
    else:
        txt += "\n" + line + "\n"

for k in ("APP_KEY", "API_KEY_PEPPER", "FERNET_SALT"):
    cur = get(k)
    if not cur or "PLACEHOLDER" in cur:
        setv(k, secrets.token_hex(32))
base = f"https://{domain}"
for k, v in {
    "HOST_SERVER": base,
    "FLASK_HOST_IP": "0.0.0.0",          # must listen on the container interface, not loopback
    "WEBSOCKET_HOST": "0.0.0.0",
    "WEBSOCKET_URL": f"wss://{domain}/ws",
    "CORS_ALLOWED_ORIGINS": base,
    "TRUST_PROXY_HEADERS": "TRUE",       # Caddy is the only thing in front
    "FLASK_ENV": "production",
    "FLASK_DEBUG": "False",
}.items():
    setv(k, v)
open(path, "w").write(txt)
