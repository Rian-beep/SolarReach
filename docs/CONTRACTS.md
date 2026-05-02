# SolarReach API & Component Contracts

> **The single source of truth for every interface between agents.**
> Every agent reads this before changing payload shapes. Every change requires updating this doc.

Last updated: 2026-05-02

---

## 1. MongoDB Collections (canonical schemas)

JSON Schema source-of-truth lives in `packages/shared/schemas/*.schema.json`. Mirrored to TS in `packages/shared/ts/src/models.ts` and Py in `packages/shared/py/solarreach_shared/models.py`.

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

### `inspire_polygons`
```json
{
  "_id": "inspire_<uuid>",
  "inspire_id": "abc123",
  "borough": "London Borough of Camden",
  "polygon": { "type": "Polygon", "coordinates": [[[lng,lat],...]] },
  "area_m2_approx": 1240,
  "centroid": { "type": "Point", "coordinates": [lng, lat] }
}
```

Indexes:
- `{ "polygon": "2dsphere" }`
- `{ "centroid": "2dsphere" }`
- `{ "inspire_id": 1 }`

### `clients`
```json
{
  "_id": "client-greensolar-uk",
  "name": "GreenSolar UK",
  "branding": { "primary": "#0F172A", "logo_url": "..." },
  "pricing": { "panel_unit_gbp": 850, "install_per_kw_gbp": 180 },
  "session_budget_gbp": 1.00
}
```

### `audit_log` (append-only)
```json
{
  "_id": "audit_<uuid>",
  "ts": "ISO-8601",
  "actor": "user|system|agent_<name>",
  "action": "lead.scan|lead.pitch|voice.session|api.call",
  "lead_id": "lead_<uuid>|null",
  "cost_cents": 5,
  "recipient_sha256": "sha256-of-email|null",
  "metadata": { /* action-specific */ }
}
```

### Time-series collections (Atlas-native)
- `calls_ts` — granularity `seconds`, meta=`lead_id`, fields=`role, text, embedding`
- `energy_yield_ts` — granularity `hours`, meta=`building_id`, fields=`kwh, weather_cell`
- `weather_ts` — granularity `hours`, meta=`cell_id`, fields=`irradiance, temp_c, cloud_pct`

---

## 2. REST API Endpoints (FastAPI)

Base URL: `http://localhost:8000` (dev) · port `8000`

### `POST /scan`
**Body**: `{ "postcode": "EC1Y 8AF", "client_id": "client-greensolar-uk", "limit": 50 }`
**Returns**: `{ "scan_id": "...", "lead_count": 50, "stream_url": "/scan/<scan_id>/stream" }`

### `GET /scan/<scan_id>/stream` (SSE)
Server-sent events streaming `{type: "lead", data: <Lead>}` then `{type: "done"}`.

### `GET /lead/<id>`
**Returns**: full Lead doc (see schema above) with joined company + directors.

### `POST /lead/<id>/flux_overlay`
**Returns**: `{ "url": "/lead/<id>/flux_overlay/raster.png", "bbox": [w,s,e,n], "vmin": 2.1, "vmax": 5.4 }`
Implementation: Solar API `dataLayers:get` → GeoTIFF → reproject to EPSG:4326 → inferno colormap → PNG.

### `POST /lead/<id>/panels`
**Returns**: `{ "panels": [...], "annual_kwh": 10080, "clipped_at": "..." }`
Implementation: Solar API `findClosest` → server-side ray-cast clip against `rooftop_polygon` → persist `panel_layout`.

### `POST /lead/<id>/refresh_directors`
**Returns**: `{ "directors": [...] }`
Implementation: Companies House `/company/<ch_number>/officers`.

### `POST /lead/<id>/build_org`
**Returns**: `{ "decision_maker": {name, role, confidence, rationale} }`
Implementation: Opus 4.7 over directors list using `decision_maker_inference.md` prompt.

### `POST /lead/<id>/pitch`
**Body**: `{ "client_id": "client-greensolar-uk" }`
**Returns**: `{ "pptx_url": "/static/...", "pdf_url": "/static/...", "emails": {a:..., b:...}, "deck_json": {...} }`
Implementation: Sonnet 4.6 (prompt-cached) → JSON spec → python-pptx → libreoffice headless → PDF.

### `GET /lead/<id>/pitch/download?format=pdf|pptx`
Stream the file.

### `GET /lead/spend/session`
**Returns**: `{ "spent_cents": 12, "budget_cents": 100, "budget_pct": 0.12 }`

### `POST /admin/client/<slug>`
Update client config (branding, pricing).

### `POST /financial/calculator`
**Body**: `{ "address", "annual_kwh", "premises_type" }`
**Returns**: full financial breakdown for residential calculator mode.

### `GET /voice/signed-url?lead_id=<id>`
**Returns**: `{ "signed_url": "...", "agent_id": "...", "system_prompt_filled": "..." }`
Implementation: ElevenLabs `/v1/convai/conversation/get_signed_url` + context injection.

### `GET /health`
**Returns**: `{ "status": "ok", "services": {mongo, redis, anthropic_reachable} }`

---

## 3. SSE Event Schema

`/scan/<scan_id>/stream` emits text/event-stream:
```
event: lead
data: {"_id": "lead_...", "address": "...", "scores": {...}, "geo": {...}}

event: progress
data: {"completed": 12, "total": 50}

event: done
data: {"scan_id": "...", "lead_count": 50}
```

---

## 4. Frontend Component Contracts

### `<MapSlot />` (USER-OWNED — Google Maps lane)
**Props**: `{ leads: Lead[], selectedLeadId: string|null, onLeadClick: (id) => void, fluxOverlay: FluxOverlay|null, panelLayout: PanelLayout|null }`
**Renders**: Google `<gmp-map-3d>` with markers + flux PNG + panels.
**Lazy-loaded**: dynamic import to keep main bundle small.

### `<LeadDrawer />` (A3-owned)
4 tabs: Intel · Pitch · Voice · Reference. Reads from `useLeadStore()` (Zustand).

### `<SpendIndicator />` (A3-owned)
Polls `/lead/spend/session` every 4s. Amber at 60%, magenta+pulse at 90%.

### `<VoiceRehearsalSection />` (A3-owned, A4 wires backend)
Calls `/voice/signed-url` on mount, opens `Conversation.startSession({signedUrl})`.

---

## 5. Frontend Store Schemas (Zustand)

### `useLeadStore`
```ts
{
  leads: Lead[],
  selectedLeadId: string | null,
  filter: { score_min: number, premises_type: string|null, q: string|null },
  scan: (postcode: string) => Promise<void>,
  select: (id: string) => void,
  refreshFlux: (id: string) => Promise<void>,
}
```

### `useSpendStore`
```ts
{ spent_cents: number, budget_cents: number, budget_pct: number, refresh: () => void }
```

### `useVoiceStore`
```ts
{ session: ConvSession|null, transcript: TranscriptChunk[], start: (leadId) => void, stop: () => void }
```

---

## 6. Cross-agent Integration Points

| From → To | Contract | Owner |
|---|---|---|
| Foundation → API | `packages/shared/schemas/*.json` (loaded as Pydantic at API startup) | A1 + A2 |
| Foundation → Codex | `Lead` Pydantic model | A1 + A4 |
| API → Frontend | OpenAPI auto-gen at `/openapi.json` (typed via `openapi-typescript`) | A2 + A3 |
| Frontend → User (Maps) | `<MapSlot />` props above; user fills implementation | A3 + Lead |
| Frontend → API | TanStack Query hooks in `packages/web/src/lib/api.ts` | A3 |
| Codex → API | Async via `POST /lead/<id>/pitch`; result streamed to job table | A4 + A2 |
| Voice → API | `/voice/signed-url` proxy hides ElevenLabs key | A5 + A2 |

---

## 7. Hard Rules (cardinal — agents enforce these)

1. NEVER commit `.env` or any file containing real keys.
2. NEVER set Google API key Application restrictions to HTTP referrer (breaks server calls).
3. NEVER overwrite an INSPIRE polygon with a Solar API bbox.
4. NEVER auto-fire paid APIs without spend tracker visible + user-initiated click.
5. ALWAYS server-side ray-cast clip panels against `rooftop_polygon` before persisting.
6. ALWAYS append `?authSource=admin` to local Mongo URIs.
7. ALWAYS hash recipient emails with sha256 in `audit_log`.
8. ALWAYS verify AI disclosure in voice agent system prompt before issuing signed URL.
