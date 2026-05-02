"""Tests for voice_pitch script generator."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock


class _FakeUsage:
    def __init__(self):
        self.input_tokens = 80
        self.output_tokens = 220
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 350


class _FakeBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _FakeResponse:
    def __init__(self, text: str):
        self.content = [_FakeBlock(text)]
        self.usage = _FakeUsage()


SAMPLE_VOICE_JSON = """```json
{
  "script": "Hello Sarah, this is a quick proposal from SolarReach for Old Street Holdings at 1 Old Street.",
  "est_seconds": 88,
  "rationale": "AIA fits a CFO frame."
}
```"""


def _lead():
    return {
        "_id": "lead_v1",
        "address": "1 Old Street, London EC1Y 8AF",
        "borough": "City of London",
        "premises_type": "office",
        "owner": {"company_name": "Old Street Holdings Ltd", "source": "ccod"},
        "financial": {
            "capex_gbp": 24500,
            "annual_saving_gbp": 3120,
            "payback_years": 7.8,
            "npv_25yr_gbp": 41200,
        },
    }


def _dm():
    return {"name": "Sarah Patel", "role": "CFO", "confidence": 0.92}


@pytest.mark.asyncio
async def test_generate_voice_pitch_returns_script_and_seconds():
    from codex_brain.anthropic_client import AnthropicClient
    from codex_brain.generators.voice_pitch import generate_voice_pitch

    client = AnthropicClient(api_key="sk-ant-fake-test-key-1234567890")
    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(
        return_value=_FakeResponse(SAMPLE_VOICE_JSON)
    )

    result = await generate_voice_pitch(_lead(), client, _dm())

    assert "SolarReach" in result.script
    assert result.est_seconds == 88
    assert result.cost_cents >= 0
    assert "AIA" in result.rationale or result.rationale  # non-empty


@pytest.mark.asyncio
async def test_generate_voice_pitch_uses_cached_system_prompt():
    """The system param must be sent as a list-of-blocks with cache_control,
    so subsequent calls hit the prompt cache and stay cheap."""
    from codex_brain.anthropic_client import AnthropicClient
    from codex_brain.generators.voice_pitch import generate_voice_pitch

    client = AnthropicClient(api_key="sk-ant-fake-test-key-1234567890")
    captured: dict = {}

    async def _capture(*args, **kwargs):
        captured.update(kwargs)
        return _FakeResponse(SAMPLE_VOICE_JSON)

    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(side_effect=_capture)
    await generate_voice_pitch(_lead(), client, _dm())

    sys_param = captured.get("system")
    assert isinstance(sys_param, list)
    assert sys_param[0].get("cache_control") == {"type": "ephemeral"}
    assert "voice pitch" in sys_param[0].get("text", "").lower()


@pytest.mark.asyncio
async def test_generate_voice_pitch_falls_back_when_model_fails():
    """A model exception must not break the route — return a deterministic
    lead-specific script with cost=0 and a sensible duration."""
    from codex_brain.anthropic_client import AnthropicClient
    from codex_brain.generators.voice_pitch import generate_voice_pitch

    client = AnthropicClient(api_key="sk-ant-fake-test-key-1234567890")
    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(side_effect=RuntimeError("boom"))

    result = await generate_voice_pitch(_lead(), client, _dm())

    # Fallback script must mention the building and the payback figure.
    assert "Old Street" in result.script
    assert "7.8" in result.script
    assert result.cost_cents == 0
    assert 30 <= result.est_seconds <= 180
    assert "fallback" in result.rationale.lower()


@pytest.mark.asyncio
async def test_generate_voice_pitch_estimates_seconds_from_word_count():
    """If the model omits est_seconds, derive it from script word count."""
    from codex_brain.anthropic_client import AnthropicClient
    from codex_brain.generators.voice_pitch import generate_voice_pitch

    client = AnthropicClient(api_key="sk-ant-fake-test-key-1234567890")
    # 165 wpm → ~165 words ≈ 60 seconds
    text = " ".join(["word"] * 165)
    payload = (
        '{"script": "' + text + '", "rationale": "x"}'
    )
    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(
        return_value=_FakeResponse(payload)
    )

    result = await generate_voice_pitch(_lead(), client, _dm())
    assert 55 <= result.est_seconds <= 65


def test_fallback_script_handles_missing_financial_block():
    from codex_brain.generators.voice_pitch import _fallback_script

    bare_lead = {"address": "10 South Place"}
    bare_dm = {"name": "Tom", "role": "Director"}
    s = _fallback_script(bare_lead, bare_dm)
    assert "Tom" in s
    assert "10 South Place" in s
    # Must NOT crash or emit "None pounds" when figures are absent.
    assert "None" not in s
    assert "competitive" in s or "meaningful" in s or "long-term" in s
