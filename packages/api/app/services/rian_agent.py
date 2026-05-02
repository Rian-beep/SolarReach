"""Provider for Rian's deepagents/LangGraph agent stack.

Why this exists
---------------
Rian's repo (``Rian-beep/solarreach-project1``) ships a deepagents-based Lead
Researcher built on LangGraph + ``langgraph-checkpoint-mongodb`` + the
``deepagents`` package. We want our API to be able to *invoke* his agent on a
specific lead and surface the result in our UI — without forcing every API
deploy to install his heavy LangChain dependency tree.

Strategy: **lazy import + demo-mode fallback** (same pattern as
``voice_provider.RianProjectVoiceProvider``).

- If ``lead_agent`` is importable in this venv (caller did ``pip install -e
  /path/to/sr-rian[agent]``) → run the real agent in a worker thread.
- If not importable → return a deterministic ``demo_mode`` payload so the UI
  renders gracefully.

Why a worker thread (not async): Rian's ``run_lead_agent_session`` is sync
and uses ``pymongo.MongoClient`` internally. Wrapping it in
``asyncio.to_thread`` keeps the FastAPI event loop responsive.

Why we don't import his package eagerly: ``deepagents`` pulls in LangChain +
LangGraph + 30+ transitive deps. Keeping the import lazy means our API can
boot — and our tests can run — without that footprint.
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

log = logging.getLogger("solarreach.api.rian_agent")

# Status taxonomy mirrors the voice provider: "ok" means a real run, anything
# else is a degraded/safe fallback the UI can render explicitly.
RianAgentStatus = Literal["ok", "demo_mode", "upstream_error"]

# Known agent kinds. The lead researcher is the only one Rian's repo ships
# today; future agents (outreach_drafter, enrichment) plug into the same
# router by adding a key here.
KnownAgent = Literal["lead_research", "outreach_drafter"]


@dataclass
class RianAgentResult:
    """Shape returned to the router → persisted under
    ``rian_agent_runs.<run_id>.output``.

    Keeping it a dataclass so we can ``asdict()`` for Mongo without a Pydantic
    model spec. Drop-in JSON-serialisable.
    """

    status: RianAgentStatus
    agent: str
    summary: str
    thread_id: str | None
    message_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Lazy probe — keep this guard tight so our import path stays light.
# ---------------------------------------------------------------------------


def _probe_lead_agent():
    """Attempt to import Rian's lead agent. Returns the module or None.

    We intentionally swallow *any* exception (ImportError, ModuleNotFoundError,
    TypeError on partial installs, RuntimeError from the langchain config
    loader) — falling back to demo mode is always preferable to 500ing.
    """
    try:
        # Imported here, never at module top — if Rian's repo isn't installed,
        # the rest of the API is unaffected.
        from lead_agent import run_lead_agent_session  # type: ignore

        return run_lead_agent_session
    except Exception as e:  # noqa: BLE001
        log.info("lead_agent unavailable (%s); using demo_mode", type(e).__name__)
        return None


# ---------------------------------------------------------------------------
# Real-mode invocation
# ---------------------------------------------------------------------------


def _invoke_lead_agent_sync(
    *,
    target_lead_id: str | None,
    client_id: str,
    params: dict[str, Any],
) -> RianAgentResult:
    """Run Rian's agent synchronously. Called from a worker thread."""
    runner = _probe_lead_agent()
    if runner is None:
        return _demo_result(
            agent="lead_research",
            target_lead_id=target_lead_id,
            reason="lead_agent package not importable",
        )

    # Rian's session takes ``client_slug`` (his naming) — we accept the more
    # standard ``client_id`` from our payload and adapt.
    batch_size = max(1, min(int(params.get("batch_size", 1)), 10))
    thread_id = params.get("thread_id")  # optional resume hook

    try:
        result = runner(
            client_slug=client_id,
            batch_size=batch_size,
            thread_id=thread_id,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("rian agent invocation failed")
        return RianAgentResult(
            status="upstream_error",
            agent="lead_research",
            summary=f"agent error: {type(e).__name__}: {e}",
            thread_id=thread_id,
            message_count=0,
            metadata={"target_lead_id": target_lead_id},
        )

    return RianAgentResult(
        status="ok",
        agent="lead_research",
        summary=str(result.get("final_message", ""))[:4000],
        thread_id=str(result.get("thread_id") or ""),
        message_count=int(result.get("message_count") or 0),
        metadata={"target_lead_id": target_lead_id, "client_id": client_id},
    )


# ---------------------------------------------------------------------------
# Demo-mode fallback
# ---------------------------------------------------------------------------


def _demo_result(
    *, agent: str, target_lead_id: str | None, reason: str
) -> RianAgentResult:
    """Deterministic demo-mode payload. Same shape as a real run."""
    return RianAgentResult(
        status="demo_mode",
        agent=agent,
        summary=(
            "Demo: Rian's agent pipeline is not installed in this venv. To enable "
            "real runs, install his package via "
            "`pip install -e /path/to/sr-rian[agent]` and restart the API. "
            f"Reason: {reason}"
        ),
        thread_id=None,
        message_count=0,
        metadata={
            "target_lead_id": target_lead_id,
            "stub": True,
            "reason": reason,
        },
    )


# ---------------------------------------------------------------------------
# Outreach-drafter stub (Rian's repo doesn't ship one yet — we keep the slot
# open so the router contract is stable when his second agent lands).
# ---------------------------------------------------------------------------


def _outreach_drafter_stub(
    *, target_lead_id: str | None, client_id: str, params: dict[str, Any]
) -> RianAgentResult:
    return _demo_result(
        agent="outreach_drafter",
        target_lead_id=target_lead_id,
        reason="outreach_drafter not yet implemented in solarreach-project1",
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


_AGENT_DISPATCH = {
    "lead_research": _invoke_lead_agent_sync,
    "outreach_drafter": _outreach_drafter_stub,
}


async def run_rian_agent(
    *,
    agent: str,
    target_lead_id: str | None,
    client_id: str,
    params: dict[str, Any] | None = None,
) -> RianAgentResult:
    """Run a named Rian agent. Async — wraps the sync runner in a thread.

    Unknown ``agent`` values resolve to a ``demo_mode`` payload rather than
    raising; the router re-uses this method for both real and stub modes so
    keeping the contract uniform matters.
    """
    params = params or {}
    fn = _AGENT_DISPATCH.get(agent)
    if fn is None:
        return _demo_result(
            agent=agent,
            target_lead_id=target_lead_id,
            reason=f"unknown agent kind: {agent!r}",
        )

    return await asyncio.to_thread(
        fn,
        target_lead_id=target_lead_id,
        client_id=client_id,
        params=params,
    )


# ---------------------------------------------------------------------------
# Run-document helpers — kept here so the router stays thin and tests can
# inject a fake run without standing up the whole HTTP stack.
# ---------------------------------------------------------------------------

RUN_COLLECTION = "rian_agent_runs"


def make_run_id() -> str:
    return f"rian_{uuid.uuid4()}"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def serialise_result(result: RianAgentResult) -> dict[str, Any]:
    return asdict(result)


__all__ = [
    "RianAgentResult",
    "RianAgentStatus",
    "RUN_COLLECTION",
    "make_run_id",
    "now_iso",
    "run_rian_agent",
    "serialise_result",
]
