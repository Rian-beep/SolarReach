"""Reference constants for SolarReach financial / fund modelling.

All monetary values are GBP. Energy values are kWh.
Sources documented in agent log.
"""

from __future__ import annotations

# --- Hardware & install ---
PANEL_UNIT_COST_GBP: float = 850.0  # per panel, supply cost
INSTALL_COST_PER_KW_GBP: float = 180.0  # labour + scaffolding per kW installed
PANEL_RATED_KW: float = 0.42  # 420W panel typical
INSTALLER_MARGIN_PCT: float = 0.04  # 4% margin baked into capex

# --- Tariffs (UK, 2026) ---
UK_SEG_EXPORT_RATE_GBP_PER_KWH: float = 0.15
UK_IMPORT_RATE_GBP_PER_KWH: float = 0.27
RESIDENTIAL_VAT_PCT: float = 0.0  # 0% VAT for residential solar (UK 2022-)

# --- Self-consumption split (typical) ---
SELF_CONSUME_FRACTION: float = 0.50  # 50% used on-site, 50% exported

# --- NPV ---
DISCOUNT_RATE: float = 0.05  # 5% real discount rate
NPV_HORIZON_YEARS: int = 25
PANEL_DEGRADATION_PER_YEAR: float = 0.005  # 0.5% per year

# --- Composite score weighting ---
SCORE_WEIGHT_SOLAR_ROI: float = 0.5
SCORE_WEIGHT_FIN_HEALTH: float = 0.3
SCORE_WEIGHT_SOCIAL_IMPACT: float = 0.2
SCORE_THRESHOLD_DEFAULT: int = 70

# --- Fund model reference (impact / green-investor) ---
FUND_MODELS: dict[str, dict[str, float]] = {
    "greensolar_uk_residential": {
        "min_composite_score": 70.0,
        "target_irr": 0.08,
        "max_payback_years": 12.0,
        "carbon_price_gbp_per_tco2": 85.0,
    },
    "greensolar_uk_commercial": {
        "min_composite_score": 75.0,
        "target_irr": 0.10,
        "max_payback_years": 9.0,
        "carbon_price_gbp_per_tco2": 85.0,
    },
}

# --- Carbon ---
GRID_CARBON_KG_PER_KWH: float = 0.207  # UK 2025 grid intensity

# --- Target postcodes (demo) ---
DEMO_POSTCODES: list[str] = ["EC1Y 8AF", "EC1V 9FR", "WC1H 0PD", "BS1 4ST", "BS2 0PT"]
