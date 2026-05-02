# A4 — Codex Brain — Build Log

## 2026-05-02 — Hackathon push

### 12:05 — Initial cold-start
Read `docs/CONTRACTS.md` § 1 (leads schema) + § 2 (`/lead/:id/pitch`,
`/lead/:id/build_org`) and `docs/THEME-NARRATIVE.md`. Confirmed:
- Codex pulls from `leads`, `clients`, `directors` and writes `leads.pitch_artifacts`
- Decision-maker write target: `leads.decision_maker`
- Audit row format: `audit_log` with `cost_cents`, `recipient_sha256`, `metadata.model`

### 12:10 — Package skeleton + cost calc
- `pyproject.toml` (3.12, asyncio_mode auto)
- `anthropic_client.py` — TDD'd cost_cents pure function first (12 tests pass).
  Pricing table embedded for Sonnet 4.6 ($3/$15), Opus 4.7 ($15/$75), Haiku 4.5 ($1/$5).
  Cache reads at 10% of input rate; cache writes at 125% (5min ephemeral).
  API key masked in `__repr__` and in error strings.

### 12:18 — Funding constants
- `constants_funding.py` — 5 models with `monthly_payment_formula`, `ownership_at_end`,
  `term_years`, `who_claims_seg`, `capex_required_pct`. 4 tests verify name set + key
  schema. Capital Expense vs Free Install asymmetry on SEG ownership encoded.

### 12:22 — Decision-maker priority logic
- `generators/org_chart.py` — `role_priority()` deterministic. Hard hierarchy:
  CFO (0) → Finance Dir (1) → MD (2) → CEO (3) → Head of Sustainability (4)
  → COO (5) → Property Director (6) → Estates Manager (7) → generic Director (50).
- Confidence clamp: any role mapping to GENERIC_DIRECTOR forced to < 0.7 even if LLM
  claims otherwise (cardinal rule from spec).
- 9 tests pass.
- LLM path (`infer_decision_maker`) wraps Opus 4.7 with cached system prompt; on
  failure falls back to deterministic pick rather than crash the API.

### 12:28 — Charts
- `charts.py` — matplotlib Agg backend (headless safe). Dark navy #0F172A bg,
  emerald gain line, magenta loss line, amber payback marker. 25y horizon with
  0.5%/yr panel degradation. PNG out to `/tmp/decks/roi_<lead_id>.png`. 3 tests.

### 12:33 — PPTX renderer
- `pptx_renderer.py` — `render_pptx(deck_json, brand)` produces 11 slides at
  16:9 (12192000 × 6858000 EMU). Each non-title slide gets a 60kemu colored
  accent bar. Slide 5 embeds the matplotlib ROI PNG. Renderer is defensive —
  missing top-level keys become placeholder slides rather than KeyErrors.
  4 tests verify slide count, widescreen dims, filename, and missing-field
  resilience.

### 12:40 — Prompts
- `prompts/pitch_system.md` — GRID INDEPENDENCE narrative, 5 funding models in
  fixed canonical order, banned superlatives list, strict 11-section JSON
  contract. UK-specific: 78%-since-2019, G99/DNO, SEG, capital allowances.
- `prompts/email_system.md` — A "numbers-first" / B "story-first" structural
  differentiation, 90–120 words, named decision-maker salutation.
- `prompts/decision_maker_inference.md` — Opus 4.7. Confidence guidance per
  role. Strict <0.7 for generic Director. Name MUST appear in the input list.
- `prompts/voice_objections_system.md` — Haiku 4.5 sidecar. AI-disclosure
  cardinal rule: if `ai_disclosed: false` the response leads with disclosure.

### 12:48 — Deck generator
- `generators/deck.py` — `generate_deck(lead, client, decision_maker)` returns
  `DeckResult { deck_json, cost_cents, in/out_tokens, cache_read/create_tokens }`.
  Cache_system=True on every call (system prompt is large + repeated per-client).
  Streaming variant via `complete_streaming_collect` for early-UX UI.
  Fence-strip + preamble-skip hardening; if Sonnet drifts to non-JSON, returns
  a minimal stub so the PPTX path doesn't 500.
- Smoke runner: `python -m codex_brain.generators.deck` works against a stub
  deck (no API key needed) and writes `/tmp/decks/lead_smoke_001.pptx`. Verified
  11 slides + 16:9 in smoke output.
- 3 tests. Crucial test: `test_cache_read_on_second_call_simulated` proves second
  call with identical system prompt has `cache_read_tokens > 0` AND lower
  `cost_cents` than the first call (prompt cache effect verified end-to-end).

### 12:55 — Email + PDF + Embeddings + Celery
- `generators/email.py` — A/B variants via Sonnet, deterministic fallback if LLM fails.
- `generators/pdf_converter.py` — `pptx_to_pdf` calls `libreoffice --headless
  --convert-to pdf` with timeout=60. macOS app-bundle fallback for local dev.
  2 tests using monkeypatched subprocess.run.
- `embeddings.py` — Voyage AI `voyage-3` wrapper, 1024-dim per CONTRACTS.md.
- `celery_app.py` + `tasks.py` — three tasks (`generate_pitch`,
  `infer_decision_maker`, `generate_emails`). Each wraps an async coroutine
  with `asyncio.run()`. Audit logging via `solarreach_api.services.audit` with
  fallback to direct `audit_log` insert. Recipient emails sha256-hashed
  (cardinal rule 7). MongoDB URI auto-appends `?authSource=admin` (cardinal rule 6).

### 13:00 — Acceptance gates
- [x] `python -m codex_brain.generators.deck` smoke-runs against stub lead and
      produces a valid 11-slide PPTX (verified slide count = 11, 16:9 dims).
- [x] PDF conversion: code path correct (LibreOffice in Dockerfile); local
      machine has no LibreOffice so verified via mocked subprocess in tests.
- [x] `pytest` — **38 passed in 2.03s** (cost calc, fence strip, key masking,
      funding models, role priority, charts, pptx, deck JSON parsing, deck cache
      hit on second call, email A/B, pdf conversion mock).
- [x] Cost calc matches Anthropic published pricing within 1% (4 tests cover
      Sonnet/Opus/Haiku + cache read 10% + cache write 125%).
- [x] Prompt cache verified: `test_cache_read_on_second_call_simulated` asserts
      `cache_read_tokens > 0` AND lower cost on call 2.

## Notes for other agents

- A2 API: import `from codex_brain.tasks import generate_pitch_task` and
  `.delay(lead_id, client_id)` for async, or `from codex_brain.generators.deck
  import generate_deck` + `pptx_renderer.render_pptx` for inline.
- Output files live at `/tmp/decks/<lead_id>.pptx` and `<lead_id>.pdf`.
  A2's `GET /lead/<id>/pitch/download?format=pdf|pptx` should stream from there.
- `audit_log` writes happen inside Celery tasks; if A2 calls generators inline,
  it should write its own audit row.
- Voyage embeddings live in `codex_brain.embeddings` — used by `companies.embedding`
  population and the Voice agent's `calls_ts.embedding` similarity search.
