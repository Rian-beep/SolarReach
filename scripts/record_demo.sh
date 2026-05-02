#!/usr/bin/env bash
# Placeholder screen capture. macOS only.
# Usage: scripts/record_demo.sh [duration_seconds]
# Output: docs/reports/demo-<timestamp>.mov
set -euo pipefail

DUR="${1:-420}"  # 7 minutes default
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$ROOT/docs/reports"
mkdir -p "$OUT_DIR"
TS="$(date +%Y%m%d-%H%M%S)"
OUT="$OUT_DIR/demo-$TS.mov"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "macOS only (uses screencapture -v). On Linux use 'ffmpeg -f x11grab'." >&2
  exit 2
fi

echo "Recording $DUR seconds → $OUT"
echo "Press Ctrl-C to stop early."
# -v video, -V records named display, default is main; -o overrides timeout via SIGINT.
screencapture -v -V "$DUR" "$OUT"
echo "→ $OUT"
