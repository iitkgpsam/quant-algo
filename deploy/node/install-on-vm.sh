#!/usr/bin/env bash
# For a member who ALREADY has their own VM (any Debian/Ubuntu, Mumbai preferred, ports 80 and 443 open).
# usage:  sudo QA_DOMAIN=algo.yourdomain.com bash install-on-vm.sh
# Their web address must already point at this VM's public IP; that same IP is what they register at Dhan.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "run with sudo"; exit 1; }
: "${QA_DOMAIN:?set QA_DOMAIN to the web address that points at this VM}"
export QA_NAME="${QA_NAME:-member}" QA_DOMAIN
apt-get update -y
apt-get install -y git curl ca-certificates python3 sqlite3
command -v docker >/dev/null || { curl -fsSL https://get.docker.com | sh; systemctl enable --now docker; }
timedatectl set-timezone Asia/Kolkata || true
[ -d /opt/quant-algo ] || git clone https://github.com/iitkgpsam/quant-algo /opt/quant-algo
cd /opt/quant-algo && git pull --ff-only
bash deploy/node/up.sh
echo "Installed. Open https://$QA_DOMAIN/setup and create your admin password NOW, then switch to Analyzer Mode."
echo "Your server's public IP (register it at Dhan as your static IP): $(curl -fsS https://api.ipify.org || echo 'check your cloud console')"
