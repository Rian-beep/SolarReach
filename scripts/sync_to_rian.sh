#!/usr/bin/env bash
# sync_to_rian.sh — push SolarReach data exports to Rian's solarreach-project1.
#
# IMPORTANT: This script is a STUB for Rian to invoke. It does NOT push to
# his repo by default — set ``SOLARREACH_RIAN_DO_PUSH=1`` to actually push.
# Default mode prints what would happen so we can dry-run safely.
#
# Steps:
#   1. Run scripts/export_for_rian.py to refresh ``exports/`` artefacts.
#   2. Stage them onto branch ``data/exports`` of the ``rian`` git remote.
#      Assumes ``git remote add rian git@github.com:Rian-beep/solarreach-project1.git``
#      has been run by whoever invokes the script.
#   3. Optionally POST a Slack/webhook notification (env-gated by
#      ``SOLARREACH_NOTIFY_WEBHOOK``).
#
# Usage:
#   ./scripts/sync_to_rian.sh [--push]
#
# Env vars:
#   SOLARREACH_RIAN_DO_PUSH    — 1 to actually push to rian; default dry-run
#   SOLARREACH_RIAN_REMOTE     — git remote name (default: rian)
#   SOLARREACH_RIAN_BRANCH     — branch to push to (default: data/exports)
#   SOLARREACH_NOTIFY_WEBHOOK  — Slack-compatible webhook URL (optional)
#   MONGO_URI / MONGO_DB       — passed through to export_for_rian.py
#
# Cardinal rules respected:
#   - No secrets logged.
#   - Exports directory rebuilt fresh each run (idempotent).
#   - Never force-pushes; aborts if remote rejects fast-forward.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

REMOTE="${SOLARREACH_RIAN_REMOTE:-rian}"
BRANCH="${SOLARREACH_RIAN_BRANCH:-data/exports}"
DO_PUSH="${SOLARREACH_RIAN_DO_PUSH:-0}"
EXPORT_DIR="${REPO_ROOT}/exports"

if [[ "${1:-}" == "--push" ]]; then
    DO_PUSH=1
fi

log() { printf '[sync_to_rian] %s\n' "$*"; }

# --- 1. Refresh exports -----------------------------------------------------
log "step 1/3 — refreshing exports/ via export_for_rian.py"

# Prefer the API venv's python (has all deps); fall back to system python3.
PY="$REPO_ROOT/packages/api/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
    PY="$(command -v python3 || true)"
fi
if [[ -z "$PY" ]]; then
    echo "ERROR: no python interpreter found (tried packages/api/.venv + system python3)" >&2
    exit 1
fi

"$PY" scripts/export_for_rian.py --out "$EXPORT_DIR"

if [[ ! -f "$EXPORT_DIR/leads.jsonl" ]]; then
    echo "ERROR: export script did not produce $EXPORT_DIR/leads.jsonl" >&2
    exit 1
fi

# --- 2. Stage onto Rian's branch -------------------------------------------
log "step 2/3 — staging exports onto remote=$REMOTE branch=$BRANCH"

if ! git remote get-url "$REMOTE" >/dev/null 2>&1; then
    cat >&2 <<EOF
ERROR: git remote '$REMOTE' is not configured.
  Run, e.g.:
    git remote add $REMOTE git@github.com:Rian-beep/solarreach-project1.git
  Then re-run this script.
EOF
    exit 1
fi

if [[ "$DO_PUSH" != "1" ]]; then
    log "DRY RUN — set SOLARREACH_RIAN_DO_PUSH=1 (or pass --push) to actually push."
    log "would: git push $REMOTE HEAD:refs/heads/$BRANCH (with exports/ subtree only)"
    log "files that would be synced:"
    ls -la "$EXPORT_DIR" | sed 's/^/  /'
    exit 0
fi

# Real-push path: build a single commit on a temporary branch containing only
# the exports/ directory. We never alter the working tree of main.
TMP_BRANCH="solarreach-export-$(date -u +%Y%m%dT%H%M%SZ)"
log "creating temporary commit on $TMP_BRANCH"

# Use a worktree so we don't disturb the live checkout.
WORKTREE_DIR="$(mktemp -d)"
trap 'git worktree remove --force "$WORKTREE_DIR" >/dev/null 2>&1 || true; rm -rf "$WORKTREE_DIR"' EXIT

git worktree add --detach "$WORKTREE_DIR" >/dev/null

(
    cd "$WORKTREE_DIR"
    git checkout --orphan "$TMP_BRANCH"
    git rm -rf --cached . >/dev/null 2>&1 || true
    # Clean working tree (we are orphaned).
    find . -mindepth 1 -maxdepth 1 ! -name ".git" -exec rm -rf {} +
    mkdir -p data/exports
    cp -R "$EXPORT_DIR"/. data/exports/
    git add data/exports
    git -c user.email="solarreach-sync@local" \
        -c user.name="SolarReach Sync" \
        commit -m "chore(data): sync exports $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    git push --no-verify "$REMOTE" "HEAD:refs/heads/$BRANCH"
)

log "pushed to $REMOTE/$BRANCH"

# --- 3. Notify (optional) ---------------------------------------------------
log "step 3/3 — notification"

if [[ -n "${SOLARREACH_NOTIFY_WEBHOOK:-}" ]]; then
    LEAD_COUNT=$(wc -l < "$EXPORT_DIR/leads.jsonl" | tr -d ' ')
    PAYLOAD=$(printf '{"text":"SolarReach exports synced to %s/%s — %s leads"}' \
        "$REMOTE" "$BRANCH" "$LEAD_COUNT")
    if curl -fsS -X POST -H 'Content-Type: application/json' \
        -d "$PAYLOAD" "$SOLARREACH_NOTIFY_WEBHOOK" >/dev/null; then
        log "notification posted"
    else
        log "WARN: webhook post failed (non-fatal)"
    fi
else
    log "no SOLARREACH_NOTIFY_WEBHOOK set, skipping notification"
fi

log "done"
