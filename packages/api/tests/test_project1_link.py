"""Tests for the project1 link layer (Atlas-side bridge to companion repo)."""
from __future__ import annotations

import pytest

from app.services.project1_link import (
    OUTREACH_EVENTS,
    fetch_project1_leads,
    push_outreach_event,
)


@pytest.mark.asyncio
async def test_fetch_project1_leads_returns_atlas_leads(mock_db):
    """With no agent-store notes available, we just return our canonical leads."""
    await mock_db.leads.insert_many(
        [
            {
                "_id": "lead_a",
                "client_id": "client-greensolar-uk",
                "postcode": "EC1Y 8AF",
                "scores": {"composite_score": 80},
                "created_at": "2026-01-01T00:00:00Z",
            },
            {
                "_id": "lead_b",
                "client_id": "client-greensolar-uk",
                "postcode": "EC1Y 8AF",
                "scores": {"composite_score": 60},
                "created_at": "2026-01-02T00:00:00Z",
            },
            {
                "_id": "lead_other_client",
                "client_id": "other-client",
                "postcode": "EC1Y 8AF",
                "scores": {"composite_score": 95},
            },
        ]
    )
    leads = await fetch_project1_leads(
        mock_db,
        client_id="client-greensolar-uk",
        postcode="EC1Y 8AF",
        limit=50,
        motor_client=None,
    )
    assert len(leads) == 2
    ids = {l["_id"] for l in leads}
    assert ids == {"lead_a", "lead_b"}
    # Sorted by composite_score desc
    assert leads[0]["_id"] == "lead_a"
    # No notes attached when no motor_client passed
    assert "project1_notes" not in leads[0]


@pytest.mark.asyncio
async def test_fetch_project1_leads_filters_postcode(mock_db):
    await mock_db.leads.insert_many(
        [
            {"_id": "l1", "client_id": "c1", "postcode": "EC1Y 8AF", "scores": {"composite_score": 50}},
            {"_id": "l2", "client_id": "c1", "postcode": "SW1 1AA", "scores": {"composite_score": 70}},
        ]
    )
    leads = await fetch_project1_leads(
        mock_db, client_id="c1", postcode="SW1 1AA", limit=50, motor_client=None
    )
    assert [l["_id"] for l in leads] == ["l2"]


@pytest.mark.asyncio
async def test_push_outreach_event_inserts_doc(mock_db):
    await mock_db.leads.insert_one({"_id": "lead_42"})
    inserted_id = await push_outreach_event(
        mock_db,
        lead_id="lead_42",
        event={
            "event_type": "email_sent",
            "payload": {"variant": "a"},
            "actor": "outreach_agent",
        },
    )
    assert inserted_id.startswith("oe_lead_42_")
    rows = await mock_db[OUTREACH_EVENTS].find({"lead_id": "lead_42"}).to_list(10)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "email_sent"
    assert rows[0]["payload"] == {"variant": "a"}


@pytest.mark.asyncio
async def test_outreach_event_endpoint_records_row(client, mock_db):
    await mock_db.leads.insert_one({"_id": "lead_xyz"})
    r = client.post(
        "/lead/lead_xyz/outreach_event",
        json={"event_type": "email_opened", "payload": {"variant": "b"}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["id"].startswith("oe_lead_xyz_")
    rows = await mock_db[OUTREACH_EVENTS].find({"lead_id": "lead_xyz"}).to_list(10)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "email_opened"


@pytest.mark.asyncio
async def test_outreach_event_endpoint_404_when_lead_missing(client):
    r = client.post(
        "/lead/lead_nope/outreach_event",
        json={"event_type": "email_opened"},
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_leads_augment_project1_returns_filtered(client, mock_db):
    """`/leads?augment=project1` runs through the link layer (which dedupes by id)."""
    await mock_db.leads.insert_many(
        [
            {
                "_id": "lp1",
                "client_id": "client-greensolar-uk",
                "postcode": "EC1Y 8AF",
                "scores": {"composite_score": 80},
            },
            {
                "_id": "lp2",
                "client_id": "client-greensolar-uk",
                "postcode": "SW1 1AA",
                "scores": {"composite_score": 60},
            },
        ]
    )
    r = client.get(
        "/leads?client_id=client-greensolar-uk&augment=project1&postcode=EC1Y%208AF"
    )
    assert r.status_code == 200, r.text
    rows = r.json()
    assert [row["_id"] for row in rows] == ["lp1"]
