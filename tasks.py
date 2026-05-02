"""
SolarReach Codex Brain — Celery tasks
Async pitch generation, email variant optimization.
"""

from __future__ import annotations

import logging
from pathlib import Path

from codex_brain.celery_app import app
from codex_brain.generators.deck import generate_pitch, LeadBrief
from codex_brain.generators.email import rewrite_losing_variant, EmailVariant

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=2, default_retry_delay=10)
def task_generate_pitch(self, lead_id: str, brief_dict: dict, output_dir: str) -> dict:
    """
    Async pitch deck generation.
    Called by FastAPI background task or directly by Celery beat.
    """
    try:
        brief = LeadBrief(**brief_dict)
        result = generate_pitch(brief, Path(output_dir))
        return {
            "lead_id": lead_id,
            "pptx_path": str(result.pptx_path),
            "pdf_path": str(result.pdf_path) if result.pdf_path else None,
            "slide_count": len(result.slides),
            "cost_cents": result.usage.cost_cents,
            "cache_read_tokens": result.usage.cache_read_tokens,
        }
    except Exception as exc:
        logger.exception("task_generate_pitch failed for lead %s", lead_id)
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=1)
def task_rewrite_losing_email(
    self,
    losing_variant_dict: dict,
    winning_angle: str,
    open_rate: float,
    click_rate: float,
) -> dict:
    """
    Atlas Trigger → this task.
    Rewrites the losing email variant when SendGrid/Resend webhooks confirm a winner.
    """
    try:
        losing = EmailVariant(**losing_variant_dict)
        new_variant, usage = rewrite_losing_variant(
            losing=losing,
            winning_angle=winning_angle,
            open_rate=open_rate,
            click_rate=click_rate,
        )
        return {
            "variant": new_variant.variant,
            "subject": new_variant.subject,
            "body": new_variant.body,
            "angle": new_variant.angle,
            "cost_cents": usage.cost_cents,
        }
    except Exception as exc:
        logger.exception("task_rewrite_losing_email failed")
        raise self.retry(exc=exc)
