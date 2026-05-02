"""python-pptx renderer for SolarReach pitch decks.

Output: 11 slides, 16:9, dark theme by default, brand-color accents.
Slide map (must be stable — A2 frontend embeds these in order):
  1. Title
  2. Problem
  3. Solution
  4. Grid Independence
  5. ROI (with embedded matplotlib chart)
  6. Funding (5 models)
  7. Timeline
  8. Decision-maker callout
  9. Social impact
 10. Tech specs
 11. CTA

The renderer is defensive: any missing top-level section becomes a placeholder slide
rather than crashing the API request.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Emu, Inches, Pt

from .charts import roi_chart


# Layout constants — 16:9 widescreen
SLIDE_W_EMU = 12192000  # 13.333 in
SLIDE_H_EMU = 6858000   # 7.5 in
DEFAULT_PRIMARY = "#0F172A"
DEFAULT_ACCENT = "#34D399"
TEXT_LIGHT = "#F8FAFC"
TEXT_MUTED = "#94A3B8"


def _hex_to_rgb(h: str) -> RGBColor:
    h = h.lstrip("#")
    if len(h) != 6:
        h = "0F172A"
    return RGBColor(int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _set_bg(slide, color_hex: str) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _hex_to_rgb(color_hex)


def _add_text_box(
    slide,
    text: str,
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    font_size: int = 18,
    bold: bool = False,
    color_hex: str = TEXT_LIGHT,
    align: str = "left",
) -> None:
    from pptx.enum.text import PP_ALIGN
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = {
        "left": PP_ALIGN.LEFT,
        "center": PP_ALIGN.CENTER,
        "right": PP_ALIGN.RIGHT,
    }.get(align, PP_ALIGN.LEFT)
    run = p.add_run()
    run.text = text or ""
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = _hex_to_rgb(color_hex)


def _add_bullets(
    slide,
    bullets: list[str],
    *,
    left: float,
    top: float,
    width: float,
    height: float,
    font_size: int = 16,
    color_hex: str = TEXT_LIGHT,
) -> None:
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    for i, b in enumerate(bullets or []):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        run = p.add_run()
        run.text = f"•  {b}"
        run.font.size = Pt(font_size)
        run.font.color.rgb = _hex_to_rgb(color_hex)


def _add_accent_bar(slide, color_hex: str) -> None:
    """Thin colored bar at the top of every content slide for brand cohesion."""
    bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, SLIDE_W_EMU, Emu(60000))
    bar.line.fill.background()
    bar.fill.solid()
    bar.fill.fore_color.rgb = _hex_to_rgb(color_hex)


def render_pptx(
    deck_json: dict[str, Any],
    brand: dict[str, Any] | None = None,
    *,
    lead_id: str | None = None,
    out_dir: Path | str = "/tmp/decks",
) -> Path:
    brand = brand or {}
    primary = brand.get("primary") or DEFAULT_PRIMARY
    accent = brand.get("accent") or DEFAULT_ACCENT

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"{lead_id or 'pitch'}.pptx"
    out_path = out_dir / fname

    pres = Presentation()
    pres.slide_width = SLIDE_W_EMU
    pres.slide_height = SLIDE_H_EMU
    blank = pres.slide_layouts[6]  # fully blank layout

    # ---- 1. Title ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    title = (deck_json.get("title") or {})
    _add_text_box(
        s,
        title.get("headline", "Solar Proposal"),
        left=0.7, top=2.4, width=12.0, height=1.4,
        font_size=44, bold=True, color_hex=TEXT_LIGHT,
    )
    _add_text_box(
        s,
        title.get("subhead", ""),
        left=0.7, top=3.9, width=12.0, height=0.8,
        font_size=20, color_hex=TEXT_MUTED,
    )
    _add_text_box(
        s,
        title.get("decision_maker", ""),
        left=0.7, top=4.7, width=12.0, height=0.6,
        font_size=16, color_hex=accent,
    )
    _add_text_box(
        s,
        brand.get("name", ""),
        left=0.7, top=6.6, width=12.0, height=0.4,
        font_size=12, color_hex=TEXT_MUTED,
    )

    # ---- 2. Problem ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    p = deck_json.get("problem") or {}
    _add_text_box(s, p.get("heading", "The problem"),
                  left=0.7, top=0.4, width=12.0, height=0.9,
                  font_size=32, bold=True)
    _add_bullets(s, p.get("bullets", []), left=0.9, top=1.6, width=11.5, height=5.0, font_size=20)

    # ---- 3. Solution ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    sol = deck_json.get("solution") or {}
    _add_text_box(s, sol.get("heading", "Solution"),
                  left=0.7, top=0.4, width=12.0, height=0.9,
                  font_size=32, bold=True)
    _add_bullets(s, sol.get("bullets", []), left=0.9, top=1.6, width=11.5, height=5.0, font_size=20)

    # ---- 4. Grid Independence (theme slide) ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    gi = deck_json.get("grid_independence") or {}
    _add_text_box(s, gi.get("heading", "Grid independence"),
                  left=0.7, top=0.4, width=12.0, height=0.9,
                  font_size=36, bold=True, color_hex=accent)
    _add_text_box(s, gi.get("body", ""),
                  left=0.9, top=1.8, width=11.5, height=2.5,
                  font_size=22)
    pct = gi.get("metric_pct_offset")
    if pct is not None:
        _add_text_box(s, f"{int(pct)}%",
                      left=0.9, top=4.5, width=4.0, height=1.6,
                      font_size=72, bold=True, color_hex=accent)
        _add_text_box(s, "of grid demand offset on-site",
                      left=0.9, top=6.0, width=8.0, height=0.6,
                      font_size=14, color_hex=TEXT_MUTED)

    # ---- 5. ROI (with embedded chart) ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    roi = deck_json.get("roi") or {}
    _add_text_box(s, roi.get("heading", "Return on investment"),
                  left=0.7, top=0.4, width=12.0, height=0.9,
                  font_size=32, bold=True)

    capex = float(roi.get("capex_gbp") or 0)
    saving = float(roi.get("annual_saving_gbp") or 0)
    payback = float(roi.get("payback_years") or 0)
    npv = float(roi.get("npv_25yr_gbp") or 0)

    _add_text_box(
        s,
        f"Capex: £{int(capex):,}    |    Annual saving: £{int(saving):,}    |    "
        f"Payback: {payback:.1f}y    |    25-yr NPV: £{int(npv):,}",
        left=0.7, top=1.4, width=12.5, height=0.6,
        font_size=14, color_hex=TEXT_MUTED,
    )

    # Render + embed chart
    try:
        chart_path = roi_chart(
            payback_years=payback,
            capex=capex,
            annual_saving=saving,
            npv_25yr=npv,
            out_dir=out_dir,
            lead_id=lead_id or "deck",
        )
        s.shapes.add_picture(str(chart_path), Inches(0.7), Inches(2.2), Inches(11.9), Inches(4.7))
    except Exception:
        # If matplotlib fails, leave a placeholder text box rather than break the deck.
        _add_text_box(s, "[ROI chart unavailable]",
                      left=0.7, top=2.2, width=11.9, height=4.7,
                      font_size=20, color_hex=TEXT_MUTED, align="center")

    # ---- 6. Funding ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    fnd = deck_json.get("funding") or {}
    _add_text_box(s, fnd.get("heading", "5 ways to fund it"),
                  left=0.7, top=0.4, width=12.0, height=0.9,
                  font_size=32, bold=True)
    models = fnd.get("models") or []
    for i, m in enumerate(models[:5]):
        col = i % 5
        x = 0.5 + col * 2.55
        # Card bg
        card = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE,
                                  Inches(x), Inches(2.0), Inches(2.4), Inches(3.6))
        card.fill.solid()
        card.fill.fore_color.rgb = _hex_to_rgb("#1E293B")
        card.line.color.rgb = _hex_to_rgb(accent)
        _add_text_box(s, m.get("name", ""),
                      left=x + 0.1, top=2.2, width=2.2, height=0.8,
                      font_size=14, bold=True, color_hex=accent)
        _add_text_box(s, m.get("fit", ""),
                      left=x + 0.1, top=3.0, width=2.2, height=2.4,
                      font_size=11, color_hex=TEXT_LIGHT)

    # ---- 7. Timeline ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    tl = deck_json.get("timeline") or {}
    _add_text_box(s, tl.get("heading", "Timeline"),
                  left=0.7, top=0.4, width=12.0, height=0.9,
                  font_size=32, bold=True)
    phases = tl.get("phases") or []
    if phases:
        n = len(phases)
        col_w = 12.0 / n
        for i, ph in enumerate(phases):
            x = 0.7 + i * col_w
            _add_text_box(s, ph.get("name", ""),
                          left=x, top=2.6, width=col_w, height=0.7,
                          font_size=16, bold=True, color_hex=accent)
            _add_text_box(s, f"{ph.get('weeks', '?')} weeks",
                          left=x, top=3.4, width=col_w, height=0.6,
                          font_size=14, color_hex=TEXT_MUTED)

    # ---- 8. Decision-maker callout ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    dmc = deck_json.get("decision_maker_callout") or {}
    _add_text_box(s, dmc.get("heading", "For you"),
                  left=0.7, top=0.4, width=12.0, height=0.9,
                  font_size=32, bold=True, color_hex=accent)
    _add_text_box(s, dmc.get("body", ""),
                  left=0.9, top=2.0, width=11.5, height=4.0,
                  font_size=22)

    # ---- 9. Social impact ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    si = deck_json.get("social_impact") or {}
    _add_text_box(s, si.get("heading", "Carbon offset"),
                  left=0.7, top=0.4, width=12.0, height=0.9,
                  font_size=32, bold=True)
    co2 = si.get("tonnes_co2_yr")
    trees = si.get("equiv_trees")
    if co2 is not None:
        _add_text_box(s, f"{co2}",
                      left=0.9, top=1.8, width=5.0, height=2.0,
                      font_size=72, bold=True, color_hex=accent)
        _add_text_box(s, "tonnes CO₂ avoided per year",
                      left=0.9, top=3.8, width=8.0, height=0.6,
                      font_size=16, color_hex=TEXT_MUTED)
    if trees is not None:
        _add_text_box(s, f"≈ {trees} trees planted, every year of operation",
                      left=0.9, top=4.8, width=11.0, height=0.6,
                      font_size=14, color_hex=TEXT_MUTED)

    # ---- 10. Tech specs ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    ts = deck_json.get("tech_specs") or {}
    _add_text_box(s, ts.get("heading", "Tech specs"),
                  left=0.7, top=0.4, width=12.0, height=0.9,
                  font_size=32, bold=True)
    rows = [
        ("Panels", ts.get("panels", "—")),
        ("Peak power (kWp)", ts.get("kw_peak", "—")),
        ("Annual generation (kWh)", ts.get("annual_kwh", "—")),
        ("Warranty (years)", ts.get("warranty_years", 25)),
    ]
    for i, (k, v) in enumerate(rows):
        _add_text_box(s, k, left=0.9, top=1.8 + i * 0.9, width=5.0, height=0.6,
                      font_size=18, color_hex=TEXT_MUTED)
        _add_text_box(s, str(v), left=6.0, top=1.8 + i * 0.9, width=5.0, height=0.6,
                      font_size=18, bold=True, color_hex=accent)

    # ---- 11. CTA ----
    s = pres.slides.add_slide(blank)
    _set_bg(s, primary)
    _add_accent_bar(s, accent)
    cta = deck_json.get("cta") or {}
    _add_text_box(s, cta.get("heading", "Next step"),
                  left=0.7, top=2.0, width=12.0, height=1.0,
                  font_size=44, bold=True, color_hex=accent, align="center")
    _add_text_box(s, cta.get("body", ""),
                  left=0.7, top=3.4, width=12.0, height=1.5,
                  font_size=22, align="center")
    _add_text_box(s, cta.get("contact", ""),
                  left=0.7, top=5.4, width=12.0, height=0.8,
                  font_size=18, color_hex=TEXT_MUTED, align="center")

    pres.save(str(out_path))
    return out_path
