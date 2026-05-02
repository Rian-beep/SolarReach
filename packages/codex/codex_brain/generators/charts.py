"""Matplotlib ROI cumulative cash-flow chart.

Embedded on slide 5 of every pitch deck. Dark theme matches deck aesthetic.
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")  # headless — no display needed in Docker / Celery
import matplotlib.pyplot as plt  # noqa: E402


# Dark theme colors — deck-matched. Hex picked to match THEME-NARRATIVE solar palette.
DECK_BG = "#0F172A"   # deep navy (matches default client.branding.primary)
PANEL_BG = "#1E293B"
GRID = "#334155"
LINE_NEG = "#F472B6"  # magenta for losses
LINE_POS = "#34D399"  # emerald green for gains
PAYBACK_MARK = "#FCD34D"  # amber for payback marker
TEXT = "#F8FAFC"


def roi_chart(
    payback_years: float,
    capex: float,
    annual_saving: float,
    npv_25yr: float,
    out_dir: Path | str = Path("/tmp/decks"),
    lead_id: str | None = None,
    horizon_years: int = 25,
    panel_degradation_pct_yr: float = 0.5,
) -> Path:
    """Render a 25-year cumulative cash-flow chart.

    X axis: years 0..25
    Y axis: cumulative GBP (start at -capex, climb by annual_saving with mild degradation)
    Markers: payback crossing (year_payback, 0)
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname = f"roi_{lead_id or uuid.uuid4().hex[:8]}.png"
    out = out_dir / fname

    years = list(range(0, horizon_years + 1))
    cumulative: list[float] = []
    running = -float(capex)
    cumulative.append(running)
    for y in range(1, horizon_years + 1):
        # Mild panel degradation
        deg = (1 - panel_degradation_pct_yr / 100.0) ** (y - 1)
        running += float(annual_saving) * deg
        cumulative.append(running)

    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    fig.patch.set_facecolor(DECK_BG)
    ax.set_facecolor(PANEL_BG)

    # Split into negative (pre-payback) and positive segments for color emphasis
    neg_x = [y for y, c in zip(years, cumulative) if c < 0]
    neg_y = [c for c in cumulative if c < 0]
    pos_x = [y for y, c in zip(years, cumulative) if c >= 0]
    pos_y = [c for c in cumulative if c >= 0]

    if neg_x:
        ax.plot(neg_x, neg_y, color=LINE_NEG, linewidth=2.5, label="Pre-payback")
    if pos_x:
        ax.plot(pos_x, pos_y, color=LINE_POS, linewidth=2.5, label="Net gain")

    # Payback marker
    if 0 < payback_years < horizon_years:
        ax.axvline(payback_years, color=PAYBACK_MARK, linestyle="--", alpha=0.7)
        ax.scatter([payback_years], [0], color=PAYBACK_MARK, s=80, zorder=5)
        ax.annotate(
            f"Payback {payback_years:.1f}y",
            xy=(payback_years, 0),
            xytext=(payback_years + 0.5, max(cumulative) * 0.1 if max(cumulative) > 0 else 1000),
            color=PAYBACK_MARK,
            fontsize=10,
            fontweight="bold",
        )

    # NPV annotation
    ax.annotate(
        f"25-yr NPV: £{int(npv_25yr):,}",
        xy=(horizon_years, cumulative[-1]),
        xytext=(horizon_years - 7, cumulative[-1] * 0.85 if cumulative[-1] > 0 else cumulative[-1] * 1.15),
        color=TEXT,
        fontsize=11,
        fontweight="bold",
    )

    # Zero line
    ax.axhline(0, color=GRID, linewidth=0.8, alpha=0.6)

    ax.set_xlabel("Years", color=TEXT, fontsize=11)
    ax.set_ylabel("Cumulative cash flow (£)", color=TEXT, fontsize=11)
    ax.set_title(
        "Solar investment — 25-year cumulative cash flow",
        color=TEXT,
        fontsize=13,
        fontweight="bold",
        pad=12,
    )
    ax.tick_params(colors=TEXT)
    for spine in ax.spines.values():
        spine.set_color(GRID)
    ax.grid(color=GRID, alpha=0.4, linewidth=0.5)
    ax.legend(facecolor=PANEL_BG, edgecolor=GRID, labelcolor=TEXT, loc="lower right")

    fig.tight_layout()
    fig.savefig(out, facecolor=DECK_BG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return out
