def test_financial_calculator_returns_breakdown(client):
    body = {
        "address": "1 Sample Rd",
        "annual_kwh": 4200,
        "premises_type": "residential",
    }
    r = client.post("/financial/calculator", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "capex_gbp" in data
    assert "annual_saving_gbp" in data
    assert "payback_years" in data
    assert "npv_25yr_gbp" in data
    assert data["capex_gbp"] > 0
