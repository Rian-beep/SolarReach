#!/usr/bin/env python3
"""ingest_real_demo.py — bulk-create 300 demo leads backed by REAL data.

Replaces the synthesized seed leads with:
1. Real INSPIRE rooftop polygons sampled from
   `data/raw/inspire-camden/Land_Registry_Cadastral_Parcels.gml`
   (filtered to area_m2_approx in [400, 5000], reprojected EPSG:27700 -> 4326).
2. Real CCOD owner names streamed from
   `~/Downloads/Hackathon Govt Data/CCOD_FULL_2026_04.zip`,
   filtered to central-London postcodes (EC, WC, SW1, W1, E1, SE1, N1).
   Sample of ~50 plausible companies, round-robin assigned to polygons.
3. Realistic composite scores: clamped normal mean=70 std=12, clamp [40, 95].
   Sub-scores back-derived to keep the schema consistent.
4. Realistic financials: derived from polygon area via existing
   `solarreach_shared.financial` helpers — capex typically £80-300k, payback
   ~7-15yr, NPV calculated.
5. Postcode lookup: centroid -> nearest of a fixed set of Camden / central-London
   anchor postcodes (avoids 300 HTTP calls to postcodes.io).

Idempotency:
- Lead _id pattern: `lead_real_<seed-derived-hex>`.
- Company _id pattern: `company_real_<title-no-or-name-hash>`.
- `--reset-real-leads` drops ONLY docs whose _id matches `^lead_real_` /
  `^company_real_`. Leaves other leads / companies untouched.

Usage:
    cd "/Users/lukedudley/Downloads/SolarReach Mongo Hackathon"
    set -a; source .env.local; set +a
    python3 scripts/ingest_real_demo.py [--count 300] [--reset-real-leads]
"""

from __future__ import annotations

import os
import sys

# Defensive sys.path scrub: a stray `email.py` lives in the repo root and
# shadows the stdlib `email` module if Python adds the repo-root cwd to
# sys.path. pyproj transitively imports `email` via `importlib.metadata`,
# which then explodes. Strip the repo root from sys.path BEFORE any 3rd-party
# imports.
_REPO_ROOT_ABS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path[:] = [p for p in sys.path if os.path.abspath(p or ".") != _REPO_ROOT_ABS]

import argparse  # noqa: E402
import csv  # noqa: E402
import hashlib  # noqa: E402
import io  # noqa: E402
import random  # noqa: E402
import re  # noqa: E402
import uuid  # noqa: E402
import zipfile  # noqa: E402
from datetime import datetime, timezone  # noqa: E402
from typing import Iterator  # noqa: E402

try:
    from lxml import etree
except ImportError as e:  # pragma: no cover
    print(f"ERROR: lxml not installed: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from pyproj import Transformer
except ImportError as e:  # pragma: no cover
    print(f"ERROR: pyproj not installed: {e}", file=sys.stderr)
    sys.exit(1)

try:
    from pymongo import MongoClient, ReplaceOne, errors as pymongo_errors
except ImportError as e:  # pragma: no cover
    print(f"ERROR: pymongo not installed: {e}", file=sys.stderr)
    sys.exit(1)

# Reuse existing scoring/financial helpers.
sys.path.insert(0, os.path.join(_REPO_ROOT_ABS, "packages", "shared", "py"))
from solarreach_shared.financial import (  # noqa: E402
    annual_saving_gbp,
    capex,
    npv_25yr,
    payback_years,
)


# --- Config ---
SEED = 2026

DEFAULT_GML_CAMDEN = os.path.join(
    _REPO_ROOT_ABS, "data", "raw", "inspire-camden", "Land_Registry_Cadastral_Parcels.gml"
)
DEFAULT_GML_CITY = os.path.join(
    _REPO_ROOT_ABS, "data", "raw", "inspire-city", "Land_Registry_LU_Residential.gml"
)
DEFAULT_CCOD_ZIP = os.path.expanduser(
    "~/Downloads/Hackathon Govt Data/CCOD_FULL_2026_04.zip"
)

CLIENT_ID_DEFAULT = "client-greensolar-uk"

# Camden + central London anchor postcodes (approx centroids in EPSG:4326).
# We snap each polygon's centroid to its nearest anchor — avoids 300 HTTP calls
# to postcodes.io while still giving plausible postcode distribution. Anchors
# are dense in Camden (where the bulk of polygons sit) and spread across
# central London so City-of-London polygons land in EC1-EC4.
POSTCODE_ANCHORS: list[tuple[str, float, float, str]] = [
    # postcode, lng, lat, borough
    # --- Camden (dense) ---
    ("NW1 0NU", -0.1490, 51.5392, "London Borough of Camden"),   # Camden Town
    ("NW1 7AY", -0.1432, 51.5354, "London Borough of Camden"),   # Mornington Cresc
    ("NW1 8NH", -0.1551, 51.5418, "London Borough of Camden"),   # Primrose Hill
    ("NW1 2AD", -0.1382, 51.5269, "London Borough of Camden"),   # Euston
    ("NW1 3HZ", -0.1280, 51.5263, "London Borough of Camden"),   # St Pancras
    ("NW3 2QG", -0.1762, 51.5519, "London Borough of Camden"),   # Belsize Park
    ("NW3 5SS", -0.1705, 51.5450, "London Borough of Camden"),   # Swiss Cottage
    ("NW3 6QU", -0.1832, 51.5570, "London Borough of Camden"),   # Hampstead
    ("NW5 1AG", -0.1455, 51.5532, "London Borough of Camden"),   # Kentish Town
    ("NW5 2PA", -0.1400, 51.5483, "London Borough of Camden"),   # Kentish Town S
    ("NW6 4SN", -0.1942, 51.5474, "London Borough of Camden"),   # West Hampstead
    ("WC1H 0PD", -0.1278, 51.5260, "London Borough of Camden"),  # Bloomsbury
    ("WC1N 3XX", -0.1198, 51.5230, "London Borough of Camden"),  # Russell Sq
    ("WC1E 7HX", -0.1340, 51.5220, "London Borough of Camden"),  # Tottenham Ct Rd
    ("WC1B 4DA", -0.1262, 51.5197, "London Borough of Camden"),  # Holborn
    ("WC1V 6LJ", -0.1142, 51.5189, "London Borough of Camden"),  # Holborn
    # --- Westminster ---
    ("WC2H 9JQ", -0.1289, 51.5145, "City of Westminster"),       # Leicester Sq
    ("W1T 4JE", -0.1372, 51.5193, "City of Westminster"),        # Fitzrovia
    ("W1F 8TH", -0.1358, 51.5135, "City of Westminster"),        # Soho
    ("W1B 5TE", -0.1430, 51.5147, "City of Westminster"),        # Oxford Circus
    ("SW1A 1AA", -0.1419, 51.5014, "City of Westminster"),       # Westminster
    ("SW1Y 4UH", -0.1339, 51.5081, "City of Westminster"),       # St James
    # --- Islington ---
    ("N1 9DF", -0.1108, 51.5360, "London Borough of Islington"), # Kings Cross
    ("N1 0RA", -0.1059, 51.5395, "London Borough of Islington"), # Islington
    ("N1 7GU", -0.0937, 51.5365, "London Borough of Islington"), # Angel
    # --- City of London / Clerkenwell / EC ---
    ("EC1V 9FR", -0.0986, 51.5274, "London Borough of Islington"),  # Clerkenwell
    ("EC1Y 8AF", -0.0876, 51.5256, "London Borough of Islington"),  # Old St
    ("EC1A 4HD", -0.1004, 51.5184, "City of London Corporation"),   # Smithfield
    ("EC1M 6BQ", -0.1014, 51.5226, "London Borough of Islington"),  # Farringdon
    ("EC1N 8JS", -0.1097, 51.5180, "City of London Corporation"),   # Holborn Circus
    ("EC2A 3EJ", -0.0826, 51.5232, "London Borough of Hackney"),    # Shoreditch
    ("EC2A 4PS", -0.0817, 51.5249, "London Borough of Hackney"),    # Shoreditch
    ("EC2M 7EB", -0.0863, 51.5189, "City of London Corporation"),   # Liverpool St
    ("EC2V 7HN", -0.0931, 51.5152, "City of London Corporation"),   # Guildhall
    ("EC3A 7BB", -0.0807, 51.5141, "City of London Corporation"),   # Aldgate
    ("EC3V 0BB", -0.0853, 51.5128, "City of London Corporation"),   # Bank
    ("EC3M 3BD", -0.0809, 51.5113, "City of London Corporation"),   # Tower Hill
    ("EC4A 3DE", -0.1110, 51.5147, "City of London Corporation"),   # Fleet St
    ("EC4M 7DN", -0.0980, 51.5145, "City of London Corporation"),   # St Paul's
    ("EC4V 6EE", -0.0980, 51.5121, "City of London Corporation"),   # Blackfriars
    ("EC4N 8AR", -0.0913, 51.5127, "City of London Corporation"),   # Cannon St
    # --- Tower Hamlets / Southwark ---
    ("E1 6AN", -0.0734, 51.5186, "London Borough of Tower Hamlets"),  # Aldgate
    ("E1 7AE", -0.0709, 51.5211, "London Borough of Tower Hamlets"),  # Whitechapel
    ("SE1 9SG", -0.1064, 51.5043, "London Borough of Southwark"),  # Bankside
    ("SE1 7PB", -0.1187, 51.4974, "London Borough of Southwark"),  # Waterloo
    ("SE1 2HZ", -0.0886, 51.5039, "London Borough of Southwark"),  # London Bridge
]

# Premises type bias from area (very rough London commercial heuristic).
# Used only to set realistic-looking sub-scores — composite is sampled directly.
def _premises_type_for_area(rng: random.Random, area_m2: float) -> str:
    if area_m2 >= 2500:
        return rng.choices(["warehouse", "office", "retail"], weights=[0.4, 0.4, 0.2])[0]
    if area_m2 >= 1200:
        return rng.choices(["office", "retail", "leisure", "warehouse"], weights=[0.45, 0.25, 0.15, 0.15])[0]
    if area_m2 >= 700:
        return rng.choices(["office", "retail", "leisure", "education"], weights=[0.5, 0.25, 0.15, 0.10])[0]
    return rng.choices(["office", "retail", "education"], weights=[0.55, 0.25, 0.20])[0]


# CCOD postcode prefix matcher: brief asks for EC, WC, SW1, W1, E1, SE1, N1.
# Use regex: prefix followed by digit OR space (to exclude SW11/W10/E14 etc).
_CCOD_POSTCODE_RE = re.compile(
    r"^(?:EC[1-4]|WC[12]|SW1[A-Z]?|W1[A-Z]?|E1[A-Z]?|SE1[A-Z]?|N1[A-Z]?)(?:\s|$)"
)


# --- GML parsing (reused pattern from ingest_inspire.py) ---
_TF = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
GML_NS = "http://www.opengis.net/gml/3.2"
GML_NS_V31 = "http://www.opengis.net/gml"
POS_LIST_TAGS = {f"{{{GML_NS}}}posList", f"{{{GML_NS_V31}}}posList"}
POLYGON_TAGS = {f"{{{GML_NS}}}Polygon", f"{{{GML_NS_V31}}}Polygon"}
# Camden file: {www.landregistry.gov.uk}INSPIREID
# City file:   {www.landregistry.gov.uk/inspire}inspireid
# Match either by suffix.
_INSPIRE_ID_LOCALNAMES = ("INSPIREID", "inspireid")


def _shoelace(coords: list[tuple[float, float]]) -> float:
    n = len(coords)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = coords[i]
        x2, y2 = coords[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) * 0.5


def _parse_pos_list(text: str) -> list[tuple[float, float]]:
    parts = re.split(r"\s+", text.strip())
    nums = [float(x) for x in parts if x]
    if len(nums) % 2 != 0:
        return []
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]


def _project_ring(ring_27700: list[tuple[float, float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for x, y in ring_27700:
        lng, lat = _TF.transform(x, y)
        out.append([lng, lat])
    return out


def _ring_centroid(ring: list[list[float]]) -> tuple[float, float]:
    if not ring:
        return (0.0, 0.0)
    sx = sum(p[0] for p in ring) / len(ring)
    sy = sum(p[1] for p in ring) / len(ring)
    return (sx, sy)


def _find_inspire_id_on_ancestor(elem) -> str | None:
    """Walk up the parent chain looking for an INSPIREID/inspireid child element
    or, failing that, a gml:id attribute.

    Camden file: <LR:INSPIREID>44079687</LR:INSPIREID>
    City file:   <inspire:inspireid>150539</inspire:inspireid>
    """
    anc = elem.getparent()
    while anc is not None:
        # Look for any direct child with localname INSPIREID or inspireid.
        for child in anc:
            try:
                # lxml localname extraction
                local = etree.QName(child).localname
            except ValueError:
                continue
            if local in _INSPIRE_ID_LOCALNAMES and child.text:
                return child.text.strip()
        # gml:id attr fallback.
        for k, v in anc.attrib.items():
            if k.endswith("}id") or k == "id":
                return v
        anc = anc.getparent()
    return None


def _iter_polygons(gml_path: str) -> Iterator[tuple[str | None, list[tuple[float, float]]]]:
    """Yield (inspire_id_or_None, ring_27700) per Polygon, memory-safe.

    Works for both Camden (LR:PREDEFINED features) and City (inspire:LU.ResidentialUse).
    """
    context = etree.iterparse(
        gml_path, events=("end",), tag=tuple(POLYGON_TAGS), huge_tree=True,
    )
    for _, elem in context:
        inspire_id = _find_inspire_id_on_ancestor(elem)

        pos_list_text = None
        for desc in elem.iter():
            if desc.tag in POS_LIST_TAGS:
                pos_list_text = desc.text
                break
        if pos_list_text:
            ring = _parse_pos_list(pos_list_text)
            if ring:
                yield inspire_id, ring

        elem.clear(keep_tail=True)
        prev = elem.getprevious()
        while prev is not None:
            parent = elem.getparent()
            if parent is None:
                break
            del parent[0]
            prev = elem.getprevious()


def _sample_one_gml(
    gml_path: str,
    want: int,
    rng: random.Random,
    source_label: str,
    area_min: float,
    area_max: float,
) -> list[dict]:
    print(f"[ingest_real_demo] streaming {gml_path} (target sample={want}, source={source_label})")
    reservoir: list[dict] = []
    seen = 0
    kept = 0
    for inspire_id, ring_27700 in _iter_polygons(gml_path):
        seen += 1
        area = _shoelace(ring_27700)
        if not (area_min <= area <= area_max):
            continue
        ring_4326 = _project_ring(ring_27700)
        if len(ring_4326) < 4:
            continue
        if ring_4326[0] != ring_4326[-1]:
            ring_4326.append(ring_4326[0])
        cx, cy = _ring_centroid(ring_4326)
        rec = {
            "inspire_id": inspire_id or f"{source_label}_{uuid.uuid4().hex[:12]}",
            "ring_4326": ring_4326,
            "area_m2_approx": round(area, 2),
            "centroid_lng": cx,
            "centroid_lat": cy,
            "source_label": source_label,
        }
        kept += 1
        # Reservoir sampling (Algorithm R) — uniform without knowing total upfront.
        if len(reservoir) < want:
            reservoir.append(rec)
        else:
            j = rng.randint(0, kept - 1)
            if j < want:
                reservoir[j] = rec
    print(
        f"[ingest_real_demo] {source_label}: read={seen} in_area_band={kept} sampled={len(reservoir)}"
    )
    return reservoir


def sample_polygons(
    sources: list[tuple[str, str, int]],
    rng: random.Random,
    area_min: float = 400.0,
    area_max: float = 5000.0,
) -> list[dict]:
    """Sample polygons from multiple GML sources.

    sources: list of (path, source_label, want_count).
    """
    out: list[dict] = []
    for path, label, want in sources:
        if want <= 0 or not os.path.exists(path):
            if not os.path.exists(path):
                print(f"WARN: skipping missing GML {path}", file=sys.stderr)
            continue
        out.extend(_sample_one_gml(path, want, rng, label, area_min, area_max))
    rng.shuffle(out)
    return out


# --- CCOD streaming ---
def stream_ccod_central_london(zip_path: str, want: int, rng: random.Random) -> list[dict]:
    """Stream the CCOD CSV, reservoir-sample `want` rows whose Postcode matches
    central-London prefixes (EC, WC, SW1, W1, E1, SE1, N1).
    """
    if not os.path.exists(zip_path):
        raise FileNotFoundError(f"CCOD zip not found: {zip_path}")
    print(f"[ingest_real_demo] streaming CCOD {zip_path} (target sample={want})")

    reservoir: list[dict] = []
    matched = 0
    scanned = 0
    with zipfile.ZipFile(zip_path) as zf:
        members = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not members:
            raise RuntimeError(f"No .csv in {zip_path}")
        with zf.open(members[0], "r") as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
            reader = csv.DictReader(text)
            for row in reader:
                scanned += 1
                pc = (row.get("Postcode") or "").strip().upper()
                if not pc or not _CCOD_POSTCODE_RE.match(pc):
                    continue
                name = (row.get("Proprietor Name (1)") or "").strip()
                if not name:
                    continue
                title_no = (row.get("Title Number") or "").strip()
                ch_no = (row.get("Company Registration No. (1)") or "").strip() or None
                reg_addr = (row.get("Proprietor (1) Address (1)") or "").strip() or None
                prop_addr = (row.get("Property Address") or "").strip()
                rec = {
                    "title_number": title_no or None,
                    "name": name,
                    "ch_number": ch_no,
                    "registered_address": reg_addr,
                    "property_address": prop_addr,
                    "postcode": pc,
                }
                matched += 1
                if len(reservoir) < want:
                    reservoir.append(rec)
                else:
                    j = rng.randint(0, matched - 1)
                    if j < want:
                        reservoir[j] = rec

    print(
        f"[ingest_real_demo] CCOD: scanned={scanned} central_london_matches={matched} sampled={len(reservoir)}"
    )
    return reservoir


# --- Postcode snap ---
def snap_to_postcode(lng: float, lat: float) -> tuple[str, str]:
    """Return (postcode, borough) for the nearest anchor."""
    # Squared Euclidean is fine at ~50km scale.
    best = min(
        POSTCODE_ANCHORS,
        key=lambda a: (a[1] - lng) ** 2 + (a[2] - lat) ** 2,
    )
    return (best[0], best[3])


# --- Scoring ---
def sample_composite_score(rng: random.Random) -> int:
    """Clamped Normal(70, 12) -> int in [40, 95]."""
    raw = rng.gauss(70.0, 12.0)
    return int(round(max(40.0, min(95.0, raw))))


def derive_subscores(rng: random.Random, composite: int, premises_type: str) -> tuple[float, float, float]:
    """Back-derive sub-scores so the schema's solar/fin/social fields are
    plausible AND `composite_score(s, f, ss)` is close to the target composite.

    Weights: solar 0.5, fin 0.3, social 0.2 (from constants).
    Pick solar_roi & fin_health from premises bias + small noise; solve social.
    """
    bias = {
        "warehouse": (0.85, 0.65),
        "retail": (0.75, 0.70),
        "office": (0.78, 0.80),
        "leisure": (0.72, 0.65),
        "education": (0.68, 0.55),
        "residential": (0.70, 0.60),
        "mixed": (0.74, 0.68),
    }.get(premises_type, (0.75, 0.70))
    solar = max(0.0, min(1.0, bias[0] + rng.gauss(0.0, 0.04)))
    fin = max(0.0, min(1.0, bias[1] + rng.gauss(0.0, 0.04)))
    target = composite / 100.0  # in [0,1]
    # composite_unit = 0.5*solar + 0.3*fin + 0.2*social  -> solve social.
    social = (target - 0.5 * solar - 0.3 * fin) / 0.2
    social = max(0.0, min(1.0, social))
    return solar, fin, social


# --- Lead doc construction ---
def build_lead_and_company(
    rng: random.Random,
    polygon: dict,
    owner: dict,
    client_id: str,
) -> tuple[dict, dict]:
    cx = polygon["centroid_lng"]
    cy = polygon["centroid_lat"]
    area_m2 = polygon["area_m2_approx"]

    postcode, borough = snap_to_postcode(cx, cy)
    # City source = LU_Residential -> bias to residential/mixed; Camden = mixed.
    if polygon.get("source_label") == "city":
        premises_type = rng.choices(
            ["residential", "mixed", "office"], weights=[0.65, 0.25, 0.10],
        )[0]
    else:
        premises_type = _premises_type_for_area(rng, area_m2)

    composite = sample_composite_score(rng)
    solar_roi, fin_health, social_impact = derive_subscores(rng, composite, premises_type)

    # Panel count: scale from rooftop area, but cap to keep capex in £80-300k.
    # capex(p) ~ £962/panel -> 80k=83 panels, 300k=312 panels. Cap to [80, 300].
    raw_panel_count = max(80, int(area_m2 * 0.5 / 1.7))
    panel_count = min(300, raw_panel_count)

    # Per-panel annual kWh varies with orientation/shading: 320-430 kWh/yr.
    yield_per_panel = rng.uniform(320.0, 430.0)
    annual_kwh = panel_count * yield_per_panel

    # Site install premium: tricky access / scaffolding / glass roof etc.
    # Multiplier 1.0..1.35 on top of base capex.
    install_premium = rng.uniform(1.0, 1.35)
    cap = capex(panel_count) * install_premium

    asg = annual_saving_gbp(annual_kwh)
    pyrs = payback_years(cap, asg)
    npv = npv_25yr(cap, asg)

    now = datetime.now(timezone.utc).isoformat()

    # Stable lead _id from polygon inspire_id + owner title_number — fully
    # reproducible across runs (idempotent under same SEED + same data).
    seed_str = f"{polygon['inspire_id']}|{owner.get('title_number') or owner['name']}"
    lead_hash = hashlib.sha1(seed_str.encode("utf-8")).hexdigest()[:24]
    lead_id = f"lead_real_{lead_hash}"

    # Stable company _id by title_number when present, else by name slug.
    co_seed = owner.get("title_number") or owner["name"]
    co_hash = hashlib.sha1(co_seed.encode("utf-8")).hexdigest()[:20]
    company_id = f"company_real_{co_hash}"

    # Address: use the CCOD property address if it looks like a real address;
    # otherwise synthesise from polygon centroid + chosen postcode.
    addr_src = (owner.get("property_address") or "").strip()
    address = addr_src if addr_src else f"Property near {postcode}"

    nice_name = owner["name"].title() if owner["name"].isupper() else owner["name"]

    lead: dict = {
        "_id": lead_id,
        "client_id": client_id,
        "address": address,
        "postcode": postcode,
        "borough": borough,
        "premises_type": premises_type,
        "geo": {"point": {"type": "Point", "coordinates": [cx, cy]}},
        "rooftop_polygon": {
            "type": "Polygon",
            "coordinates": [polygon["ring_4326"]],
            "source": "inspire_index_polygon",
            "inspire_id": polygon["inspire_id"],
            "area_m2_approx": area_m2,
        },
        "scores": {
            "solar_roi": round(solar_roi, 4),
            "financial_health": round(fin_health, 4),
            "social_impact": round(social_impact, 4),
            "composite_score": composite,
            "scored_at": now,
        },
        "owner": {
            "company_id": company_id,
            "company_name": nice_name,
            "source": "ccod",
            "match_method": "round_robin",  # extension field — schema allows additionalProperties
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

    company: dict = {
        "_id": company_id,
        "name": nice_name,
        "ccod_proprietor_name": owner["name"],
        "ch_number": owner.get("ch_number"),
        "title_number": owner.get("title_number"),
        "registered_address": owner.get("registered_address"),
        "property_address": owner.get("property_address"),
        "directors": [],
        "embedding": None,
    }
    return lead, company


# --- Mongo plumbing ---
def get_db():
    uri = os.environ.get("MONGO_URI")
    if not uri:
        print("ERROR: MONGO_URI env var is required.", file=sys.stderr)
        sys.exit(1)
    if "authSource=" not in uri and "mongodb+srv://" not in uri:
        print("WARN: MONGO_URI lacks authSource=admin (cardinal rule 6).", file=sys.stderr)
    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=10000)
        client.admin.command("ping")
    except pymongo_errors.PyMongoError as e:
        print(f"ERROR: cannot reach Mongo: {e}", file=sys.stderr)
        sys.exit(1)
    try:
        db = client.get_default_database()
    except Exception:
        db = None
    if db is None:
        db = client["solarreach"]
    return db


def ensure_client(db, client_id: str) -> None:
    db["clients"].update_one(
        {"_id": client_id},
        {
            "$setOnInsert": {
                "_id": client_id,
                "name": "GreenSolar UK",
                "branding": {"primary": "#0F172A", "logo_url": "https://example.invalid/logo.svg"},
                "pricing": {"panel_unit_gbp": 850.0, "install_per_kw_gbp": 180.0},
                "session_budget_gbp": 1.00,
            }
        },
        upsert=True,
    )


def reset_real(db) -> None:
    """Drop ONLY docs whose _id starts with `lead_real_` / `company_real_`."""
    r1 = db["leads"].delete_many({"_id": {"$regex": "^lead_real_"}})
    r2 = db["companies"].delete_many({"_id": {"$regex": "^company_real_"}})
    print(
        f"[ingest_real_demo] --reset-real-leads: removed leads={r1.deleted_count} "
        f"companies={r2.deleted_count}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("--count", type=int, default=300)
    parser.add_argument("--gml-camden", default=DEFAULT_GML_CAMDEN)
    parser.add_argument("--gml-city", default=DEFAULT_GML_CITY)
    parser.add_argument(
        "--city-share",
        type=float,
        default=0.35,
        help="Fraction of `count` to draw from City of London (rest from Camden).",
    )
    parser.add_argument("--ccod-zip", default=DEFAULT_CCOD_ZIP)
    parser.add_argument("--client-id", default=CLIENT_ID_DEFAULT)
    parser.add_argument("--owner-sample", type=int, default=50)
    parser.add_argument("--reset-real-leads", action="store_true",
                        help="Drop ONLY lead_real_*/company_real_* docs first.")
    args = parser.parse_args()

    if not os.path.exists(args.ccod_zip):
        print(f"ERROR: CCOD zip not found: {args.ccod_zip}", file=sys.stderr)
        return 1

    db = get_db()

    if args.reset_real_leads:
        reset_real(db)

    ensure_client(db, args.client_id)

    rng = random.Random(SEED)

    # 1) Sample real polygons from both Camden + City sources.
    city_n = int(round(args.count * args.city_share))
    camden_n = args.count - city_n
    polygons = sample_polygons(
        sources=[
            (args.gml_camden, "camden", camden_n),
            (args.gml_city, "city", city_n),
        ],
        rng=rng,
    )
    if len(polygons) < args.count:
        print(
            f"WARN: only {len(polygons)} polygons matched area filter "
            f"(wanted {args.count}). Will produce that many leads.",
            file=sys.stderr,
        )

    # 2) Sample real CCOD owners.
    owners = stream_ccod_central_london(args.ccod_zip, want=args.owner_sample, rng=rng)
    if not owners:
        print("ERROR: no CCOD owners matched central-London filter.", file=sys.stderr)
        return 1

    # Shuffle once for deterministic round-robin.
    rng.shuffle(owners)

    # 3) Build docs.
    leads: list[dict] = []
    companies: dict[str, dict] = {}  # dedupe by _id
    for i, poly in enumerate(polygons):
        owner = owners[i % len(owners)]
        lead, co = build_lead_and_company(rng, poly, owner, args.client_id)
        leads.append(lead)
        companies[co["_id"]] = co  # last write wins; same id = same content

    # 4) Bulk upsert: companies first (FK target), then leads.
    co_ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in companies.values()]
    if co_ops:
        co_res = db["companies"].bulk_write(co_ops, ordered=False)
        print(
            f"[ingest_real_demo] companies upserted={co_res.upserted_count} "
            f"matched={co_res.matched_count} modified={co_res.modified_count}"
        )

    lead_ops = [ReplaceOne({"_id": d["_id"]}, d, upsert=True) for d in leads]
    BATCH = 500
    upserted = matched = modified = 0
    for i in range(0, len(lead_ops), BATCH):
        chunk = lead_ops[i : i + BATCH]
        res = db["leads"].bulk_write(chunk, ordered=False)
        upserted += res.upserted_count
        matched += res.matched_count
        modified += res.modified_count
    print(
        f"[ingest_real_demo] leads upserted={upserted} matched={matched} "
        f"modified={modified}"
    )

    # 5) Verify.
    n_real = db["leads"].count_documents({"_id": {"$regex": "^lead_real_"}})
    total_leads = db["leads"].count_documents({})
    n_inspire_polys = db["leads"].count_documents(
        {"_id": {"$regex": "^lead_real_"}, "rooftop_polygon.source": "inspire_index_polygon"}
    )
    n_ccod_owners = db["leads"].count_documents(
        {"_id": {"$regex": "^lead_real_"}, "owner.source": "ccod"}
    )
    sample = db["leads"].find_one(
        {"_id": {"$regex": "^lead_real_"}},
        projection={
            "_id": 1, "postcode": 1, "rooftop_polygon.source": 1, "rooftop_polygon.inspire_id": 1,
            "owner.source": 1, "owner.company_name": 1, "scores.composite_score": 1,
            "financial.capex_gbp": 1, "financial.payback_years": 1,
        },
    )
    print(f"[ingest_real_demo] DONE")
    print(f"  total leads in db ............ {total_leads}")
    print(f"  lead_real_* leads ............ {n_real}")
    print(f"  ... with inspire polygons .... {n_inspire_polys}")
    print(f"  ... with ccod owners ......... {n_ccod_owners}")
    print(f"  sample lead .................. {sample}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
