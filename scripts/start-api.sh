#!/usr/bin/env bash
# Start the FastAPI server with .env.local loaded into the process env.
# We use python-dotenv (not bash source) so values with `&`, quotes, etc. parse
# correctly from a real .env file.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/packages/api"

export PATH="$HOME/.local/bin:$PATH"
# Local docker mongo
export MONGO_URI="${MONGO_URI:-mongodb://solarreach:solarreach@localhost:27017/solarreach?authSource=admin}"

# Load .env.local via python-dotenv into a temp 'export' format that bash can `source` safely
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
uv run python -c "
from dotenv import dotenv_values
v = dotenv_values('$ROOT/.env.local')
for k, val in v.items():
    if val is not None:
        # printf %q-equivalent quoting
        safe = val.replace(\"'\", \"'\\\\''\")
        print(f\"export {k}='{safe}'\")
" > "$TMP"
# shellcheck disable=SC1090
source "$TMP"

echo "[start-api] env loaded: ANTHROPIC=$([[ -n \"${ANTHROPIC_API_KEY:-}\" ]] && echo yes || echo no), GOOGLE=$([[ -n \"${GOOGLE_MAPS_API_KEY:-}\" ]] && echo yes || echo no)"

exec uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
