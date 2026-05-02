"""Async Anthropic client wrapper with prompt caching + cost accounting.

Why this exists:
- We always want async (Celery wraps with asyncio.run).
- We always want cache_control on the system prompt (5min TTL ephemeral).
- We always want cost_cents on every call (drives /lead/spend/session).
- Sonnet sometimes wraps JSON in ```json ... ``` fences — we strip.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Iterable

try:
    from anthropic import AsyncAnthropic
except ImportError:  # pragma: no cover — allow tests to run without SDK installed
    AsyncAnthropic = None  # type: ignore[assignment,misc]


# Anthropic public pricing (USD per 1M tokens). Cache reads at 10%, cache writes at 125%.
PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"in": 3.0, "out": 15.0},
    "claude-sonnet-4-6-20260101": {"in": 3.0, "out": 15.0},
    "claude-opus-4-7": {"in": 15.0, "out": 75.0},
    "claude-opus-4-7-20260101": {"in": 15.0, "out": 75.0},
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0},
    "claude-haiku-4-5-20260101": {"in": 1.0, "out": 5.0},
}

USD_TO_CENTS = 100.0


def _resolve_price(model: str) -> dict[str, float]:
    if model in PRICING_USD_PER_MTOK:
        return PRICING_USD_PER_MTOK[model]
    for key, price in PRICING_USD_PER_MTOK.items():
        if model.startswith(key):
            return price
    # Fallback to Sonnet rates rather than crash. Logged externally.
    return PRICING_USD_PER_MTOK["claude-sonnet-4-6"]


def compute_cost_cents(
    model: str,
    in_tokens: int,
    out_tokens: int,
    cache_read_tokens: int = 0,
    cache_create_tokens: int = 0,
) -> float:
    """Compute USD cost in cents.

    cache reads = 10% of input rate
    cache writes (5min ephemeral) = 125% of input rate
    Regular input tokens billed at full input rate.
    """
    price = _resolve_price(model)
    in_rate = price["in"]
    out_rate = price["out"]

    cost_usd = (
        (in_tokens / 1_000_000.0) * in_rate
        + (out_tokens / 1_000_000.0) * out_rate
        + (cache_read_tokens / 1_000_000.0) * (in_rate * 0.10)
        + (cache_create_tokens / 1_000_000.0) * (in_rate * 1.25)
    )
    return round(cost_usd * USD_TO_CENTS, 6)


def strip_json_fence(text: str) -> str:
    """Sonnet sometimes wraps JSON in ```json ... ```. Strip it."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if "```" in text:
            text = text.rsplit("```", 1)[0]
    return text.strip()


@dataclass
class CompletionResult:
    text: str
    in_tokens: int
    out_tokens: int
    cache_read_tokens: int
    cache_create_tokens: int
    model: str
    cost_cents: float
    raw: Any = field(default=None, repr=False)


def _mask_key(key: str | None) -> str:
    if not key:
        return "<none>"
    if len(key) <= 8:
        return "***"
    return f"{key[:4]}…{key[-4:]}"


class AnthropicClient:
    """Async wrapper. NEVER logs api_key. Always uses prompt cache when asked."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-6",
        max_retries: int = 2,
        timeout: float = 120.0,
    ) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        self._key_repr = _mask_key(api_key)
        self.model = model
        if AsyncAnthropic is not None:
            self._client = AsyncAnthropic(
                api_key=api_key,
                max_retries=max_retries,
                timeout=timeout,
            )
        else:  # pragma: no cover
            self._client = None

    def __repr__(self) -> str:
        return f"AnthropicClient(model={self.model!r}, key={self._key_repr})"

    @staticmethod
    def _format_system(system: Any, cache: bool) -> Any:
        if system is None:
            return None
        if isinstance(system, list):
            return system
        if cache:
            return [
                {
                    "type": "text",
                    "text": system,
                    "cache_control": {"type": "ephemeral"},
                }
            ]
        return system

    @staticmethod
    def _coerce_messages(messages: Any) -> list[dict[str, Any]]:
        if isinstance(messages, str):
            return [{"role": "user", "content": messages}]
        return list(messages)

    async def complete(
        self,
        messages: Any,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        cache_system: bool = True,
        model: str | None = None,
    ) -> CompletionResult:
        if self._client is None:
            raise RuntimeError("anthropic SDK not installed")
        msgs = self._coerce_messages(messages)
        sys_param = self._format_system(system, cache_system)
        m = model or self.model

        kwargs: dict[str, Any] = {
            "model": m,
            "max_tokens": max_tokens,
            "messages": msgs,
            "temperature": temperature,
        }
        if sys_param is not None:
            kwargs["system"] = sys_param

        try:
            resp = await self._client.messages.create(**kwargs)
        except Exception as exc:
            raise RuntimeError(
                f"Anthropic call failed (model={m}, key={self._key_repr}): {type(exc).__name__}"
            ) from exc

        text_parts = []
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        text = "".join(text_parts)

        usage = resp.usage
        in_tokens = getattr(usage, "input_tokens", 0) or 0
        out_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0

        cost = compute_cost_cents(m, in_tokens, out_tokens, cache_read, cache_create)

        return CompletionResult(
            text=text,
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cache_read_tokens=cache_read,
            cache_create_tokens=cache_create,
            model=m,
            cost_cents=cost,
            raw=resp,
        )

    async def complete_streaming(
        self,
        messages: Any,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        cache_system: bool = True,
        model: str | None = None,
    ) -> AsyncIterator[str]:
        if self._client is None:
            raise RuntimeError("anthropic SDK not installed")
        msgs = self._coerce_messages(messages)
        sys_param = self._format_system(system, cache_system)
        m = model or self.model

        kwargs: dict[str, Any] = {
            "model": m,
            "max_tokens": max_tokens,
            "messages": msgs,
            "temperature": temperature,
        }
        if sys_param is not None:
            kwargs["system"] = sys_param

        async with self._client.messages.stream(**kwargs) as stream:
            async for delta in stream.text_stream:
                yield delta

    async def complete_streaming_collect(
        self,
        messages: Any,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        cache_system: bool = True,
        model: str | None = None,
        on_delta=None,
    ) -> CompletionResult:
        if self._client is None:
            raise RuntimeError("anthropic SDK not installed")
        msgs = self._coerce_messages(messages)
        sys_param = self._format_system(system, cache_system)
        m = model or self.model

        kwargs: dict[str, Any] = {
            "model": m,
            "max_tokens": max_tokens,
            "messages": msgs,
            "temperature": temperature,
        }
        if sys_param is not None:
            kwargs["system"] = sys_param

        text_parts: list[str] = []
        async with self._client.messages.stream(**kwargs) as stream:
            async for delta in stream.text_stream:
                text_parts.append(delta)
                if on_delta is not None:
                    on_delta(delta)
            final = await stream.get_final_message()

        usage = final.usage
        in_tokens = getattr(usage, "input_tokens", 0) or 0
        out_tokens = getattr(usage, "output_tokens", 0) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
        cost = compute_cost_cents(m, in_tokens, out_tokens, cache_read, cache_create)

        return CompletionResult(
            text="".join(text_parts),
            in_tokens=in_tokens,
            out_tokens=out_tokens,
            cache_read_tokens=cache_read,
            cache_create_tokens=cache_create,
            model=m,
            cost_cents=cost,
            raw=final,
        )

    async def complete_json(
        self,
        messages: Any,
        system: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.4,
        cache_system: bool = True,
        model: str | None = None,
    ) -> tuple[Any, CompletionResult]:
        result = await self.complete(
            messages=messages,
            system=system,
            max_tokens=max_tokens,
            temperature=temperature,
            cache_system=cache_system,
            model=model,
        )
        cleaned = strip_json_fence(result.text)
        if cleaned and cleaned[0] not in "{[":
            mtch = re.search(r"[\{\[]", cleaned)
            if mtch:
                cleaned = cleaned[mtch.start():]
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Anthropic returned non-JSON after fence strip: {exc.msg}"
            ) from exc
        return parsed, result
