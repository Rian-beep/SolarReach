#!/usr/bin/env python3
"""match_leads_to_inspire.py — link each lead to nearest INSPIRE polygon (<=200m).

CARDINAL RULE 3: do NOT overwrite if the existing polygon source is already
"inspire_index_polygon".

Usage:
    MONGO_URI="..." python scripts/match_leads_to_inspire.py [--radius-m 200]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone

try:
    from pymongo import MongoClient, errors as pymongo_errors
except ImportError as e:  # pragma: no cover
    print(f"ERROR: pymongo not installed: {e}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--radius-m", type=int, default=200)
    parser.add_argument(
        "--min-area",
        type=float,
        default=50.0,
        help="Minimum INSPIRE polygon area_m2_approx considered plausible.",
    )
    parser.add_argument(
        "--max-area",
        type=float,
        default=5000.0,
        help="Maximum INSPIRE polygon area_m2_approx considered plausible.",
    )
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
    leads = db["leads"]
    polys = db["inspire_polygons"]

    matched = 0
    skipped_already_inspire = 0
    no_match = 0
    bad_area = 0

    cursor = leads.find({}, projection={"_id": 1, "geo": 1, "rooftop_polygon": 1})
    for lead in cursor:
        existing_poly = lead.get("rooftop_polygon") or {}
        existing_source = existing_poly.get("source")
        if existing_source == "inspire_index_polygon":
            skipped_already_inspire += 1
            continue

        point = lead.get("geo", {}).get("point")
        if not point or "coordinates" not in point:
            no_match += 1
            continue

        # Find nearest INSPIRE polygon centroid within radius.
        nearest = polys.find_one(
            {
                "centroid": {
                    "$nearSphere": {
                        "$geometry": point,
                        "$maxDistance": args.radius_m,
                    }
                }
            }
        )
        if not nearest:
            no_match += 1
            continue

        area = nearest.get("area_m2_approx", 0.0)
        if not (args.min_area <= area <= args.max_area):
            bad_area += 1
            continue

        new_poly = {
            "type": "Polygon",
            "coordinates": nearest["polygon"]["coordinates"],
            "source": "inspire_index_polygon",
            "inspire_id": nearest.get("inspire_id"),
            "area_m2_approx": area,
        }
        leads.update_one(
            {"_id": lead["_id"]},
            {
                "$set": {
                    "rooftop_polygon": new_poly,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            },
        )
        matched += 1

    print(
        f"[match_leads_to_inspire] matched={matched} "
        f"skipped_already_inspire={skipped_already_inspire} "
        f"no_match={no_match} bad_area={bad_area}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
