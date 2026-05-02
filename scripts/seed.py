#!/usr/bin/env python3
"""seed.py — populate Mongo with 50 demo leads, deterministic via random.seed(42).

Usage:
    MONGO_URI="mongodb://solarreach:solarreach_dev_password@localhost:27017/solarreach?authSource=admin" \
        python scripts/seed.py [--reset] [--count 50]

Cardinal:
- All EPSG:4326. Postcodes from CONTRACTS-fixed list.
- Idempotent w/o --reset (uses upsert via _id).
- Premises types are bound to name patterns — no random misclassification.
- Rooftop polygon synthesized as a small rectangle around geo.point;
  match_leads_to_inspire.py replaces with INSPIRE polygon when found.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from datetime import datetime, timezone

try:
    from pymongo import MongoClient, errors as pymongo_errors
except ImportError as e:  # pragma: no cover
    print(f"ERROR: pymongo not installed: {e}", file=sys.stderr)
    sys.exit(1)

# --- import shared package; fall back to sibling path so script works from repo root ---
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "packages", "shared", "py"))
from solarreach_shared import constants  # noqa: E402
from solarreach_shared.financial import (  # noqa: E402
    annual_saving_gbp,
    capex,
    composite_score,
    npv_25yr,
    payback_years,
)


# Approx postcode centroids in EPSG:4326 (lng, lat).
POSTCODE_CENTROIDS = {
    "EC1Y 8AF": (-0.0876, 51.5256),  # Old Street / Shoreditch
    "EC1V 9FR": (-0.0986, 51.5274),  # Clerkenwell
    "WC1H 0PD": (-0.1278, 51.5260),  # Bloomsbury
    "BS1 4ST": (-2.5879, 51.4545),   # Bristol central
    "BS2 0PT": (-2.5701, 51.4632),   # Bristol St Pauls
}

POSTCODE_BOROUGH = {
    "EC1Y 8AF": "London Borough of Islington",
    "EC1V 9FR": "London Borough of Islington",
    "WC1H 0PD": "London Borough of Camden",
    "BS1 4ST": "Bristol City Council",
    "BS2 0PT": "Bristol City Council",
}

# Name pattern -> premises_type. Names look like CCOD entries (uppercased ltd).
NAME_PATTERNS: list[tuple[str, str]] = [
    ("OLD STREET HOLDINGS LIMITED", "office"),
    ("SHOREDITCH MEDIA WORKS LIMITED", "office"),
    ("CLERKENWELL TECH HUB LIMITED", "office"),
    ("BLOOMSBURY ACADEMY TRUST", "education"),
    ("CAMDEN TOWN LEISURE LIMITED", "leisure"),
    ("ISLINGTON RETAIL PARK LIMITED", "retail"),
    ("BRISTOL HARBOUR WAREHOUSING LIMITED", "warehouse"),
    ("ST PAULS COMMUNITY EDUCATION LIMITED", "education"),
    ("THE OLD STREET GYM COMPANY LIMITED", "leisure"),
    ("FARRINGDON LOGISTICS LIMITED", "warehouse"),
    ("WC1 RETAIL HOLDINGS LIMITED", "retail"),
    ("BLOOMSBURY OFFICE PROPERTIES LIMITED", "office"),
    ("CLERKENWELL FOOD HALL LIMITED", "retail"),
    ("BRISTOL DISTRIBUTION CENTRE LIMITED", "warehouse"),
    ("EC1 SPORTS COMPLEX LIMITED", "leisure"),
    ("CITY EDUCATION ACADEMY", "education"),
    ("OLD STREET STUDIO SPACE LIMITED", "office"),
    ("STOKES CROFT GALLERY LIMITED", "retail"),
    ("BRISTOL UNIVERSITY ANNEXE LIMITED", "education"),
    ("CAMDEN MARKET TRADERS LIMITED", "retail"),
]

STREET_NAMES = {
    "EC1Y 8AF": ["Old Street", "City Road", "Featherstone Street", "Mallow Street"],
    "EC1V 9FR": ["Clerkenwell Road", "Goswell Road", "St John Street", "Lever Street"],
    "WC1H 0PD": ["Tavistock Square", "Gordon Square", "Endsleigh Street", "Woburn Place"],
    "BS1 4ST": ["Corn Street", "Baldwin Street", "St Stephens Avenue", "Welsh Back"],
    "BS2 0PT": ["City Road", "Stokes Croft", "Ashley Road", "Brunswick Street"],
}


def _gen_lead(
    rng: random.Random,
    idx: int,
    client_id: str,
) -> dict:
    postcode = rng.choice(list(POSTCODE_CENTROIDS.keys()))
    base_lng, base_lat = POSTCODE_CENTROIDS[postcode]

    # Jitter ~120m at this latitude. 0.001 deg ~111m.
    lng = base_lng + rng.uniform(-0.0015, 0.0015)
    lat = base_lat + rng.uniform(-0.0010, 0.0010)

    name, premises_type = rng.choice(NAME_PATTERNS)
    street = rng.choice(STREET_NAMES[postcode])
    house_no = rng.randint(1, 240)
    address = f"{house_no} {street}, {postcode}"

    # Synthesized rooftop polygon ~ 30m x 20m rectangle.
    # 0.0003 deg lng @ lat 51.5 ~ 21m; 0.00018 deg lat ~ 20m.
    dx = 0.00027
    dy = 0.00018
    poly = [
        [lng - dx, lat - dy],
        [lng + dx, lat - dy],
        [lng + dx, lat + dy],
        [lng - dx, lat + dy],
        [lng - dx, lat - dy],
    ]
    area_m2 = 30.0 * 20.0  # synthesized

    # Heuristic sub-scores per premises_type, with controlled noise.
    type_bias = {
        "warehouse": (0.85, 0.65, 0.45),
        "retail": (0.75, 0.70, 0.55),
        "office": (0.78, 0.80, 0.50),
        "leisure": (0.72, 0.65, 0.65),
        "education": (0.68, 0.55, 0.85),
    }[premises_type]
    solar_roi = max(0.0, min(1.0, type_bias[0] + rng.uniform(-0.10, 0.10)))
    fin_health = max(0.0, min(1.0, type_bias[1] + rng.uniform(-0.10, 0.10)))
    social_impact = max(0.0, min(1.0, type_bias[2] + rng.uniform(-0.10, 0.10)))

    score = composite_score(solar_roi, fin_health, social_impact)

    # Modelled panel count: ~ rooftop_m2 * 0.5 / (panel area ~1.7m^2)
    panel_count = max(8, int(area_m2 * 0.5 / 1.7))
    annual_kwh = panel_count * 380.0  # London-ish 380 kWh/yr/panel
    cap = capex(panel_count)
    asg = annual_saving_gbp(annual_kwh)
    pyrs = payback_years(cap, asg)
    npv = npv_25yr(cap, asg)

    now = datetime.now(timezone.utc).isoformat()
    lead_id = f"lead_{uuid.UUID(int=rng.getrandbits(128), version=4)}"

    return {
        "_id": lead_id,
        "client_id": client_id,
        "address": address,
        "postcode": postcode,
        "borough": POSTCODE_BOROUGH[postcode],
        "premises_type": premises_type,
        "geo": {"point": {"type": "Point", "coordinates": [lng, lat]}},
        "rooftop_polygon": {
            "type": "Polygon",
            "coordinates": [poly],
            "source": "synthesized",
            "inspire_id": None,
            "area_m2_approx": area_m2,
        },
        "scores": {
            "solar_roi": round(solar_roi, 4),
            "financial_health": round(fin_health, 4),
            "social_impact": round(social_impact, 4),
            "composite_score": score,
            "scored_at": now,
        },
        "owner": {
            "company_id": None,  # filled later by ingest_ccod_subset.py + matcher
            "company_name": name.title().replace("Limited", "Ltd"),
            "source": "synthesized",
        },
        "panel_layout": {
            "panels": [],
            "panel_count": panel_count,
            "annual_kwh": annual_kwh,
            "clipped_at": None,
            "clip_method": None,
        },
        "financial": {
            "capex_gbp": round(cap, 2),
            "annual_saving_gbp": round(asg, 2),
            "payback_years": round(pyrs, 2) if pyrs != float("inf") else 9999.0,
            "npv_25yr_gbp": round(npv, 2),
        },
        "created_at": now,
        "updated_at": now,
    }


def _seed_clients(db) -> None:
    """Ensure at least one client doc exists."""
    db["clients"].update_one(
        {"_id": "client-greensolar-uk"},
        {
            "$setOnInsert": {
                "_id": "client-greensolar-uk",
                "name": "GreenSolar UK",
                "branding": {
                    "primary": "#0F172A",
                    "logo_url": "https://example.invalid/logo.svg",
                },
                "pricing": {
                    "panel_unit_gbp": constants.PANEL_UNIT_COST_GBP,
                    "install_per_kw_gbp": constants.INSTALL_COST_PER_KW_GBP,
                },
                "session_budget_gbp": 1.00,
            }
        },
        upsert=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo SolarReach data.")
    parser.add_argument("--reset", action="store_true", help="Drop leads collection first.")
    parser.add_argument("--count", type=int, default=50, help="Number of leads to generate.")
    parser.add_argument(
        "--client-id", default="client-greensolar-uk", help="Client _id to assign."
    )
    args = parser.parse_args()

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print(
            "ERROR: MONGO_URI env var is not set. Example:\n"
            "  export MONGO_URI='mongodb://solarreach:solarreach_dev_password@localhost:27017/solarreach?authSource=admin'",
            file=sys.stderr,
        )
        return 1
    if "authSource=" not in uri:
        print(
            "WARN: MONGO_URI lacks `authSource=admin` — local Docker setups will fail to auth (cardinal rule 6).",
            file=sys.stderr,
        )

    print(f"[seed] connecting to Mongo ...")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except pymongo_errors.PyMongoError as e:
        print(f"ERROR: cannot reach Mongo: {e}", file=sys.stderr)
        return 1

    db = client.get_default_database()
    if db is None:
        db = client["solarreach"]

    if args.reset:
        print("[seed] --reset: dropping leads collection ...")
        db["leads"].drop()

    _seed_clients(db)

    rng = random.Random(42)
    leads = [_gen_lead(rng, i, args.client_id) for i in range(args.count)]

    # Bulk upsert by _id for idempotency.
    from pymongo import ReplaceOne

    ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in leads]
    result = db["leads"].bulk_write(ops, ordered=False)
    print(
        f"[seed] upserted={result.upserted_count} matched={result.matched_count} modified={result.modified_count}"
    )

    total = db["leads"].count_documents({})
    print(f"[seed] leads collection now has {total} documents")
    print("[seed] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
