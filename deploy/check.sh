#!/usr/bin/env bash
# Post-deploy checks: ./deploy/check.sh https://algo.samirmishra.com
set -u; U=${1:?}; ok=0
chk(){ if eval "$2" >/dev/null 2>&1; then echo "PASS $1"; else echo "FAIL $1"; ok=1; fi; }
chk "https reachable"      "curl -fsS -m 10 $U/auth/check-setup"
chk "tls valid"            "curl -fsS -m 10 -o /dev/null $U/"
chk "no http->https gap"   "curl -fsSI -m 10 http://${U#https://} | grep -qi 'location: https'"
chk "branding present"     "curl -fsS -m 10 $U/ | grep -q 'QUANT ALGO'"
chk "secrets not exposed"  "! curl -fsS -m 10 $U/.env"
exit $ok
