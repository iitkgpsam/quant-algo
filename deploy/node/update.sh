#!/usr/bin/env bash
# Update YOUR instance to the latest platform code. Keeps your database, keys and settings.
# usage on your VM:  sudo QA_NAME=member QA_DOMAIN=algo.yourdomain.com bash /opt/quant-algo/deploy/node/update.sh
set -euo pipefail
: "${QA_DOMAIN:?}"; export QA_NAME="${QA_NAME:-member}" QA_DOMAIN
cd /opt/quant-algo && git pull --ff-only && bash deploy/node/up.sh
