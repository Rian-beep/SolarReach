import pytest


@pytest.mark.asyncio
async def test_flux_overlay_returns_mock_url(client, mock_db):
    await mock_db.leads.insert_one({"_id": "lead_f1", "address": "x", "postcode": "EC1Y 8AF"})
    r = client.post("/lead/lead_f1/flux_overlay")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["url"].endswith(".png")
    assert isinstance(body["bbox"], list) and len(body["bbox"]) == 4
    assert body["vmin"] < body["vmax"]


@pytest.mark.asyncio
async def test_panels_returns_grid(client, mock_db):
    await mock_db.leads.insert_one({"_id": "lead_p1", "address": "x", "postcode": "EC1Y 8AF"})
    r = client.post("/lead/lead_p1/panels")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["panel_count"] == 12
    assert len(body["panels"]) == 12
    assert body["annual_kwh"] > 0
    p0 = body["panels"][0]
    assert "corners" in p0 and len(p0["corners"]) == 4
