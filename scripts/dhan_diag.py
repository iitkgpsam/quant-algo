#!/usr/bin/env python3
"""Safe Dhan credential diagnostic. Prints shapes/matches only, never values.
Run inside the app container:  docker exec qa1-app python /app/scripts/dhan_diag.py [--call]
--call makes ONE generate-consent request (no login completed, no order)."""
import os, sys

def shape(raw_key: str, raw_secret: str) -> dict:
    ws = lambda s: s != s.strip() or any(c in s for c in "\r\n\t \"'")
    d = {"key_parts(:::)": raw_key.count(":::") + 1 if raw_key else 0,
         "key_has_whitespace_or_quote": ws(raw_key), "secret_has_whitespace_or_quote": ws(raw_secret),
         "secret_empty": not raw_secret.strip()}
    if ":::" in raw_key:
        cid, api = (p.strip() for p in raw_key.split(":::", 1))
        d.update({"client_id_len": len(cid), "client_id_numeric": cid.isdigit(),
                  "api_key_len": len(api), "api_key_empty": not api,
                  "api_key_contains_colons": ":" in api,
                  "api_key_equals_client_id": api == cid,
                  "secret_equals_api_key": raw_secret.strip() == api,
                  "secret_len": len(raw_secret.strip())})
    return d

def main():
    from dotenv import load_dotenv
    load_dotenv("/app/.env")
    sys.path.insert(0, "/app")
    from utils.broker_keys import resolve
    k = resolve("dhan")
    if not k:
        print("NO Dhan keys found (neither .env nor saved)"); return 1
    print("source:", k.source)
    key, sec = k.api_key or "", k.api_secret or ""
    for a, b in shape(key, sec).items(): print(f"  {a}: {b}")
    if "--call" in sys.argv and ":::" in key:
        import httpx
        cid, api = (p.strip() for p in key.split(":::", 1))
        r = httpx.post("https://auth.dhan.co/app/generate-consent", params={"client_id": cid},
                       headers={"app_id": api, "app_secret": sec.strip()}, timeout=20)
        body = r.text
        for v in (api, sec.strip(), cid):
            body = body.replace(v, "<redacted>") if v else body
        try: j = r.json(); ok = j.get("status")
        except Exception: j, ok = {}, None
        print("generate-consent HTTP", r.status_code, "| status:", ok, "| consent_id_returned:", bool(j.get("consentAppId")))
        if r.status_code != 200 or ok != "success":
            print("Dhan says:", body[:300])
    return 0

if __name__ == "__main__":
    sys.exit(main())
