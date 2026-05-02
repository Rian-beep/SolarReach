def test_admin_client_upserts(client):
    body = {
        "name": "GreenSolar UK",
        "branding": {"primary": "#0F172A", "logo_url": "https://x"},
        "pricing": {"panel_unit_gbp": 850, "install_per_kw_gbp": 180},
    }
    r = client.post("/admin/client/client-greensolar-uk", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["_id"] == "client-greensolar-uk"
    assert data["name"] == "GreenSolar UK"
