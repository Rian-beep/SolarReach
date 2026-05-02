# SolarReach API — FastAPI on uv.
# Multi-stage: deps layer cached separately from app code so a `make api-restart` after
# a source-only edit rebuilds in <5s.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

# uv from official image
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

# Shared package (sibling) — copied first so layer caches across api/codex/voice
COPY ../shared /shared
# (Docker compose context is packages/api; shared is mounted at runtime instead.
#  The COPY above is a no-op when context lacks ../shared. We rely on the runtime mount.)

# Dependency layer
COPY pyproject.toml ./
RUN uv pip install --system -e ".[dev]" || \
    uv pip install --system fastapi uvicorn[standard] motor pydantic pydantic-settings \
        sse-starlette httpx anthropic redis celery python-multipart pytest pytest-asyncio mongomock-motor

# App code (overridden by bind-mount in dev for HMR)
COPY app ./app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--reload-dir", "/app/app"]
