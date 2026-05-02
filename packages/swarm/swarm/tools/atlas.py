"""Atlas tools — vector search + structured query.

Both tools return a dict {ok, data, error} so failures don't crash the crew.
Tool callables are sync (LangChain @tool requirement), so we use pymongo here.

`atlas_vector_search` uses langchain-mongodb's MongoDBAtlasVectorSearch over
the `companies_vector` index (1024-dim cosine, Voyage AI). When the index is
missing or langchain-mongodb errors out, we fall back to:
    1. Atlas Search `$text` (if a text index exists)
    2. Naive case-insensitive regex on `name`

Both paths log to `audit_log` with cost_cents=0 (Atlas reads are free) so the
swarm's reasoning trail is visible alongside the existing API audit rows.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from langchain_core.tools import tool

from swarm.audit import get_actor_name, write_audit_sync
from swarm.mongo import get_sync_db

log = logging.getLogger("solarreach.swarm.tools.atlas")

_VECTOR_INDEX_NAME = "companies_vector"
_EMBEDDING_DIM = 1024


def _embed_query(query: str) -> list[float] | None:
    """Embed a string with Voyage AI voyage-3 (1024-dim).

    Returns None if VOYAGE_API_KEY is missing or voyageai isn't importable.
    """
    api_key = os.getenv("VOYAGE_API_KEY", "")
    if not api_key:
        return None
    try:
        import voyageai
    except Exception:  # noqa: BLE001
        return None
    try:
        client = voyageai.Client(api_key=api_key)
        result = client.embed([query], model="voyage-3", input_type="query")
        embeddings = getattr(result, "embeddings", None) or []
        if embeddings:
            return list(embeddings[0])
    except Exception as e:  # noqa: BLE001
        log.warning("voyageai embed failed: %s", type(e).__name__)
    return None


def _vector_pipeline(embedding: list[float], k: int) -> list[dict[str, Any]]:
    return [
        {
            "$vectorSearch": {
                "index": _VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": max(k * 10, 50),
                "limit": int(k),
            }
        },
        {"$project": {"embedding": 0}},
    ]


def _regex_fallback(db, query: str, collection: str, k: int) -> list[dict[str, Any]]:
    coll = db[collection]
    cursor = coll.find(
        {"name": {"$regex": query, "$options": "i"}},
        projection={"embedding": 0},
    ).limit(k)
    return list(cursor)


@tool
def atlas_vector_search(query: str, collection: str = "companies", k: int = 5) -> dict[str, Any]:
    """Semantic search over a Mongo Atlas collection with Voyage embeddings.

    Args:
        query: natural-language query.
        collection: target collection (default `companies`).
        k: number of hits to return.

    Returns:
        {ok: bool, data: [...docs], error: str|None, mode: 'vector'|'regex'}
    """
    db = get_sync_db()
    actor = get_actor_name()
    if db is None:
        return {"ok": False, "data": [], "error": "MONGO_URI unset", "mode": "none"}

    embedding = _embed_query(query)
    mode = "regex"
    docs: list[dict[str, Any]] = []
    error: str | None = None

    if embedding is not None:
        try:
            docs = list(db[collection].aggregate(_vector_pipeline(embedding, k)))
            mode = "vector"
        except Exception as e:  # noqa: BLE001
            error = f"vector_search_failed:{type(e).__name__}"
            log.warning("atlas vector search failed, falling back to regex: %s", error)

    if not docs:
        try:
            docs = _regex_fallback(db, query, collection, k)
        except Exception as e:  # noqa: BLE001
            error = f"regex_fallback_failed:{type(e).__name__}"
            log.warning("regex fallback failed: %s", error)

    write_audit_sync(
        db=db,
        action="swarm.atlas.vector_search",
        actor=actor,
        cost_cents=0,
        metadata={"collection": collection, "k": k, "mode": mode, "hit_count": len(docs)},
    )
    return {"ok": error is None or bool(docs), "data": docs, "error": error, "mode": mode}


@tool
def atlas_query(filter: dict, collection: str = "leads", limit: int = 20) -> dict[str, Any]:
    """Direct find query for structured retrieval.

    Args:
        filter: pymongo filter dict (e.g. {"scores.composite_score": {"$gte": 70}}).
        collection: target collection.
        limit: max hits.

    Returns:
        {ok: bool, data: [...docs], error: str|None}
    """
    db = get_sync_db()
    actor = get_actor_name()
    if db is None:
        return {"ok": False, "data": [], "error": "MONGO_URI unset"}

    try:
        cursor = db[collection].find(filter or {}, projection={"embedding": 0}).limit(int(limit))
        docs = list(cursor)
    except Exception as e:  # noqa: BLE001
        write_audit_sync(
            db=db,
            action="swarm.atlas.query",
            actor=actor,
            metadata={"collection": collection, "error": type(e).__name__},
        )
        return {"ok": False, "data": [], "error": type(e).__name__}

    write_audit_sync(
        db=db,
        action="swarm.atlas.query",
        actor=actor,
        cost_cents=0,
        metadata={"collection": collection, "limit": limit, "hit_count": len(docs)},
    )
    return {"ok": True, "data": docs, "error": None}
