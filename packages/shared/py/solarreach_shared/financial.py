"""Financial / scoring math for SolarReach.

All sums in GBP; energy in kWh; rates per kWh.
"""

from __future__ import annotations

from . import constants


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def composite_score(solar_roi: float, fin_health: float, social_impact: float) -> int:
    """Weighted composite score in 0..100.

    Inputs are unit-interval [0,1]; out-of-range values are clamped before weighting.
    Weights: solar_roi 0.5, financial_health 0.3, social_impact 0.2.
    """
    s = (
        _clamp(solar_roi) * constants.SCORE_WEIGHT_SOLAR_ROI
        + _clamp(fin_health) * constants.SCORE_WEIGHT_FIN_HEALTH
        + _clamp(social_impact) * constants.SCORE_WEIGHT_SOCIAL_IMPACT
    )
    return int(round(s * 100))


def roi_gate(score: int, threshold: int = constants.SCORE_THRESHOLD_DEFAULT) -> bool:
    """Pass/fail gate over a composite score (>= threshold)."""
    return score >= threshold


def capex(panel_count: int) -> float:
    """Estimated capex (GBP) including 4% installer margin.

    capex = (panel_count * panel_unit_cost + rated_kw * install_per_kw) * (1 + margin)
    """
    if panel_count <= 0:
        return 0.0
    rated_kw = panel_count * constants.PANEL_RATED_KW
    base = (
        panel_count * constants.PANEL_UNIT_COST_GBP
        + rated_kw * constants.INSTALL_COST_PER_KW_GBP
    )
    return base * (1.0 + constants.INSTALLER_MARGIN_PCT)


def annual_saving_gbp(annual_kwh: float) -> float:
    """Modelled annual saving = self-consumed kWh * import rate
    + exported kWh * SEG export rate.
    """
    if annual_kwh <= 0:
        return 0.0
    self_consumed = annual_kwh * constants.SELF_CONSUME_FRACTION
    exported = annual_kwh - self_consumed
    return (
        self_consumed * constants.UK_IMPORT_RATE_GBP_PER_KWH
        + exported * constants.UK_SEG_EXPORT_RATE_GBP_PER_KWH
    )


def payback_years(capex_gbp: float, annual_saving_gbp: float) -> float:
    """Simple payback. Returns +inf if saving is non-positive."""
    if annual_saving_gbp <= 0:
        return float("inf")
    return capex_gbp / annual_saving_gbp


def npv_25yr(capex_gbp: float, annual_saving_gbp: float) -> float:
    """25-year NPV with 0.5%/yr panel degradation, fixed discount rate.

    NPV = -capex + sum_{t=1..25} saving_t / (1+r)^t
    saving_t = annual_saving_gbp * (1 - degradation)^(t-1)
    """
    npv = -float(capex_gbp)
    for t in range(1, constants.NPV_HORIZON_YEARS + 1):
        deg = (1.0 - constants.PANEL_DEGRADATION_PER_YEAR) ** (t - 1)
        cf = annual_saving_gbp * deg
        disc = (1.0 + constants.DISCOUNT_RATE) ** t
        npv += cf / disc
    return npv


if __name__ == "__main__":
    # Smoke run
    print("composite_score(0.8, 0.6, 0.4) =", composite_score(0.8, 0.6, 0.4))
    print("roi_gate(74) =", roi_gate(74))
    print("capex(24 panels) = £", round(capex(24), 2))
    print("annual_saving(10000 kWh) = £", round(annual_saving_gbp(10000), 2))
    print(
        "payback_years(20000, 2500) =",
        round(payback_years(20000.0, 2500.0), 2),
    )
    print(
        "npv_25yr(20000, 2500) = £",
        round(npv_25yr(20000.0, 2500.0), 2),
    )
