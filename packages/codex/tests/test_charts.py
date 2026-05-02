"""ROI chart smoke tests — file is created and is a valid PNG."""

import os


def test_roi_chart_creates_png(tmp_path):
    from codex_brain.generators.charts import roi_chart
    out = roi_chart(
        payback_years=7.8,
        capex=24500,
        annual_saving=3120,
        npv_25yr=41200,
        out_dir=tmp_path,
    )
    assert out.exists()
    assert out.suffix == ".png"
    assert out.stat().st_size > 1000  # non-trivial image
    # PNG magic bytes
    with open(out, "rb") as f:
        head = f.read(8)
    assert head[:8] == b"\x89PNG\r\n\x1a\n"


def test_roi_chart_handles_zero_saving(tmp_path):
    from codex_brain.generators.charts import roi_chart
    out = roi_chart(
        payback_years=99.0,
        capex=10000,
        annual_saving=0,
        npv_25yr=-10000,
        out_dir=tmp_path,
    )
    assert out.exists()


def test_roi_chart_filename_matches_lead_id(tmp_path):
    from codex_brain.generators.charts import roi_chart
    out = roi_chart(
        payback_years=7.8,
        capex=24500,
        annual_saving=3120,
        npv_25yr=41200,
        out_dir=tmp_path,
        lead_id="lead_abc123",
    )
    assert "lead_abc123" in out.name
