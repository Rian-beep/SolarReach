"""POST /lead/<id>/panels — STUB.

Mock panel array so MapSlot can render. Luke replaces with real Solar API
`findClosest` → ray-cast clip against `rooftop_polygon` → persist `panel_layout`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import get_db
from app.services.audit import log_audit

router = APIRouter()
log = logging.getLogger("solarreach.api.panels")


def _grid_panels(lng: float, lat: float, count: int = 12) -> list[dict]:
    panels: list[dict] = []
    # ~2m x 1m grid, 12 panels = 4 cols x 3 rows.
    cols, rows = 4, 3
    panel_lng = 0.00002  # ~1.4 m at UK lat
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
):
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")
    await log_audit(
        db,
        action="api.call",
        lead_id=lead_id,
        cost_cents=0,
        metadata={"provider": "google_solar.findClosest", "stub": True},
    )
    log.info("# A2 STUB panels lead=%s", lead_id)
    coords = (lead.get("geo", {}).get("point", {}) or {}).get("coordinates")
    lng, lat = coords if coords and len(coords) == 2 else (-0.0876, 51.5256)
    grid = _grid_panels(lng, lat, 12)
    annual = sum(p["kwh_yr"] for p in grid)
    payload = {
        "panels": grid,
        "panel_count": len(grid),
        "annual_kwh": annual,
        "clipped_at": datetime.now(timezone.utc).isoformat(),
        "clip_method": "stub_grid",  # TODO(LUKE): inspire_polygon_raycast.
    }
    await db.leads.update_one({"_id": lead_id}, {"$set": {"panel_layout": payload}})
    return payload
