# Antigravity review handover
**Scope of change vs upstream (7ba5267):** branding in `frontend/src` (Navbar, Home, Login, Faq, Footer, titles, logo);
new `quant_algo/` (risk, duplicate guard, re-entry, exec log, spec loader, Red Bar scaffold); `deploy/`; `tests_qa/`.
**Review first:** `quant_algo/orders.py` (single order choke point, LIVE lock, key reserved before send),
`quant_algo/risk.py`, `deploy/gcp/bootstrap.sh` (never executed yet), `deploy/node/up.sh` (secret generation).
**Run tests:** `python3 -m pytest tests_qa -q -c /dev/null --rootdir .` (9 pass) and `cd frontend && npx vitest run src/components/layout`.
**Known gaps:** see READINESS.md. Reuse OpenAlgo's built-in Dhan adapter, Analyzer mode, WebSocket proxy, and `/python` strategy host; nothing was reimplemented.
