# A6 — Solar API Backend log

## 2026-05-02

### 13:21 — Bootstrap
- Mission: replace mock flux + panels stubs with REAL Google Solar API.
- Read CONTRACTS § 2 (`/lead/:id/flux_overlay`, `/lead/:id/panels`).
- Read existing stubs in `app/routers/{flux,panels}.py` — keep payload shapes
  identical so frontend/MapSlot doesn't break.
- Confirmed `.env.local` has `GOOGLE_MAPS_API_KEY` populated, surfaced via
  `Settings.google_maps_api_key`.
- Cardinal rules pinned: 80m findClosest reject, INSPIRE polygon preserved,
  meters-based panel rotation (`theta = -azimuth`), 2nd–98th percentile
  stretch, mask negative nodata, audit BEFORE call, append `?key=` to
  GeoTIFF download URLs (separate origin still needs auth).
- API key restriction note: must NOT be HTTP-referrer restricted on Cloud
  Console (server-side calls fail 403 API_KEY_HTTP_REFERRER_BLOCKED).

### 13:30 — Implementation
- `app/services/solar_api.py` — full async wrapper:
  - `find_closest_building()` — rejects > 80m drift.
  - `get_data_layers()` — view=FULL_LAYERS.
  - `download_geotiff()` — appends `?key=` (cardinal rule).
  - `geotiff_to_inferno_png()` — rasterio reproject EPSG:4326, 2-98%
    stretch, inferno colormap, nodata transparent alpha.
  - `panels_from_solar_api()` — meters-rotation `theta = -azimuth`,
    ray-cast clip against rooftop polygon.
- `app/routers/flux.py` — REPLACED stub; 24h cache by lead_id, persists
  `flux_overlay`. Falls back to stub-shape mock if key missing or API fails.
- `app/routers/panels.py` — REPLACED stub; preserves INSPIRE polygon,
  ray-cast clips, persists `panel_layout` with
  `clip_method="inspire_polygon_raycast"`.
- `app/main.py` — mounted `/static/flux` -> `/tmp/flux`; created on
  lifespan startup.
- `pyproject.toml` — added rasterio, pyproj, matplotlib, pillow, numpy.
- `tests/test_solar_api.py` — 7 tests with respx-mocked HTTP:
  1. findClosest > 80m raises
  2. findClosest ≤ 80m accepts
  3. dataLayers URL has key appended
  4. GeoTIFF download URL appends `?key=`
  5. inferno PNG bbox + vmin/vmax sane
  6. panels rotation math (south azimuth = N-S aligned)
  7. ray-cast clip discards out-of-polygon panels

### Contract changes
- None. Both endpoint payloads match CONTRACTS § 2 verbatim and
  `lead.flux_overlay` / `lead.panel_layout` shapes match § 1.

### Cross-agent notes
- A3 (frontend) / Luke (Maps): no changes needed. The mock URL
  `/static/mock-flux.png` is replaced with `/static/flux/<lead_id>.png`
  but the field `url` and bbox/vmin/vmax shape is identical.
- A2 (api): cost meter ticks 1c per findClosest, 2c per dataLayers — your
  `/lead/spend/session` aggregator picks them up automatically.
- A1 (foundation): `lead.panel_layout.clip_method` now reads
  `"inspire_polygon_raycast"` per schema.

### 13:30 — Live test results (Atlas + uvicorn --reload)
- `POST /lead/<id>/flux_overlay` → real PNG at
  `/static/flux/lead_<id>.png`, 1267x795 RGBA, 1.2 MB. bbox legit
  (±70m around target), vmin=299.5 kWh/m²/yr, vmax=891.3.
- `POST /lead/<id>/panels` → 9 real panels on Old Street rooftop,
  annual_kwh=2730. azimuth=0° (north-facing), tilt=0.93° (flat roof).
  rooftop_polygon source preserved.
- Cache: 2nd flux call cost 0 cents (hit), 1st cost 3 cents.
- All 35 tests pass (8 new in test_solar_api.py + 27 pre-existing).

### Real-API response shape note
- Solar API `solarPanels[i]` uses `orientation: "LANDSCAPE"|"PORTRAIT"`
  (NOT a numeric degrees value). True azimuth lives on
  `solarPotential.roofSegmentStats[panel.segmentIndex].azimuthDegrees`.
  Updated `panels_from_solar_api` to handle both real shape and the
  simpler test-fixture shape (numeric orientation).
- Panel dims default to API-reported `panelWidthMeters`/`panelHeightMeters`
  (1.045 / 1.879 for the demo response) and swap on PORTRAIT.
