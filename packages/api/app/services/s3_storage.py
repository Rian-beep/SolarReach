"""S3 storage for generated artifacts (decks, voice mp3s, flux PNGs).

Falls back to a local-only no-op mode when AWS credentials are absent — in
that mode ``put_object`` returns a ``file://`` URL pointing at the local copy
the caller already wrote, and ``get_signed_url`` / ``delete_object`` no-op
quietly with a warning. This means every consumer in the API can call S3
unconditionally and get something coherent back without crashing the demo
when the operator forgot to set AWS env vars.

Env (any missing → no-op mode):
  AWS_ACCESS_KEY_ID
  AWS_SECRET_ACCESS_KEY
  AWS_REGION       (default: eu-west-2)
  S3_BUCKET        (default: solarreach-artifacts)

Thread-safety: a single ``S3Storage`` instance is reused per process via
``get_s3_storage()`` (lru_cache). aioboto3 ``Session`` is cheap and creates
a fresh client per ``async with`` block, so concurrent calls don't share
mutable state.

Cardinal rules:
- NEVER raise out of ``put_object`` / ``get_signed_url`` / ``delete_object``.
  All upstream failures degrade to local-only behaviour with a logged warning.
  Routes already write a local copy first; S3 is the gravy.
- NEVER log the secret key. Log presence/absence only.
- Presigned URLs expire in 1 hour by default. Long-lived URLs are an
  anti-pattern — re-sign on demand.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("solarreach.api.s3")

DEFAULT_REGION = "eu-west-2"
DEFAULT_BUCKET = "solarreach-artifacts"
DEFAULT_TTL_SEC = 3600


@dataclass
class S3PutResult:
    """Outcome of a single ``put_object`` call.

    ``url`` is always populated — either an S3 presigned URL (live mode)
    or a ``file://`` URI to the local copy the caller already wrote
    (no-op fallback mode). Consumers persist this URL on the lead doc so
    the frontend can ``<a href={url}>`` it without caring which path
    produced it.
    """

    url: str
    key: str
    bucket: str | None
    uploaded: bool  # True if actually pushed to S3, False for local-only.
    error: str | None = None


class S3Storage:
    """Thin async wrapper around aioboto3 with graceful local fallback.

    Construction is cheap and never touches the network. The first method
    call that needs S3 is the one that surfaces credential / network errors,
    and even then they're logged + swallowed — the caller gets a result with
    ``uploaded=False`` and a usable local URL.
    """

    def __init__(
        self,
        *,
        access_key_id: str | None = None,
        secret_access_key: str | None = None,
        region: str | None = None,
        bucket: str | None = None,
    ) -> None:
        # Env fallback so this stays usable both as a singleton (via
        # ``get_s3_storage``) and as a directly-instantiated test double.
        self.access_key_id = access_key_id or os.getenv("AWS_ACCESS_KEY_ID", "")
        self.secret_access_key = (
            secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY", "")
        )
        self.region = region or os.getenv("AWS_REGION", DEFAULT_REGION)
        self.bucket = bucket or os.getenv("S3_BUCKET", DEFAULT_BUCKET)

        # No-op mode: either credential is missing OR the bucket name is empty.
        # We log presence (not values) once so operators can confirm.
        self.enabled = bool(
            self.access_key_id and self.secret_access_key and self.bucket
        )
        if not self.enabled:
            log.warning(
                "S3Storage running in local-only mode "
                "(access_key_id=%s, secret=%s, bucket=%s) — "
                "uploads will return file:// URLs",
                "set" if self.access_key_id else "missing",
                "set" if self.secret_access_key else "missing",
                self.bucket or "missing",
            )
        else:
            log.info(
                "S3Storage enabled bucket=%s region=%s", self.bucket, self.region
            )

    # ─── Internal: aioboto3 session/client ──────────────────────────────

    def _session(self):
        """Build an aioboto3 Session.

        Imported lazily so test collection (and the no-op mode) don't
        require the package to be installed at import time. This also
        means we surface a clear error if a deployer enables S3 mode
        without ``uv sync``-ing the dep.
        """
        try:
            import aioboto3  # type: ignore[import-not-found]
        except ImportError as e:  # pragma: no cover — caught at runtime
            raise RuntimeError(
                "aioboto3 is required for S3Storage but not installed. "
                "Run `uv sync` in packages/api or unset AWS_* env vars to "
                "use local-only mode."
            ) from e
        return aioboto3.Session(
            aws_access_key_id=self.access_key_id,
            aws_secret_access_key=self.secret_access_key,
            region_name=self.region,
        )

    # ─── Public API ─────────────────────────────────────────────────────

    async def put_object(
        self,
        key: str,
        data: bytes,
        content_type: str,
        *,
        ttl_sec: int = DEFAULT_TTL_SEC,
        local_path: str | Path | None = None,
    ) -> S3PutResult:
        """Upload ``data`` to ``s3://{bucket}/{key}`` and return a presigned URL.

        ``local_path`` is the on-disk file the caller already wrote (every
        producer in this codebase writes a local copy first as a durability
        fallback). If S3 is disabled or the upload fails, the returned
        ``url`` is ``file://{local_path}`` — never None — so consumers can
        unconditionally persist whatever we hand back.

        Never raises. Failures are logged and surfaced via ``error`` /
        ``uploaded=False`` on the result.
        """
        if not self.enabled:
            return _local_fallback_result(
                key=key, bucket=self.bucket, local_path=local_path,
                error="s3_disabled",
            )

        try:
            session = self._session()
            async with session.client("s3", region_name=self.region) as s3:
                await s3.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=data,
                    ContentType=content_type,
                    # Server-side encryption mirrors aws_setup.sh bucket policy.
                    # Setting it per-object too is belt-and-braces but cheap.
                    ServerSideEncryption="AES256",
                )
                # Re-use the same client for the presign — saves a session.
                url = await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=ttl_sec,
                )
            log.info("s3 put ok key=%s bytes=%d", key, len(data))
            return S3PutResult(
                url=url, key=key, bucket=self.bucket, uploaded=True, error=None
            )
        except Exception as e:  # noqa: BLE001 — never crash the route
            log.warning("s3 put failed key=%s err=%s", key, type(e).__name__)
            return _local_fallback_result(
                key=key, bucket=self.bucket, local_path=local_path,
                error=f"s3_put_failed:{type(e).__name__}",
            )

    async def get_signed_url(self, key: str, ttl_sec: int = DEFAULT_TTL_SEC) -> str:
        """Generate a fresh presigned URL for an existing object.

        In no-op mode returns an empty string (caller should fall back to
        the persisted ``file://`` URL on the lead doc — we don't have one
        here without the original local_path).
        """
        if not self.enabled:
            log.debug("s3 get_signed_url no-op (disabled) key=%s", key)
            return ""
        try:
            session = self._session()
            async with session.client("s3", region_name=self.region) as s3:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=ttl_sec,
                )
        except Exception as e:  # noqa: BLE001
            log.warning("s3 presign failed key=%s err=%s", key, type(e).__name__)
            return ""

    async def delete_object(self, key: str) -> None:
        """Delete an object. No-op + warning if disabled or upstream fails."""
        if not self.enabled:
            log.debug("s3 delete no-op (disabled) key=%s", key)
            return
        try:
            session = self._session()
            async with session.client("s3", region_name=self.region) as s3:
                await s3.delete_object(Bucket=self.bucket, Key=key)
            log.info("s3 delete ok key=%s", key)
        except Exception as e:  # noqa: BLE001
            log.warning("s3 delete failed key=%s err=%s", key, type(e).__name__)


# ─── Helpers ────────────────────────────────────────────────────────────


def _local_fallback_result(
    *,
    key: str,
    bucket: str | None,
    local_path: str | Path | None,
    error: str,
) -> S3PutResult:
    """Build an S3PutResult that points at the local copy the caller wrote.

    If ``local_path`` is missing (caller didn't write a local file), we still
    return a ``file://`` URL using the key as a relative path — better than
    None for consumers that just want to print "<not uploaded>" later.
    """
    if local_path is not None:
        # Resolve to absolute so the file:// URL is unambiguous when the
        # consumer is in a different cwd.
        abs_path = Path(local_path).resolve()
        url = f"file://{abs_path}"
    else:
        url = f"file://local-only/{key}"
    return S3PutResult(
        url=url, key=key, bucket=bucket, uploaded=False, error=error
    )


@lru_cache(maxsize=1)
def get_s3_storage() -> S3Storage:
    """Process-wide singleton, configured from env at first call.

    Cleared by tests via ``get_s3_storage.cache_clear()`` after monkeypatching
    AWS_* env vars.
    """
    return S3Storage()


__all__ = [
    "S3Storage",
    "S3PutResult",
    "get_s3_storage",
    "DEFAULT_REGION",
    "DEFAULT_BUCKET",
    "DEFAULT_TTL_SEC",
]
