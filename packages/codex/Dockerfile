# SolarReach Codex Brain — Celery worker for Anthropic content generation
# (pitch deck, email A/B variants, decision-maker inference).
# Includes LibreOffice headless for PPTX -> PDF conversion.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_LINK_MODE=copy

# LibreOffice + Inter font (deck branding) + matplotlib runtime deps
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl ca-certificates build-essential \
        libreoffice libreoffice-impress \
        fonts-inter fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# uv for fast installs
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /usr/local/bin/uv

WORKDIR /app

# Install package + deps
COPY pyproject.toml README.md ./
COPY codex_brain ./codex_brain
RUN uv pip install --system -e "." || \
    uv pip install --system \
        anthropic pydantic python-pptx matplotlib pillow \
        motor celery redis httpx pypdf voyageai

# Pre-create deck output dir for /tmp/decks/<lead_id>.pptx
RUN mkdir -p /tmp/decks

ENV REDIS_URL=redis://redis:6379/0 \
    MONGO_URI=mongodb://mongo:27017/?authSource=admin \
    MONGO_DB=solarreach

# Celery worker; concurrency 2 keeps Anthropic rate-limit headroom.
CMD ["celery", "-A", "codex_brain.celery_app:celery_app", "worker", "--loglevel=info", "--concurrency=2"]
