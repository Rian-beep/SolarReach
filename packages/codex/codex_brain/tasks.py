"""Celery tasks — async generators bridged via asyncio.run().

Each task:
- fetches the lead from Mongo (motor) by lead_id
- builds an AnthropicClient from env
- runs the appropriate generator
- writes the artifact back to Mongo
- appends an audit_log entry (best-effort import — falls back to no-op)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import os
import uuid
from pathlib import Path
from typing import Any

from .celery_app import celery_app


def _utcnow_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _sha256_hex(s: str | None) -> str | None:
    if not s:
        return None
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


async def _audit(db, *, actor: str, action: str, lead_id: str | None, cost_cents: float,
                 metadata: dict | None = None, recipient_email: str | None = None) -> None:
    """Append-only audit row. Recipient emails MUST be hashed (cardinal rule 7)."""
    if db is None:
        return
    try:
        # Prefer a shared API service if available
        from solarreach_api.services.audit import log_audit  # type: ignore
        await log_audit(
            actor=actor,
            action=action,
            lead_id=lead_id,
            cost_cents=cost_cents,
            metadata=metadata or {},
            recipient_sha256=_sha256_hex(recipient_email),
        )
        return
    except Exception:
        pass  # fall through to direct insert
    try:
        await db.audit_log.insert_one({
            "_id": f"audit_{uuid.uuid4().hex}",
            "ts": _utcnow_iso(),
            "actor": actor,
            "action": action,
            "lead_id": lead_id,
            "cost_cents": cost_cents,
            "recipient_sha256": _sha256_hex(recipient_email),
            "metadata": metadata or {},
        })
    except Exception:
        pass  # never break the pipeline on audit failure


async def _get_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/?authSource=admin")
    if "?" not in uri:
        uri = uri + "?authSource=admin"
    elif "authSource=" not in uri:
        uri = uri + "&authSource=admin"
    db_name = os.environ.get("MONGO_DB", "solarreach")
    return AsyncIOMotorClient(uri)[db_name]


def _anthropic_client(model: str = "claude-sonnet-4-6"):
    from .anthropic_client import AnthropicClient
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return AnthropicClient(api_key=key, model=model)


# -------------------------------------------------------------------- #
# generate_pitch_task                                                   #
# -------------------------------------------------------------------- #
async def _generate_pitch(lead_id: str, client_id: str) -> dict[str, Any]:
    from .generators.deck import generate_deck
    from .generators.pptx_renderer import render_pptx
    from .generators.pdf_converter import pptx_to_pdf
    from .generators.email import generate_email_variants

    db = await _get_db()
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise ValueError(f"lead not found: {lead_id}")
    client_doc = await db.clients.find_one({"_id": client_id}) or {}

    sonnet = _anthropic_client("claude-sonnet-4-6")
    dm = lead.get("decision_maker") or {"name": "Unknown", "role": "Director", "confidence": 0.4}

    deck_result = await generate_deck(lead, sonnet, dm)
    brand = client_doc.get("branding") or {}
    brand.setdefault("name", client_doc.get("name", ""))

    out_dir = Path("/tmp/decks")
    pptx_path = render_pptx(deck_result.deck_json, brand, lead_id=lead_id, out_dir=out_dir)
    try:
        pdf_path = pptx_to_pdf(pptx_path, out_dir=out_dir)
    except Exception:
        pdf_path = None  # Non-fatal: PDF is a nice-to-have on first run

    emails = await generate_email_variants(lead, dm, sonnet)

    artifacts = {
        "deck_json": deck_result.deck_json,
        "pptx_path": str(pptx_path),
        "pdf_path": str(pdf_path) if pdf_path else None,
        "emails": emails,
        "generated_at": _utcnow_iso(),
        "cost_cents": deck_result.cost_cents,
    }
    await db.leads.update_one(
        {"_id": lead_id},
        {"$set": {"pitch_artifacts": artifacts, "updated_at": _utcnow_iso()}},
    )
    await _audit(
        db,
        actor="agent_codex_brain",
        action="lead.pitch",
        lead_id=lead_id,
        cost_cents=deck_result.cost_cents,
        metadata={
            "model": "claude-sonnet-4-6",
            "in_tokens": deck_result.in_tokens,
            "out_tokens": deck_result.out_tokens,
            "cache_read_tokens": deck_result.cache_read_tokens,
            "cache_create_tokens": deck_result.cache_create_tokens,
            "client_id": client_id,
        },
    )
    return artifacts


@celery_app.task(name="codex.generate_pitch")
def generate_pitch_task(lead_id: str, client_id: str) -> dict[str, Any]:
    return asyncio.run(_generate_pitch(lead_id, client_id))


# -------------------------------------------------------------------- #
# infer_decision_maker_task                                             #
# -------------------------------------------------------------------- #
async def _infer_decision_maker(lead_id: str) -> dict[str, Any]:
    from .generators.org_chart import infer_decision_maker

    db = await _get_db()
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise ValueError(f"lead not found: {lead_id}")
    company_id = (lead.get("owner") or {}).get("company_id")
    directors: list[dict[str, Any]] = []
    if company_id:
        cursor = db.directors.find({"company_id": company_id})
        directors = [d async for d in cursor]

    opus = _anthropic_client("claude-opus-4-7")
    dm = await infer_decision_maker(directors, lead, client=opus, model="claude-opus-4-7")
    dm_dict = dm.to_dict()
    await db.leads.update_one(
        {"_id": lead_id},
        {"$set": {"decision_maker": dm_dict, "updated_at": _utcnow_iso()}},
    )
    await _audit(
        db,
        actor="agent_codex_brain",
        action="lead.decision_maker",
        lead_id=lead_id,
        cost_cents=0.0,  # cost rolled into deck/email tasks; this is best-effort
        metadata={"role": dm.role, "confidence": dm.confidence},
    )
    return dm_dict


@celery_app.task(name="codex.infer_decision_maker")
def infer_decision_maker_task(lead_id: str) -> dict[str, Any]:
    return asyncio.run(_infer_decision_maker(lead_id))


# -------------------------------------------------------------------- #
# generate_emails_task                                                  #
# -------------------------------------------------------------------- #
async def _generate_emails(lead_id: str) -> dict[str, Any]:
    from .generators.email import generate_email_variants

    db = await _get_db()
    lead = await db.leads.find_one({"_id": lead_id})
    if not lead:
        raise ValueError(f"lead not found: {lead_id}")
    dm = lead.get("decision_maker") or {"name": "Unknown", "role": "Director"}
    sonnet = _anthropic_client("claude-sonnet-4-6")
    variants = await generate_email_variants(lead, dm, sonnet)
    await db.leads.update_one(
        {"_id": lead_id},
        {"$set": {"pitch_artifacts.emails": variants, "updated_at": _utcnow_iso()}},
    )
    await _audit(
        db,
        actor="agent_codex_brain",
        action="lead.emails",
        lead_id=lead_id,
        cost_cents=0.0,
        metadata={"variants": list(variants.keys())},
    )
    return variants


@celery_app.task(name="codex.generate_emails")
def generate_emails_task(lead_id: str) -> dict[str, Any]:
    return asyncio.run(_generate_emails(lead_id))
