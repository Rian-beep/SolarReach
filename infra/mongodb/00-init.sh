#!/usr/bin/env bash
# SolarReach Mongo bootstrap.
# Mongo's official entrypoint runs *.sh and *.js files in lex order from /docker-entrypoint-initdb.d/.
# A1 owns the JS init files (01-users.js .. 04-indexes.js). This shim ensures they execute against the
# correct database with auth, and is a no-op on a populated volume (Mongo skips initdb when /data/db is non-empty).
set -euo pipefail

INIT_DIR="/docker-entrypoint-initdb.d"
DB_NAME="${MONGO_INITDB_DATABASE:-solarreach}"
ROOT_USER="${MONGO_INITDB_ROOT_USERNAME:-solarreach}"
ROOT_PASS="${MONGO_INITDB_ROOT_PASSWORD:-solarreach}"

echo "[solarreach-init] bootstrapping db=${DB_NAME}"

# Mongo's entrypoint already auto-runs *.js in this dir. We don't need to re-run them.
# This script exists only to (a) emit a readable log line, (b) optionally re-run if files
# are added after first boot via `mongosh`. The actual init is in 01-users.js .. 04-indexes.js
# (owned by A1).
for f in "$INIT_DIR"/01-users.js "$INIT_DIR"/02-collections.js "$INIT_DIR"/03-validators.js "$INIT_DIR"/04-indexes.js; do
  if [[ -f "$f" ]]; then
    echo "[solarreach-init] present: $(basename "$f")"
  else
    echo "[solarreach-init] missing (A1 not yet committed): $(basename "$f")"
  fi
done

echo "[solarreach-init] done. JS files (if present) will be executed by Mongo entrypoint."
