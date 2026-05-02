"""Compliance helpers — recipient hashing, outbound gating."""

from __future__ import annotations

import hashlib
import os


def hash_recipient(email: str) -> str:
    """SHA-256 hex digest of a normalised recipient email.

    Used for `audit_log.recipient_sha256` per cardinal rule 7.
    Normalisation: strip + lowercase. Empty/whitespace-only inputs hash deterministically too.
    """
    normalised = (email or "").strip().lower()
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


def is_live_outbound() -> bool:
    """Returns True iff env var `SOLARREACH_LIVE_OUTBOUND` is truthy.

    Default (unset/false): we are in safe-mode — no real emails / no real voice calls
    leave the box. Anything paid or with PII implications must check this gate first.
    """
    val = os.environ.get("SOLARREACH_LIVE_OUTBOUND", "").strip().lower()
    return val in {"1", "true", "yes", "on"}
