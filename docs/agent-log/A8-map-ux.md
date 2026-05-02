# A8 Map UX Polish — agent log

## 2026-05-02 13:30 — A8 SHIPPED

Cinematic camera, layer toggles wired, score-banded markers, live HUD readouts.
All work in `packages/web/src/components/map3d/`, `App.tsx`, `index.css`,
plus a new `useCameraStore` Zustand store.

### Acceptance

- `pnpm typecheck` clean (zero TS errors)
- `pnpm build` clean (Vite + tsc -b, CSS bundle 32.76 KB, JS 530 KB)
- All hooks before any conditional return (cardinal — black-screen rule)
- Linear / ease-out animations only, 200–1500 ms range
- `prefers-reduced-motion` honoured: snap (no fly), camera state still updates
- No glassmorphism, sharp 2px corners preserved
- MapSlot props contract preserved — `layers` prop added as optional with
  default-on legacy behaviour (CONTRACTS § 4 updated, marked `A8 PROPOSAL`)
- Did NOT touch `/flux_overlay` or `/panels` API endpoints (A6 scope)

### Files SHIPPED

**New**

- `src/stores/useCameraStore.ts` — Zustand slice holding `{ lat, lng, range, tilt, heading }`.
  MapSlot pushes updates from `gmp-camerachange`; HUDs subscribe to slices.

**Modified**

- `src/components/map3d/MapSlot.tsx` — full rewrite of camera + overlay logic:
  - Default boot camera: `54.5, -2.5, 600000` (central England), range 500 000 m,
    tilt 30°. UK-wide tactical view; reads as "whole UK commercial market".
  - First-scan flyout: when `leads.length` transitions 0 → N AND no lead is
    selected, fly to centroid of leads at `range=2000m, tilt=55°` over 1500 ms.
    Latched via `flewToScanRef` so it only fires once per population. Latch
    resets if leads drops back to zero (e.g. reset action).
  - Lead-selected flyout: range 220 m, tilt 67°, alt 80 m over 1200 ms.
  - `prefers-reduced-motion` check inside `flyOrSnap()` — snaps via
    `setAttribute("center"|"range"|"tilt", …)` instead of calling `flyCameraTo`.
  - Added `data-score-band="low|mid|high"` to every marker (cutoffs <50 / 50–69 / ≥70)
    and `data-selected="0|1"` for the selected pop.
  - Added `layers` prop (optional). When unset, all overlays render. When set,
    each layer is gated:
    - `layers.pins` → marker rendering
    - `layers.radiance` → flux overlay polygon
    - `layers.panels` → panel polygons
    - `layers.polygons` → rooftop polygon (for selected lead)
  - Camera-change listener seeds the store on mount and pushes on every
    `gmp-camerachange` event. Reads attributes (most reliable across alpha
    SDK builds) with property fallback.
- `src/components/map3d/HUD-LayerToggle.tsx` — added `hasSelectedLead` prop.
  Disables radiance/panels/polygons checkboxes (50% opacity, `cursor-not-allowed`)
  when no lead is selected. Adds a tiny mono caption `select a lead` underneath.
  Pins toggle stays live regardless.
- `src/components/map3d/HUD-Coords.tsx` — now subscribes to `useCameraStore`
  for live LAT/LNG. Falls back to selected lead's coords, then to em-dash.
  Updates every camera tick (panning, zooming).
- `src/components/map3d/HUD-Scale.tsx` — reads `range` from `useCameraStore`,
  picks a scale-stop set:
  - `< 500 m`     → 100 m / 50 m / 10 m
  - `500–5000 m`  → 1 km / 500 m / 100 m
  - `5–50 km`     → 10 km / 5 km / 1 km
  - `≥ 50 km`     → 100 km / 50 km / 10 km
- `src/App.tsx` — passes `layers` state down to `<MapSlot />` and
  `hasSelectedLead={selectedLeadId !== null}` to `<HUDLayerToggle />`.
- `src/index.css` — added marker styling block targeting
  `gmp-marker-3d-interactive-element[data-score-band=…]` and
  `…[data-selected="1"]`. Selected marker scales 1.35× with a coloured
  drop-shadow halo. Hover scales 1.1×.

### What worked

- Centroid computation lives in a `useMemo` keyed on `leads` so we don't
  recompute on every render.
- The first-scan latch (`flewToScanRef`) intentionally checks
  `prev === 0 && curr > 0` so re-renders that don't change leads length
  (e.g. filter changes that just hide rows) don't re-trigger the flyout.
- `flyOrSnap()` consolidates the reduced-motion check into a single helper
  so we never accidentally animate when the user has the OS pref set.

### What didn't work / known limits

- **Marker shadow DOM is not reachable.** The Photorealistic alpha SDK
  does NOT expose `::part(label)` or `::part(pin)` on
  `<gmp-marker-3d-interactive-element>` (verified empirically). The label
  text and pin icon are rendered inside closed shadow DOM. We can only
  style the host element itself — so the score-band colouring shows up
  via `transform: scale()` and `filter: drop-shadow()` on the host,
  giving a visible halo + size pop on selection. The numeric label text
  inside the marker is locked to whatever Google's default chip styling is.
  If a future SDK build exposes parts, drop richer rules into the same
  CSS block.
- The alpha SDK's `flyCameraTo` is not always present on every released
  build — `flyOrSnap()` falls through to `setAttribute(…)` if the method
  is missing. Demo audience sees a snap rather than a fly in that case.
- We rely on `getAttribute("center")` to read camera state because the
  property accessors on the alpha web component aren't stable. Strings
  in `lat, lng, alt` form parse cleanly with split + parseFloat.

### Hand-off

- Frontend owners (A3): the `layers` state is already lifted in `App.tsx`,
  so any future map-related toggle just needs to extend `LayerState` and
  add a check inside `MapSlot.tsx`.
- API owner (A6): unchanged — we consume `flux_overlay` and `panel_layout`
  off the Lead doc as before. No new endpoints requested.
- Voice / pitch lanes: unaffected.
