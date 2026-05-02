"""Crew structure tests — mocked tools, no live LLM calls.

We don't kickoff() the crew (that would hit Anthropic). We assert the
declarative shape: agents present, tools attached to the right roles,
hierarchical process selected, async tasks marked async.
"""
from __future__ import annotations

import os

import pytest

# Ensure the API key check inside ChatAnthropic doesn't error during module
# import — agents.py instantiates the LLM at module-load time via lru_cache.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-used")


def test_crew_has_manager_and_three_specialists():
    from crewai import Process

    from swarm.crew import build_crew

    crew = build_crew(objective="Generate pitch for top-3 EC2M leads")
    # 4 specialists registered; manager is implicit via manager_llm.
    roles = {a.role for a in crew.agents}
    assert {"GoogleEngineer", "PitchDeckBuilder", "OutreachEditor", "ElevenLabsTTSAgent"}.issubset(roles)
    assert crew.process == Process.hierarchical
    assert crew.manager_llm is not None


def test_async_tasks_marked_async():
    from swarm.crew import build_crew

    crew = build_crew(objective="ping", target_lead_id="lead_xyz")
    # First task is the manager's umbrella task (sync); the other three are async.
    assert crew.tasks[0].async_execution is False
    assert all(t.async_execution for t in crew.tasks[1:])


def test_pitch_builder_has_pptx_and_atlas_tools():
    from swarm.agents import make_pitch_deck_builder

    agent = make_pitch_deck_builder()
    tool_names = {getattr(t, "name", t.__class__.__name__) for t in agent.tools}
    # langchain @tool sets .name from the function name
    assert "build_pptx" in tool_names
    assert "atlas_vector_search" in tool_names
    assert "atlas_query" in tool_names


def test_atlas_vector_search_returns_dict_when_mongo_unset(monkeypatch):
    monkeypatch.delenv("MONGO_URI", raising=False)
    # Bust the lru_cache so unset MONGO_URI is re-read.
    from swarm import mongo as mongo_mod

    mongo_mod.get_sync_client.cache_clear()

    from swarm.tools.atlas import atlas_vector_search

    result = atlas_vector_search.invoke({"query": "solar farm", "collection": "companies", "k": 3})
    assert isinstance(result, dict)
    assert result["ok"] is False
    assert result["data"] == []
    assert "MONGO_URI" in (result.get("error") or "")
