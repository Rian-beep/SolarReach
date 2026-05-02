"""POST /langchain/run — single ReAct agent invocation.

Body
----
``{lead_id: str, prompt: str, model?: str, max_iterations?: int}``

Behaviour
---------
- Same queued/running/done lifecycle as ``/swarm/run`` and ``/rian/run_agent``
  so the UI's polling pattern is reusable. Persisted in the
  ``langchain_jobs`` collection.
- Background task runs ``swarm.langchain_bridge.arun`` (Sonnet 4.6 +
  ConversationBufferMemory keyed by lead_id + 4 ReAct tools).
- The final response carries ``output``, ``intermediate_steps`` (the ReAct
  trace), and ``cost_cents`` (estimated from LLM usage_metadata).

Why the ReAct trace is in the response
--------------------------------------
The CrewAI swarm exposes a markdown summary; this endpoint exposes the
raw tool-call sequence so demo viewers can see exactly which Atlas reads
+ benchmarks lookups the agent did before drafting outreach. That's the
"autonomous" theme front and centre.

Why a background task (not blocking)
------------------------------------
ReAct loops with Atlas reads and Anthropic calls run 5-30s. Mirrors the
existing ``/swarm/run`` and ``/rian/run_agent`` shape so the frontend's
polling logic is a copy-paste pair.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger("solarreach.api.langchain")
router = APIRouter()

_COLLECTION = "langchain_jobs"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class LangchainRunRequest(BaseModel):
    lead_id: str = Field(..., min_length=1, max_length=200)
    prompt: str = Field(..., min_length=1, max_length=4000)
    model: str | None = Field(
        default=None,
        description=(
            "Anthropic model id. Defaults to claude-sonnet-4-6 inside "
            "the bridge module."
        ),
    )
    max_iterations: int | None = Field(default=None, ge=1, le=20)


class LangchainRunResponse(BaseModel):
    """Initial queue response. Output lands later via GET poll."""

    job_id: str
    status: str  # queued | running | done | error


class LangchainStep(BaseModel):
    tool: str
    tool_input: Any | None = None
    log: str | None = None
    observation: Any | None = None


class LangchainJobDetail(BaseModel):
    job_id: str
    status: str
    lead_id: str | None = None
    prompt: str | None = None
    model: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    output: str | None = None
    intermediate_steps: list[LangchainStep] = []
    cost_cents: float = 0.0
    error: str | None = None


# ---------------------------------------------------------------------------
# Helpers — same shape as routers/swarm.py + routers/rian.py
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db(request: Request):
    """Return the Mongo db handle, or None if the API booted without it."""
    client = getattr(request.app.state, "mongo_client", None)
    if client is None:
        return None
    from app.config import get_settings  # local import — avoid circulars

    return client[get_settings().mongo_db]


async def _set_job(db, job_id: str, **fields: Any) -> None:
    if db is None:
        return
    try:
        await db[_COLLECTION].update_one(
            {"_id": job_id},
            {"$set": {**fields, "updated_at": _now_iso()}},
            upsert=True,
        )
    except Exception as e:  # noqa: BLE001
        log.warning(
            "langchain_jobs update failed (%s): %s", job_id, type(e).__name__
        )


# ---------------------------------------------------------------------------
# Background runner
# ---------------------------------------------------------------------------


async def _run_agent(lead_id: str, prompt: str, model: str | None, max_iter: int | None):
    """Run the LangChain ReAct agent. Lazy-import the bridge so the API can
    boot even when ``solarreach-swarm`` isn't installed in this venv."""
    from swarm.langchain_bridge import arun  # type: ignore

    kwargs: dict[str, Any] = {"lead_id": lead_id, "prompt": prompt}
    if model:
        kwargs["model"] = model
    if max_iter:
        kwargs["max_iterations"] = max_iter
    return await arun(**kwargs)


async def _spawn_job(
    db,
    *,
    job_id: str,
    lead_id: str,
    prompt: str,
    model: str | None,
    max_iterations: int | None,
) -> None:
    await _set_job(db, job_id, status="running", started_at=_now_iso())
    try:
        result = await _run_agent(lead_id, prompt, model, max_iterations)
    except Exception as e:  # noqa: BLE001
        log.exception("langchain job %s crashed", job_id)
        await _set_job(
            db,
            job_id,
            status="error",
            error=f"{type(e).__name__}: {e}",
            finished_at=_now_iso(),
        )
        return

    # arun() never raises — it returns the error in the dict instead.
    err = result.get("error")
    final_status = "error" if err else "done"
    await _set_job(
        db,
        job_id,
        status=final_status,
        output=result.get("output", ""),
        intermediate_steps=result.get("intermediate_steps") or [],
        cost_cents=float(result.get("cost_cents", 0.0)),
        model=result.get("model"),
        error=err,
        finished_at=_now_iso(),
    )

    # Best-effort audit row — never block the response on the audit write.
    try:
        from app.services.audit import log_audit

        await log_audit(
            db,
            action="langchain.run",
            lead_id=lead_id,
            cost_cents=int(round(float(result.get("cost_cents", 0.0)))),
            actor="agent_langchain",
            metadata={
                "job_id": job_id,
                "model": result.get("model"),
                "step_count": len(result.get("intermediate_steps") or []),
                "in_tokens": result.get("in_tokens", 0),
                "out_tokens": result.get("out_tokens", 0),
            },
        )
    except Exception as e:  # noqa: BLE001
        log.info("langchain audit log skipped: %s", type(e).__name__)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.post("/langchain/run", response_model=LangchainRunResponse)
async def langchain_run(
    body: LangchainRunRequest,
    background: BackgroundTasks,
    request: Request,
) -> LangchainRunResponse:
    # Verify the bridge is importable before promising a job_id — surfaces
    # missing deps as 503 instead of an opaque background-task error.
    try:
        import swarm.langchain_bridge  # type: ignore  # noqa: F401
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"langchain bridge unavailable: {type(e).__name__}",
        ) from e

    db = _get_db(request)
    job_id = f"lc_{uuid.uuid4()}"
    await _set_job(
        db,
        job_id,
        status="queued",
        lead_id=body.lead_id,
        prompt=body.prompt,
        model=body.model,
        created_at=_now_iso(),
        started_at=None,
        finished_at=None,
        output=None,
        intermediate_steps=[],
        cost_cents=0.0,
        error=None,
    )
    background.add_task(
        _spawn_job,
        db,
        job_id=job_id,
        lead_id=body.lead_id,
        prompt=body.prompt,
        model=body.model,
        max_iterations=body.max_iterations,
    )
    return LangchainRunResponse(job_id=job_id, status="queued")


@router.get("/langchain/job/{job_id}", response_model=LangchainJobDetail)
async def langchain_job(job_id: str, request: Request) -> LangchainJobDetail:
    db = _get_db(request)
    if db is None:
        raise HTTPException(status_code=503, detail="mongo unavailable")
    doc = await db[_COLLECTION].find_one({"_id": job_id})
    if doc is None:
        raise HTTPException(status_code=404, detail="job not found")
    raw_steps = doc.get("intermediate_steps") or []
    steps: list[LangchainStep] = []
    for s in raw_steps:
        if isinstance(s, dict):
            steps.append(
                LangchainStep(
                    tool=str(s.get("tool", "unknown")),
                    tool_input=s.get("tool_input"),
                    log=s.get("log"),
                    observation=s.get("observation"),
                )
            )
    return LangchainJobDetail(
        job_id=job_id,
        status=doc.get("status", "unknown"),
        lead_id=doc.get("lead_id"),
        prompt=doc.get("prompt"),
        model=doc.get("model"),
        started_at=doc.get("started_at"),
        finished_at=doc.get("finished_at"),
        output=doc.get("output"),
        intermediate_steps=steps,
        cost_cents=float(doc.get("cost_cents", 0.0)),
        error=doc.get("error"),
    )
