"""/lead/* endpoints — fetch, refresh directors, build org, pitch, downloads.

Long-running stages (build_org, pitch) are A2-stubbed but return shapes that
match CONTRACTS § 2 so the frontend can wire blind.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.config import Settings
from app.deps import get_app_settings, get_db
from app.services.audit import log_audit

router = APIRouter()
log = logging.getLogger("solarreach.api.leads")


# --- helpers ---

async def _join_lead(db: AsyncIOMotorDatabase, lead: dict) -> dict:
    """$lookup-style join: attach company + directors to lead doc."""
    company_id = (lead.get("owner") or {}).get("company_id")
    if not company_id:
        return lead
    company = await db.companies.find_one({"_id": company_id})
    if not company:
        return lead
    director_ids = company.get("directors", []) or []
    directors: list[dict] = []
    if director_ids:
        cursor = db.directors.find({"_id": {"$in": director_ids}})
        directors = await cursor.to_list(length=200)
    lead = {**lead, "company": company, "directors": directors}
    return lead


# --- GET /lead/<id> ---

@router.get("/lead/{lead_id}")
async def get_lead(
    lead_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(status_code=404, detail="lead not found")
    joined = await _join_lead(db, lead)
    return joined


# --- POST /lead/<id>/refresh_directors ---

class RefreshDirectorsResponse(BaseModel):
    directors: list[dict]


@router.post("/lead/{lead_id}/refresh_directors", response_model=RefreshDirectorsResponse)
async def refresh_directors(
    lead_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> RefreshDirectorsResponse:
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    company_id = (lead.get("owner") or {}).get("company_id")
    if not company_id:
        raise HTTPException(400, "lead has no associated company")
    company = await db.companies.find_one({"_id": company_id})
    if not company:
        raise HTTPException(404, "company not found")

    ch_number = company.get("ch_number")
    # Audit BEFORE the call (cardinal rule).
    await log_audit(
        db,
        action="api.call",
        lead_id=lead_id,
        cost_cents=0,
        metadata={"provider": "companies_house", "ch_number": ch_number},
    )

    if not ch_number or not settings.companies_house_api_key:
        # A2 STUB — return mock directors so frontend can render.
        log.info("# A2 STUB refresh_directors lead=%s", lead_id)
        mock = [
            {
                "_id": f"director_{uuid.uuid4()}",
                "company_id": company_id,
                "name": "Patel, Sarah",
                "name_display": "Sarah Patel",
                "role": "Director",
                "appointed_on": "2018-04-01",
            }
        ]
        return RefreshDirectorsResponse(directors=mock)

    # Live path — Companies House officers list.
    url = f"https://api.company-information.service.gov.uk/company/{ch_number}/officers"
    async with httpx.AsyncClient(timeout=10.0) as cx:
        resp = await cx.get(url, auth=(settings.companies_house_api_key, ""))
    if resp.status_code != 200:
        raise HTTPException(502, f"companies house: {resp.status_code}")
    data = resp.json()
    return RefreshDirectorsResponse(directors=data.get("items", []))


# --- POST /lead/<id>/build_org ---

class BuildOrgResponse(BaseModel):
    decision_maker: dict


@router.post("/lead/{lead_id}/build_org", response_model=BuildOrgResponse)
async def build_org(
    lead_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
) -> BuildOrgResponse:
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")
    # A2 STUB — TODO(A4): delegate to codex via celery.
    await log_audit(
        db,
        action="lead.build_org",
        lead_id=lead_id,
        cost_cents=0,
        metadata={"stub": True},
    )
    log.info("# A2 STUB build_org lead=%s", lead_id)
    decision_maker = {
        "name": "Sarah Patel",
        "role": "CFO",
        "confidence": 0.78,
        "rationale": "Stubbed — codex pipeline (A4) will replace.",
    }
    await db.leads.update_one(
        {"_id": lead_id}, {"$set": {"decision_maker": decision_maker}}
    )
    return BuildOrgResponse(decision_maker=decision_maker)


# --- POST /lead/<id>/pitch ---

class PitchRequest(BaseModel):
    client_id: str


@router.post("/lead/{lead_id}/pitch")
async def pitch(
    lead_id: str,
    body: PitchRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")
    await log_audit(
        db,
        action="lead.pitch",
        lead_id=lead_id,
        cost_cents=0,
        metadata={"client_id": body.client_id, "stub": True},
    )
    log.info("# A2 STUB pitch lead=%s", lead_id)
    pitch_id = f"pitch_{uuid.uuid4()}"
    base = f"/static/pitches/{pitch_id}"
    # TODO(A4): codex generates real PPTX/PDF; for now return mock URLs.
    payload = {
        "pptx_url": f"{base}.pptx",
        "pdf_url": f"{base}.pdf",
        "emails": {
            "a": "Subject: Solar partnership for {{company}}\n\nHi {{name}}, ...",
            "b": "Subject: Cutting your energy bill\n\nHi {{name}}, ...",
        },
        "deck_json": {
            "slides": [
                {"title": "Why Solar, Why Now", "bullets": ["ROI", "ESG", "Resilience"]},
                {"title": "Your Building", "bullets": [lead.get("address", "")]},
            ]
        },
    }
    await db.leads.update_one({"_id": lead_id}, {"$set": {"pitch": payload}})
    return JSONResponse(payload)


@router.get("/lead/{lead_id}/pitch/download")
async def pitch_download(
    lead_id: str,
    format: str = Query(default="pdf", pattern="^(pdf|pptx)$"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")
    static_dir = Path(os.environ.get("SOLARREACH_STATIC_DIR", "static")) / "pitches"
    static_dir.mkdir(parents=True, exist_ok=True)
    # A2 STUB — write a placeholder so download is testable.
    fname = f"{lead_id}.{format}"
    fpath = static_dir / fname
    if not fpath.exists():
        fpath.write_bytes(b"%PDF-stub\n" if format == "pdf" else b"PK\x03\x04stub")
    return FileResponse(
        path=str(fpath),
        filename=fname,
        media_type="application/pdf" if format == "pdf" else
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )


# --- GET /lead/spend/session ---

@router.get("/lead/spend/session")
async def spend_session(
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$cost_cents"}}}]
    cursor = db.audit_log.aggregate(pipeline)
    docs = await cursor.to_list(length=1)
    spent = int(docs[0]["total"]) if docs else 0
    budget = int(settings.session_budget_gbp * 100)
    pct = (spent / budget) if budget > 0 else 0.0
    return {"spent_cents": spent, "budget_cents": budget, "budget_pct": round(pct, 4)}
