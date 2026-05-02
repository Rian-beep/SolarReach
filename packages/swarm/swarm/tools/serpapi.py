"""SerpApi tool — Google search via google-search-results.

No-op when SERPAPI_API_KEY is absent. Cost charged on every successful call
(SerpApi pricing: ~0.5 cents per search, conservative estimate).
"""
from __future__ import annotations

import logging
import os
from typing import Any

from crewai.tools import tool

from swarm.audit import get_actor_name, write_audit_sync
from swarm.mongo import get_sync_db

log = logging.getLogger("solarreach.swarm.tools.serpapi")

# Conservative cost per call. SerpApi sells 5k/$50 plans → ~1¢ each;
# 0.5¢ keeps us safe-side on the spend tracker.
SERPAPI_COST_CENTS = 1


@tool
def serpapi_search(query: str, num: int = 5) -> dict[str, Any]:
    """Run a SerpApi Google search.

    Args:
        query: search query.
        num: max organic results (capped at 10).

    Returns:
        {ok: bool, data: [{title, link, snippet}], error: str|None}
    """
    api_key = os.getenv("SERPAPI_API_KEY", "")
    if not api_key:
        return {"ok": False, "data": [], "error": "SERPAPI_API_KEY missing"}

    try:
        from serpapi import GoogleSearch
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "data": [], "error": f"serpapi_import:{type(e).__name__}"}

    params = {
        "q": query,
        "api_key": api_key,
        "engine": "google",
        "num": int(min(max(num, 1), 10)),
    }
    try:
        results = GoogleSearch(params).get_dict()
    except Exception as e:  # noqa: BLE001
        log.warning("serpapi failed: %s", type(e).__name__)
        return {"ok": False, "data": [], "error": type(e).__name__}

    organic = results.get("organic_results") or []
    trimmed = [
        {
            "title": r.get("title"),
            "link": r.get("link"),
            "snippet": r.get("snippet"),
        }
        for r in organic[: int(num)]
    ]

    write_audit_sync(
        db=get_sync_db(),
        action="swarm.serpapi.search",
        actor=get_actor_name(),
        cost_cents=SERPAPI_COST_CENTS,
        metadata={"q_len": len(query), "hit_count": len(trimmed)},
    )
    return {"ok": True, "data": trimmed, "error": None}
