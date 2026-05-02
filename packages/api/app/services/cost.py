"""Anthropic cost calculator.

Prices are USD per million tokens. We round to nearest cent (USD).
Cache pricing follows Anthropic's published 4.x rules:
  - cache_create: 1.25x base input price
  - cache_read:   0.10x base input price
"""
from __future__ import annotations

# USD per million tokens — (input, output)
_PRICE_TABLE: dict[str, tuple[float, float]] = {
    # Sonnet 4.6
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-sonnet-4-6-20250101": (3.0, 15.0),
    # Opus 4.7
    "claude-opus-4-7": (15.0, 75.0),
    "claude-opus-4-7-20250101": (15.0, 75.0),
    # Haiku 4.5
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-haiku-4-5-20250101": (1.0, 5.0),
}


def _resolve_price(model: str) -> tuple[float, float]:
    if model in _PRICE_TABLE:
        return _PRICE_TABLE[model]
    # Best-effort prefix match (handles dated suffixes).
    for key, price in _PRICE_TABLE.items():
        if model.startswith(key):
            return price
    raise KeyError(f"Unknown model for pricing: {model!r}")


def compute_cost_cents(
    model: str,
    in_tokens: int,
    out_tokens: int,
    cache_read: int = 0,
    cache_create: int = 0,
) -> int:
    """Return integer USD cents for a single inference call."""
    in_price, out_price = _resolve_price(model)
    usd = (
        (in_tokens / 1_000_000) * in_price
        + (out_tokens / 1_000_000) * out_price
        + (cache_read / 1_000_000) * (in_price * 0.10)
        + (cache_create / 1_000_000) * (in_price * 1.25)
    )
    return round(usd * 100)
