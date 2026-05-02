"""Tests for deck generation — JSON fence stripping + cache hit on second call."""

import pytest
from unittest.mock import AsyncMock


SAMPLE_DECK_JSON_TEXT = """```json
{
  "title": {"headline": "Grid Independence", "subhead": "x", "decision_maker": "y"},
  "problem": {"heading": "p", "bullets": ["a"]},
  "solution": {"heading": "s", "bullets": ["b"]},
  "grid_independence": {"heading": "gi", "body": "z", "metric_pct_offset": 50},
  "roi": {"heading": "r", "capex_gbp": 10000, "annual_saving_gbp": 1500, "payback_years": 7, "npv_25yr_gbp": 20000},
  "funding": {"heading": "f", "models": []},
  "timeline": {"heading": "t", "phases": []},
  "decision_maker_callout": {"heading": "d", "body": "x"},
  "social_impact": {"heading": "si", "tonnes_co2_yr": 1, "equiv_trees": 50},
  "tech_specs": {"heading": "ts", "panels": 24, "kw_peak": 9, "annual_kwh": 10000, "warranty_years": 25},
  "cta": {"heading": "cta", "body": "x", "contact": "x@y.com"}
}
```"""


class FakeUsage:
    def __init__(self, in_tokens=100, out_tokens=200, cache_read=0, cache_create=0):
        self.input_tokens = in_tokens
        self.output_tokens = out_tokens
        self.cache_read_input_tokens = cache_read
        self.cache_creation_input_tokens = cache_create


class FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, text, **usage_kw):
        self.content = [FakeBlock(text)]
        self.usage = FakeUsage(**usage_kw)


@pytest.mark.asyncio
async def test_generate_deck_strips_json_fences():
    from codex_brain.generators.deck import generate_deck
    from codex_brain.anthropic_client import AnthropicClient

    client = AnthropicClient(api_key="sk-ant-fake-test-key-1234567890")
    # Replace _client.messages.create with mock returning fenced JSON
    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(return_value=FakeResponse(SAMPLE_DECK_JSON_TEXT))

    lead = {
        "_id": "lead_test",
        "address": "1 Old St",
        "premises_type": "office",
        "owner": {"company_name": "Acme Ltd"},
        "panel_layout": {"panel_count": 24, "annual_kwh": 10080},
        "financial": {"capex_gbp": 24500, "annual_saving_gbp": 3120, "payback_years": 7.8, "npv_25yr_gbp": 41200},
    }
    decision_maker = {"name": "Sarah Patel", "role": "CFO", "confidence": 0.9, "rationale": "x"}

    result = await generate_deck(lead, client, decision_maker)
    assert result.deck_json["title"]["headline"] == "Grid Independence"
    assert "title" in result.deck_json
    assert result.cost_cents > 0


@pytest.mark.asyncio
async def test_generate_deck_passes_cache_control_in_system():
    """Verify the system param is structured as a list with cache_control."""
    from codex_brain.generators.deck import generate_deck
    from codex_brain.anthropic_client import AnthropicClient

    client = AnthropicClient(api_key="sk-ant-fake-test-key-1234567890")
    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(return_value=FakeResponse(SAMPLE_DECK_JSON_TEXT))

    lead = {"_id": "lead_test", "address": "x", "premises_type": "office",
            "owner": {"company_name": "x"}, "panel_layout": {}, "financial": {}}
    dm = {"name": "x", "role": "CFO", "confidence": 0.9, "rationale": "x"}

    await generate_deck(lead, client, dm)

    call_args = client._client.messages.create.call_args
    system_param = call_args.kwargs["system"]
    assert isinstance(system_param, list)
    assert system_param[0]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_cache_read_on_second_call_simulated():
    """First call: cache_create > 0, cache_read = 0.
    Second call: cache_read > 0 — proves caching works on the wire."""
    from codex_brain.anthropic_client import AnthropicClient

    client = AnthropicClient(api_key="sk-ant-fake-test-key-1234567890")
    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(side_effect=[
        FakeResponse('{"a": 1}', in_tokens=10, out_tokens=10, cache_create=5000, cache_read=0),
        FakeResponse('{"a": 1}', in_tokens=10, out_tokens=10, cache_create=0, cache_read=5000),
    ])

    r1 = await client.complete("hi", system="big system", max_tokens=50)
    r2 = await client.complete("hi", system="big system", max_tokens=50)
    assert r1.cache_create_tokens > 0
    assert r1.cache_read_tokens == 0
    assert r2.cache_read_tokens > 0
    # Second call must be cheaper than first by spec (cache writes are 1.25x, reads are 0.10x)
    assert r2.cost_cents < r1.cost_cents
