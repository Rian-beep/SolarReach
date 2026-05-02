"""Smoke tests for /langchain/run + /langchain/job/{id}.

Mirrors test_swarm.py: we don't kick the live ReAct agent (it would call
Anthropic). Instead we monkeypatch ``_run_agent`` so the background task
resolves with a canned result, and we assert:
  - POST /langchain/run returns a job_id and persists a Mongo doc
  - GET /langchain/job/{id} round-trips through the contract shape
  - 404 on unknown job_id
  - 503 when the bridge module is not importable
  - the agent's error path produces status="error" with the error preserved
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _override_app_state_db(app, mock_db):
    """Mount the mongomock db on app.state.mongo_client so the router's
    ``_get_db`` helper resolves to it. Same shim as test_swarm/test_rian."""

    class _StubClient:
        def __getitem__(self, _name):
            return mock_db

        def close(self):
            return None

    app.state.mongo_client = _StubClient()


def test_langchain_run_returns_job_id(
    client: TestClient, mock_db, monkeypatch
) -> None:
    from app.main import app
    from app.routers import langchain_router as lc_router

    _override_app_state_db(app, mock_db)

    async def _fake_run_agent(lead_id, prompt, model, max_iter):
        return {
            "output": f"draft for {lead_id} re: {prompt[:20]}",
            "intermediate_steps": [
                {
                    "tool": "atlas_query",
                    "tool_input": {"filter": {"_id": lead_id}},
                    "log": "Action: atlas_query\n",
                    "observation": "{'ok': True, 'data': [{'_id': '" + lead_id + "'}]}",
                },
                {
                    "tool": "pull_industry_benchmarks",
                    "tool_input": {},
                    "log": "Action: pull_industry_benchmarks\n",
                    "observation": "{'ok': True, 'key_count': 18}",
                },
            ],
            "cost_cents": 1.234,
            "model": "claude-sonnet-4-6",
            "lead_id": lead_id,
            "in_tokens": 1200,
            "out_tokens": 250,
        }

    monkeypatch.setattr(lc_router, "_run_agent", _fake_run_agent)

    r = client.post(
        "/langchain/run",
        json={
            "lead_id": "lead_codenode_demo",
            "prompt": "Draft an executive intro email focusing on the £41k NPV.",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["job_id"].startswith("lc_")


def test_langchain_run_unavailable_when_bridge_missing(
    client: TestClient, monkeypatch
) -> None:
    """If ``swarm.langchain_bridge`` can't be imported, the POST 503s up front
    so the UI can surface a clear error instead of seeing a queued job die
    silently in the background task."""
    import builtins

    real_import = builtins.__import__

    def _raise_for_bridge(name, *args, **kwargs):
        if name == "swarm.langchain_bridge" or name.startswith("swarm.langchain_bridge"):
            raise ModuleNotFoundError("swarm.langchain_bridge")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _raise_for_bridge)

    r = client.post(
        "/langchain/run",
        json={"lead_id": "lead_x", "prompt": "ping"},
    )
    assert r.status_code == 503
    assert "langchain bridge unavailable" in r.json()["detail"]


def test_langchain_job_404_for_unknown(client: TestClient, mock_db) -> None:
    from app.main import app

    _override_app_state_db(app, mock_db)

    r = client.get("/langchain/job/lc_does_not_exist")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_langchain_run_persists_done_doc(
    client: TestClient, mock_db, monkeypatch
) -> None:
    """End-to-end: POST kicks the background task, the fake agent resolves,
    and the job doc is at status=done with intermediate_steps preserved."""
    from app.main import app
    from app.routers import langchain_router as lc_router

    _override_app_state_db(app, mock_db)

    async def _fake_run_agent(lead_id, prompt, model, max_iter):
        return {
            "output": "Final answer.",
            "intermediate_steps": [
                {
                    "tool": "atlas_query",
                    "tool_input": {"filter": {"_id": lead_id}},
                    "log": "Action: atlas_query",
                    "observation": "ok",
                }
            ],
            "cost_cents": 0.5,
            "model": "claude-sonnet-4-6",
            "lead_id": lead_id,
            "in_tokens": 500,
            "out_tokens": 100,
        }

    monkeypatch.setattr(lc_router, "_run_agent", _fake_run_agent)

    r = client.post(
        "/langchain/run",
        json={"lead_id": "lead_abc", "prompt": "research please"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    doc = await mock_db.langchain_jobs.find_one({"_id": job_id})
    assert doc is not None
    # By the time TestClient flushes BackgroundTasks, status should be done.
    assert doc["status"] == "done"
    assert doc["lead_id"] == "lead_abc"
    assert doc["output"] == "Final answer."
    assert doc["cost_cents"] == 0.5
    assert len(doc["intermediate_steps"]) == 1
    assert doc["intermediate_steps"][0]["tool"] == "atlas_query"


@pytest.mark.asyncio
async def test_langchain_run_records_agent_error(
    client: TestClient, mock_db, monkeypatch
) -> None:
    """When ``arun`` returns ``error`` in its result dict, the job status
    propagates to "error" so the UI can show the failure mode."""
    from app.main import app
    from app.routers import langchain_router as lc_router

    _override_app_state_db(app, mock_db)

    async def _fake_run_agent(lead_id, prompt, model, max_iter):
        return {
            "output": "",
            "intermediate_steps": [],
            "cost_cents": 0.0,
            "model": "claude-sonnet-4-6",
            "lead_id": lead_id,
            "error": "build_agent_failed:RuntimeError: ANTHROPIC_API_KEY unset",
        }

    monkeypatch.setattr(lc_router, "_run_agent", _fake_run_agent)

    r = client.post(
        "/langchain/run",
        json={"lead_id": "lead_y", "prompt": "boom"},
    )
    assert r.status_code == 200
    job_id = r.json()["job_id"]
    doc = await mock_db.langchain_jobs.find_one({"_id": job_id})
    assert doc is not None
    assert doc["status"] == "error"
    assert "ANTHROPIC_API_KEY" in doc["error"]


@pytest.mark.asyncio
async def test_langchain_job_round_trips(client: TestClient, mock_db) -> None:
    """Direct doc-write → GET surfaces it through the response model."""
    from app.main import app

    _override_app_state_db(app, mock_db)

    await mock_db.langchain_jobs.insert_one(
        {
            "_id": "lc_test_done",
            "status": "done",
            "lead_id": "lead_codenode_demo",
            "prompt": "summary please",
            "model": "claude-sonnet-4-6",
            "started_at": "2026-05-02T15:00:00+00:00",
            "finished_at": "2026-05-02T15:00:30+00:00",
            "output": "Here are the 3 strongest reasons.",
            "intermediate_steps": [
                {
                    "tool": "pull_industry_benchmarks",
                    "tool_input": {},
                    "log": "Action: pull_industry_benchmarks",
                    "observation": "{'ok': True, 'key_count': 18}",
                }
            ],
            "cost_cents": 2.5,
            "error": None,
        }
    )

    r = client.get("/langchain/job/lc_test_done")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "done"
    assert body["lead_id"] == "lead_codenode_demo"
    assert body["output"].startswith("Here are")
    assert body["cost_cents"] == 2.5
    assert len(body["intermediate_steps"]) == 1
    assert body["intermediate_steps"][0]["tool"] == "pull_industry_benchmarks"
