"""Shared pytest fixtures.

We use mongomock-motor to fake the AsyncIOMotorClient so tests run without a
real Mongo. The app's get_db dependency is overridden in `client` fixture.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient

# Force minimal env BEFORE app import so Settings picks up safe defaults.
os.environ.setdefault("SOLARREACH_LIVE_OUTBOUND", "false")
os.environ.setdefault("ANTHROPIC_API_KEY", "")
os.environ.setdefault("ELEVENLABS_API_KEY", "")
os.environ.setdefault("MONGO_URI", "mongodb://localhost:27017/?authSource=admin")
os.environ.setdefault("MONGO_DB", "solarreach_test")
# Force-clear Google key so tests don't accidentally hit live Solar API.
# (`.env.local` would otherwise leak in via pydantic-settings.)
os.environ["GOOGLE_MAPS_API_KEY"] = ""


@pytest_asyncio.fixture
async def mock_db() -> AsyncIterator:
    client = AsyncMongoMockClient()
    db = client["solarreach_test"]
    yield db


@pytest.fixture
def client(mock_db, monkeypatch) -> TestClient:
    from app import deps
    from app.main import app

    async def _get_db_override():
        return mock_db

    app.dependency_overrides[deps.get_db] = _get_db_override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
