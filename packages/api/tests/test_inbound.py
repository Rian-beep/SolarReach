def test_inbound_lead_captures(client):
    body = {
        "address": "12 Sample Rd, London EC1Y 8AF",
        "postcode": "EC1Y 8AF",
        "annual_kwh": 4200,
        "email": "lead@example.com",
        "premises_type": "residential",
    }
    r = client.post("/inbound/lead", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["_id"].startswith("lead_")
    assert data["postcode"] == "EC1Y 8AF"
    assert "financial" in data
    # Email must NOT be stored as plaintext anywhere visible.
    assert "lead@example.com" not in str(data)
