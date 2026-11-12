#!/usr/bin/env bash
# Run ON the VM (Cloud Shell -> gcloud compute ssh qa1 ...) : sudo bash /opt/quant-algo/deploy/verify-vm.sh [--repair]
set -u; N=qa1; D=algo.samirmishra.com; cd /opt/quant-algo
if [ "${1:-}" = "--repair" ]; then git pull --ff-only && QA_NAME=$N QA_DOMAIN=$D bash deploy/node/up.sh; sleep 30; fi
echo "commit: $(git rev-parse --short HEAD)  (expect c346d2c or newer)"
docker ps --format '{{.Names}} {{.Status}}'
echo "app health: $(curl -s -m 10 -o /dev/null -w %{http_code} localhost:5000/auth/check-setup)"
echo "setup via caddy: $(curl -s -m 10 -o /dev/null -w %{http_code} -H "Host: $D" localhost/setup)"
echo "branding: $(curl -s -m 10 -H "Host: $D" localhost/ | grep -c 'QUANT ALGO')"
ls -la /data/$N/db | head; df -h /data | tail -1
echo "LIVE flag in env: $(grep -c '^QA_LIVE_ENABLED' /data/$N/.env)  (0 = disabled)"
docker logs --tail 15 $N-app 2>&1 | tail -15
