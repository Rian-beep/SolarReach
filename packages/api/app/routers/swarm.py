"""POST /swarm/run + GET /swarm/job/{id} — async crew dispatch.

Jobs are persisted in the `swarm_jobs` Mongo collection (see CONTRACTS § 1)
so they survive API restarts and can be polled from any process. The crew
itself is heavy (CrewAI hierarchical + Anthropic) so we run it in a worker
thread (CrewAI is sync internally) via FastAPI's BackgroundTasks.

Job lifecycle:
    queued → running → done | error

When done, the `result` field carries the manager's final markdown summary
plus an `artifacts` block scraped from any `/tmp/swarm-decks` and
`/tmp/swarm-tts` files produced by the specialists.

Why no Celery here:
- The existing API already spawns Celery for the codex pitch path. The swarm
  is short-lived (sub-minute) and benefits from sharing the API process's
  Mongo client + audit pipeline. A future move to Celery would only require
  swapping `_spawn_job` body for a `tasks.run_swarm.delay(...)`.
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel, Field

log = logging.getLogger("solarreach.api.swarm")
router = APIRouter()

_COLLECTION = "swarm_jobs"
_DECK_DIR = Path("/tmp/swarm-decks")
_TTS_DIR = Path("/tmp/swarm-tts")


class SwarmRunRequest(BaseModel):
    objective: str = Field(..., min_length=1, max_length=2000)
    target_lead_id: str | None = None


class SwarmRunResponse(BaseModel):
    job_id: str
    status: str


class SwarmArtifacts(BaseModel):
    pptx_url: str | None = None
    mp3_url: str | None = None
    research_bullets: list[str] = []


class SwarmJobResponse(BaseModel):
    job_id: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None
    result: str | None = None
    error: str | None = None
    artifacts: SwarmArtifacts | None = None


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
        log.warning("swarm_jobs update failed (%s): %s", job_id, type(e).__name__)


def _scrape_artifacts(target_lead_id: str | None) -> SwarmArtifacts:
    """Pick the freshest pptx/mp3 for the lead from the swarm output dirs."""
    pptx_url: str | None = None
    mp3_url: str | None = None
    try:
        # Prefer files matching the target lead, else fall back to newest.
        if _DECK_DIR.exists():
            decks = sorted(
                _DECK_DIR.glob("*.pptx"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            if target_lead_id:
                for p in decks:
                    if target_lead_id in p.name:
                        pptx_url = f"/static/swarm/decks/{p.name}"
                        break
            if pptx_url is None and decks:
                pptx_url = f"/static/swarm/decks/{decks[0].name}"
    except Exception as e:  # noqa: BLE001
        log.warning("scrape decks failed: %s", type(e).__name__)
    try:
        if _TTS_DIR.exists():
            mp3s = sorted(
                _TTS_DIR.glob("*.mp3"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            if mp3s:
                mp3_url = f"/static/swarm/tts/{mp3s[0].name}"
    except Exception as e:  # noqa: BLE001
        log.warning("scrape tts failed: %s", type(e).__name__)
    return SwarmArtifacts(pptx_url=pptx_url, mp3_url=mp3_url, research_bullets=[])


_BULLET_RE = re.compile(r"^[\s]*[-*•]\s+(.+)$", re.MULTILINE)


def _extract_bullets(text: str, limit: int = 8) -> list[str]:
    if not text:
        return []
    bullets = [m.group(1).strip() for m in _BULLET_RE.finditer(text)]
    # de-dupe while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for b in bullets:
        if b in seen:
            continue
        seen.add(b)
        out.append(b)
        if len(out) >= limit:
            break
    return out


async def _run_crew_async(objective: str, target_lead_id: str | None) -> str:
    """Run the crew in a worker thread (CrewAI is sync internally)."""
    # Import lazily so the API can boot even if `solarreach-swarm` isn't
    # installed in this venv yet — endpoint then 503s with a clear error.
    from swarm.crew import build_crew  # type: ignore

    def _kick() -> str:
        crew = build_crew(objective=objective, target_lead_id=target_lead_id)
        return str(
            crew.kickoff(
                inputs={
                    "objective": objective,
                    "target_lead_id": target_lead_id or "",
                }
            )
        )

    return await asyncio.to_thread(_kick)


async def _spawn_job(
    db, job_id: str, objective: str, target_lead_id: str | None
) -> None:
    await _set_job(db, job_id, status="running", started_at=_now_iso())
    try:
        result = await _run_crew_async(objective, target_lead_id)
        artifacts = _scrape_artifacts(target_lead_id)
        artifacts.research_bullets = _extract_bullets(result)
        await _set_job(
            db,
            job_id,
            status="done",
            result=result,
            artifacts=artifacts.model_dump(),
            finished_at=_now_iso(),
        )
    except Exception as e:  # noqa: BLE001
        log.warning("swarm job %s failed: %s", job_id, type(e).__name__)
        await _set_job(
            db,
            job_id,
            status="error",
            error=f"{type(e).__name__}: {e}",
            finished_at=_now_iso(),
        )


@router.post("/swarm/run", response_model=SwarmRunResponse)
async def swarm_run(
    body: SwarmRunRequest,
    background: BackgroundTasks,
    request: Request,
) -> SwarmRunResponse:
    # Verify the swarm package is importable before promising a job_id.
    try:
        import swarm.crew  # type: ignore  # noqa: F401
    except Exception as e:  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail=f"swarm package unavailable: {type(e).__name__}",
        ) from e

    db = _get_db(request)
    job_id = f"job_{uuid.uuid4()}"
    await _set_job(
        db,
        job_id,
        status="queued",
        objective=body.objective,
        target_lead_id=body.target_lead_id,
        started_at=None,
        finished_at=None,
        result=None,
        error=None,
        artifacts=None,
        created_at=_now_iso(),
    )
    background.add_task(_spawn_job, db, job_id, body.objective, body.target_lead_id)
    return SwarmRunResponse(job_id=job_id, status="queued")


@router.get("/swarm/job/{job_id}", response_model=SwarmJobResponse)
async def swarm_job(job_id: str, request: Request) -> SwarmJobResponse:
    db = _get_db(request)
    if db is None:
        raise HTTPException(status_code=503, detail="mongo unavailable")
    job = await db[_COLLECTION].find_one({"_id": job_id})
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    artifacts_doc = job.get("artifacts")
    return SwarmJobResponse(
        job_id=job_id,
        status=job.get("status", "unknown"),
        started_at=job.get("started_at"),
        finished_at=job.get("finished_at"),
        result=job.get("result"),
        error=job.get("error"),
        artifacts=SwarmArtifacts(**artifacts_doc) if artifacts_doc else None,
    )
