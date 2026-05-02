#!/usr/bin/env bash
# Run mongo+redis in Docker, but api/codex/voice/web natively for fast iteration.
# Use this when you're rapidly iterating on API code and don't want to wait for image rebuilds.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GREEN='\033[0;32m'; CYAN='\033[0;36m'; RESET='\033[0m'

if [[ ! -f .env.local ]]; then
  cp .env.example .env.local
  echo "Created .env.local — edit to add API keys"
fi

# Boot infra containers only
echo -e "${CYAN}→ starting mongo + redis containers${RESET}"
docker compose -f infra/docker-compose.yml up -d mongo redis

# Wait for mongo health
for i in {1..30}; do
  if docker compose -f infra/docker-compose.yml exec -T mongo mongosh --quiet --eval 'db.runCommand({ping:1}).ok' >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

# Override mongo URI to localhost for native processes
export MONGO_URI="${MONGO_URI:-mongodb://solarreach:solarreach@localhost:27017/solarreach?authSource=admin}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"

# Load .env.local
set -a
# shellcheck disable=SC1091
source .env.local
set +a
# Re-override (compose-internal hostnames don't resolve from host)
export MONGO_URI="mongodb://solarreach:solarreach@localhost:27017/solarreach?authSource=admin"
export REDIS_URL="redis://localhost:6379/0"

cleanup() {
  echo -e "\n${CYAN}→ shutting down native processes${RESET}"
  jobs -p | xargs -I {} kill {} 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo -e "${CYAN}→ launching api (8000), voice (8001), codex worker, web (5173)${RESET}"

(cd packages/api    && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload) &
(cd packages/voice  && uv run uvicorn voice_service.main:app --host 0.0.0.0 --port 8001 --reload) &
(cd packages/codex  && uv run celery -A codex_brain.tasks worker --loglevel=info --concurrency=2) &
(cd packages/web    && pnpm dev --host) &

echo -e "${GREEN}✓ stack up — Ctrl-C to stop${RESET}"
wait
