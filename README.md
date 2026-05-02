# SolarReach

> **MongoDB Agentic Evolution Hackathon — May 2 2026**
> Theme: **Multi-Agent Collaboration** — specialized agents coordinate via MongoDB as the context engine.

Operations cockpit for the UK commercial solar industry. Every UK rooftop, joined to its real owner via HM Land Registry, scored for solar opportunity, photorealistically rendered in 3D, and pitched by an AI voice agent — all on a MongoDB Atlas-native stack with Google Maps Platform Photorealistic 3D Tiles.

## One-line pitch
*"Every UK rooftop, joined to its occupant, scored for solar opportunity, conversed with by AI — in real-time on MongoDB Atlas with Google Maps 3D."*

## Stack
- **Frontend**: React 19 + Vite + TypeScript 5.6 + Tailwind v4 + Google `<gmp-map-3d>`
- **API**: FastAPI 0.115+ on Python 3.12 (uv + ruff + ty)
- **Workers**: Celery 5.4 + Redis
- **AI**: Claude Sonnet 4.6 (content) + Opus 4.7 (decisions) + Haiku 4.5 (voice) + Voyage AI embeddings
- **Voice**: ElevenLabs ConvAI in-browser (WebRTC)
- **Data**: MongoDB Atlas (collections, time-series, 2dsphere, Atlas Search, Vector Search, change streams, triggers)

## Repo layout
```
docs/                     specs, runbooks, agent logs (live status from each agent)
packages/
  shared/                 cross-language types: TS + Py + JSON Schema
  api/                    FastAPI gateway
  scoring/                Celery worker (Land Registry + Solar API + composite score)
  codex/                  Anthropic content generation (pitch + email)
  voice/                  ElevenLabs ConvAI + Haiku sidecar
  web/                    React frontend
infra/
  docker-compose.yml
  mongodb/                init scripts (collections, validators, indexes)
scripts/                  ingest, seed, validate
tests/e2e/                Playwright demo path
```

## Quickstart (local, no Atlas required)
```bash
make dev          # docker-compose up
make seed         # populate ~50 demo leads
make verify       # health check all services
open http://localhost:5173
```

## Key docs
- [`docs/CONTRACTS.md`](docs/CONTRACTS.md) — API + component contracts (every team member reads this first)
- [`docs/TEAMMATE-ONBOARDING.md`](docs/TEAMMATE-ONBOARDING.md) — start-here guide for non-agentic teammates
- [`docs/RUNBOOK-DEMO.md`](docs/RUNBOOK-DEMO.md) — verbatim 7-min demo path
- [`docs/agent-log/`](docs/agent-log/) — live status from each parallel build agent

## Hackathon rules adherence
- **New work only** — every commit on this repo dated 2026-05-02 onward
- **MongoDB Atlas core** — all production state in Atlas (local Docker Mongo for dev only)
- **Public repo** — pushed to GitHub
- **Theme: Multi-Agent Collaboration** — see `docs/THEME-NARRATIVE.md`

## License
MIT — open source per hackathon rule.
