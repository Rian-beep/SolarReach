"""GET /voice/signed-url — provider-backed proxy.

Hard requirements (CONTRACTS § 7.8):
  - Verify AI disclosure exists in the voice agent system prompt before
    issuing a signed URL.
  - Hide the ElevenLabs API key from the browser.

Behaviour:
  - 404 only when the lead does not exist.
  - 200 in every other case. Failure modes are surfaced via `status`
    (`ok` | `demo_mode` | `disclosure_pending` | `upstream_error`) so the
    UI can render a graceful pill instead of an error toast. This keeps
    the rehearsal button responsive while Rian's voice service is still
    being merged in.
"""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings
from app.deps import get_app_settings, get_db
from app.services.audit import log_audit
from app.services.voice_provider import (
    SignedUrlResult,
    ai_disclosure_ok,
    get_provider,
)

router = APIRouter()
log = logging.getLogger("solarreach.api.voice")

# Re-exported for back-compat with any consumer that imported the underscore
# helper from this module before the refactor (notably the unit test).
_PROMPT_PATH_CANDIDATES: list[Path] = [
    # Kept as a public-ish constant so tests / debugging still find it.
]


def _ai_disclosure_ok() -> tuple[bool, str]:
    """Back-compat shim — delegates to the provider module."""
    return ai_disclosure_ok()


@router.get("/voice/signed-url")
async def voice_signed_url(
    lead_id: str = Query(..., description="lead id for context injection"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    provider = get_provider()
    try:
        result: SignedUrlResult = await provider.get_signed_url(
            lead=lead,
            settings=settings,
        )
    except Exception as e:  # noqa: BLE001 — provider must never crash the route
        log.exception("voice provider %s raised: %s", provider.name, e)
        result = SignedUrlResult(
            signed_url=None,
            agent_id=None,
            system_prompt_filled="",
            status="upstream_error",
            message=f"voice provider error: {type(e).__name__}",
        )

    await log_audit(
        db,
        action="voice.session",
        lead_id=lead_id,
        cost_cents=0,
        metadata={
            "provider": provider.name,
            "status": result.status,
            "agent_id": result.agent_id,
        },
    )

    return {
        "signed_url": result.signed_url,
        "agent_id": result.agent_id,
        "system_prompt_filled": result.system_prompt_filled,
        "status": result.status,
        "message": result.message,
        "provider": provider.name,
    }
