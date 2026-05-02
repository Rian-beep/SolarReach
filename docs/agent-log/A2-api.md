# A2 — API Gateway log

## 2026-05-02

### Bootstrap
- Created `packages/api/` package with FastAPI + pyproject.
- Spun up `.venv` (python 3.12.2 via pyenv) and installed deps.
- Tests run via `./.venv/bin/pytest` from `packages/api/`.

### Endpoints implemented (CONTRACTS § 2)
- `GET /health` — pings mongo, reports redis + anthropic key presence.
- `POST /scan` — creates job in `scan_jobs`, seeds 5 mock leads (A2 STUB),
  audits before any paid call.
- `GET /scan/{id}/stream` — SSE; uses `services/change_streams.iter_new_leads`
  which falls back from real `collection.watch()` to polling on standalone mongo.
- `GET /lead/{id}` — joins company + directors via two `find_one` lookups
  (cheaper than `$lookup` for hot path; we can swap if Atlas profile flags it).
- `POST /lead/{id}/refresh_directors` — Companies House live path; falls back
  to mock director when key missing or company has no `ch_number`.
- `POST /lead/{id}/build_org` — STUB: returns mock decision-maker, persists to
  `leads.decision_maker`. TODO(A4): delegate to codex.
- `POST /lead/{id}/pitch` — STUB: mock URLs + deck_json. TODO(A4): codex generates
  real PPTX/PDF.
- `GET /lead/{id}/pitch/download?format=pdf|pptx` — streams a placeholder file.
- `GET /lead/spend/session` — aggregates `audit_log.cost_cents`, returns budget pct.
- `POST /lead/{id}/flux_overlay` — STUB: mock URL + bbox. TODO(LUKE).
- `POST /lead/{id}/panels` — STUB: 12-panel grid. TODO(LUKE) for ray-cast clip.
- `GET /voice/signed-url` — proxies ElevenLabs `/get_signed_url`. Hard-refuses
  if AI disclosure missing from `packages/voice/voice_service/prompts/agent_system.md`.
- `POST /admin/client/{slug}` — upserts client doc.
- `POST /financial/calculator` — residential breakdown; tries shared module,
  falls back to inline 25-yr NPV at 4%.
- `POST /inbound/lead` — calculator-mode capture; recipient email is hashed
  in audit log only, never persisted on lead.
- `GET /realapi/ch/{company,officers}/{ch_number}` — Companies House proxies
  with Basic auth (key as username).

### Services
- `services/cost.py` — Anthropic price table for Sonnet 4.6 / Opus 4.7 /
  Haiku 4.5 with cache-create (1.25x) and cache-read (0.10x) modifiers.
- `services/audit.py` — `log_audit()` writes `audit_log` doc, sha256-hashes
  recipient emails (cardinal rule § 7.7).
- `services/compliance_gate.py` — `send_outbound_email` diverts to `outbox/`
  when `SOLARREACH_LIVE_OUTBOUND=false` (default). Cardinal rule § 7.4 backstop.
- `services/change_streams.py` — adapter: real watch → polling fallback.

### Tests (16 passing)
- `test_health.py` (2) — happy path + degraded shape.
- `test_cost.py` (3) — Sonnet, Opus, determinism.
- `test_audit.py` (1) — write + hash check.
- `test_compliance_gate.py` (1) — outbox redirect.
- `test_scan.py` (1) — round-trip create scan.
- `test_lead.py` (2) — get with company join + spend aggregation.
- `test_flux_panels.py` (2) — stub shapes.
- `test_voice.py` (1) — 503 without ElevenLabs key.
- `test_admin.py` (1), `test_financial.py` (1), `test_inbound.py` (1).

### Cross-agent notes
- Frontend (A3): `/openapi.json` covers all 17 paths — typegen against it.
- Codex (A4): pitch/build_org persist results to `leads.{pitch,decision_maker}`
  so when you replace the stub bodies, no schema migration needed.
- Luke: flux + panels stubs return spec-correct shapes — wire the MapSlot
  blind, swap stubs out without touching frontend.
- Voice (A5): `/voice/signed-url` will refuse if `agent_system.md` is missing
  the strings "AI" + "disclose" (case-insensitive). Make sure your prompt
  contains those words verbatim or it's a 503.

### Known stubs / TODOs
- `# A2 STUB` markers in: scan seeding, refresh_directors fallback, build_org,
  pitch, pitch_download, flux_overlay, panels.
- `TODO(A4)` for codex-owned bodies; `TODO(LUKE)` for Solar API integrations.

### Contract changes
- None. All payloads match CONTRACTS.md verbatim.
