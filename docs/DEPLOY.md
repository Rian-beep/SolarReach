# DEPLOY — SolarReach

> Production-deployment runbook. For the local dev quickstart, see `README.md` + `make dev`.
> For the demo path, see `docs/RUNBOOK-DEMO-FINAL.md`.

This document covers:
1. Prerequisites + secrets
2. Cloning the repo on a fresh box
3. Configuring the environment
4. Building production images (locally OR via CI)
5. Deploying with `docker compose` (single-host)
6. Verifying the deployment
7. Rollback + observability

---

## 1. Prerequisites

| Tool | Version | Why |
|---|---|---|
| Docker Engine | ≥ 24 | Multi-stage builds, BuildKit on by default |
| Docker Compose v2 | ≥ 2.20 | `docker compose` (no hyphen) |
| Git | ≥ 2.40 | Clone + tag |
| `gh` CLI | ≥ 2.40 | Optional — pulling images from ghcr.io |

**Hardware floor**: 2 vCPU, 4 GB RAM, 20 GB disk. The codex worker spikes RAM during PPTX → PDF; size up if you generate many decks concurrently.

### Secrets you need

Collected once, never committed. Stored either in a deploy-only `.env.local` on the host, or in GitHub Actions secrets for CI-driven deploys.

| Key | Required? | Source |
|---|---|---|
| `MONGO_URI` | yes | MongoDB Atlas connection string (`mongodb+srv://...`) |
| `MONGO_DB` | yes | Default: `solarreach` |
| `ANTHROPIC_API_KEY` | yes | console.anthropic.com |
| `GOOGLE_MAPS_API_KEY` | yes | Google Cloud — restrict to "None" or IP allowlist |
| `ELEVENLABS_API_KEY` | for voice | elevenlabs.io |
| `ELEVENLABS_AGENT_ID` | for voice | elevenlabs.io ConvAI agent |
| `COMPANIES_HOUSE_API_KEY` | optional | UK gov, free tier OK |
| `VOYAGE_API_KEY` | optional | MongoDB partner — 50M tokens/mo free |
| `REDIS_URL` | yes | `redis://redis:6379/0` for compose; managed Redis URL otherwise |

> **Never commit secrets.** `.env` and `.env.local` are gitignored. Workflows pull from `${{ secrets.* }}`.

---

## 2. Clone

```bash
git clone https://github.com/Rian-beep/SolarReach.git solarreach
cd solarreach
```

If deploying from a fork, set the upstream image registry:
```bash
export REGISTRY=ghcr.io
export IMAGE_PREFIX="<your-org>/solarreach"
```

---

## 3. Environment

Copy the template and fill in real values:

```bash
cp .env.example .env.local
$EDITOR .env.local
```

**Critical to flip for prod**:

```dotenv
SOLARREACH_LIVE_OUTBOUND=false   # keep false unless email outreach has been reviewed
ROI_GATE_THRESHOLD=70
SESSION_BUDGET_GBP=1.00
VITE_API_BASE=https://api.your-domain.example   # if web is behind a separate origin
```

Compose reads `infra/docker-compose.yml` with `--env-file ../.env.local` (the Makefile already does this).

---

## 4. Build production images

You have two paths.

### 4a. Locally (single host)

```bash
# From repo root. Build context for api/codex is the repo root so sibling
# packages (shared/py, codex, swarm) resolve.
docker build -f infra/Dockerfile.prod.api   -t solarreach-api:local   .
docker build -f infra/Dockerfile.prod.codex -t solarreach-codex:local .

# Web context is packages/web. Pass the public Maps key + API origin.
docker build -f infra/Dockerfile.prod.web \
  --build-arg VITE_API_BASE="https://api.your-domain.example" \
  --build-arg VITE_GOOGLE_MAPS_API_KEY="AIza..." \
  -t solarreach-web:local \
  packages/web
```

Image sizes (approximate, post multi-stage):
- `solarreach-api`: ~250 MB (was ~700 MB in dev)
- `solarreach-codex`: ~1.1 GB (LibreOffice + fonts; can't shrink further without dropping deck rendering)
- `solarreach-web`: ~50 MB (nginx alpine + static bundle)

### 4b. Via GitHub Actions

Trigger the `deploy` workflow manually:

```bash
gh workflow run deploy.yml \
  -f tag="v0.1.0" \
  -f push="true"
```

Or in the GitHub UI: **Actions → deploy → Run workflow**.

What it does:
- Builds 3 images in parallel (api, codex, web)
- Tags each with `:<git-sha-short>`, `:latest`, and any `tag` input you provided
- Pushes to `ghcr.io/<owner>/solarreach-{api,codex,web}` if `push=true` and `GITHUB_TOKEN` has `write:packages`
- Skips push but still validates the build if no auth — useful for PR-time smoke

Image references after a successful run with `tag=v0.1.0`:
```
ghcr.io/rian-beep/solarreach-api:v0.1.0
ghcr.io/rian-beep/solarreach-api:latest
ghcr.io/rian-beep/solarreach-api:abc1234
ghcr.io/rian-beep/solarreach-codex:v0.1.0
ghcr.io/rian-beep/solarreach-web:v0.1.0
```

> **Make the package public** in GitHub *Packages* settings if your deployment box pulls anonymously.

---

## 5. Deploy

For a single-host deployment, copy the production compose file alongside your existing infra. Two-line example:

```bash
# Pull built images
docker pull ghcr.io/rian-beep/solarreach-api:latest
docker pull ghcr.io/rian-beep/solarreach-codex:latest
docker pull ghcr.io/rian-beep/solarreach-web:latest

# Bring up via the dev compose with image overrides, OR write infra/docker-compose.prod.yml
docker compose -f infra/docker-compose.yml --env-file .env.local up -d mongo redis
docker run -d --name solarreach-api   --network solarreach_solarreach --env-file .env.local -p 8000:8000 ghcr.io/rian-beep/solarreach-api:latest
docker run -d --name solarreach-codex --network solarreach_solarreach --env-file .env.local                ghcr.io/rian-beep/solarreach-codex:latest
docker run -d --name solarreach-web   --network solarreach_solarreach -e UPSTREAM_API=solarreach-api:8000 -p 80:80 ghcr.io/rian-beep/solarreach-web:latest
```

For Atlas-backed prod, drop the `mongo` service from compose and point `MONGO_URI` at `mongodb+srv://...`.

### 5a. Reverse proxy / TLS

The repo ships `infra/Caddyfile` for Caddy fronting. Terminate TLS there and proxy to the `web` container on port 80; the web container in turn proxies `/api`, `/scan`, `/lead`, `/voice`, `/admin`, `/financial`, `/health`, `/static` to `$UPSTREAM_API`.

---

## 6. Verify

```bash
# Health (api direct)
curl -fsS http://localhost:8000/health | jq
# Expect: {"status":"ok","services":{"mongo":true,"anthropic_reachable":true,"redis":true}}

# Health (through nginx)
curl -fsS http://localhost/health | jq

# Smoke a scan
curl -fsS -X POST http://localhost:8000/scan \
  -H 'Content-Type: application/json' \
  -d '{"postcode":"EC1Y 8AF","client_id":"client-greensolar-uk","limit":5}' | jq '.results | length'

# Web bundle served
curl -fsSI http://localhost/ | head -1
# Expect: HTTP/1.1 200 OK
```

If `mongo:false`: `MONGO_URI` is unreachable or wrong-auth. Check Atlas IP allowlist.
If `anthropic_reachable:false`: `ANTHROPIC_API_KEY` empty or invalid. Check `.env.local`.
If `redis:false`: `REDIS_URL` wrong, or compose redis service down. `docker logs solarreach-redis`.

The `scripts/verify.sh` helper does the full sweep:
```bash
bash scripts/verify.sh
```

---

## 7. Rollback

Images are SHA-tagged, so rollback is `docker pull <sha>` + `docker stop` + `docker run`:

```bash
PREV_SHA=$(git rev-parse HEAD~1 | cut -c1-7)
docker stop solarreach-api && docker rm solarreach-api
docker run -d --name solarreach-api --env-file .env.local -p 8000:8000 \
  ghcr.io/rian-beep/solarreach-api:${PREV_SHA}
```

Mongo data is in the named volume `mongo-data` — rolling back code does NOT touch data. Atlas snapshots cover the data side.

---

## 8. Observability

- **Container logs**: `docker compose logs -f api` (or `make logs`)
- **Health endpoint**: `/health` returns Mongo / Anthropic / Redis status as booleans — frontend pill polls this
- **Audit log** (Mongo): collection `audit_log` records every outbound + LLM call with cost
- **Spend tracker**: `GET /financial/spend` summarises today's session vs `SESSION_BUDGET_GBP`

For a fresh demo state:
```bash
make demo-reset            # zeros spend tracker, clears caches
```

---

## 9. CI safety net

The `ci.yml` workflow runs on every push to `main` and every PR:
- Lint + typecheck (ruff, biome, tsc)
- pytest matrix across api / codex / swarm / shared/py with mongomock-motor
- Boot the api in-process and assert `/health` returns 200 with the expected schema
- Build the web bundle and upload it as an artifact

A red CI run blocks deploy. Don't bypass with `--no-verify`.

---

## 10. Known gotchas

- **The repo path contains spaces** (`SolarReach Mongo Hackathon`). Quote it everywhere if you script against the local checkout.
- **GHCR image names must be lowercase** — `deploy.yml` does this for you.
- **Web build bakes `VITE_*` vars at build time** — to change `VITE_API_BASE` you must rebuild the web image.
- **`pnpm typecheck` requires the workspace shared/ts package to have `dist/` built** if anything imports from `@solarreach/shared`. The web tsconfig currently uses path aliases inside its own `src`, so this is moot — but watch for it if you wire shared types into the web bundle.
