"""Compliance gate for outbound side-effects.

When `SOLARREACH_LIVE_OUTBOUND` is false (default), every email/voice send is
diverted to a dated `.eml` (or `.json`) file under `outbox/`. The sender
function returns a structured dict so callers can audit the redirect.

Cardinal rule (CONTRACTS § 7.4): never auto-fire paid APIs without the
spend tracker visible + user-initiated click. The gate is the technical
backstop for that rule.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from app.config import get_settings


def _live_outbound() -> bool:
    # Honour live env var, since tests monkeypatch the environment after
    # Settings has cached. Fall back to the cached settings otherwise.
    raw = os.environ.get("SOLARREACH_LIVE_OUTBOUND")
    if raw is not None:
        return raw.lower() in ("1", "true", "yes", "on")
    return get_settings().solarreach_live_outbound


def _outbox_dir() -> Path:
    p = Path(os.environ.get("SOLARREACH_OUTBOX_DIR", "outbox"))
    p.mkdir(parents=True, exist_ok=True)
    return p


async def send_outbound_email(
    *,
    to: str,
    subject: str,
    body: str,
    sender: str = "no-reply@solarreach.local",
) -> dict[str, Any]:
    """Send (or divert) an outbound email.

    Returns dict with keys: status ("outbox"|"sent"), path|provider_id.
    """
    if _live_outbound():  # pragma: no cover — no real provider in dev
        # TODO(A4): wire SES/SendGrid here.
        return {"status": "sent", "provider_id": "stub-live-provider"}

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = _outbox_dir() / f"{ts}.eml"
    path.write_bytes(bytes(msg))
    return {"status": "outbox", "path": str(path)}


async def divert_voice_session(payload: dict[str, Any]) -> dict[str, Any]:
    """Mirror for voice — drops a JSON record under outbox/ when disabled."""
    if _live_outbound():  # pragma: no cover
        return {"status": "live"}
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = _outbox_dir() / f"voice-{ts}.json"
    path.write_text(json.dumps(payload, indent=2))
    return {"status": "outbox", "path": str(path)}
