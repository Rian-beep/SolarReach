"""
SolarReach Codex Brain — Email A/B variant generator
Haiku 4.5 for fast rewrites; Sonnet 4.6 for fresh generation.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Literal

from codex_brain.anthropic_client import get_client, SONNET, HAIKU, UsageRecord

logger = logging.getLogger(__name__)

Theme = Literal["GRID INDEPENDENCE", "NET ZERO", "ROI FIRST"]


@dataclass
class EmailVariant:
    variant: Literal["A", "B"]
    subject: str
    body: str
    theme: str
    angle: str  # e.g. "cost certainty", "sustainability credentials"


@dataclass
class EmailResult:
    variant_a: EmailVariant
    variant_b: EmailVariant
    usage: UsageRecord


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

_GEN_SYSTEM = """\
You are a B2B email copywriter for SolarReach, a UK commercial solar sales platform.
Write concise, compelling outreach emails. No fluff, no buzzwords.
Theme: {theme}. Every email must have a clear single CTA.
Output ONLY valid JSON — no markdown fences.
"""

_REWRITE_SYSTEM = """\
You are optimising underperforming sales emails for SolarReach.
You receive a losing email variant and engagement data.
Rewrite it with a completely different angle while keeping the same factual claims.
Output ONLY valid JSON — no markdown fences.
"""

_GEN_USER = """\
Write two A/B email variants for this lead:

Company:        {company_name}
Decision-maker: {dm_name}, {dm_role}
Annual saving:  £{saving:,}/yr
Payback:        {payback} years
Postcode:       {postcode}
Sender:         {client_name}

Variant A: lead with the cost certainty / grid independence angle.
Variant B: lead with sustainability credentials / net zero angle.

Return:
{{
  "variant_a": {{
    "subject": "...",
    "body": "...(3-4 sentences)",
    "angle": "cost certainty"
  }},
  "variant_b": {{
    "subject": "...",
    "body": "...(3-4 sentences)",
    "angle": "sustainability credentials"
  }}
}}
"""

_REWRITE_USER = """\
Losing variant:
Subject: {subject}
Body:    {body}

Engagement: open_rate={open_rate:.0%}, click_rate={click_rate:.0%}
Winning variant angle: {winning_angle}

Rewrite the losing variant with a completely different angle.
Return:
{{
  "subject": "...",
  "body": "...(3-4 sentences)",
  "angle": "..."
}}
"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_email_variants(
    *,
    company_name: str,
    dm_name: str,
    dm_role: str,
    annual_saving_gbp: float,
    payback_years: float,
    postcode: str,
    client_name: str = "GreenSolar UK",
    theme: Theme = "GRID INDEPENDENCE",
) -> EmailResult:
    """Generate fresh A/B email variants via Sonnet 4.6."""
    client = get_client()
    system = _GEN_SYSTEM.format(theme=theme)
    user = _GEN_USER.format(
        company_name=company_name,
        dm_name=dm_name,
        dm_role=dm_role,
        saving=int(annual_saving_gbp),
        payback=payback_years,
        postcode=postcode,
        client_name=client_name,
    )

    raw, usage = client.complete(
        system=system,
        user=user,
        model=SONNET,
        max_tokens=800,
        cache_system=True,
        call_type="email_gen",
    )

    data = json.loads(raw)
    a = data["variant_a"]
    b = data["variant_b"]

    return EmailResult(
        variant_a=EmailVariant(
            variant="A",
            subject=a["subject"],
            body=a["body"],
            theme=theme,
            angle=a.get("angle", "cost certainty"),
        ),
        variant_b=EmailVariant(
            variant="B",
            subject=b["subject"],
            body=b["body"],
            theme=theme,
            angle=b.get("angle", "sustainability credentials"),
        ),
        usage=usage,
    )


def rewrite_losing_variant(
    *,
    losing: EmailVariant,
    winning_angle: str,
    open_rate: float,
    click_rate: float,
) -> tuple[EmailVariant, UsageRecord]:
    """
    Optimization loop: called by Atlas Trigger when SendGrid/Resend webhooks
    report that one variant has clearly lost. Uses Haiku for speed + cost.
    """
    client = get_client()
    user = _REWRITE_USER.format(
        subject=losing.subject,
        body=losing.body,
        open_rate=open_rate,
        click_rate=click_rate,
        winning_angle=winning_angle,
    )

    raw, usage = client.complete(
        system=_REWRITE_SYSTEM,
        user=user,
        model=HAIKU,
        max_tokens=400,
        cache_system=False,
        call_type="email_rewrite",
    )

    data = json.loads(raw)
    new_variant = EmailVariant(
        variant=losing.variant,
        subject=data["subject"],
        body=data["body"],
        theme=losing.theme,
        angle=data.get("angle", "rewritten"),
    )
    return new_variant, usage
