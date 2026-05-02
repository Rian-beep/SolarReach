"""Celery application — wired to Redis broker/back-end.

Tasks:
  - generate_pitch_task(lead_id, client_id)
  - infer_decision_maker_task(lead_id)
  - generate_emails_task(lead_id)

Each task wraps the async generator with asyncio.run() per the spec.
"""

from __future__ import annotations

import os

from celery import Celery


REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "codex_brain",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["codex_brain.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=120,
    task_soft_time_limit=90,
    timezone="UTC",
    enable_utc=True,
)


# Re-export for convenience: `from codex_brain.celery_app import celery_app`
__all__ = ["celery_app"]
