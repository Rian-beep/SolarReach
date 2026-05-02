"""GET /health — returns service statuses.

Never throws. Reports degraded when subsystems fail.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings
from app.deps import get_db, get_app_settings

router = APIRouter()


@router.get("/health")
async def health(
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    services: dict[str, bool | str] = {}

    # Mongo ping
    try:
        await db.command("ping")
        services["mongo"] = True
    except Exception as e:  # pragma: no cover
        services["mongo"] = f"error: {type(e).__name__}"

    # Anthropic key presence is the cheap reachability proxy
    services["anthropic_reachable"] = bool(settings.anthropic_api_key)

    # Redis — presence of URL only (no TCP poke at /health to keep it fast)
    services["redis"] = bool(settings.redis_url)

    status = "ok" if all(v is True for v in services.values()) else "degraded"
    return {"status": status, "services": services}
