#!/usr/bin/env bash
# Add one more independent member instance: own VM, own static IP, own disk, own database, own Dhan account.
# usage: deploy/gcp/add-member.sh algo4.samirmishra.com
# Picks the next free name (qa1, qa2, ...), records it in deploy/instances.env (git-ignored) and provisions it.
set -euo pipefail
cd "$(dirname "$0")/.."; source instances.env
DOMAIN="${1:?usage: add-member.sh <domain>}"
for i in $INSTANCES; do
  if [[ ${i#*:} == "$DOMAIN" ]]; then echo "domain already assigned to ${i%%:*}; (re)running its bootstrap"; exec bash gcp/bootstrap.sh "${i%%:*}"; fi
done
n=1; while [[ " $INSTANCES " == *" qa$n:"* ]]; do n=$((n+1)); done
NAME="qa$n"
sed -i "s|^INSTANCES=\"\(.*\)\"|INSTANCES=\"\1 $NAME:$DOMAIN\"|" instances.env
echo "new member instance: $NAME -> $DOMAIN"
exec bash gcp/bootstrap.sh "$NAME"
