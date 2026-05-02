import pytest

from app.services.audit import log_audit, hash_recipient


@pytest.mark.asyncio
async def test_log_audit_writes_doc(mock_db):
    await log_audit(
        mock_db,
        action="lead.scan",
        lead_id="lead_abc",
        cost_cents=5,
        metadata={"foo": "bar"},
        recipient_email="a@b.com",
    )
    docs = await mock_db.audit_log.find({}).to_list(length=10)
    assert len(docs) == 1
    d = docs[0]
    assert d["action"] == "lead.scan"
    assert d["lead_id"] == "lead_abc"
    assert d["cost_cents"] == 5
    assert d["metadata"] == {"foo": "bar"}
    # Recipient must be hashed, never plaintext.
    assert "a@b.com" not in str(d)
    assert d["recipient_sha256"] == hash_recipient("a@b.com")
    assert "ts" in d
