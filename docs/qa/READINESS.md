# QUANT ALGO — readiness report (state at handover)
## Done and tested locally
- Fork base inspected: OpenAlgo v2.0.3.3, AGPL-3.0, Dhan broker plugin + streaming adapter present, Analyzer/sandbox mode present, `/python` strategy host present.
- UI branded (QUANT ALGO name, logo, favicon, titles, footer with AGPL source link and upstream credit). Frontend layout tests: 30/30 pass.
- `quant_algo` execution layer: 9/9 tests pass (risk limits incl. daily-loss halt, duplicate-order prevention, controlled re-entry, LIVE hard-lock, failed-send key retention, latency log).
- Deploy scripts written, bash syntax-checked, compose file validated.
## NOT done (blocked)
| Item | Why | Owner action |
|---|---|---|
| GitHub repo `iitkgpsam/quant-algo` | session `GH_TOKEN` invalid | Reconnect GitHub / supply valid token with repo scope |
| GCP project, VM, static IP, HTTPS | no gcloud credentials | `gcloud auth login` or service-account token; give billing account ID |
| DNS for algo.samirmishra.com | DNS outside my access | Add A record to the static IP printed by bootstrap.sh |
| Dhan connectivity / WebSocket / order updates | needs Dhan API key + access token + static IP whitelisting | Provide on VM `.env` yourself; not through chat |
| Red Bar RB5/RB30 logic | **your exact rules were not in the request**; none invented | Fill `quant_algo/strategies/redbar/spec.template.yaml` |
| Risk limit values | not specified; guard refuses to start with any unset | Supply numbers |
| Feed-to-fill latency numbers | requires live Dhan market-data session | Measured after Dhan is connected; no figure promised |
| qa2/qa3 VMs | by design only after qa1 validated | Approve after qa1 passes |
## Estimated cloud cost (asia-south1, list prices, verify before billing)
e2-medium ~US$30/mo + 20GB boot ~$1.6 + 30GB pd-balanced ~$3.6 + static IP in use $0 (idle $2.9 ) + snapshots ~$1 ≈ **US$35–40/mo per VM; ~US$110/mo for three**. Egress extra (small).
## Decisions needing you
1. Billing approval and project ID. 2. Subdomains for family VMs (default algo2/algo3). 3. Repo public (required if network users get source; AGPL) — default public.
4. LIVE enablement is owner-only: `QA_LIVE_ENABLED=1` + `QA_LIVE_CONFIRM` on the VM; never done by me.
## Not touched
quant.samirmishra.com and its repo/VMs/brokers: not accessed.
