#!/usr/bin/env bash
# Pre-fetch flux overlay + panel layout for the top 5 leads by composite_score.
# Run before the live demo to avoid hitting Solar API quota / latency on stage.
set -euo pipefail

API="${API_BASE:-http://localhost:8000}"
GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RESET='\033[0m'

# Get top-5 lead ids
ids=$(curl -fsS "$API/leads?sort=-scores.composite_score&limit=5" 2>/dev/null \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print('\n'.join(x['_id'] for x in (d.get('leads') or d if isinstance(d, list) else [])))" \
  || true)

if [[ -z "$ids" ]]; then
  printf "${YELLOW}no leads found — run 'make seed' first${RESET}\n"
  exit 0
fi

while IFS= read -r id; do
  [[ -z "$id" ]] && continue
  printf "  prefetch %s ... " "$id"
  curl -fsS -X POST "$API/lead/$id/flux_overlay" >/dev/null 2>&1 && printf "flux ok " || printf "${YELLOW}flux fail${RESET} "
  curl -fsS -X POST "$API/lead/$id/panels" >/dev/null 2>&1     && printf "panels ok\n" || printf "${YELLOW}panels fail${RESET}\n"
done <<< "$ids"

printf "${GREEN}✓ prefetch complete${RESET}\n"
