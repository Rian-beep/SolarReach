"""Tests for app.services.s3_storage.

Covers the no-op fallback paths exhaustively (this is the path that runs
in CI, on every dev machine without AWS creds, and on the demo box if
the operator forgets to set env vars). The live-S3 path is exercised via
a stubbed aioboto3 session so we don't need real AWS credentials.
"""
from __future__ import annotations

import pytest

from app.services import s3_storage


# ─── No-op (local fallback) mode ────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_op_mode_when_creds_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    s3 = s3_storage.S3Storage()
    assert s3.enabled is False

    local = tmp_path / "deck.pptx"
    local.write_bytes(b"PK\x03\x04fakepptx")
    res = await s3.put_object(
        "pitches/lead_x/p_x.pptx",
        b"PK\x03\x04fakepptx",
        content_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        local_path=local,
    )
    assert res.uploaded is False
    assert res.error == "s3_disabled"
    assert res.url.startswith("file://"), res.url
    # Local path resolves to absolute and ends with the filename.
    assert res.url.endswith("deck.pptx"), res.url
    assert res.key == "pitches/lead_x/p_x.pptx"


@pytest.mark.asyncio
async def test_no_op_get_signed_url_returns_empty(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    s3 = s3_storage.S3Storage()
    assert await s3.get_signed_url("any/key.png") == ""


@pytest.mark.asyncio
async def test_no_op_delete_is_silent_noop(monkeypatch):
    """delete_object must be a no-op in disabled mode — never raises."""
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    s3 = s3_storage.S3Storage()
    # Just confirm it doesn't raise.
    await s3.delete_object("missing/key")


def test_no_op_when_only_one_credential_set(monkeypatch):
    """Half-configured (only access key, no secret) → still disabled."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA...")
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    s3 = s3_storage.S3Storage()
    assert s3.enabled is False


def test_no_op_when_bucket_missing(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("S3_BUCKET", "")
    s3 = s3_storage.S3Storage()
    assert s3.enabled is False


# ─── put_object: failure path falls back to local URL ───────────────────


@pytest.mark.asyncio
async def test_put_object_upstream_failure_falls_back_to_file_url(
    monkeypatch, tmp_path
):
    """Even with S3 enabled, an upstream failure (mocked) must produce a
    file:// URL rather than raising — this is the cardinal rule for the
    demo never breaking on AWS hiccups."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("S3_BUCKET", "solarreach-artifacts")
    s3 = s3_storage.S3Storage()
    assert s3.enabled is True

    # Replace _session with one whose client raises on put_object.
    class _BoomClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def put_object(self, **_kwargs):
            raise RuntimeError("simulated network error")

        async def generate_presigned_url(self, *a, **kw):
            return "should-not-be-called"

    class _Sess:
        def client(self, *_a, **_kw):
            return _BoomClient()

    monkeypatch.setattr(s3, "_session", lambda: _Sess())

    local = tmp_path / "deck.pdf"
    local.write_bytes(b"%PDF-fake")
    res = await s3.put_object(
        "pitches/lead_x/p.pdf",
        b"%PDF-fake",
        content_type="application/pdf",
        local_path=local,
    )
    assert res.uploaded is False
    assert res.url.startswith("file://")
    assert res.error and "s3_put_failed" in res.error


# ─── put_object: success path returns presigned URL ─────────────────────


@pytest.mark.asyncio
async def test_put_object_happy_path_returns_presigned_url(monkeypatch, tmp_path):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv("S3_BUCKET", "solarreach-artifacts")
    s3 = s3_storage.S3Storage()

    captured: dict = {}

    class _OkClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def put_object(self, **kwargs):
            captured["put"] = kwargs
            return {"ETag": "abc"}

        async def generate_presigned_url(self, op, Params, ExpiresIn):  # noqa: N803
            captured["presign"] = {
                "op": op, "params": Params, "ttl": ExpiresIn,
            }
            return f"https://solarreach-artifacts.s3.eu-west-2.amazonaws.com/{Params['Key']}?X-Amz-Sig=1"

    class _Sess:
        def client(self, *_a, **_kw):
            return _OkClient()

    monkeypatch.setattr(s3, "_session", lambda: _Sess())

    local = tmp_path / "img.png"
    local.write_bytes(b"\x89PNG\r\n\x1a\n")

    res = await s3.put_object(
        "flux/lead_y.png",
        b"\x89PNG\r\n\x1a\n",
        content_type="image/png",
        local_path=local,
        ttl_sec=3600,
    )
    assert res.uploaded is True
    assert res.error is None
    assert res.url.startswith("https://solarreach-artifacts.s3.")
    assert "flux/lead_y.png" in res.url
    # Server-side encryption was set on the put.
    assert captured["put"]["ServerSideEncryption"] == "AES256"
    assert captured["put"]["ContentType"] == "image/png"
    assert captured["presign"]["ttl"] == 3600


# ─── singleton lifecycle ────────────────────────────────────────────────


def test_get_s3_storage_is_cached(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    s3_storage.get_s3_storage.cache_clear()
    a = s3_storage.get_s3_storage()
    b = s3_storage.get_s3_storage()
    assert a is b
    s3_storage.get_s3_storage.cache_clear()
