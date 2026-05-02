# Palantir Gotham Visual System

> **Reference for the UX retheme agent.** Once A3 lands the functional shell, this spec re-skins everything.

## North star

Operations cockpit, not a SaaS dashboard. Tactical / intelligence feel — like sitting at a workstation in a SOC. The map is the canvas; everything else is a HUD overlay. Data-dense, monospace where data lives, no rounded marshmallows.

## Color system (Tailwind v4 tokens)

```
/* --- ground --- */
bg-app-void        #050608    /* deep black, page bg */
bg-app-surface     #0A0E14    /* card/panel bg */
bg-app-elev-1      #0F141C    /* hover / active */
bg-app-elev-2      #131A24    /* drawer interior */
bg-app-glass       #0A0E14CC  /* translucent overlay */

/* --- borders / chrome --- */
border-iron        #1A2230    /* default border */
border-iron-bright #2A3445    /* hover/focus */
border-iron-grid   #131C2A    /* faint grid */

/* --- text --- */
text-bone          #E8EDF5    /* primary text */
text-mute          #93A3B8    /* secondary */
text-dim           #5A6878    /* tertiary, captions */
text-grid          #3A4658    /* axis labels, super-mute */

/* --- accents --- */
accent-cyan        #1FB6FF    /* primary action / data viz */
accent-cyan-glow   #1FB6FF40  /* halo */
accent-amber       #FFB020    /* warnings, attention */
accent-amber-glow  #FFB02033
accent-red         #FF4757    /* errors, critical */
accent-emerald     #20D082    /* success, scores >70 */
accent-magenta     #F040C0    /* anomaly / live signal */

/* --- score gradient --- */
score-low    #FF4757   /* 0-49 */
score-mid    #FFB020   /* 50-69 */
score-high   #20D082   /* 70-100 */
```

DO NOT use names that collide with Tailwind utility shortcuts (`base`, `sm`, `md`, `lg`, `xl`).

## Typography

Two-font system:
- **Sans (chrome)**: `Inter` — already loaded. Weights 400/500/600. UI labels, buttons, body.
- **Mono (data)**: `JetBrains Mono` (load from Google Fonts). Weights 400/500. Use for: any number, postcode, ID, score, GBP value, lat/lng, coordinates, address codes, timestamps.

Sizes:
- xs `11px / 16px` — captions, axis labels
- sm `12px / 16px` — body, UI labels (DEFAULT for dense panels)
- base `13px / 18px` — data values
- md `14px / 20px` — tab labels, button text
- lg `16px / 24px` — section titles
- xl `20px / 28px` — drawer header
- 2xl `28px / 32px` — score badge
- display `40px / 44px` — kpi numbers

Letter-spacing:
- `tracking-tight` (-0.01em) on display
- `tracking-wide` (0.04em) UPPERCASE caption labels (e.g. `OWNER`, `COMPOSITE SCORE`, `ROOF AREA`)

## Geometry

- **Border radius**: 2px default, 4px max on cards, 0 on data tables. NO 12-16px marshmallow corners.
- **Border width**: 1px everywhere. Use 2px only for active/focused states.
- **Spacing**: tight — `4 / 8 / 12 / 16` instead of `12 / 16 / 24 / 32`. Dense.
- **Grid**: subtle 32px-square background grid in `border-iron-grid` on the canvas (CSS `background-image: linear-gradient(...)`).
- **Shadows**: minimal. Use 1px inner border instead of drop shadow. One drop shadow allowed: drawer overlay (`shadow-[0_0_64px_-16px_rgba(0,0,0,0.8)]`).

## Motion

- Sharp + technical, NOT bouncy. Linear or `ease-out` only. NO spring physics.
- Drawer slide: 200ms ease-out.
- Modal fade: 120ms.
- Hover transitions: 80ms.
- Pulse on live data: 1s linear infinite, 60-100% opacity.
- NO frosted-glass blur on overlays > 4px (perf + reads as "Apple", not Gotham). Use 2-4px or solid bg.

## Component conventions

### Header (top bar)
- Height 48px, `border-b border-iron`, `bg-app-surface`.
- Left: SolarReach wordmark in mono, lower-case `solarreach://` prefix style (data-feel).
- Center: postcode input is a faux-terminal `> _ EC1Y 8AF` with cyan caret blink.
- Right: SpendIndicator (mono digits) + status pill `● ATLAS LIVE` / `● ATLAS DEGRADED` (live-pulse dot).

### Map canvas (Luke's lane — frame for context)
- Subtle grid overlay above the Google 3D scene at 8% opacity.
- Top-left HUD: `LAT/LNG` mono readout updating on camera move.
- Top-right HUD: scale bar (1km / 500m / 100m).
- Bottom-left: legend (radiance kWh/m²·day) with cyan→amber→magenta gradient bar.
- Bottom-right: layer toggle stack (Pins / Radiance / Panels / Polygons), each with `[x]` checkbox.

### Drawer
- Slides from right, 520px wide (NOT 480 — more data room).
- Solid `bg-app-elev-2`, no transparency.
- Header: lead address mono, composite-score badge, close `[ESC]` hint.
- Tabs: underlined active, `text-cyan border-b-2 border-cyan`, others muted. NO pill background.

### Cards
- `bg-app-surface border border-iron rounded-[2px]`. Hover: `border-iron-bright`.
- Title row: tiny UPPERCASE caption (e.g. `LAND REGISTRY OWNER`) in `text-mute tracking-wide`.
- Body: bone color, mono for numbers/codes.

### Buttons
- Primary: `bg-cyan text-app-void` with 1px `border-cyan` and inner glow `shadow-[inset_0_0_0_1px_rgba(31,182,255,0.3)]`.
- Ghost: `bg-transparent border-iron text-bone hover:border-cyan hover:text-cyan`.
- Danger: `text-red border-red` outline only.
- Sharp corners (2px), `tracking-wide uppercase` for action verbs (`SCAN`, `GENERATE PITCH`, `REHEARSE`).

### Data tables / lists
- Zebra striping in `bg-app-elev-1` alt rows.
- Mono columns for IDs / codes / lat/lng / GBP.
- Hover row: `bg-app-elev-1 cursor-pointer`.
- Selected row: 2px left border in `accent-cyan`.

### Score badge
- Square, 32×32px, mono, score-color background, `text-app-void` if mid/high, `text-bone` if low.
- Append a 4px segmented bar below showing percentile in score-color.

### Spend indicator
- Always mono.
- Format: `£0.12 / £1.00` + 1px filled bar below.
- States: `<60% text-mute`, `60-90% text-amber`, `≥90% text-magenta animate-pulse`.

### Cost-confirm modal
- Centered, 320px wide.
- Title mono UPPERCASE: `CONFIRM SPEND`.
- Body bone: "This action will spend £0.05 from session budget."
- Primary button: `[CONFIRM]`, ghost: `[CANCEL]`.

### HUDs and overlays
- Position absolute, 1px iron-bright border, 4px padding, rounded-[2px].
- Mono labels in `tracking-wide uppercase text-grid`.
- Values in `text-bone mono`.

## Iconography

- `lucide-react` set, 16px default, 20px in headers.
- Stroke 1.5 (slightly thinner than default 2 — more "technical").
- Use the line-art versions, not filled.

## Empty states & loading

- Skeleton: `bg-app-elev-1 animate-[shimmer_1.5s_linear_infinite]` — 1px grid pattern overlay so it reads as "data loading" not "image placeholder".
- Empty state: ASCII-art icon (e.g. `[ -- ]` for no data), mono caption.

## Scrollbars

- Custom: thin, 6px, `bg-app-elev-1` track, `bg-iron-bright` thumb, no rounded.

## Composition sketch (homepage)

```
┌─────────────────────────────────────────────────────────────────────────┐
│ solarreach://  [> _ EC1Y 8AF      ]  [SCAN]    £0.12/£1.00  ● ATLAS LIVE │
├─────────────────────────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐ ┌─────────────────┐ │
│ │ LAT 51.5256  LNG -0.0876         SCALE: 250m   │ │ INTEL · PITCH   │ │
│ │                                                 │ │ VOICE · REF     │ │
│ │     [Photorealistic 3D map of London]           │ │ ─────────────── │ │
│ │     • markers labelled with composite_score     │ │ COMPOSITE SCORE │ │
│ │     • radiance overlay + panels on click        │ │   84            │ │
│ │                                                 │ │ ████████▒▒      │ │
│ │                                                 │ │                 │ │
│ │ ┌─ LEGEND ──────────┐                          │ │ OWNER           │ │
│ │ │ kWh/m²·day        │                          │ │ Old Street      │ │
│ │ │ ░░▓▓▓▓▒▒██████    │                          │ │ Holdings Ltd    │ │
│ │ │ 1.5         5.5   │                          │ │ ─────────────── │ │
│ │ └────────────────────┘                          │ │ DECISION MAKER  │ │
│ │                                  [● ● PINS]     │ │ Sarah Patel CFO │ │
│ │                                  [○   RADIANCE] │ │ confidence 0.78 │ │
│ │                                  [○   PANELS]   │ │ ─────────────── │ │
│ │                                  [● ● POLYGONS] │ │ [BUILD ORG]     │ │
│ └─────────────────────────────────────────────────┘ │ [GENERATE PITCH]│ │
│                                                     │ [REHEARSE]      │ │
│                                                     └─────────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
```

## Anti-patterns (do NOT do)

- ❌ Glassmorphism / heavy backdrop blur
- ❌ Gradient buttons / colorful CTAs
- ❌ 16px+ rounded corners
- ❌ Drop shadows everywhere
- ❌ Sans-serif for numerical data
- ❌ Spring/bouncy animations
- ❌ Stock illustration / 3D blobs
- ❌ Emoji in chrome (allowed only in stub placeholder until Luke ships maps)
- ❌ "Saas pink/purple" gradients
- ❌ Centered single-column hero layouts (this is a cockpit, not a marketing site)

## Reference inspiration (look at these, don't copy)

- Palantir Gotham marketing screenshots
- Bloomberg Terminal
- military C2 (command & control) HUDs
- Falcon CrowdStrike dashboard
- Linear app's command palette dark mode
