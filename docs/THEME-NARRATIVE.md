# Theme — Multi-Agent Collaboration

> **The framing for judges. Memorize before pitching.**

## The hackathon ask

> "Develop a multi-agent system in which specialized agents explore, assign tasks, and communicate with one another, using MongoDB to organize and oversee contexts. How do agents convey their skills, identify suitable peers for a sub-task, share context effectively within token limits, and perform intricate tasks resulting from successful collaborations?"

## How SolarReach answers it

**MongoDB IS the context engine.** Five specialized agents share a single Mongo state-store and coordinate through Atlas-native primitives:

| Agent | Skill | Reads from Mongo | Writes to Mongo | How it finds peers |
|---|---|---|---|---|
| **Scoring Agent** | Composite score, ROI gate | `inspire_polygons`, `companies` (CCOD/OCOD) | `leads` (composite_score) | Triggers next agent via change stream `leads.composite_score >= 70` |
| **Decision-Maker Inferer** | Identify the buyer | `directors`, prompt template | `leads.decision_maker` | Listens on `leads.directors` change |
| **Codex Brain** | Generate pitch deck + email A/B | `leads`, `clients`, `directors`, decision-maker | `leads.pitch_artifacts`, `audit_log` | Triggered by frontend `/pitch` request |
| **Voice Agent (ElevenLabs ConvAI)** | Live duplex objection-handling call | `leads`, `clients`, `decision_maker`, vector-similar past calls | `calls_ts` (time-series transcript), `audit_log` | Vector-similar peer lookup against `calls_ts.embedding` (Voyage 1024-dim) |
| **Optimizer Agent** | Rewrite losing email variants | `outreach_variants`, `webhooks_inbox` | `outreach_variants.rewritten` | Atlas Trigger on webhook ingest |

## How agents convey skills

Each agent registers a capabilities document in a `agent_registry` Mongo collection:
```json
{
  "_id": "agent_codex_brain",
  "skills": ["pitch_deck.pptx", "email.ab", "context_inject.from_lead"],
  "input_schema_ref": "/schemas/codex_input.schema.json",
  "cost_per_invocation_cents": 5,
  "p50_latency_ms": 8200
}
```
Other agents query `agent_registry` to **discover** suitable peers (e.g. Voice Agent looks up "objection_handle.fast" → finds Haiku sidecar).

## How agents share context within token limits

- **MongoDB as out-of-band store**: rather than pass full `Lead` docs through prompts, agents pass a `lead_id` and the receiver fetches its own slice (Codex needs `decision_maker`+`financial`; Voice needs `decision_maker`+`panels_count`+`payback_years`).
- **Atlas Vector Search** for context retrieval: instead of stuffing all past calls into the system prompt, Voice agent queries `calls_ts.embedding` for the 3 most-similar prior conversations and only includes those snippets.
- **Prompt caching** (Anthropic ephemeral cache, 5-min TTL): the system prompt + client config is cached once per session, every per-lead pitch generation pays only for the variable suffix → 70%+ cache hit rate, 90% cost reduction on system tokens.

## How collaborations succeed

The end-to-end pipeline is one prolonged multi-agent collaboration:

```
postcode in
  → Scoring Agent populates leads (uses change stream to fan out)
  → Decision-Maker Inferer enriches eligible leads (composite_score >= 70 ROI gate)
  → frontend user clicks "Generate pitch"
  → Codex Brain reads enriched lead, writes pitch artifacts
  → user clicks "Rehearse"
  → Voice Agent fetches lead + decision_maker + similar past calls (vector)
  → live conversation runs, transcript persists to calls_ts
  → Optimizer watches for failures, rewrites email variants via SendGrid webhook trigger
```

Every hop is **MongoDB-mediated**. No agent calls another agent directly. The collection IS the message bus.

## Atlas features deliberately exposed

| Feature | Where in the demo | Why MongoDB-specific |
|---|---|---|
| Collections + JSON Schema validators | every collection | type-safety at write time |
| 2dsphere geospatial | `leads.geo.point`, `inspire_polygons.polygon` | radius queries against London + Bristol |
| Atlas Search | `companies_text` (lucene) | full-text owner lookup |
| Atlas Vector Search | `companies_vector`, `calls_ts.embedding` | semantic similarity for cross-call learning |
| Change Streams | scan SSE pipe | live UI without polling |
| Aggregation pipelines | composite score `$bucketAuto`, leads-companies-directors join | server-side computation |
| Time-series | `calls_ts`, `weather_ts`, `energy_yield_ts` | granular meta-indexed time data |

## The 30-second judge pitch

> "Five specialized agents — Scoring, Decision-Maker Inferer, Codex Brain, Voice, Optimizer — coordinate through MongoDB Atlas as the context engine. Agents discover peers via an `agent_registry` collection, share context via collection writes (not prompt-stuffing), and use Atlas Vector Search for semantic peer-context retrieval to stay within token limits. Change streams trigger the next agent in pipeline. The result: a UK rooftop, joined to its real Land Registry owner, scored, pitched, and conversed-with by AI — all on Atlas."
