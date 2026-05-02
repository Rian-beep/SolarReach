#!/usr/bin/env python3
"""ingest_ccod_subset.py — stream HM Land Registry CCOD CSV from a zip,
filter to rows whose property_address contains our target postcodes,
and upsert into `companies`.

Source zip default: ~/Downloads/Hackathon Govt Data/CCOD_FULL_2026_04.zip

Usage:
    MONGO_URI="..." python scripts/ingest_ccod_subset.py [--zip-path PATH] [--limit 5000]
"""

from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import uuid
import zipfile
from typing import Iterator

try:
    from pymongo import MongoClient, ReplaceOne, errors as pymongo_errors
except ImportError as e:  # pragma: no cover
    print(f"ERROR: pymongo not installed: {e}", file=sys.stderr)
    sys.exit(1)


_DEFAULT_ZIP = os.path.expanduser(
    "~/Downloads/Hackathon Govt Data/CCOD_FULL_2026_04.zip"
)

# Postcode prefixes (note: CCOD addresses use no space, e.g. "EC1Y8AF" — match prefix).
TARGET_PREFIXES = ["EC1Y", "EC1V", "WC1H", "BS1 ", "BS2 ", "BS1,", "BS2,"]


def _open_csv_in_zip(zip_path: str) -> Iterator[dict]:
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"CCOD zip not found: {zip_path}")
    with zipfile.ZipFile(zip_path) as zf:
        # Find the .csv inside the zip.
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise RuntimeError(f"No .csv in {zip_path}")
        member = members[0]
        with zf.open(member, "r") as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
            reader = csv.DictReader(text)
            for row in reader:
                yield row


def _row_matches(row: dict) -> bool:
    addr = (row.get("Property Address") or row.get("property_address") or "").upper()
    if not addr:
        return False
    return any(p in addr for p in TARGET_PREFIXES)


def _to_company_doc(row: dict) -> dict:
    name = (
        row.get("Proprietor Name (1)")
        or row.get("Proprietor Name")
        or row.get("proprietor_name")
        or "UNKNOWN"
    ).strip()
    title_no = (row.get("Title Number") or row.get("title_number") or "").strip() or None
    addr = (row.get("Property Address") or row.get("property_address") or "").strip()
    reg_addr = (
        row.get("Proprietor (1) Address (1)")
        or row.get("Proprietor Address (1)")
        or ""
    ).strip() or None
    ch_no = (row.get("Company Registration No. (1)") or "").strip() or None

    return {
        "_id": f"company_{uuid.uuid4().hex[:16]}",
        "name": name.title() if name.isupper() else name,
        "ccod_proprietor_name": name,
        "ch_number": ch_no,
        "title_number": title_no,
        "registered_address": reg_addr,
        "property_address": addr,
        "directors": [],
        "embedding": None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip-path", default=_DEFAULT_ZIP)
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("ERROR: MONGO_URI env var is required.", file=sys.stderr)
        return 1
    if "authSource=" not in uri:
        print("WARN: MONGO_URI lacks `authSource=admin` (cardinal rule 6).", file=sys.stderr)

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except pymongo_errors.PyMongoError as e:
        print(f"ERROR: cannot reach Mongo: {e}", file=sys.stderr)
        return 1

    db = client.get_default_database() or client["solarreach"]
    coll = db["companies"]

    print(f"[ingest_ccod_subset] reading {args.zip_path}")
    BATCH_SIZE = 500
    batch: list[ReplaceOne] = []

    read = 0
    matched = 0
    inserted = 0
    try:
        for row in _open_csv_in_zip(args.zip_path):
            read += 1
            if not _row_matches(row):
                continue
            matched += 1
            if matched > args.limit:
                break
            doc = _to_company_doc(row)
            # Idempotency: dedupe by (title_number, ccod_proprietor_name) when title is known.
            key = (
                {"title_number": doc["title_number"], "ccod_proprietor_name": doc["ccod_proprietor_name"]}
                if doc["title_number"]
                else {"ccod_proprietor_name": doc["ccod_proprietor_name"], "property_address": doc["property_address"]}
            )
            batch.append(ReplaceOne(key, doc, upsert=True))
            if len(batch) >= BATCH_SIZE:
                res = coll.bulk_write(batch, ordered=False)
                inserted += res.upserted_count + res.modified_count
                batch.clear()
                print(f"[ingest_ccod_subset] read={read} matched={matched} inserted~={inserted}")
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if batch:
        res = coll.bulk_write(batch, ordered=False)
        inserted += res.upserted_count + res.modified_count

    print(
        f"[ingest_ccod_subset] DONE read={read} matched={matched} inserted~={inserted}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
