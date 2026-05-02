"""Smoke tests for the /swarm/run + /swarm/job endpoints.

We don't kick off the live crew (that hits Anthropic). Instead we monkeypatch
`_run_crew_async` so the background task resolves with a canned manager
response, and we assert:
  - POST /swarm/run returns a job_id and queues a Mongo doc
  - GET /swarm/job/{id} reads the doc back through the contract shape
  - 404 on unknown job_id
  - 503 when the swarm package is not importable
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _override_app_state_db(app, mock_db):
    """Mount the mongomock db on app.state.mongo_client so the router's
    `_get_db` helper returns it.
    """

    class _StubClient:
        def __getitem__(self, _name):
            return mock_db

        def close(self):
            return None

    app.state.mongo_client = _StubClient()


def test_swarm_run_returns_job_id(client: TestClient, mock_db, monkeypatch):
    from app.main import app
    from app.routers import swarm as swarm_router

    _override_app_state_db(app, mock_db)

    async def _fake_run_crew(objective, target_lead_id):
        return f"manager plan for {objective[:30]} (lead={target_lead_id})"

    monkeypatch.setattr(swarm_router, "_run_crew_async", _fake_run_crew)

    r = client.post(
        "/swarm/run",
        json={"objective": "Pitch the top-3 EC1Y leads", "target_lead_id": None},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["job_id"].startswith("job_")


def test_swarm_run_unavailable_when_package_missing(
    client: TestClient, monkeypatch
) -> None:
    """If `swarm.crew` can't be imported, the router 503s so the UI can show
    a clear error instead of swallowing the failure inside a background task.
    """
    import builtins

    real_import = builtins.__import__

    def _raise_for_swarm(name, *args, **kwargs):
        if name == "swarm.crew" or name.startswith("swarm.crew"):
            raise ModuleNotFoundError("swarm.crew")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _raise_for_swarm)

    r = client.post(
        "/swarm/run",
        json={"objective": "ping", "target_lead_id": None},
    )
    assert r.status_code == 503
    assert "swarm package unavailable" in r.json()["detail"]


def test_swarm_job_404_for_unknown(client: TestClient, mock_db) -> None:
    from app.main import app

    _override_app_state_db(app, mock_db)

    r = client.get("/swarm/job/job_does_not_exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_swarm_job_reads_doc_from_mongo(
    client: TestClient, mock_db
) -> None:
    """End-to-end shape check: writing a job doc directly should round-trip
    through GET /swarm/job/{id} into the response model.
    """
    from app.main import app

    _override_app_state_db(app, mock_db)

    await mock_db.swarm_jobs.insert_one(
        {
            "_id": "job_test_done",
            "status": "done",
            "started_at": "2026-05-02T15:00:00+00:00",
            "finished_at": "2026-05-02T15:00:30+00:00",
            "result": "manager-plan",
            "error": None,
            "artifacts": {
                "pptx_url": "/static/swarm/decks/foo.pptx",
                "mp3_url": None,
                "research_bullets": ["bullet a", "bullet b"],
            },
        }
    )

    r = client.get("/swarm/job/job_test_done")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["result"] == "manager-plan"
    assert body["artifacts"]["pptx_url"] == "/static/swarm/decks/foo.pptx"
    assert body["artifacts"]["research_bullets"] == ["bullet a", "bullet b"]
