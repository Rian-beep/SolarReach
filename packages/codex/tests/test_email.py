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


def test_subject_expertise_block_empty_when_no_doc():
    from codex_brain.generators.email import _build_subject_expertise_block
    assert _build_subject_expertise_block(None) == ""
    assert _build_subject_expertise_block({}) == ""
    assert _build_subject_expertise_block({"unrelated": "x"}) == ""


def test_subject_expertise_block_includes_notes_and_product():
    from codex_brain.generators.email import _build_subject_expertise_block
    out = _build_subject_expertise_block(
        {
            "expertise_notes": "20-year track record on warehouse roof PV.",
            "product_description": "Tier-1 monocrystalline panels.",
            "product_features": ["MCS-certified", "Battery-ready"],
        }
    )
    assert "## Subject expertise" in out
    assert "20-year track record" in out
    assert "Tier-1 monocrystalline" in out
    assert "MCS-certified" in out
    assert "Battery-ready" in out


@pytest.mark.asyncio
async def test_generate_email_variants_splices_client_doc_into_system_prompt():
    """When `client_doc` is passed, the system prompt sent to the model
    must include the expertise block."""
    from codex_brain.generators.email import generate_email_variants
    from codex_brain.anthropic_client import AnthropicClient

    client = AnthropicClient(api_key="sk-ant-fake-1234567890")
    captured: dict = {}

    async def _capture(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse(SAMPLE_EMAIL_JSON)

    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(side_effect=_capture)

    lead = {"_id": "lead_y", "address": "2 St", "premises_type": "warehouse",
            "owner": {"company_name": "Y Ltd"},
            "financial": {"capex_gbp": 50000, "payback_years": 6.0, "npv_25yr_gbp": 80000}}
    dm = {"name": "Tom Jones", "role": "COO"}
    client_doc = {
        "expertise_notes": "30-year warehouse PV specialist · regulated DNO.",
        "product_description": "On-site PPA with battery hybrid.",
        "product_features": ["No upfront capex", "20-year fixed rate"],
    }

    out = await generate_email_variants(lead, dm, client, client_doc=client_doc)
    assert "a" in out and "b" in out

    # The client doc should have been spliced into the system parameter.
    system_arg = captured.get("system")
    assert system_arg is not None
    if isinstance(system_arg, list):
        # Anthropic SDK accepts list-of-blocks; concat the text fields.
        sys_text = "\n".join(
            block.get("text", "") for block in system_arg if isinstance(block, dict)
        )
    else:
        sys_text = str(system_arg)
    assert "Subject expertise" in sys_text
    assert "30-year warehouse PV specialist" in sys_text
    assert "On-site PPA with battery hybrid" in sys_text


@pytest.mark.asyncio
async def test_generate_email_variants_no_doc_unchanged_prompt():
    """No client_doc means no extra system text appended."""
    from codex_brain.generators.email import generate_email_variants
    from codex_brain.anthropic_client import AnthropicClient

    client = AnthropicClient(api_key="sk-ant-fake-1234567890")
    captured: dict = {}

    async def _capture(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse(SAMPLE_EMAIL_JSON)

    client._client = AsyncMock()
    client._client.messages.create = AsyncMock(side_effect=_capture)

    lead = {"_id": "lead_z", "address": "3 St", "premises_type": "office",
            "owner": {"company_name": "Z Ltd"},
            "financial": {"capex_gbp": 25000, "payback_years": 7.5, "npv_25yr_gbp": 40000}}
    dm = {"name": "Sarah Patel", "role": "CFO"}
    await generate_email_variants(lead, dm, client)

    system_arg = captured.get("system")
    assert system_arg is not None
    if isinstance(system_arg, list):
        sys_text = "\n".join(
            block.get("text", "") for block in system_arg if isinstance(block, dict)
        )
    else:
        sys_text = str(system_arg)
    assert "Subject expertise" not in sys_text
