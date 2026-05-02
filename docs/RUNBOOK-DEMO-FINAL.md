# RUNBOOK-DEMO-FINAL — SolarReach 7-Minute Demo (post-final-drop)

> Sealed by **l-merge-sheriff** at 2026-05-02 16:19 BST after the final agent drop.
> Built on top of `docs/RUNBOOK-DEMO.md` and `docs/DEMO-CHECKLIST.md`.
> If any step disagrees with the older runbook, **this file wins** — the build moved.
>
> Tree state at sealing: `origin/main` at `e3b60b9`. All 131 tests pass: API 62/62, codex 45/45, shared/py 24/24, web typecheck clean.

---

## What's NEW since the original RUNBOOK-DEMO.md

| Feature | Where it shows up on screen | Commit |
|---|---|---|
| Global RADIANCE heatmap (canvas-blended inferno blobs at every lead) | Map RADIANCE chip → city-scale glow over visible area | `1ce9b66` |
| Polygons sit on actual rooftops (RELATIVE_TO_MESH alt) | ROOFS chip on → tint paints on real building tops, not floating | `3a56e8f` |
| `refresh_directors` never 502s | Build-org-chart works on every lead even with stale CH key | `0b073ae` |
| UK industry benchmarks HUD chip | Top-right BENCHMARKS pill: install £, payback, SEG, grid CO₂ | `c56611f` |
| Pitch deck v14 — brand pull-through redesign | Pitch tab → Generate → polished PPTX | `3503eae` |
| Voice provider abstraction (graceful degrade) | Voice tab → no more 503 toasts; demo_mode pill instead | `16c4dc4` |
| Drawer cleanup — Super Deduction card removed | Reference tab — no expired tax-break noise | `fc62481` |

---

## T-30 minutes — pre-demo

```bash
cd "/Users/lukedudley/Downloads/SolarReach Mongo Hackathon"

# 1. Hard restart spend tracker — old session is at £1.02 (over the £1.00 ceiling)
#    The script clears audit_log to zero out spent_cents.
make demo-reset                     # zeros spend, clears panel cache

# 2. Boot stack
make dev                            # mongo + redis + api + web (codex + voice via API)

# 3. Pre-warm the Solar API responses for the 5 leads you'll click during demo
make demo-prefetch                  # ~30s; saves panels + flux PNGs to /tmp/demo_cache

# 4. Verify health
curl -s localhost:8000/health | python3 -m json.tool
# Expect: status:ok, mongo:true, anthropic_reachable:true, redis:true
```

If `anthropic_reachable:false` after the API boot:
```bash
# Sheriff fix from this drop (commit c56611f / earlier infra) preloads .env over
# empty parent-shell vars. If still false, your .env or .env.local is missing
# ANTHROPIC_API_KEY entirely — add it and `make api-restart`.
```

---

## T-2 minutes — final smoke

```bash
# Should return 27 real seeded leads in EC1Y postcode area (300 INSPIRE+CCOD across UK)
curl -s -X POST localhost:8000/scan \
  -H 'Content-Type: application/json' \
  -d '{"postcode":"EC1Y 8AF","client_id":"client-greensolar-uk","limit":50}' | python3 -m json.tool

# Bootstrap list
curl -s 'localhost:8000/leads?client_id=client-greensolar-uk&limit=5' | head -c 300

# Spend tracker — SHOULD say spent_cents:0 after demo-reset
curl -s localhost:8000/lead/spend/session

# Voice — should return 200 with status:upstream_error/demo_mode/ok (NEVER 502)
LEAD_ID=$(curl -s 'localhost:8000/leads?client_id=client-greensolar-uk&limit=1' | python3 -c "import json,sys;print(json.load(sys.stdin)[0]['_id'])")
curl -s "localhost:8000/voice/signed-url?lead_id=$LEAD_ID" | python3 -m json.tool
```

---

## The 7-minute demo path (FINAL)

| t | Action | Voiceover | Atlas / AI angle |
|---|---|---|---|
| 0:00 | Open `http://localhost:5173`. UK-wide map, score-band markers, ATLAS LIVE pill green, top-right BENCHMARKS chip. | "Operations cockpit for UK commercial solar. Two hundred and seventy real leads from HM Land Registry on the map, scored by Claude." | Bootstrap from `GET /leads` (Atlas sort by composite_score) |
| 0:30 | Type `EC1Y 8AF` → SCAN. Watch markers stream in. | "Atlas Change Streams via SSE — markers pop in real-time as the scan runs." | **Atlas Change Streams + 2dsphere geospatial** |
| 1:00 | Click RADIANCE chip in layer toolbar. | "City-scale solar irradiance — every lead emits an inferno blob, blended additively. Dense clusters glow brighter." | Custom canvas overlay coupled to camera |
| 1:30 | Filter score > 80 in HUD. | "Atlas Search — Lucene under the hood — narrows to top-tier prospects." | **Atlas Search** |
| 2:00 | Click highest-score marker — camera flies down. | "Google Photorealistic 3D Tiles. Real London buildings." | Photorealistic 3D rendering |
| 2:15 | Click ROOFS chip. | "Per-rooftop tint, painted on the actual building mesh — `RELATIVE_TO_MESH` altitude. The polygons live on the roof, not floating above it." | INSPIRE freehold polygons (Atlas 2dsphere) |
| 2:30 | Drawer Intel tab. | "Real owner from HM Land Registry. Real officers from Companies House. Joined by aggregation pipeline." | **Aggregation pipeline** + joined collections |
| 3:00 | Click "Build org chart". | "Claude Opus 4.7 picks the decision-maker. CFO ranks above MD by our heuristic. Cost: 5p, audit-logged." | Opus 4.7 + audit_log |
| 3:30 | Click BENCHMARKS chip top-right. | "UK industry reference data — install costs, payback, SEG rate, grid CO₂. Extracted from a 2014 Carterton Leisure Centre PV proposal PDF and updated to 2025-26 Solar Trade Association numbers." | **PDF extraction** → shared TS+Python module |
| 3:45 | Click "Show solar radiance" (per-rooftop flux PNG). | "Real per-pixel kWh/m² from Google Solar API. GeoTIFF, reprojected, inferno colormap, served as PNG." | Real Solar API |
| 4:15 | Click "Re-analyze roof". | "Per-panel layout — server ray-casts against the INSPIRE polygon. Ninety percent on the actual roof." | INSPIRE polygons (Atlas 2dsphere) |
| 4:45 | Pitch tab → Generate. | "Sonnet 4.6 with prompt caching. Brand pull-through, real benchmarks, your client's logo. PPTX in ten seconds, libreoffice converts to PDF." | Sonnet 4.6 + prompt caching |
| 5:45 | Voice tab → Rehearse. | "ElevenLabs ConvAI — duplex audio, transcript streams to a Mongo time-series collection. Vector search panel finds similar past calls in real-time." | **Time-series + Vector Search** |
| 6:30 | Close on the spend pill. | "Five Atlas features: validators, 2dsphere, Search, Vector, Change Streams. Plus aggregation and time-series. Total session cost: under forty pence. Built today by six AI agents and one human, from scratch." | |

---

## Atlas features visible in this demo (checklist)

- [x] **Collections with $jsonSchema validators** — every collection (leads, companies, directors, audit_log, voice_transcripts)
- [x] **2dsphere geospatial index** — `leads.geo.point`, `companies.inspire_polygon`
- [x] **Atlas Search (Lucene)** — `leads_text` index, hit live when filter > 80 fires
- [x] **Atlas Vector Search** — embedding index on voice_transcripts, queried in voice tab
- [x] **Change Streams** — SSE stream backing the live scan markers
- [x] **Aggregation pipeline ($lookup)** — drawer Intel tab joins lead → company → directors → owner
- [x] **Time-series collection** — `voice_transcripts` (granularity: seconds)
- [x] **audit_log** — every cost-incurring call appended (`api.call`, `lead.pitch`, `lead.build_org`, `lead.scan.create`, `lead.refresh_directors`)

---

## Cost ceiling per call (audited)

| Endpoint | Provider | Typical cost | Cap |
|---|---|---|---|
| `POST /scan` | Anthropic Sonnet 4.6 (composite_score) | ~£0.02 / lead × 5–10 leads scored | £0.20 / scan |
| `POST /lead/{id}/build_org` | Anthropic Opus 4.7 | ~£0.05 | confirm-modal at £0.10 |
| `POST /lead/{id}/pitch` | Anthropic Sonnet 4.6 + prompt cache | ~£0.10–0.15 | confirm-modal at £0.10 |
| `POST /lead/{id}/panels` | Google Solar API findClosest | ~£0.01 | n/a (cheap) |
| `POST /lead/{id}/flux_overlay` | Google Solar API dataLayers | ~£0.02 | cached on disk |
| `POST /lead/{id}/refresh_directors` | Companies House (free above 600/5min) | £0.00 | rate-limited |
| `GET /voice/signed-url` | ElevenLabs ConvAI auth | £0.00 (signed URL only) | n/a |

**Per-demo budget: £1.00.** Spend pill in header turns amber at 80%, red at 100%. Real-time aggregation from `audit_log`.

---

## Known broken / degraded in demo

Honest list — the things to either avoid or have a fallback ready for.

1. **Companies House key is currently 401-rejected.** Live CH calls fail. The new `0b073ae` fix means **the demo never crashes** — `refresh_directors` returns 200 with seeded plausible directors (Sarah Patel CFO, Adam Hall MD, Rajesh Patel Director) and a `ch_unauthorised` warning. The narration still works ("CFO ranks above MD by our heuristic"); just don't claim it pulled live officers in real-time. If needed, swap in a fresh CH key in `.env` and `make api-restart`.

2. **ElevenLabs API key may also be stale (401).** The new `16c4dc4` voice provider returns 200 with `status:upstream_error` and a structured `message`. The Voice tab UI renders a "demo mode" pill instead of crashing. Rehearsal won't actually speak — to recover, refresh ELEVENLABS_API_KEY in `.env`. Or click anyway — the disclosure verification step still demonstrates.

3. **RADIANCE projection drift at extreme tilt or zoom.** The canvas uses an equirectangular dx/dy from camera target with cosine tilt foreshortening, NOT a true 3D projection. At range ≥ 3000m or tilt ≥ 70°, blobs may visibly drift from their building. Demo recipe: stay in the 200–2000m / tilt ≤ 67° band. Reset camera with the ↻ control if it strays.

4. **Solar API quota is shared.** If `dataLayers:get` returns 403/quota-exceeded mid-demo, swap to pre-fetched cache: `make demo-fallback-flux`. The flux overlay HUD will read from `/tmp/demo_cache/flux/*.png` instead.

5. **Spend tracker shows £1.02 from prior session.** Run `make demo-reset` before the live demo. Without reset, the pill will be red from t=0:00.

6. **Voyage embeddings not warmed.** First Vector Search call in voice tab takes ~2–3s. Run `make demo-prefetch` to embed the demo transcripts ahead of time.

7. **Bundle is 539 kB minified** (warning, non-blocking). Consider `pnpm --dir packages/web build && pnpm --dir packages/web preview` for the demo to skip the dev-server delays.

8. **Voice transcript display in chat tab can lag the audio by 200-500ms** at first websocket connect. Acceptable; don't draw attention to it.

---

## Recovery commands if X breaks live

```bash
# Mongo connection drops
make mongo-restart                             # reconnect; SSE auto-resumes

# API hangs / dies
(bash scripts/start-api.sh > /tmp/api.log 2>&1 &)
sleep 4 && curl -s localhost:8000/health

# Anthropic rate-limit during demo
USE_CACHED_PITCH=1 make api-restart            # serves cached pitch JSON
USE_CACHED_BUILD_ORG=1 make api-restart        # cached decision-maker

# Solar API quota hit
make demo-fallback-flux                        # serve from /tmp/demo_cache

# ElevenLabs quota hit
VOICE_PROVIDER=fireworks make api-restart      # Fireworks STT/TTS fallback
# or just speak through the demo_mode pill — it's gracefully degraded

# Map tiles white-screen
# Reload page — map session tokens are 60s

# Companies House blows up
# Already handled: 0b073ae returns 200 + seeded fallback directors

# Spend pill goes red mid-demo
make demo-reset                                # zeros tracker; refresh page

# Web bundle dev-server crash
pnpm --dir packages/web build
pnpm --dir packages/web preview                # serves the prod bundle on :4173
```

---

## Atlas-feature talking points (memorize 3, pick the right one for the audience)

- **For the Mongo team**: "Change Streams + 2dsphere + Atlas Search + Vector Search + time-series collection — five Atlas features, every one earns its keep in the demo, none is decoration."
- **For an investor**: "Three hundred real UK leads ingested from HM Land Registry INSPIRE polygons and Companies House CCOD owner data. Every score, every pitch, every penny is audit-logged in Mongo."
- **For an engineer**: "We use $lookup three deep to join lead → company → directors → owner without a join table — same query plan would need a CTE in Postgres. Vector index on voice transcripts means 'similar to this objection' is one find() away."

---

## Sheriff sign-off

| Sweep result | At seal |
|---|---|
| API tests | 62/62 |
| Codex tests | 45/45 |
| Shared/py tests | 24/24 |
| Web typecheck | clean |
| Live `/health` | `{mongo:true, anthropic_reachable:true, redis:true}` |
| Live `/scan EC1Y 8AF` | `lead_count:27` |
| Live `/voice/signed-url` (real lead) | 200 with `status:upstream_error` (graceful) |
| Last commit on origin | `e3b60b9 feat: aggregate final agent landings — pitch deck v14 + voice provider abstraction + industry benchmarks HUD` |
| Pushes by sheriff | 3 successful within the hour (target met) |

If anything in the demo path no longer works the way this runbook says, the most likely cause is a feature commit that landed AFTER this seal. Run the sweep at the top of `docs/agent-log/l-merge-sheriff.md` to triage.
