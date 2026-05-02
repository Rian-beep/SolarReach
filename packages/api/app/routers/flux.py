"""POST /lead/<id>/flux_overlay — REAL Google Solar API integration.

Pipeline:
  findClosest (HIGH) → dataLayers:get (FULL_LAYERS) → download annualFluxUrl
  → reproject to EPSG:4326 + 2-98% inferno colormap → PNG at /tmp/flux/<id>.png
  → persist `lead.flux_overlay` and return CONTRACTS § 2 shape.

Cache by `lead_id`: if `flux_overlay.cached_at` is < 24h old we serve the
cached result without any paid API calls.

Cardinal rules enforced:
- 80m findClosest reject (services/solar_api).
- `?key=` appended to GeoTIFF URL (services/solar_api).
- Audit-log every paid call BEFORE making it.
- Mask negative-sentinel nodata; 2nd–98th percentile color stretch
  (services/solar_api.geotiff_to_inferno_png).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings
from app.deps import get_app_settings, get_db
from app.services import solar_api
from app.services.audit import log_audit

router = APIRouter()
log = logging.getLogger("solarreach.api.flux")

FLUX_DIR = "/tmp/flux"
CACHE_HOURS = 24


def _is_cache_fresh(cached_at: str | None) -> bool:
    if not cached_at:
        return False
    try:
        ts = datetime.fromisoformat(cached_at.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return False
    return datetime.now(timezone.utc) - ts < timedelta(hours=CACHE_HOURS)


def _mock_payload(lng: float, lat: float) -> dict:
    """Fallback when GOOGLE_MAPS_API_KEY missing or Solar API unreachable.

    Same shape as success path so the frontend never breaks.
    """
    delta = 0.0008
    return {
        "url": "/static/mock-flux.png",
        "bbox": [lng - delta, lat - delta, lng + delta, lat + delta],
        "vmin": 2.1,
        "vmax": 5.4,
        "cached_at": datetime.now(timezone.utc).isoformat(),
        "mock": True,
    }


@router.post("/lead/{lead_id}/flux_overlay")
async def flux_overlay(
    lead_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    # Cache hit → return cached, no paid call.
    cached = lead.get("flux_overlay") or {}
    if _is_cache_fresh(cached.get("cached_at")) and cached.get("url"):
        log.info("flux_overlay cache-hit lead=%s", lead_id)
        return {
            "url": cached["url"],
            "bbox": cached["bbox"],
            "vmin": cached["vmin"],
            "vmax": cached["vmax"],
            "cached_at": cached["cached_at"],
        }

    coords = (lead.get("geo", {}).get("point", {}) or {}).get("coordinates")
    if coords and len(coords) == 2:
        lng, lat = float(coords[0]), float(coords[1])
    else:
        # No geo on lead — fall back to demo coords; downstream we'll
        # serve the mock payload so the frontend never gaps.
        lng, lat = -0.0876, 51.5256

    # Graceful degrade if no key.
    if not settings.google_maps_api_key:
        payload = _mock_payload(lng, lat)
        await db.leads.update_one(
            {"_id": lead_id}, {"$set": {"flux_overlay": payload}}
        )
        return payload

    # Audit BEFORE call (cardinal rule). 1c findClosest + 2c dataLayers = 3c.
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
        log.warning("flux findClosest failed lead=%s err=%s", lead_id, e)
        payload = _mock_payload(lng, lat)
        payload["mock_reason"] = str(e)
        await db.leads.update_one(
            {"_id": lead_id}, {"$set": {"flux_overlay": payload}}
        )
        return payload

    await log_audit(
        db,
        action="api.call",
        lead_id=lead_id,
        cost_cents=2,
        metadata={"provider": "google_solar.dataLayers"},
    )
    try:
        # Use the building's reported center as the data-layers anchor.
        c = insights.get("center", {})
        c_lat = float(c.get("latitude", lat))
        c_lng = float(c.get("longitude", lng))
        layers = await solar_api.get_data_layers(c_lat, c_lng, 50, settings)
        flux_url = layers.get("annualFluxUrl")
        if not flux_url:
            raise solar_api.SolarAPIError("no annualFluxUrl in dataLayers")
        tiff_bytes = await solar_api.download_geotiff(flux_url, settings)
        out_path = os.path.join(FLUX_DIR, f"{lead_id}.png")
        # Use the S3-aware variant: same return shape with extra `s3_url`
        # / `s3_uploaded` keys. S3 mode is auto-detected from env, so this
        # is a no-op when AWS_* aren't configured.
        meta = await solar_api.geotiff_to_inferno_png_with_s3(
            tiff_bytes, out_path, s3_key=f"flux/{lead_id}.png"
        )
    except (solar_api.SolarAPIError, Exception) as e:  # noqa: BLE001
        log.warning("flux dataLayers/render failed lead=%s err=%s", lead_id, e)
        payload = _mock_payload(lng, lat)
        payload["mock_reason"] = str(e)
        await db.leads.update_one(
            {"_id": lead_id}, {"$set": {"flux_overlay": payload}}
        )
        return payload

    payload = {
        "url": f"/static/flux/{lead_id}.png",
        "bbox": meta["bbox"],
        "vmin": meta["vmin"],
        "vmax": meta["vmax"],
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.leads.update_one(
        {"_id": lead_id}, {"$set": {"flux_overlay": payload}}
    )
    log.info(
        "flux_overlay ok lead=%s bbox=%s v=%s..%s",
        lead_id,
        payload["bbox"],
        payload["vmin"],
        payload["vmax"],
    )
    return payload
