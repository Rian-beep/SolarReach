"""Project1 (deepagents/Atlas lead-research) linkage layer.

The companion repo `Rian-beep/solarreach-project1` writes to the same Atlas
cluster: `solarreach` for application data, `solarreach_agent_store` for the
LangGraph long-term store. Rather than import its heavy langgraph stack into
our API, we read those collections directly via the existing motor client.

Two surfaces:

- ``fetch_project1_leads(db, client_id, postcode, limit)`` — returns leads
  for a client/postcode, opportunistically merging any agent notes from
  ``solarreach_agent_store.store`` keyed by ``lead:<id>``. If the agent-store
  database/collection does not exist, the merge is a no-op.

- ``push_outreach_event(db, lead_id, event)`` — append a row to the
  ``outreach_events`` collection. The collection is created lazily with a
  $jsonSchema validator so downstream consumers (project1 outreach agent,
  analytics) get a stable contract.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

log = logging.getLogger("solarreach.api.project1_link")


# Name kept here so it is greppable across services and tests.
OUTREACH_EVENTS = "outreach_events"
AGENT_STORE_DB = "solarreach_agent_store"
AGENT_STORE_COLL = "store"


_outreach_events_ready = False


async def _ensure_outreach_events_collection(db: AsyncIOMotorDatabase) -> None:
    """Create ``outreach_events`` with $jsonSchema validator if missing.

    Idempotent. Process-cached so we only pay the listCollections roundtrip
    once per worker.
    """
    global _outreach_events_ready
    if _outreach_events_ready:
        return

    schema = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["lead_id", "event_type", "ts"],
            "properties": {
                "lead_id": {"bsonType": "string"},
                "event_type": {
                    "bsonType": "string",
                    "description": "e.g. email_sent, email_opened, voice_called",
                },
                "payload": {"bsonType": "object"},
                "ts": {"bsonType": "string"},
                "actor": {"bsonType": "string"},
            },
        }
    }
    try:
        existing = await db.list_collection_names(filter={"name": OUTREACH_EVENTS})
        if not existing:
            await db.create_collection(OUTREACH_EVENTS, validator=schema)
            log.info("created %s with validator", OUTREACH_EVENTS)
        else:
            # Best-effort upgrade of validator on already-existing collection.
            try:
                await db.command(
                    {"collMod": OUTREACH_EVENTS, "validator": schema}
                )
            except Exception as e:  # noqa: BLE001
                log.info("collMod for %s skipped: %s", OUTREACH_EVENTS, e)
    except Exception as e:  # noqa: BLE001
        # mongomock and other test backends don't support validators — log and move on.
        log.info("validator setup for %s skipped: %s", OUTREACH_EVENTS, e)
    _outreach_events_ready = True


async def _fetch_agent_notes(
    motor_client: AsyncIOMotorClient | None,
    lead_ids: list[str],
) -> dict[str, dict[str, Any]]:
    """Pull notes the project1 agent has stored for these leads, if any.

    Project1 uses langgraph-store-mongodb which writes documents shaped as
    ``{namespace: [...], key: ..., value: {...}}``. We look up by
    ``key == "lead:<id>"`` across any namespace.
    """
    if not motor_client or not lead_ids:
        return {}
    try:
        store_db = motor_client[AGENT_STORE_DB]
        store_coll = store_db[AGENT_STORE_COLL]
        keys = [f"lead:{lid}" for lid in lead_ids]
        cursor = store_coll.find({"key": {"$in": keys}})
        out: dict[str, dict[str, Any]] = {}
        async for doc in cursor:
            key = doc.get("key", "")
            if key.startswith("lead:"):
                lid = key.split(":", 1)[1]
                value = doc.get("value")
                if isinstance(value, dict):
                    out[lid] = value
        return out
    except Exception as e:  # noqa: BLE001
        log.info("agent-store note fetch skipped: %s", e)
        return {}


async def fetch_project1_leads(
    db: AsyncIOMotorDatabase,
    *,
    client_id: str,
    postcode: str | None = None,
    limit: int = 50,
    motor_client: AsyncIOMotorClient | None = None,
) -> list[dict[str, Any]]:
    """Return leads for ``client_id`` (optionally filtered by ``postcode``)
    with project1 agent-store notes merged in.

    Atlas-first: we query OUR canonical ``leads`` collection. Then, if the
    agent store DB exists, we look up ``lead:<id>`` keys there and attach
    matched docs under each lead's ``project1_notes`` field.

    Dedupes by ``_id`` (defensive — leads should already be unique-by-id).
    """
    query: dict[str, Any] = {"client_id": client_id}
    if postcode:
        query["postcode"] = postcode
    cursor = (
        db.leads.find(query)
        .sort([("scores.composite_score", -1), ("created_at", -1)])
        .limit(limit)
    )
    leads: list[dict[str, Any]] = await cursor.to_list(length=limit)

    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for lead in leads:
        lid = lead.get("_id")
        if not lid or lid in seen:
            continue
        seen.add(lid)
        deduped.append(lead)

    notes_by_id = await _fetch_agent_notes(
        motor_client, [str(lead["_id"]) for lead in deduped]
    )
    if notes_by_id:
        for lead in deduped:
            lid = str(lead["_id"])
            if lid in notes_by_id:
                lead["project1_notes"] = notes_by_id[lid]

    return deduped


async def push_outreach_event(
    db: AsyncIOMotorDatabase,
    *,
    lead_id: str,
    event: dict[str, Any],
) -> str:
    """Write an outreach event row. Returns the inserted doc's ``_id``.

    ``event`` should at minimum contain ``event_type`` (str). Optional
    ``payload`` (dict) is passed through. ``ts`` is auto-stamped if absent.
    """
    await _ensure_outreach_events_collection(db)

    doc: dict[str, Any] = {
        "_id": f"oe_{lead_id}_{int(datetime.now(timezone.utc).timestamp() * 1000)}",
        "lead_id": lead_id,
        "event_type": str(event.get("event_type") or "unknown"),
        "payload": event.get("payload") or {},
        "ts": event.get("ts") or datetime.now(timezone.utc).isoformat(),
        "actor": event.get("actor") or "system",
    }
    await db[OUTREACH_EVENTS].insert_one(doc)
    return str(doc["_id"])


__all__ = [
    "fetch_project1_leads",
    "push_outreach_event",
    "OUTREACH_EVENTS",
    "AGENT_STORE_DB",
    "AGENT_STORE_COLL",
]
