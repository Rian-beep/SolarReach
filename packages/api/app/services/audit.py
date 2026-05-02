"""Audit log writer.

Append-only `audit_log` collection. Recipient emails are sha256-hashed before
write — never store plaintext per CONTRACTS § 7 cardinal rule.
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


def hash_recipient(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


async def log_audit(
    db: AsyncIOMotorDatabase,
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
        "recipient_sha256": hash_recipient(recipient_email) if recipient_email else None,
        "metadata": metadata or {},
    }
    await db.audit_log.insert_one(doc)
    return doc["_id"]
