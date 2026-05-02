def test_voice_signed_url_503_without_key(client, monkeypatch):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    # Settings is cached; we need to clear cache so monkeypatch takes effect.
    from app.config import get_settings
    get_settings.cache_clear()
    r = client.get("/voice/signed-url?lead_id=lead_v1")
    assert r.status_code == 503
    assert "ELEVENLABS_API_KEY" in r.text or "elevenlabs" in r.text.lower()


def test_voice_disclosure_check_finds_repo_root_agent_system_md():
    """The hackathon build keeps `agent_system.md` at the repo root.
    The disclosure probe must find it there — otherwise /voice/signed-url
    returns 503 and kills the demo's Voice tab.
    """
    from app.routers.voice import _ai_disclosure_ok

    ok, reason = _ai_disclosure_ok()
    assert ok, f"disclosure check failed despite repo-root agent_system.md present: {reason}"
    # Reason on success is the path that was matched — must be a real file.
    from pathlib import Path

    assert Path(reason).exists(), reason
