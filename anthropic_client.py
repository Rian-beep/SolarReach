"""
SolarReach Codex Brain — Anthropic SDK wrapper
Prompt caching (ephemeral), cost tracking, JSON fence stripping.
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any

import anthropic

logger = logging.getLogger(__name__)

# Cost per million tokens in USD cents
_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-20250514": {"in": 300, "out": 1500, "cache_write": 375, "cache_read": 30},
    "claude-opus-4-20250514":   {"in": 1500, "out": 7500, "cache_write": 1875, "cache_read": 150},
    "claude-haiku-4-5-20251001": {"in": 80,  "out": 400,  "cache_write": 100,  "cache_read": 8},
}

SONNET = "claude-sonnet-4-20250514"
OPUS   = "claude-opus-4-20250514"
HAIKU  = "claude-haiku-4-5-20251001"


@dataclass
class UsageRecord:
    model: str
    input_tokens: int
    output_tokens: int
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    cost_cents: float = 0.0
    duration_ms: int = 0
    call_type: str = ""

    def __post_init__(self) -> None:
        p = _PRICING.get(self.model, _PRICING[SONNET])
        self.cost_cents = (
            self.input_tokens      * p["in"]          / 1_000_000
            + self.output_tokens   * p["out"]         / 1_000_000
            + self.cache_write_tokens * p["cache_write"] / 1_000_000
            + self.cache_read_tokens  * p["cache_read"]  / 1_000_000
        ) * 100  # USD cents


@dataclass
class CodexClient:
    """
    Thin wrapper around the Anthropic SDK.

    Usage:
        client = CodexClient()
        text, usage = client.complete(
            system="You are a solar pitch writer.",
            user="Write a pitch for Bunhill Leisure Centre.",
            model=SONNET,
            cache_system=True,
            call_type="pitch_deck",
        )
    """

    _client: anthropic.Anthropic = field(init=False)
    _usage_log: list[UsageRecord] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    # ------------------------------------------------------------------
    # Core completion
    # ------------------------------------------------------------------

    def complete(
        self,
        *,
        system: str,
        user: str,
        model: str = SONNET,
        max_tokens: int = 2048,
        cache_system: bool = True,
        call_type: str = "",
        extra_messages: list[dict] | None = None,
    ) -> tuple[str, UsageRecord]:
        """
        Send a completion request.

        Args:
            system: System prompt text.
            user: User message text.
            model: Model string (use module constants SONNET / OPUS / HAIKU).
            max_tokens: Max output tokens.
            cache_system: Wrap system prompt with cache_control ephemeral.
            call_type: Label for audit log (e.g. "pitch_deck", "org_chart").
            extra_messages: Additional messages to prepend before user turn.

        Returns:
            (text, UsageRecord)
        """
        system_block: list[dict] = [
            {
                "type": "text",
                "text": system,
                **({"cache_control": {"type": "ephemeral"}} if cache_system else {}),
            }
        ]

        messages: list[dict] = list(extra_messages or [])
        messages.append({"role": "user", "content": user})

        t0 = time.monotonic()
        response = self._client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_block,
            messages=messages,
        )
        duration_ms = int((time.monotonic() - t0) * 1000)

        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )
        text = _strip_json_fences(text)

        usage = UsageRecord(
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            cache_write_tokens=getattr(response.usage, "cache_creation_input_tokens", 0),
            cache_read_tokens=getattr(response.usage, "cache_read_input_tokens", 0),
            duration_ms=duration_ms,
            call_type=call_type,
        )
        self._usage_log.append(usage)

        logger.info(
            "codex_call model=%s type=%s in=%d out=%d cache_read=%d cost_cents=%.4f ms=%d",
            model, call_type,
            usage.input_tokens, usage.output_tokens,
            usage.cache_read_tokens, usage.cost_cents, duration_ms,
        )
        return text, usage

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def session_cost_cents(self) -> float:
        return sum(u.cost_cents for u in self._usage_log)

    def usage_log(self) -> list[UsageRecord]:
        return list(self._usage_log)


# ------------------------------------------------------------------
# Utility
# ------------------------------------------------------------------

def _strip_json_fences(text: str) -> str:
    """Remove ```json ... ``` wrappers that Sonnet sometimes adds."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # drop opening fence line
        lines = lines[1:]
        # drop closing fence if present
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


# Module-level singleton — import and reuse across the process
_default_client: CodexClient | None = None


def get_client() -> CodexClient:
    global _default_client
    if _default_client is None:
        _default_client = CodexClient()
    return _default_client
