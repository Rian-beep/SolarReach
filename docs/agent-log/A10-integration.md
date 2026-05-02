# A10 — Integration / Merge Sheriff / QA log

## 2026-05-02 — final integration sweep before submission

### Test Results Matrix

| Suite | Command | Result |
|---|---|---|
| Web typecheck | `pnpm typecheck` (packages/web) | PASS — 0 errors |
| Web build | `pnpm build` (packages/web) | PASS — 539 kB bundle (warning: >500 kB, non-blocking; see Risks) |
| API tests | `uv run pytest -q` (packages/api) | PASS — 35/35, 1 deprecation warning (matplotlib `cm.get_cmap`, non-blocking) |
| Codex tests | `uv run --extra dev pytest -q` (packages/codex) | PASS — 38/38 |
| Shared tests | `uv run --extra dev pytest -q` (packages/shared/py) | PASS — 24/24 |
| Contract validator | `python3 scripts/validate_contracts.py` | PASS — 21 declared = 21 routes, zero drift |

> Note: codex/shared `uv run pytest -q` requires `--extra dev` to install pytest. The brief's command form works once dev extras are resolved (which uv now does on first call). Updating `Makefile` is out of scope this hour.

### Live endpoint smoke (API on :8000, Atlas + Anthropic + Redis live)

| Endpoint | Result |
|---|---|
| `GET /health` | `{mongo:true, anthropic_reachable:true, redis:true}` |
| `POST /scan` (EC1Y 8AF, limit 50) | `lead_count: 10` (real seeded London leads — Lloyds, Barclays, real owner whitelist) |
| `POST /lead/<id>/build_org` | `{decision_maker:{name:"Unknown",...}}` — graceful fallback when CH directors not yet ingested for that company; works with directors when they exist |
| `POST /lead/<id>/pitch` | Real Sonnet 4.6 deck + emails, `used_real:true`, ~12 cents per call, real PPTX written to `/tmp/decks` |
| `POST /lead/<id>/panels` | 17+ panels, real per-panel `corners`/`tilt`/`azimuth`/`kwh_yr` from Solar API findClosest |
| `POST /lead/<id>/flux_overlay` | Real PNG, bbox + vmin/vmax, cached on disk |
| `GET /lead/spend/session` | Aggregates audit_log (`spent_cents` rises after each cost-incurring call) |

### Audit log integrity
21 entries, schema verified — every cost-incurring action present (`api.call`, `lead.pitch`, `lead.build_org`, `lead.scan.create`). All required keys (`ts, actor, action, lead_id, cost_cents, recipient_sha256, metadata`) populated.

### Contract drift found + resolved

The validator initially showed **6 routes shipped by A6/A7 not declared in CONTRACTS.md § 2** plus **1 wiring bug (frontend → 404)**:

1. `POST /realapi/companies-house/search` — A7 — **documented** in CONTRACTS.md § 2 with `# A10` annotation.
2. `POST /realapi/companies-house/officers` — A7 — **documented**.
3. `POST /realapi/companies-house/company` — A7 — **documented**.
4. `GET /realapi/ch/company/<ch_number>` — legacy back-compat — **documented**.
5. `GET /realapi/ch/officers/<ch_number>` — legacy back-compat — **documented**.
6. `POST /inbound/lead` — calculator capture — **documented**.
7. `GET /leads?client_id=...&limit=...` — **was missing from API entirely** but called by frontend `useLeads()` for bootstrap. Added in `packages/api/app/routers/leads.py` (sorts by composite_score desc, then created_at desc) **and** declared in CONTRACTS.md.

Validator now reports: `21 declared = 21 routes ✓ contracts match`.

### Wiring fixes (additive)

- **SSE for live scan markers** — `packages/web/src/components/header/Header.tsx`: after `useScan().mutateAsync()` resolves, opens an `EventSource` against `res.stream_url` and pushes `lead` events into `useLeadStore.addLead()`. This delivers the "markers stream in real-time" experience described in `docs/RUNBOOK-DEMO.md` (Atlas Change Streams behind SSE). Prior behaviour: scan returned but only React Query invalidation refetched leads in batch.

### Dead code / stale comment cleanup

- `packages/api/app/routers/leads.py:406` — replaced `# A2 STUB — write a placeholder` comment with accurate doc explaining the fallback for un-generated pitches (real renderer writes to `/tmp/decks`, exposed via `/static/pitches`; this branch only fires when no pitch exists yet).
- `# TODO(A4): wire SES/SendGrid here.` in `compliance_gate.py` left in place — genuine future work, gated behind `SOLARREACH_LIVE_OUTBOUND` which is `false` by default per CONTRACTS § 7.4.

### Lint

Skipped — biome is configured at root but the only diagnostics were stylistic (import sort, line-break formatting) across 80+ files. Auto-fixing would create a noisy diff against an already-green typecheck/build. Not worth the regression risk this close to submission.

### Hard rules respected

- Did NOT touch `packages/web/src/components/map3d/MapSlot.tsx` (Luke is editing concurrently).
- Did NOT modify `.env.local` or any secret-bearing file.
- Did NOT delete agent-log files.
- Did NOT push to git (commits ready for Luke to push).
- Did NOT change any contract payloads — only **documented** existing ones with `# A10` annotation.

### Remaining known issues / risks

1. **Bundle size warning (539 kB > 500 kB)** — non-blocking, only a vite suggestion. Code-splitting MapSlot and the calculator would shave ~120 kB but is risky to do an hour before submission.
2. **`build_org` returns Unknown for some leads** — expected behaviour when the company has no CH directors ingested yet. The route works correctly with directors (Opus 4.7 over the directors list per `decision_maker_inference.md`). Demo path uses a high-score lead with seeded directors; if you pick a lead that returns Unknown, just click another marker.
3. **Solar API latency on first hit** — `panels`/`flux_overlay` take 5–15 s on uncached leads. Pre-fetch via `make demo-prefetch` before the demo.
4. **PDF conversion may skip locally** — pitch endpoint catches `pptx_to_pdf` failure (libreoffice may be missing) and returns `pdf_url: null`. PPTX always renders. The web app should handle the null gracefully (already does via the download-stub fallback in `/lead/<id>/pitch/download`).
5. **Matplotlib deprecation warning** in `solar_api.py:276` — `cm.get_cmap("inferno")` will break in matplotlib 3.11. Trivial fix (`matplotlib.colormaps["inferno"]`) but out of scope before demo.

### Files changed by A10

- `packages/api/app/routers/leads.py` — added `GET /leads`, fixed stale STUB comment.
- `packages/web/src/components/header/Header.tsx` — wired SSE consumer for `/scan` stream.
- `docs/CONTRACTS.md` — documented 7 endpoints with `# A10` annotation; zero contract drift.
- `docs/agent-log/A10-integration.md` — this file.
- `docs/DEMO-CHECKLIST.md` — short 7-min path for Luke pre-submit.
