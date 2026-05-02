"""Companies House orchestration endpoints — keeps key server-side.

Companies House uses HTTP Basic auth with the key as the username and an
empty password. We never expose the key to the browser.

POST endpoints (spec'd in CONTRACTS § 2 + agent A7 brief):
  POST /realapi/companies-house/search    body {name}        -> top-5 results
  POST /realapi/companies-house/officers  body {ch_number}   -> officer list

Legacy GET endpoints kept for back-compat with frontend already using them:
  GET  /realapi/ch/company/<ch_number>
  GET  /realapi/ch/officers/<ch_number>
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel

from app.config import Settings
from app.deps import get_app_settings, get_db
from app.services.companies_house import CompaniesHouseClient

router = APIRouter()


# --- Request bodies ---

class CHSearchRequest(BaseModel):
    name: str
    limit: int = 5


class CHOfficersRequest(BaseModel):
    ch_number: str


# --- POST /realapi/companies-house/search ---

@router.post("/realapi/companies-house/search")
async def companies_house_search(
    body: CHSearchRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    if not settings.companies_house_api_key:
        raise HTTPException(503, "COMPANIES_HOUSE_API_KEY not configured.")
    if not body.name or not body.name.strip():
        raise HTTPException(400, "name is required")
    async with CompaniesHouseClient(
        settings.companies_house_api_key, db=db, actor="agent_a7_search"
    ) as ch:
        results = await ch.search_company(body.name, limit=body.limit)
    return {"results": [asdict(r) for r in results]}


# --- POST /realapi/companies-house/officers ---

@router.post("/realapi/companies-house/officers")
async def companies_house_officers(
    body: CHOfficersRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    if not settings.companies_house_api_key:
        raise HTTPException(503, "COMPANIES_HOUSE_API_KEY not configured.")
    if not body.ch_number or not body.ch_number.strip():
        raise HTTPException(400, "ch_number is required")
    async with CompaniesHouseClient(
        settings.companies_house_api_key, db=db, actor="agent_a7_officers"
    ) as ch:
        officers = await ch.get_officers(body.ch_number)
    return {"officers": [asdict(o) for o in officers]}


# --- POST /realapi/companies-house/company ---

@router.post("/realapi/companies-house/company")
async def companies_house_company(
    body: CHOfficersRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    """Fetch full company profile (POST variant for symmetry)."""
    if not settings.companies_house_api_key:
        raise HTTPException(503, "COMPANIES_HOUSE_API_KEY not configured.")
    if not body.ch_number or not body.ch_number.strip():
        raise HTTPException(400, "ch_number is required")
    async with CompaniesHouseClient(
        settings.companies_house_api_key, db=db, actor="agent_a7_company"
    ) as ch:
        detail = await ch.get_company(body.ch_number)
    if detail is None:
        raise HTTPException(404, "company not found")
    return {"company": asdict(detail)}


# --- Legacy GET endpoints (keep for back-compat) ---

@router.get("/realapi/ch/company/{ch_number}")
async def ch_company(
    ch_number: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    if not settings.companies_house_api_key:
        raise HTTPException(503, "COMPANIES_HOUSE_API_KEY not configured.")
    async with CompaniesHouseClient(
        settings.companies_house_api_key, db=db, actor="agent_a7_company"
    ) as ch:
        detail = await ch.get_company(ch_number)
    if detail is None:
        raise HTTPException(404, "company not found")
    return detail.raw  # raw payload for back-compat


@router.get("/realapi/ch/officers/{ch_number}")
async def ch_officers(
    ch_number: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
):
    if not settings.companies_house_api_key:
        raise HTTPException(503, "COMPANIES_HOUSE_API_KEY not configured.")
    async with CompaniesHouseClient(
        settings.companies_house_api_key, db=db, actor="agent_a7_officers"
    ) as ch:
        officers = await ch.get_officers(ch_number)
    return {"items": [o.raw for o in officers]}
