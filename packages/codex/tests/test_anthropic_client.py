"""Tests for AnthropicClient — start with cost calc (pure function, no SDK)."""

import pytest

from codex_brain.anthropic_client import compute_cost_cents


def test_cost_cents_sonnet_basic():
    # Sonnet 4.6: $3/Mtok in, $15/Mtok out
    # 1M in tokens = $3 = 300 cents
    cost = compute_cost_cents("claude-sonnet-4-6", in_tokens=1_000_000, out_tokens=0)
    assert cost == pytest.approx(300.0, rel=0.01)


def test_cost_cents_sonnet_combined():
    # 100k in + 50k out: 0.1*$3 + 0.05*$15 = $0.30 + $0.75 = $1.05 = 105 cents
    cost = compute_cost_cents("claude-sonnet-4-6", in_tokens=100_000, out_tokens=50_000)
    assert cost == pytest.approx(105.0, rel=0.01)


def test_cost_cents_cache_read_is_10pct():
    # Cache read: 10% of input rate
    # 1M cache_read on Sonnet ($3/Mtok) = $0.30 = 30 cents
    cost = compute_cost_cents(
        "claude-sonnet-4-6",
        in_tokens=0,
        out_tokens=0,
        cache_read_tokens=1_000_000,
    )
    assert cost == pytest.approx(30.0, rel=0.01)


def test_cost_cents_cache_write_is_125pct():
    # Cache write: 125% of input rate
    # 1M cache_create on Sonnet = $3.75 = 375 cents
    cost = compute_cost_cents(
        "claude-sonnet-4-6",
        in_tokens=0,
        out_tokens=0,
        cache_create_tokens=1_000_000,
    )
    assert cost == pytest.approx(375.0, rel=0.01)


def test_cost_cents_opus_pricing():
    # Opus 4.7: $15/Mtok in, $75/Mtok out
    # 1M out = $75 = 7500 cents
    cost = compute_cost_cents("claude-opus-4-7", in_tokens=0, out_tokens=1_000_000)
    assert cost == pytest.approx(7500.0, rel=0.01)


def test_cost_cents_haiku_pricing():
    # Haiku 4.5: $1/Mtok in, $5/Mtok out
    # 1M in = $1 = 100 cents
    cost = compute_cost_cents("claude-haiku-4-5", in_tokens=1_000_000, out_tokens=0)
    assert cost == pytest.approx(100.0, rel=0.01)


def test_cost_cents_unknown_model_falls_back():
    # Should not crash on unknown model
    cost = compute_cost_cents("claude-unknown-future", in_tokens=1000, out_tokens=1000)
    assert cost > 0


def test_strip_json_fence_basic():
    from codex_brain.anthropic_client import strip_json_fence
    assert strip_json_fence('```json\n{"a": 1}\n```') == '{"a": 1}'


def test_strip_json_fence_no_fence_passthrough():
    from codex_brain.anthropic_client import strip_json_fence
    assert strip_json_fence('{"a": 1}') == '{"a": 1}'


def test_strip_json_fence_bare_triple_backtick():
    from codex_brain.anthropic_client import strip_json_fence
    assert strip_json_fence('```\n{"a": 1}\n```') == '{"a": 1}'


def test_client_requires_api_key():
    from codex_brain.anthropic_client import AnthropicClient
    with pytest.raises(ValueError):
        AnthropicClient(api_key="")


def test_client_masks_key_in_repr():
    from codex_brain.anthropic_client import AnthropicClient
    c = AnthropicClient(api_key="sk-ant-supersecret-12345-abcdef")
    r = repr(c)
    assert "supersecret" not in r
    assert "12345" not in r
    assert "sk-ant" in r or "sk-a" in r  # prefix shown
