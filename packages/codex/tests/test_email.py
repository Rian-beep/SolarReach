"""Tests for email A/B variant generator."""

import pytest
from unittest.mock import AsyncMock


class FakeUsage:
    def __init__(self):
        self.input_tokens = 50
        self.output_tokens = 100
        self.cache_read_input_tokens = 0
        self.cache_creation_input_tokens = 200


class FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, text):
        self.content = [FakeBlock(text)]
        self.usage = FakeUsage()


SAMPLE_EMAIL_JSON = """```json
{
  "a": {"subject": "10080 kWh, your roof", "body": "Hi Sarah,\\n\\nbody A\\n\\ncta"},
  "b": {"subject": "Bills won't get cheaper", "body": "Hi Sarah,\\n\\nbody B\\n\\ncta"}
}
```"""


@pytest.mark.asyncio
async def test_generate_email_variants_returns_a_and_b():
    from codex_brain.generators.email import generate_email_variants
    from codex_brain.anthropic_client import AnthropicClient
    client = AnthropicClient(api_key="sk-ant-fake-1234567890")
    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(return_value=FakeResponse(SAMPLE_EMAIL_JSON))

    lead = {"_id": "lead_x", "address": "1 St", "premises_type": "office",
            "owner": {"company_name": "X Ltd"},
            "financial": {"capex_gbp": 25000, "payback_years": 7.5, "npv_25yr_gbp": 40000}}
    dm = {"name": "Sarah Patel", "role": "CFO"}

    out = await generate_email_variants(lead, dm, client)
    assert "a" in out
    assert "b" in out
    assert out["a"]["subject"]
    assert out["b"]["subject"]
    assert out["a"]["subject"] != out["b"]["subject"]
