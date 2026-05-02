"""LangChain `@tool` wrappers exposed to the CrewAI agents."""
from __future__ import annotations

from .atlas import atlas_query, atlas_vector_search
from .elevenlabs_tts import elevenlabs_tts
from .pptx import build_pptx
from .serpapi import serpapi_search

__all__ = [
    "atlas_query",
    "atlas_vector_search",
    "build_pptx",
    "elevenlabs_tts",
    "serpapi_search",
]
