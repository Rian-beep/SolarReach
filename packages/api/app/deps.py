"""FastAPI dependency providers — Mongo client + settings.

Single AsyncIOMotorClient is reused across requests via app.state.
Tests override `get_db` with a mongomock client.
"""
from __future__ import annotations

from typing import Any

from fastapi import Request
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import Settings, get_settings


def get_mongo_client(request: Request) -> AsyncIOMotorClient:
    client = getattr(request.app.state, "mongo_client", None)
    if client is None:  # pragma: no cover — lifespan should set this
        settings = get_settings()
        client = AsyncIOMotorClient(settings.mongo_uri, serverSelectionTimeoutMS=2000)
        request.app.state.mongo_client = client
    return client


async def get_db(request: Request) -> AsyncIOMotorDatabase:
    settings = get_settings()
    client = get_mongo_client(request)
    return client[settings.mongo_db]


def get_app_settings() -> Settings:
    return get_settings()


__all__ = ["get_db", "get_mongo_client", "get_app_settings", "get_settings"]


# Re-export for tests that import via `from app import deps`.
def _placeholder_for_typing() -> Any:  # noqa: D401
    """Keeps motor imported even when unused at module top-level."""
    return None
