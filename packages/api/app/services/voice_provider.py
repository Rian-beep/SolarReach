"""Voice provider abstraction.

The voice tab in the UI calls `GET /voice/signed-url`. That endpoint historically
spoke to ElevenLabs ConvAI directly. As the integration with Rian's secondary
project (`Rian-beep/solarreach-project1`) lands, we need a swap-in point so the
router doesn't have to change shape.

Selection is driven by the `VOICE_PROVIDER` env var:

    VOICE_PROVIDER=elevenlabs   # default — current ConvAI flow
    VOICE_PROVIDER=rian         # Rian's lib (stub until his branch lands)

The router calls `get_provider().get_signed_url(lead_id, ...)` and renders
whatever `SignedUrlResult` it gets back. All upstream errors are caught here
and surfaced as a structured result — never as 502/503 — so the UI can render
a graceful "demo mode" state instead of an error toast.

See `docs/VOICE-INTEGRATION.md` for the merge-handshake checklist.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx

from app.config import Settings

log = logging.getLogger("solarreach.api.voice.provider")

VoiceStatus = Literal["ok", "demo_mode", "disclosure_pending", "upstream_error"]


@dataclass
class SignedUrlResult:
    """What every provider returns to the router.

    `signed_url` is None for any non-ok status. `status` drives UI state.
    `message` is a human-readable hint surfaced in the demo-mode pill.
    """

    signed_url: str | None
    agent_id: str | None
    system_prompt_filled: str
    status: VoiceStatus
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)


class VoiceProvider(Protocol):
    """Interface implemented by ElevenLabs + Rian's voice service."""

    name: str

    async def get_signed_url(
        self,
        *,
        lead: dict[str, Any],
        settings: Settings,
    ) -> SignedUrlResult: ...


# ─── Helpers ──────────────────────────────────────────────────────────────────

# Candidate locations for the AI-disclosure system prompt. Kept in sync with the
# original router logic so behaviour doesn't shift during the refactor.
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PROMPT_PATH_CANDIDATES = [
    _REPO_ROOT / "agent_system.md",
    _REPO_ROOT / "packages/voice/voice_service/prompts/agent_system.md",
    Path("agent_system.md"),
    Path("packages/voice/voice_service/prompts/agent_system.md"),
]


def ai_disclosure_ok() -> tuple[bool, str]:
    for p in _PROMPT_PATH_CANDIDATES:
        if p.exists():
            text = p.read_text(encoding="utf-8", errors="ignore").lower()
            if "ai" in text and "disclose" in text:
                return True, str(p)
            return False, f"prompt missing required disclosure: {p}"
    return False, "agent_system.md not found"


def _system_prompt_for(lead: dict[str, Any]) -> str:
    company_name = (lead.get("owner") or {}).get("company_name", "")
    return (
        f"You are calling on behalf of SolarReach about {company_name} "
        f"at {lead.get('address', '')}. Disclose that you are an AI."
    )


# ─── ElevenLabs ───────────────────────────────────────────────────────────────


class ElevenLabsProvider:
    """Existing flow — proxy to ElevenLabs ConvAI.

    Errors degrade to `demo_mode` rather than HTTP 5xx.
    """

    name = "elevenlabs"

    async def get_signed_url(
        self,
        *,
        lead: dict[str, Any],
        settings: Settings,
    ) -> SignedUrlResult:
        prompt = _system_prompt_for(lead)

        if not settings.elevenlabs_api_key:
            return SignedUrlResult(
                signed_url=None,
                agent_id=settings.elevenlabs_agent_id or None,
                system_prompt_filled=prompt,
                status="demo_mode",
                message=(
                    "ElevenLabs API key not configured — rotate the key into "
                    ".env.local to enable live voice."
                ),
            )

        if not settings.elevenlabs_agent_id:
            return SignedUrlResult(
                signed_url=None,
                agent_id=None,
                system_prompt_filled=prompt,
                status="demo_mode",
                message="ELEVENLABS_AGENT_ID not configured.",
            )

        ok, reason = ai_disclosure_ok()
        if not ok:
            log.warning("AI disclosure check failed: %s", reason)
            return SignedUrlResult(
                signed_url=None,
                agent_id=settings.elevenlabs_agent_id,
                system_prompt_filled=prompt,
                status="disclosure_pending",
                message=f"AI disclosure missing: {reason}",
            )

        url = "https://api.elevenlabs.io/v1/convai/conversation/get_signed_url"
        params = {"agent_id": settings.elevenlabs_agent_id}
        headers = {"xi-api-key": settings.elevenlabs_api_key}
        try:
            async with httpx.AsyncClient(timeout=10.0) as cx:
                resp = await cx.get(url, params=params, headers=headers)
        except httpx.HTTPError as e:
            log.warning("ElevenLabs request failed: %s", e)
            return SignedUrlResult(
                signed_url=None,
                agent_id=settings.elevenlabs_agent_id,
                system_prompt_filled=prompt,
                status="upstream_error",
                message=f"ElevenLabs unreachable: {type(e).__name__}",
            )

        if resp.status_code != 200:
            log.warning(
                "ElevenLabs non-200: %s body=%s",
                resp.status_code,
                resp.text[:200],
            )
            return SignedUrlResult(
                signed_url=None,
                agent_id=settings.elevenlabs_agent_id,
                system_prompt_filled=prompt,
                status="upstream_error",
                message=f"ElevenLabs error {resp.status_code}",
            )

        data = resp.json()
        return SignedUrlResult(
            signed_url=data.get("signed_url"),
            agent_id=settings.elevenlabs_agent_id,
            system_prompt_filled=prompt,
            status="ok",
            message="",
        )


# ─── Rian's voice service (stub) ──────────────────────────────────────────────


class RianProjectVoiceProvider:
    """Stub for Rian's voice service.

    Until Rian's voice lib lands at the agreed path, this provider always
    returns `demo_mode`. The MERGE HANDSHAKE in `docs/VOICE-INTEGRATION.md`
    walks through swapping the stub for the real thing — typically a 5-line
    diff inside `get_signed_url` once `from solarreach_voice import client`
    (or the agreed-upon import path) is available.
    """

    name = "rian"

    async def get_signed_url(
        self,
        *,
        lead: dict[str, Any],
        settings: Settings,
    ) -> SignedUrlResult:
        prompt = _system_prompt_for(lead)
        # Probe for Rian's lib — keep this guarded so we never hard-import a
        # module that doesn't exist yet. When Rian merges, this `try` block is
        # the only thing we need to swap.
        try:
            # NOTE: replace this import + call when Rian's lib lands.
            # Example expected interface (subject to change before merge):
            #   from solarreach_voice import VoiceClient
            #   client = VoiceClient.from_env()
            #   url = await client.signed_url(lead_id=lead["_id"])
            raise ImportError("solarreach_voice not yet on PYTHONPATH")
        except ImportError as e:
            log.info("Rian voice provider stub: %s", e)
            return SignedUrlResult(
                signed_url=None,
                agent_id=None,
                system_prompt_filled=prompt,
                status="demo_mode",
                message=(
                    "Voice integration pending — pulling from teammate's branch."
                ),
                metadata={"provider": "rian", "stub": True},
            )


# ─── Selector ─────────────────────────────────────────────────────────────────


_PROVIDER_REGISTRY: dict[str, type[VoiceProvider]] = {
    "elevenlabs": ElevenLabsProvider,
    "rian": RianProjectVoiceProvider,
}


def get_provider(name: str | None = None) -> VoiceProvider:
    """Resolve the active provider.

    Order of precedence:
      1. Explicit `name` argument (used in tests).
      2. `VOICE_PROVIDER` env var.
      3. Default: `elevenlabs`.
    """
    chosen = (name or os.environ.get("VOICE_PROVIDER") or "elevenlabs").lower()
    cls = _PROVIDER_REGISTRY.get(chosen)
    if cls is None:
        log.warning("Unknown VOICE_PROVIDER=%r — falling back to elevenlabs", chosen)
        cls = ElevenLabsProvider
    return cls()


__all__ = [
    "SignedUrlResult",
    "VoiceProvider",
    "VoiceStatus",
    "ElevenLabsProvider",
    "RianProjectVoiceProvider",
    "ai_disclosure_ok",
    "get_provider",
]
