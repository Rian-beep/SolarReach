"""Tailored outreach generator — Sonnet 4.6, per-channel.

Wired:
  generate_tailored_outreach(lead, decision_maker, client_doc, channel)
    -> {"subject", "body", "channel", "cost_cents"}

Three channels:
  - email     → 180-word commercial cold email
  - linkedin  → 90-word connection-request body
  - intro_call → opener line + 3 talking-point bullets (≤ 100 words)

The system prompt is cached (5-min ephemeral); only the user payload + the
optional vendor-positioning tail bust cache, so repeated runs across channels
within a session hit the cache for the bulk of input tokens.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from solarreach_shared.industry_benchmarks import (
    AIA_CAP_GBP_MILLION,
    UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT,
    UK_SEG_EXPORT_RATE_GBP_PER_KWH,
    UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL,
)

from ..anthropic_client import AnthropicClient
from ..prompts import load_prompt


SONNET_MODEL = "claude-sonnet-4-6"

OutreachChannel = Literal["email", "linkedin", "intro_call"]
VALID_CHANNELS: tuple[OutreachChannel, ...] = ("email", "linkedin", "intro_call")


def _build_subject_expertise_block(client_doc: dict[str, Any] | None) -> str:
    """Mirror of email.py — append vendor positioning to the system prompt.

    Empty/missing fields are skipped. Returned block is appended to the cached
    system prompt; only the tail busts cache when admin updates positioning.
    """
    if not client_doc:
        return ""
    expertise = (client_doc.get("expertise_notes") or "").strip()
    product = (client_doc.get("product_description") or "").strip()
    features = client_doc.get("product_features") or []
    if not (expertise or product or features):
        return ""

    parts: list[str] = ["", "## Subject expertise"]
    parts.append(
        "You are writing on behalf of a vendor with the following positioning. "
        "Reflect this expertise concretely (one specific reference / fact), "
        "do NOT list it verbatim."
    )
    if product:
        parts.append(f"Product: {product}")
    if features:
        bullet_lines = "\n".join(
            f"- {f}" for f in features if isinstance(f, str) and f.strip()
        )
        if bullet_lines:
            parts.append("Key features:\n" + bullet_lines)
    if expertise:
        parts.append(f"Expertise notes: {expertise}")
    return "\n\n".join(parts)


def _benchmark_citation_pack() -> dict[str, Any]:
    """A small bundle of UK figures the model can cite. Kept narrow so the
    output stays grounded; broader stats live in the deck prompt.
    """
    return {
        "seg_export_rate_p_per_kwh": round(UK_SEG_EXPORT_RATE_GBP_PER_KWH * 100, 1),
        "aia_cap_gbp_million": AIA_CAP_GBP_MILLION,
        "commercial_price_rise_since_2019_pct": int(
            UK_COMMERCIAL_ELECTRICITY_PRICE_RISE_SINCE_2019_PCT * 100
        ),
        "uk_median_commercial_payback_years": UK_TYPICAL_PAYBACK_YEARS_COMMERCIAL,
        "full_expensing_available": True,
    }


def _fallback_message(
    lead: dict[str, Any],
    decision_maker: dict[str, Any],
    channel: OutreachChannel,
) -> dict[str, str]:
    """Deterministic fallback if Sonnet fails or returns malformed JSON.

    Mirrors channel-specific tone so the demo never blocks.
    """
    fin = lead.get("financial") or {}
    pl = lead.get("panel_layout") or {}
    name = (decision_maker.get("name") or "there").split()[0]
    company = (lead.get("owner") or {}).get("company_name") or "your company"
    addr = lead.get("address") or "your premises"
    panel_count = pl.get("panel_count") or "?"
    payback = fin.get("payback_years") or "?"
    npv = fin.get("npv_25yr_gbp") or "?"

    if channel == "linkedin":
        subject = f"{company} — solar on the {addr} roof"
        body = (
            f"Hi {name}, "
            f"we modelled a {panel_count}-panel array on the {addr} roof — "
            f"{payback}-year payback against current commercial import rates.\n\n"
            f"UK commercial electricity is up 78% since 2019 and SEG export "
            f"is paying 15p/kWh. Worth a brief connect to share the numbers?"
        )
        return {"subject": subject, "body": body}

    if channel == "intro_call":
        subject = f"Solar proposal — {company}"
        body = (
            f"Hi {name}, this is a 30-second intro on a solar proposal we "
            f"modelled for {addr}.\n\n"
            f"Talking point 1: {panel_count} panels on your roof — "
            f"{payback}-year payback at today's import rates.\n"
            f"Talking point 2: AIA covers the full capex against year-1 "
            f"corporation tax under the £1m cap.\n"
            f"Talking point 3: Open to a 20-minute call next week, "
            f"or I can email the deck first."
        )
        return {"subject": subject, "body": body}

    # default: email
    subject = f"{addr} — {payback}-year solar payback"
    body = (
        f"Hi {name},\n\n"
        f"Quick numbers on a solar PV proposal for {company} at {addr}: "
        f"{panel_count} panels, {payback}-year payback, "
        f"£{npv:,} NPV over 25 years.\n\n"
        f"UK commercial electricity is up 78% since 2019 and the SEG export "
        f"tariff currently pays 15p/kWh. With full expensing now permanent, "
        f"the year-one tax position is the strongest it's been since the "
        f"FiT era.\n\n"
        f"Worth a 20-minute call next week?"
    )
    return {"subject": subject, "body": body}


def _build_user_payload(
    lead: dict[str, Any],
    decision_maker: dict[str, Any],
    channel: OutreachChannel,
) -> str:
    fin = lead.get("financial") or {}
    pl = lead.get("panel_layout") or {}
    payload = {
        "channel": channel,
        "lead": {
            "_id": lead.get("_id"),
            "address": lead.get("address"),
            "premises_type": lead.get("premises_type"),
            "owner": {
                "company_name": (lead.get("owner") or {}).get("company_name"),
            },
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
        },
        "decision_maker": {
            "name": decision_maker.get("name"),
            "role": decision_maker.get("role"),
        },
        "uk_industry_benchmarks": _benchmark_citation_pack(),
        "instructions": (
            f"Generate ONE outreach message for channel='{channel}'. "
            "Follow the channel rules in the system prompt strictly. "
            "Return JSON only — no fences, no preamble."
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


async def generate_tailored_outreach(
    lead: dict[str, Any],
    decision_maker: dict[str, Any],
    client_doc: dict[str, Any] | None,
    channel: OutreachChannel,
    *,
    anthropic_client: AnthropicClient,
    model: str = SONNET_MODEL,
) -> dict[str, Any]:
    """Generate one channel-specific tailored outreach message.

    Returns:
        {"subject": str, "body": str, "channel": str, "cost_cents": float}

    Soft-fails to a deterministic fallback on any LLM error so the demo
    flow never blocks.
    """
    if channel not in VALID_CHANNELS:
        raise ValueError(
            f"unknown channel {channel!r}; must be one of {VALID_CHANNELS}"
        )

    system = load_prompt("outreach_system.md")
    expertise_block = _build_subject_expertise_block(client_doc)
    if expertise_block:
        system = system + expertise_block

    user_msg = _build_user_payload(lead, decision_maker, channel)

    # Channel-aware token budget — intro_call is the shortest, email the longest.
    max_tokens = {"email": 800, "linkedin": 500, "intro_call": 500}[channel]

    try:
        parsed, result = await anthropic_client.complete_json(
            messages=user_msg,
            system=system,
            max_tokens=max_tokens,
            temperature=0.55,
            cache_system=True,
            model=model,
        )
        if not (
            isinstance(parsed, dict)
            and isinstance(parsed.get("subject"), str)
            and isinstance(parsed.get("body"), str)
        ):
            fallback = _fallback_message(lead, decision_maker, channel)
            return {
                "subject": fallback["subject"],
                "body": fallback["body"],
                "channel": channel,
                "cost_cents": float(result.cost_cents),
            }
        return {
            "subject": parsed["subject"].strip(),
            "body": parsed["body"].strip(),
            "channel": channel,
            "cost_cents": float(result.cost_cents),
        }
    except Exception:
        fallback = _fallback_message(lead, decision_maker, channel)
        return {
            "subject": fallback["subject"],
            "body": fallback["body"],
            "channel": channel,
            "cost_cents": 0.0,
        }
