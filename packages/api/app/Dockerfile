# Multi-stage Dockerfile for the SolarReach API.
# Stage 1 builds wheels into a venv; stage 2 ships only the runtime.
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy shared package and api package
COPY packages/shared/py /build/shared
COPY packages/api/pyproject.toml /build/api/pyproject.toml
COPY packages/api/README.md /build/api/README.md

RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --upgrade pip \
    && /opt/venv/bin/pip install /build/shared \
    && /opt/venv/bin/pip install \
        "fastapi>=0.115" \
        "uvicorn[standard]>=0.32" \
        "motor>=3.6" \
        "pydantic[email]>=2.9" \
        "pydantic-settings>=2.6" \
        "sse-starlette>=2.1" \
        "httpx>=0.28" \
        "anthropic>=0.40" \
        "redis>=5.2" \
        "celery>=5.4" \
        "python-multipart"

# ---- runtime ----
FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv
COPY packages/api/app /app/app

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
