import httpx
import pytest
import respx

from app.services.companies_house import CH_BASE_URL


@pytest.mark.asyncio
async def test_get_lead_returns_full_doc(client, mock_db):
    await mock_db.leads.insert_one(
        {
            "_id": "lead_test1",
            "client_id": "client-greensolar-uk",
            "address": "1 Old St",
            "postcode": "EC1Y 8AF",
            "scores": {"composite_score": 74},
            "owner": {"company_id": "company_a", "company_name": "Acme Ltd"},
        }
    )
    await mock_db.companies.insert_one({"_id": "company_a", "name": "Acme Ltd", "directors": []})

    r = client.get("/lead/lead_test1")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["_id"] == "lead_test1"
    assert body["address"] == "1 Old St"
    assert "company" in body
    assert body["company"]["name"] == "Acme Ltd"


@pytest.mark.asyncio
async def test_spend_session_aggregates_audit_log(client, mock_db):
    await mock_db.audit_log.insert_many(
        [
            {"_id": "a1", "cost_cents": 5, "ts": "x"},
            {"_id": "a2", "cost_cents": 10, "ts": "x"},
        ]
    )
    r = client.get("/lead/spend/session")
    assert r.status_code == 200
    body = r.json()
    assert body["spent_cents"] == 15
    assert "budget_cents" in body
    assert "budget_pct" in body


@pytest.mark.asyncio
async def test_refresh_directors_no_company_returns_400(client, mock_db):
    await mock_db.leads.insert_one(
        {"_id": "lead_orphan", "owner": {"company_id": None}}
    )
    r = client.post("/lead/lead_orphan/refresh_directors")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_refresh_directors_no_ch_number_returns_warning(client, mock_db):
    await mock_db.leads.insert_one(
        {"_id": "lead_x", "owner": {"company_id": "company_x"}}
    )
    await mock_db.companies.insert_one(
        {"_id": "company_x", "name": "Acme Ltd", "ch_number": None, "directors": []}
    )
    r = client.post("/lead/lead_x/refresh_directors")
    assert r.status_code == 200
    body = r.json()
    assert body["directors"] == []
    assert body["warning"] == "no_companies_house_link"


@pytest.mark.asyncio
async def test_refresh_directors_live_upserts_directors(client, mock_db, monkeypatch):
    # Make the route think a CH key is configured.
    from app import config as cfg

    cfg.get_settings.cache_clear()
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "test_key_for_live_path")
    cfg.get_settings.cache_clear()

    await mock_db.leads.insert_one(
        {"_id": "lead_live", "owner": {"company_id": "company_live"}}
    )
    await mock_db.companies.insert_one(
        {"_id": "company_live", "name": "Acme Ltd", "ch_number": "00012345", "directors": []}
    )

    payload = {
        "items": [
            {
                "name": "PATEL, Sarah",
                "officer_role": "director",
                "appointed_on": "2018-04-01",
                "links": {"officer": {"appointments": "/officers/abc/appointments"}},
            },
            {
                "name": "JONES, Tom",
                "officer_role": "secretary",
                "appointed_on": "2019-01-15",
                "links": {"officer": {"appointments": "/officers/def/appointments"}},
            },
        ]
    }
    try:
        with respx.mock(base_url=CH_BASE_URL) as router:
            router.get("/company/00012345/officers").mock(
                return_value=httpx.Response(200, json=payload)
            )
            r = client.post("/lead/lead_live/refresh_directors")
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["directors"]) == 2
        assert body["directors"][0]["name_display"] == "Sarah Patel"
        assert body["directors"][0]["role"] == "DIRECTOR"
        # Mongo: directors collection upserted
        all_dirs = await mock_db.directors.find({}).to_list(length=10)
        assert len(all_dirs) == 2
        # Company doc updated with director ids
        co = await mock_db.companies.find_one({"_id": "company_live"})
        assert len(co["directors"]) == 2
    finally:
        monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)
        cfg.get_settings.cache_clear()
