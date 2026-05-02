import pytest


def test_scan_creates_job_and_returns_stream_url(client):
    body = {
        "postcode": "EC1Y 8AF",
        "client_id": "client-greensolar-uk",
        "limit": 10,
    }
    r = client.post("/scan", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "scan_id" in data
    assert "lead_count" in data
    assert data["stream_url"] == f"/scan/{data['scan_id']}/stream"


@pytest.mark.asyncio
async def test_scan_stream_progress_total_matches_lead_count(client, mock_db):
    """CONTRACTS § 3 reconciliation: scan.lead_count, every progress.total,
    and done.lead_count must agree. Previously progress.total quoted the
    request `limit` (50) while only ~3 real leads existed, producing a
    "3 / 50" progress bar.
    """
    # Seed three real leads matching postcode + client.
    await mock_db.leads.insert_many(
        [
            {
                "_id": f"lead_t{i}",
                "client_id": "client-greensolar-uk",
                "postcode": "EC1Y 8AF",
                "address": f"{i} Old St",
            }
            for i in range(3)
        ]
    )
    body = {"postcode": "EC1Y 8AF", "client_id": "client-greensolar-uk", "limit": 50}
    r = client.post("/scan", json=body)
    assert r.status_code == 200
    sd = r.json()
    assert sd["lead_count"] == 3, sd

    # Stream and parse SSE frames.
    with client.stream("GET", f"/scan/{sd['scan_id']}/stream") as resp:
        assert resp.status_code == 200
        body_text = "".join(resp.iter_text())

    import json as _json

    progress_totals: list[int] = []
    done_payload: dict | None = None
    lead_events = 0
    current_event: str | None = None
    for line in body_text.splitlines():
        if line.startswith("event:"):
            current_event = line.split(":", 1)[1].strip()
        elif line.startswith("data:") and current_event:
            data = line.split(":", 1)[1].strip()
            try:
                obj = _json.loads(data)
            except Exception:
                obj = None
            if current_event == "progress" and isinstance(obj, dict):
                progress_totals.append(int(obj.get("total", -1)))
            elif current_event == "done" and isinstance(obj, dict):
                done_payload = obj
            elif current_event == "lead":
                lead_events += 1
            current_event = None

    assert lead_events == 3, f"expected 3 lead events, got {lead_events}"
    assert progress_totals, "no progress events emitted"
    assert all(t == 3 for t in progress_totals), (
        f"progress.total must equal scan.lead_count (3), got {progress_totals}"
    )
    assert done_payload is not None, "missing 'done' SSE event"
    assert done_payload["lead_count"] == 3
