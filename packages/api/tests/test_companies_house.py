"""Tests for app.services.companies_house using respx-mocked HTTP.

Covers:
- search_company parsing
- get_officers parsing of "LAST, First" name format + role normalisation
- HTTP Basic auth header (key as user, blank password)
- Rate-limit sleep between consecutive calls (>= 0.6s)
- get_company parsing + 404 handling
- audit_log emitted with cost_cents=0 (free API)
"""
from __future__ import annotations

import asyncio
import base64
import time

import httpx
import pytest
import respx

from app.services.companies_house import (
    CH_BASE_URL,
    CompaniesHouseClient,
    _format_name_display,
)

API_KEY = "test_ch_key_12345"


def _expected_basic_header(key: str) -> str:
    token = base64.b64encode(f"{key}:".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


@pytest.mark.asyncio
async def test_search_company_parses_results():
    payload = {
        "items": [
            {
                "company_number": "00048839",
                "title": "BARCLAYS PLC",
                "company_status": "active",
                "address_snippet": "1 Churchill Place, London, E14 5HP",
                "company_type": "plc",
                "date_of_creation": "1896-07-20",
            },
            {
                "company_number": "01906991",
                "title": "BARCLAYS BANK PLC",
                "company_status": "active",
                "address_snippet": "1 Churchill Place, London",
            },
            # A row with no company_number — must be filtered out.
            {"title": "ORPHAN ENTRY"},
        ]
    }
    async with respx.mock(base_url=CH_BASE_URL) as router:
        route = router.get("/search/companies").mock(
            return_value=httpx.Response(200, json=payload)
        )
        async with CompaniesHouseClient(API_KEY) as ch:
            results = await ch.search_company("Barclays")

    assert len(results) == 2
    assert results[0].ch_number == "00048839"
    assert results[0].title == "BARCLAYS PLC"
    assert results[0].company_status == "active"
    # query string was passed
    assert route.calls.last.request.url.params["q"] == "Barclays"
    assert route.calls.last.request.url.params["items_per_page"] == "5"


@pytest.mark.asyncio
async def test_get_officers_parses_last_first_name_format():
    payload = {
        "items": [
            {
                "name": "PATEL, Sarah",
                "officer_role": "director",
                "appointed_on": "2018-04-01",
                "links": {"officer": {"appointments": "/officers/abc123/appointments"}},
            },
            {
                "name": "SMITH, John Henry",
                "officer_role": "llp-designated-member",
                "appointed_on": "2020-02-10",
                "links": {"officer": {"appointments": "/officers/xyz789/appointments"}},
            },
            # Corporate officer / no comma — must keep raw text gracefully.
            {
                "name": "CORPORATE NOMINEES LIMITED",
                "officer_role": "secretary",
                "links": {},
            },
            # Empty name — filtered.
            {"name": "", "officer_role": "director"},
        ]
    }
    async with respx.mock(base_url=CH_BASE_URL) as router:
        router.get("/company/00048839/officers").mock(
            return_value=httpx.Response(200, json=payload)
        )
        async with CompaniesHouseClient(API_KEY) as ch:
            officers = await ch.get_officers("00048839")

    assert len(officers) == 3
    # "PATEL, Sarah" -> name_display "Sarah Patel"
    assert officers[0].name == "PATEL, Sarah"
    assert officers[0].name_display == "Sarah Patel"
    assert officers[0].role == "DIRECTOR"
    assert officers[0].ch_officer_id == "abc123"
    assert officers[0].appointed_on == "2018-04-01"
    # Multi-token first name preserved
    assert officers[1].name_display == "John Henry Smith"
    # Hyphen in role normalised to space and uppercased
    assert officers[1].role == "LLP DESIGNATED MEMBER"
    # Corporate officer with no comma — keep raw text
    assert officers[2].name_display == "CORPORATE NOMINEES LIMITED"


@pytest.mark.asyncio
async def test_basic_auth_header_set_correctly():
    async with respx.mock(base_url=CH_BASE_URL) as router:
        route = router.get("/search/companies").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        async with CompaniesHouseClient(API_KEY) as ch:
            await ch.search_company("anything")

    assert route.called
    sent_auth = route.calls.last.request.headers.get("authorization")
    expected = _expected_basic_header(API_KEY)
    assert sent_auth == expected, f"expected {expected}, got {sent_auth}"


@pytest.mark.asyncio
async def test_rate_limit_sleep_between_consecutive_calls():
    async with respx.mock(base_url=CH_BASE_URL) as router:
        router.get("/search/companies").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        async with CompaniesHouseClient(API_KEY, sleep_s=0.5) as ch:
            t0 = time.monotonic()
            await ch.search_company("A")
            await ch.search_company("B")
            await ch.search_company("C")
            elapsed = time.monotonic() - t0

    # 3 calls with 0.5s sleep => first immediate, next two waited >=0.5s each.
    # Allow generous slack but require at least 0.9s (some asyncio scheduler jitter).
    assert elapsed >= 0.9, f"expected >=0.9s, got {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_get_company_parses_registered_address_and_404():
    payload = {
        "company_number": "00048839",
        "company_name": "BARCLAYS PLC",
        "company_status": "active",
        "type": "plc",
        "date_of_creation": "1896-07-20",
        "registered_office_address": {
            "address_line_1": "1 Churchill Place",
            "locality": "London",
            "postal_code": "E14 5HP",
        },
    }
    async with respx.mock(base_url=CH_BASE_URL) as router:
        router.get("/company/00048839").mock(
            return_value=httpx.Response(200, json=payload)
        )
        router.get("/company/missing").mock(return_value=httpx.Response(404, json={}))
        async with CompaniesHouseClient(API_KEY) as ch:
            detail = await ch.get_company("00048839")
            missing = await ch.get_company("missing")

    assert detail is not None
    assert detail.ch_number == "00048839"
    assert detail.name == "BARCLAYS PLC"
    assert "1 Churchill Place" in (detail.registered_address or "")
    assert "E14 5HP" in (detail.registered_address or "")
    assert missing is None


@pytest.mark.asyncio
async def test_audit_log_writes_cost_cents_zero(mock_db):
    async with respx.mock(base_url=CH_BASE_URL) as router:
        router.get("/search/companies").mock(
            return_value=httpx.Response(200, json={"items": []})
        )
        async with CompaniesHouseClient(API_KEY, db=mock_db) as ch:
            await ch.search_company("Barclays")

    docs = await mock_db.audit_log.find({}).to_list(length=5)
    assert len(docs) == 1
    d = docs[0]
    assert d["action"] == "ch.search"
    assert d["cost_cents"] == 0  # CH is free — cardinal rule
    assert d["metadata"]["provider"] == "companies_house"
    assert d["metadata"]["status"] == 200
    # API key must never appear in any audit doc.
    assert API_KEY not in str(d)


@pytest.mark.asyncio
async def test_format_name_display_unit_cases():
    assert _format_name_display("PATEL, Sarah") == "Sarah Patel"
    assert _format_name_display("SMITH, John Henry") == "John Henry Smith"
    assert _format_name_display("VAN DER BERG, Klaus") == "Klaus Van Der Berg"
    assert _format_name_display("CORPORATE NOMINEES LIMITED") == "CORPORATE NOMINEES LIMITED"
    assert _format_name_display("") == ""


@pytest.mark.asyncio
async def test_missing_api_key_raises():
    with pytest.raises(ValueError):
        CompaniesHouseClient("")
