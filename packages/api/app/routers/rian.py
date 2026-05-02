"""POST /rian/run_agent — invoke a named agent from Rian's stack.

Surface
-------
``POST /rian/run_agent``
    Body: ``{agent: str, target_lead_id: str|null, client_id?: str, params?: dict}``
    Queues a run and returns ``{run_id, status}`` immediately. The actual
    agent invocation happens in a background task because Rian's pipelines
    are sub-minute but not sub-second — we don't want to block the request
    on a 30s LangGraph loop.

``GET /rian/run_agent/{run_id}``
    Polled by the UI. Returns ``{run_id, status, agent, output, ...}``.

Persistence
-----------
Every run is written to ``rian_agent_runs`` (collection auto-created — no
$jsonSchema validator yet because the run document shape is in active
flux). Each run also produces a row in ``audit_log`` and emits an
``agent_events`` row via the existing integration handshake so the same
observability surface (`docs/RIAN-INTEGRATION.md § 3`) covers our calls.

Why a job table (not blocking response)
---------------------------------------
The existing `/swarm/run` route uses the same pattern. Reusing it means
the UI's polling logic (`useSwarmJob` → `useRianAgentRun`) is a
copy-paste pair, and a future migration to Celery is one swap of the
``BackgroundTasks.add_task`` call.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.audit import log_audit
from app.services.rian_agent import (
    RUN_COLLECTION,
    make_run_id,
    now_iso,
    run_rian_agent,
    serialise_result,
)

log = logging.getLogger("solarreach.api.rian")
router = APIRouter()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RunAgentRequest(BaseModel):
    agent: str = Field(
        ...,
        description="Named agent kind. Currently supported: 'lead_research', 'outreach_drafter'.",
    )
    target_lead_id: str | None = Field(
        default=None,
        description="Optional lead id this run pertains to. Persisted in metadata for tracing.",
    )
    client_id: str = Field(default="client-greensolar-uk")
    params: dict[str, Any] = Field(default_factory=dict)


class RunAgentResponse(BaseModel):
    """Initial queue response. Output lands later via GET poll."""

    run_id: str
    status: str  # "queued" | "running" | "done" | "error"


class RunAgentDetail(BaseModel):
    run_id: str
    status: str
    agent: str
    target_lead_id: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    output: dict[str, Any] | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# DB helpers — same shape as routers/swarm.py
# ---------------------------------------------------------------------------


def _get_db(request: Request):
    client = getattr(request.app.state, "mongo_client", None)
    if client is None:
        return None
    from app.config import get_settings

    return client[get_settings().mongo_db]


async def _set_run(db, run_id: str, **fields: Any) -> None:
    if db is None:
        return
    try:
        await db[RUN_COLLECTION].update_one(
            {"_id": run_id},
            {"$set": {**fields, "updated_at": now_iso()}},
            upsert=True,
        )
    except Exception as e:  # noqa: BLE001
        log.warning("rian_agent_runs update failed (%s): %s", run_id, type(e).__name__)


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------


async def _spawn_run(
    db,
    *,
    run_id: str,
    agent: str,
    target_lead_id: str | None,
    client_id: str,
    params: dict[str, Any],
) -> None:
    """Run the agent and persist the result. Errors are caught and logged
    onto the run doc — never raised back into the BackgroundTasks runner.
    """
    await _set_run(db, run_id, status="running", started_at=now_iso())
    try:
        result = await run_rian_agent(
            agent=agent,
            target_lead_id=target_lead_id,
            client_id=client_id,
            params=params,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("rian run %s crashed", run_id)
        await _set_run(
            db,
            run_id,
            status="error",
            error=f"{type(e).__name__}: {e}",
            finished_at=now_iso(),
        )
        return

    # The result dataclass already encodes status — propagate it onto the run
    # doc so the UI can show "demo_mode" / "upstream_error" as a distinct
    # state from "done" without re-reading nested fields.
    final_status = "done" if result.status == "ok" else result.status
    await _set_run(
        db,
        run_id,
        status=final_status,
        output=serialise_result(result),
        finished_at=now_iso(),
    )

    # Best-effort audit row. log_audit failing should never break the run
    # response — already logged at INFO inside the helper.
    if db is not None:
        try:
            await log_audit(
                db,
                action="rian.run_agent",
                lead_id=target_lead_id,
                cost_cents=0,
                actor=f"rian-project1/{result.agent}",
                metadata={
                    "run_id": run_id,
                    "agent": result.agent,
                    "agent_status": result.status,
                    "thread_id": result.thread_id,
                    "message_count": result.message_count,
                },
            )
        except Exception as e:  # noqa: BLE001
            log.info("rian audit log skipped: %s", type(e).__name__)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/rian/run_agent", response_model=RunAgentResponse)
async def post_run_agent(
    body: RunAgentRequest,
    background: BackgroundTasks,
    request: Request,
) -> RunAgentResponse:
    db = _get_db(request)
    run_id = make_run_id()
    await _set_run(
        db,
        run_id,
        status="queued",
        agent=body.agent,
        target_lead_id=body.target_lead_id,
        client_id=body.client_id,
        params=body.params,
        created_at=now_iso(),
        started_at=None,
        finished_at=None,
        output=None,
        error=None,
    )
    background.add_task(
        _spawn_run,
        db,
        run_id=run_id,
        agent=body.agent,
        target_lead_id=body.target_lead_id,
        client_id=body.client_id,
        params=body.params,
    )
    return RunAgentResponse(run_id=run_id, status="queued")


@router.get("/rian/run_agent/{run_id}", response_model=RunAgentDetail)
async def get_run_agent(run_id: str, request: Request) -> RunAgentDetail:
    db = _get_db(request)
    if db is None:
        raise HTTPException(status_code=503, detail="mongo unavailable")
    doc = await db[RUN_COLLECTION].find_one({"_id": run_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunAgentDetail(
        run_id=run_id,
        status=doc.get("status", "unknown"),
        agent=doc.get("agent", "unknown"),
        target_lead_id=doc.get("target_lead_id"),
        started_at=doc.get("started_at"),
        finished_at=doc.get("finished_at"),
        output=doc.get("output"),
        error=doc.get("error"),
    )
