import os
from pathlib import Path

import pytest

from app.services.compliance_gate import send_outbound_email


@pytest.mark.asyncio
async def test_outbound_email_persists_to_outbox_when_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLARREACH_LIVE_OUTBOUND", "false")
    monkeypatch.chdir(tmp_path)
    result = await send_outbound_email(
        to="someone@example.com",
        subject="Hi",
        body="Hello",
    )
    assert result["status"] == "outbox"
    eml_path = Path(result["path"])
    assert eml_path.exists()
    contents = eml_path.read_text()
    assert "Hello" in contents
    assert "someone@example.com" in contents
