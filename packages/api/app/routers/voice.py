"""GET /voice/signed-url — proxy to ElevenLabs.

Hard requirements (CONTRACTS § 7.8):
  - Verify AI disclosure exists in the voice agent system prompt before
    issuing a signed URL.
  - Hide the ElevenLabs API key from the browser.
"""
from __future__ import annotations

import logging
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings
from app.deps import get_app_settings, get_db
from app.services.audit import log_audit

router = APIRouter()
log = logging.getLogger("solarreach.api.voice")

_PROMPT_PATH_CANDIDATES = [
    Path("packages/voice/voice_service/prompts/agent_system.md"),
    Path(__file__).resolve().parents[4] / "voice/voice_service/prompts/agent_system.md",
    Path(__file__).resolve().parents[3] / "packages/voice/voice_service/prompts/agent_system.md",
]


def _ai_disclosure_ok() -> tuple[bool, str]:
    for p in _PROMPT_PATH_CANDIDATES:
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="ignore").lower()
            if "ai" in text and "disclose" in text:
                return True, str(p)
            return False, f"prompt missing required disclosure: {p}"
    return False, "agent_system.md not found"


@router.get("/voice/signed-url")
async def voice_signed_url(
    lead_id: str = Query(..., description="lead id for context injection"),
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    if not settings.elevenlabs_api_key:
        raise HTTPException(
            status_code=503,
            detail="ELEVENLABS_API_KEY not configured on server.",
        )

    ok, reason = _ai_disclosure_ok()
    if not ok:
        log.warning("AI disclosure check failed: %s", reason)
        raise HTTPException(
            status_code=503,
            detail=f"AI disclosure missing — refusing to issue signed URL ({reason}).",
        )

    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    await log_audit(
        db,
        action="voice.session",
        lead_id=lead_id,
        cost_cents=0,
        metadata={"agent_id": settings.elevenlabs_agent_id},
    )

    if not settings.elevenlabs_agent_id:
        raise HTTPException(503, "ELEVENLABS_AGENT_ID not configured.")

    url = "https://api.elevenlabs.io/v1/convai/conversation/get_signed_url"
    params = {"agent_id": settings.elevenlabs_agent_id}
    headers = {"xi-api-key": settings.elevenlabs_api_key}
    async with httpx.AsyncClient(timeout=10.0) as cx:
        resp = await cx.get(url, params=params, headers=headers)
    if resp.status_code != 200:
        raise HTTPException(502, f"ElevenLabs error: {resp.status_code}")
    data = resp.json()

    company_name = (lead.get("owner") or {}).get("company_name", "")
    system_prompt_filled = (
        f"You are calling on behalf of SolarReach about {company_name} "
        f"at {lead.get('address', '')}. Disclose that you are an AI."
    )
    return {
        "signed_url": data.get("signed_url"),
        "agent_id": settings.elevenlabs_agent_id,
        "system_prompt_filled": system_prompt_filled,
    }
