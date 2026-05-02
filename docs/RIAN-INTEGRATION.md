# SolarReach × Rian (`solarreach-project1`) Integration Handshake

> Last updated: 2026-05-02
> Owners: A2 (API) + A10 (integration)
> Companion: `docs/CONTRACTS.md` (canonical contracts — do not duplicate, link)

This is the contract between **SolarReach Atlas** (this repo) and **Rian's
agentic stack** (`Rian-beep/solarreach-project1`). It covers:

1. Shared MongoDB collections (schemas)
2. REST endpoints Rian's agents can call into us
3. Webhook spec — how his agents push events back to us
4. Auth — token / signed-request pattern
5. Data dump format — what we publish to him as bulk artefacts

---

## 0. Where things live

| Artefact | Path | Owner |
|---|---|---|
| Bulk data dumps | `exports/*.jsonl` + `exports/*.json` | this repo, refreshed by `scripts/export_for_rian.py` |
| Sync script (stub) | `scripts/sync_to_rian.sh` | invoked by Rian, pushes to his `data/exports` branch |
| Inbound webhook | `POST /integration/agent_event` (FastAPI) | this repo, `packages/api/app/routers/integration.py` |
| Atlas cluster | shared — DB `solarreach`; Rian also writes `solarreach_agent_store` | both |

---

## 1. MongoDB Collections (canonical schemas)

Single source of truth: `docs/CONTRACTS.md § 1`. Below is the subset Rian's
ingester needs — schemas reproduced verbatim from CONTRACTS so anyone reading
this doc alone can wire up without bouncing.

### `leads`
```json
{
  "_id": "lead_<uuid>",
  "client_id": "client-greensolar-uk",
  "address": "1 Old St, London EC1Y 8AF",
  "postcode": "EC1Y 8AF",
  "borough": "London Borough of Camden",
  "premises_type": "office|leisure|warehouse|retail|education",
  "geo": { "point": { "type": "Point", "coordinates": [-0.0876, 51.5256] } },
  "rooftop_polygon": {
    "type": "Polygon",
    "coordinates": [[[lng,lat], ...]],
    "source": "inspire_index_polygon|solar_api_bbox|synthesized",
    "inspire_id": "abc123",
    "area_m2_approx": 1240
  },
  "scores": {
    "solar_roi": 0.82,
    "financial_health": 0.71,
    "social_impact": 0.55,
    "composite_score": 74,
    "scored_at": "ISO-8601"
  },
  "owner": {
    "company_id": "company_<uuid>|null",
    "company_name": "Old Street Holdings Ltd",
    "source": "ccod|ocod|synthesized"
  },
  "decision_maker": {
    "name": "Sarah Patel",
    "role": "CFO",
    "confidence": 0.78,
    "rationale": "..."
  },
  "panel_layout": {
    "panels": [{"corners":[[lng,lat],...], "tilt":35, "azimuth":180, "kwh_yr":420}],
    "panel_count": 24,
    "annual_kwh": 10080,
    "clipped_at": "ISO-8601",
    "clip_method": "inspire_polygon_raycast"
  },
  "flux_overlay": {
    "url": "/lead/<id>/flux_overlay/raster.png",
    "bbox": [w, s, e, n],
    "vmin": 2.1, "vmax": 5.4,
    "cached_at": "ISO-8601"
  },
  "financial": {
    "capex_gbp": 24500,
    "annual_saving_gbp": 3120,
    "payback_years": 7.8,
    "npv_25yr_gbp": 41200
  },
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

Indexes:
- `{ "geo.point": "2dsphere" }`
- `{ "client_id": 1, "scores.composite_score": -1 }` (compound)
- `{ "postcode": 1 }`
- Atlas Search index `leads_text` on `address + owner.company_name + premises_type`

### `companies`
```json
{
  "_id": "company_<uuid>",
  "name": "Old Street Holdings Ltd",
  "ch_number": "12345678|null",
  "registered_address": "...",
  "title_number": "NGL12345",
  "ccod_proprietor_name": "OLD STREET HOLDINGS LIMITED",
  "directors": ["director_<uuid>", ...],
  "embedding": [/* 1024-dim Voyage AI voyage-3 */]
}
```

Indexes:
- Atlas Search `companies_text` (lucene) on `name + registered_address`
- Atlas Vector Search `companies_vector` (1024-dim cosine) on `embedding`

### `directors`
```json
{
  "_id": "director_<uuid>",
  "company_id": "company_<uuid>",
  "name": "Patel, Sarah",
  "name_display": "Sarah Patel",
  "role": "Director",
  "appointed_on": "ISO-8601",
  "email": "...",
  "linkedin_url": "...",
  "ch_officer_id": "..."
}
```

### `audit_log` (append-only)
```json
{
  "_id": "audit_<uuid>",
  "ts": "ISO-8601",
  "actor": "user|system|agent_<name>",
  "action": "lead.scan|lead.pitch|voice.session|api.call|integration.agent_event",
  "lead_id": "lead_<uuid>|null",
  "cost_cents": 5,
  "recipient_sha256": "sha256-of-email|null",
  "metadata": { /* action-specific */ }
}
```

> **Cardinal**: `audit_log` rows are NOT exported in bulk. Recipient hashes,
> while non-reversible, are still PII-adjacent. Use `audit_summary.json` (counts
> + sums only) for ingestion.

### `agent_events` (NEW — Rian's inbound webhook target)

Created lazily with a `$jsonSchema` validator on first POST to
`/integration/agent_event`. See § 3 below for the payload shape.

```json
{
  "_id": "ae_<uuid>",
  "source": "rian-project1",
  "agent": "research|outreach|enrichment|...",
  "event_type": "trace.start|trace.tool_call|lead.note|error|...",
  "lead_id": "lead_<uuid>|null",
  "trace_id": "<caller-supplied>|null",
  "payload": { /* free-form */ },
  "ts": "ISO-8601"
}
```

---

## 2. REST API Endpoints (FastAPI) — what Rian can call

Base URL: `http://localhost:8000` (dev) · port `8000`. Production base URL TBD.

> Reference: `docs/CONTRACTS.md § 2`. The list below is the subset relevant to
> Rian's agents — research/enrichment/outreach loops. All endpoints respond
> with JSON unless noted.

### `GET /health`
Liveness probe. Always 200, body indicates per-service degraded state.
Returns: `{ "status": "ok|degraded", "services": {mongo, redis, anthropic_reachable} }`

### `GET /leads`
Bootstrap list — leads sorted by composite_score desc.
Query: `?client_id=...&limit=50&postcode=EC1Y%208AF&augment=project1`
- `augment=project1` triggers `services/project1_link.py` to merge any agent
  notes Rian's stack has written under `solarreach_agent_store.store` keyed by
  `lead:<id>`. Pass it when you want your own notes round-tripped.

### `GET /lead/<id>`
Full Lead doc with joined `company` + `directors`.

### `POST /lead/<id>/refresh_directors`
Pulls officers from Companies House and upserts them. Always 200; soft-fails
to seeded fallback directors (warning surfaced) on CH 401/5xx so Rian's loops
never block on CH being down.

### `POST /lead/<id>/build_org`
Opus 4.7 decision-maker inference. Returns `{decision_maker: {name, role, confidence, rationale}}`.
Soft-fails to a deterministic stub when `ANTHROPIC_API_KEY` missing.

### `POST /lead/<id>/pitch`
Body: `{ "client_id": "client-greensolar-uk" }`
Generates pitch deck (Sonnet 4.6 → JSON spec → PPTX → PDF) + email variants.
Returns: `{ pptx_url, pdf_url, emails: {a, b}, deck_json, cost_cents, used_real }`.

### `POST /lead/<id>/outreach_event`
Body: `{ event_type: str, payload: dict|null, actor: str|null }`
Appends a row to `outreach_events` for cross-system tracking. Use this for
*business* events tied to a specific lead (email_sent, email_opened, voice_called).

### `POST /integration/agent_event`
**Use this** for *agent trace* events (steps inside Rian's loops). See § 3.

### `POST /rian/run_agent` / `GET /rian/run_agent/{run_id}`

**Outbound** — our API invokes Rian's deepagents stack. Used by the UI's
`[RUN RIAN AGENT]` button on the Pitch tab. See § 8 for the demo-mode
fallback contract.

Body (POST):
```json
{
  "agent": "lead_research" | "outreach_drafter",
  "target_lead_id": "lead_<uuid>" | null,
  "client_id": "client-greensolar-uk",
  "params": { "batch_size": 1, "thread_id": "<resume>" }
}
```

Returns immediately: `{ run_id, status: "queued" }`. The agent runs in a
background task and the run document is upserted into `rian_agent_runs`.
Poll `GET /rian/run_agent/{run_id}` until `status` is terminal (`done`,
`demo_mode`, `upstream_error`, or `error`).

GET response:
```json
{
  "run_id": "rian_<uuid>",
  "status": "done|demo_mode|upstream_error|error|queued|running",
  "agent": "lead_research",
  "target_lead_id": "lead_abc",
  "started_at": "ISO-8601",
  "finished_at": "ISO-8601",
  "output": {
    "status": "ok|demo_mode|upstream_error",
    "agent": "lead_research",
    "summary": "<final agent message>",
    "thread_id": "<langgraph thread for resume>",
    "message_count": 8,
    "metadata": { "target_lead_id": "lead_abc", ... }
  },
  "error": null
}
```

### `POST /realapi/companies-house/search` / `/officers` / `/company`
Server-side proxy to Companies House. Hides our CH key from the browser and
audit-logs every call. Use when Rian's agents need CH data without each agent
holding a key.

### `GET /lead/spend/session`
Aggregated `audit_log.cost_cents`. Both repos write to the same `audit_log`,
so this gives a unified spend view.

---

## 3. Webhook spec — `POST /integration/agent_event`

This is the inbound surface for Rian's agents to push agent traces / notes
back to us. Each event is persisted to `agent_events` and mirrored to
`audit_log` so spend + observability dashboards see the cross-system traffic.

### Request

```http
POST /integration/agent_event HTTP/1.1
Authorization: Bearer <token>
Content-Type: application/json

{
  "source": "rian-project1",
  "agent": "research",
  "event_type": "trace.tool_call",
  "lead_id": "lead_37f8a88b-17fc-495a-87a0-ca6e0822e8f3",
  "trace_id": "t_2026-05-02_research_001",
  "payload": {
    "tool": "companies_house_search",
    "input": {"name": "BARCLAYS PLC"},
    "output_summary": {"hits": 3, "top_ch_number": "00048839"}
  },
  "ts": "2026-05-02T15:24:23.883Z"
}
```

Required fields: `agent`, `event_type`. All others are optional.
- `source` defaults to `"rian-project1"` if omitted.
- `ts` is server-stamped (UTC) if omitted.
- `payload` must be a JSON object (no top-level arrays/strings).

### Response

```json
{
  "ok": true,
  "id": "ae_<uuid>",
  "auth_status": "authenticated|dev_open"
}
```

- `auth_status="dev_open"` means the server is running with no
  `RIAN_INTEGRATION_TOKEN` set — calls succeed unauthenticated. Useful for
  local dev. Production must set the token (see § 4).

### Suggested `event_type` taxonomy

Free-form, but stick to dotted lowercase so we can group cleanly in the
audit dashboard:

| `event_type` | When to send |
|---|---|
| `trace.start` | Beginning of an agent run |
| `trace.tool_call` | Each tool invocation (LLM tool use, REST call, etc.) |
| `trace.complete` | Successful end-of-run |
| `trace.error` | Unhandled exception in an agent loop |
| `lead.note` | Agent's research note attached to a specific `lead_id` |
| `lead.enrichment` | New facts discovered (e.g. director email) |
| `pipeline.heartbeat` | Long-running task pulse — paired with `trace_id` |

### Errors

| Status | Meaning |
|---|---|
| 401 | `RIAN_INTEGRATION_TOKEN` is set but Authorization header missing/wrong |
| 422 | Request body fails Pydantic validation (missing `agent`/`event_type`) |
| 500 | Mongo write failed (rare — surfaced; `agent_events` retains nothing) |

### Worked example (Python)

```python
import httpx, os
r = httpx.post(
    "http://localhost:8000/integration/agent_event",
    headers={"Authorization": f"Bearer {os.environ['RIAN_INTEGRATION_TOKEN']}"},
    json={
        "agent": "research",
        "event_type": "lead.note",
        "lead_id": "lead_abc",
        "payload": {"note": "Director also serves on board of X."},
    },
    timeout=10.0,
)
r.raise_for_status()
print(r.json())  # {"ok": True, "id": "ae_...", "auth_status": "authenticated"}
```

---

## 4. Auth — bearer token

Both directions share a single token: `RIAN_INTEGRATION_TOKEN`.

### Inbound (Rian → us)

- Server reads `RIAN_INTEGRATION_TOKEN` from env at request time (not boot).
- Caller sends `Authorization: Bearer <token>`.
- Token unset on the server → **dev-open** mode: requests succeed and are
  tagged `auth_status="dev_open"` in `audit_log.metadata`. Convenient locally,
  must not be the case in prod.
- Token set + header missing/wrong → **401**.
- Token set + header matches → 200, tagged `auth_status="authenticated"`.

> Why bearer not signed-request? We considered HMAC-signed requests
> (`X-Signature: hmac-sha256=<...>` over body) for replay protection. We
> picked bearer + TLS for v1 because (a) deadline pressure, (b) Atlas-side
> idempotency makes a replay no worse than a duplicate trace row.
> Upgrade path: when we move to prod, swap `_verify_token` for a HMAC verify
> in `app/routers/integration.py` — the route signature stays identical.

### Outbound (us → Rian)

The `scripts/sync_to_rian.sh` stub does NOT need a token — it pushes via SSH
git. If Rian wants webhook notifications, set `SOLARREACH_NOTIFY_WEBHOOK`
(Slack-compatible POST URL) and the sync script will hit it after a successful
push. If Rian's webhook needs auth, encode it in the URL or extend the script
to set a `Authorization` header (intentionally not done now — keeps the stub
trivially auditable).

### Secrets storage

- `.env.local` (gitignored) per CONTRACTS § 7 cardinal rule 1.
- Production: Atlas/AWS Secrets Manager. Never commit.
- Rotation: bump the env var on both sides simultaneously; the inbound route
  re-reads `os.environ` per request so no restart needed on our side.

---

## 5. Bulk data dumps — `exports/`

Generated by `scripts/export_for_rian.py`. Run via `scripts/sync_to_rian.sh`
(see § 0).

| File | Source | Format |
|---|---|---|
| `leads.jsonl` | All `leads` docs | JSONL (one doc per line) |
| `companies.jsonl` | All `companies` docs | JSONL |
| `directors.jsonl` | All `directors` docs | JSONL |
| `industry_benchmarks.json` | `solarreach_shared.industry_benchmarks.INDUSTRY_BENCHMARKS` | JSON object |
| `audit_summary.json` | Aggregates over `audit_log` (no PII) | JSON object |
| `manifest.json` | Row counts + generation timestamp | JSON object |

Ingestion contract: each `*.jsonl` line is a self-contained JSON object — no
multiline records. Field names follow CONTRACTS § 1 exactly. Any nested
`embedding` arrays in `companies.jsonl` are 1024-dim Voyage AI vectors; ignore
or re-embed as needed.

The sync script `scripts/sync_to_rian.sh` defaults to **dry-run** mode. Set
`SOLARREACH_RIAN_DO_PUSH=1` (or pass `--push`) to actually push to the `rian`
git remote on branch `data/exports`. The script never force-pushes — it aborts
if the remote rejects fast-forward.

---

## 6. Operational notes

- **Rate**: no formal limits yet. Rian's agents shouldn't exceed ~10 events/sec
  per agent. If we see sustained > 100 events/sec we will add a token-bucket.
- **Idempotency**: server-generated `_id` (`ae_<uuid>`) means duplicates create
  duplicate rows. Pass a stable `trace_id` if you need client-side dedup.
- **Backfill**: agents may resend old events with their original `ts` — we
  trust caller-supplied timestamps when present.
- **Spend visibility**: every `agent_event` writes a `cost_cents=0` row to
  `audit_log`. To attribute cost to a specific Rian agent run, set
  `payload.cost_cents` and we'll wire that into the dashboard in v2.

---

## 7. Cardinal rules (apply to BOTH repos)

Reproduced from CONTRACTS § 7 — non-negotiable:

1. NEVER commit `.env` or any file containing real keys.
2. NEVER auto-fire paid APIs without spend tracker visible + user-initiated click.
3. ALWAYS append `?authSource=admin` to local Mongo URIs.
4. ALWAYS hash recipient emails with sha256 in `audit_log`.
5. Both repos write to the SAME `audit_log` collection — coordinate `actor`
   strings (`agent_<name>` namespace per agent) so the dashboard can split.

---

## 8. Outbound: invoking Rian's deepagents stack from our API

Surface: `POST /rian/run_agent` (see § 2). Implementation lives in
`packages/api/app/services/rian_agent.py` + `packages/api/app/routers/rian.py`.

### Architecture

```
UI (PitchTab [RUN RIAN AGENT])
  └─ POST /rian/run_agent          (returns run_id immediately)
       └─ BackgroundTasks
            └─ services.rian_agent.run_rian_agent
                 ├─ try: import lead_agent.run_lead_agent_session
                 │    └─ asyncio.to_thread(run_lead_agent_session, ...)
                 │         └─ Rian's pymongo + deepagents + LangGraph loop
                 └─ except: return demo_mode dataclass
       └─ persist to rian_agent_runs + audit_log
  └─ GET /rian/run_agent/{run_id}  (polled every 2s by useRianAgentRun)
```

### Demo-mode contract

If `lead_agent` cannot be imported in the API venv, the route returns a
deterministic `demo_mode` payload — never a 5xx. This mirrors the existing
`voice_provider.RianProjectVoiceProvider` pattern (§ `services/voice_provider.py`).

`output.status` values:

| Value | Meaning |
|---|---|
| `ok` | Rian's stack ran, agent finished, summary in `output.summary` |
| `demo_mode` | `lead_agent` package isn't installed (or unknown agent kind) — UI shows amber badge |
| `upstream_error` | Stack ran but raised — `summary` carries the exception class + message |

The `RianRunStatus` on the run document (top-level `status`) collapses
`ok` → `done` so polling logic only watches one terminal state per "happy
path". `demo_mode` / `upstream_error` / `error` propagate through unchanged
so the UI can render distinct badges.

### Enabling real-agent mode

The API does **not** depend on Rian's package by default — keeps boot-time
imports light and CI green without LangGraph + 30 transitive packages.

To enable real runs in your dev venv:

```bash
# 1. Get Rian's repo on disk somewhere stable
git clone https://github.com/Rian-beep/solarreach-project1 ~/solarreach-project1

# 2. Install with agent extras into the API's venv
cd packages/api
uv pip install --editable "/path/to/solarreach-project1[agent]"

# 3. Restart the API. Verify with:
curl -sX POST http://localhost:8000/rian/run_agent \
  -H 'Content-Type: application/json' \
  -d '{"agent":"lead_research","target_lead_id":"lead_abc"}'
# Then poll /rian/run_agent/{run_id} — status should land at "done"
# with a non-stub summary, not "demo_mode".
```

The probe is silent (`logging.INFO`) — check the API log for
`lead_agent unavailable (...)` if you expect real mode but see demo_mode.

### Why this isn't a hard dependency

- `deepagents` + `langchain-mongodb` + `langgraph-checkpoint-mongodb` total
  ~30 packages and ~120 MB on disk. Installing them in our API container
  for the prod path inflates cold-start by 6-8 seconds.
- Rian's checkpointer needs Mongo Atlas, not mongomock. Forcing it as a
  dep would break our test suite (which uses `mongomock-motor`).
- The handshake stays loose: Rian can change his agent surface, ship new
  agents, or rewrite the lead researcher; our route contract is
  unaffected as long as `run_lead_agent_session(client_slug=..., batch_size=..., thread_id=...) → {thread_id, final_message, message_count}` holds.

If that signature changes, the failure mode is **`output.status = "upstream_error"`**
(caught in `_invoke_lead_agent_sync`), not a 500. The UI shows an amber badge
and we know to update the adapter.
