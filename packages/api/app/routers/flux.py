"""POST /lead/<id>/flux_overlay — STUB.

Returns a mock URL + bbox so frontend (A3) and Luke's Maps integration can
wire blind. Real Solar API `dataLayers:get` integration replaces this body.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.deps import get_db
from app.services.audit import log_audit

router = APIRouter()
log = logging.getLogger("solarreach.api.flux")


@router.post("/lead/{lead_id}/flux_overlay")
async def flux_overlay(
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
        metadata={"provider": "google_solar.dataLayers", "stub": True},
    )
    log.info("# A2 STUB flux_overlay lead=%s", lead_id)
    # TODO(LUKE): replace with real Solar API → GeoTIFF → reproject → PNG.
    # Bbox is a small box around our default demo coord.
    coords = (lead.get("geo", {}).get("point", {}) or {}).get("coordinates")
    if coords and len(coords) == 2:
        lng, lat = coords
    else:
        lng, lat = -0.0876, 51.5256
    delta = 0.0008
    payload = {
        "url": "/static/mock-flux.png",
        "bbox": [lng - delta, lat - delta, lng + delta, lat + delta],
        "vmin": 2.1,
        "vmax": 5.4,
        "cached_at": None,
    }
    await db.leads.update_one({"_id": lead_id}, {"$set": {"flux_overlay": payload}})
    return payload
