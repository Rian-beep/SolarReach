"""Tests for POST /integration/agent_event — Rian inbound integration."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_agent_event_dev_open_when_no_token(client, mock_db, monkeypatch):
    """No RIAN_INTEGRATION_TOKEN set → dev_open mode, accepts unauthenticated calls."""
    monkeypatch.delenv("RIAN_INTEGRATION_TOKEN", raising=False)

    r = client.post(
        "/integration/agent_event",
        json={
            "source": "rian-project1",
            "agent": "research",
            "event_type": "trace.start",
            "lead_id": "lead_abc",
            "trace_id": "t_123",
            "payload": {"step": 1},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["auth_status"] == "dev_open"
    assert body["id"].startswith("ae_")

    # Persisted to agent_events
    docs = await mock_db.agent_events.find({}).to_list(length=10)
    assert len(docs) == 1
    assert docs[0]["agent"] == "research"
    assert docs[0]["event_type"] == "trace.start"
    assert docs[0]["lead_id"] == "lead_abc"
    assert docs[0]["payload"] == {"step": 1}

    # Mirrored to audit_log
    audit = await mock_db.audit_log.find({}).to_list(length=10)
    assert len(audit) == 1
    assert audit[0]["action"] == "integration.agent_event"
    assert audit[0]["actor"] == "rian-project1/research"
    assert audit[0]["metadata"]["auth_status"] == "dev_open"


@pytest.mark.asyncio
async def test_agent_event_rejects_missing_token_when_configured(
    client, mock_db, monkeypatch
):
    """Token configured + no Authorization header → 401."""
    monkeypatch.setenv("RIAN_INTEGRATION_TOKEN", "secret-token")

    r = client.post(
        "/integration/agent_event",
        json={"agent": "research", "event_type": "trace.start"},
    )
    assert r.status_code == 401
    docs = await mock_db.agent_events.find({}).to_list(length=10)
    assert docs == []


@pytest.mark.asyncio
async def test_agent_event_rejects_wrong_token(client, mock_db, monkeypatch):
    """Token configured + bad bearer → 401."""
    monkeypatch.setenv("RIAN_INTEGRATION_TOKEN", "secret-token")

    r = client.post(
        "/integration/agent_event",
        json={"agent": "research", "event_type": "trace.start"},
        headers={"Authorization": "Bearer not-the-right-one"},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_agent_event_accepts_correct_token(client, mock_db, monkeypatch):
    """Matching bearer token → 200, auth_status='authenticated'."""
    monkeypatch.setenv("RIAN_INTEGRATION_TOKEN", "secret-token")

    r = client.post(
        "/integration/agent_event",
        json={"agent": "outreach", "event_type": "lead.note"},
        headers={"Authorization": "Bearer secret-token"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["auth_status"] == "authenticated"

    docs = await mock_db.agent_events.find({}).to_list(length=10)
    assert len(docs) == 1
    assert docs[0]["agent"] == "outreach"


@pytest.mark.asyncio
async def test_agent_event_validates_required_fields(client, monkeypatch):
    """Missing `agent` / `event_type` → 422 from pydantic."""
    monkeypatch.delenv("RIAN_INTEGRATION_TOKEN", raising=False)

    r = client.post("/integration/agent_event", json={"source": "x"})
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_agent_event_server_stamps_ts_when_absent(client, mock_db, monkeypatch):
    """No ts in body → server stamps one."""
    monkeypatch.delenv("RIAN_INTEGRATION_TOKEN", raising=False)

    r = client.post(
        "/integration/agent_event",
        json={"agent": "research", "event_type": "trace.start"},
    )
    assert r.status_code == 200
    docs = await mock_db.agent_events.find({}).to_list(length=10)
    assert len(docs) == 1
    assert docs[0]["ts"]  # ISO-8601 string, server-stamped
    assert "T" in docs[0]["ts"]
