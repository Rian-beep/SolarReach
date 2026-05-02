"""GET /health — returns service statuses.

Never throws, never 5xx, never hangs. Each probe wrapped in a 2s timeout.
Frontend ATLAS LIVE pill flips amber/red based on which services are False.
"""
from __future__ import annotations

import asyncio
import socket
from urllib.parse import urlparse

from fastapi import APIRouter, Depends
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.config import Settings
from app.deps import get_app_settings, get_db

router = APIRouter()

PROBE_TIMEOUT_S = 2.0


async def _probe_mongo(db: AsyncIOMotorDatabase) -> bool:
    try:
        await asyncio.wait_for(db.command("ping"), timeout=PROBE_TIMEOUT_S)
        return True
    except (asyncio.TimeoutError, Exception):
        return False


async def _probe_redis(redis_url: str) -> bool:
    """Cheap TCP-connect to host:port. No protocol handshake — we just want to
    know the box is reachable. If the URL is malformed or anything fails, we
    return False rather than crashing the endpoint."""
    if not redis_url:
        return False
    try:
        parsed = urlparse(redis_url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 6379
    except Exception:
        return False

    def _connect() -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(PROBE_TIMEOUT_S)
            s.connect((host, port))
        return True

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(_connect), timeout=PROBE_TIMEOUT_S
        )
    except (asyncio.TimeoutError, OSError, Exception):
        return False


@router.get("/health")
async def health(
    db: AsyncIOMotorDatabase = Depends(get_db),
    settings: Settings = Depends(get_app_settings),
) -> dict:
    # Probes run in parallel so worst-case latency is one timeout, not three.
    # return_exceptions=True is belt-and-braces: even if a probe regresses
    # and stops swallowing its own errors, /health stays a 200.
    results = await asyncio.gather(
        _probe_mongo(db),
        _probe_redis(settings.redis_url),
        return_exceptions=True,
    )
    mongo_ok = results[0] is True
    redis_ok = results[1] is True
    anthropic_reachable = bool(settings.anthropic_api_key)

    services: dict[str, bool] = {
        "mongo": mongo_ok,
        "anthropic_reachable": anthropic_reachable,
        "redis": redis_ok,
    }
    status = "ok" if all(services.values()) else "degraded"
    return {"status": status, "services": services}
