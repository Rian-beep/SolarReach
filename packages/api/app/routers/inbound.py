"""POST /inbound/lead — calculator-mode capture.

Inbound user submits address + estimated annual kWh. We persist a lead and
return the financial breakdown so the calculator UI can render immediately.
Recipient email is sha256-hashed in the audit log; we strip it from the
returned doc to avoid leaking via openapi typegen + browser dev tools.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, EmailStr, Field

from app.deps import get_db
from app.routers.financial import _calc
from app.services.audit import log_audit

router = APIRouter()


class InboundLead(BaseModel):
    address: str
    postcode: str
    annual_kwh: float = Field(gt=0)
    email: EmailStr | None = None
    premises_type: str = "residential"


@router.post("/inbound/lead")
async def inbound_lead(
    body: InboundLead,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    now = datetime.now(timezone.utc).isoformat()
    lead_id = f"lead_{uuid.uuid4()}"
    fin = _calc(body.annual_kwh, body.premises_type)
    doc = {
        "_id": lead_id,
        "client_id": "calculator",
        "address": body.address,
        "postcode": body.postcode,
        "premises_type": body.premises_type,
        "financial": fin,
        "scores": {"composite_score": 0, "scored_at": now},
        "created_at": now,
        "updated_at": now,
        # email is hashed in audit log; never persisted plaintext on lead.
    }
    await db.leads.insert_one(doc)
    await log_audit(
        db,
        action="inbound.lead",
        lead_id=lead_id,
        cost_cents=0,
        recipient_email=str(body.email) if body.email else None,
        metadata={"premises_type": body.premises_type},
    )
    return doc
