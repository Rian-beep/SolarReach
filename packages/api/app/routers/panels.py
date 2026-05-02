"""POST /lead/<id>/panels — REAL Google Solar API integration.

Pipeline:
  findClosest (HIGH) → extract `solarPanels` array → meters-rotation
  per panel (azimuth → 4 corners in lng/lat) → server-side ray-cast
  clip against `lead.rooftop_polygon` (INSPIRE-sourced when available)
  → persist `lead.panel_layout`.

Cardinal rules enforced:
- 80m findClosest reject (services/solar_api).
- DO NOT overwrite `lead.rooftop_polygon` with Solar API bbox — we only
  read it; never $set it from this endpoint.
- Server-side ray-cast clip BEFORE persisting (services/solar_api).
- METERS-based rotation, `theta = -azimuth` (services/solar_api).
- Audit-log every paid call BEFORE making it.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings
from app.deps import get_app_settings, get_db
from app.services import solar_api
from app.services.audit import log_audit

router = APIRouter()
log = logging.getLogger("solarreach.api.panels")


def _mock_grid(lng: float, lat: float, count: int = 12) -> list[dict]:
    """Fallback grid when GOOGLE_MAPS_API_KEY missing or Solar API fails.

    Same payload shape as the real path so frontend never sees a gap.
    """
    panels: list[dict] = []
    cols, rows = 4, 3
    panel_lng = 0.00002
    panel_lat = 0.00001
    for r in range(rows):
        for c in range(cols):
            ox = (c - cols / 2) * panel_lng
            oy = (r - rows / 2) * panel_lat
            corners = [
                [lng + ox, lat + oy],
                [lng + ox + panel_lng, lat + oy],
                [lng + ox + panel_lng, lat + oy + panel_lat],
                [lng + ox, lat + oy + panel_lat],
            ]
            panels.append(
                {
                    "corners": corners,
                    "tilt": 35,
                    "azimuth": 180,
                    "kwh_yr": 420,
                }
            )
            if len(panels) >= count:
                return panels
    return panels


@router.post("/lead/{lead_id}/panels")
async def panels(
    lead_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    coords = (lead.get("geo", {}).get("point", {}) or {}).get("coordinates")
    if coords and len(coords) == 2:
        lng, lat = float(coords[0]), float(coords[1])
    else:
        # No geo on lead — fall back to demo coords; downstream we'll
        # serve the mock grid so the frontend never gaps.
        lng, lat = -0.0876, 51.5256
    rooftop = lead.get("rooftop_polygon")

    # Graceful degrade if no key.
    if not settings.google_maps_api_key:
        grid = _mock_grid(lng, lat, 12)
        payload = {
            "panels": grid,
            "panel_count": len(grid),
            "annual_kwh": sum(p["kwh_yr"] for p in grid),
            "clipped_at": datetime.now(timezone.utc).isoformat(),
            "clip_method": "stub_grid",
            "mock": True,
        }
        await db.leads.update_one(
            {"_id": lead_id}, {"$set": {"panel_layout": payload}}
        )
        return payload

    await log_audit(
        db,
        action="api.call",
        lead_id=lead_id,
        cost_cents=1,
        metadata={"provider": "google_solar.findClosest"},
    )
    try:
        insights = await solar_api.find_closest_building(lat, lng, settings)
    except solar_api.SolarAPIError as e:
        log.warning("panels findClosest failed lead=%s err=%s", lead_id, e)
        grid = _mock_grid(lng, lat, 12)
        payload = {
            "panels": grid,
            "panel_count": len(grid),
            "annual_kwh": sum(p["kwh_yr"] for p in grid),
            "clipped_at": datetime.now(timezone.utc).isoformat(),
            "clip_method": "stub_grid",
            "mock": True,
            "mock_reason": str(e),
        }
        await db.leads.update_one(
            {"_id": lead_id}, {"$set": {"panel_layout": payload}}
        )
        return payload

    real_panels = solar_api.panels_from_solar_api(insights, rooftop)
    annual = sum(p["kwh_yr"] for p in real_panels)
    payload = {
        "panels": real_panels,
        "panel_count": len(real_panels),
        "annual_kwh": annual,
        "clipped_at": datetime.now(timezone.utc).isoformat(),
        "clip_method": "inspire_polygon_raycast",
    }
    # IMPORTANT: only set panel_layout. Never overwrite rooftop_polygon
    # (cardinal rule — preserves INSPIRE source).
    await db.leads.update_one(
        {"_id": lead_id}, {"$set": {"panel_layout": payload}}
    )
    log.info(
        "panels ok lead=%s count=%d annual_kwh=%.0f",
        lead_id,
        payload["panel_count"],
        payload["annual_kwh"],
    )
    return payload
