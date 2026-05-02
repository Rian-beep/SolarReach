# SolarReach — root Makefile.
# Project dir contains spaces. Every shell command quotes paths.
# Use bash with -e -u -o pipefail for sane failure modes.

SHELL := /usr/bin/env bash
.SHELLFLAGS := -eu -o pipefail -c
.ONESHELL:
.DEFAULT_GOAL := help

# --- vars -------------------------------------------------------------------

ROOT      := $(CURDIR)
COMPOSE   := docker compose -f "$(ROOT)/infra/docker-compose.yml" --env-file "$(ROOT)/.env.local"
PY_PKGS   := api codex scoring voice
NODE_PKGS := web
API_URL   := http://localhost:8000
WEB_URL   := http://localhost:5173
VOICE_URL := http://localhost:8001

# Color helpers
GREEN  := \033[0;32m
RED    := \033[0;31m
YELLOW := \033[0;33m
CYAN   := \033[0;36m
RESET  := \033[0m

# --- meta -------------------------------------------------------------------

.PHONY: help
help:  ## list targets
	@printf "$(CYAN)SolarReach Makefile$(RESET)\n"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(GREEN)%-22s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# --- env --------------------------------------------------------------------

.env.local:
	@if [ ! -f "$(ROOT)/.env.local" ]; then \
		printf "$(YELLOW)Creating .env.local from .env.example$(RESET)\n"; \
		cp "$(ROOT)/.env.example" "$(ROOT)/.env.local"; \
		printf "$(YELLOW)Edit .env.local to add your API keys before running paid features.$(RESET)\n"; \
	fi

# --- install ----------------------------------------------------------------

.PHONY: install
install:  ## install all deps (uv per Py pkg + pnpm monorepo)
	@printf "$(CYAN)→ pnpm install$(RESET)\n"
	pnpm install
	@for pkg in $(PY_PKGS); do \
		if [ -f "$(ROOT)/packages/$$pkg/pyproject.toml" ]; then \
			printf "$(CYAN)→ uv sync packages/$$pkg$(RESET)\n"; \
			(cd "$(ROOT)/packages/$$pkg" && uv sync) || printf "$(YELLOW)  warn: uv sync failed for $$pkg (skip if not yet authored)$(RESET)\n"; \
		fi; \
	done
	@printf "$(GREEN)✓ install complete$(RESET)\n"

# --- compose lifecycle ------------------------------------------------------

.PHONY: dev
dev: .env.local  ## boot full stack (mongo+redis+api+codex+voice+web)
	$(COMPOSE) up -d --build
	@printf "$(GREEN)✓ stack up$(RESET) — api:$(API_URL)  web:$(WEB_URL)  voice:$(VOICE_URL)\n"

.PHONY: down
down:  ## stop all services
	$(COMPOSE) down

.PHONY: logs
logs:  ## tail all services
	$(COMPOSE) logs -f --tail=100

.PHONY: ps
ps:  ## list running services
	$(COMPOSE) ps

.PHONY: clean
clean:  ## destroy containers + named volumes (DATA LOSS)
	$(COMPOSE) down -v --remove-orphans
	@printf "$(YELLOW)✓ containers + volumes removed$(RESET)\n"

# --- single-service restarts -----------------------------------------------

.PHONY: mongo-restart
mongo-restart:  ## restart mongo only
	$(COMPOSE) restart mongo

.PHONY: api-restart
api-restart:  ## restart api only (rebuild image)
	$(COMPOSE) up -d --build --no-deps api

.PHONY: web-restart
web-restart:  ## restart web only
	$(COMPOSE) up -d --build --no-deps web

.PHONY: codex-restart
codex-restart:
	$(COMPOSE) up -d --build --no-deps codex

.PHONY: voice-restart
voice-restart:
	$(COMPOSE) up -d --build --no-deps voice

# --- data -------------------------------------------------------------------

.PHONY: seed
seed:  ## populate ~50 demo leads (A1 owns scripts/seed.py)
	@if [ ! -f "$(ROOT)/scripts/seed.py" ]; then \
		printf "$(YELLOW)scripts/seed.py not yet authored by A1 — skipping$(RESET)\n"; \
	else \
		cd "$(ROOT)" && uv run python scripts/seed.py --reset; \
	fi

.PHONY: ingest-inspire
ingest-inspire:  ## ingest INSPIRE polygons (limit 5000)
	@if [ ! -f "$(ROOT)/scripts/ingest_inspire.py" ]; then \
		printf "$(YELLOW)scripts/ingest_inspire.py not yet authored — skipping$(RESET)\n"; \
	else \
		cd "$(ROOT)" && uv run python scripts/ingest_inspire.py --limit 5000; \
	fi

.PHONY: ingest-ccod
ingest-ccod:  ## ingest CCOD owners subset (limit 5000)
	@if [ ! -f "$(ROOT)/scripts/ingest_ccod_subset.py" ]; then \
		printf "$(YELLOW)scripts/ingest_ccod_subset.py not yet authored — skipping$(RESET)\n"; \
	else \
		cd "$(ROOT)" && uv run python scripts/ingest_ccod_subset.py --limit 5000; \
	fi

.PHONY: extract-data
extract-data:  ## unzip remaining govt-data zips to data/raw/
	@bash "$(ROOT)/scripts/extract_govt_data.sh"

# --- verification -----------------------------------------------------------

.PHONY: verify
verify:  ## health-check every service (colored ok/fail)
	@bash "$(ROOT)/scripts/verify.sh"

# --- demo ops --------------------------------------------------------------

.PHONY: demo-reset
demo-reset:  ## wipe spend tracker, drop audit_log, clear caches
	@printf "$(CYAN)→ POST /admin/demo-reset$(RESET)\n"
	@curl -fsS -X POST "$(API_URL)/admin/demo-reset" || printf "$(YELLOW)  warn: /admin/demo-reset not implemented yet$(RESET)\n"
	@printf "$(CYAN)→ drop audit_log collection$(RESET)\n"
	@$(COMPOSE) exec -T mongo mongosh \
		"mongodb://solarreach:solarreach@localhost:27017/solarreach?authSource=admin" \
		--quiet --eval 'db.audit_log.drop(); db.flux_cache.drop(); print("audit_log+flux_cache dropped")' \
		|| printf "$(YELLOW)  warn: mongo not reachable$(RESET)\n"

.PHONY: demo-prefetch
demo-prefetch:  ## pre-fetch flux + panels for top 5 leads (avoid live cost during demo)
	@bash "$(ROOT)/scripts/demo_prefetch.sh"

.PHONY: demo-fallback-flux
demo-fallback-flux:  ## switch flux endpoint to pre-cached PNGs (Solar API outage fallback)
	@$(COMPOSE) exec -T api sh -c 'echo "USE_CACHED_FLUX=1" >> /tmp/runtime.env' || true
	@printf "$(YELLOW)Set USE_CACHED_FLUX=1; restart api to pick up.$(RESET)\n"

.PHONY: record-demo
record-demo:  ## start a screen capture of the demo (macOS screencapture -v)
	@bash "$(ROOT)/scripts/record_demo.sh"

# --- test / lint / typecheck -----------------------------------------------

.PHONY: test
test:  ## run all suites in parallel (pytest + vitest)
	@printf "$(CYAN)→ pytest packages$(RESET)\n"
	@for pkg in api codex scoring; do \
		if [ -d "$(ROOT)/packages/$$pkg/tests" ]; then \
			(cd "$(ROOT)/packages/$$pkg" && uv run pytest -q) & \
		fi; \
	done; \
	if [ -d "$(ROOT)/packages/web/src" ] && grep -q '"vitest"' "$(ROOT)/packages/web/package.json" 2>/dev/null; then \
		(cd "$(ROOT)/packages/web" && pnpm exec vitest run) & \
	fi; \
	wait
	@printf "$(GREEN)✓ tests done$(RESET)\n"

.PHONY: typecheck
typecheck:  ## ty (Py) + tsc (TS) across the monorepo
	@printf "$(CYAN)→ pnpm -r typecheck$(RESET)\n"
	pnpm -r typecheck || true
	@for pkg in $(PY_PKGS); do \
		if [ -f "$(ROOT)/packages/$$pkg/pyproject.toml" ]; then \
			printf "$(CYAN)→ ty check packages/$$pkg$(RESET)\n"; \
			(cd "$(ROOT)/packages/$$pkg" && uv run ty check . 2>/dev/null) || \
				printf "$(YELLOW)  warn: ty not installed in $$pkg$(RESET)\n"; \
		fi; \
	done

.PHONY: lint
lint:  ## ruff + biome
	@printf "$(CYAN)→ ruff check$(RESET)\n"
	uv run ruff check . || ruff check . || printf "$(YELLOW)ruff not installed$(RESET)\n"
	@printf "$(CYAN)→ ruff format --check$(RESET)\n"
	uv run ruff format --check . || ruff format --check . || true
	@printf "$(CYAN)→ biome check$(RESET)\n"
	pnpm exec biome check packages/web 2>/dev/null || printf "$(YELLOW)biome not configured for web yet$(RESET)\n"

.PHONY: format
format:  ## auto-format
	uv run ruff format . || ruff format . || true
	uv run ruff check --fix . || ruff check --fix . || true
	pnpm exec biome format --write packages/web 2>/dev/null || true

# --- contract validation ---------------------------------------------------

.PHONY: validate-contracts
validate-contracts:  ## diff CONTRACTS.md endpoints vs FastAPI routes
	uv run python "$(ROOT)/scripts/validate_contracts.py"

# --- alias ------------------------------------------------------------------

.PHONY: up start
up: dev
start: dev
