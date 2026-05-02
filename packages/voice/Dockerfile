# SolarReach Voice — ElevenLabs ConvAI signed-URL issuer + Haiku sidecar.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml* ./
RUN uv pip install --system -e "." 2>/dev/null || \
    uv pip install --system fastapi uvicorn[standard] motor pydantic httpx anthropic

COPY voice_service ./voice_service

EXPOSE 8001
CMD ["uvicorn", "voice_service.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload", "--reload-dir", "/app/voice_service"]
