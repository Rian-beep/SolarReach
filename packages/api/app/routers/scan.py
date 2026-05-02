"""POST /scan and GET /scan/<id>/stream.

Strategy:
  - POST /scan creates a job doc in `scan_jobs` and returns scan_id + stream_url.
  - The actual scoring pipeline is owned by A4 (codex). For demo, we seed the
    `leads` collection with a mocked lead so that downstream endpoints have data
    to return. The SSE stream emits any leads matching client_id+postcode and
    finishes with `event: done`.
  - When a real Mongo replica set is wired up, swap the polling loop in
    `change_streams.iter_new_leads` for a true `collection.watch()`.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.deps import get_db

log = logging.getLogger("solarreach.api.scan")
from app.services.audit import log_audit
from app.services.change_streams import iter_new_leads

router = APIRouter()


class ScanRequest(BaseModel):
    postcode: str = Field(min_length=2)
    client_id: str
    limit: int = 50


class ScanResponse(BaseModel):
    scan_id: str
    lead_count: int
    stream_url: str


@router.post("/scan", response_model=ScanResponse)
async def create_scan(
    body: ScanRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> ScanResponse:
    scan_id = f"scan_{uuid.uuid4()}"
    now = datetime.now(timezone.utc).isoformat()
    await db.scan_jobs.insert_one(
        {
            "_id": scan_id,
            "postcode": body.postcode,
            "client_id": body.client_id,
            "limit": body.limit,
            "status": "queued",
            "created_at": now,
        }
    )
    # Audit BEFORE any paid call (per A2 hard rule).
    await log_audit(
        db,
        action="lead.scan.create",
        cost_cents=0,
        metadata={"postcode": body.postcode, "client_id": body.client_id},
    )

    # Real path: query existing leads matching postcode (A1's seeded data
    # populated by scripts/seed_demo_real.py + match_leads_to_inspire.py).
    # We do NOT synthesise on every scan — that pollutes the corpus and
    # produces fake "Demo Holdings N Ltd" owners which kill the demo story.
    #
    # Tag the matched leads with this scan_id so the SSE stream picks them up.
    matched = await db.leads.update_many(
        {"client_id": body.client_id, "postcode": body.postcode},
        {"$set": {"scan_id": scan_id}},
    )
    lead_count = matched.modified_count
    log.info(
        "scan_id=%s postcode=%s matched=%d real leads (no synth)",
        scan_id,
        body.postcode,
        lead_count,
    )

    # Persist the actual lead_count so the SSE stream can quote it as the
    # `progress.total` — that way `scan.lead_count`, every `progress.total`,
    # and the final `done.lead_count` all agree (CONTRACTS § 3).
    await db.scan_jobs.update_one(
        {"_id": scan_id},
        {"$set": {"lead_count": lead_count, "status": "matched"}},
    )

    return ScanResponse(
        scan_id=scan_id,
        lead_count=lead_count,
        stream_url=f"/scan/{scan_id}/stream",
    )


@router.get("/scan/{scan_id}/stream")
async def stream_scan(
    scan_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    job = await db.scan_jobs.find_one({"_id": scan_id})
    if not job:
        raise HTTPException(status_code=404, detail="scan not found")

    # Use the persisted lead_count (set by POST /scan) as the progress total
    # so frontend progress bars don't claim "12 / 50" when only 12 real leads
    # exist. Falls back to job["limit"] for legacy jobs created before this fix.
    total = int(job.get("lead_count", job.get("limit", 0)))

    async def event_gen():
        completed = 0
        async for lead in iter_new_leads(
            db, client_id=job["client_id"], postcode=job["postcode"], scan_id=scan_id
        ):
            completed += 1
            yield {"event": "lead", "data": json.dumps(lead, default=str)}
            yield {
                "event": "progress",
                "data": json.dumps({"completed": completed, "total": total}),
            }
            # Yield to event loop briefly so SSE flushes.
            await asyncio.sleep(0)
        yield {
            "event": "done",
            "data": json.dumps({"scan_id": scan_id, "lead_count": completed}),
        }

    return EventSourceResponse(event_gen())
