#!/usr/bin/env python3
"""seed_demo_real.py — alternative seeder using REAL UK FTSE company names.

Difference from `seed.py`: instead of synthesized "OLD STREET HOLDINGS LIMITED"-
style names, the owners are real publicly-traded UK companies that resolve
directly via Companies House search. This means:
- No enrichment fallback step needed (but enrich_demo_leads.py still works)
- Demo flow shows real plc names from the start
- 50 leads, 5 demo postcodes, deterministic via random.seed(42)

Each lead gets a stub `companies` doc inserted with the real name + null
ch_number (filled in by enrich_demo_leads.py).

Usage:
    cd "/Users/lukedudley/Downloads/SolarReach Mongo Hackathon"
    export MONGO_URI="mongodb://solarreach:solarreach@localhost:27017/solarreach?authSource=admin"
    python scripts/seed_demo_real.py [--reset] [--count 50]
"""

from __future__ import annotations

import argparse
import os
import random
import sys
import uuid
from datetime import datetime, timezone

try:
    from pymongo import MongoClient, ReplaceOne, errors as pymongo_errors
except ImportError as e:
    print(f"ERROR: pymongo not installed: {e}", file=sys.stderr)
    sys.exit(1)

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


# Approx postcode centroids (lng, lat).
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

# REAL UK plcs / large companies, plausibly holding commercial property near
# each demo postcode. The name strings are precisely what Companies House
# search returns, so enrichment finds them without fuzz.
REAL_OWNERS_BY_POSTCODE: dict[str, list[tuple[str, str]]] = {
    # (CompanyName, premises_type)
    "EC1Y 8AF": [
        ("BARCLAYS PLC", "office"),
        ("LLOYDS BANKING GROUP PLC", "office"),
        ("VODAFONE GROUP PLC", "office"),
        ("HSBC HOLDINGS PLC", "office"),
        ("BT GROUP PLC", "office"),
    ],
    "EC1V 9FR": [
        ("PRUDENTIAL PLC", "office"),
        ("AVIVA PLC", "office"),
        ("LEGAL & GENERAL GROUP PLC", "office"),
        ("LAND SECURITIES GROUP PLC", "office"),
        ("BRITISH LAND COMPANY PLC", "office"),
    ],
    "WC1H 0PD": [
        ("RECKITT BENCKISER GROUP PLC", "office"),
        ("UNILEVER PLC", "office"),
        ("DIAGEO PLC", "office"),
        ("ASTRAZENECA PLC", "office"),
        ("GLAXOSMITHKLINE PLC", "office"),
    ],
    "BS1 4ST": [
        ("ROLLS-ROYCE HOLDINGS PLC", "warehouse"),
        ("BAE SYSTEMS PLC", "warehouse"),
        ("IMPERIAL BRANDS PLC", "warehouse"),
        ("NATIONAL GRID PLC", "office"),
        ("TESCO PLC", "retail"),
    ],
    "BS2 0PT": [
        ("SAINSBURY (J) PLC", "retail"),
        ("MARKS AND SPENCER GROUP P.L.C.", "retail"),
        ("BERKELEY GROUP HOLDINGS PLC", "office"),
        ("TAYLOR WIMPEY PLC", "office"),
        ("ROYAL MAIL PLC", "warehouse"),
    ],
}

STREET_NAMES = {
    "EC1Y 8AF": ["Old Street", "City Road", "Featherstone Street", "Mallow Street"],
    "EC1V 9FR": ["Clerkenwell Road", "Goswell Road", "St John Street", "Lever Street"],
    "WC1H 0PD": ["Tavistock Square", "Gordon Square", "Endsleigh Street", "Woburn Place"],
    "BS1 4ST": ["Corn Street", "Baldwin Street", "St Stephens Avenue", "Welsh Back"],
    "BS2 0PT": ["City Road", "Stokes Croft", "Ashley Road", "Brunswick Street"],
}


def _gen_lead(rng: random.Random, idx: int, client_id: str) -> tuple[dict, dict]:
    """Generate (lead_doc, company_stub_doc).

    company_stub has _id but null ch_number — enrich_demo_leads.py fills the
    real ch_number once Companies House search resolves the name.
    """
    postcode = rng.choice(list(POSTCODE_CENTROIDS.keys()))
    base_lng, base_lat = POSTCODE_CENTROIDS[postcode]
    lng = base_lng + rng.uniform(-0.0015, 0.0015)
    lat = base_lat + rng.uniform(-0.0010, 0.0010)

    name, premises_type = rng.choice(REAL_OWNERS_BY_POSTCODE[postcode])
    street = rng.choice(STREET_NAMES[postcode])
    house_no = rng.randint(1, 240)
    address = f"{house_no} {street}, {postcode}"

    # Synthesized rooftop polygon ~ 30m x 20m rectangle.
    dx = 0.00027
    dy = 0.00018
    poly = [
        [lng - dx, lat - dy],
        [lng + dx, lat - dy],
        [lng + dx, lat + dy],
        [lng - dx, lat + dy],
        [lng - dx, lat - dy],
    ]
    area_m2 = 30.0 * 20.0

    type_bias = {
        "warehouse": (0.85, 0.65, 0.45),
        "retail": (0.75, 0.70, 0.55),
        "office": (0.78, 0.80, 0.50),
        "leisure": (0.72, 0.65, 0.65),
        "education": (0.68, 0.55, 0.85),
    }[premises_type]
    # Plausible 60-95 range driven by the unit-interval inputs + composite_score.
    solar_roi = max(0.0, min(1.0, type_bias[0] + rng.gauss(0.0, 0.06)))
    fin_health = max(0.0, min(1.0, type_bias[1] + rng.gauss(0.0, 0.06)))
    social_impact = max(0.0, min(1.0, type_bias[2] + rng.gauss(0.0, 0.06)))
    score = composite_score(solar_roi, fin_health, social_impact)

    panel_count = max(8, int(area_m2 * 0.5 / 1.7))
    annual_kwh = panel_count * 380.0
    cap = capex(panel_count)
    asg = annual_saving_gbp(annual_kwh)
    pyrs = payback_years(cap, asg)
    npv = npv_25yr(cap, asg)

    now = datetime.now(timezone.utc).isoformat()
    lead_id = f"lead_{uuid.UUID(int=rng.getrandbits(128), version=4)}"
    # Stable company_id by name slug so duplicates collide.
    name_slug = "".join(c if c.isalnum() else "_" for c in name.lower())[:32].strip("_")
    company_id = f"company_seed_{name_slug}"

    company_stub = {
        "_id": company_id,
        "name": name.title() if name.isupper() else name,
        "ccod_proprietor_name": name,
        "ch_number": None,  # filled by enrich_demo_leads.py
        "registered_address": None,
        "title_number": None,
        "directors": [],
        "embedding": None,
    }

    lead = {
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
            "company_id": company_id,
            "company_name": name.title() if name.isupper() else name,
            "source": "real_owners_whitelist",
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
    return lead, company_stub


def _seed_clients(db) -> None:
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
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument("--reset", action="store_true", help="Drop leads + companies first")
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--client-id", default="client-greensolar-uk")
    args = parser.parse_args()

    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("ERROR: MONGO_URI is required.", file=sys.stderr)
        return 1
    if "authSource=" not in uri and "mongodb+srv://" not in uri:
        print("WARN: MONGO_URI lacks authSource=admin (cardinal rule 6).", file=sys.stderr)

    print("[seed_demo_real] connecting to Mongo ...")
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")
    except pymongo_errors.PyMongoError as e:
        print(f"ERROR: cannot reach Mongo: {e}", file=sys.stderr)
        return 1

    try:
        _default_db = client.get_default_database()
    except Exception:
        _default_db = None
    db = _default_db if _default_db is not None else client["solarreach"]

    if args.reset:
        print("[seed_demo_real] --reset: dropping leads + companies ...")
        db["leads"].drop()
        db["companies"].drop()

    _seed_clients(db)

    rng = random.Random(42)
    pairs = [_gen_lead(rng, i, args.client_id) for i in range(args.count)]

    # Companies first (FK target).
    co_ops: list[ReplaceOne] = []
    seen_co: set[str] = set()
    for _, co in pairs:
        if co["_id"] in seen_co:
            continue
        seen_co.add(co["_id"])
        co_ops.append(ReplaceOne({"_id": co["_id"]}, co, upsert=True))
    if co_ops:
        co_res = db["companies"].bulk_write(co_ops, ordered=False)
        print(
            f"[seed_demo_real] companies upserted={co_res.upserted_count} "
            f"matched={co_res.matched_count}"
        )

    lead_ops = [ReplaceOne({"_id": lead["_id"]}, lead, upsert=True) for lead, _ in pairs]
    res = db["leads"].bulk_write(lead_ops, ordered=False)
    print(
        f"[seed_demo_real] leads upserted={res.upserted_count} matched={res.matched_count} "
        f"modified={res.modified_count}"
    )

    total = db["leads"].count_documents({})
    print(f"[seed_demo_real] leads collection now has {total} documents")
    print("[seed_demo_real] done — run scripts/enrich_demo_leads.py next to wire CH directors.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
