"""Voice router + provider tests.

The /voice/signed-url endpoint is intentionally lenient: any non-404 outcome
returns 200 with a `status` field describing the demo/error mode. The UI
relies on that contract to render the "voice integration pending" pill
rather than an error toast.
"""
from __future__ import annotations

import pytest

# ─── Lead fixture ─────────────────────────────────────────────────────────────


@pytest.fixture
def seeded_lead(client, mock_db):
    """Insert a minimal lead so /voice/signed-url passes the 404 gate."""
    import asyncio

    async def _seed():
        await mock_db.leads.insert_one(
            {
                "_id": "lead_v1",
                "client_id": "client-greensolar-uk",
                "address": "1 Old St, London EC1Y 8AF",
                "owner": {"company_name": "Old Street Holdings Ltd"},
            }
        )

    asyncio.get_event_loop().run_until_complete(_seed())
    yield "lead_v1"


# ─── Router tests ─────────────────────────────────────────────────────────────


def test_voice_signed_url_404_for_unknown_lead(client):
    r = client.get("/voice/signed-url?lead_id=does_not_exist")
    assert r.status_code == 404


def test_voice_signed_url_demo_mode_without_key(client, monkeypatch, seeded_lead):
    """No ELEVENLABS_API_KEY → 200 + status=demo_mode (NOT 502/503)."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    monkeypatch.setenv("VOICE_PROVIDER", "elevenlabs")
    from app.config import get_settings

    get_settings.cache_clear()

    r = client.get(f"/voice/signed-url?lead_id={seeded_lead}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["signed_url"] is None
    assert body["status"] == "demo_mode"
    assert "rotate" in body["message"].lower() or "configured" in body["message"].lower()
    assert body["provider"] == "elevenlabs"


def test_voice_signed_url_rian_provider_returns_demo_mode(
    client, monkeypatch, seeded_lead
):
    """Rian's provider is a stub until the lib lands — should always 200."""
    monkeypatch.setenv("VOICE_PROVIDER", "rian")
    from app.config import get_settings

    get_settings.cache_clear()

    r = client.get(f"/voice/signed-url?lead_id={seeded_lead}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "demo_mode"
    assert body["provider"] == "rian"
    assert "pending" in body["message"].lower() or "teammate" in body["message"].lower()


def test_voice_disclosure_check_finds_repo_root_agent_system_md():
    """The hackathon build keeps `agent_system.md` at the repo root.
    The disclosure probe must find it there — otherwise a real ElevenLabs
    call would degrade to `disclosure_pending`.
    """
    from app.routers.voice import _ai_disclosure_ok

    ok, reason = _ai_disclosure_ok()
    assert ok, f"disclosure check failed despite repo-root agent_system.md present: {reason}"
    from pathlib import Path

    assert Path(reason).exists(), reason


# ─── Provider unit tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_elevenlabs_provider_demo_mode_when_key_missing():
    from app.config import Settings
    from app.services.voice_provider import ElevenLabsProvider

    settings = Settings(elevenlabs_api_key="", elevenlabs_agent_id="agent_x")
    result = await ElevenLabsProvider().get_signed_url(
        lead={"_id": "lead_x", "owner": {"company_name": "Foo Ltd"}, "address": "1 St"},
        settings=settings,
    )
    assert result.status == "demo_mode"
    assert result.signed_url is None
    assert "Foo Ltd" in result.system_prompt_filled


@pytest.mark.asyncio
async def test_rian_provider_is_stubbed():
    from app.config import Settings
    from app.services.voice_provider import RianProjectVoiceProvider

    result = await RianProjectVoiceProvider().get_signed_url(
        lead={"_id": "lead_x", "owner": {"company_name": "Foo Ltd"}, "address": "1 St"},
        settings=Settings(),
    )
    assert result.status == "demo_mode"
    assert result.metadata.get("stub") is True


def test_get_provider_falls_back_on_unknown_name(monkeypatch):
    from app.services.voice_provider import ElevenLabsProvider, get_provider

    monkeypatch.setenv("VOICE_PROVIDER", "totally-unknown")
    p = get_provider()
    assert isinstance(p, ElevenLabsProvider)


def test_get_provider_explicit_arg_wins(monkeypatch):
    from app.services.voice_provider import RianProjectVoiceProvider, get_provider

    monkeypatch.setenv("VOICE_PROVIDER", "elevenlabs")
    p = get_provider("rian")
    assert isinstance(p, RianProjectVoiceProvider)


# ─── /voice/pitch_audio ───────────────────────────────────────────────────────


def test_voice_pitch_audio_404_for_unknown_lead(client):
    r = client.post("/voice/pitch_audio", json={"lead_id": "does_not_exist"})
    assert r.status_code == 404


def test_voice_pitch_audio_demo_mode_without_elevenlabs_key(
    client, monkeypatch, seeded_lead
):
    """No ELEVENLABS_API_KEY → 200 + status=demo_mode + script populated.

    The Anthropic key is also empty in the test env, so the script comes from
    the deterministic fallback inside generate_voice_pitch.
    """
    monkeypatch.setenv("ELEVENLABS_API_KEY", "")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    r = client.post("/voice/pitch_audio", json={"lead_id": seeded_lead})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "demo_mode"
    assert body["audio_url"] is None
    # Fallback script is still useful — must mention the building.
    assert "Old Street" in body["script"]
    assert body["duration_sec"] > 0


def test_voice_pitch_audio_writes_mp3_when_tts_succeeds(
    client, monkeypatch, seeded_lead, tmp_path
):
    """With a fake ElevenLabs response, the route should write an mp3 file
    under /tmp/swarm-tts and return a /static/swarm/tts/* URL."""
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    fake_mp3 = b"ID3\x03" + b"\x00" * 1024  # not real audio, but non-empty bytes

    async def _fake_synth(*, text, voice_id, api_key, out_path, timeout=60.0):
        from pathlib import Path

        Path(out_path).write_bytes(fake_mp3)
        return True, "", len(fake_mp3)

    from app.routers import voice as voice_router

    monkeypatch.setattr(voice_router, "_synthesize_tts", _fake_synth)

    r = client.post("/voice/pitch_audio", json={"lead_id": seeded_lead})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ok"
    assert body["audio_url"] == f"/static/swarm/tts/pitch_{seeded_lead}.mp3"
    assert body["script"]
    assert body["duration_sec"] > 0
    assert body["cost_cents"] >= 25  # at minimum the TTS line item

    from pathlib import Path

    assert Path(f"/tmp/swarm-tts/pitch_{seeded_lead}.mp3").exists()


def test_voice_pitch_audio_upstream_error_when_tts_fails(
    client, monkeypatch, seeded_lead
):
    monkeypatch.setenv("ELEVENLABS_API_KEY", "fake-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    from app.config import get_settings

    get_settings.cache_clear()

    async def _fake_synth(**_kwargs):
        return False, "tts_http_401:bad key", 0

    from app.routers import voice as voice_router

    monkeypatch.setattr(voice_router, "_synthesize_tts", _fake_synth)

    r = client.post("/voice/pitch_audio", json={"lead_id": seeded_lead})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "upstream_error"
    assert body["audio_url"] is None
    assert "401" in body["message"]
    # Script is still returned so the UI can show the rehearsal text.
    assert body["script"]
