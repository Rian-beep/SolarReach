#!/usr/bin/env python3
"""enrich_demo_leads.py — wire REAL Companies House data onto demo leads.

The demo flow needs real directors so the Opus org-chart inferer can pick a real
CFO/MD. This script:

1. Picks the top-N leads by composite_score in the demo postcodes.
2. For each lead, searches Companies House for the lead.owner.company_name; if
   that fails (synthesized "Demo Holdings N Ltd" names won't match), falls back
   to a curated whitelist of real UK FTSE-150 / large-cap commercial property
   owners that plausibly hold buildings near each demo postcode.
3. Upserts a real `companies` doc with the CH number + registered address.
4. Pulls /officers from CH and upserts the directors into `directors` (~5 each).
5. Links lead.owner.company_id to the matched company.

Idempotent: pass `--reset-companies` to drop companies + directors first.
Cost: 0p (Companies House is free; we sleep 0.6s between calls).

Usage:
    cd "/Users/lukedudley/Downloads/SolarReach Mongo Hackathon"
    export MONGO_URI="mongodb://solarreach:solarreach@localhost:27017/solarreach?authSource=admin"
    export COMPANIES_HOUSE_API_KEY="<key>"
    python scripts/enrich_demo_leads.py [--top 10] [--reset-companies]

Env reads (auto-loaded via .env.local if available):
    MONGO_URI                 — Mongo connection string (must include authSource for local)
    MONGO_DB                  — defaults to "solarreach"
    COMPANIES_HOUSE_API_KEY   — required (HTTP Basic; key as username, blank password)
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import uuid
from datetime import datetime, timezone

# --- repo path bootstrap so we can import the API service module directly ---
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_REPO_ROOT, "packages", "api"))

# Best-effort .env.local loader so the script works from project root.
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv(os.path.join(_REPO_ROOT, ".env.local"))
    load_dotenv(os.path.join(_REPO_ROOT, ".env"))
except Exception:
    pass

try:
    from motor.motor_asyncio import AsyncIOMotorClient
except ImportError as e:
    print(f"ERROR: motor not installed: {e}", file=sys.stderr)
    sys.exit(1)

from app.services.companies_house import CompaniesHouseClient  # noqa: E402

log = logging.getLogger("solarreach.enrich_demo_leads")
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


# --- Demo postcodes (must match seed.py) ---
DEMO_POSTCODES = ["EC1Y 8AF", "EC1V 9FR", "WC1H 0PD", "BS1 4ST", "BS2 0PT"]


# --- Real-companies whitelist per postcode ---
# Hand-picked FTSE-150 / well-known UK plcs that plausibly own commercial
# property near each demo postcode. CH search resolves these by name, so the
# fallback always finds REAL officer rows. Each list is ordered roughly by
# preference; we round-robin if the same postcode appears twice.
REAL_COMPANIES_BY_POSTCODE: dict[str, list[str]] = {
    "EC1Y 8AF": [
        "BARCLAYS PLC",
        "LLOYDS BANKING GROUP PLC",
        "VODAFONE GROUP PLC",
        "HSBC HOLDINGS PLC",
        "BT GROUP PLC",
    ],
    "EC1V 9FR": [
        "PRUDENTIAL PLC",
        "AVIVA PLC",
        "LEGAL & GENERAL GROUP PLC",
        "LAND SECURITIES GROUP PLC",
        "BRITISH LAND COMPANY PLC",
    ],
    "WC1H 0PD": [
        "RECKITT BENCKISER GROUP PLC",
        "GLAXOSMITHKLINE PLC",
        "ASTRAZENECA PLC",
        "UNILEVER PLC",
        "DIAGEO PLC",
    ],
    "BS1 4ST": [
        "ROLLS-ROYCE HOLDINGS PLC",
        "BAE SYSTEMS PLC",
        "AIRBUS OPERATIONS LIMITED",
        "IMPERIAL BRANDS PLC",
        "NATIONAL GRID PLC",
    ],
    "BS2 0PT": [
        "TESCO PLC",
        "SAINSBURY (J) PLC",
        "MARKS AND SPENCER GROUP P.L.C.",
        "BERKELEY GROUP HOLDINGS PLC",
        "TAYLOR WIMPEY PLC",
    ],
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _pick_top_leads(db, top_n: int) -> list[dict]:
    """Top-N leads in demo postcodes by composite_score desc."""
    cursor = db.leads.find(
        {"postcode": {"$in": DEMO_POSTCODES}}
    ).sort("scores.composite_score", -1).limit(top_n)
    return [doc async for doc in cursor]


async def _resolve_real_company(
    ch: CompaniesHouseClient, lead: dict, fallback_used: set[str]
) -> tuple[str, dict] | None:
    """Find a real CH company for this lead.

    Strategy:
    1. Try lead.owner.company_name (often synthesized — usually misses).
    2. Walk REAL_COMPANIES_BY_POSTCODE[postcode] and use the first not-yet-used.

    Returns (ch_number, raw_company_detail.raw) or None on total failure.
    """
    owner_name = (lead.get("owner") or {}).get("company_name") or ""
    postcode = lead.get("postcode") or ""

    # 1) Try the actual seeded name (cheap — usually fails for synthesized names)
    if owner_name:
        try:
            results = await ch.search_company(owner_name, limit=3)
            for r in results:
                if r.ch_number and r.ch_number not in fallback_used:
                    detail = await ch.get_company(r.ch_number)
                    if detail and detail.ch_number:
                        log.info(
                            "[enrich] direct match owner=%s -> %s (%s)",
                            owner_name, detail.name, detail.ch_number,
                        )
                        return detail.ch_number, detail.raw
        except Exception as e:
            log.warning("[enrich] direct search failed for %r: %s", owner_name, type(e).__name__)

    # 2) Fallback: real-companies whitelist for this postcode
    candidates = REAL_COMPANIES_BY_POSTCODE.get(postcode, [])
    for cand in candidates:
        try:
            results = await ch.search_company(cand, limit=3)
        except Exception as e:
            log.warning("[enrich] CH search failed for %r: %s", cand, type(e).__name__)
            continue
        # Take the first result whose ch_number is unused.
        for r in results:
            if not r.ch_number or r.ch_number in fallback_used:
                continue
            try:
                detail = await ch.get_company(r.ch_number)
            except Exception as e:
                log.warning(
                    "[enrich] CH company lookup failed for %s: %s", r.ch_number, type(e).__name__
                )
                continue
            if detail and detail.ch_number:
                fallback_used.add(detail.ch_number)
                log.info(
                    "[enrich] fallback match for postcode=%s -> %s (%s)",
                    postcode, detail.name, detail.ch_number,
                )
                return detail.ch_number, detail.raw
    log.warning("[enrich] could not resolve any company for lead=%s postcode=%s",
                lead.get("_id"), postcode)
    return None


async def _upsert_company(db, raw: dict) -> str:
    """Upsert the companies doc. Returns _id."""
    ch_number = raw.get("company_number")
    if not ch_number:
        raise RuntimeError("CH detail missing company_number")
    # Stable _id by ch_number so re-runs collide.
    company_id = f"company_ch_{ch_number}"
    name = (raw.get("company_name") or "").strip()
    ra = raw.get("registered_office_address") or {}
    addr = ", ".join(
        [
            str(v).strip()
            for v in (
                ra.get("address_line_1"),
                ra.get("address_line_2"),
                ra.get("locality"),
                ra.get("region"),
                ra.get("postal_code"),
            )
            if v
        ]
    ) or None
    doc = {
        "_id": company_id,
        "name": name.title() if name.isupper() else name,
        "ccod_proprietor_name": name,  # we don't have a real CCOD link, store name
        "ch_number": ch_number,
        "registered_address": addr,
        "title_number": None,
        "directors": [],
        "embedding": None,
        "enriched_at": _now_iso(),
    }
    await db.companies.update_one(
        {"_id": company_id}, {"$set": doc}, upsert=True
    )
    return company_id


async def _upsert_directors(db, ch: CompaniesHouseClient, ch_number: str, company_id: str) -> int:
    """Pull officers for ch_number and upsert ~5 directors. Returns count upserted."""
    try:
        officers = await ch.get_officers(ch_number, limit=20)
    except Exception as e:
        log.warning("[enrich] /officers failed for %s: %s", ch_number, type(e).__name__)
        return 0
    if not officers:
        log.warning("[enrich] no officers for %s", ch_number)
        return 0

    # Prefer current directors first, take up to 5.
    def _is_current_director(o):
        return (o.role or "").upper() in {"DIRECTOR", "LLP MEMBER", "LLP DESIGNATED MEMBER"} \
               and not o.resigned_on

    current = [o for o in officers if _is_current_director(o)]
    others = [o for o in officers if not _is_current_director(o)]
    chosen = (current + others)[:5]

    director_ids: list[str] = []
    for off in chosen:
        if off.ch_officer_id:
            director_id = f"director_{company_id[:24]}_{off.ch_officer_id[:24]}"
        else:
            tag = f"{off.name}|{off.role}|{off.appointed_on or ''}"
            tag_hash = uuid.uuid5(uuid.NAMESPACE_OID, tag).hex[:16]
            director_id = f"director_{company_id[:24]}_{tag_hash}"
        doc = {
            "_id": director_id,
            "company_id": company_id,
            "name": off.name,
            "name_display": off.name_display,
            "role": off.role,
            "appointed_on": off.appointed_on,
            "resigned_on": off.resigned_on,
            "ch_officer_id": off.ch_officer_id or None,
            "occupation": off.occupation,
            "nationality": off.nationality,
        }
        await db.directors.update_one(
            {"_id": director_id}, {"$set": doc}, upsert=True
        )
        director_ids.append(director_id)

    await db.companies.update_one(
        {"_id": company_id}, {"$set": {"directors": director_ids}}
    )
    return len(director_ids)


async def _link_lead_to_company(db, lead_id: str, company_id: str, company_name: str) -> None:
    await db.leads.update_one(
        {"_id": lead_id},
        {
            "$set": {
                "owner.company_id": company_id,
                "owner.company_name": company_name,
                "owner.source": "ch_enriched",
                "updated_at": _now_iso(),
            }
        },
    )


async def run(top_n: int, reset_companies: bool) -> int:
    uri = os.environ.get("MONGO_URI")
    if not uri:
        log.error("MONGO_URI is required.")
        return 1
    if "authSource=" not in uri and "mongodb+srv://" not in uri:
        log.warning("MONGO_URI lacks authSource=admin — local Docker will fail (cardinal rule 6)")
    ch_key = os.environ.get("COMPANIES_HOUSE_API_KEY")
    if not ch_key:
        log.error("COMPANIES_HOUSE_API_KEY is required (free at developer.company-information.service.gov.uk).")
        return 1

    db_name = os.environ.get("MONGO_DB", "solarreach")
    log.info("[enrich] connecting to Mongo db=%s ...", db_name)
    client = AsyncIOMotorClient(uri, serverSelectionTimeoutMS=8000)
    try:
        await client.admin.command("ping")
    except Exception as e:  # noqa: BLE001
        log.error("Mongo unreachable: %s", type(e).__name__)
        return 1
    db = client[db_name]

    if reset_companies:
        log.info("[enrich] --reset-companies: dropping companies + directors")
        await db.companies.drop()
        await db.directors.drop()

    leads = await _pick_top_leads(db, top_n)
    if not leads:
        log.error("[enrich] no leads found in demo postcodes — run scripts/seed.py first.")
        client.close()
        return 1
    log.info("[enrich] picked %d top leads", len(leads))

    fallback_used: set[str] = set()
    total_directors = 0
    enriched_leads = 0

    async with CompaniesHouseClient(ch_key, db=db, actor="agent_a7_enrich") as ch:
        for lead in leads:
            lead_id = lead["_id"]
            log.info(
                "[enrich] lead=%s postcode=%s owner=%s",
                lead_id, lead.get("postcode"), (lead.get("owner") or {}).get("company_name"),
            )
            resolved = await _resolve_real_company(ch, lead, fallback_used)
            if not resolved:
                log.warning("[enrich] skip lead=%s — no resolvable company", lead_id)
                continue
            ch_number, raw_company = resolved
            try:
                company_id = await _upsert_company(db, raw_company)
            except Exception as e:  # noqa: BLE001
                log.warning("[enrich] upsert_company failed lead=%s err=%s", lead_id, type(e).__name__)
                continue

            n_dirs = await _upsert_directors(db, ch, ch_number, company_id)
            total_directors += n_dirs

            await _link_lead_to_company(
                db, lead_id, company_id, raw_company.get("company_name") or "Unknown"
            )
            enriched_leads += 1
            log.info(
                "[enrich]   linked lead=%s -> company_id=%s directors=%d",
                lead_id, company_id, n_dirs,
            )

    # Final report
    leads_count = await db.leads.count_documents({})
    co_count = await db.companies.count_documents({})
    dir_count = await db.directors.count_documents({})
    log.info(
        "[enrich] DONE leads_enriched=%d directors_upserted=%d total_dirs_in_db=%d companies=%d leads=%d",
        enriched_leads, total_directors, dir_count, co_count, leads_count,
    )
    client.close()
    return 0 if (enriched_leads >= 1 and dir_count >= 1) else 2


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument("--top", type=int, default=10, help="Number of top leads to enrich")
    parser.add_argument("--reset-companies", action="store_true",
                        help="Drop companies + directors first")
    args = parser.parse_args()
    return asyncio.run(run(top_n=args.top, reset_companies=args.reset_companies))


if __name__ == "__main__":
    sys.exit(main())
