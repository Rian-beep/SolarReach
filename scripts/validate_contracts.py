#!/usr/bin/env python3
"""Diff endpoints declared in docs/CONTRACTS.md § 2 against FastAPI routes registered in
packages/api/app. Fails (exit 1) on drift so CI catches contract violations early.

Owned by A5. Run as part of `make validate-contracts` and CI smoke.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "docs" / "CONTRACTS.md"
API_APP = ROOT / "packages" / "api" / "app"

# --- parse CONTRACTS.md -----------------------------------------------------

ENDPOINT_RE = re.compile(
    r"^###\s+`(GET|POST|PUT|PATCH|DELETE)\s+([^`]+)`",
    re.MULTILINE,
)


def parse_contracts() -> set[tuple[str, str]]:
    if not CONTRACTS.exists():
        print(f"::error::missing {CONTRACTS}", file=sys.stderr)
        sys.exit(1)
    text = CONTRACTS.read_text(encoding="utf-8")
    # Restrict to "## 2. REST API Endpoints" through next "## "
    m = re.search(r"## 2\. REST API Endpoints.*?(?=\n## \d)", text, re.DOTALL)
    if not m:
        print("::warning::§2 not found in CONTRACTS.md", file=sys.stderr)
        section = text
    else:
        section = m.group(0)
    return {(method, _normalize(path)) for method, path in ENDPOINT_RE.findall(section)}


# --- parse FastAPI routes ---------------------------------------------------

ROUTE_DECL_RE = re.compile(
    r"@(?:app|router)\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]+)['\"]",
    re.IGNORECASE,
)


def parse_fastapi_routes() -> set[tuple[str, str]]:
    if not API_APP.exists():
        print(f"::warning::api app dir not found at {API_APP}; skipping", file=sys.stderr)
        return set()
    routes: set[tuple[str, str]] = set()
    for py in API_APP.rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        # Pull prefix from APIRouter(prefix="...")
        prefix_match = re.search(r"APIRouter\([^)]*prefix\s*=\s*['\"]([^'\"]+)['\"]", text)
        prefix = prefix_match.group(1) if prefix_match else ""
        for method, path in ROUTE_DECL_RE.findall(text):
            full = (prefix + path) or "/"
            routes.add((method.upper(), _normalize(full)))
    return routes


# --- normalization ----------------------------------------------------------

PARAM_RE = re.compile(r"<[^>]+>|\{[^}]+\}")


def _normalize(p: str) -> str:
    """Collapse path params: `/lead/<id>` and `/lead/{id}` → `/lead/:id`. Trim trailing /."""
    p = p.strip().split("?", 1)[0]
    p = PARAM_RE.sub(":param", p)
    if p.endswith("/") and len(p) > 1:
        p = p[:-1]
    return p


# --- main -------------------------------------------------------------------


def main() -> int:
    declared = parse_contracts()
    actual = parse_fastapi_routes()

    missing = declared - actual
    extra = actual - declared

    print(f"contracts declared : {len(declared)}")
    print(f"fastapi routes     : {len(actual)}")

    ok = True
    if missing:
        ok = False
        print("\n::error::endpoints declared in CONTRACTS.md but NOT implemented in FastAPI:")
        for method, path in sorted(missing):
            print(f"  - {method:6} {path}")

    if extra:
        # Extras are warnings, not errors — internal routes (admin, openapi) are fine.
        # Filter known internals.
        meaningful = {
            (m, p)
            for (m, p) in extra
            if not p.startswith(
                ("/openapi", "/docs", "/redoc", "/admin/demo-reset", "/static")
            )
        }
        if meaningful:
            print("\n::warning::FastAPI routes not declared in CONTRACTS.md:")
            for method, path in sorted(meaningful):
                print(f"  + {method:6} {path}")

    if ok:
        print("\n✓ contracts match")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
