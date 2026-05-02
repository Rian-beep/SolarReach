"""Companies House proxy — keeps key server-side.

Companies House uses HTTP Basic auth with the key as the username and an
empty password. We never expose the key to the browser.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.config import Settings
from app.deps import get_app_settings

router = APIRouter()


@router.get("/realapi/ch/company/{ch_number}")
async def ch_company(
    ch_number: str,
    settings: Settings = Depends(get_app_settings),
):
    if not settings.companies_house_api_key:
        raise HTTPException(503, "COMPANIES_HOUSE_API_KEY not configured.")
    url = f"https://api.company-information.service.gov.uk/company/{ch_number}"
    async with httpx.AsyncClient(timeout=10.0) as cx:
        resp = await cx.get(url, auth=(settings.companies_house_api_key, ""))
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)
    return resp.json()


@router.get("/realapi/ch/officers/{ch_number}")
async def ch_officers(
    ch_number: str,
    settings: Settings = Depends(get_app_settings),
):
    if not settings.companies_house_api_key:
        raise HTTPException(503, "COMPANIES_HOUSE_API_KEY not configured.")
    url = f"https://api.company-information.service.gov.uk/company/{ch_number}/officers"
    async with httpx.AsyncClient(timeout=10.0) as cx:
        resp = await cx.get(url, auth=(settings.companies_house_api_key, ""))
    if resp.status_code != 200:
        raise HTTPException(resp.status_code, resp.text)
    return resp.json()
