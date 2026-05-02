"""Mongo change-stream helpers.

True `collection.watch()` requires a replica set, which our local docker
mongo may not have. We expose a single iterator function that:
  1. First emits all leads that already match (fast path for synthesised data).
  2. Then attempts a real change stream; if not available, polls the
     collection for new docs every 500ms up to a short timeout.

This keeps the SSE contract identical regardless of deployment shape.
"""
from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase


async def iter_new_leads(
    db: AsyncIOMotorDatabase,
    *,
    client_id: str,
    postcode: str,
    scan_id: str | None = None,
    poll_seconds: float = 0.5,
    max_wait_seconds: float = 5.0,
) -> AsyncIterator[dict[str, Any]]:
    seen: set[str] = set()
    query: dict[str, Any] = {"client_id": client_id, "postcode": postcode}
    if scan_id:
        query["scan_id"] = scan_id

    # Phase 1 — flush whatever already matches.
    async for doc in db.leads.find(query):
        seen.add(doc["_id"])
        yield doc

    # Phase 2 — try true change stream; on failure, fall back to polling.
    try:
        # `watch` raises on standalone mongo; we don't try-await separately.
        # noqa: SIM117
        async with db.leads.watch(
            [{"$match": {"operationType": "insert", "fullDocument.client_id": client_id,
                         "fullDocument.postcode": postcode}}]
        ) as stream:
            async with asyncio.timeout(max_wait_seconds):
                async for change in stream:
                    doc = change.get("fullDocument") or {}
                    if doc.get("_id") in seen:
                        continue
                    seen.add(doc.get("_id"))
                    yield doc
    except Exception:
        # Polling fallback for standalone mongo / mongomock.
        elapsed = 0.0
        while elapsed < max_wait_seconds:
            await asyncio.sleep(poll_seconds)
            elapsed += poll_seconds
            async for doc in db.leads.find(query):
                if doc["_id"] in seen:
                    continue
                seen.add(doc["_id"])
                yield doc
