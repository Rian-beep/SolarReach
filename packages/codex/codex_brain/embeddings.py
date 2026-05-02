"""Voyage AI embeddings — voyage-3 model, 1024-dim cosine.

Used for `companies.embedding` and `calls_ts.embedding` (per CONTRACTS.md § 1).
"""

from __future__ import annotations

import os
from typing import Iterable

try:
    import voyageai
except ImportError:  # pragma: no cover
    voyageai = None  # type: ignore[assignment]


VOYAGE_MODEL = "voyage-3"
EMBED_DIM = 1024


class VoyageClient:
    """Async wrapper. Uses voyageai.AsyncClient when available."""

    def __init__(self, api_key: str | None = None, model: str = VOYAGE_MODEL) -> None:
        self.api_key = api_key or os.environ.get("VOYAGE_API_KEY")
        if not self.api_key:
            raise ValueError("VOYAGE_API_KEY is required")
        if voyageai is None:
            raise RuntimeError("voyageai SDK not installed")
        self.model = model
        self._client = voyageai.AsyncClient(api_key=self.api_key)

    async def embed(self, texts: list[str], input_type: str = "document") -> list[list[float]]:
        if not texts:
            return []
        result = await self._client.embed(texts, model=self.model, input_type=input_type)
        # voyageai returns .embeddings: list[list[float]]
        return list(result.embeddings)


async def embed(texts: list[str]) -> list[list[float]]:
    """Module-level convenience: instantiate from env and embed."""
    client = VoyageClient()
    return await client.embed(texts)
