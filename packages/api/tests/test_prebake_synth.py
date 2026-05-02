"""Unit tests for the synthesised-panel fallback in scripts/prebake_demo.py.

We import the module via importlib because scripts/ is not a package — keeps
the test self-contained and avoids polluting the API's import graph.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def prebake():
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "scripts" / "prebake_demo.py"
    spec = importlib.util.spec_from_file_location("prebake_demo_under_test", script)
    assert spec and spec.loader, f"could not load {script}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# CodeNode demo polygon — same coords as `lead_codenode_demo.rooftop_polygon`.
CODENODE_POLY = {
    "type": "Polygon",
    "coordinates": [
        [
            [-0.087, 51.518],
            [-0.086, 51.518],
            [-0.086, 51.5188],
            [-0.087, 51.5188],
            [-0.087, 51.518],
        ]
    ],
    "source": "synthesized",
    "area_m2_approx": 720,
}


def test_synth_panel_layout_codenode(prebake) -> None:
    layout = prebake.synthesise_panel_layout(CODENODE_POLY)
    assert layout is not None
    assert layout["clip_method"] == "synthesised_for_demo"
    assert layout["synthesised"] is True
    # Spec target: ~150-200 panels for the CodeNode footprint.
    assert layout["panel_count"] == prebake.SYNTH_TARGET_PANELS
    assert 100 <= layout["panel_count"] <= 220
    # Every panel must be a 4-corner polygon.
    for p in layout["panels"]:
        assert len(p["corners"]) == 4
        assert all(len(c) == 2 for c in p["corners"])
        assert p["azimuth"] == 180.0
        assert p["tilt"] == 60.0
        assert p["kwh_yr"] > 0
    # Annual kWh should be panel_count * per-panel.
    assert layout["annual_kwh"] == pytest.approx(
        layout["panel_count"] * prebake.PANEL_KWH_YR
    )


def test_synth_corners_inside_polygon(prebake) -> None:
    layout = prebake.synthesise_panel_layout(CODENODE_POLY)
    assert layout
    ring = CODENODE_POLY["coordinates"][0]
    # Every corner of every panel must lie inside the rooftop polygon —
    # otherwise we'd render panels hanging off the roof on the demo.
    for panel in layout["panels"]:
        for lng, lat in panel["corners"]:
            assert prebake._point_in_ring(lng, lat, ring), (
                f"corner ({lng}, {lat}) outside ring"
            )


def test_synth_handles_missing_polygon(prebake) -> None:
    assert prebake.synthesise_panel_layout(None) is None
    assert prebake.synthesise_panel_layout({}) is None
    assert prebake.synthesise_panel_layout({"coordinates": []}) is None
    assert prebake.synthesise_panel_layout({"coordinates": [[]]}) is None


def test_synth_thin_polygon_returns_centroid_panel(prebake) -> None:
    """Polygons too thin to fit a 1.0×1.7m grid still get one centroid panel."""
    thin = {
        "type": "Polygon",
        "coordinates": [
            [
                [0.0, 0.0],
                [0.0, 0.000001],
                [0.000001, 0.000001],
                [0.000001, 0.0],
                [0.0, 0.0],
            ]
        ],
    }
    layout = prebake.synthesise_panel_layout(thin)
    assert layout is not None
    assert layout["panel_count"] == 1
    assert len(layout["panels"][0]["corners"]) == 4
