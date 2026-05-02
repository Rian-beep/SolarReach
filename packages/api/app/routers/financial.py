"""POST /financial/calculator — residential calculator mode.

Calls into the shared Py financial module if available; falls back to a
deterministic inline model otherwise so the endpoint never hard-fails.
"""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


class CalcRequest(BaseModel):
    address: str
    annual_kwh: float = Field(gt=0)
    premises_type: str = "residential"


def _calc(annual_kwh: float, premises_type: str) -> dict:
    """Try shared module; fall back to inline math.

    Inline model: 4 kW system, £6500 capex, £0.30/kWh saved, 25-year horizon
    at 4% discount.
    """
    try:  # pragma: no cover — shared package optional during dev.
        from solarreach_shared.financial import residential_breakdown  # type: ignore
        return residential_breakdown(annual_kwh=annual_kwh, premises_type=premises_type)
    except Exception:
        capex = 6500.0 if premises_type == "residential" else 24500.0
        saving = annual_kwh * 0.30
        payback = capex / saving if saving > 0 else 0.0
        # NPV at 4% over 25 years.
        r = 0.04
        years = 25
        npv = sum(saving / ((1 + r) ** y) for y in range(1, years + 1)) - capex
        return {
            "capex_gbp": round(capex, 2),
            "annual_saving_gbp": round(saving, 2),
            "payback_years": round(payback, 2),
            "npv_25yr_gbp": round(npv, 2),
        }


@router.post("/financial/calculator")
async def calculator(body: CalcRequest):
    return _calc(body.annual_kwh, body.premises_type)
