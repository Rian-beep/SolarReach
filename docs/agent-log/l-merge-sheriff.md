# l-merge-sheriff — running sitrep

Final integration sweep, 2026-05-02. Five feature agents landing in parallel
(g-ch-fix, h-radiance-global, i-pitch-quality, j-pdf-extract, k-voice-bridge).
Sheriff role: pull, integration-test, push when stable. No feature code.

---

## Sweep #1 — 2026-05-02 16:12 BST

### State of the union
- Branch `main`, was at `ba6aafa` (origin sync).
- One unpushed feature commit landed mid-sweep: `1ce9b66` — h-radiance-global.
- Modified working tree: 5 files (main.py, leads.py, audit.py, App.tsx … evolving).
- Untracked: voice_provider.py, industry_benchmarks.py (py + ts), HUD-Benchmarks.tsx, RadianceCanvas.tsx — feature work in flight.

### Pass/fail matrix

| Suite | Result | Notes |
|---|---|---|
| `pnpm --dir packages/web typecheck` | PASS | Clean, no errors |
| `uv run pytest -q` (api) | **51/52** | 1 fail: `test_voice_signed_url_503_without_key` — k-voice-bridge in flight, voice router refactored to return 200+demo_mode instead of 503; test not yet updated. Isolated to dirty tree (passes when uncommitted voice work stashed) |
| `uv run --extra dev pytest -q` (codex) | PASS | 42/42 |
| `uv run --extra dev pytest -q` (shared/py) | PASS | 24/24 |
| `GET /health` | PASS | `mongo:true, anthropic_reachable:true, redis:true` |
| `POST /scan EC1Y 8AF` | PASS | `lead_count: 27` real leads streamed |
| `GET /lead/spend/session` | WARN | `spent_cents:102 / budget_cents:100` — over by 2¢. Existing session has been crunching real Sonnet calls; a fresh session reset is recommended pre-demo (see RUNBOOK final). Not a regression. |

### Integrated this sweep
- `1ce9b66` — RADIANCE heatmap canvas (h-radiance-global). Clean isolated commit, tests green without dirty tree, pushed to `origin/main`.

### Holding (waiting for agent commit)
- **g-ch-fix** — leads.py refresh_directors hardened with seeded fallback (200 always, never 502) + 3 new tests in test_lead.py. Looks correct, not yet committed by agent.
- **j-pdf-extract** — industry_benchmarks (py+ts), HUD-Benchmarks.tsx, App.tsx mount. Not yet committed.
- **k-voice-bridge** — voice_provider.py service + voice.py refactor. test_voice.py change in flight; one existing test still on old contract → temporarily failing. **Holding push until k-voice-bridge updates the failing test.**
- **i-pitch-quality** — pptx_renderer.py modified (uncommitted).

### Sheriff infra fixes (staged in working tree, not yet committed)
1. `packages/api/app/main.py` — preload `.env` / `.env.local` via `dotenv_values` to override empty parent-shell env vars (Claude Desktop exports `ANTHROPIC_API_KEY=""`). This is why `anthropic_reachable` previously read false; now true.
2. `packages/swarm/swarm/audit.py` — sniff coroutine return so `_fallback_log_audit` works with both sync pymongo (CrewAI tool callback) and async motor (API process). Was crashing tools at runtime.

These are integration plumbing, not feature code — sheriff territory. Will commit + push once the in-flight feature dust settles to keep one clean commit per concern.

### Last commit pushed
`1ce9b66` — `feat(map): global RADIANCE heatmap canvas across visible map area`

---
