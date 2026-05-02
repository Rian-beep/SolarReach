def test_voice_signed_url_503_without_key(client, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    # Settings is cached; we need to clear cache so monkeypatch takes effect.
    from app.config import get_settings
    get_settings.cache_clear()
    r = client.get("/voice/signed-url?lead_id=lead_v1")
    assert r.status_code == 503
    assert "ELEVENLABS_API_KEY" in r.text or "elevenlabs" in r.text.lower()
