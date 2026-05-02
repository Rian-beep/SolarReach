"""Companies House async client (UK government registry).

Free + unlimited but rate-limited (600 requests / 5 min). HTTP Basic auth: API
key as username, blank password — NOT a Bearer header. Officer names come back
formatted as "LASTNAME, Firstname" — we split + reverse for display.

Cardinal rules (CONTRACTS § 7):
- never log the API key
- audit every call (cost_cents=0 since CH is free)
- 0.6s sleep between requests to honour the rate limit

Usage:
    from app.services.companies_house import CompaniesHouseClient
    async with CompaniesHouseClient(api_key) as ch:
        results = await ch.search_company("Barclays")
        officers = await ch.get_officers("00048839")
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

import httpx
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.audit import log_audit

log = logging.getLogger("solarreach.api.ch")

CH_BASE_URL = "https://api.company-information.service.gov.uk"
RATE_LIMIT_SLEEP_S = 0.6  # 600 req / 5 min ≈ 1 every 0.5s; 0.6 gives headroom
DEFAULT_TIMEOUT_S = 10.0


# ---------- DTOs ---------- #

@dataclass
class CompanyResult:
    """One hit from /search/companies."""

    ch_number: str
    title: str
    company_status: str | None = None
    address_snippet: str | None = None
    company_type: str | None = None
    date_of_creation: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompanyDetail:
    """One hit from /company/<ch_number>."""

    ch_number: str
    name: str
    status: str | None = None
    registered_address: str | None = None
    company_type: str | None = None
    date_of_creation: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class Officer:
    """One officer from /company/<ch_number>/officers.

    `name` is the raw "LASTNAME, Firstname" form CH returns.
    `name_display` is "Firstname LASTNAME" (split + reversed) for human display.
    """

    ch_officer_id: str  # parsed from `links.officer.appointments`
    name: str
    name_display: str
    role: str
    appointed_on: str | None = None
    resigned_on: str | None = None
    nationality: str | None = None
    occupation: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


# ---------- helpers ---------- #

def _format_name_display(raw_name: str) -> str:
    """Convert "PATEL, Sarah" -> "Sarah Patel".

    If no comma is present (rare — corporate officers, sometimes), return the
    original string with title-cased trailing portion preserved.
    """
    if "," in raw_name:
        last, _, first = raw_name.partition(",")
        first = first.strip()
        last = last.strip().title()  # "PATEL" -> "Patel"
        if first and last:
            return f"{first} {last}"
        if first:
            return first
        return last
    return raw_name.strip()


def _extract_officer_id(item: dict[str, Any]) -> str:
    """Pull officer id from `links.officer.appointments` like
    `/officers/<id>/appointments`."""
    links = item.get("links") or {}
    officer_link = ((links.get("officer") or {}).get("appointments")) or ""
    if "/officers/" in officer_link:
        return officer_link.split("/officers/")[1].split("/")[0]
    return item.get("officer_id") or ""


def _mask_key(key: str | None) -> str:
    """Mask an API key to last 4 chars for safe logging."""
    if not key:
        return "<none>"
    if len(key) <= 4:
        return "***"
    return f"***{key[-4:]}"


# ---------- client ---------- #

class CompaniesHouseClient:
    """Async Companies House client.

    Use as `async with` (preferred) or call `aclose()` manually.

    Pass `db` to enable per-call audit logging. Without `db` calls just hit
    the network — the live router endpoints always pass it.
    """

    def __init__(
        self,
        api_key: str,
        *,
        db: AsyncIOMotorDatabase | None = None,
        actor: str = "system",
        timeout_s: float = DEFAULT_TIMEOUT_S,
        sleep_s: float = RATE_LIMIT_SLEEP_S,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("Companies House API key is required")
        self._api_key = api_key
        self._db = db
        self._actor = actor
        self._sleep_s = sleep_s
        self._auth = httpx.BasicAuth(api_key, "")
        # If caller injects a client (tests via respx), reuse it.
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=CH_BASE_URL,
            timeout=timeout_s,
            auth=self._auth,
        )
        self._last_request_at: float | None = None

    async def __aenter__(self) -> "CompaniesHouseClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    # ---------- public API ---------- #

    async def search_company(self, name: str, limit: int = 5) -> list[CompanyResult]:
        if not name or not name.strip():
            return []
        params = {"q": name.strip(), "items_per_page": int(limit)}
        data = await self._get("/search/companies", params=params, action="ch.search")
        items = data.get("items") or []
        results: list[CompanyResult] = []
        for it in items:
            ch_no = (it.get("company_number") or "").strip()
            if not ch_no:
                continue
            results.append(
                CompanyResult(
                    ch_number=ch_no,
                    title=(it.get("title") or "").strip(),
                    company_status=it.get("company_status"),
                    address_snippet=it.get("address_snippet"),
                    company_type=it.get("company_type"),
                    date_of_creation=it.get("date_of_creation"),
                    raw=it,
                )
            )
        return results

    async def get_company(self, ch_number: str) -> CompanyDetail | None:
        ch_number = (ch_number or "").strip()
        if not ch_number:
            return None
        data = await self._get(f"/company/{ch_number}", action="ch.company")
        if not data or "company_number" not in data:
            return None
        ra = data.get("registered_office_address") or {}
        addr = ", ".join(
            [
                str(v).strip()
                for v in (
                    ra.get("address_line_1"),
                    ra.get("address_line_2"),
                    ra.get("locality"),
                    ra.get("region"),
                    ra.get("postal_code"),
                )
                if v
            ]
        ) or None
        return CompanyDetail(
            ch_number=data.get("company_number") or ch_number,
            name=(data.get("company_name") or "").strip(),
            status=data.get("company_status"),
            registered_address=addr,
            company_type=data.get("type"),
            date_of_creation=data.get("date_of_creation"),
            raw=data,
        )

    async def get_officers(self, ch_number: str, limit: int = 20) -> list[Officer]:
        ch_number = (ch_number or "").strip()
        if not ch_number:
            return []
        params = {"items_per_page": int(limit)}
        data = await self._get(
            f"/company/{ch_number}/officers", params=params, action="ch.officers"
        )
        items = data.get("items") or []
        out: list[Officer] = []
        for it in items:
            raw_name = (it.get("name") or "").strip()
            if not raw_name:
                continue
            role = (it.get("officer_role") or "officer").upper().replace("-", " ")
            out.append(
                Officer(
                    ch_officer_id=_extract_officer_id(it),
                    name=raw_name,
                    name_display=_format_name_display(raw_name),
                    role=role,
                    appointed_on=it.get("appointed_on"),
                    resigned_on=it.get("resigned_on"),
                    nationality=it.get("nationality"),
                    occupation=it.get("occupation"),
                    raw=it,
                )
            )
        return out

    # ---------- internal ---------- #

    async def _respect_rate_limit(self) -> None:
        loop = asyncio.get_event_loop()
        now = loop.time()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            if elapsed < self._sleep_s:
                await asyncio.sleep(self._sleep_s - elapsed)
        self._last_request_at = loop.time()

    async def _get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        action: str = "ch.call",
    ) -> dict[str, Any]:
        await self._respect_rate_limit()
        try:
            resp = await self._client.get(path, params=params)
        except httpx.HTTPError as e:
            # Mask any potential leak. Never include url with auth.
            log.warning("CH request failed key=%s path=%s err=%s",
                        _mask_key(self._api_key), path, type(e).__name__)
            await self._audit(action, status=0, path=path, error=type(e).__name__)
            raise

        await self._audit(action, status=resp.status_code, path=path)

        if resp.status_code == 404:
            return {}
        if resp.status_code == 401:
            # Auth issue — do NOT echo the key back.
            raise PermissionError(
                f"Companies House: 401 unauthorised (key={_mask_key(self._api_key)})"
            )
        if resp.status_code == 429:
            raise RuntimeError("Companies House: 429 rate limited")
        if resp.status_code >= 400:
            raise RuntimeError(f"Companies House: {resp.status_code} {path}")
        return resp.json() if resp.content else {}

    async def _audit(
        self,
        action: str,
        *,
        status: int,
        path: str,
        error: str | None = None,
    ) -> None:
        if self._db is None:
            return
        try:
            await log_audit(
                self._db,
                action=action,
                cost_cents=0,  # CH is free
                actor=self._actor,
                metadata={
                    "provider": "companies_house",
                    "path": path,
                    "status": status,
                    "error": error,
                },
            )
        except Exception as e:  # noqa: BLE001 — audit must never break the call
            log.warning("audit_log write failed: %s", type(e).__name__)


__all__ = [
    "CompaniesHouseClient",
    "CompanyResult",
    "CompanyDetail",
    "Officer",
]
