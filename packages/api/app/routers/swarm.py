"""POST /swarm/run + GET /swarm/job/{id} — async crew dispatch.

The crew is heavy (CrewAI hierarchical + Anthropic). We run it in a background
asyncio task and persist state via an in-process dict keyed by job_id. The web
client polls /swarm/job/{id}.

Why no Celery here:
- The existing API already spawns Celery for the codex pitch path. The swarm
  is short-lived (sub-minute) and benefits from sharing the API process's
  Mongo client + audit pipeline. A future move to Celery would only require
  swapping `_spawn_job` body for a `tasks.run_swarm.delay(...)`.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from pydantic import BaseModel, Field

log = logging.getLogger("solarreach.api.swarm")
router = APIRouter()

# In-process job store. job_id → {status, started_at, finished_at, result, error}
_JOBS: dict[str, dict[str, Any]] = {}


class SwarmRunRequest(BaseModel):
    objective: str = Field(..., min_length=1, max_length=2000)
    target_lead_id: str | None = None


class SwarmRunResponse(BaseModel):
    job_id: str
    status: str


class SwarmJobResponse(BaseModel):
    job_id: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    result: str | None = None
    error: str | None = None


async def _run_crew_async(objective: str, target_lead_id: str | None) -> str:
    """Run the crew in a worker thread (CrewAI is sync internally)."""
    # Import lazily so the API can boot even if `solarreach-swarm` isn't
    # installed in this venv yet — endpoint then 503s with a clear error.
    from swarm.crew import build_crew  # type: ignore

    def _kick() -> str:
        crew = build_crew(objective=objective, target_lead_id=target_lead_id)
        return str(crew.kickoff(inputs={
            "objective": objective,
            "target_lead_id": target_lead_id or "",
        }))

    return await asyncio.to_thread(_kick)


async def _spawn_job(job_id: str, objective: str, target_lead_id: str | None) -> None:
    _JOBS[job_id]["started_at"] = datetime.now(timezone.utc).isoformat()
    _JOBS[job_id]["status"] = "running"
    try:
        result = await _run_crew_async(objective, target_lead_id)
        _JOBS[job_id].update(
            status="done",
            result=result,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("swarm job %s failed: %s", job_id, type(e).__name__)
        _JOBS[job_id].update(
            status="error",
            error=f"{type(e).__name__}: {e}",
            finished_at=datetime.now(timezone.utc).isoformat(),
        )


@router.post("/swarm/run", response_model=SwarmRunResponse)
async def swarm_run(
    body: SwarmRunRequest,
    background: BackgroundTasks,
) -> SwarmRunResponse:
    # Verify the swarm package is importable before promising a job_id.
    try:
        import swarm.crew  # type: ignore  # noqa: F401
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"swarm package unavailable: {type(e).__name__}",
        ) from e

    job_id = f"job_{uuid.uuid4()}"
    _JOBS[job_id] = {
        "status": "queued",
        "started_at": None,
        "finished_at": None,
        "result": None,
        "error": None,
    }
    background.add_task(_spawn_job, job_id, body.objective, body.target_lead_id)
    return SwarmRunResponse(job_id=job_id, status="queued")


@router.get("/swarm/job/{job_id}", response_model=SwarmJobResponse)
async def swarm_job(job_id: str) -> SwarmJobResponse:
    job = _JOBS.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return SwarmJobResponse(job_id=job_id, **job)
