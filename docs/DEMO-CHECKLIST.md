# SolarReach Demo Checklist — pre-submit

> The 90-second sanity sweep before you hit RECORD. For the full 7-minute narration see `docs/RUNBOOK-DEMO.md`.

## T-15 minutes — environment

- [ ] API up: `curl -s localhost:8000/health` → `{"status":"ok","services":{"mongo":true,"anthropic_reachable":true,"redis":true}}`
- [ ] Web up: `http://localhost:5173` loads, header shows `ATLAS LIVE` (green), spend pill at `£0.00`.
- [ ] Atlas connected (header pill green): if degraded, `make mongo-restart` then reload web.
- [ ] If running clean: `make demo-reset` (zeros spend tracker, clears panel cache).
- [ ] Pre-fetch top-5 flux/panels to avoid live latency: `make demo-prefetch` (or skip and live-call — Solar API is 5–15 s on first hit).

## T-2 minutes — final smoke

```bash
# Should return 10 leads (real seeded London/UK leads)
curl -s -X POST localhost:8000/scan \
  -H 'Content-Type: application/json' \
  -d '{"postcode":"EC1Y 8AF","client_id":"client-greensolar-uk","limit":50}' | python3 -m json.tool

# Bootstrap list (used by frontend on app load)
curl -s 'localhost:8000/leads?client_id=client-greensolar-uk&limit=5' | head -c 200

# Spend tracker
curl -s localhost:8000/lead/spend/session
```

## The 7-minute demo path

| t | Action | Atlas/AI angle |
|---|---|---|
| 0:00 | Open `http://localhost:5173` — UK-wide map, score-band markers, ATLAS LIVE pill | Bootstrap leads from `GET /leads` (Atlas + sort by composite_score) |
| 0:30 | Type `EC1Y 8AF` → SCAN | **Atlas Change Streams** stream `lead` events via SSE; markers pop in real-time |
| 1:30 | Filter score > 80 in HUD | **Atlas Search** (Lucene) on `leads_text` index |
| 2:00 | Click a high-score marker → camera flies down | Google Photorealistic 3D Tiles |
| 2:30 | Drawer Intel tab — payback hero, decision-maker | **Aggregation pipeline** $lookup joins owner + directors |
| 3:00 | Click "Build org chart" | Claude Opus 4.7 picks decision-maker; logged to `audit_log` (£0.05) |
| 3:30 | Click "Show solar radiance" | Real Google Solar API `dataLayers:get` → GeoTIFF → inferno PNG overlay |
| 4:00 | Click "Re-analyze roof" | Solar API `findClosest` per-panel layout, ray-cast clipped against INSPIRE freehold polygon (Atlas 2dsphere) |
| 4:30 | Pitch tab → Generate | Claude Sonnet 4.6 with prompt caching → JSON spec → python-pptx → PPTX/PDF |
| 5:30 | Voice tab → Rehearse | ElevenLabs ConvAI duplex audio; transcripts → Atlas **time-series** `calls_ts`; **Vector Search** for similar past calls |
| 6:30 | Close — show spend pill | Total session under £0.40, every cent in `audit_log` |

## The 5 Atlas features visible in the demo

1. **Document model with JSON-Schema validators** — `leads`, `companies`, `directors`, `inspire_polygons`, `clients`, `audit_log` (see CONTRACTS § 1).
2. **2dsphere geospatial index** — `leads.geo.point` and `inspire_polygons.polygon`; powers postcode → lead lookup and ray-cast clipping.
3. **Atlas Search (Lucene)** — `leads_text` index on address + company name + premises type; powers HUD filter.
4. **Atlas Vector Search** — `companies_vector` (1024-dim Voyage AI cosine); powers "similar past calls" panel in the Voice tab.
5. **Atlas Change Streams** — backs the SSE that streams scan results to the map in real-time (see `services/change_streams.py` + `routers/scan.py`).

Plus: aggregation pipelines (`$lookup`, `$group`), time-series collections (`calls_ts`, `energy_yield_ts`, `weather_ts`).

## Fallbacks if something blows up mid-demo

| Symptom | One-liner |
|---|---|
| Solar API 403 | `make demo-fallback-flux` (uses pre-cached raster) |
| ElevenLabs quota | `VOICE_PROVIDER=fireworks make web-restart` |
| Anthropic rate-limit | `USE_CACHED_PITCH=1 make api-restart` |
| Mongo blip | `make mongo-restart`; SSE auto-reconnects |
| Map tiles not loading | Reload page; sessions are 60 s |

## Post-demo

```bash
make demo-reset    # zero spend tracker for next run
```

— A10
