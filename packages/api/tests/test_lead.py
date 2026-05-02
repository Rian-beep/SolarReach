import pytest


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
