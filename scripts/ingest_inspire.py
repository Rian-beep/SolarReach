#!/usr/bin/env python3
"""ingest_inspire.py — streaming ingest of INSPIRE Land Registry GML.

Parses the Camden + City of London cadastral / residential GML files using
`lxml.iterparse`, reprojects EPSG:27700 -> EPSG:4326 with `pyproj`, computes
approx polygon area in m^2 (in original CRS), filters to [80, 5000] m^2,
and inserts into `inspire_polygons`.

Cardinal:
- NEVER store EPSG:27700 in 2dsphere indexes — convert to 4326 first.
- Free elements with `.clear()` and parent-del to stay memory-safe.
- Idempotent: upsert by `inspire_id`.

Usage:
    MONGO_URI="..." python scripts/ingest_inspire.py [--limit 5000] [--source camden|city|both]
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from typing import Iterator

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


# Default paths (relative to repo root).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATHS = {
    "camden": os.path.join(
        _REPO_ROOT, "data", "raw", "inspire-camden", "Land_Registry_Cadastral_Parcels.gml"
    ),
    "city": os.path.join(
        _REPO_ROOT, "data", "raw", "inspire-city", "Land_Registry_LU_Residential.gml"
    ),
}

BOROUGH_LABELS = {
    "camden": "London Borough of Camden",
    "city": "City of London Corporation",
}

# Transformer is cheap to create but reused.
_TF = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)

GML_NS = "http://www.opengis.net/gml/3.2"
GML_NS_V31 = "http://www.opengis.net/gml"

POS_LIST_TAGS = {
    f"{{{GML_NS}}}posList",
    f"{{{GML_NS_V31}}}posList",
}

# Top-level features may use different tag names per dataset; we match anything
# that contains a posList descendant. We scan generic Polygon elements.
POLYGON_TAGS = {
    f"{{{GML_NS}}}Polygon",
    f"{{{GML_NS_V31}}}Polygon",
}


def _shoelace_area(coords: list[tuple[float, float]]) -> float:
    """Polygon area via shoelace, in input CRS units."""
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
    """Parse `posList` text — sequence of x y x y ... in EPSG:27700."""
    parts = re.split(r"\s+", text.strip())
    nums = [float(x) for x in parts if x]
    if len(nums) % 2 != 0:
        return []
    return [(nums[i], nums[i + 1]) for i in range(0, len(nums), 2)]


def _project_ring(ring_27700: list[tuple[float, float]]) -> list[list[float]]:
    """Reproject a ring to EPSG:4326 [lng, lat]."""
    out: list[list[float]] = []
    for x, y in ring_27700:
        lng, lat = _TF.transform(x, y)
        out.append([lng, lat])
    return out


def _ring_centroid_4326(ring: list[list[float]]) -> tuple[float, float]:
    if not ring:
        return (0.0, 0.0)
    sx = sum(p[0] for p in ring) / len(ring)
    sy = sum(p[1] for p in ring) / len(ring)
    return (sx, sy)


def _iter_polygons(gml_path: str) -> Iterator[tuple[str | None, list[tuple[float, float]]]]:
    """Yield (inspire_id_or_None, ring_27700) for each Polygon in the GML.

    Memory-safe via element clear + parent-del.
    """
    # Iterate over Polygon end events; we'll grab the first posList descendant.
    context = etree.iterparse(
        gml_path,
        events=("end",),
        tag=tuple(POLYGON_TAGS),
        huge_tree=True,
    )

    for _, elem in context:
        # Try to find an INSPIRE id from the closest ancestor with gml:id.
        # Walk up looking for any gml:id attr.
        inspire_id = None
        anc = elem
        while anc is not None:
            for k, v in anc.attrib.items():
                if k.endswith("}id") or k == "id":
                    inspire_id = v
                    break
            if inspire_id is not None:
                break
            anc = anc.getparent()

        # First posList in the polygon is the outer ring.
        pos_list_text = None
        for desc in elem.iter():
            if desc.tag in POS_LIST_TAGS:
                pos_list_text = desc.text
                break

        if pos_list_text:
            ring = _parse_pos_list(pos_list_text)
            if ring:
                yield inspire_id, ring

        # Free this polygon and its parent siblings.
        elem.clear(keep_tail=True)
        # Drop preceding siblings to keep memory bounded (lxml fast-iter pattern).
        prev = elem.getprevious()
        while prev is not None:
            parent = elem.getparent()
            if parent is None:
                break
            del parent[0]
            prev = elem.getprevious()


def ingest_file(
    db,
    gml_path: str,
    borough: str,
    limit: int,
) -> tuple[int, int]:
    """Returns (read, inserted)."""
    if not os.path.exists(gml_path):
        print(f"WARN: missing GML file {gml_path} — skipping {borough}", file=sys.stderr)
        return 0, 0

    print(f"[ingest_inspire] streaming {gml_path}")
    coll = db["inspire_polygons"]
    batch: list[ReplaceOne] = []
    BATCH_SIZE = 500

    read = 0
    inserted = 0
    for inspire_id, ring_27700 in _iter_polygons(gml_path):
        read += 1
        if read >= limit:
            break

        if not inspire_id:
            inspire_id = f"synthetic_{uuid.uuid4().hex[:12]}"

        area = _shoelace_area(ring_27700)
        if not (80.0 <= area <= 5000.0):
            continue

        ring_4326 = _project_ring(ring_27700)
        if len(ring_4326) < 4:
            continue
        # Ensure ring closure for GeoJSON.
        if ring_4326[0] != ring_4326[-1]:
            ring_4326.append(ring_4326[0])

        cx, cy = _ring_centroid_4326(ring_4326)
        doc = {
            "_id": f"inspire_{uuid.uuid4().hex[:16]}",
            "inspire_id": inspire_id,
            "borough": borough,
            "polygon": {
                "type": "Polygon",
                "coordinates": [ring_4326],
            },
            "area_m2_approx": round(area, 2),
            "centroid": {"type": "Point", "coordinates": [cx, cy]},
        }
        batch.append(
            ReplaceOne({"inspire_id": inspire_id}, doc, upsert=True)
        )

        if len(batch) >= BATCH_SIZE:
            try:
                res = coll.bulk_write(batch, ordered=False)
                inserted += res.upserted_count + res.modified_count
            except pymongo_errors.BulkWriteError as e:
                print(f"WARN: partial bulk write: {e.details.get('writeErrors', [])[:3]}", file=sys.stderr)
            batch.clear()
            if read % 5000 == 0:
                print(f"[ingest_inspire] {borough}: read={read} inserted~={inserted}")

    if batch:
        try:
            res = coll.bulk_write(batch, ordered=False)
            inserted += res.upserted_count + res.modified_count
        except pymongo_errors.BulkWriteError as e:
            print(f"WARN: partial bulk write: {e.details.get('writeErrors', [])[:3]}", file=sys.stderr)

    print(f"[ingest_inspire] {borough}: total read={read} inserted~={inserted}")
    return read, inserted


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5000)
    parser.add_argument("--source", choices=["camden", "city", "both"], default="both")
    parser.add_argument("--camden-path", default=DEFAULT_PATHS["camden"])
    parser.add_argument("--city-path", default=DEFAULT_PATHS["city"])
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

    sources: list[tuple[str, str]] = []
    if args.source in ("camden", "both"):
        sources.append((args.camden_path, BOROUGH_LABELS["camden"]))
    if args.source in ("city", "both"):
        sources.append((args.city_path, BOROUGH_LABELS["city"]))

    grand_read = 0
    grand_inserted = 0
    for path, borough in sources:
        r, i = ingest_file(db, path, borough, args.limit)
        grand_read += r
        grand_inserted += i

    print(f"[ingest_inspire] DONE read={grand_read} inserted~={grand_inserted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
