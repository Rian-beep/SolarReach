"""Standalone LangChain ReAct agent — runs alongside the CrewAI swarm.

This is intentionally additive to the existing CrewAI hierarchical crew: it
shares the Atlas tooling but exposes a different surface (single ReAct loop,
per-lead conversation memory) so the API can route certain prompts here when
a fast, single-thread agent makes more sense than a multi-specialist crew.

Architecture
------------
- LLM:    ``ChatAnthropic(model="claude-sonnet-4-6")``
- Tools:  ``atlas_query`` / ``atlas_vector_search`` (rewrapped from the
          existing CrewAI tools via their ``.func`` attribute), plus two new
          tools ``pull_industry_benchmarks`` and ``compose_outreach``.
- Memory: ``ConversationBufferMemory`` keyed by ``lead_id`` — one buffer per
          lead, shared across calls in the same process. Cleared on
          ``reset_memory(lead_id)``.

Why use ``langchain_classic`` for the executor + memory?
LangChain 1.x moved the legacy ``AgentExecutor`` + ``ConversationBufferMemory``
out of the top-level ``langchain`` package into ``langchain_classic``. The
"new" agent surface is LangGraph, which Rian already integrates via
``services/rian_agent.py``. Using the classic ReAct executor keeps this
module distinct from Rian's stack and matches the spec's request for an
``AgentExecutor`` + ``ConversationBufferMemory`` pairing.

Cost accounting
---------------
``arun()`` returns ``(output, intermediate_steps, cost_cents)``. Cost is
estimated from the LLM's reported usage_metadata across the run callback.
This is the same cents unit our /lead/spend/session endpoint uses.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langchain_anthropic import ChatAnthropic
from langchain_classic.agents import AgentExecutor, create_react_agent
from langchain_classic.memory import ConversationBufferMemory
from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.prompts import PromptTemplate
from langchain_core.tools import BaseTool, tool

from swarm.tools.atlas import atlas_query as _crew_atlas_query
from swarm.tools.atlas import atlas_vector_search as _crew_atlas_vector_search

log = logging.getLogger("solarreach.swarm.langchain_bridge")

# Sonnet 4.6 — cheap enough for a multi-step ReAct loop, smart enough to
# reason over Atlas docs + benchmarks. The CrewAI manager uses Opus; this
# bridge intentionally uses Sonnet so the two surfaces feel different.
_DEFAULT_MODEL = "claude-sonnet-4-6"

# Anthropic public pricing (USD per 1M tokens). Mirrors codex_brain's table.
_PRICING_USD_PER_MTOK: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"in": 3.0, "out": 15.0},
    "claude-opus-4-7": {"in": 15.0, "out": 75.0},
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0},
}

# One memory buffer per lead. Cheap (in-process dict) — fine for a hackathon
# surface. A future move to Redis-backed memory would only need a different
# memory class plumbed in here.
_MEMORY_BY_LEAD: dict[str, ConversationBufferMemory] = {}


def _resolve_price(model: str) -> dict[str, float]:
    if model in _PRICING_USD_PER_MTOK:
        return _PRICING_USD_PER_MTOK[model]
    for key, price in _PRICING_USD_PER_MTOK.items():
        if model.startswith(key):
            return price
    return _PRICING_USD_PER_MTOK["claude-sonnet-4-6"]


def _compute_cost_cents(model: str, in_tokens: int, out_tokens: int) -> float:
    price = _resolve_price(model)
    cost_usd = (
        (in_tokens / 1_000_000.0) * price["in"]
        + (out_tokens / 1_000_000.0) * price["out"]
    )
    return round(cost_usd * 100.0, 6)


# ---------------------------------------------------------------------------
# Tool wrappers
# ---------------------------------------------------------------------------
# The CrewAI ``@tool``-decorated callables in ``swarm.tools.atlas`` are
# CrewAI BaseTool instances, not LangChain BaseTool instances. We rewrap
# their ``.func`` attribute via langchain_core's ``@tool`` decorator so the
# ReAct AgentExecutor sees proper LangChain tools.


@tool
def atlas_query(filter: dict, collection: str = "leads", limit: int = 20) -> dict[str, Any]:
    """Direct Mongo Atlas find query. Use for structured retrieval (e.g.
    {"_id": "lead_codenode_demo"} or {"scores.composite_score": {"$gte": 70}}).
    Returns {ok, data:[docs], error}."""
    return _crew_atlas_query.func(filter=filter, collection=collection, limit=limit)


@tool
def atlas_vector_search(
    query: str, collection: str = "companies", k: int = 5
) -> dict[str, Any]:
    """Semantic vector search over a Mongo Atlas collection (Voyage AI
    voyage-3 embeddings, cosine similarity). Use for natural-language
    queries about leads, companies, or industries. Returns
    {ok, data:[docs], error, mode}."""
    return _crew_atlas_vector_search.func(query=query, collection=collection, k=k)


@tool
def pull_industry_benchmarks() -> dict[str, Any]:
    """Return the canonical UK 2025-26 commercial-solar benchmarks (18 keys
    covering install cost £/kW, generation kWh/kWp, SEG export rate, IRR,
    payback, grid carbon intensity, capital allowances). Always cite these
    when making claims about "industry typical" numbers — these are the
    single source of truth for the deck and HUD."""
    # Lazy import so the package can boot even if shared isn't installed.
    from solarreach_shared.industry_benchmarks import INDUSTRY_BENCHMARKS

    # tuples (e.g. range bands) -> lists for LLM-friendly JSON
    out: dict[str, Any] = {}
    for k, v in INDUSTRY_BENCHMARKS.items():
        out[k] = list(v) if isinstance(v, tuple) else v
    return {"ok": True, "data": out, "key_count": len(out)}


@tool
def compose_outreach(
    lead_id: str,
    channel: str = "email",
    angle: str = "",
) -> dict[str, Any]:
    """Draft outreach copy for a target lead. Pulls the lead doc from Atlas,
    grabs its decision_maker, and asks the codex email generator (Sonnet
    4.6) for two A/B variants. ``channel`` is one of "email" | "linkedin"
    | "voice"; non-email channels reuse the email body but flag intent in
    the metadata. ``angle`` is an optional one-line steer (e.g.
    "lead with NPV", "lead with carbon"). Returns {ok, variants, channel,
    error}."""
    import asyncio

    # Resolve lead via Atlas.
    lead_lookup = _crew_atlas_query.func(
        filter={"_id": lead_id}, collection="leads", limit=1
    )
    if not lead_lookup.get("ok") or not lead_lookup.get("data"):
        return {
            "ok": False,
            "variants": None,
            "channel": channel,
            "error": f"lead_not_found:{lead_id}",
        }
    lead = lead_lookup["data"][0]
    dm = lead.get("decision_maker") or {
        "name": "there",
        "role": "Decision Maker",
    }

    # Lazy-import the codex generator to keep this module's import tree light.
    try:
        from codex_brain.anthropic_client import AnthropicClient
        from codex_brain.generators.email import generate_email_variants
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "variants": None,
            "channel": channel,
            "error": f"codex_brain_unavailable:{type(e).__name__}",
        }

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {
            "ok": False,
            "variants": None,
            "channel": channel,
            "error": "ANTHROPIC_API_KEY unset",
        }

    # Splice the angle into the lead's address line so the email generator
    # picks it up via its existing system prompt without us having to
    # rewrite the prompt loader. Cheap, additive — the generator already
    # ignores unknown fields gracefully.
    if angle:
        lead = {**lead, "_langchain_angle": angle.strip()}

    client = AnthropicClient(api_key=api_key, model="claude-sonnet-4-6")

    # generate_email_variants is async — call it via asyncio.run() because
    # this @tool body is sync (LangChain ReAct tools are sync by default
    # in the classic executor).
    try:
        variants = asyncio.run(generate_email_variants(lead, dm, client))
    except RuntimeError:
        # Already inside an event loop (e.g. uvicorn worker). Use a fresh
        # loop in a worker thread to avoid the "asyncio.run() cannot be
        # called from a running event loop" footgun.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                asyncio.run, generate_email_variants(lead, dm, client)
            )
            variants = future.result(timeout=60)
    except Exception as e:  # noqa: BLE001
        return {
            "ok": False,
            "variants": None,
            "channel": channel,
            "error": f"generate_failed:{type(e).__name__}",
        }

    return {
        "ok": True,
        "variants": variants,
        "channel": channel,
        "lead_id": lead_id,
    }


# ---------------------------------------------------------------------------
# Agent assembly
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are SolarReach's solar sales intelligence agent. You reason over "
    "real Mongo Atlas data (leads, companies, decision-makers, Land "
    "Registry / INSPIRE polygons), cite UK 2025-26 industry benchmarks for "
    "every claim about \"industry typical\" numbers, and draft outreach when "
    "asked.\n\n"
    "Operating rules:\n"
    "- Always pull the target lead's doc via atlas_query before drafting "
    "anything. The lead's `financial`, `panel_layout`, and `scores` blocks "
    "are the ground truth.\n"
    "- Cite benchmarks only by calling pull_industry_benchmarks — never "
    "from memory. Numbers drift; the dict doesn't.\n"
    "- For outreach, call compose_outreach with the lead_id; do not hand-"
    "write copy. The generator is tuned for Sonnet 4.6 cache hits.\n"
    "- Prefer atlas_vector_search for fuzzy/topical questions about a "
    "company; prefer atlas_query when you have an _id or structured filter.\n"
    "- Be concise. Final answers are 5-10 lines unless asked otherwise."
)

# ReAct prompt template — same shape the langchain hub ReAct prompt uses,
# inlined here to avoid a network fetch on every cold start. The
# {agent_scratchpad} variable is required by create_react_agent; the
# {chat_history} variable lets ConversationBufferMemory inject prior turns.
_REACT_TEMPLATE = """{system}

Recent conversation (most recent last):
{chat_history}

You have access to the following tools:

{tools}

Use the following format strictly. The Action line MUST be one of [{tool_names}] verbatim, with no extra text.

Question: the user's question
Thought: think about what to do
Action: the tool name (one of [{tool_names}])
Action Input: a JSON object matching the tool's signature
Observation: the tool's result
... (this Thought/Action/Action Input/Observation pattern can repeat)
Thought: I now know the final answer
Final Answer: the answer to the question, citing data + benchmarks

Begin.

Question: {input}
{agent_scratchpad}"""


class _UsageCallback(AsyncCallbackHandler):
    """Sums input/output tokens reported by the LLM across the agent loop.

    LangChain emits usage on `on_llm_end` for ChatAnthropic; we accumulate
    so the router can return a single cost_cents number.
    """

    def __init__(self) -> None:
        super().__init__()
        self.in_tokens = 0
        self.out_tokens = 0
        self.model: str = _DEFAULT_MODEL

    async def on_llm_end(self, response: Any, **kwargs: Any) -> None:  # noqa: ANN401
        try:
            llm_output = getattr(response, "llm_output", None) or {}
            usage = llm_output.get("usage") or llm_output.get("usage_metadata") or {}
            # Walk generations for usage_metadata too — this is where Anthropic
            # reports it in newer langchain-anthropic.
            for gen_list in getattr(response, "generations", []) or []:
                for gen in gen_list:
                    msg = getattr(gen, "message", None)
                    if msg is None:
                        continue
                    meta = getattr(msg, "usage_metadata", None) or {}
                    self.in_tokens += int(meta.get("input_tokens", 0) or 0)
                    self.out_tokens += int(meta.get("output_tokens", 0) or 0)
            # Fallback: top-level usage dict.
            self.in_tokens += int(usage.get("input_tokens", 0) or 0)
            self.out_tokens += int(usage.get("output_tokens", 0) or 0)
        except Exception as e:  # noqa: BLE001
            log.debug("usage callback parse failed: %s", type(e).__name__)


def _get_memory(lead_id: str) -> ConversationBufferMemory:
    """One ConversationBufferMemory per lead_id; created on first access."""
    mem = _MEMORY_BY_LEAD.get(lead_id)
    if mem is None:
        mem = ConversationBufferMemory(
            memory_key="chat_history",
            input_key="input",
            return_messages=False,
        )
        _MEMORY_BY_LEAD[lead_id] = mem
    return mem


def reset_memory(lead_id: str | None = None) -> None:
    """Drop one lead's buffer (or all). Used by tests + admin tooling."""
    if lead_id is None:
        _MEMORY_BY_LEAD.clear()
        return
    _MEMORY_BY_LEAD.pop(lead_id, None)


def _tools() -> list[BaseTool]:
    return [
        atlas_query,
        atlas_vector_search,
        pull_industry_benchmarks,
        compose_outreach,
    ]


def build_agent(
    *,
    lead_id: str,
    model: str = _DEFAULT_MODEL,
    max_iterations: int = 8,
) -> AgentExecutor:
    """Build a ReAct AgentExecutor for ``lead_id``.

    The memory buffer is keyed by lead so multiple calls about the same
    lead form a coherent thread (e.g. "now draft the email" referencing
    a lead pulled in a prior turn).
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY unset — cannot build LangChain agent")

    llm = ChatAnthropic(
        model=model,  # type: ignore[arg-type]
        api_key=api_key,  # type: ignore[arg-type]
        max_tokens=4096,
        timeout=120,
        max_retries=2,
    )

    tools = _tools()
    prompt = PromptTemplate.from_template(_REACT_TEMPLATE).partial(system=_SYSTEM_PROMPT)
    memory = _get_memory(lead_id)

    agent = create_react_agent(llm=llm, tools=tools, prompt=prompt)
    executor = AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        max_iterations=max_iterations,
        return_intermediate_steps=True,
        handle_parsing_errors=True,
        verbose=False,
    )
    return executor


async def arun(
    *,
    lead_id: str,
    prompt: str,
    model: str = _DEFAULT_MODEL,
    max_iterations: int = 8,
) -> dict[str, Any]:
    """Run the ReAct agent for one prompt.

    Returns ``{output, intermediate_steps, cost_cents, model, lead_id}``.
    Never raises — agent failures are captured in ``error`` and the call
    still resolves so the API job table stays consistent.
    """
    try:
        executor = build_agent(
            lead_id=lead_id, model=model, max_iterations=max_iterations
        )
    except Exception as e:  # noqa: BLE001
        return {
            "output": "",
            "intermediate_steps": [],
            "cost_cents": 0.0,
            "model": model,
            "lead_id": lead_id,
            "error": f"build_agent_failed:{type(e).__name__}: {e}",
        }

    usage = _UsageCallback()
    try:
        result = await executor.ainvoke(
            {"input": prompt},
            config={"callbacks": [usage]},
        )
    except Exception as e:  # noqa: BLE001
        log.warning("langchain agent run failed: %s", type(e).__name__)
        return {
            "output": "",
            "intermediate_steps": [],
            "cost_cents": _compute_cost_cents(model, usage.in_tokens, usage.out_tokens),
            "model": model,
            "lead_id": lead_id,
            "error": f"{type(e).__name__}: {e}",
        }

    cost_cents = _compute_cost_cents(model, usage.in_tokens, usage.out_tokens)
    return {
        "output": result.get("output", ""),
        "intermediate_steps": _serialise_steps(result.get("intermediate_steps") or []),
        "cost_cents": cost_cents,
        "model": model,
        "lead_id": lead_id,
        "in_tokens": usage.in_tokens,
        "out_tokens": usage.out_tokens,
    }


def _serialise_steps(steps: list[Any]) -> list[dict[str, Any]]:
    """Flatten (AgentAction, observation) tuples into JSON-safe dicts."""
    out: list[dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, tuple) or len(step) != 2:
            continue
        action, observation = step
        out.append(
            {
                "tool": getattr(action, "tool", "unknown"),
                "tool_input": getattr(action, "tool_input", None),
                "log": getattr(action, "log", None),
                "observation": _truncate(observation),
            }
        )
    return out


def _truncate(value: Any, max_len: int = 4000) -> Any:  # noqa: ANN401
    """Truncate observations so a chatty Atlas hit doesn't bloat the
    response payload past sensible JSON sizes."""
    if isinstance(value, str) and len(value) > max_len:
        return value[:max_len] + f"… [truncated {len(value) - max_len} chars]"
    return value


__all__ = [
    "arun",
    "build_agent",
    "reset_memory",
    "atlas_query",
    "atlas_vector_search",
    "pull_industry_benchmarks",
    "compose_outreach",
]
