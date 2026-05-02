"""Inbound integration endpoint for Rian's agentic stack.

Surface
-------
``POST /integration/agent_event``
    Rian's agents push trace events here. Each event lands in the
    ``agent_events`` Atlas collection and is mirrored to ``audit_log`` so the
    spend/observability dashboard sees the cross-system traffic.

Auth
----
Token-based. ``RIAN_INTEGRATION_TOKEN`` env var holds the shared secret. The
caller sends it via ``Authorization: Bearer <token>``. If the env var is unset
we run in **dev-open** mode (logged-only) so local development still works
without coordinating secrets — every event is tagged ``auth_status="dev_open"``
in audit metadata for traceability.

The collection ``agent_events`` is created lazily with a ``$jsonSchema``
validator so the contract is enforced server-side. The validator is best-effort
on test backends (mongomock) — failures to install it are logged and ignored,
matching the pattern in ``services/project1_link.py``.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

from app.deps import get_db
from app.services.audit import log_audit

router = APIRouter()
log = logging.getLogger("solarreach.api.integration")

AGENT_EVENTS_COLLECTION = "agent_events"

_agent_events_ready = False


async def _ensure_agent_events_collection(db: AsyncIOMotorDatabase) -> None:
    """Create ``agent_events`` with a ``$jsonSchema`` validator if missing.

    Idempotent. Process-cached so we only pay one ``listCollections`` round-trip
    per worker. Mirrors the pattern in ``services/project1_link.py``.
    """
    global _agent_events_ready
    if _agent_events_ready:
        return

    schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["source", "agent", "event_type", "ts"],
            "properties": {
                "source": {
                    "bsonType": "string",
                    "description": "Logical sender — e.g. 'rian-project1'.",
                },
                "agent": {
                    "bsonType": "string",
                    "description": "The agent inside that source (research, outreach, ...)",
                },
                "event_type": {
                    "bsonType": "string",
                    "description": "e.g. trace.start, trace.tool_call, lead.note, error",
                },
                "lead_id": {"bsonType": ["string", "null"]},
                "trace_id": {"bsonType": ["string", "null"]},
                "payload": {"bsonType": "object"},
                "ts": {"bsonType": "string"},
            },
        }
    }
    try:
        existing = await db.list_collection_names(filter={"name": AGENT_EVENTS_COLLECTION})
        if not existing:
            await db.create_collection(AGENT_EVENTS_COLLECTION, validator=schema)
            log.info("created %s with validator", AGENT_EVENTS_COLLECTION)
        else:
            try:
                await db.command(
                    {"collMod": AGENT_EVENTS_COLLECTION, "validator": schema}
                )
            except Exception as e:  # noqa: BLE001
                log.info("collMod for %s skipped: %s", AGENT_EVENTS_COLLECTION, e)
    except Exception as e:  # noqa: BLE001
        log.info("validator setup for %s skipped: %s", AGENT_EVENTS_COLLECTION, e)
    _agent_events_ready = True


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def _verify_token(authorization: str | None) -> str:
    """Validate the bearer token. Returns auth_status for audit metadata.

    - No env var set       → "dev_open" (allowed, logged)
    - Header missing/wrong → 401
    - Header matches token → "authenticated"
    """
    expected = os.environ.get("RIAN_INTEGRATION_TOKEN", "").strip()
    if not expected:
        return "dev_open"

    if not authorization:
        raise HTTPException(401, "missing Authorization header")
    parts = authorization.split(None, 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(401, "expected `Authorization: Bearer <token>`")
    if parts[1].strip() != expected:
        raise HTTPException(401, "invalid integration token")
    return "authenticated"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class AgentEvent(BaseModel):
    source: str = Field(
        default="rian-project1",
        description="Logical sender of the event (system identifier).",
    )
    agent: str = Field(
        ...,
        description="Agent name inside the sender (e.g. 'research', 'outreach').",
    )
    event_type: str = Field(
        ...,
        description="Event kind — e.g. 'trace.start', 'trace.tool_call', 'lead.note'.",
    )
    lead_id: str | None = Field(default=None, description="Optional SolarReach lead id this event refers to.")
    trace_id: str | None = Field(default=None, description="Caller-supplied trace correlator.")
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: str | None = Field(
        default=None,
        description="ISO-8601 timestamp; server-stamped if absent.",
    )


class AgentEventResponse(BaseModel):
    ok: bool
    id: str
    auth_status: str


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------


@router.post("/integration/agent_event", response_model=AgentEventResponse)
async def post_agent_event(
    body: AgentEvent,
    authorization: str | None = Header(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> AgentEventResponse:
    """Append an agent trace event from Rian's stack.

    Writes to ``agent_events`` and mirrors a row to ``audit_log`` so spend +
    cross-system observability stay in one place.
    """
    auth_status = _verify_token(authorization)
    await _ensure_agent_events_collection(db)

    now = datetime.now(timezone.utc).isoformat()
    event_id = f"ae_{uuid.uuid4()}"
    doc = {
        "_id": event_id,
        "source": body.source,
        "agent": body.agent,
        "event_type": body.event_type,
        "lead_id": body.lead_id,
        "trace_id": body.trace_id,
        "payload": body.payload or {},
        "ts": body.ts or now,
    }
    try:
        await db[AGENT_EVENTS_COLLECTION].insert_one(doc)
    except Exception as e:  # noqa: BLE001 — never crash the integration route
        log.exception("agent_events insert failed: %s", e)
        raise HTTPException(500, f"agent_events insert failed: {type(e).__name__}")

    await log_audit(
        db,
        action="integration.agent_event",
        lead_id=body.lead_id,
        cost_cents=0,
        actor=f"{body.source}/{body.agent}",
        metadata={
            "source": body.source,
            "agent": body.agent,
            "event_type": body.event_type,
            "trace_id": body.trace_id,
            "auth_status": auth_status,
        },
    )

    return AgentEventResponse(ok=True, id=event_id, auth_status=auth_status)
