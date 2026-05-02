# A5 Integration / DevOps — Live Log

> Owner: A5. Append-only. Newest entries at top.

## 2026-05-02 — phase 0 scaffold complete

Wrote the entire infra layer in one pass:

- **`infra/docker-compose.yml`** — 6 services on `solarreach` bridge network: `mongo` (7.0, healthcheck via `mongosh ping`), `redis` (7-alpine, AOF on, healthcheck via `redis-cli ping`), `api` (HMR bind-mount on `app/` + `/shared`), `codex` (Celery worker, no exposed port), `voice` (8001), `web` (HMR bind-mounts on `src/`, `index.html`, `vite.config.ts`, `package.json`, `tsconfig.json`, `postcss.config.js`). `depends_on` uses `service_healthy` for api+codex+voice so they don't race the data layer.
- **`infra/mongodb/00-init.sh`** — bootstrap shim that logs which of A1's `01-users.js` … `04-indexes.js` are present. Mongo's official entrypoint auto-runs `*.js` in lex order, so this stays a no-op once A1 commits.
- **`infra/.dockerignore`** — excludes node_modules, .venv, data/raw, *.zip, .env*.
- **`infra/Caddyfile`** — optional TLS reverse proxy with SSE buffer disabled on `/scan/*/stream`. Domain placeholder, swap before deploy.
- **Dockerfiles** for `api`, `codex`, `voice`, `web`. Multi-stage where useful. Codex pulls libreoffice for PPTX→PDF. uv installed from official ghcr image.

- **Root `Makefile`** — every target quote-safe (the project dir has spaces). Targets: `dev`, `down`, `logs`, `ps`, `clean`, `seed`, `ingest-inspire`, `ingest-ccod`, `extract-data`, `verify`, `demo-reset`, `demo-prefetch`, `demo-fallback-flux`, `record-demo`, `mongo-restart`, `api-restart`, `web-restart`, `codex-restart`, `voice-restart`, `test` (parallel pytest+vitest), `typecheck` (pnpm -r + ty per pkg), `lint` (ruff+biome), `format`, `install`, `validate-contracts`. Auto-creates `.env.local` from `.env.example` if missing.
- **Root `package.json`** + **`pnpm-workspace.yaml`** — pnpm 9.12, `packages/*` workspace. Biome 1.9.4 only at root.
- **Root `pyproject.toml`** + **`ruff.toml`** — ruff line-length 100, py312, ruff lints `E,F,I,B,UP,SIM,RUF`. ty config block. pytest asyncio_mode=auto.
- **Root `biome.json`** — formatter+linter, 2-space, lineWidth 100, double quotes, semicolons always.

- **Scripts**:
  - `scripts/verify.sh` — colored ok/FAIL across all containers + http endpoints (`/health`, `/lead/spend/session`, web `/`). Exit code propagates.
  - `scripts/dev-native.sh` — alternative to Docker for fast iteration. Boots mongo+redis in compose, runs api/codex/voice/web natively. Localhost mongo URI override.
  - `scripts/validate_contracts.py` — parses `docs/CONTRACTS.md` § 2 endpoints and FastAPI `@router.METHOD()` decorators across `packages/api/app`, diffs them. Path-param normalization handles both `<id>` and `{id}`. Missing = error, extra = warning (with internal-route allowlist).
  - `scripts/demo_prefetch.sh` — top-5 leads → POST flux + panels.
  - `scripts/record_demo.sh` — macOS `screencapture -v` placeholder, defaults to 420s.
  - `scripts/extract_govt_data.sh` — idempotent unzip from `~/Downloads/Hackathon Govt Data` into `data/raw/`.

- **`.github/workflows/ci.yml`** — three jobs: `lint-and-typecheck`, `validate-contracts`, `api-smoke` (pytest with mongomock-motor; skips gracefully when no tests yet).

### Decisions (defensible, not researched)
1. **HMR bind-mounts are read-only on `api`** (`:ro`) but **read-write on `web`** because Vite writes a `.vite/` cache inside the working dir. Read-only on api prevents accidental container-side writes leaking back to host.
2. **Compose context is `packages/<pkg>`** not repo root — keeps each image's build context small. `shared/` is bind-mounted at runtime instead of COPYed, so type updates from A1 propagate without rebuild.
3. **Healthcheck on api uses `urllib.request`** (stdlib) rather than `curl` — no apt install needed in the slim image.
4. **`.env.local` is single source for all services** via `env_file:`. Frontend reads `VITE_*` variants automatically.
5. **CI doesn't try to boot full stack** — only lint/typecheck/contract diff + a mongomock-backed pytest. Full integration is human-driven via `make verify`.

### Known gaps (waiting on other agents)
- A1 must commit `infra/mongodb/01-users.js` … `04-indexes.js` before mongo init exercises real schema. Until then Mongo runs vanilla.
- A2 must implement `/health`, `/lead/spend/session`, `/admin/demo-reset` for `make verify` and `make demo-reset` to pass cleanly. `verify.sh` tolerates missing endpoints (FAIL is logged, not fatal until phase 1 sweep).
- A4's codex worker requires `ANTHROPIC_API_KEY` in `.env.local` to start cleanly — I've documented this in `.env.example`.

### Next actions (merge-sheriff phase)
- [ ] Phase-1 sweep at ~T+1.5h: `make dev && make verify && make test` — fix any agent-merge breakage.
- [ ] Pin dep versions in root `pyproject.toml` and `package.json` once all agents have committed first cuts.
- [ ] Run `validate_contracts.py` after A2 commits routers; resolve drift.
- [ ] End-to-end smoke: scan → SSE → drawer → mock pitch → voice signed-URL.
