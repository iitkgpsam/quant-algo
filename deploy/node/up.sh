#!/usr/bin/env bash
# Brings up one isolated instance: own .env (generated secrets), own DB/log/keys volumes under /data/$QA_NAME.
set -euo pipefail
: "${QA_NAME:?}" "${QA_DOMAIN:?}"
ROOT=/data/$QA_NAME; mkdir -p "$ROOT"/{db,log,strategies,keys,caddy}
cd "$(dirname "$0")/../.."
if [ ! -f "$ROOT/.env" ]; then
  cp .sample.env "$ROOT/.env"
  gen() { python3 -c 'import secrets;print(secrets.token_hex(32))'; }
  sed -i "s|^APP_KEY = .*|APP_KEY = '$(gen)'|; s|^API_KEY_PEPPER = .*|API_KEY_PEPPER = '$(gen)'|; s|^FERNET_SALT = .*|FERNET_SALT = '$(gen)'|" "$ROOT/.env"
  sed -i "s|^HOST_SERVER = .*|HOST_SERVER = 'https://$QA_DOMAIN'|" "$ROOT/.env"
  # Broker creds (BROKER_API_KEY/SECRET for Dhan) are added by the owner on the VM, never committed.
  chmod 600 "$ROOT/.env"
fi
export QA_NAME QA_DOMAIN QA_ROOT=$ROOT
docker compose -p "$QA_NAME" -f deploy/node/docker-compose.yaml up -d --build
