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
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.deps import get_db
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

    # A2 STUB: synthesise a small set of leads inline so frontend has data.
    # TODO(A4): replace with real codex pipeline trigger.
    seeded: list[dict] = []
    for i in range(min(body.limit, 5)):
        lead_id = f"lead_{uuid.uuid4()}"
        seeded.append(
            {
                "_id": lead_id,
                "client_id": body.client_id,
                "address": f"{i + 1} Demo Street, {body.postcode}",
                "postcode": body.postcode,
                "borough": "London Borough of Camden",
                "premises_type": ["office", "retail", "warehouse"][i % 3],
                "geo": {
                    "point": {
                        "type": "Point",
                        "coordinates": [-0.0876 + i * 0.001, 51.5256 + i * 0.001],
                    }
                },
                "scores": {
                    "solar_roi": 0.6 + 0.05 * i,
                    "financial_health": 0.5 + 0.04 * i,
                    "social_impact": 0.4 + 0.03 * i,
                    "composite_score": 60 + i * 4,
                    "scored_at": now,
                },
                "owner": {
                    "company_id": None,
                    "company_name": f"Demo Holdings {i + 1} Ltd",
                    "source": "synthesized",
                },
                "scan_id": scan_id,
                "created_at": now,
                "updated_at": now,
            }
        )
    if seeded:
        await db.leads.insert_many(seeded)

    return ScanResponse(
        scan_id=scan_id,
        lead_count=len(seeded),
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

    async def event_gen():
        completed = 0
        async for lead in iter_new_leads(
            db, client_id=job["client_id"], postcode=job["postcode"], scan_id=scan_id
        ):
            completed += 1
            yield {"event": "lead", "data": json.dumps(lead, default=str)}
            yield {
                "event": "progress",
                "data": json.dumps({"completed": completed, "total": job["limit"]}),
            }
            # Yield to event loop briefly so SSE flushes.
            await asyncio.sleep(0)
        yield {
            "event": "done",
            "data": json.dumps({"scan_id": scan_id, "lead_count": completed}),
        }

    return EventSourceResponse(event_gen())
