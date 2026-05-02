"""Tests for POST /rian/run_agent + GET /rian/run_agent/{id}.

We don't pull in deepagents/LangGraph here. Instead we either let the route
hit its built-in demo_mode fallback (because `lead_agent` isn't installed in
the test venv) or we monkeypatch ``run_rian_agent`` to return a synthesised
result. Both paths assert the run document round-trips through Mongo.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _override_app_state_db(app, mock_db):
    """Mount the mongomock db on app.state.mongo_client so the router's
    ``_get_db`` helper resolves to it. Mirrors the swarm test pattern."""

    class _StubClient:
        def __getitem__(self, _name):
            return mock_db

        def close(self):
            return None

    app.state.mongo_client = _StubClient()


@pytest.mark.asyncio
async def test_post_run_agent_queues_and_persists(
    client: TestClient, mock_db, monkeypatch
) -> None:
    """POST returns a run_id and the doc is persisted with status=queued."""
    from app.main import app
    from app.services import rian_agent
    from app.services.rian_agent import RianAgentResult

    _override_app_state_db(app, mock_db)

    async def _fake_run_rian_agent(*, agent, target_lead_id, client_id, params):
        return RianAgentResult(
            status="ok",
            agent=agent,
            summary="ran ok",
            thread_id="t_test",
            message_count=4,
            metadata={"target_lead_id": target_lead_id},
        )

    monkeypatch.setattr(rian_agent, "run_rian_agent", _fake_run_rian_agent)
    # The router imports run_rian_agent by name, so patch the binding inside
    # the router module too.
    from app.routers import rian as rian_router

    monkeypatch.setattr(rian_router, "run_rian_agent", _fake_run_rian_agent)

    r = client.post(
        "/rian/run_agent",
        json={
            "agent": "lead_research",
            "target_lead_id": "lead_abc",
            "client_id": "client-greensolar-uk",
            "params": {"batch_size": 1},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["run_id"].startswith("rian_")
    run_id = body["run_id"]

    # Background task ran and finalised the doc.
    doc = await mock_db.rian_agent_runs.find_one({"_id": run_id})
    assert doc is not None
    # The status migrates from "queued" → "running" → "done" — by the time
    # the BackgroundTasks have flushed (TestClient awaits them), the doc
    # should be at "done" because the fake returns status="ok".
    assert doc["status"] == "done"
    assert doc["agent"] == "lead_research"
    assert doc["target_lead_id"] == "lead_abc"
    assert doc["output"]["status"] == "ok"
    assert doc["output"]["summary"] == "ran ok"
    assert doc["output"]["thread_id"] == "t_test"
    assert doc["output"]["message_count"] == 4


@pytest.mark.asyncio
async def test_run_agent_demo_mode_when_lead_agent_missing(
    client: TestClient, mock_db
) -> None:
    """Without ``lead_agent`` installed in the venv (the default in CI), the
    run should resolve to status="demo_mode" with a stub payload — never error.
    """
    from app.main import app

    _override_app_state_db(app, mock_db)

    r = client.post(
        "/rian/run_agent",
        json={
            "agent": "lead_research",
            "target_lead_id": "lead_xyz",
            "client_id": "client-greensolar-uk",
        },
    )
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    doc = await mock_db.rian_agent_runs.find_one({"_id": run_id})
    assert doc is not None
    # demo_mode comes from the dataclass status (lead_agent isn't importable)
    assert doc["status"] == "demo_mode"
    assert doc["output"]["status"] == "demo_mode"
    assert doc["output"]["metadata"]["stub"] is True
    assert "lead_agent" in doc["output"]["summary"].lower()


@pytest.mark.asyncio
async def test_run_agent_unknown_agent_kind(
    client: TestClient, mock_db
) -> None:
    """Unknown agent strings resolve to demo_mode — the router never 400s on
    a future-named agent, so Rian can ship new agents without us first
    having to ship a server release."""
    from app.main import app

    _override_app_state_db(app, mock_db)

    r = client.post(
        "/rian/run_agent",
        json={"agent": "future_unreleased_agent", "target_lead_id": None},
    )
    assert r.status_code == 200
    run_id = r.json()["run_id"]

    doc = await mock_db.rian_agent_runs.find_one({"_id": run_id})
    assert doc is not None
    assert doc["status"] == "demo_mode"
    assert "unknown agent" in doc["output"]["summary"].lower()


def test_get_run_agent_404_for_unknown(client: TestClient, mock_db) -> None:
    from app.main import app

    _override_app_state_db(app, mock_db)
    r = client.get("/rian/run_agent/rian_does_not_exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_run_agent_round_trips(client: TestClient, mock_db) -> None:
    """Direct doc-write → GET surfaces it through the response model."""
    from app.main import app

    _override_app_state_db(app, mock_db)

    await mock_db.rian_agent_runs.insert_one(
        {
            "_id": "rian_abc123",
            "status": "done",
            "agent": "lead_research",
            "target_lead_id": "lead_42",
            "started_at": "2026-05-02T15:00:00+00:00",
            "finished_at": "2026-05-02T15:00:30+00:00",
            "output": {
                "status": "ok",
                "agent": "lead_research",
                "summary": "scored 1 lead",
                "thread_id": "t_xyz",
                "message_count": 8,
                "metadata": {"target_lead_id": "lead_42"},
            },
            "error": None,
        }
    )

    r = client.get("/rian/run_agent/rian_abc123")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["agent"] == "lead_research"
    assert body["target_lead_id"] == "lead_42"
    assert body["output"]["summary"] == "scored 1 lead"
    assert body["output"]["thread_id"] == "t_xyz"
