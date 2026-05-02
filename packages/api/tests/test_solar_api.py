"""Tests for app.services.solar_api — Google Solar API wrapper.

All HTTP calls are mocked via respx so these tests are hermetic and run
without a live `solar.googleapis.com` reachable.

Coverage:
1. findClosest rejects when reported building.center > 80m drift.
2. findClosest accepts ≤ 80m drift.
3. dataLayers URL has `key=` appended in params.
4. download_geotiff appends `?key=` to bare GeoTIFF URLs (cardinal rule
   — GeoTIFFs are on a separate origin but still need auth).
5. geotiff_to_inferno_png returns sensible bbox + vmin/vmax.
6. panel rotation math: south-facing (azimuth=180) panel oriented
   correctly with width along east axis.
7. ray-cast clip discards out-of-polygon panels.
"""
from __future__ import annotations

import math

import httpx
import numpy as np
import pytest
import respx

from app.config import Settings
from app.services import solar_api


def _settings() -> Settings:
    """Local Settings with a fixed key so respx assertions are stable."""
    return Settings(google_maps_api_key="test-key-xyz")


# ─── 1+2. findClosest 80m guard ─────────────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_find_closest_rejects_drift_over_80m():
    # Request London Old St; mock Solar API to return a building 200m north.
    req_lat, req_lng = 51.5256, -0.0876
    far_lat = req_lat + 0.0018  # ~200 m north of req
    respx.get("https://solar.googleapis.com/v1/buildingInsights:findClosest").mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "buildings/abc",
                "center": {"latitude": far_lat, "longitude": req_lng},
                "solarPanels": [],
            },
        )
    )
    with pytest.raises(solar_api.SolarAPIError, match="drift"):
        await solar_api.find_closest_building(req_lat, req_lng, _settings())


@pytest.mark.asyncio
@respx.mock
async def test_find_closest_accepts_drift_under_80m():
    req_lat, req_lng = 51.5256, -0.0876
    # ~30 m north — well within the 80 m threshold.
    near_lat = req_lat + 0.00027
    route = respx.get(
        "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "name": "buildings/abc",
                "center": {"latitude": near_lat, "longitude": req_lng},
                "solarPanels": [],
            },
        )
    )
    body = await solar_api.find_closest_building(req_lat, req_lng, _settings())
    assert body["name"] == "buildings/abc"
    assert route.called
    # Verify the API key was sent as a query param (cardinal rule —
    # NEVER referrer-restricted, use the URL key).
    sent = route.calls[0].request
    assert "key=test-key-xyz" in str(sent.url)


# ─── 3. dataLayers URL has key appended ─────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_data_layers_appends_key_param():
    route = respx.get("https://solar.googleapis.com/v1/dataLayers:get").mock(
        return_value=httpx.Response(
            200,
            json={
                "annualFluxUrl": "https://solar.googleusercontent.com/foo/flux.tif",
                "dsmUrl": "https://solar.googleusercontent.com/foo/dsm.tif",
                "maskUrl": "https://solar.googleusercontent.com/foo/mask.tif",
            },
        )
    )
    out = await solar_api.get_data_layers(51.5256, -0.0876, 50, _settings())
    assert "annualFluxUrl" in out
    sent = route.calls[0].request
    assert "key=test-key-xyz" in str(sent.url)
    assert "view=FULL_LAYERS" in str(sent.url)


# ─── 4. download_geotiff appends ?key= ──────────────────────────────


@pytest.mark.asyncio
@respx.mock
async def test_download_geotiff_appends_key_to_url():
    """GeoTIFF assets are on a separate origin but still require auth.

    This is the rule the README screams about: appending `?key=` to the
    annualFluxUrl is not optional.
    """
    bare_url = "https://solar.googleusercontent.com/foo/flux.tif"
    route = respx.get(bare_url).mock(
        return_value=httpx.Response(200, content=b"GEOTIFF_BYTES_SENTINEL")
    )
    out = await solar_api.download_geotiff(bare_url, _settings())
    assert out == b"GEOTIFF_BYTES_SENTINEL"
    sent = route.calls[0].request
    assert "key=test-key-xyz" in str(sent.url), str(sent.url)


# ─── 5. inferno PNG bbox + vmin/vmax ────────────────────────────────


def _build_synthetic_geotiff() -> bytes:
    """Build an in-memory single-band GeoTIFF with valid + nodata pixels.

    Uses rasterio's MemoryFile so we don't touch disk. Negative pixels
    represent nodata to exercise the masking path.
    """
    import rasterio
    from rasterio.io import MemoryFile
    from rasterio.transform import from_bounds

    # 16x16 EPSG:4326 raster centered on Old Street, ~50 m radius.
    w = 16
    h = 16
    cx, cy = -0.0876, 51.5256
    deg = 0.00045  # ~50 m at this latitude
    transform = from_bounds(cx - deg, cy - deg, cx + deg, cy + deg, w, h)
    data = np.linspace(2.0, 5.5, w * h, dtype="float32").reshape(h, w)
    # Mark a 4x4 corner as nodata (negative sentinel).
    data[:4, :4] = -9999.0
    profile = {
        "driver": "GTiff",
        "dtype": "float32",
        "count": 1,
        "width": w,
        "height": h,
        "crs": "EPSG:4326",
        "transform": transform,
        "nodata": -9999,
    }
    with MemoryFile() as mf:
        with mf.open(**profile) as ds:
            ds.write(data, 1)
        return mf.read()


def test_geotiff_to_inferno_png_outputs_sane_bbox_and_stretch(tmp_path):
    tiff = _build_synthetic_geotiff()
    out = tmp_path / "lead_x.png"
    meta = solar_api.geotiff_to_inferno_png(tiff, str(out))
    # File written.
    assert out.exists() and out.stat().st_size > 0
    # bbox is [w,s,e,n] in EPSG:4326 around Old Street.
    bbox = meta["bbox"]
    assert len(bbox) == 4
    w, s, e, n = bbox
    assert -1.0 < w < 0.0 < -w  # west of Greenwich
    assert 51.0 < s < n < 52.0  # London latitudes
    # 2-98% stretch: with our linspace(2.0, 5.5) and 16 nodata cells,
    # vmin should land between 2.0 and 2.5, vmax between 5.0 and 5.5.
    assert 2.0 <= meta["vmin"] < 3.0
    assert 5.0 < meta["vmax"] <= 5.5
    # Verify it's actually RGBA with transparency on the nodata corner.
    from PIL import Image

    img = Image.open(out)
    assert img.mode == "RGBA"
    # Top-left corner pixel was nodata → alpha must be 0.
    px = img.getpixel((0, img.size[1] - 1))  # PIL origin top-left, our nodata is top in array → bottom in img? rely on alpha 0 SOMEWHERE.
    # Just assert the alpha channel has some 0s (nodata) and some 220 (valid).
    arr = np.asarray(img)
    alphas = arr[..., 3]
    assert int(alphas.min()) == 0
    assert int(alphas.max()) == 220


# ─── 6. Panel rotation math (meters, theta = -azimuth) ──────────────


def test_panels_rotation_south_facing_aligns_north_south():
    """A south-facing panel (azimuth=180) on a south-facing roof: width
    runs east-west, height runs north-south. Verify corners.
    """
    # Build a fake buildingInsights with one south-facing panel.
    insights = {
        "solarPanels": [
            {
                "center": {"latitude": 51.5256, "longitude": -0.0876},
                "orientation": 180,
                "yearlyEnergyDcKwh": 420,
                "tiltDegrees": 35,
            }
        ]
    }
    panels = solar_api.panels_from_solar_api(
        insights, rooftop_polygon=None, panel_width_m=1.0, panel_height_m=1.7
    )
    assert len(panels) == 1
    p = panels[0]
    corners = p["corners"]
    assert len(corners) == 4
    # A 180deg rotation of the unit-square base [(-w/2,-h/2)...] is itself
    # negated. So the rotated corner offsets in meters should still be
    # ±0.5m east and ±0.85m north — the panel's bounding box is the same
    # as un-rotated (just corner order flipped).
    lats = [c[1] for c in corners]
    lngs = [c[0] for c in corners]
    # North-south span ~ 1.7 m → ~0.0000153 deg. Tolerance 5%.
    ns_span_deg = max(lats) - min(lats)
    expected_ns_deg = 1.7 / 111_320.0
    assert abs(ns_span_deg - expected_ns_deg) / expected_ns_deg < 0.05
    # East-west span ~ 1.0 m → ~0.0000144 deg at 51.5N (cos(51.5) ≈ 0.62).
    ew_span_deg = max(lngs) - min(lngs)
    expected_ew_deg = 1.0 / (111_320.0 * math.cos(math.radians(51.5256)))
    assert abs(ew_span_deg - expected_ew_deg) / expected_ew_deg < 0.05


def test_panels_rotation_90_swaps_axes():
    """Azimuth=90 (east-facing) rotates the panel: width now runs
    north-south, height runs east-west. The N-S extent should be the
    panel's WIDTH (1.0 m) and E-W should be its HEIGHT (1.7 m).
    """
    insights = {
        "solarPanels": [
            {
                "center": {"latitude": 51.5256, "longitude": -0.0876},
                "orientation": 90,
                "yearlyEnergyDcKwh": 420,
                "tiltDegrees": 35,
            }
        ]
    }
    panels = solar_api.panels_from_solar_api(
        insights, rooftop_polygon=None, panel_width_m=1.0, panel_height_m=1.7
    )
    p = panels[0]
    lats = [c[1] for c in p["corners"]]
    lngs = [c[0] for c in p["corners"]]
    ns_span_deg = max(lats) - min(lats)
    ew_span_deg = max(lngs) - min(lngs)
    # N-S extent should now be ~1.0 m (the width) — axes swapped.
    expected_ns_for_swap = 1.0 / 111_320.0
    expected_ew_for_swap = 1.7 / (111_320.0 * math.cos(math.radians(51.5256)))
    assert abs(ns_span_deg - expected_ns_for_swap) / expected_ns_for_swap < 0.05
    assert abs(ew_span_deg - expected_ew_for_swap) / expected_ew_for_swap < 0.05


# ─── 7. Ray-cast clip discards out-of-polygon panels ────────────────


def test_raycast_clip_discards_panels_outside_polygon():
    # Polygon: small square around (lng=0, lat=0) of half-size 0.001.
    rooftop = {
        "type": "Polygon",
        "coordinates": [
            [
                [-0.001, -0.001],
                [0.001, -0.001],
                [0.001, 0.001],
                [-0.001, 0.001],
                [-0.001, -0.001],
            ]
        ],
    }
    insights = {
        "solarPanels": [
            # Panel A: center at origin → fully inside.
            {
                "center": {"latitude": 0.0, "longitude": 0.0},
                "orientation": 180,
                "yearlyEnergyDcKwh": 420,
                "tiltDegrees": 35,
            },
            # Panel B: center far outside the square (0.01 lat).
            {
                "center": {"latitude": 0.01, "longitude": 0.0},
                "orientation": 180,
                "yearlyEnergyDcKwh": 420,
                "tiltDegrees": 35,
            },
        ]
    }
    out = solar_api.panels_from_solar_api(insights, rooftop)
    # Only the inside panel survives the ray-cast clip.
    assert len(out) == 1
    # Roughly verify it's the origin one.
    centroid_lng = sum(c[0] for c in out[0]["corners"]) / 4
    centroid_lat = sum(c[1] for c in out[0]["corners"]) / 4
    assert abs(centroid_lng) < 1e-6
    assert abs(centroid_lat) < 1e-6
