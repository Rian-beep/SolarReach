"""Email A/B variant generator — Sonnet 4.6.

Reads optional ``client_doc`` from the admin centre to splice subject-expertise
notes + product description into the system prompt. This makes the outreach
sound like a domain-specialist account exec, not a generic SDR.
"""

from __future__ import annotations

import json
from typing import Any

from ..anthropic_client import AnthropicClient
from ..prompts import load_prompt


SONNET_MODEL = "claude-sonnet-4-6"


def _fallback_variants(lead: dict[str, Any], dm: dict[str, Any]) -> dict[str, dict[str, str]]:
    fin = lead.get("financial") or {}
    name = (dm.get("name") or "there").split()[0]
    addr = lead.get("address") or "your premises"
    payback = fin.get("payback_years") or "?"
    npv = fin.get("npv_25yr_gbp") or "?"
    a_body = (
        f"Hi {name},\n\n"
        f"Quick numbers on a solar PV proposal for {addr}: "
        f"{payback}-year payback, £{npv:,} NPV over 25 years.\n\n"
        f"Worth a 30-minute call?"
    )
    b_body = (
        f"Hi {name},\n\n"
        f"UK commercial electricity is up 78% since 2019. The roof at {addr} can offset "
        f"a significant share of that bill at a fixed marginal cost.\n\n"
        f"Open to a short conversation?"
    )
    return {
        "a": {"subject": f"{addr}: {payback}-year payback", "body": a_body},
        "b": {"subject": "The bill is not coming down", "body": b_body},
    }


def _build_subject_expertise_block(client_doc: dict[str, Any] | None) -> str:
    """Return a markdown block to append to the email system prompt, or "".

    Reads ``expertise_notes`` and ``product_description`` from the admin
    centre's clients doc. Empty/missing fields are skipped silently.
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
        bullet_lines = "\n".join(f"- {f}" for f in features if isinstance(f, str) and f.strip())
        if bullet_lines:
            parts.append("Key features:\n" + bullet_lines)
    if expertise:
        parts.append(f"Expertise notes: {expertise}")
    return "\n\n".join(parts)


async def generate_email_variants(
    lead: dict[str, Any],
    decision_maker: dict[str, Any],
    client: AnthropicClient,
    *,
    model: str = SONNET_MODEL,
    client_doc: dict[str, Any] | None = None,
) -> dict[str, dict[str, str]]:
    """Generate two email variants for ``lead`` addressed to ``decision_maker``.

    If ``client_doc`` (the admin centre's ``clients`` doc) is provided, its
    ``expertise_notes`` + ``product_description`` are spliced into the
    system prompt. We pass it in via the call site so the cache hits on
    the base prompt and only the expertise tail busts cache when admin
    changes (rare).
    """
    system = load_prompt("email_system.md")
    expertise_block = _build_subject_expertise_block(client_doc)
    if expertise_block:
        system = system + expertise_block
    fin = lead.get("financial") or {}
    payload = {
        "lead": {
            "_id": lead.get("_id"),
            "address": lead.get("address"),
            "owner": lead.get("owner") or {},
            "premises_type": lead.get("premises_type"),
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
        "instructions": "Generate the two-variant JSON now. JSON only.",
    }
    user = json.dumps(payload, ensure_ascii=False)
    try:
        parsed, _result = await client.complete_json(
            messages=user,
            system=system,
            max_tokens=1500,
            temperature=0.6,
            cache_system=True,
            model=model,
        )
        # Validate structure
        if not (isinstance(parsed, dict) and "a" in parsed and "b" in parsed):
            return _fallback_variants(lead, decision_maker)
        return parsed
    except Exception:
        return _fallback_variants(lead, decision_maker)
