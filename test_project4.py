"""
Project 4 unit tests — Content AI
Run: pytest packages/codex/tests/ -v
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from codex_brain.anthropic_client import _strip_json_fences, UsageRecord, SONNET
from codex_brain.constants_funding import FUNDING_MODELS
from codex_brain.generators.org_chart import _reverse_ch_name, _format_directors


# ---------------------------------------------------------------------------
# anthropic_client helpers
# ---------------------------------------------------------------------------

class TestStripJsonFences:
    def test_clean_json_unchanged(self):
        raw = '{"a": 1}'
        assert _strip_json_fences(raw) == '{"a": 1}'

    def test_strips_json_fence(self):
        raw = '```json\n{"a": 1}\n```'
        result = _strip_json_fences(raw)
        assert result == '{"a": 1}'

    def test_strips_plain_fence(self):
        raw = '```\n{"a": 1}\n```'
        result = _strip_json_fences(raw)
        assert result == '{"a": 1}'

    def test_strips_whitespace(self):
        raw = '  \n{"a": 1}\n  '
        assert _strip_json_fences(raw) == '{"a": 1}'


class TestUsageRecord:
    def test_cost_calculation_sonnet(self):
        u = UsageRecord(
            model=SONNET,
            input_tokens=1_000_000,
            output_tokens=1_000_000,
        )
        # Sonnet: in=$3/M, out=$15/M → total $18 = 1800 cents
        assert abs(u.cost_cents - 1800.0) < 1.0

    def test_cost_with_cache_read(self):
        u = UsageRecord(
            model=SONNET,
            input_tokens=0,
            output_tokens=0,
            cache_read_tokens=1_000_000,
        )
        # cache read = $0.30/M = 30 cents
        assert abs(u.cost_cents - 30.0) < 0.5

    def test_zero_cost_zero_tokens(self):
        u = UsageRecord(model=SONNET, input_tokens=0, output_tokens=0)
        assert u.cost_cents == 0.0


# ---------------------------------------------------------------------------
# Funding models
# ---------------------------------------------------------------------------

class TestFundingModels:
    def test_five_models_present(self):
        assert len(FUNDING_MODELS) == 5

    def test_required_fields(self):
        required = {"name", "short", "headline", "description", "pros", "cons", "typical_payback_yrs"}
        for model in FUNDING_MODELS:
            assert required.issubset(model.keys()), f"Missing fields in {model['name']}"

    def test_model_names(self):
        names = {m["name"] for m in FUNDING_MODELS}
        assert "Capital Expense" in names
        assert "Free Install" in names
        assert "Lease Purchase" in names
        assert "Operational Lease" in names
        assert "Hire Purchase" in names

    def test_pros_cons_are_lists(self):
        for model in FUNDING_MODELS:
            assert isinstance(model["pros"], list)
            assert isinstance(model["cons"], list)
            assert len(model["pros"]) >= 1
            assert len(model["cons"]) >= 1


# ---------------------------------------------------------------------------
# Org chart helpers
# ---------------------------------------------------------------------------

class TestReverseCHName:
    def test_reverses_comma_format(self):
        assert _reverse_ch_name("PATEL, Sarah") == "Sarah Patel"

    def test_handles_no_comma(self):
        assert _reverse_ch_name("John Smith") == "John Smith"

    def test_handles_all_caps(self):
        assert _reverse_ch_name("SMITH, JOHN") == "John Smith"

    def test_multipart_first_name(self):
        result = _reverse_ch_name("VAN DER BERG, Anne")
        assert "Anne" in result


class TestFormatDirectors:
    def test_formats_active_director(self):
        directors = [{"name": "PATEL, Sarah", "officer_role": "Director"}]
        result = _format_directors(directors)
        assert "Sarah Patel" in result
        assert "Director" in result
        assert "[resigned]" not in result

    def test_marks_resigned(self):
        directors = [
            {"name": "JONES, Bob", "officer_role": "Secretary", "resigned_on": "2023-01-01"}
        ]
        result = _format_directors(directors)
        assert "[resigned]" in result

    def test_empty_directors(self):
        result = _format_directors([])
        assert "no directors found" in result

    def test_multiple_directors(self):
        directors = [
            {"name": "PATEL, Sarah", "officer_role": "CFO"},
            {"name": "SMITH, James", "officer_role": "CEO"},
        ]
        result = _format_directors(directors)
        assert "Sarah Patel" in result
        assert "James Smith" in result


# ---------------------------------------------------------------------------
# Integration smoke tests (mocked Anthropic)
# ---------------------------------------------------------------------------

MOCK_DECK_RESPONSE = json.dumps({
    "slides": [
        {
            "title": f"Slide {i+1}",
            "subtitle": f"Subtitle {i+1}",
            "bullets": ["Bullet one", "Bullet two"],
            "speaker_note": "Speak clearly."
        }
        for i in range(11)
    ],
    "emails": [
        {"subject": "Cut your energy bill", "body": "Body A", "angle": "cost"},
        {"subject": "Hit net zero faster", "body": "Body B", "angle": "sustainability"},
    ]
})

MOCK_ORG_RESPONSE = json.dumps({
    "primary": {
        "name": "Sarah Patel",
        "role": "CFO",
        "confidence": 0.92,
        "rationale": "CFO owns CapEx budget.",
        "seniority_tier": 1,
    },
    "secondary": None,
})


def _make_mock_response(content: str) -> MagicMock:
    block = MagicMock()
    block.text = content
    response = MagicMock()
    response.content = [block]
    response.usage.input_tokens = 500
    response.usage.output_tokens = 200
    response.usage.cache_creation_input_tokens = 0
    response.usage.cache_read_input_tokens = 400
    return response


@patch("codex_brain.anthropic_client.anthropic.Anthropic")
def test_complete_returns_text_and_usage(MockAnthropic):
    from codex_brain.anthropic_client import CodexClient
    mock_api = MagicMock()
    mock_api.messages.create.return_value = _make_mock_response('{"ok": true}')
    MockAnthropic.return_value = mock_api

    client = CodexClient()
    text, usage = client.complete(system="sys", user="usr", model=SONNET)

    assert text == '{"ok": true}'
    assert usage.input_tokens == 500
    assert usage.cache_read_tokens == 400
    assert usage.cost_cents > 0


@patch("codex_brain.anthropic_client.anthropic.Anthropic")
def test_org_chart_inference(MockAnthropic):
    from codex_brain.anthropic_client import _default_client
    import codex_brain.anthropic_client as ac
    ac._default_client = None  # reset singleton

    mock_api = MagicMock()
    mock_api.messages.create.return_value = _make_mock_response(MOCK_ORG_RESPONSE)
    MockAnthropic.return_value = mock_api

    from codex_brain.generators.org_chart import infer_decision_maker
    result = infer_decision_maker(
        company_name="Bunhill Leisure Centre Ltd",
        directors=[{"name": "PATEL, Sarah", "officer_role": "CFO"}],
    )

    assert result.primary.name == "Sarah Patel"
    assert result.primary.confidence == 0.92
    assert result.secondary is None
    ac._default_client = None
