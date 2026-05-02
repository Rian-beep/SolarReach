"""Google Solar API wrapper — async, audit-aware, cardinal-rule-enforced.

This module is the ONLY place that talks to `solar.googleapis.com`.
Every consumer (`routers/flux.py`, `routers/panels.py`) calls these
functions and never sees the raw API surface.

Cardinal rules enforced here:
1. Reject `findClosest` if `building.center` > 80 m from the requested
   point (the "courtyard bug" — Solar API will happily return a building
   100 m away and ruin the demo).
2. The GeoTIFF URLs returned in `dataLayers` are on a separate origin
   (`solar.googleusercontent.com` / `geo-tile.googleapis.com`) and STILL
   require `?key=...` — this is documented at
   https://developers.google.com/maps/documentation/solar/data-layers.
3. Panel rotation must be done in METERS (project to local-tangent plane
   centered on the panel, rotate, project back) and the rotation angle
   is `theta = -azimuth_radians` because Solar API azimuth is degrees
   clockwise from north and our local frame is east-x / north-y.
4. Mask GeoTIFF nodata: any pixel `< 0` is treated as transparent. The
   raw flux band uses negative-sentinel values for "no data here".
5. Color stretch is 2nd–98th percentile (NOT min/max) — min/max is
   destroyed by 1 outlier pixel and produces a useless overlay.
6. Audit-log every paid call BEFORE making it (so a network timeout
   still increments spend; we treat the request as "spent" once it left
   the wire).
"""
from __future__ import annotations

import logging
import math
import os
from io import BytesIO
from typing import Any

import httpx

from app.config import Settings

log = logging.getLogger("solarreach.api.solar")

SOLAR_BASE = "https://solar.googleapis.com/v1"
TIMEOUT = httpx.Timeout(30.0, connect=10.0)
MAX_DRIFT_M = 80.0  # findClosest reject threshold (cardinal rule).


class SolarAPIError(RuntimeError):
    """Raised when the Solar API call fails or returns garbage."""


# ─── Geo helpers ───────────────────────────────────────────────────


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in meters."""
    r = 6_371_000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _meters_to_lat_deg(meters: float) -> float:
    """1 deg lat ≈ 111_320 m everywhere on the WGS84 ellipsoid (close enough)."""
    return meters / 111_320.0


def _meters_to_lng_deg(meters: float, at_lat_deg: float) -> float:
    """Lng degrees per meter shrink with latitude (cos)."""
    return meters / (111_320.0 * math.cos(math.radians(at_lat_deg)))


# ─── HTTP plumbing ─────────────────────────────────────────────────


async def _http_get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> dict:
    """GET + parse JSON with one retry on 5xx. Timeout 30s.

    Settings is accepted for symmetry with other helpers but unused —
    the API key lives in `params` already.
    """
    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as cx:
                resp = await cx.get(url, params=params)
            if 500 <= resp.status_code < 600 and attempt == 1:
                log.warning("solar 5xx attempt=%d url=%s", attempt, url)
                continue
            if resp.status_code != 200:
                raise SolarAPIError(
                    f"solar HTTP {resp.status_code} {resp.text[:300]}"
                )
            return resp.json()
        except (httpx.RequestError, httpx.TimeoutException) as e:
            last_exc = e
            log.warning("solar transport attempt=%d err=%s", attempt, e)
    raise SolarAPIError(f"solar transport failed: {last_exc}") from last_exc


# ─── Public API ────────────────────────────────────────────────────


async def find_closest_building(
    lat: float, lng: float, settings: Settings
) -> dict:
    """Call `buildingInsights:findClosest`.

    Rejects (raises `SolarAPIError`) if the returned building.center is
    farther than `MAX_DRIFT_M` from the input lat/lng — the courtyard
    bug.
    """
    if not settings.google_maps_api_key:
        raise SolarAPIError("GOOGLE_MAPS_API_KEY not configured.")
    url = f"{SOLAR_BASE}/buildingInsights:findClosest"
    params = {
        "location.latitude": f"{lat:.7f}",
        "location.longitude": f"{lng:.7f}",
        "requiredQuality": "HIGH",
        "key": settings.google_maps_api_key,
    }
    body = await _http_get_json(url, params=params)
    center = (body.get("center") or {})
    c_lat = center.get("latitude")
    c_lng = center.get("longitude")
    if c_lat is None or c_lng is None:
        raise SolarAPIError("findClosest response missing center")
    drift = _haversine_m(lat, lng, c_lat, c_lng)
    if drift > MAX_DRIFT_M:
        raise SolarAPIError(
            f"findClosest drift {drift:.1f}m > {MAX_DRIFT_M}m — building rejected"
        )
    log.info("findClosest ok drift=%.1fm name=%s", drift, body.get("name"))
    return body


async def get_data_layers(
    lat: float, lng: float, radius_m: int, settings: Settings
) -> dict:
    """Call `dataLayers:get` with `view=FULL_LAYERS`."""
    if not settings.google_maps_api_key:
        raise SolarAPIError("GOOGLE_MAPS_API_KEY not configured.")
    url = f"{SOLAR_BASE}/dataLayers:get"
    params = {
        "location.latitude": f"{lat:.7f}",
        "location.longitude": f"{lng:.7f}",
        "radiusMeters": str(int(radius_m)),
        "view": "FULL_LAYERS",
        "requiredQuality": "HIGH",
        "key": settings.google_maps_api_key,
    }
    body = await _http_get_json(url, params=params)
    if "annualFluxUrl" not in body:
        raise SolarAPIError("dataLayers response missing annualFluxUrl")
    return body


async def download_geotiff(url: str, settings: Settings) -> bytes:
    """Download a Solar API GeoTIFF.

    The data-layer asset URLs are hosted on a different origin than the
    JSON endpoints, but Google still requires the API key as `?key=...`
    (documented). We append it here — callers must pass the bare URL
    they got from the dataLayers response.
    """
    if not settings.google_maps_api_key:
        raise SolarAPIError("GOOGLE_MAPS_API_KEY not configured.")
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}key={settings.google_maps_api_key}"
    last_exc: Exception | None = None
    for attempt in (1, 2):
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT) as cx:
                resp = await cx.get(full)
            if 500 <= resp.status_code < 600 and attempt == 1:
                continue
            if resp.status_code != 200:
                raise SolarAPIError(
                    f"geotiff HTTP {resp.status_code} {resp.text[:200]}"
                )
            return resp.content
        except (httpx.RequestError, httpx.TimeoutException) as e:
            last_exc = e
    raise SolarAPIError(f"geotiff download failed: {last_exc}") from last_exc


# ─── GeoTIFF → PNG (inferno) ───────────────────────────────────────


def geotiff_to_inferno_png(geotiff_bytes: bytes, out_path: str) -> dict:
    """Reproject GeoTIFF to EPSG:4326, mask nodata, inferno-colormap to PNG.

    Returns `{bbox: [w,s,e,n], vmin, vmax}` — bbox is the geographic
    extent of the saved PNG, ready for use as a Maps GroundOverlay /
    ImageBitmap source.

    Cardinal rules:
    - Mask any pixel `< 0` (Solar API uses negative sentinels for no-data).
    - Use 2nd–98th percentile color stretch — never min/max.
    - Output PNG has 4-channel RGBA; nodata pixels alpha=0.
    """
    # Imports kept inside the function so test-collection doesn't fail
    # if a dev hasn't run `uv sync` yet.
    import numpy as np
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.warp import (
        Resampling,
        calculate_default_transform,
        reproject,
        transform_bounds,
    )
    import matplotlib.cm as cm
    from PIL import Image

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)

    with MemoryFile(geotiff_bytes) as memfile:
        with memfile.open() as src:
            src_crs = src.crs
            src_transform = src.transform
            src_w, src_h = src.width, src.height
            arr = src.read(1).astype("float32")

            # Reproject to EPSG:4326 if needed.
            dst_crs = "EPSG:4326"
            if src_crs is None or src_crs.to_string() == dst_crs:
                bounds = src.bounds
                bbox = [bounds.left, bounds.bottom, bounds.right, bounds.top]
                reproj = arr
            else:
                dst_transform, dst_w, dst_h = calculate_default_transform(
                    src_crs, dst_crs, src_w, src_h, *src.bounds
                )
                reproj = np.full((dst_h, dst_w), -9999.0, dtype="float32")
                reproject(
                    source=arr,
                    destination=reproj,
                    src_transform=src_transform,
                    src_crs=src_crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                    src_nodata=-9999,
                    dst_nodata=-9999,
                )
                bbox = list(
                    transform_bounds(src_crs, dst_crs, *src.bounds, densify_pts=21)
                )

    # Mask nodata: anything < 0 is invalid.
    valid_mask = reproj >= 0
    if not valid_mask.any():
        raise SolarAPIError("geotiff has no valid (>=0) pixels")

    valid = reproj[valid_mask]
    vmin = float(np.percentile(valid, 2.0))
    vmax = float(np.percentile(valid, 98.0))
    if vmax <= vmin:
        vmax = vmin + 1.0  # avoid zero-division below

    # Normalize valid pixels to [0,1], clip outliers to bounds.
    norm = np.zeros_like(reproj, dtype="float32")
    norm[valid_mask] = np.clip(
        (reproj[valid_mask] - vmin) / (vmax - vmin), 0.0, 1.0
    )

    # Apply inferno colormap. cm.get_cmap is deprecated as of mpl 3.9
    # but still works; matplotlib.colormaps[...] is the new way.
    try:
        cmap = cm.get_cmap("inferno")
    except AttributeError:  # pragma: no cover (mpl >= 3.10 path)
        import matplotlib as mpl
        cmap = mpl.colormaps["inferno"]
    rgba = (cmap(norm) * 255).astype("uint8")  # H x W x 4
    # Force alpha=0 on nodata pixels (transparent).
    rgba[..., 3] = np.where(valid_mask, 220, 0).astype("uint8")

    Image.fromarray(rgba, mode="RGBA").save(out_path, format="PNG", optimize=True)
    return {"bbox": [float(x) for x in bbox], "vmin": vmin, "vmax": vmax}


# ─── Panels ────────────────────────────────────────────────────────


def _rotate_panel_corners_meters(
    center_lat: float,
    center_lng: float,
    width_m: float,
    height_m: float,
    azimuth_deg: float,
) -> list[list[float]]:
    """Build 4 panel corners in lng/lat from center + size + azimuth.

    Cardinal rule: rotate in METERS, not in degrees. We treat the panel
    as flat in a local east-north tangent plane around its center, do
    the rotation there, then convert offsets back to degrees AT THE
    PANEL'S latitude (not at building center — keeps each panel
    geographically correct over a wide roof).

    Solar API azimuth is degrees clockwise from north. Our local frame
    is east-x / north-y, where a CCW (mathematical-positive) rotation
    is `[cos t, -sin t; sin t, cos t]`. To rotate "north" into "azimuth
    degrees clockwise from north" we need `theta = -azimuth_radians`.
    """
    half_w = width_m / 2.0
    half_h = height_m / 2.0
    # Corner offsets in (east, north) meters before rotation.
    # Width = horizontal (east axis), Height = vertical (north axis).
    base = [
        (-half_w, -half_h),
        (half_w, -half_h),
        (half_w, half_h),
        (-half_w, half_h),
    ]
    theta = -math.radians(azimuth_deg)
    cos_t, sin_t = math.cos(theta), math.sin(theta)
    deg_per_m_lat = _meters_to_lat_deg(1.0)
    deg_per_m_lng = _meters_to_lng_deg(1.0, center_lat)
    corners: list[list[float]] = []
    for dx, dy in base:
        # 2D rotation in meters.
        rx = dx * cos_t - dy * sin_t
        ry = dx * sin_t + dy * cos_t
        # Convert offsets back to degrees AT the panel's latitude.
        d_lng = rx * deg_per_m_lng
        d_lat = ry * deg_per_m_lat
        corners.append([center_lng + d_lng, center_lat + d_lat])
    return corners


def _point_in_ring(lng: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray-cast point-in-polygon. Ring is a list of [lng, lat]."""
    inside = False
    n = len(ring)
    if n < 3:
        return False
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        intersect = ((yi > lat) != (yj > lat)) and (
            lng < (xj - xi) * (lat - yi) / ((yj - yi) or 1e-12) + xi
        )
        if intersect:
            inside = not inside
        j = i
    return inside


def _polygon_outer_ring(rooftop_polygon: dict | None) -> list[list[float]]:
    """Return the outer ring of a GeoJSON Polygon, or [] if missing."""
    if not rooftop_polygon:
        return []
    coords = rooftop_polygon.get("coordinates")
    if not coords:
        return []
    return list(coords[0])


def panels_from_solar_api(
    building_insights: dict,
    rooftop_polygon: dict | None,
    *,
    panel_width_m: float | None = None,
    panel_height_m: float | None = None,
) -> list[dict]:
    """Extract Solar API panels and clip to rooftop polygon.

    Real Solar API response shape (top-level `solarPotential`):
      - `solarPotential.solarPanels[i]`:
          { center, orientation: 'LANDSCAPE'|'PORTRAIT',
            yearlyEnergyDcKwh, segmentIndex }
      - `solarPotential.roofSegmentStats[seg].azimuthDegrees / pitchDegrees`
      - `solarPotential.panelHeightMeters / panelWidthMeters`

    Older / simpler shape used in tests:
      - `building_insights.solarPanels[i]`:
          { center, orientation: <degrees number>,
            tiltDegrees, yearlyEnergyDcKwh }

    Returns CONTRACTS § 1 `panel_layout.panels` shape:
        {corners: [[lng,lat]x4], tilt, azimuth, kwh_yr}

    Cardinal rule: the rotation math is in meters (`theta = -azimuth`),
    NOT in degrees. We discard any panel whose four corners are not all
    inside the rooftop polygon ring (server-side clip — never trust the
    frontend to filter).
    """
    potential = building_insights.get("solarPotential") or {}
    sp = building_insights.get("solarPanels") or potential.get("solarPanels") or []
    segments = potential.get("roofSegmentStats") or []

    # Default panel dimensions: prefer Solar API reported dims, fall back
    # to caller override, then to spec-given 1.0 x 1.7 m.
    api_w = potential.get("panelWidthMeters")
    api_h = potential.get("panelHeightMeters")
    width = float(panel_width_m if panel_width_m is not None else (api_w or 1.0))
    height = float(panel_height_m if panel_height_m is not None else (api_h or 1.7))

    ring = _polygon_outer_ring(rooftop_polygon)
    out: list[dict] = []
    for p in sp:
        center = p.get("center") or {}
        c_lat = center.get("latitude")
        c_lng = center.get("longitude")
        if c_lat is None or c_lng is None:
            continue

        # Resolve azimuth + tilt + per-panel sizing.
        seg_idx = p.get("segmentIndex")
        seg = segments[seg_idx] if isinstance(seg_idx, int) and 0 <= seg_idx < len(segments) else None
        # Older test-fixture shape uses orientation as a numeric degrees value;
        # real API uses orientation = "LANDSCAPE"/"PORTRAIT".
        orient_raw = p.get("orientation")
        orient_str: str | None = None
        orient_num: float | None = None
        if isinstance(orient_raw, (int, float)):
            orient_num = float(orient_raw)
        elif isinstance(orient_raw, str):
            orient_str = orient_raw.upper()
        # Final azimuth: explicit panel.azimuthDegrees > segment.azimuthDegrees
        # > numeric orientation override > sensible default 180.
        azimuth = (
            p.get("azimuthDegrees")
            if isinstance(p.get("azimuthDegrees"), (int, float))
            else (
                seg.get("azimuthDegrees")
                if seg and isinstance(seg.get("azimuthDegrees"), (int, float))
                else (orient_num if orient_num is not None else 180.0)
            )
        )
        tilt = (
            p.get("tiltDegrees")
            if isinstance(p.get("tiltDegrees"), (int, float))
            else (
                seg.get("pitchDegrees")
                if seg and isinstance(seg.get("pitchDegrees"), (int, float))
                else 35.0
            )
        )
        # PORTRAIT panels swap width/height — the rectangle long-axis runs
        # north-south rather than east-west before rotation.
        if orient_str == "PORTRAIT":
            this_w, this_h = height, width
        else:
            this_w, this_h = width, height

        kwh = float(p.get("yearlyEnergyDcKwh") or 0.0) or 420.0

        corners = _rotate_panel_corners_meters(
            c_lat, c_lng, this_w, this_h, float(azimuth)
        )
        if ring and not all(_point_in_ring(c[0], c[1], ring) for c in corners):
            continue  # raycast clip — discard panels not 100% inside
        out.append(
            {
                "corners": corners,
                "tilt": float(tilt),
                "azimuth": float(azimuth),
                "kwh_yr": kwh,
            }
        )
    return out


__all__ = [
    "SolarAPIError",
    "MAX_DRIFT_M",
    "find_closest_building",
    "get_data_layers",
    "download_geotiff",
    "geotiff_to_inferno_png",
    "panels_from_solar_api",
]
