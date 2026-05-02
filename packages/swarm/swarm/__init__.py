"""SolarReach swarm — hierarchical CrewAI orchestration.

Manager: Anthropic Claude Opus 4.7 (strategic planning + delegation).
Specialists: Anthropic Claude Haiku 4.5 (concurrent execution).

Specialists:
- GoogleEngineer    — SerpApi research + delegation
- PitchDeckBuilder  — python-pptx via Atlas vector retrieval
- OutreachEditor    — Atlas read/write + audit_log
- ElevenLabsTTSAgent — ElevenLabs TTS to /tmp/swarm-tts/

All paid tool calls are logged to `audit_log` (CONTRACTS § 1).
Tools no-op gracefully when their API key is absent.
"""
from __future__ import annotations

__version__ = "0.1.0"

MANAGER_MODEL = "claude-opus-4-7"
WORKER_MODEL = "claude-haiku-4-5-20251001"

__all__ = ["MANAGER_MODEL", "WORKER_MODEL"]
