def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "services" in body
    assert "mongo" in body["services"]
    assert "anthropic_reachable" in body["services"]
    assert "redis" in body["services"]


def test_health_degrades_without_keys(client):
    r = client.get("/health")
    body = r.json()
    # No Anthropic key set → reachable should be falsy.
    assert body["services"]["anthropic_reachable"] is False
    assert body["status"] == "degraded"
