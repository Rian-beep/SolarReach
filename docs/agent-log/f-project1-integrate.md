# f-project1-integrate — log

## 2026-05-02

### Task 1 — Probe secondary repo

- Cloned `Rian-beep/solarreach-project1` into `/tmp/sr-project1`.
- Stack: deepagents on LangGraph; checkpoints + store in same Mongo cluster
  ("3-in-one" pattern). App data in `solarreach` DB, agent state in
  `solarreach_agent_checkpoints`, long-term in `solarreach_agent_store`.
- Lead-data fetcher is `packages/agents/lead_agent/tools/mongo_tools.py`
  exposing `fetch_unscored_leads`, `get_lead`, etc as LangChain `@tool`s
  reading directly from the `solarreach.leads` collection.
- Schema overlap with our `leads` is high (composite_score, postcode,
  premises_type), but project1 uses `client_slug` while ours uses `client_id`.
- Decision: link layer queries OUR `solarreach.leads` first (already populated
  by A1 seed + A6 enrichment), then opportunistically reads project1's
  `solarreach_agent_store` for cross-thread enrichment notes if present.
  Importing project1 as a Python package is out-of-scope for this PR (heavy
  langgraph deps); we stay in pymongo land.

### Task 2 — Atlas linkage layer (API)

- Added `packages/api/app/services/project1_link.py` with
  `fetch_project1_leads(db, client_id, postcode, limit)` which:
  - queries our `leads` collection (the canonical store)
  - opportunistically merges any agent notes from
    `solarreach_agent_store.store` keyed by `lead:<id>` (no fail if absent)
  - dedupes by `_id`
- Added `push_outreach_event(db, lead_id, event)` which writes to a new
  `outreach_events` collection. The collection is created lazily via
  `_ensure_outreach_events_collection` with a `$jsonSchema` validator
  pinned to `{lead_id, event_type, payload, ts}`.
- Wired into `routers/leads.py` `GET /leads`: when `?augment=project1`
  is passed, leads pass through `fetch_project1_leads` for note merge;
  default behaviour unchanged.
- Added `POST /lead/{id}/outreach_event` endpoint.

### Task 3 — Solar metrics card

- Extended `packages/web/src/components/drawer/IntelTab.tsx` with a
  collapsible `SOLAR METRICS · DEEP RESEARCH` Card.
- Built lightweight in-component collapsible (no new dep — Radix
  Collapsible is not in package.json; ChevronDown rotation is sufficient).
- Sections: Energy Generated, Money Saved, Sales Metrics, Funding Models
  (link), Tax Breaks (link).
- Used `lead.panel_layout.annual_kwh`, `lead.financial.annual_saving_gbp`.
- CO2 offset = annual_kwh × 0.193 kg/kWh.
- Funding/Tax cards link to REF tab.

### Task 4 — Admin Centre extensions

- Extended `packages/web/src/components/admin/AdminCentre.tsx` with three
  new sections: PRODUCT PAGE, PRICING TIERS (Starter/Pro/Enterprise),
  OUTREACH AGENT CONTEXT.
- Single Save button persists `product_description`, `pricing_tiers[]`,
  `expertise_notes` on the existing `clients` doc via the existing
  `POST /admin/client/<slug>` endpoint (extra fields just pass through —
  the route does `$set` on body which already accepts arbitrary keys).
- Save invalidates the `client` query so subsequent pitch/email calls
  re-read the updated doc.

### Task 5 — Outreach AI subject expertise

- Patched `packages/codex/codex_brain/generators/email.py`
  `generate_email_variants(lead, decision_maker, client, *, client_doc=None)`
  to accept an optional `client_doc` and splice
  `expertise_notes` + `product_description` into the system prompt as a
  trailing `## Subject expertise` block.
- Patched `routers/leads.py` `pitch` to pass `client_doc` down so
  Sonnet 4.6 sees the admin-config expertise notes.

### Verify

- `pnpm typecheck` (web) — clean
- `uv run pytest -q` (api) — 49 passed (6 new in test_project1_link.py)
- `uv run pytest -q` (codex) — 42 passed (4 new in test_email.py)

### Notes for orchestrator

- Task 3 (solar-metrics card) was already swept into commit `f463c84`
  ("aggregate agent work — IntelTab solar metrics") by the orchestrator
  before this branch could commit it. The card is in place, working,
  and matches the spec.
- Tasks 1+2 landed in `92f47ba` (atlas linkage + outreach event endpoint)
- Tasks 4+5 land in this commit (admin extensions + email expertise splice)
- No changes to MapSlot.tsx, App.tsx, Header.tsx, HUD-*.tsx, or .env.local.
