"""Pitch deck JSON-spec generator.

Wired:
  generate_deck(lead, client, decision_maker) -> DeckResult { deck_json, cost_cents, ... }

The result feeds straight into pptx_renderer.render_pptx(deck_json, brand).
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..anthropic_client import AnthropicClient, CompletionResult
from ..prompts import load_prompt


SONNET_MODEL = "claude-sonnet-4-6"


@dataclass
class DeckResult:
    deck_json: dict[str, Any]
    cost_cents: float
    in_tokens: int
    out_tokens: int
    cache_read_tokens: int
    cache_create_tokens: int
    raw_text: str


def _ensure_eleven_sections(deck: dict[str, Any]) -> dict[str, Any]:
    required = [
        "title", "problem", "solution", "grid_independence", "roi", "funding",
        "timeline", "decision_maker_callout", "social_impact", "tech_specs", "cta",
    ]
    for k in required:
        if k not in deck:
            deck[k] = {}
    return deck


def _build_user_payload(lead: dict[str, Any], decision_maker: dict[str, Any]) -> str:
    fin = lead.get("financial") or {}
    pl = lead.get("panel_layout") or {}
    payload = {
        "lead": {
            "_id": lead.get("_id"),
            "address": lead.get("address"),
            "borough": lead.get("borough"),
            "premises_type": lead.get("premises_type"),
            "owner": lead.get("owner") or {},
            "panel_layout": {
                "panel_count": pl.get("panel_count"),
                "annual_kwh": pl.get("annual_kwh"),
            },
            "financial": {
                "capex_gbp": fin.get("capex_gbp"),
                "annual_saving_gbp": fin.get("annual_saving_gbp"),
                "payback_years": fin.get("payback_years"),
                "npv_25yr_gbp": fin.get("npv_25yr_gbp"),
            },
            "scores": lead.get("scores") or {},
        },
        "decision_maker": {
            "name": decision_maker.get("name"),
            "role": decision_maker.get("role"),
            "confidence": decision_maker.get("confidence"),
        },
        "instructions": (
            "Generate the 11-section pitch deck JSON now. "
            "Copy financial figures verbatim from lead.financial. "
            "Tone: CFO-grade UK English. JSON only — no fences, no preamble."
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


async def generate_deck(
    lead: dict[str, Any],
    client: AnthropicClient,
    decision_maker: dict[str, Any],
    *,
    model: str = SONNET_MODEL,
    on_delta=None,
    max_tokens: int = 4096,
) -> DeckResult:
    """Run Sonnet 4.6 against the cached system prompt; return parsed deck JSON."""
    system = load_prompt("pitch_system.md")
    user_msg = _build_user_payload(lead, decision_maker)

    if on_delta is not None:
        # Streaming path for early UX (chunks shown as they arrive)
        result = await client.complete_streaming_collect(
            messages=user_msg,
            system=system,
            max_tokens=max_tokens,
            temperature=0.4,
            cache_system=True,
            model=model,
            on_delta=on_delta,
        )
        text = result.text
    else:
        result = await client.complete(
            messages=user_msg,
            system=system,
            max_tokens=max_tokens,
            temperature=0.4,
            cache_system=True,
            model=model,
        )
        text = result.text

    # Strip fences / preamble, parse JSON
    from ..anthropic_client import strip_json_fence
    cleaned = strip_json_fence(text)
    if cleaned and cleaned[0] != "{":
        # Skip preamble before the first {
        idx = cleaned.find("{")
        if idx > 0:
            cleaned = cleaned[idx:]
    try:
        deck_json = json.loads(cleaned)
    except json.JSONDecodeError:
        # Hardening: if Sonnet drifts, return a minimal-but-valid stub so the
        # downstream PPTX renderer doesn't crash the request.
        deck_json = {"title": {"headline": "Solar proposal"}}
    deck_json = _ensure_eleven_sections(deck_json)

    return DeckResult(
        deck_json=deck_json,
        cost_cents=result.cost_cents,
        in_tokens=result.in_tokens,
        out_tokens=result.out_tokens,
        cache_read_tokens=result.cache_read_tokens,
        cache_create_tokens=result.cache_create_tokens,
        raw_text=text,
    )


# ---------------------------------------------------------------------------
# Smoke runner: `python -m codex_brain.generators.deck`
# ---------------------------------------------------------------------------

STUB_LEAD = {
    "_id": "lead_smoke_001",
    "address": "1 Old Street, London EC1Y 8AF",
    "borough": "London Borough of Camden",
    "premises_type": "office",
    "owner": {"company_name": "Old Street Holdings Ltd", "source": "ccod"},
    "panel_layout": {"panel_count": 24, "annual_kwh": 10080},
    "financial": {
        "capex_gbp": 24500,
        "annual_saving_gbp": 3120,
        "payback_years": 7.8,
        "npv_25yr_gbp": 41200,
    },
    "scores": {"composite_score": 82, "solar_roi": 0.82},
}
STUB_DM = {"name": "Sarah Patel", "role": "CFO", "confidence": 0.92, "rationale": "x"}

# Stub deck used when ANTHROPIC_API_KEY is absent — exercises pptx + pdf path.
STUB_DECK_JSON: dict[str, Any] = {
    "title": {
        "headline": "Grid Independence — 1 Old St",
        "subhead": "Solar PV proposal for Old Street Holdings Ltd",
        "decision_maker": "Sarah Patel, CFO",
    },
    "problem": {
        "heading": "Volatile grid, predictable bill",
        "bullets": [
            "UK commercial electricity up 78% since 2019",
            "Wholesale market remains price-volatile",
            "Next contract renewal is the cliff",
        ],
    },
    "solution": {
        "heading": "Own your generation",
        "bullets": [
            "10,080 kWh on-site every year",
            "24 panels on existing roof",
            "30-year asset under your control",
        ],
    },
    "grid_independence": {
        "heading": "Grid independence",
        "body": "Your roof. Your generation. Your terms.",
        "metric_pct_offset": 42,
    },
    "roi": {
        "heading": "Return on investment",
        "capex_gbp": 24500,
        "annual_saving_gbp": 3120,
        "payback_years": 7.8,
        "npv_25yr_gbp": 41200,
    },
    "funding": {
        "heading": "5 ways to fund it",
        "models": [
            {"name": "Capital Expense", "fit": "Best NPV, full ownership"},
            {"name": "Free Install", "fit": "Zero capex, PPA model"},
            {"name": "Lease Purchase", "fit": "Cashflow + ownership"},
            {"name": "Operational Lease", "fit": "Off-balance-sheet"},
            {"name": "Hire Purchase", "fit": "VAT efficient, year-1 allowances"},
        ],
    },
    "timeline": {
        "heading": "Timeline to commissioning",
        "phases": [
            {"name": "Survey", "weeks": 2},
            {"name": "Design + DNO", "weeks": 6},
            {"name": "Install", "weeks": 4},
            {"name": "Commissioning", "weeks": 1},
        ],
    },
    "decision_maker_callout": {
        "heading": "For Sarah Patel, CFO",
        "body": (
            "This is a finance decision dressed as a roof decision. £24,500 capex "
            "delivers £41,200 NPV over 25 years and locks a unit cost the grid "
            "cannot match. Capital allowances, SEG income, and a 25-year warranty "
            "all sit on your balance sheet."
        ),
    },
    "social_impact": {"heading": "Carbon offset", "tonnes_co2_yr": 2.4, "equiv_trees": 110},
    "tech_specs": {"heading": "Tech", "panels": 24, "kw_peak": 9.6,
                   "annual_kwh": 10080, "warranty_years": 25},
    "cta": {
        "heading": "Next step",
        "body": "30-min call this week to walk through the funding fit.",
        "contact": "hello@greensolar.uk",
    },
}


async def _smoke():
    from .pptx_renderer import render_pptx
    out_dir = Path("/tmp/decks")
    out_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        client = AnthropicClient(api_key=api_key, model=SONNET_MODEL)
        result = await generate_deck(STUB_LEAD, client, STUB_DM)
        print(f"[deck] tokens in/out: {result.in_tokens}/{result.out_tokens}, "
              f"cache r/w: {result.cache_read_tokens}/{result.cache_create_tokens}, "
              f"cost: {result.cost_cents:.4f}¢")
        deck_json = result.deck_json
    else:
        print("[deck] ANTHROPIC_API_KEY absent — using stub deck JSON")
        deck_json = STUB_DECK_JSON

    brand = {"primary": "#0F172A", "accent": "#34D399", "name": "GreenSolar UK"}
    pptx_path = render_pptx(deck_json, brand, lead_id=STUB_LEAD["_id"], out_dir=out_dir)
    print(f"[deck] wrote PPTX -> {pptx_path}")
    return pptx_path


if __name__ == "__main__":
    asyncio.run(_smoke())
