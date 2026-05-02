"""Voice endpoints — ConvAI signed URL + one-shot AI voice pitch.

GET /voice/signed-url — provider-backed proxy for live ConvAI duplex.
POST /voice/pitch_audio — Sonnet 4.6 → ElevenLabs TTS → mp3 served from /static/swarm/tts.

Hard requirements (CONTRACTS § 7.8):
  - Verify AI disclosure exists in the voice agent system prompt before
    issuing a signed URL (live duplex only).
  - Hide the ElevenLabs API key from the browser.

Behaviour:
  - 404 only when the lead does not exist.
  - 200 in every other case. Failure modes are surfaced via `status`
    (`ok` | `demo_mode` | `disclosure_pending` | `upstream_error`) so the
    UI can render a graceful pill instead of an error toast.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Literal

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.config import Settings
from app.deps import get_app_settings, get_db
from app.services.audit import log_audit
from app.services.s3_storage import get_s3_storage
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

# TTS output dir is mounted by main.py at /static/swarm/tts. Mirror that path
# here — main.py creates it at startup but we mkdir defensively for unit tests
# that import the router without going through the lifespan.
TTS_OUT_DIR = Path("/tmp/swarm-tts")
TTS_OUT_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # ElevenLabs "Rachel" — matches swarm tool.

# Conservative: ElevenLabs charges per character. A ~250-word script lands
# around 1,500 chars → ~25¢ at standard tier. We surface this estimate to
# the cost-confirm modal; the audit row records the same figure.
TTS_PITCH_COST_CENTS = 25


def _ai_disclosure_ok() -> tuple[bool, str]:
    """Back-compat shim — delegates to the provider module."""
    return ai_disclosure_ok()


# ─── GET /voice/signed-url ────────────────────────────────────────────────────


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


# ─── POST /voice/pitch_audio ──────────────────────────────────────────────────


class PitchAudioRequest(BaseModel):
    lead_id: str = Field(..., description="lead id to pitch")
    client_id: str = Field(default="client-greensolar-uk")
    voice_id: str | None = Field(
        default=None,
        description="Override ElevenLabs voice id; defaults to Rachel.",
    )


PitchAudioStatus = Literal["ok", "demo_mode", "upstream_error"]


class PitchAudioResponse(BaseModel):
    audio_url: str | None
    # Presigned S3 URL (1h TTL) when AWS_* env is set and upload succeeded.
    # Frontend prefers this over `audio_url` because it's CDN-friendly and
    # not tied to the API host's filesystem.
    audio_s3_url: str | None = None
    script: str
    duration_sec: int
    cost_cents: int
    status: PitchAudioStatus
    message: str = ""


async def _synthesize_tts(
    *,
    text: str,
    voice_id: str,
    api_key: str,
    out_path: Path,
    timeout: float = 60.0,
) -> tuple[bool, str, int]:
    """Call ElevenLabs TTS HTTP API → write mp3 to ``out_path``.

    Returns ``(ok, error_or_empty, bytes_written)``. Never raises; all
    upstream failures degrade to ``ok=False`` so the route can surface them
    via the response status field instead of HTTP 5xx.
    """
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
    }
    body = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "output_format": "mp3_44100_128",
        "voice_settings": {"stability": 0.45, "similarity_boost": 0.75},
    }
    try:
        async with httpx.AsyncClient(timeout=timeout) as cx:
            resp = await cx.post(url, headers=headers, json=body)
    except httpx.HTTPError as e:
        return False, f"tts_unreachable:{type(e).__name__}", 0

    if resp.status_code != 200:
        snippet = resp.text[:200] if resp.text else ""
        return False, f"tts_http_{resp.status_code}:{snippet}", 0

    try:
        out_path.write_bytes(resp.content)
    except OSError as e:
        return False, f"tts_write_failed:{type(e).__name__}", 0
    return True, "", len(resp.content)


@router.post("/voice/pitch_audio", response_model=PitchAudioResponse)
async def voice_pitch_audio(
    body: PitchAudioRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> PitchAudioResponse:
    """Generate a Sonnet voice-pitch script and synthesize it via ElevenLabs TTS.

    Always returns 200 unless the lead is missing. Demo / upstream failures
    surface via ``status`` so the UI shows a pill, not an error toast — same
    contract as ``/voice/signed-url``.
    """
    lead = await db.leads.find_one({"_id": body.lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    client_doc = await db.clients.find_one({"_id": body.client_id}) or {}
    decision_maker = lead.get("decision_maker") or {
        "name": "Decision Maker",
        "role": "Director",
        "confidence": 0.5,
        "rationale": "default — call /build_org to refine",
    }

    # 1. Generate the script (Sonnet 4.6 + prompt cache, with deterministic fallback).
    script_text = ""
    script_cost_cents = 0
    duration_sec = 0
    rationale = ""
    try:
        from codex_brain.anthropic_client import AnthropicClient
        from codex_brain.generators.voice_pitch import generate_voice_pitch

        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY missing")

        ac = AnthropicClient(api_key=settings.anthropic_api_key)
        pitch = await generate_voice_pitch(
            lead, ac, decision_maker, client_doc=client_doc
        )
        script_text = pitch.script
        script_cost_cents = pitch.cost_cents
        duration_sec = pitch.est_seconds
        rationale = pitch.rationale
    except Exception as e:
        log.warning("voice_pitch script generation fell back: %s", e)
        from codex_brain.generators.voice_pitch import (
            _fallback_script,
            _seconds_from_words,
            _word_count,
        )

        script_text = _fallback_script(lead, decision_maker)
        duration_sec = _seconds_from_words(_word_count(script_text))

    # 2. Synthesize audio. No key → demo_mode (no audio_url, script still useful).
    api_key = (settings.elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY") or "").strip()
    voice_id = body.voice_id or DEFAULT_VOICE_ID

    if not api_key:
        await log_audit(
            db,
            action="voice.pitch_audio",
            lead_id=body.lead_id,
            cost_cents=script_cost_cents,
            metadata={
                "voice_id": voice_id,
                "status": "demo_mode",
                "reason": "elevenlabs_api_key_missing",
                "script_chars": len(script_text),
                "rationale": rationale,
            },
        )
        return PitchAudioResponse(
            audio_url=None,
            script=script_text,
            duration_sec=duration_sec,
            cost_cents=script_cost_cents,
            status="demo_mode",
            message=(
                "ElevenLabs API key not configured — script ready, audio "
                "synthesis skipped."
            ),
        )

    out_path = TTS_OUT_DIR / f"pitch_{body.lead_id}.mp3"
    ok, err, n_bytes = await _synthesize_tts(
        text=script_text,
        voice_id=voice_id,
        api_key=api_key,
        out_path=out_path,
    )

    total_cost_cents = script_cost_cents + (TTS_PITCH_COST_CENTS if ok else 0)

    if not ok:
        await log_audit(
            db,
            action="voice.pitch_audio",
            lead_id=body.lead_id,
            cost_cents=script_cost_cents,
            metadata={
                "voice_id": voice_id,
                "status": "upstream_error",
                "error": err,
                "script_chars": len(script_text),
                "rationale": rationale,
            },
        )
        return PitchAudioResponse(
            audio_url=None,
            script=script_text,
            duration_sec=duration_sec,
            cost_cents=script_cost_cents,
            status="upstream_error",
            message=f"ElevenLabs TTS failed: {err}",
        )

    audio_url = f"/static/swarm/tts/{out_path.name}"

    # Upload the mp3 to S3 alongside the local copy. ts in the key (rather
    # than fixed filename) lets us keep historical takes for debugging if
    # the operator wants — bucket lifecycle moves them to Glacier after 30d.
    audio_s3_url: str | None = None
    try:
        from datetime import datetime, timezone

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        s3 = get_s3_storage()
        mp3_bytes = out_path.read_bytes()
        s3_key = f"voice/{body.lead_id}/{ts}.mp3"
        res = await s3.put_object(
            s3_key,
            mp3_bytes,
            content_type="audio/mpeg",
            local_path=out_path,
        )
        if res.uploaded:
            audio_s3_url = res.url
    except Exception as e:  # noqa: BLE001 — never break the route on S3 failure
        log.warning("s3 voice upload failed (non-fatal): %s", e)

    await log_audit(
        db,
        action="voice.pitch_audio",
        lead_id=body.lead_id,
        cost_cents=total_cost_cents,
        metadata={
            "voice_id": voice_id,
            "status": "ok",
            "bytes": n_bytes,
            "script_chars": len(script_text),
            "duration_sec": duration_sec,
            "audio_url": audio_url,
            "audio_s3_url": audio_s3_url,
            "rationale": rationale,
        },
    )
    return PitchAudioResponse(
        audio_url=audio_url,
        audio_s3_url=audio_s3_url,
        script=script_text,
        duration_sec=duration_sec,
        cost_cents=total_cost_cents,
        status="ok",
        message="",
    )
