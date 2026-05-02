"""
SolarReach API — /lead/{lead_id}/pitch
POST  → generate deck JSON + emails + PPTX + PDF
GET   → download PPTX or PDF
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel

from codex_brain.generators.deck import generate_pitch, LeadBrief
from codex_brain.generators.email import generate_email_variants
from codex_brain.generators.org_chart import infer_decision_maker
from codex_brain.constants_funding import FUNDING_MODELS

router = APIRouter(prefix="/lead/{lead_id}", tags=["pitch"])

OUTPUT_DIR = Path(os.getenv("PITCH_OUTPUT_DIR", "/tmp/solarreach_pitches"))


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class PitchRequest(BaseModel):
    company_name: str
    decision_maker_name: str
    decision_maker_role: str
    postcode: str
    roof_area_m2: float
    annual_kwh: float
    panel_count: int
    payback_years: float
    pitch_theme: str = "GRID INDEPENDENCE"
    client_name: str = "GreenSolar UK"


class SlideOut(BaseModel):
    title: str
    subtitle: str | None = None
    bullets: list[str] = []
    speaker_note: str | None = None


class EmailOut(BaseModel):
    variant: str
    subject: str
    body: str
    angle: str


class FundingModelOut(BaseModel):
    name: str
    short: str
    headline: str
    description: str
    pros: list[str]
    cons: list[str]
    typical_payback_yrs: str


class PitchResponse(BaseModel):
    lead_id: str
    slides: list[SlideOut]
    emails: list[EmailOut]
    funding_models: list[FundingModelOut]
    pptx_url: str
    pdf_url: str | None
    cost_cents: float
    cache_read_tokens: int


# ---------------------------------------------------------------------------
# POST /lead/{lead_id}/pitch
# ---------------------------------------------------------------------------

@router.post("/pitch", response_model=PitchResponse)
async def build_pitch(lead_id: str, req: PitchRequest) -> PitchResponse:
    out_dir = OUTPUT_DIR / lead_id
    out_dir.mkdir(parents=True, exist_ok=True)

    brief = LeadBrief(
        company_name=req.company_name,
        decision_maker_name=req.decision_maker_name,
        decision_maker_role=req.decision_maker_role,
        postcode=req.postcode,
        roof_area_m2=req.roof_area_m2,
        annual_kwh=req.annual_kwh,
        panel_count=req.panel_count,
        payback_years=req.payback_years,
        pitch_theme=req.pitch_theme,
        client_name=req.client_name,
    )

    try:
        result = generate_pitch(brief, out_dir)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    slides = [
        SlideOut(
            title=s.get("title", ""),
            subtitle=s.get("subtitle"),
            bullets=s.get("bullets", []),
            speaker_note=s.get("speaker_note"),
        )
        for s in result.slides
    ]

    emails = [
        EmailOut(variant="A", subject=result.emails[0]["subject"],
                 body=result.emails[0]["body"], angle=result.emails[0].get("angle", "")),
        EmailOut(variant="B", subject=result.emails[1]["subject"],
                 body=result.emails[1]["body"], angle=result.emails[1].get("angle", "")),
    ] if len(result.emails) >= 2 else []

    funding = [FundingModelOut(**m) for m in FUNDING_MODELS]

    pptx_url = f"/lead/{lead_id}/pitch/download?format=pptx"
    pdf_url  = f"/lead/{lead_id}/pitch/download?format=pdf" if result.pdf_path else None

    return PitchResponse(
        lead_id=lead_id,
        slides=slides,
        emails=emails,
        funding_models=funding,
        pptx_url=pptx_url,
        pdf_url=pdf_url,
        cost_cents=result.usage.cost_cents,
        cache_read_tokens=result.usage.cache_read_tokens,
    )


# ---------------------------------------------------------------------------
# GET /lead/{lead_id}/pitch/download
# ---------------------------------------------------------------------------

@router.get("/pitch/download")
async def download_pitch(lead_id: str, format: str = "pdf") -> FileResponse:
    out_dir = OUTPUT_DIR / lead_id

    if format == "pdf":
        matches = list(out_dir.glob("*.pdf"))
        if not matches:
            raise HTTPException(status_code=404, detail="PDF not found — generate first")
        path = matches[0]
        media_type = "application/pdf"
    else:
        matches = list(out_dir.glob("*.pptx"))
        if not matches:
            raise HTTPException(status_code=404, detail="PPTX not found — generate first")
        path = matches[0]
        media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

    return FileResponse(
        path=path,
        media_type=media_type,
        filename=path.name,
    )
