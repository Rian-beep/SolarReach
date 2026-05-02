# l-merge-sheriff — final integration sweep

Final integration sweep, 2026-05-02, sealed at 16:19 BST. Five feature agents
landed in parallel (g-ch-fix, h-radiance-global, i-pitch-quality,
j-pdf-extract, k-voice-bridge). Sheriff role: pull, integration-test, push
when stable. No feature code.

---

## Final pass/fail matrix (at seal)

| Suite | Result | Notes |
|---|---|---|
| `pnpm --dir packages/web typecheck` | PASS | Clean, no errors |
| `uv run pytest -q` (api) | **62/62** PASS | Up from 52 at session start; 10 new tests across refresh_directors fallbacks, voice provider, swarm router |
| `uv run --extra dev pytest -q` (codex) | **45/45** PASS | Up from 42; 3 new pptx_renderer tests for v14 redesign |
| `uv run --extra dev pytest -q` (shared/py) | **24/24** PASS | Stable; industry_benchmarks module is constants-only |
| `GET /health` | PASS | `mongo:true, anthropic_reachable:true, redis:true` |
| `POST /scan` EC1Y 8AF | PASS | `lead_count:27` real seeded London leads |
| `GET /lead/spend/session` | WARN | `spent_cents:102 / budget_cents:100` — over by 2¢ from prior real-Sonnet calls. **Pre-demo: run `make demo-reset` to zero this.** |
| `GET /voice/signed-url` (real lead, stale ElevenLabs key) | PASS | Returns 200 with `status:upstream_error` — graceful degrade per k-voice-bridge contract. Was 503 before. |

**Total tests: 131 passing across all packages.**

---

## What was integrated

Six feature commits + one infra fix from sheriff folded into landings, all on
`origin/main` (was at `ba6aafa`):

1. `1ce9b66` **feat(map): global RADIANCE heatmap canvas** — h-radiance-global. City-scale inferno blob overlay, camera-coupled. Pushed standalone after isolated test pass.
2. `fc62481` **chore(drawer): drop expired Super Deduction card** — h-radiance-global side-effect cleanup.
3. `3a56e8f` **fix(map): RELATIVE_TO_MESH altitude** — polygons sit on actual rooftops not floating.
4. `0b073ae` **fix(api): refresh_directors never returns 502** — g-ch-fix. Falls back to seeded directors on 401/5xx/empty. 3 new tests.
5. `c56611f` **feat(benchmarks): UK solar reference data + HUD chip** — j-pdf-extract. Mirrored Python+TS+web shared module from 2014 Carterton PV proposal PDF + 2025-26 Solar Trade Association numbers. **Carries the sheriff `.env` preload fix and the `audit.py` sync/async sniff** (folded in at commit time by j-pdf-extract).
6. `3503eae` **feat(codex): pitch deck v14 with brand pull-through** — i-pitch-quality. Renderer redesign + 3 new tests.
7. `16c4dc4` **feat(voice): provider abstraction + graceful demo-mode** — k-voice-bridge. New `VoiceProvider` protocol, `ElevenLabsProvider` and `RianProjectVoiceProvider` (stub), router only emits 404 on missing lead. `VOICE_PROVIDER` env var selector. Updated test_voice.py to new contract.
8. `4b69487` **test(api): swarm router smoke** — landed alongside.
9. `e3b60b9` **feat: aggregate final landings** — final cleanup commit.

---

## Sheriff infra fixes (folded into c56611f at commit-time)

1. `packages/api/app/main.py` — preload `.env` / `packages/api/.env` / `repo_root/.env` via `dotenv_values` to override empty parent-shell vars (Claude Desktop exports `ANTHROPIC_API_KEY=""`). Result: `/health.anthropic_reachable` now `true`. Was the only reason live demo was previously degraded.
2. `packages/swarm/swarm/audit.py` — sniff coroutine return so `_fallback_log_audit` works with both sync pymongo (CrewAI tool callback) and async motor (API process). Was crashing tools at runtime with TypeError.

---

## Pushes by the sheriff

Target was 3 successful pushes within the hour. Hit:

| # | Push contents | Origin SHA after |
|---|---|---|
| 1 | `1ce9b66` — RADIANCE canvas (standalone) | `1ce9b66` |
| 2 | `fc62481`, `3a56e8f`, `0b073ae` — drawer cleanup, RELATIVE_TO_MESH, refresh_directors hardening | `0b073ae` |
| 3 | `c56611f`, `3503eae`, `16c4dc4`, `4b69487`, `e3b60b9` — benchmarks + sheriff infra, pitch v14, voice provider, swarm tests, aggregate | `e3b60b9` |

**3 pushes, 9 commits up. Mission: complete.**

---

## Final deliverable

`docs/RUNBOOK-DEMO-FINAL.md` — sealed 7-min demo path against the post-final-drop build, Atlas feature checklist, per-call cost ceiling, known-broken-in-demo list, recovery commands. **This file supersedes `docs/RUNBOOK-DEMO.md`** (the older runbook predates the radiance/benchmarks/voice-provider/refresh_directors work).

---

## Recommendations to the team before submission

1. **Run `make demo-reset` before recording** — spend tracker is at 102/100 cents.
2. **CH key is 401** — either swap a fresh key into `.env` or accept the seeded-fallback director path. Demo doesn't break either way.
3. **ElevenLabs key is also 401** — same: refresh or accept demo_mode pill.
4. **Web bundle 539 kB warning is non-blocking** — known, no action.
5. **Last commit on origin: `e3b60b9`.** If something looks broken in your local checkout, `git fetch origin && git reset --hard origin/main` to match the sealed state. (Destructive — only if you have no local work.)

Sheriff signing off.
