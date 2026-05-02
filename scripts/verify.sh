#!/usr/bin/env bash
# Health-check every SolarReach service. Exit 0 only if everything is green.
set -uo pipefail

GREEN='\033[0;32m'; RED='\033[0;31m'; YELLOW='\033[0;33m'; CYAN='\033[0;36m'; RESET='\033[0m'

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/infra/docker-compose.yml")

fail=0

check() {
  local label="$1" cmd="$2"
  printf "  %-22s " "$label"
  if eval "$cmd" >/dev/null 2>&1; then
    printf "${GREEN}ok${RESET}\n"
  else
    printf "${RED}FAIL${RESET}\n"
    fail=$((fail+1))
  fi
}

check_http() {
  local label="$1" url="$2"
  printf "  %-22s " "$label"
  local code
  code=$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 5 "$url" 2>/dev/null || echo 000)
  if [[ "$code" == "200" || "$code" == "204" ]]; then
    printf "${GREEN}ok${RESET} (%s)\n" "$code"
  else
    printf "${RED}FAIL${RESET} (%s)\n" "$code"
    fail=$((fail+1))
  fi
}

printf "${CYAN}SolarReach verify${RESET}\n"

printf "${CYAN}— containers —${RESET}\n"
for svc in mongo redis api codex voice web; do
  check "$svc running" "${COMPOSE[*]} ps --format '{{.Service}} {{.State}}' | grep -E '^${svc}\\s+(running|Up)'"
done

printf "${CYAN}— endpoints —${RESET}\n"
check_http "api /health"        "http://localhost:8000/health"
check_http "voice /health"      "http://localhost:8001/health"
check_http "web /"              "http://localhost:5173/"
check     "mongo ping"          "${COMPOSE[*]} exec -T mongo mongosh --quiet --eval 'db.runCommand({ping:1}).ok'"
check     "redis ping"          "${COMPOSE[*]} exec -T redis redis-cli ping | grep -q PONG"

printf "${CYAN}— api spend endpoint —${RESET}\n"
check_http "api spend session"   "http://localhost:8000/lead/spend/session"

if [[ $fail -gt 0 ]]; then
  printf "${RED}✗ %d check(s) failed${RESET}\n" "$fail"
  exit 1
fi
printf "${GREEN}✓ all green${RESET}\n"
