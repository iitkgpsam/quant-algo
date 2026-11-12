#!/usr/bin/env bash
# Usage: deploy/gcp/bootstrap.sh qa1     (provision ONE instance; run qa2/qa3 only after qa1 validated)
# Requires: gcloud authenticated as the owner. Idempotent where possible.
set -euo pipefail
cd "$(dirname "$0")/.."; source instances.env
NAME="${1:?instance name e.g. qa1}"
DOMAIN=""; for i in $INSTANCES; do if [[ ${i%%:*} == "$NAME" ]]; then DOMAIN="${i#*:}"; fi; done
[[ -n "$DOMAIN" ]] || { echo "unknown instance $NAME"; exit 1; }

gcloud projects describe "$PROJECT_ID" >/dev/null 2>&1 || {
  gcloud projects create "$PROJECT_ID" --name="QUANT ALGO"
  gcloud billing projects link "$PROJECT_ID" --billing-account="$BILLING_ACCOUNT"; }
gcloud config set project "$PROJECT_ID"
gcloud services enable compute.googleapis.com iap.googleapis.com

# Reserved static external IP = the outbound IP seen by the broker (no Cloud NAT used). Whitelist this in Dhan.
gcloud compute addresses describe "$NAME-ip" --region="$REGION" >/dev/null 2>&1 || \
  gcloud compute addresses create "$NAME-ip" --region="$REGION"
IP=$(gcloud compute addresses describe "$NAME-ip" --region="$REGION" --format='value(address)')

# Firewall: web only; SSH through IAP only (no public 22).
gcloud compute firewall-rules describe qa-web >/dev/null 2>&1 || \
  gcloud compute firewall-rules create qa-web --allow=tcp:80,tcp:443 --target-tags=qa-web
gcloud compute firewall-rules describe qa-iap-ssh >/dev/null 2>&1 || \
  gcloud compute firewall-rules create qa-iap-ssh --allow=tcp:22 --source-ranges=35.235.240.0/20 --target-tags=qa-web

gcloud compute disks describe "$NAME-data" --zone="$ZONE" >/dev/null 2>&1 || \
  gcloud compute disks create "$NAME-data" --zone="$ZONE" --size="${DATA_DISK_GB}GB" --type=pd-balanced

gcloud compute instances describe "$NAME" --zone="$ZONE" >/dev/null 2>&1 || \
gcloud compute instances create "$NAME" --zone="$ZONE" --machine-type="$MACHINE_TYPE" \
  --address="$IP" --tags=qa-web --image-family=debian-12 --image-project=debian-cloud \
  --boot-disk-size=20GB --disk="name=$NAME-data,device-name=data,mode=rw,auto-delete=no" \
  --metadata="qa-domain=$DOMAIN,qa-name=$NAME" \
  --metadata-from-file=startup-script=gcp/startup.sh

# Daily snapshots of the data disk, kept 14 days.
gcloud compute resource-policies describe qa-daily --region="$REGION" >/dev/null 2>&1 || \
  gcloud compute resource-policies create snapshot-schedule qa-daily --region="$REGION" \
    --max-retention-days=14 --daily-schedule --start-time=19:00      # 19:00 UTC = 00:30 IST
gcloud compute disks add-resource-policies "$NAME-data" --zone="$ZONE" --resource-policies=qa-daily 2>/dev/null || true

cat <<MSG
Instance $NAME ready.  STATIC IP: $IP
1. DNS: create A record  $DOMAIN -> $IP  (HTTPS certificate is issued automatically once DNS resolves)
2. Dhan: whitelist $IP as the static IP for this account's API.
3. First login: https://$DOMAIN/setup creates the admin user.
MSG
