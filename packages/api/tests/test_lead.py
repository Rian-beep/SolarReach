import httpx
import pytest
import respx

from app.services.companies_house import CH_BASE_URL


@pytest.mark.asyncio
async def test_pitch_download_404_when_no_pitch_generated(client, mock_db):
    """No pitch ever generated → 404, never an 8-byte stub."""
    await mock_db.leads.insert_one({"_id": "lead_nopitch"})
    r = client.get("/lead/lead_nopitch/pitch/download?format=pdf")
    assert r.status_code == 404
    assert "no pdf pitch" in r.text.lower() or "not generated" in r.text.lower() or "no pdf" in r.text.lower()


@pytest.mark.asyncio
async def test_pitch_download_serves_persisted_pdf(client, mock_db, tmp_path, monkeypatch):
    """`lead.pitch.pdf_url` resolves to disk and FileResponse streams it."""
    pitches_dir = tmp_path / "decks"
    pitches_dir.mkdir()
    real_pdf = pitches_dir / "pitch_abc.pdf"
    real_pdf.write_bytes(b"%PDF-1.7\nrealcontent\n%%EOF")
    monkeypatch.setenv("SOLARREACH_PITCHES_DIR", str(pitches_dir))

    await mock_db.leads.insert_one(
        {
            "_id": "lead_withpitch",
            "pitch": {
                "pdf_url": "/static/pitches/pitch_abc.pdf",
                "pptx_url": "/static/pitches/pitch_abc.pptx",
            },
        }
    )
    r = client.get("/lead/lead_withpitch/pitch/download?format=pdf")
    assert r.status_code == 200, r.text
    body = r.content
    # Must be the actual file, not the 8-byte stub.
    assert body.startswith(b"%PDF-1.7"), f"got: {body[:40]!r}"
    assert len(body) > 16


@pytest.mark.asyncio
async def test_pitch_download_404_when_url_set_but_file_missing(
    client, mock_db, tmp_path, monkeypatch
):
    """`lead.pitch.pdf_url` exists in Mongo but file gone from disk → 404."""
    pitches_dir = tmp_path / "decks"
    pitches_dir.mkdir()
    monkeypatch.setenv("SOLARREACH_PITCHES_DIR", str(pitches_dir))

    await mock_db.leads.insert_one(
        {
            "_id": "lead_ghostpitch",
            "pitch": {"pdf_url": "/static/pitches/missing.pdf"},
        }
    )
    r = client.get("/lead/lead_ghostpitch/pitch/download?format=pdf")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_pitch_download_rejects_path_traversal(
    client, mock_db, tmp_path, monkeypatch
):
    """A persisted URL trying to escape the pitches root must 404, not leak files."""
    pitches_dir = tmp_path / "decks"
    pitches_dir.mkdir()
    monkeypatch.setenv("SOLARREACH_PITCHES_DIR", str(pitches_dir))

    await mock_db.leads.insert_one(
        {
            "_id": "lead_evil",
            "pitch": {"pdf_url": "/static/pitches/../../../etc/passwd"},
        }
    )
    r = client.get("/lead/lead_evil/pitch/download?format=pdf")
    assert r.status_code == 404


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
async def test_refresh_directors_ch_401_returns_seeded_fallback(
    client, mock_db, monkeypatch
):
    """CH key configured but rejected (stale 401) → return 200 with seeded
    fallback directors + warning, never 502."""
    from app import config as cfg

    cfg.get_settings.cache_clear()
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "stale_key_will_401")
    cfg.get_settings.cache_clear()

    await mock_db.leads.insert_one(
        {"_id": "lead_401", "owner": {"company_id": "company_401"}}
    )
    await mock_db.companies.insert_one(
        {"_id": "company_401", "name": "Acme Ltd", "ch_number": "00012345", "directors": []}
    )

    try:
        with respx.mock(base_url=CH_BASE_URL) as router:
            router.get("/company/00012345/officers").mock(
                return_value=httpx.Response(401, json={"error": "unauthorized"})
            )
            r = client.post("/lead/lead_401/refresh_directors")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["warning"] == "ch_unauthorised"
        assert len(body["directors"]) >= 1
        assert "name_display" in body["directors"][0]
        # Fallback directors must be persisted to mongo.
        co = await mock_db.companies.find_one({"_id": "company_401"})
        assert len(co["directors"]) >= 1
    finally:
        monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)
        cfg.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_refresh_directors_ch_5xx_returns_seeded_fallback(
    client, mock_db, monkeypatch
):
    """CH service down (5xx) → seed fallback, return 200, never crash demo."""
    from app import config as cfg

    cfg.get_settings.cache_clear()
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "k")
    cfg.get_settings.cache_clear()

    await mock_db.leads.insert_one(
        {"_id": "lead_5xx", "owner": {"company_id": "company_5xx"}}
    )
    await mock_db.companies.insert_one(
        {"_id": "company_5xx", "name": "Acme", "ch_number": "00099999", "directors": []}
    )

    try:
        with respx.mock(base_url=CH_BASE_URL) as router:
            router.get("/company/00099999/officers").mock(
                return_value=httpx.Response(503, json={"error": "down"})
            )
            r = client.post("/lead/lead_5xx/refresh_directors")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["warning"] == "ch_unavailable"
        assert len(body["directors"]) >= 1
    finally:
        monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)
        cfg.get_settings.cache_clear()


@pytest.mark.asyncio
async def test_refresh_directors_search_by_name_when_no_ch_number(
    client, mock_db, monkeypatch
):
    """Company has no ch_number → search-by-name resolves it, then fetches officers."""
    from app import config as cfg

    cfg.get_settings.cache_clear()
    monkeypatch.setenv("COMPANIES_HOUSE_API_KEY", "k")
    cfg.get_settings.cache_clear()

    await mock_db.leads.insert_one(
        {
            "_id": "lead_search",
            "owner": {"company_id": "company_search", "company_name": "Acme Ltd"},
        }
    )
    await mock_db.companies.insert_one(
        {"_id": "company_search", "name": "Acme Ltd", "ch_number": None, "directors": []}
    )

    search_payload = {
        "items": [
            {"company_number": "00077777", "title": "ACME LTD", "company_status": "active"}
        ]
    }
    officers_payload = {
        "items": [
            {
                "name": "PATEL, Sarah",
                "officer_role": "director",
                "appointed_on": "2018-04-01",
                "links": {"officer": {"appointments": "/officers/abc/appointments"}},
            }
        ]
    }

    try:
        with respx.mock(base_url=CH_BASE_URL) as router:
            router.get("/search/companies").mock(
                return_value=httpx.Response(200, json=search_payload)
            )
            router.get("/company/00077777/officers").mock(
                return_value=httpx.Response(200, json=officers_payload)
            )
            r = client.post("/lead/lead_search/refresh_directors")
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("warning") is None
        assert len(body["directors"]) == 1
        assert body["directors"][0]["name_display"] == "Sarah Patel"
        # ch_number was persisted on the company doc.
        co = await mock_db.companies.find_one({"_id": "company_search"})
        assert co["ch_number"] == "00077777"
    finally:
        monkeypatch.delenv("COMPANIES_HOUSE_API_KEY", raising=False)
        cfg.get_settings.cache_clear()


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
