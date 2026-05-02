"""Voice pitch script generator — Sonnet 4.6.

Produces a TTS-ready spoken script (~250 words, 90s read time) keyed off the
lead's financial block. The output is fed verbatim into ElevenLabs TTS by
the API router; nothing here calls ElevenLabs directly so the generator
stays unit-testable without mocking the audio SDK.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from ..anthropic_client import AnthropicClient
from ..prompts import load_prompt


SONNET_MODEL = "claude-sonnet-4-6"

# TTS pacing target — used to estimate seconds when the model omits the field
# and to drive the visible "duration" pill in the UI.
WORDS_PER_MINUTE = 165


@dataclass
class VoicePitchResult:
    script: str
    est_seconds: int
    cost_cents: int
    rationale: str = ""


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text or ""))


def _seconds_from_words(words: int) -> int:
    if words <= 0:
        return 0
    return max(1, round(words / WORDS_PER_MINUTE * 60))


def _format_currency_for_tts(amount: int | float | None) -> str:
    """Render a GBP figure the way TTS reads it cleanly."""
    if amount is None:
        return "the projected saving"
    try:
        amt = int(round(float(amount)))
    except (TypeError, ValueError):
        return "the projected saving"
    return f"{amt:,} pounds"


def _fallback_script(lead: dict[str, Any], dm: dict[str, Any]) -> str:
    """Deterministic 90-second pitch used when the model is unavailable.

    Hits the same beats as the system prompt: building, payback, biggest
    tax break (AIA), bold close. Numbers come straight from the lead so the
    fallback is still bespoke per-prospect.
    """
    fin = lead.get("financial") or {}
    owner = (lead.get("owner") or {}).get("company_name") or "your business"
    address = lead.get("address") or "your premises"
    first_name = (dm.get("name") or "there").split()[0]
    role = dm.get("role") or "the team"
    payback = fin.get("payback_years")
    annual = fin.get("annual_saving_gbp")
    npv = fin.get("npv_25yr_gbp")

    payback_str = (
        f"a {payback}-year payback" if payback else "a competitive payback"
    )
    annual_str = (
        f"around {_format_currency_for_tts(annual)} a year"
        if annual
        else "a meaningful annual saving"
    )
    npv_str = (
        f"and a 25-year net present value of about {_format_currency_for_tts(npv)}"
        if npv
        else "with a strong long-term return"
    )

    return (
        f"Hello {first_name}, this is a quick proposal from SolarReach for "
        f"{owner} at {address}. UK commercial electricity is up 78 percent "
        f"since 2019, and the next contract renewal is the cliff most "
        f"finance teams are bracing for. Our survey of your roof models "
        f"{payback_str}, {annual_str}, {npv_str}.\n\n"
        f"For a {role} like yourself, the relevant lever is Capital "
        f"Allowances. Solar PV qualifies for the Annual Investment "
        f"Allowance, which gives you a 100 percent first-year deduction on "
        f"qualifying capex up to one million pounds. Full expensing for "
        f"new main-rate plant is also on the table. That turns the install "
        f"into a tax-efficient capital decision rather than an operating "
        f"cost.\n\n"
        f"I would like to walk you through the funding fit on a 30-minute "
        f"call this week. Reply to the email on its way, or pick a slot on "
        f"the calendar link, and we will lock the survey window for the "
        f"next available Tuesday."
    )


def _build_user_payload(
    lead: dict[str, Any],
    decision_maker: dict[str, Any],
    client_doc: dict[str, Any] | None,
) -> str:
    fin = lead.get("financial") or {}
    payload = {
        "lead": {
            "_id": lead.get("_id"),
            "address": lead.get("address"),
            "borough": lead.get("borough"),
            "premises_type": lead.get("premises_type"),
            "owner": lead.get("owner") or {},
            "financial": {
                "capex_gbp": fin.get("capex_gbp"),
                "annual_saving_gbp": fin.get("annual_saving_gbp"),
                "payback_years": fin.get("payback_years"),
                "npv_25yr_gbp": fin.get("npv_25yr_gbp"),
            },
        },
        "decision_maker": {
            "name": decision_maker.get("name"),
            "role": decision_maker.get("role"),
        },
        "client": {
            "name": (client_doc or {}).get("name"),
            "expertise_notes": (client_doc or {}).get("expertise_notes"),
        }
        if client_doc
        else None,
        "live_call": False,
        "instructions": (
            "Generate the JSON now. Plain prose only inside `script`. "
            "JSON only — no fences, no preamble."
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


async def generate_voice_pitch(
    lead: dict[str, Any],
    client: AnthropicClient,
    decision_maker: dict[str, Any],
    *,
    model: str = SONNET_MODEL,
    client_doc: dict[str, Any] | None = None,
) -> VoicePitchResult:
    """Generate a TTS-ready ~90-second pitch script for ``lead``.

    Falls back to a deterministic, lead-specific script on any error so the
    Voice tab always has audio to play.
    """
    system = load_prompt("voice_pitch_system.md")
    user = _build_user_payload(lead, decision_maker, client_doc)

    try:
        parsed, result = await client.complete_json(
            messages=user,
            system=system,
            max_tokens=900,
            temperature=0.55,
            cache_system=True,
            model=model,
        )
        if not isinstance(parsed, dict) or not parsed.get("script"):
            raise ValueError("model returned no script field")
        script = str(parsed["script"]).strip()
        rationale = str(parsed.get("rationale") or "").strip()
        try:
            est_seconds = int(parsed.get("est_seconds") or 0)
        except (TypeError, ValueError):
            est_seconds = 0
        if est_seconds <= 0:
            est_seconds = _seconds_from_words(_word_count(script))
        cost_cents = int(round(result.cost_cents))
        return VoicePitchResult(
            script=script,
            est_seconds=est_seconds,
            cost_cents=cost_cents,
            rationale=rationale,
        )
    except Exception:
        script = _fallback_script(lead, decision_maker)
        return VoicePitchResult(
            script=script,
            est_seconds=_seconds_from_words(_word_count(script)),
            cost_cents=0,
            rationale="fallback (model unavailable)",
        )


__all__ = [
    "VoicePitchResult",
    "generate_voice_pitch",
    "WORDS_PER_MINUTE",
]
