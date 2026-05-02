"""Mongo client helpers for swarm tools.

LangChain `@tool` callables are sync, so we use pymongo (sync) here. The API
router uses Motor (async) directly — these helpers are tool-side only.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

from pymongo import MongoClient
from pymongo.database import Database

log = logging.getLogger("solarreach.swarm.mongo")


@lru_cache(maxsize=1)
def get_sync_client() -> MongoClient | None:
    """Return a sync pymongo client, or None if MONGO_URI is unset."""
    uri = os.getenv("MONGO_URI", "")
    if not uri:
        log.warning("MONGO_URI unset — Atlas tools will return empty results")
        return None
    try:
        return MongoClient(uri, serverSelectionTimeoutMS=2000)
    except Exception as e:  # noqa: BLE001
        log.warning("pymongo init failed: %s", type(e).__name__)
        return None


def get_sync_db() -> Database | None:
    client = get_sync_client()
    if client is None:
        return None
    return client[os.getenv("MONGO_DB", "solarreach")]
