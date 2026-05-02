"""Audit log writer for swarm tools.

Tries to reuse `app.services.audit.log_audit` if importable, else falls back
to an inline async writer that produces the same `audit_log` document shape
(see CONTRACTS § 1 `audit_log`).
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger("solarreach.swarm.audit")

try:
    # Reuse the canonical writer when running in the API process.
    from app.services.audit import log_audit as _log_audit_app  # type: ignore
except Exception:  # noqa: BLE001
    _log_audit_app = None


def _hash_email(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


async def _fallback_log_audit(
    db,
    *,
    action: str,
    lead_id: str | None = None,
    cost_cents: int = 0,
    metadata: dict[str, Any] | None = None,
    recipient_email: str | None = None,
    actor: str = "system",
) -> str:
    doc = {
        "_id": f"audit_{uuid.uuid4()}",
        "ts": datetime.now(timezone.utc).isoformat(),
        "actor": actor,
        "action": action,
        "lead_id": lead_id,
        "cost_cents": int(cost_cents),
        "recipient_sha256": _hash_email(recipient_email) if recipient_email else None,
        "metadata": metadata or {},
    }
    try:
        await db.audit_log.insert_one(doc)
    except Exception as e:  # noqa: BLE001 — audit must never break the call
        log.warning("audit_log fallback insert failed: %s", type(e).__name__)
    return doc["_id"]


async def write_audit(
    db,
    *,
    action: str,
    actor: str = "agent_swarm",
    lead_id: str | None = None,
    cost_cents: int = 0,
    metadata: dict[str, Any] | None = None,
    recipient_email: str | None = None,
) -> str | None:
    """Write an audit row. Never raises — returns None on failure."""
    if db is None:
        return None
    try:
        if _log_audit_app is not None:
            return await _log_audit_app(
                db,
                action=action,
                lead_id=lead_id,
                cost_cents=cost_cents,
                metadata=metadata,
                recipient_email=recipient_email,
                actor=actor,
            )
        return await _fallback_log_audit(
            db,
            action=action,
            lead_id=lead_id,
            cost_cents=cost_cents,
            metadata=metadata,
            recipient_email=recipient_email,
            actor=actor,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("audit write failed: %s", type(e).__name__)
        return None


def write_audit_sync(**kwargs) -> str | None:
    """Sync shim for LangChain `@tool` callables (which are sync)."""
    db = kwargs.pop("db", None)
    if db is None:
        return None
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an existing loop (CrewAI hierarchical worker).
            # Fire-and-forget the audit write so we don't block the tool call.
            loop.create_task(write_audit(db, **kwargs))
            return None
        return loop.run_until_complete(write_audit(db, **kwargs))
    except RuntimeError:
        # No event loop in this thread — make one.
        return asyncio.run(write_audit(db, **kwargs))


def get_actor_name() -> str:
    return os.getenv("SWARM_ACTOR", "agent_swarm")
