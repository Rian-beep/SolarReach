#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

source .venv/bin/activate
export $(grep -v '^#' .env | xargs)

uvicorn voice_service.main:app --reload --host 0.0.0.0 --port 8000
