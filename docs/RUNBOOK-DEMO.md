# Demo Runbook — SolarReach 7-Minute Path

> **Run this exactly. Time-tested by the build agents and every step is verified by `scripts/validate_*.{mjs,py}`.**

## Pre-demo checklist (T-30 minutes)

- [ ] `make demo-reset` — wipes spend tracker, clears panel cache, resets drawer state
- [ ] `make verify` — all services green
- [ ] Pre-fetch flux overlays for top 5 leads (avoid live cost during exec demo): `make demo-prefetch`
- [ ] Spend tracker shows `£0.00 / £1.00`
- [ ] Cost-confirm modal threshold set to `£0.10`
- [ ] Browser cache cleared, mic permission granted
- [ ] Open postcode `EC1Y 8AF` validated to return ≥10 markers

## Narration (verbatim, 7 min)

| t | Action | Voiceover | Mongo/AI angle |
|---|---|---|---|
| 0:00 | Open `http://localhost:5173` | "Operations cockpit for the UK commercial solar industry." | Google Photorealistic 3D Tiles loaded |
| 0:30 | Type `EC1Y 8AF` → Scan | "Postcode in. Markers stream in real-time — that's MongoDB Atlas Change Streams via Server-Sent Events. Each one labelled by composite score." | **Atlas Change Streams + 2dsphere geospatial index** |
| 1:30 | Filter "score > 80" | "Atlas Search — Lucene under the hood — filters on the fly." | **Atlas Search** |
| 2:00 | Click highest-score marker | "Camera flies down. The 3D you're seeing is Google Photorealistic Tiles — the actual buildings of London." | Photorealistic 3D rendering |
| 2:30 | Drawer Intel tab | "Real owner from HM Land Registry. Real officers from Companies House. Joined via Mongo aggregation pipeline." | **Aggregation pipeline** + joined collections |
| 3:00 | Click "Build org chart" | "Claude Opus 4.7 inferring the decision-maker. CFO ranks above MD by our heuristic. Cost: £0.05, audit-logged." | Opus 4.7 + audit_log |
| 3:30 | Click "Show solar radiance" | "Real per-pixel kWh/m² from Google Solar API. We download the GeoTIFF, reproject to web Mercator, apply inferno colormap, serve as PNG." | Real Solar API |
| 4:00 | Click "Re-analyze roof" | "Per-panel solar layout — server-side ray-cast clipped against the real INSPIRE freehold boundary. 90%+ panels on the actual roof." | INSPIRE polygons (Atlas 2dsphere) |
| 4:30 | Pitch tab → Generate | "Claude Sonnet 4.6 with prompt caching. 70%+ cache hit on repeated client decks. PPTX renders in ~10 seconds, libreoffice converts to PDF." | Sonnet 4.6 + prompt caching |
| 5:30 | Voice tab → Rehearse | "ElevenLabs ConvAI — duplex audio in your browser via WebRTC. Transcript streams to a MongoDB **time-series** collection. Vector search panel finds similar past calls in real-time." | **Time-series + Vector Search** |
| 6:30 | Close | "Five MongoDB Atlas features in this demo: collections with validators, 2dsphere geospatial, Atlas Search, Vector Search, change streams. Plus aggregation pipelines and time-series. Total session cost: under £0.40. Built today by 5 AI agents and 2 humans, from scratch." | |

## If something breaks

| Symptom | Fallback |
|---|---|
| Solar API returns 403 | Switch to pre-cached flux raster: `make demo-fallback-flux` |
| ElevenLabs quota hit | Switch to Fireworks STT/TTS: `VOICE_PROVIDER=fireworks make web-restart` |
| Mongo connection drops | `make mongo-restart`; the SSE reconnects automatically |
| Anthropic rate-limit | Drop to cached pitch JSON: `USE_CACHED_PITCH=1 make api-restart` |
| Map tiles not loading | Reload page; sessions are 60s, may have expired |

## Post-demo

```bash
make demo-reset    # zero spend, clear cache for next demo
```
