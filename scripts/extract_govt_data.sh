#!/usr/bin/env bash
# Unzip govt-data zips found in /Users/lukedudley/Downloads/Hackathon Govt Data into data/raw/.
# Idempotent: skips already-extracted directories.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC_DIR="${GOVT_DATA_SRC:-/Users/lukedudley/Downloads/Hackathon Govt Data}"
DEST="$ROOT/data/raw"

mkdir -p "$DEST"

if [[ ! -d "$SRC_DIR" ]]; then
  echo "Govt data dir not found: $SRC_DIR (skipping)"
  exit 0
fi

shopt -s nullglob
zips=("$SRC_DIR"/*.zip)
if [[ ${#zips[@]} -eq 0 ]]; then
  echo "No zips in $SRC_DIR"
  exit 0
fi

for z in "${zips[@]}"; do
  name="$(basename "$z" .zip)"
  out="$DEST/$name"
  if [[ -d "$out" ]]; then
    echo "skip (exists): $name"
    continue
  fi
  echo "extract: $name → $out"
  mkdir -p "$out"
  unzip -q -o "$z" -d "$out"
done

echo "✓ extract complete → $DEST"
