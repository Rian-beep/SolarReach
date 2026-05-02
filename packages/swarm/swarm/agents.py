"""CrewAI agent definitions.

Manager (Opus 4.7) plans + delegates. Three specialists run on Haiku 4.5
in parallel via async_execution=True on their tasks.

Theme alignment (docs/THEME-NARRATIVE.md):
- Manager mirrors the Opus-driven decision-maker inferer pattern.
- Specialists discover peers via Mongo collection writes — same pattern as
  the broader pipeline; CrewAI's hierarchical process gives us the
  delegation primitive without us having to roll our own queue.
"""
from __future__ import annotations

import os
from functools import lru_cache

from crewai import Agent
from langchain_anthropic import ChatAnthropic

from . import MANAGER_MODEL, WORKER_MODEL
from .tools import (
    atlas_query,
    atlas_vector_search,
    build_pptx,
    elevenlabs_tts,
    serpapi_search,
)


# ---------- LLM factories ---------- #

@lru_cache(maxsize=1)
def manager_llm() -> ChatAnthropic:
    """Opus 4.7 — strategic planning + delegation. Cached system prompt added
    by CrewAI; we keep temp moderate to leave room for the delegation
    reasoning to vary."""
    return ChatAnthropic(
        model=MANAGER_MODEL,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        temperature=0.4,
        max_tokens=4096,
    )


@lru_cache(maxsize=1)
def worker_llm() -> ChatAnthropic:
    """Haiku 4.5 — fast, cheap, parallelisable."""
    return ChatAnthropic(
        model=WORKER_MODEL,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        temperature=0.5,
        max_tokens=4096,
    )


# ---------- System prompts ---------- #

MANAGER_PROMPT = (
    "You are the SolarReach swarm manager. You receive a high-level objective "
    "and delegate to specialised crew members. Use Atlas vector retrieval to "
    "ground decisions in real Land Registry data."
)

GOOGLE_ENGINEER_PROMPT = (
    "You are the GoogleEngineer specialist. Use SerpApi to research approaches "
    "to engineering problems. You are a high-level architect: research first, "
    "then write a brief plan and delegate code-writing back to the manager. "
    "Never produce code yourself — your output is research notes + a plan."
)

PITCH_DECK_PROMPT = (
    "You are the PitchDeckBuilder specialist. Read lead and company context "
    "from Atlas via the vector retrieval tool. When you have enough context, "
    "call build_pptx with a deck spec following the SolarReach 11-slide schema "
    "(title, problem, solution, grid_independence, roi, funding, timeline, "
    "decision_maker_callout, social_impact, tech_specs, cta). Return the "
    "rendered file path."
)

OUTREACH_EDITOR_PROMPT = (
    "You are the OutreachEditor specialist. You read leads from Atlas via "
    "atlas_query and you may write outreach updates back. Every action you "
    "take is audit-logged automatically. Be silent — print only a one-line "
    "summary of what you changed."
)

TTS_PROMPT = (
    "You are the ElevenLabsTTSAgent specialist. Convert text to speech using "
    "elevenlabs_tts and report the resulting mp3 path. If the API key is "
    "missing, report that gracefully — do not retry."
)


# ---------- Agent factories ---------- #

def make_manager() -> Agent:
    return Agent(
        role="Swarm Manager",
        goal=(
            "Decompose the user's objective into specialist sub-tasks and "
            "delegate them. Use Atlas grounding before delegating."
        ),
        backstory=MANAGER_PROMPT,
        llm=manager_llm(),
        allow_delegation=True,
        verbose=True,
        tools=[atlas_vector_search, atlas_query],
    )


def make_google_engineer() -> Agent:
    return Agent(
        role="GoogleEngineer",
        goal=(
            "Research engineering approaches via SerpApi, then produce a "
            "concise plan and hand back to the manager."
        ),
        backstory=GOOGLE_ENGINEER_PROMPT,
        llm=worker_llm(),
        allow_delegation=True,
        verbose=False,
        tools=[serpapi_search, atlas_vector_search],
    )


def make_pitch_deck_builder() -> Agent:
    return Agent(
        role="PitchDeckBuilder",
        goal=(
            "Generate a .pptx deck for a target lead, grounded in Atlas data."
        ),
        backstory=PITCH_DECK_PROMPT,
        llm=worker_llm(),
        allow_delegation=False,
        verbose=False,
        tools=[atlas_vector_search, atlas_query, build_pptx],
    )


def make_outreach_editor() -> Agent:
    return Agent(
        role="OutreachEditor",
        goal=(
            "Read and (when instructed) update leads in Atlas, with every "
            "action audit-logged. Output a one-line summary."
        ),
        backstory=OUTREACH_EDITOR_PROMPT,
        llm=worker_llm(),
        allow_delegation=False,
        verbose=False,
        tools=[atlas_query, atlas_vector_search],
    )


def make_tts_agent() -> Agent:
    return Agent(
        role="ElevenLabsTTSAgent",
        goal="Convert text to mp3 via ElevenLabs and report the path.",
        backstory=TTS_PROMPT,
        llm=worker_llm(),
        allow_delegation=False,
        verbose=False,
        tools=[elevenlabs_tts],
    )
