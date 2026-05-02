"""UK commercial solar PV industry benchmarks — single source of truth.

These constants are the canonical numbers cited across:
  - The map HUD (`HUD-Benchmarks.tsx`) — top-right cockpit chip
  - The pitch deck system prompt (`prompts/pitch_system.md` via deck.py)
  - The calculator's "industry typical" annotations
  - Any agent that needs to ground a claim in a citation

A TypeScript mirror lives at `packages/shared/ts/src/industry_benchmarks.ts`
with identical keys and values. Update both together — this is reference
data, not derived data, so it should never drift.

Sources are documented per-key. Numbers come from three streams:
  1. The `Carterton Leisure Centre` 2014 PV Proposal PDF (Langley Eco /
     Mears Group plc, project 4263) — the seed document this module was
     extracted from. Reflects 2014 FiT-era pricing; included for historical
     anchor + funding-model taxonomy.
  2. UK 2025-26 government / Ofgem published rates (SEG, capital
     allowances, BEIS grid intensity).
  3. UK Solar Trade Association / MCS industry surveys (commercial install
     cost bands, payback statistics).
"""

from __future__ import annotations

from typing import Final

# ---------------------------------------------------------------------------
# Install economics (UK commercial, 2025-26)
# ---------------------------------------------------------------------------

UK_INSTALL_COST_PER_KW_GBP: Final[float] = 950.0
"""Median £/kW installed for UK commercial roof-mount PV (10-250 kWp band).

2025-26 Solar Trade Association mid-market figure. Range £800-£1,100/kW for
commercial systems above 30 kWp; small commercial (<30 kWp) trends £1,100-
£1,400/kW. The 2014 Carterton PDF anchor was £1,550/kW (£155k for 100 kWp);
modern bulk procurement + 25-year tier-1 panels brought this down ~40%.
"""

UK_INSTALL_COST_PER_KW_RANGE_GBP: Final[tuple[float, float]] = (800.0, 1100.0)
"""(low, high) £/kW band for UK commercial PV, 2025-26."""

PANEL_RATED_KW: Final[float] = 0.42
"""Typical panel nameplate rating (kW). 420W is the 2025-26 tier-1 norm
(monocrystalline PERC/TOPCon); the 2014 PDF used 250W panels — modern
panels are ~70% denser per m². Mirrors `constants.PANEL_RATED_KW`."""

# ---------------------------------------------------------------------------
# Generation & resource
# ---------------------------------------------------------------------------

UK_AVG_IRRADIANCE_KWH_PER_M2_YR: Final[float] = 1050.0
"""UK annual horizontal irradiance average (kWh/m²·yr).

Range: ~900 kWh/m²·yr (Glasgow / Highlands) to ~1,200 kWh/m²·yr (Cornwall).
South England commercial average ~1,050. Source: BEIS / PVGIS.
"""

UK_TYPICAL_KWH_PER_KWP_YR: Final[float] = 950.0
"""UK annual yield per kWp installed (kWh/kWp·yr) — south-facing 30-40°
tilt, 85% performance ratio. The 2014 Carterton PDF assumed 850 kWh/kWp
at 85% capacity (a conservative leisure-centre figure); modern monitored
fleet data lands at 950-1,000 kWh/kWp for well-orientated commercial
roofs. We adopt 950 as the middle-of-band default."""

PERFORMANCE_DERATE_PCT: Final[float] = 0.85
"""Default performance ratio applied when system-level data is missing.
Accounts for shading, soiling, temperature, inverter losses, cable losses.
The Carterton PDF anchor used the same 85% (page 5)."""

PANEL_DEGRADATION_PER_YEAR: Final[float] = 0.005
"""Annual panel degradation (0.5%/yr). Matches `constants.PANEL_DEGRADATION_PER_YEAR`.
The Carterton PDF used a steeper ~0.75%/yr (100% → 85% over 20 yrs);
modern Tier-1 panels with linear performance warranties hit 0.4-0.55%/yr."""

# ---------------------------------------------------------------------------
# Tariffs & policy (UK 2025-26)
# ---------------------------------------------------------------------------

UK_SEG_EXPORT_RATE_GBP_PER_KWH: Final[float] = 0.15
"""Smart Export Guarantee export tariff — best available 2025-26 (Octopus
Outgoing Fixed). Suppliers must offer >0p/kWh; competitive rates 5-15p.
SEG replaced the Feed-in Tariff (closed to new entrants 2019-04-01).

Historical context (2014 Carterton PDF, page 6 — Ofgem FiT bands):
  - 4.1-10 kWp: 13.03p/kWh higher rate
  - 10.1-50 kWp: 12.13p/kWh higher rate
  - 50.1-100 kWp: 10.34p/kWh higher rate
  - >250 kWp: 6.38p/kWh
  - Export bonus on top: 4.77p/kWh
SEG today is paid only on exported units; FiT historically paid on every
kWh generated regardless of export. Modern proposals must NOT cite FiT.
"""

UK_IMPORT_RATE_GBP_PER_KWH: Final[float] = 0.27
"""Reference UK commercial import unit rate, 2025-26 (excl. standing
charge). Has risen ~78% from the 2019 baseline; Carterton PDF 2014 used
10p/kWh. Volatility-driven self-generation business case rests on this."""

VAT_RESIDENTIAL_PV_PCT: Final[float] = 0.0
"""0% VAT on residential PV installations (UK, 2022-04 to 2027-03).
Commercial installs are still 20% VAT (recoverable via input VAT)."""

# ---------------------------------------------------------------------------
# Capital allowances & tax
# ---------------------------------------------------------------------------

AIA_CAP_GBP_MILLION: Final[float] = 1.0
"""Annual Investment Allowance cap — £1m/yr permanently from 2023-04.
Solar PV (plant & machinery) qualifies for 100% first-year deduction
within this cap. Above the cap: special-rate pool 6%/yr writing-down."""

FULL_EXPENSING_AVAILABLE: Final[bool] = True
"""Full expensing (100% first-year allowance, uncapped) for new main-rate
plant — extended permanently in the 2024 Spring Budget. Solar PV qualifies
when client-owned (not under operating lease)."""

# ---------------------------------------------------------------------------
# Carbon
# ---------------------------------------------------------------------------

GRID_CARBON_KG_PER_KWH: Final[float] = 0.193
"""UK grid carbon intensity (kg CO₂e/kWh), 2025-26 — BEIS / DESNZ
greenhouse gas conversion factors. Down from 0.207 (2024) and 0.460
(the implied 2014 figure from the Carterton PDF: 781.82 tCO₂ over 20 yrs
on 85,000 kWh/yr). Reflects coal phase-out + grid wind growth.

NB: `constants.GRID_CARBON_KG_PER_KWH` still reads 0.207 — keep it there
for the 2024 baseline used by archived scoring runs; this 2025 value is
for new pitch decks + benchmarks HUD only.
"""

CO2_KG_PER_TREE_PER_YEAR: Final[float] = 22.0
"""Mature broadleaf tree CO₂ uptake (kg CO₂/yr). Used for `equiv_trees`
display in the social_impact deck slide."""

# ---------------------------------------------------------------------------
# Payback / IRR ranges
# ---------------------------------------------------------------------------

UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL: Final[float] = 7.5
"""Typical UK commercial PV payback — 2025-26 mid-market figure for
client-owned (Capex) systems with 50% self-consumption. Range 6-10 yrs
depending on tariff exposure + roof orientation. The 2014 Carterton PDF
hit year-9 break-even on FiT subsidy alone (page 7); modern systems
without FiT subsidy reach year ~8 purely on import-cost displacement."""

UK_TYPICAL_PAYBACK_RANGE_YEARS: Final[tuple[float, float]] = (6.0, 10.0)
"""(low, high) commercial payback band — capex model."""

UK_TYPICAL_IRR_COMMERCIAL: Final[float] = 0.10
"""Mid-market 25-year IRR for UK commercial PV (capex model, 50% self-
consume, SEG export). Range 8-12%. The Carterton PDF projected 20-year
gross-of-finance returns equivalent to ~12% IRR (£325k profit on £155k
capex, FiT-supported); modern unsubsidised systems land 8-11%."""

# ---------------------------------------------------------------------------
# Funding models (canonical 5)
# ---------------------------------------------------------------------------

FUNDING_MODELS: Final[tuple[dict[str, str], ...]] = (
    {
        "name": "Capital Expense",
        "fit": "Best NPV, full ownership, claims SEG",
        "term_years": "n/a (outright)",
        "balance_sheet": "on (asset)",
    },
    {
        "name": "Free Install (PPA)",
        "fit": "Zero capex, provider keeps SEG",
        "term_years": "25",
        "balance_sheet": "off (no asset, opex only)",
    },
    {
        "name": "Lease Purchase",
        "fit": "Cashflow + ownership at year 7",
        "term_years": "7",
        "balance_sheet": "on (finance lease)",
    },
    {
        "name": "Operational Lease",
        "fit": "Off-balance-sheet, fully tax-deductible",
        "term_years": "5",
        "balance_sheet": "off (operating lease)",
    },
    {
        "name": "Hire Purchase",
        "fit": "VAT efficient, year-1 capital allowances",
        "term_years": "5",
        "balance_sheet": "on (asset + loan)",
    },
)
"""Canonical funding-model taxonomy. Order is binding for the deck JSON
schema (deck.py expects all 5 in this order). Sourced from the 2014
Carterton PDF (page 4) which lists the same five — the taxonomy has been
stable since the FiT era."""

# ---------------------------------------------------------------------------
# Sales / market context
# ---------------------------------------------------------------------------

UK_COMMERCIAL_PV_GROWTH_YOY_PCT: Final[float] = 0.21
"""UK non-domestic PV capacity growth, 2024 → 2025 (21% YoY).
Source: Solar Energy UK industry report 2025."""

UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT: Final[float] = 0.78
"""UK commercial electricity unit-rate increase, 2019 → 2025 (78%).
Used in the deck's `problem` section. Source: BEIS QEP 5.1."""

# ---------------------------------------------------------------------------
# HUD-friendly summary (single dict — read by HUD-Benchmarks)
# ---------------------------------------------------------------------------

INDUSTRY_BENCHMARKS: Final[dict[str, float | str | tuple]] = {
    # Install
    "uk_install_cost_per_kw_gbp": UK_INSTALL_COST_PER_KW_GBP,
    "uk_install_cost_per_kw_range_gbp": UK_INSTALL_COST_PER_KW_RANGE_GBP,
    # Generation
    "uk_avg_irradiance_kwh_per_m2_yr": UK_AVG_IRRADIANCE_KWH_PER_M2_YR,
    "uk_typical_kwh_per_kwp_yr": UK_TYPICAL_KWH_PER_KWP_YR,
    "performance_derate_pct": PERFORMANCE_DERATE_PCT,
    "panel_degradation_per_year": PANEL_DEGRADATION_PER_YEAR,
    # Tariff / policy
    "seg_export_rate_gbp_per_kwh": UK_SEG_EXPORT_RATE_GBP_PER_KWH,
    "import_rate_gbp_per_kwh": UK_IMPORT_RATE_GBP_PER_KWH,
    "vat_residential_pct": VAT_RESIDENTIAL_PV_PCT,
    "aia_cap_gbp_million": AIA_CAP_GBP_MILLION,
    "full_expensing_available": FULL_EXPENSING_AVAILABLE,
    # Carbon
    "co2_kg_per_kwh_uk_2025": GRID_CARBON_KG_PER_KWH,
    "co2_kg_per_tree_per_year": CO2_KG_PER_TREE_PER_YEAR,
    # Returns
    "uk_typical_payback_years_commercial": UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL,
    "uk_typical_payback_range_years": UK_TYPICAL_PAYBACK_RANGE_YEARS,
    "uk_typical_irr_commercial": UK_TYPICAL_IRR_COMMERCIAL,
    # Market
    "uk_commercial_pv_growth_yoy_pct": UK_COMMERCIAL_PV_GROWTH_YOY_PCT,
    "uk_commercial_electricity_price_rise_since_2019_pct": (
        UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT
    ),
}
"""Compact dict consumed by the HUD-Benchmarks frontend chip + the deck
generator's "Industry Benchmarks" prompt section. Mirror this exactly in
`packages/shared/ts/src/industry_benchmarks.ts`.

When citing a number in user-facing copy, always pull from this dict —
do not hard-code. That keeps deck-generator output, calculator copy, and
HUD numbers in lock-step."""


__all__ = [
    "INDUSTRY_BENCHMARKS",
    "UK_INSTALL_COST_PER_KW_GBP",
    "UK_INSTALL_COST_PER_KW_RANGE_GBP",
    "PANEL_RATED_KW",
    "UK_AVG_IRRADIANCE_KWH_PER_M2_YR",
    "UK_TYPICAL_KWH_PER_KWP_YR",
    "PERFORMANCE_DERATE_PCT",
    "PANEL_DEGRADATION_PER_YEAR",
    "UK_SEG_EXPORT_RATE_GBP_PER_KWH",
    "UK_IMPORT_RATE_GBP_PER_KWH",
    "VAT_RESIDENTIAL_PV_PCT",
    "AIA_CAP_GBP_MILLION",
    "FULL_EXPENSING_AVAILABLE",
    "GRID_CARBON_KG_PER_KWH",
    "CO2_KG_PER_TREE_PER_YEAR",
    "UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL",
    "UK_TYPICAL_PAYBACK_RANGE_YEARS",
    "UK_TYPICAL_IRR_COMMERCIAL",
    "FUNDING_MODELS",
    "UK_COMMERCIAL_PV_GROWTH_YOY_PCT",
    "UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT",
]
