#!/usr/bin/env python3
"""export_for_rian.py — dump SolarReach Atlas data for ingestion by Rian's
``solarreach-project1`` agentic stack.

Outputs (under ``exports/`` at repo root):

    leads.jsonl              — one JSON doc per line, all docs in `leads`
    companies.jsonl          — one JSON doc per line, all docs in `companies`
    directors.jsonl          — one JSON doc per line, all docs in `directors`
    industry_benchmarks.json — INDUSTRY_BENCHMARKS dict from solarreach_shared
    audit_summary.json       — counts/aggregates of `audit_log` (no PII)

Cardinal rules respected:
- We do NOT export raw `audit_log` rows because they may contain
  ``recipient_sha256`` hashes that, while non-reversible, are still PII-adjacent.
  Only aggregate counts/sums leave the cluster.
- Mongo URI must include ``authSource=admin`` for local dev (rule 6).
- Idempotent: each run overwrites prior export files.

Usage::

    cd "/Users/lukedudley/Downloads/SolarReach Mongo Hackathon"
    export MONGO_URI="mongodb+srv://...?authSource=admin"
    python scripts/export_for_rian.py [--out exports] [--db solarreach]

Env reads (auto-loaded via ``.env.local`` / ``.env`` if available)::

    MONGO_URI   — Mongo connection string (must include authSource for local)
    MONGO_DB    — defaults to "solarreach"
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# --- repo path bootstrap so we can import solarreach_shared ---
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "packages" / "shared" / "py"))

# Best-effort .env loader so the script works from project root.
try:
    from dotenv import load_dotenv  # type: ignore

    load_dotenv(_REPO_ROOT / ".env.local")
    load_dotenv(_REPO_ROOT / ".env")
except Exception:
    pass

try:
    from pymongo import MongoClient
    from pymongo import errors as pymongo_errors
except ImportError as e:  # pragma: no cover
    print(f"ERROR: pymongo not installed: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from solarreach_shared.industry_benchmarks import INDUSTRY_BENCHMARKS
except ImportError as e:  # pragma: no cover
    print(
        f"ERROR: solarreach_shared not importable: {e}\n"
        "  Run from repo root, or `pip install -e packages/shared/py`.",
        file=sys.stderr,
    )
    sys.exit(1)


def _json_default(o: Any) -> Any:
    """JSON serializer for objects pymongo returns (datetime, ObjectId, tuple)."""
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, tuple):
        return list(o)
    # ObjectId / Decimal128 / bytes — fall back to string repr.
    return str(o)


def _dump_jsonl(docs: Iterable[dict], out_path: Path) -> int:
    n = 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for doc in docs:
            f.write(json.dumps(doc, default=_json_default, ensure_ascii=False))
            f.write("\n")
            n += 1
    return n


def _dump_json(obj: Any, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, default=_json_default, ensure_ascii=False, indent=2)


def export_collection(db, name: str, out_path: Path) -> int:
    """Stream a whole collection to JSONL. Returns the row count."""
    cursor = db[name].find({})
    return _dump_jsonl(cursor, out_path)


def build_audit_summary(db) -> dict[str, Any]:
    """Aggregate audit_log into a PII-free summary.

    Counts by action, total cost in cents, distinct lead/recipient counts,
    earliest/latest timestamps. No raw rows leave the cluster.
    """
    total = db.audit_log.count_documents({})
    if total == 0:
        return {
            "row_count": 0,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    actions: Counter[str] = Counter()
    actors: Counter[str] = Counter()
    cost_cents = 0
    distinct_leads: set[str] = set()
    distinct_recipients: set[str] = set()
    earliest: str | None = None
    latest: str | None = None

    # Project just what we need so we don't drag full metadata into memory.
    proj = {
        "ts": 1,
        "action": 1,
        "actor": 1,
        "lead_id": 1,
        "cost_cents": 1,
        "recipient_sha256": 1,
    }
    for doc in db.audit_log.find({}, proj):
        action = doc.get("action") or "unknown"
        actor = doc.get("actor") or "unknown"
        actions[action] += 1
        actors[actor] += 1
        cost_cents += int(doc.get("cost_cents") or 0)
        if doc.get("lead_id"):
            distinct_leads.add(str(doc["lead_id"]))
        if doc.get("recipient_sha256"):
            distinct_recipients.add(str(doc["recipient_sha256"]))
        ts = doc.get("ts")
        if ts:
            ts_str = str(ts)
            if earliest is None or ts_str < earliest:
                earliest = ts_str
            if latest is None or ts_str > latest:
                latest = ts_str

    return {
        "row_count": total,
        "actions": dict(actions),
        "actors": dict(actors),
        "total_cost_cents": cost_cents,
        "distinct_lead_count": len(distinct_leads),
        "distinct_recipient_hash_count": len(distinct_recipients),
        "earliest_ts": earliest,
        "latest_ts": latest,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Export SolarReach Atlas data for Rian's project1 ingestion."
    )
    parser.add_argument(
        "--out",
        default=str(_REPO_ROOT / "exports"),
        help="Output directory (default: <repo>/exports).",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("MONGO_DB", "solarreach"),
        help="Mongo database name (default: env MONGO_DB or 'solarreach').",
    )
    args = parser.parse_args()

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print(
            "ERROR: MONGO_URI env var is not set.\n"
            "  Set it in .env.local or export it before running.",
            file=sys.stderr,
        )
        return 1
    if "authSource=" not in uri and "mongodb+srv" not in uri:
        print(
            "WARN: MONGO_URI lacks `authSource=admin` — local Docker setups will "
            "fail to auth (CONTRACTS § 7 rule 6).",
            file=sys.stderr,
        )

    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[export] connecting to Mongo db={args.db} ...")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except pymongo_errors.PyMongoError as e:
        print(f"ERROR: cannot reach Mongo: {e}", file=sys.stderr)
        return 1

    db = client[args.db]

    leads_n = export_collection(db, "leads", out_dir / "leads.jsonl")
    print(f"[export] leads          → {leads_n} rows")

    companies_n = export_collection(db, "companies", out_dir / "companies.jsonl")
    print(f"[export] companies      → {companies_n} rows")

    directors_n = export_collection(db, "directors", out_dir / "directors.jsonl")
    print(f"[export] directors      → {directors_n} rows")

    _dump_json(
        dict(INDUSTRY_BENCHMARKS),
        out_dir / "industry_benchmarks.json",
    )
    print(f"[export] benchmarks     → {len(INDUSTRY_BENCHMARKS)} keys")

    summary = build_audit_summary(db)
    _dump_json(summary, out_dir / "audit_summary.json")
    print(f"[export] audit_summary  → {summary.get('row_count', 0)} rows aggregated")

    # Manifest so Rian's ingester can sanity-check the bundle.
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_db": args.db,
        "files": {
            "leads.jsonl": leads_n,
            "companies.jsonl": companies_n,
            "directors.jsonl": directors_n,
            "industry_benchmarks.json": len(INDUSTRY_BENCHMARKS),
            "audit_summary.json": summary.get("row_count", 0),
        },
        "schema_doc": "docs/CONTRACTS.md § 1",
    }
    _dump_json(manifest, out_dir / "manifest.json")
    print(f"[export] wrote manifest → {out_dir / 'manifest.json'}")
    print("[export] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
