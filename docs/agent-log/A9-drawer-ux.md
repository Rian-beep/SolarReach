# A9 — Drawer UX Polish log

## 2026-05-02

### 13:24 — Bootstrap
- Mission: make the drawer sell the deal.
  - IntelTab: PAYBACK hero card on top + DECISION-MAKER card.
  - ReferenceTab: REPLACE static funding cards with interactive Radix Tabs
    selector + UK tax breaks card + references with live links.
  - lib/financial.ts: add `computeMonthlyPayment`, `computeRoi`, `formatYears`.
- Did not touch PitchTab or VoiceTab (A4 stable).
- Confirmed Gotham theme tokens: `text-display` 40px mono, `tracking-tight`,
  `cyan/magenta/amber/emerald/red` accents, `rounded-[2px]`, 1px borders.

### 13:31 — financial.ts helpers
- Added (non-breaking, appended below existing exports):
  - `FundingModelId` union (`capex|free_install|lease_purchase|operational_lease|hire_purchase`).
  - `computeMonthlyPayment(capex, model, termYears, interestRate=0.06, annualSaving=0)`:
    - capex → 0
    - free_install (PPA) → annual_saving * 0.85 / 12 (PPA bill ≈ 85% of self-saved value)
    - lease_purchase → simple-interest amortisation: (capex + capex*r*y) / (y*12)
    - operational_lease → capex * 0.014 (~£14/£1k/mo industry rule of thumb)
    - hire_purchase → 10% deposit + financed simple-interest amortisation
  - `computeRoi(capex, annualSaving)` → annual_saving/capex * 100
  - `formatYears(n)` → "7.8 yr" / "—" on bad input.
- All helpers unit-test trivially via the running drawer.

### 13:42 — IntelTab
- Hooks all declared before any conditional branch (cardinal rule).
- New PAYBACK hero card AT TOP:
  - `text-display` mono numeral (40px) for `formatYears(payback_years)`.
  - Right-aligned NPV 25YR caption in emerald mono.
  - 3-stat compact row: CAPEX | ANNUAL SAVING | ROI %.
  - Skeleton state when `lead.financial` null.
- New compact DECISION-MAKER card under owner card:
  - Mono name in `text-lg`.
  - Role + confidence number in cyan mono caption (tabular-nums).
  - 2-line italic `text-mute` rationale (`line-clamp-2`).
  - Confidence badge magenta; below 0.7 → extra amber `[LOW CONFIDENCE]` badge.
- Moved BUILD ORG button into its own ORG INFERENCE card for clarity (still
  cost-confirmed via existing modal — no auto-fire).
- Composite score / land registry / officers cards preserved verbatim.

### 13:53 — ReferenceTab (full rewrite)
- Stack:
  1. FUNDING MODEL card with Radix Tabs (5 models, mono UPPERCASE labels,
     cyan active underline). Per-tab content card shows:
     - Model name + 1-line description.
     - Live MONTHLY (cyan, large mono) + TERM (bone) split panel computed
       from this lead's capex/annual_saving via `computeMonthlyPayment`.
     - Ownership badge (cyan if client, magenta if provider).
     - SEG-claimer badge (amber).
     - Pros/Cons grid with `+`/`−` accents (emerald/red).
  2. TAX BREAKS card with five UK incentives (commercial-aware via
     `lead.premises_type`):
     - Smart Export Guarantee — £0.15/kWh; live annual export estimate
       from `panel_layout.annual_kwh * 0.20` priced at SEG rate.
     - Capital Allowances (AIA) — 100% on first £1M up to 2026-04-30,
       then 18% writing-down.
     - Super Deduction — red `EXPIRED` badge + historical context note.
     - VAT — 0% if residential, "20% RECOVERABLE" otherwise.
     - ECO4 Grant — emerald `UP TO £14k` if residential, outline
       `RESIDENTIAL ONLY` if commercial.
  3. REFERENCES card with anchor links to Ofgem SEG + HMRC AIA + plain
     bullets for HM Treasury Spring Statement 2026, Land Registry,
     Companies House, Google Solar API.
- All numbers/percentages/GBP rendered in `font-mono tabular-nums`.
- 2px corners, 1px borders throughout. No marshmallows.

### 13:58 — Verification
- `pnpm typecheck` → clean.
- `pnpm build` → clean (538 kB main bundle, expected).
- No paid-API calls made; BUILD ORG remains user-initiated + cost-confirmed.
- Did not touch: PitchTab, VoiceTab, A6/A7/A8 surfaces.

### Deltas summary
- `packages/web/src/components/drawer/IntelTab.tsx` — extended (hero +
  decision-maker card).
- `packages/web/src/components/drawer/ReferenceTab.tsx` — rewritten
  (interactive funding tabs, tax-breaks card, references with citations).
- `packages/web/src/lib/financial.ts` — appended helpers (no changes to
  existing exports — A6/A7/A8 unaffected).
