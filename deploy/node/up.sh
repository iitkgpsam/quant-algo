#!/usr/bin/env bash
# Idempotent. Prepares persistent dirs + a valid .env for ONE isolated instance, then (re)starts it.
# Never overwrites existing secrets or databases.   usage: QA_NAME=qa1 QA_DOMAIN=algo.example.com bash up.sh
set -euo pipefail
: "${QA_NAME:?}" "${QA_DOMAIN:?}"
ROOT=/data/$QA_NAME
cd "$(dirname "$0")/../.."
mkdir -p "$ROOT"/{db,log,strategies,keys,tmp,caddy,backups,license}
[ -d "$ROOT/.env" ] && rmdir "$ROOT/.env"          # Docker makes a directory if the file was missing at first start
python3 deploy/node/envfix.py "$ROOT/.env" .sample.env "$QA_DOMAIN"
# The container runs as uid/gid 1000 (appuser): it must be able to read AND rewrite .env and write the data dirs.
chown 1000:1000 "$ROOT/.env"; chmod 600 "$ROOT/.env"
chown -R 1000:1000 "$ROOT"/{db,log,strategies,keys,tmp}
# Root-only copy of the three secrets: losing them makes encrypted broker tokens unrecoverable.
[ -f "$ROOT/backups/secrets.env" ] || { grep -E '^(APP_KEY|API_KEY_PEPPER|FERNET_SALT)' "$ROOT/.env" > "$ROOT/backups/secrets.env"; chmod 600 "$ROOT/backups/secrets.env"; }
export QA_NAME QA_DOMAIN QA_ROOT=$ROOT
docker compose -p "$QA_NAME" -f deploy/node/docker-compose.yaml up -d --build
