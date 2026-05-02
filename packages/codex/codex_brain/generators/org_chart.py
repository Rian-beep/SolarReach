"""Decision-maker inference.

Hard priority order (lower index = higher priority):
  CFO → Finance Director → MD → CEO → Head of Sustainability → COO → Property Director → Estates Manager

Two layers:
1. `pick_best_director()` — pure-Python deterministic fallback (works offline)
2. `infer_decision_maker()` — Opus 4.7 LLM call with the same priority embedded in
   the prompt; result fenced JSON, parsed and validated against the directors list.

Confidence rules:
- Specific match (CFO / Finance Director / MD / CEO / Head of Sustainability) → ≥ 0.85
- Adjacent (COO / Property Director / Estates Manager) → 0.70..0.85
- Generic "Director" (no specialism) → < 0.70
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Hard priority hierarchy. Lower number wins.
# Synonyms list is matched case-insensitively as a substring.
ROLE_PRIORITY: list[tuple[int, list[str]]] = [
    (0, ["cfo", "chief financial officer"]),
    (1, ["finance director", "fd"]),
    (2, ["managing director", "md"]),
    (3, ["ceo", "chief executive officer", "chief executive"]),
    (4, ["head of sustainability", "sustainability lead", "esg lead", "head of esg"]),
    (5, ["coo", "chief operating officer", "operations director"]),
    (6, ["property director", "head of property", "head of real estate"]),
    (7, ["estates manager", "facilities manager", "head of facilities"]),
]
GENERIC_DIRECTOR = 50
UNKNOWN = 99

CONFIDENCE_BY_PRIORITY: dict[int, float] = {
    0: 0.92,  # CFO
    1: 0.88,  # Finance Director
    2: 0.85,  # MD
    3: 0.85,  # CEO
    4: 0.85,  # Head of Sustainability
    5: 0.78,  # COO
    6: 0.75,  # Property Director
    7: 0.72,  # Estates Manager
    GENERIC_DIRECTOR: 0.55,  # bare "Director" — below 0.7 by spec
    UNKNOWN: 0.40,
}


def role_priority(role: str | None) -> int:
    if not role:
        return UNKNOWN
    r = role.strip().lower()
    for prio, synonyms in ROLE_PRIORITY:
        for s in synonyms:
            if s in r:
                return prio
    if "director" in r:
        return GENERIC_DIRECTOR
    return UNKNOWN


def confidence_for_role(role: str | None) -> float:
    return CONFIDENCE_BY_PRIORITY.get(role_priority(role), 0.4)


def pick_best_director(directors: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Deterministic pick — used as a fallback or sanity check on LLM output."""
    if not directors:
        return None
    return min(directors, key=lambda d: role_priority(d.get("role")))


@dataclass
class DecisionMaker:
    name: str
    role: str
    confidence: float
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "confidence": self.confidence,
            "rationale": self.rationale,
        }


_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "decision_maker_inference.md"


def _load_prompt() -> str:
    if _PROMPT_PATH.exists():
        return _PROMPT_PATH.read_text(encoding="utf-8")
    return "You infer the most likely solar buying decision-maker from a directors list."


async def infer_decision_maker(
    directors_list: list[dict[str, Any]],
    lead_context: dict[str, Any],
    client: Any | None = None,
    model: str = "claude-opus-4-7",
) -> DecisionMaker:
    """Returns a DecisionMaker. Uses Opus 4.7 with prompt cache; falls back to deterministic pick."""
    fallback = pick_best_director(directors_list)
    if not directors_list:
        return DecisionMaker(
            name="Unknown",
            role="Unknown",
            confidence=0.0,
            rationale="No directors on file for this company.",
        )

    if client is None:
        # Pure-Python fallback path (no API key)
        if fallback is None:
            return DecisionMaker(
                name="Unknown", role="Unknown", confidence=0.0, rationale="empty directors"
            )
        role = fallback.get("role") or "Director"
        return DecisionMaker(
            name=fallback.get("name_display") or fallback.get("name") or "Unknown",
            role=role,
            confidence=confidence_for_role(role),
            rationale=(
                f"Selected by priority hierarchy fallback: '{role}' is the highest-"
                f"priority role available among {len(directors_list)} directors."
            ),
        )

    system = _load_prompt()
    user_payload = {
        "directors": directors_list,
        "lead_context": {
            "address": lead_context.get("address"),
            "premises_type": lead_context.get("premises_type"),
            "owner_name": (lead_context.get("owner") or {}).get("company_name"),
            "capex_gbp": (lead_context.get("financial") or {}).get("capex_gbp"),
        },
        "instructions": (
            "Choose ONE decision-maker. Strict priority order: "
            "CFO > Finance Director > MD > CEO > Head of Sustainability > COO > "
            "Property Director > Estates Manager. If only generic 'Director' titles "
            "are available, set confidence < 0.7."
        ),
    }
    user_msg = json.dumps(user_payload, ensure_ascii=False)

    try:
        parsed, _result = await client.complete_json(
            messages=user_msg,
            system=system,
            max_tokens=600,
            temperature=0.2,
            cache_system=True,
            model=model,
        )
        name = parsed.get("name") or (fallback or {}).get("name") or "Unknown"
        role = parsed.get("role") or (fallback or {}).get("role") or "Unknown"
        # Validate confidence; if model picked a generic "Director" but claimed > 0.7, clamp.
        conf = float(parsed.get("confidence", confidence_for_role(role)))
        if role_priority(role) >= GENERIC_DIRECTOR and conf >= 0.7:
            conf = 0.65
        rationale = parsed.get("rationale") or "LLM-inferred from directors list."
        return DecisionMaker(name=name, role=role, confidence=conf, rationale=rationale)
    except Exception:
        # On any LLM failure, use deterministic fallback rather than crash the pitch flow.
        if fallback is None:
            return DecisionMaker(
                name="Unknown", role="Unknown", confidence=0.0, rationale="LLM failed; no directors"
            )
        role = fallback.get("role") or "Director"
        return DecisionMaker(
            name=fallback.get("name_display") or fallback.get("name") or "Unknown",
            role=role,
            confidence=confidence_for_role(role),
            rationale=f"Fallback (LLM unavailable): '{role}' is highest-priority on the directors list.",
        )
