"""
SolarReach Codex Brain — Decision-maker inference
Uses Opus 4.7 for high-quality org chart reasoning.
Priority: CFO > Finance Director > MD > CEO > Head of Sustainability > COO > Property Director
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from codex_brain.anthropic_client import get_client, OPUS, UsageRecord

logger = logging.getLogger(__name__)


@dataclass
class DecisionMaker:
    name: str
    role: str
    confidence: float         # 0.0–1.0
    rationale: str
    seniority_tier: int       # 1=CFO level, 2=MD level, 3=other
    email: str | None = None
    linkedin_url: str | None = None


@dataclass
class OrgChartResult:
    primary: DecisionMaker
    secondary: DecisionMaker | None
    usage: UsageRecord


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM = """\
You are a B2B sales intelligence analyst. Given a list of company directors,
infer the single best decision-maker for a commercial solar capital expenditure purchase.

Priority order (highest first):
1. CFO / Chief Financial Officer / Finance Director
2. Managing Director / CEO
3. Head of Sustainability / ESG Director
4. COO / Chief Operating Officer
5. Property Director / Estates Manager
6. Any other director (lowest confidence)

Rules:
- Confidence < 0.70 if you must pick a generic "Director" with no clear function
- Return a secondary contact if a compelling #2 exists
- Name format from Companies House is "LASTNAME, Firstname" — reverse it before output

Output ONLY valid JSON — no markdown fences.
"""

_USER_TMPL = """\
Company: {company_name}
Companies House directors:
{directors_block}

Return:
{{
  "primary": {{
    "name": "...(Firstname Lastname)",
    "role": "...",
    "confidence": 0.0–1.0,
    "rationale": "...(one sentence)",
    "seniority_tier": 1–3
  }},
  "secondary": {{
    "name": "...",
    "role": "...",
    "confidence": 0.0–1.0,
    "rationale": "...",
    "seniority_tier": 1–3
  }} or null
}}
"""


def _format_directors(directors: list[dict]) -> str:
    lines = []
    for d in directors:
        name = _reverse_ch_name(d.get("name", "Unknown"))
        role = d.get("officer_role", "Director")
        resigned = d.get("resigned_on")
        status = " [resigned]" if resigned else ""
        lines.append(f"  - {name} ({role}){status}")
    return "\n".join(lines) if lines else "  (no directors found)"


def _reverse_ch_name(ch_name: str) -> str:
    """'PATEL, Sarah' → 'Sarah Patel'"""
    if "," in ch_name:
        last, first = ch_name.split(",", 1)
        return f"{first.strip().title()} {last.strip().title()}"
    return ch_name.title()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def infer_decision_maker(
    *,
    company_name: str,
    directors: list[dict],
) -> OrgChartResult:
    """
    Infer the best solar purchase decision-maker from a Companies House
    directors list.

    Args:
        company_name: The company name for context.
        directors: List of director dicts from Companies House API.

    Returns:
        OrgChartResult with primary (and optional secondary) DecisionMaker.
    """
    client = get_client()

    directors_block = _format_directors(directors)
    user = _USER_TMPL.format(
        company_name=company_name,
        directors_block=directors_block,
    )

    raw, usage = client.complete(
        system=_SYSTEM,
        user=user,
        model=OPUS,
        max_tokens=600,
        cache_system=True,
        call_type="org_chart",
    )

    data = json.loads(raw)

    def _parse_dm(d: dict | None) -> DecisionMaker | None:
        if not d:
            return None
        return DecisionMaker(
            name=d["name"],
            role=d["role"],
            confidence=float(d["confidence"]),
            rationale=d["rationale"],
            seniority_tier=int(d["seniority_tier"]),
        )

    primary = _parse_dm(data.get("primary"))
    if primary is None:
        raise ValueError(f"Opus returned no primary decision-maker for {company_name}")

    return OrgChartResult(
        primary=primary,
        secondary=_parse_dm(data.get("secondary")),
        usage=usage,
    )
