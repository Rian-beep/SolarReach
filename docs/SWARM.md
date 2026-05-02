# SolarReach Swarm — CrewAI Hierarchical Layer

> Manager-driven multi-agent orchestration on top of the existing API.

## Architecture

```
              ┌──────────────────────┐
              │ POST /swarm/run      │
              │ FastAPI BackgroundTask│
              └──────────┬───────────┘
                         │
                         ▼
       ┌───────────────────────────────────┐
       │ Manager (Opus 4.7)                │
       │ - plans, grounds in Atlas, fans   │
       │   out to specialists              │
       └────┬───────┬───────┬────────┬─────┘
            │       │       │        │
            ▼       ▼       ▼        ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ Google     │ │ PitchDeck  │ │ Outreach   │ │ ElevenLabs │
   │ Engineer   │ │ Builder    │ │ Editor     │ │ TTSAgent   │
   │ (Haiku 4.5)│ │ (Haiku 4.5)│ │ (Haiku 4.5)│ │ (Haiku 4.5)│
   └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘
         │              │              │              │
         ▼              ▼              ▼              ▼
   ┌─────────────────────────────────────────────────────────┐
   │                  MongoDB Atlas                           │
   │  • companies (vector index: companies_vector / 1024d)    │
   │  • leads / directors / inspire_polygons                  │
   │  • audit_log  ←  every paid call writes here             │
   └─────────────────────────────────────────────────────────┘
```

## Agents

| Agent | Model | Tools | Notes |
|---|---|---|---|
| Swarm Manager | `claude-opus-4-7` | atlas_vector_search, atlas_query | Plans + delegates. Allows delegation. |
| GoogleEngineer | `claude-haiku-4-5-20251001` | serpapi_search, atlas_vector_search | Architect; researches then delegates code-writing back. |
| PitchDeckBuilder | `claude-haiku-4-5-20251001` | atlas_vector_search, atlas_query, build_pptx | Reuses `codex_brain.generators.pptx_renderer` if importable; else inline minimal renderer. |
| OutreachEditor | `claude-haiku-4-5-20251001` | atlas_query, atlas_vector_search | Reads/writes leads, audit-logged, silent (one-line summary). |
| ElevenLabsTTSAgent | `claude-haiku-4-5-20251001` | elevenlabs_tts | Saves mp3 → `/tmp/swarm-tts/<task_id>.mp3`. |

## Tools

All tools return `{ok: bool, data, error: str|None}`. Failures never crash the crew.

- **atlas_vector_search(query, collection, k)** — Voyage AI 1024-dim vector search via `companies_vector`. Falls back to regex on `name` if the index is missing or `VOYAGE_API_KEY` absent.
- **atlas_query(filter, collection, limit)** — direct find().
- **serpapi_search(query, num)** — `google-search-results`. No-op without `SERPAPI_API_KEY`.
- **elevenlabs_tts(text, voice_id)** — ElevenLabs SDK. No-op without `ELEVENLABS_API_KEY`.
- **build_pptx(deck_json, lead_id, brand)** — wraps `codex_brain` renderer; falls back to inline 3-slide pptx.

## Quickstart

```bash
# install
cd packages/swarm
uv sync

# run from CLI (loads .env.local from repo root automatically)
uv run python -m swarm.main --objective "Generate pitch for top-3 EC2M leads"
```

## API integration

```bash
# kick off
curl -X POST http://localhost:8000/swarm/run \
  -H 'Content-Type: application/json' \
  -d '{"objective":"Score and pitch leads in EC1Y","target_lead_id":null}'
# → {"job_id":"job_<uuid>","status":"queued"}

# poll
curl http://localhost:8000/swarm/job/job_<uuid>
# → {"status":"running"|"done"|"error", "result":"...", "error":null}
```

## Audit & cost

Every tool call writes to `audit_log` (see CONTRACTS § 1) with:
- `actor = "agent_swarm"`
- `action ∈ {swarm.atlas.vector_search, swarm.atlas.query, swarm.serpapi.search, swarm.elevenlabs.tts, swarm.pptx.build}`
- `cost_cents` conservative estimate (SerpApi=1¢, TTS=3¢, Atlas reads=0¢, pptx=0¢)
- `metadata` per-action

The existing `/lead/spend/session` endpoint surfaces aggregated cost — swarm calls show up alongside codex + companies-house rows.

## Theme alignment

Per `docs/THEME-NARRATIVE.md`: "MongoDB IS the context engine." The swarm extends the existing pattern:
- Specialists discover peers via collection writes (not direct calls).
- Atlas Vector Search shrinks token context (specialists fetch only the slice they need by `lead_id`).
- The hierarchical CrewAI process gives Opus-4.7 the planner role; Haiku-4.5 specialists run concurrently.

## Known limits

- **In-process job store**: `/swarm/job/{id}` reads from a Python dict in the API process. Restart the API → job state is lost. For demo/judging this is fine; production should swap for Mongo or Redis.
- **CrewAI is sync internally**: we wrap with `asyncio.to_thread`, so the FastAPI event loop stays free, but a single API worker runs at most one crew at a time. Deploy multiple uvicorn workers for parallelism.
- **`build_pptx` minimal fallback** is bare-bones (3 slides); install `codex-brain` in the swarm venv to get the full 11-slide deck.
