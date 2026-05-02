# A3 Frontend — agent log

## 2026-05-02 13:00 — A3-FINAL + A6 GOTHAM (cleanup pass)

Picked up after the prior A3 stalled at ~25 files. Finished the remaining
gaps and rethemed the entire chrome to Palantir-Gotham in one pass. All
work in `packages/web/`.

### Acceptance

- `pnpm typecheck` clean (zero TS errors)
- `pnpm build` clean (Vite + tsc -b, single CSS bundle ~32 KB, JS ~523 KB)
- `pnpm dev` serves `http://localhost:5173/` with `200` on html/main/css —
  no console errors at startup
- All Gotham hard rules respected: rounded ≤ 4px, no glassmorphism, no
  spring physics, hooks-before-conditional, no auto-paid calls (every
  ≥10p action gates through `CostConfirmModal`), no name collisions
  (avoided `base|sm|md|lg|xl` as colour tokens — `text-md` is a font-size
  token, not a colour)

### Files SHIPPED (added or rewritten)

**Foundation (theme tokens)**

- `tailwind.config.js` — complete Gotham palette (`app-void/surface/elev-1/elev-2`,
  `iron/iron-bright/iron-grid`, `bone/mute/dim/grid`, accents
  `cyan/amber/red/emerald/magenta`, `score-low/mid/high`); legacy aliases
  preserved so prior code still resolves; `fontFamily`, `borderRadius` defaulting
  to 2px, dense `keyframes` (`shimmer`, `live-dot`, `pulse-soft`,
  `caret-blink`, `slide-in-right`, `fade-in`)
- `src/index.css` — Tailwind v4 `@theme` block with all Gotham `--color-*`,
  `--text-*` (xs 11px → display 40px), `--tracking-*`, `--radius-*`,
  `--animate-*`, `--shadow-*`; `.bg-grid` / `.bg-grid-tight` 32px utilities;
  shimmer with grid-overlay pseudo; thin 6px square scrollbars; sharp 1px
  cyan focus ring
- `index.html` — body class `bg-app-void text-bone`

**UI primitives (rethemed)**

- `src/components/ui/Button.tsx` — sharp 2px corners, uppercase tracking-wide,
  `cyan` primary with inset glow, `ghost` outline, `destructive`/`magenta`/`amber`
  outline-only, dense h-7/h-8/h-10 sizes
- `src/components/ui/Card.tsx` — `bg-app-surface border border-iron rounded-[2px]`,
  hover→`iron-bright`, tight `p-3`, mono caption titles
- `src/components/ui/Tabs.tsx` — underline-active in cyan, no pill bg
- `src/components/ui/Dialog.tsx` — solid `bg-app-elev-2`, 320px width, fade-in
  120ms, no backdrop blur
- `src/components/ui/Input.tsx` — h-8, `bg-app-elev-1`, focus border cyan
- `src/components/ui/Label.tsx` — uppercase tracking-wide mute
- `src/components/ui/Badge.tsx` — re-tinted variants + `<ScoreBadge />`:
  square 32×32 mono numeral with 10-segment bar below, score-color tier
- `src/components/ui/Skeleton.tsx` — shimmer + grid-overlay
- `src/components/ui/Tooltip.tsx` — sharp 2px, iron-bright border
- `src/lib/utils.ts` — added `formatLatLng`; updated `scoreBadgeClass` tokens

**Header chrome (rethemed)**

- `src/components/header/Header.tsx` — 48px high, `solarreach://` mono
  wordmark, terminal `> _` postcode input with cyan blinking caret, ATLAS
  status pill with live-dot, OPS/CALC/ADMIN mode switch (controlled by App)
- `src/components/header/SpendIndicator.tsx` — pure mono `£0.12 / £1.00`,
  1px underline bar, mute/amber/magenta-pulse tiers
- `src/components/header/CostConfirmModal.tsx` — `CONFIRM SPEND` mono title,
  exactly 320px, ghost CANCEL + cyan CONFIRM, `< 10p` auto-resolves true

**Drawer + tabs**

- `src/components/drawer/LeadDrawer.tsx` — kept (already 520px, on-theme)
- `src/components/drawer/IntelTab.tsx` — rethemed: composite-score with
  `<ScoreBadge />`, mono postcode/lat-lng/company_id, mono financial
  snapshot table with zebra striping, ASCII `[ -- ]` empty states
- `src/components/drawer/PitchTab.tsx` — fixed bug (mutation arg shape was
  wrong: now passes `{leadId, clientId}`); 6 slide-thumb grid; A/B email
  cards with magenta live-dot; `[DOWNLOAD PPTX]` `[DOWNLOAD PDF]` ghost
  buttons; £0.10 cost-confirm gate
- `src/components/drawer/VoiceTab.tsx` — wired ElevenLabs
  `Conversation.startSession({signedUrl, onMessage, onDisconnect, onError,
  onModeChange})`; transcript chunks pushed to `useVoiceStore.appendChunk`
  with role inference; auto-scroll; AGENT: cyan / USER: bone; END CALL
  destructive button; £0.15 gate; cleanup on unmount
- `src/components/drawer/ReferenceTab.tsx` — kept (already on-theme, 5
  funding cards, ROI table, citation list)

**Map HUDs (overlay components for Luke's MapSlot)**

- `src/components/map3d/HUD-Coords.tsx` — top-left LAT/LNG mono readout;
  reads from `useLeadStore` selected lead by default; accepts override
  props for live camera updates
- `src/components/map3d/HUD-Scale.tsx` — top-right scale bar (1km/500m/100m
  static)
- `src/components/map3d/HUD-Legend.tsx` — bottom-left radiance gradient
  legend with vmin/vmax labels (cyan→amber→magenta)
- `src/components/map3d/HUD-LayerToggle.tsx` — bottom-right Pins/Radiance/
  Panels/Polygons checkbox stack with `[x]` indicator; controlled state
  pattern (lifted into `App.tsx`)

**Calculator + Admin + Charts**

- `src/components/calculator/CalculatorMode.tsx` — address + annual_kwh +
  premises-type form → POST `/financial/calculator` → mono breakdown table
  (capex/saving/payback/NPV/panels/kWh) with ECO4 emerald-pill if eligible;
  separate name/email/phone form → POST `/inbound/lead`
- `src/components/admin/AdminCentre.tsx` — read-only mono client slug,
  branding primary color picker (HTML5 color + hex Input), panel unit GBP
  Input, install £/kW Input, session-budget range slider; SAVE CONFIG
  → PUT `/admin/client/:slug`
- `src/components/charts/AtlasChartsStrip.tsx` — collapsible 4-card grid
  (LEADS BY SCORE / SCORE DISTRIBUTION / SPEND OVER TIME / PIPELINE FUNNEL),
  Skeleton bodies, footnote "atlas charts iframe wires post-mongo-config"

**Top-level wiring**

- `src/App.tsx` — mode switch (map/calculator/admin); two-pane in map mode
  with relative-positioned MapSlot + 4 HUD overlays + lead-count chip +
  drawer; ESC closes drawer; lead-detail fetched on demand; layer state
  lifted; AtlasChartsStrip below map
- `src/main.tsx` — kept; QueryClient + Toaster (re-themed via `!bg-app-elev-2
  !border-iron !text-bone !rounded-[2px]`)

**Library tweaks**

- `src/lib/elevenlabs.ts` — fixed `onStatusChange` signature to match
  `@elevenlabs/client` SDK (`{status: string} → void`)

### Files NOT touched (per instruction)

- `src/components/map3d/MapSlot.tsx` — Luke's lane (Google Maps Photorealistic
  3D + Solar API). HUD overlays compose around it.

### Known gaps / handoff notes

- `useFilterStore` defined but not yet wired into App — left for filter UI
  in next sprint
- Atlas Charts cards are Skeleton placeholders — iframe wiring waits on
  Mongo Charts public-key config
- Bundle is 523 KB minified (mostly framer-motion + radix); chunk-split
  not done — out of scope, hackathon speed
- HUD-Coords reads selected-lead coordinates as a fallback. When Luke
  ships MapSlot with camera events, pass live `lat`/`lng` props in App
