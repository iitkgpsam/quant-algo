#!/usr/bin/env bash
# Runs as root on every boot. Idempotent. Mounts data disk, installs docker, deploys from GitHub.
set -euo pipefail
md() { curl -fs -H 'Metadata-Flavor: Google' "http://metadata.google.internal/computeMetadata/v1/instance/attributes/$1"; }
NAME=$(md qa-name); DOMAIN=$(md qa-domain)
if ! blkid /dev/disk/by-id/google-data >/dev/null 2>&1; then mkfs.ext4 -F /dev/disk/by-id/google-data; fi
mkdir -p /data; grep -q google-data /etc/fstab || echo '/dev/disk/by-id/google-data /data ext4 defaults,nofail 0 2' >> /etc/fstab
mount -a
command -v docker >/dev/null || { apt-get update -y; apt-get install -y docker.io docker-compose git curl; systemctl enable --now docker; }
timedatectl set-timezone Asia/Kolkata
[ -d /opt/quant-algo ] || git clone https://github.com/iitkgpsam/quant-algo /opt/quant-algo   # repo must be public (AGPL) or use deploy key
cd /opt/quant-algo && git pull --ff-only
QA_NAME="$NAME" QA_DOMAIN="$DOMAIN" bash deploy/node/up.sh
