def test_scan_creates_job_and_returns_stream_url(client):
    body = {
        "postcode": "EC1Y 8AF",
        "client_id": "client-greensolar-uk",
        "limit": 10,
    }
    r = client.post("/scan", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "scan_id" in data
    assert "lead_count" in data
    assert data["stream_url"] == f"/scan/{data['scan_id']}/stream"
