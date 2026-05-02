def test_health_returns_200(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert "status" in body
    assert "services" in body
    assert "mongo" in body["services"]
    assert "anthropic_reachable" in body["services"]
    assert "redis" in body["services"]


def test_health_services_are_bool(client):
    r = client.get("/health")
    body = r.json()
    # All probes must report a strict bool — frontend pill relies on this.
    for key in ("mongo", "anthropic_reachable", "redis"):
        assert isinstance(body["services"][key], bool), f"{key} must be bool"


def test_health_degrades_without_keys(client):
    r = client.get("/health")
    body = r.json()
    # No Anthropic key set → reachable should be falsy.
    assert body["services"]["anthropic_reachable"] is False
    assert body["status"] == "degraded"


def test_health_never_5xx_when_mongo_down(client, monkeypatch):
    """If the Mongo probe blows up, /health still returns 200 with mongo=False.
    Demo cardinal rule: the endpoint must never hang or 5xx.
    """
    from app.routers import health as health_module

    async def boom(_db):
        raise RuntimeError("simulated mongo outage")

    monkeypatch.setattr(health_module, "_probe_mongo", boom)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["services"]["mongo"] is False
    assert body["status"] == "degraded"
