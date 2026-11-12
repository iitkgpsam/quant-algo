#!/usr/bin/env bash
# Nightly app-level backup (in addition to disk snapshots). Cron: 30 18 * * * /opt/quant-algo/deploy/backup-db.sh qa1
set -euo pipefail; N=${1:?}; D=/data/$N/backups; mkdir -p $D
for f in /data/$N/db/*.db; do sqlite3 "$f" ".backup $D/$(basename $f).$(date +%F)"; done
find $D -mtime +14 -delete
