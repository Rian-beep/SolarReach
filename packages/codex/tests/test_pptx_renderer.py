"""PPTX renderer tests — produces a valid 11-slide 16:9 deck."""

import pytest


SAMPLE_DECK = {
    "title": {
        "headline": "Grid Independence — 1 Old St",
        "subhead": "Solar PV proposal for Old Street Holdings Ltd",
        "decision_maker": "Sarah Patel, CFO",
    },
    "problem": {
        "heading": "The grid problem",
        "bullets": ["UK commercial electricity has risen 78% since 2019", "Volatility is the new normal"],
    },
    "solution": {
        "heading": "Rooftop solar — own your generation",
        "bullets": ["10,080 kWh/year on-site", "24 panels on existing roof", "30-year asset"],
    },
    "grid_independence": {
        "heading": "Grid independence",
        "body": "Your roof, your generation, your terms.",
        "metric_pct_offset": 42,
    },
    "roi": {
        "heading": "ROI",
        "capex_gbp": 24500,
        "annual_saving_gbp": 3120,
        "payback_years": 7.8,
        "npv_25yr_gbp": 41200,
    },
    "funding": {
        "heading": "5 ways to fund it",
        "models": [
            {"name": "Capital Expense", "fit": "Best NPV"},
            {"name": "Free Install", "fit": "Zero capex"},
            {"name": "Lease Purchase", "fit": "Balance"},
            {"name": "Operational Lease", "fit": "Off-balance-sheet"},
            {"name": "Hire Purchase", "fit": "VAT-efficient"},
        ],
    },
    "timeline": {
        "heading": "Timeline",
        "phases": [
            {"name": "Survey", "weeks": 2},
            {"name": "Design + DNO", "weeks": 6},
            {"name": "Install", "weeks": 4},
            {"name": "Commissioning", "weeks": 1},
        ],
    },
    "decision_maker_callout": {
        "heading": "For Sarah Patel, CFO",
        "body": "This is a finance decision dressed as a roof decision.",
    },
    "social_impact": {
        "heading": "Carbon offset",
        "tonnes_co2_yr": 2.4,
        "equiv_trees": 110,
    },
    "tech_specs": {
        "heading": "Tech",
        "panels": 24,
        "kw_peak": 9.6,
        "annual_kwh": 10080,
        "warranty_years": 25,
    },
    "cta": {
        "heading": "Next step",
        "body": "30-min call this week with Sarah Patel.",
        "contact": "hello@greensolar.uk",
    },
}


SAMPLE_BRAND = {"primary": "#0F172A", "logo_url": None, "name": "GreenSolar UK"}


def test_render_pptx_creates_11_slides(tmp_path):
    from codex_brain.generators.pptx_renderer import render_pptx
    pptx_path = render_pptx(SAMPLE_DECK, SAMPLE_BRAND, lead_id="lead_test_xyz", out_dir=tmp_path)
    assert pptx_path.exists()
    from pptx import Presentation
    pres = Presentation(str(pptx_path))
    assert len(pres.slides) == 11


def test_render_pptx_is_widescreen_169(tmp_path):
    from codex_brain.generators.pptx_renderer import render_pptx
    pptx_path = render_pptx(SAMPLE_DECK, SAMPLE_BRAND, lead_id="lead_test_169", out_dir=tmp_path)
    from pptx import Presentation
    pres = Presentation(str(pptx_path))
    # 16:9 dims in EMU: 12192000 x 6858000
    assert pres.slide_width == 12192000
    assert pres.slide_height == 6858000


def test_render_pptx_filename_uses_lead_id(tmp_path):
    from codex_brain.generators.pptx_renderer import render_pptx
    pptx_path = render_pptx(SAMPLE_DECK, SAMPLE_BRAND, lead_id="lead_my_id", out_dir=tmp_path)
    assert "lead_my_id" in pptx_path.name


def test_render_pptx_handles_missing_optional_fields(tmp_path):
    """Sonnet might omit a section — render should still produce 11 slides with placeholders."""
    from codex_brain.generators.pptx_renderer import render_pptx
    minimal = {"title": {"headline": "Test"}}
    pptx_path = render_pptx(minimal, SAMPLE_BRAND, lead_id="lead_min", out_dir=tmp_path)
    from pptx import Presentation
    pres = Presentation(str(pptx_path))
    assert len(pres.slides) == 11
