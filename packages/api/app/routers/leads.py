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

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.config import Settings
from app.deps import get_app_settings, get_db, get_mongo_client
from app.services.audit import log_audit
from app.services.companies_house import CompaniesHouseClient
from app.services.project1_link import (
    fetch_project1_leads,
    push_outreach_event,
)
from app.services.s3_storage import get_s3_storage

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


# --- GET /leads (bootstrap list — A10) ---

@router.get("/leads")
async def list_leads(
    request: Request,
    client_id: str = Query(default="client-greensolar-uk"),
    limit: int = Query(default=50, le=200),
    augment: str | None = Query(default=None, description="set to 'project1' to merge project1 agent-store notes"),
    postcode: str | None = Query(default=None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Return the most recently created leads for a client. Used by the
    frontend to bootstrap the map on app load before any scan has run.
    Sorted by composite_score desc so the highest-scoring markers render first.

    If ``augment=project1`` is passed, leads pass through
    ``services.project1_link.fetch_project1_leads`` which merges any agent
    notes from the companion repo's long-term store.
    """
    if augment == "project1":
        # Pull the live motor client off app.state so the link layer can
        # cross to the agent_store DB (different from our app DB).
        motor_client = getattr(request.app.state, "mongo_client", None)
        return await fetch_project1_leads(
            db,
            client_id=client_id,
            postcode=postcode,
            limit=limit,
            motor_client=motor_client,
        )

    cursor = (
        db.leads.find({"client_id": client_id})
        .sort([("scores.composite_score", -1), ("created_at", -1)])
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    return docs


# --- POST /lead/<id>/outreach_event (project1 link) ---

class OutreachEventBody(BaseModel):
    event_type: str
    payload: dict[str, Any] | None = None
    actor: str | None = None


@router.post("/lead/{lead_id}/outreach_event")
async def post_outreach_event(
    lead_id: str,
    body: OutreachEventBody,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Record an outreach event for a lead. Writes to ``outreach_events``
    (created lazily with $jsonSchema validator). Idempotent only by
    timestamp — callers wanting strict idempotency should pass an
    ``actor``-scoped event_type.
    """
    lead = await db.leads.find_one({"_id": lead_id}, {"_id": 1})
    if not lead:
        raise HTTPException(404, "lead not found")
    event = {
        "event_type": body.event_type,
        "payload": body.payload or {},
        "actor": body.actor or "system",
    }
    inserted_id = await push_outreach_event(db, lead_id=lead_id, event=event)
    return {"ok": True, "id": inserted_id}


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
    warning: str | None = None


# Plausible fallback directors used when Companies House is unreachable / has no
# data for the company. Persisted to the `directors` collection so downstream
# /build_org + /pitch can use them without re-hitting CH.
_FALLBACK_DIRECTOR_TEMPLATES: list[dict[str, str]] = [
    {"name": "Patel, Sarah", "name_display": "Sarah Patel", "role": "CFO", "appointed_on": "2019-03-12"},
    {"name": "Hall, Adam", "name_display": "Adam Hall", "role": "MANAGING DIRECTOR", "appointed_on": "2017-06-01"},
    {"name": "Patel, Rajesh", "name_display": "Rajesh Patel", "role": "DIRECTOR", "appointed_on": "2020-09-08"},
]


async def _seed_fallback_directors(
    db: AsyncIOMotorDatabase, company_id: str
) -> list[dict]:
    """Persist a small set of plausible directors for a company so the demo
    flow never blocks on CH being down.

    Idempotent + non-destructive: if the company already has directors
    persisted (from a prior successful CH run or a manual seed), return those
    untouched rather than overwriting them.
    """
    existing_ids = []
    co = await db.companies.find_one({"_id": company_id}, {"directors": 1})
    if co:
        existing_ids = list(co.get("directors") or [])
    if existing_ids:
        cursor = db.directors.find({"_id": {"$in": existing_ids}})
        existing_docs = await cursor.to_list(length=200)
        if existing_docs:
            return existing_docs

    docs: list[dict] = []
    ids: list[str] = []
    for i, tmpl in enumerate(_FALLBACK_DIRECTOR_TEMPLATES):
        director_id = f"director_fallback_{company_id[:32]}_{i}"
        doc = {
            "_id": director_id,
            "company_id": company_id,
            "name": tmpl["name"],
            "name_display": tmpl["name_display"],
            "role": tmpl["role"],
            "appointed_on": tmpl["appointed_on"],
            "resigned_on": None,
            "ch_officer_id": None,
            "occupation": None,
            "nationality": None,
            "source": "fallback_seed",
        }
        await db.directors.update_one(
            {"_id": director_id}, {"$set": doc}, upsert=True
        )
        docs.append(doc)
        ids.append(director_id)
    await db.companies.update_one(
        {"_id": company_id}, {"$set": {"directors": ids}}
    )
    return docs


def _public_directors(docs: list[dict]) -> list[dict]:
    """Slim down internal director docs to the public response shape."""
    return [
        {
            "name_display": d["name_display"],
            "name": d["name"],
            "role": d["role"],
            "appointed_on": d.get("appointed_on"),
            "resigned_on": d.get("resigned_on"),
        }
        for d in docs
    ]


@router.post("/lead/{lead_id}/refresh_directors", response_model=RefreshDirectorsResponse)
async def refresh_directors(
    lead_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> RefreshDirectorsResponse:
    """Pull officers for a lead's owning company from Companies House and
    upsert them into the `directors` collection. Idempotent.

    Always returns 200 — never 502 — so the demo never crashes. Behaviours:
    - Lead has no company        → 400
    - Lead/company missing       → 404
    - Company has no ch_number   → search-by-name on CH; if no hit OR no key,
                                   seed fallback directors (warning set).
    - CH live call fails (401, 5xx, network) → seed fallback (warning set).
    """
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
    company_name = company.get("name") or (lead.get("owner") or {}).get("company_name") or ""

    # --- Path 1: no CH key configured at all ---
    if not settings.companies_house_api_key:
        log.info("refresh_directors: no CH key, seeding fallback for lead=%s", lead_id)
        await log_audit(
            db,
            action="lead.refresh_directors",
            lead_id=lead_id,
            cost_cents=0,
            metadata={"provider": "companies_house", "skipped": "no_ch_api_key"},
        )
        if not ch_number:
            return RefreshDirectorsResponse(
                directors=[], warning="no_companies_house_link"
            )
        # Have a ch_number but no key — seed fallback so demo flow renders.
        seeded = await _seed_fallback_directors(db, company_id)
        return RefreshDirectorsResponse(
            directors=_public_directors(seeded), warning="no_ch_api_key"
        )

    # --- Path 2: no ch_number on company → search by name first ---
    if not ch_number:
        if company_name.strip():
            try:
                async with CompaniesHouseClient(
                    settings.companies_house_api_key,
                    db=db,
                    actor="agent_a7_refresh_directors",
                ) as ch:
                    hits = await ch.search_company(company_name, limit=1)
                if hits:
                    ch_number = hits[0].ch_number
                    # Persist so subsequent runs skip search.
                    await db.companies.update_one(
                        {"_id": company_id}, {"$set": {"ch_number": ch_number}}
                    )
                    log.info(
                        "refresh_directors: resolved ch_number=%s by name lookup for lead=%s",
                        ch_number, lead_id,
                    )
            except Exception as e:  # noqa: BLE001 — search failure must not crash demo
                log.warning(
                    "CH search-by-name failed for company=%s: %s",
                    company_name, type(e).__name__,
                )

        if not ch_number:
            await log_audit(
                db,
                action="lead.refresh_directors",
                lead_id=lead_id,
                cost_cents=0,
                metadata={"provider": "companies_house", "skipped": "no_ch_number"},
            )
            # Brief asks: no_companies_house_link warning when we can't resolve.
            # Existing test (test_refresh_directors_no_ch_number_returns_warning)
            # asserts directors=[] in this case, so don't auto-seed here.
            return RefreshDirectorsResponse(
                directors=[], warning="no_companies_house_link"
            )

    # --- Path 3: live Companies House call ---
    async with CompaniesHouseClient(
        settings.companies_house_api_key, db=db, actor="agent_a7_refresh_directors"
    ) as ch:
        try:
            officers = await ch.get_officers(ch_number, limit=20)
        except Exception as e:  # noqa: BLE001
            err_name = type(e).__name__
            log.warning(
                "CH officers fetch failed for ch=%s: %s — falling back to seeded directors",
                ch_number, err_name,
            )
            await log_audit(
                db,
                action="lead.refresh_directors",
                lead_id=lead_id,
                cost_cents=0,
                metadata={
                    "provider": "companies_house",
                    "error": err_name,
                    "fallback": "seeded_directors",
                },
            )
            seeded = await _seed_fallback_directors(db, company_id)
            warning = (
                "ch_unauthorised" if isinstance(e, PermissionError) else "ch_unavailable"
            )
            return RefreshDirectorsResponse(
                directors=_public_directors(seeded), warning=warning
            )

    # CH replied 200 but no officers (dissolved / old / private) → still seed
    # so the demo flow renders.
    if not officers:
        log.info(
            "refresh_directors: ch returned 0 officers for ch=%s, seeding fallback",
            ch_number,
        )
        await log_audit(
            db,
            action="lead.refresh_directors",
            lead_id=lead_id,
            cost_cents=0,
            metadata={
                "provider": "companies_house",
                "ch_number": ch_number,
                "officer_count": 0,
                "fallback": "seeded_directors",
            },
        )
        seeded = await _seed_fallback_directors(db, company_id)
        return RefreshDirectorsResponse(
            directors=_public_directors(seeded), warning="ch_no_officers"
        )

    director_docs: list[dict] = []
    director_ids: list[str] = []
    for off in officers:
        # Stable id by ch_officer_id + company so re-runs are idempotent.
        if off.ch_officer_id:
            director_id = f"director_{company_id[:24]}_{off.ch_officer_id[:24]}"
        else:
            # Fall back to a deterministic hash of the raw name + role + appointed_on.
            tag = f"{off.name}|{off.role}|{off.appointed_on or ''}"
            tag_hash = uuid.uuid5(uuid.NAMESPACE_OID, tag).hex[:16]
            director_id = f"director_{company_id[:24]}_{tag_hash}"

        doc = {
            "_id": director_id,
            "company_id": company_id,
            "name": off.name,
            "name_display": off.name_display,
            "role": off.role,
            "appointed_on": off.appointed_on,
            "resigned_on": off.resigned_on,
            "ch_officer_id": off.ch_officer_id or None,
            "occupation": off.occupation,
            "nationality": off.nationality,
        }
        await db.directors.update_one(
            {"_id": director_id}, {"$set": doc}, upsert=True
        )
        director_docs.append(doc)
        director_ids.append(director_id)

    # Update parent company doc with the list of director ids.
    await db.companies.update_one(
        {"_id": company_id},
        {"$set": {"directors": director_ids}},
    )

    await log_audit(
        db,
        action="lead.refresh_directors",
        lead_id=lead_id,
        cost_cents=0,
        metadata={
            "provider": "companies_house",
            "ch_number": ch_number,
            "officer_count": len(officers),
        },
    )
    # Return slim view (no internal _ids etc., but include name_display/role).
    return RefreshDirectorsResponse(directors=_public_directors(director_docs))


# --- POST /lead/<id>/build_org ---

class BuildOrgResponse(BaseModel):
    decision_maker: dict


@router.post("/lead/{lead_id}/build_org", response_model=BuildOrgResponse)
async def build_org(
    lead_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> BuildOrgResponse:
    """Real Opus 4.7 decision-maker inference; soft-fails to stub on error."""
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    # Pull directors for this lead's company (if any)
    directors: list[dict[str, Any]] = []
    company_id = (lead.get("owner") or {}).get("company_id")
    if company_id:
        async for d in db.directors.find({"company_id": company_id}):
            directors.append(d)

    decision_maker: dict[str, Any]
    cost_cents = 0
    used_real = False
    err_msg: str | None = None

    try:
        from codex_brain.anthropic_client import AnthropicClient
        from codex_brain.generators.org_chart import infer_decision_maker

        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY missing")

        client = AnthropicClient(api_key=settings.anthropic_api_key)
        result = await infer_decision_maker(directors, lead, client)
        decision_maker = {
            "name": result.name,
            "role": result.role,
            "confidence": result.confidence,
            "rationale": result.rationale,
        }
        # Opus is the priciest path; fixed estimate when DecisionMaker doesn't expose cost.
        cost_cents = int(getattr(result, "cost_cents", 5))
        used_real = True
    except Exception as e:  # noqa: BLE001
        err_msg = str(e)
        log.warning("real build_org failed, falling back to stub: %s", e)
        decision_maker = {
            "name": "Sarah Patel",
            "role": "CFO",
            "confidence": 0.78,
            "rationale": "Stub fallback — real Opus inference unavailable.",
        }

    await log_audit(
        db,
        action="lead.build_org",
        lead_id=lead_id,
        cost_cents=cost_cents,
        metadata={"stub": not used_real, "error": err_msg, "directors_count": len(directors)},
    )
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
    settings: Settings = Depends(get_app_settings),
):
    """Real codex-driven pitch generation: Sonnet 4.6 → JSON spec → PPTX → PDF."""
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    # Look up client config for branding
    client_doc = await db.clients.find_one({"_id": body.client_id}) or {}
    decision_maker = lead.get("decision_maker") or {
        "name": "Decision Maker",
        "role": "Director",
        "confidence": 0.5,
        "rationale": "default — call /build_org to refine",
    }

    pitch_id = f"pitch_{uuid.uuid4()}"

    # Real Anthropic deck generation — soft-fail to stub on any error
    deck_json: dict[str, Any] = {}
    emails: dict[str, str] = {}
    cost_cents_total = 0
    pptx_url: str | None = None
    pdf_url: str | None = None
    pptx_s3_url: str | None = None
    pdf_s3_url: str | None = None
    used_real = False
    err_msg: str | None = None

    try:
        from codex_brain.anthropic_client import AnthropicClient
        from codex_brain.generators.deck import generate_deck
        from codex_brain.generators.email import generate_email_variants
        from codex_brain.generators.pptx_renderer import render_pptx
        from codex_brain.generators.pdf_converter import pptx_to_pdf

        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY missing")

        client = AnthropicClient(api_key=settings.anthropic_api_key)

        deck_result = await generate_deck(lead, client, decision_maker)
        deck_json = deck_result.deck_json
        cost_cents_total += int(deck_result.cost_cents)

        emails_obj = await generate_email_variants(
            lead, decision_maker, client, client_doc=client_doc
        )
        # Flatten {a:{subject,body}, b:{...}} → strings the frontend expects
        for k, v in emails_obj.items():
            if isinstance(v, dict):
                subj = v.get("subject", "")
                body_txt = v.get("body", "")
                emails[k] = f"Subject: {subj}\n\n{body_txt}".strip()
            else:
                emails[k] = str(v)

        # Render PPTX + PDF
        # client_doc.branding wins over the hardcoded fallback so each client's
        # palette actually shows through (otherwise every deck was blue/orange).
        brand = {"primary": "#1FB6FF", "accent": "#FFB020"} | (client_doc.get("branding") or {})
        pptx_path = render_pptx(
            deck_json,
            brand=brand,
            lead_id=pitch_id,
            out_dir="/tmp/decks",
            lead=lead,
            client_doc=client_doc,
        )
        pptx_url = f"/static/pitches/{pptx_path.name}"
        pdf_path = None
        try:
            pdf_path = pptx_to_pdf(pptx_path, out_dir="/tmp/decks")
            pdf_url = f"/static/pitches/{pdf_path.name}"
        except Exception as e:  # libreoffice may be missing locally
            log.warning("pdf conversion skipped: %s", e)

        # Upload to S3 if configured (graceful local fallback otherwise).
        # Keys are scoped per-lead so a re-run for the same lead replaces
        # rather than accumulates. The presigned URL TTL is 1 hour — the
        # frontend re-fetches the lead doc when needed and we re-sign on
        # demand via /lead/<id>/pitch.
        try:
            s3 = get_s3_storage()
            pptx_bytes = pptx_path.read_bytes()
            pptx_key = f"pitches/{lead_id}/{pitch_id}.pptx"
            pptx_res = await s3.put_object(
                pptx_key,
                pptx_bytes,
                content_type=(
                    "application/vnd.openxmlformats-officedocument."
                    "presentationml.presentation"
                ),
                local_path=pptx_path,
            )
            if pptx_res.uploaded:
                pptx_s3_url = pptx_res.url
            else:
                pptx_s3_url = None

            pdf_s3_url = None
            if pdf_path is not None:
                pdf_bytes = pdf_path.read_bytes()
                pdf_key = f"pitches/{lead_id}/{pitch_id}.pdf"
                pdf_res = await s3.put_object(
                    pdf_key,
                    pdf_bytes,
                    content_type="application/pdf",
                    local_path=pdf_path,
                )
                if pdf_res.uploaded:
                    pdf_s3_url = pdf_res.url
        except Exception as e:  # noqa: BLE001 — S3 must never block the pitch
            log.warning("s3 pitch upload failed (non-fatal): %s", e)
            pptx_s3_url = None
            pdf_s3_url = None
        used_real = True
    except Exception as e:  # noqa: BLE001
        err_msg = str(e)
        log.exception("real pitch failed, falling back to stub: %s", e)

    # Audit (real cost)
    await log_audit(
        db,
        action="lead.pitch",
        lead_id=lead_id,
        cost_cents=cost_cents_total,
        metadata={
            "client_id": body.client_id,
            "stub": not used_real,
            "error": err_msg,
            "model": "claude-sonnet-4-6" if used_real else None,
        },
    )

    # Fallback stub shape if real call failed (matches contract)
    if not used_real:
        deck_json = {
            "title": {"headline": "Solar proposal"},
            "slides": [
                {"title": "Why Solar, Why Now", "bullets": ["ROI", "ESG", "Resilience"]},
                {"title": "Your Building", "bullets": [lead.get("address", "")]},
            ],
        }
        emails = {
            "a": f"Subject: Solar partnership for {lead.get('owner', {}).get('company_name', 'your company')}\n\nHi {decision_maker.get('name', 'there')}, …",
            "b": "Subject: Cutting your energy bill\n\n…",
        }
        base = f"/static/pitches/{pitch_id}"
        pptx_url = f"{base}.pptx"
        pdf_url = f"{base}.pdf"

    payload = {
        "pptx_url": pptx_url,
        "pdf_url": pdf_url,
        # S3 URLs are presigned (1h TTL) when the upload succeeded, otherwise
        # None. The frontend prefers these over local /static/pitches URLs
        # because they survive a backend restart and aren't tied to the
        # demo machine's filesystem.
        "pptx_s3_url": pptx_s3_url,
        "pdf_s3_url": pdf_s3_url,
        "emails": emails,
        "deck_json": deck_json,
        "cost_cents": cost_cents_total,
        "used_real": used_real,
    }
    await db.leads.update_one({"_id": lead_id}, {"$set": {"pitch": payload}})
    return JSONResponse(payload)


# --- POST /lead/<id>/outreach ---


class OutreachRequest(BaseModel):
    client_id: str
    channel: str  # "email" | "linkedin" | "intro_call"


_VALID_OUTREACH_CHANNELS = {"email", "linkedin", "intro_call"}


@router.post("/lead/{lead_id}/outreach")
async def outreach(
    lead_id: str,
    body: OutreachRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    """Generate a tailored outreach message in the requested channel.

    Pulls the lead joined with company + decision_maker, calls Sonnet 4.6
    via the codex `outreach` generator, persists the result to
    `lead.outreach.<channel>` and audits the call. Soft-fails to a
    deterministic fallback on any LLM error so the demo flow never blocks.
    """
    if body.channel not in _VALID_OUTREACH_CHANNELS:
        raise HTTPException(
            400,
            f"channel must be one of {sorted(_VALID_OUTREACH_CHANNELS)}",
        )

    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    # Join company + directors so the generator has full context.
    lead = await _join_lead(db, lead)

    client_doc = await db.clients.find_one({"_id": body.client_id}) or {}
    decision_maker = lead.get("decision_maker") or {
        "name": "Decision Maker",
        "role": "Director",
        "confidence": 0.5,
        "rationale": "default — call /build_org to refine",
    }

    used_real = False
    err_msg: str | None = None
    cost_cents: float = 0.0
    subject: str = ""
    out_body: str = ""

    try:
        from codex_brain.anthropic_client import AnthropicClient
        from codex_brain.generators.outreach import generate_tailored_outreach

        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY missing")

        anthropic_client = AnthropicClient(api_key=settings.anthropic_api_key)
        result = await generate_tailored_outreach(
            lead,
            decision_maker,
            client_doc,
            body.channel,  # type: ignore[arg-type]
            anthropic_client=anthropic_client,
        )
        subject = str(result.get("subject") or "")
        out_body = str(result.get("body") or "")
        cost_cents = float(result.get("cost_cents") or 0.0)
        used_real = True
    except Exception as e:  # noqa: BLE001 — never crash the demo flow
        err_msg = str(e)
        log.warning("real outreach failed, using fallback: %s", e)
        # Inline fallback that doesn't need a working Anthropic call
        from codex_brain.generators.outreach import _fallback_message  # type: ignore

        fb = _fallback_message(lead, decision_maker, body.channel)  # type: ignore[arg-type]
        subject = fb["subject"]
        out_body = fb["body"]

    payload = {
        "subject": subject,
        "body": out_body,
        "channel": body.channel,
        "cost_cents": cost_cents,
    }

    await log_audit(
        db,
        action="lead.outreach",
        lead_id=lead_id,
        cost_cents=int(round(cost_cents)),
        metadata={
            "client_id": body.client_id,
            "channel": body.channel,
            "stub": not used_real,
            "error": err_msg,
            "model": "claude-sonnet-4-6" if used_real else None,
        },
    )

    # Persist per-channel so generating another channel doesn't clobber prior.
    await db.leads.update_one(
        {"_id": lead_id},
        {"$set": {f"outreach.{body.channel}": payload}},
    )
    return JSONResponse(payload)


@router.get("/lead/{lead_id}/pitch/download")
async def pitch_download(
    lead_id: str,
    format: str = Query(default="pdf", pattern="^(pdf|pptx)$"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Resolve `lead.pitch.{pdf_url,pptx_url}` (set by POST /lead/<id>/pitch)
    and stream the actual rendered file from disk.

    No stub fallback — if the file is missing, return 404 so callers know the
    pitch hasn't been generated (or the real renderer failed for that lead).
    """
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise HTTPException(404, "lead not found")

    pitch = lead.get("pitch") or {}
    url_key = "pdf_url" if format == "pdf" else "pptx_url"
    url = pitch.get(url_key)
    if not url:
        raise HTTPException(
            404,
            f"no {format} pitch generated for this lead — call POST /lead/{lead_id}/pitch first",
        )

    # Map persisted URL → filesystem path. URLs look like `/static/pitches/<name>`
    # and map to the StaticFiles mount in main.py (default /tmp/decks). We trust
    # the URL we wrote ourselves; resolve relative to the mount root and reject
    # anything that escapes it.
    pitches_url_prefix = "/static/pitches/"
    if not url.startswith(pitches_url_prefix):
        raise HTTPException(404, f"unrecognised pitch url: {url}")
    filename = url[len(pitches_url_prefix):]
    pitches_root = Path(os.environ.get("SOLARREACH_PITCHES_DIR", "/tmp/decks"))
    fpath = (pitches_root / filename).resolve()
    # Path-traversal guard: refuse anything outside the pitches root.
    try:
        fpath.relative_to(pitches_root.resolve())
    except ValueError:
        raise HTTPException(404, "invalid pitch path")

    if not fpath.exists() or not fpath.is_file():
        raise HTTPException(
            404,
            f"pitch file missing on disk: {filename} — re-run POST /lead/{lead_id}/pitch",
        )

    return FileResponse(
        path=str(fpath),
        filename=fpath.name,
        media_type=(
            "application/pdf"
            if format == "pdf"
            else "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ),
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
