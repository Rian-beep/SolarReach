"""ElevenLabs TTS tool — sync wrapper around the official SDK.

Saves to /tmp/swarm-tts/<task_id>.mp3 and returns the path. No-op if
ELEVENLABS_API_KEY is absent. Cost is logged at ~3¢/clip (conservative —
ElevenLabs charges per character of output; we estimate per request).
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any

from crewai.tools import tool

from swarm.audit import get_actor_name, write_audit_sync
from swarm.mongo import get_sync_db

log = logging.getLogger("solarreach.swarm.tools.elevenlabs")

DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
TTS_OUT_DIR = Path("/tmp/swarm-tts")
TTS_OUT_DIR.mkdir(parents=True, exist_ok=True)

# Conservative — covers a few sentences. Real cost depends on char count.
TTS_COST_CENTS = 3


@tool
def elevenlabs_tts(text: str, voice_id: str = DEFAULT_VOICE_ID) -> dict[str, Any]:
    """Generate an mp3 with ElevenLabs TTS.

    Args:
        text: the text to speak.
        voice_id: ElevenLabs voice id (default = "Rachel").

    Returns:
        {ok: bool, data: {path, voice_id, bytes}, error: str|None}
    """
    api_key = os.getenv("ELEVENLABS_API_KEY", "")
    if not api_key:
        return {"ok": False, "data": None, "error": "ELEVENLABS_API_KEY missing"}

    try:
        from elevenlabs.client import ElevenLabs
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "data": None, "error": f"elevenlabs_import:{type(e).__name__}"}

    task_id = uuid.uuid4().hex
    out_path = TTS_OUT_DIR / f"{task_id}.mp3"

    try:
        client = ElevenLabs(api_key=api_key)
        # SDK returns an iterator of audio chunks for the v2 client.
        audio = client.text_to_speech.convert(
            voice_id=voice_id,
            optimize_streaming_latency="0",
            output_format="mp3_44100_128",
            text=text,
            model_id="eleven_multilingual_v2",
        )
        with out_path.open("wb") as f:
            for chunk in audio:
                if isinstance(chunk, (bytes, bytearray)):
                    f.write(chunk)
        size = out_path.stat().st_size if out_path.exists() else 0
    except Exception as e:  # noqa: BLE001
        log.warning("elevenlabs tts failed: %s", type(e).__name__)
        return {"ok": False, "data": None, "error": type(e).__name__}

    write_audit_sync(
        db=get_sync_db(),
        action="swarm.elevenlabs.tts",
        actor=get_actor_name(),
        cost_cents=TTS_COST_CENTS,
        metadata={"voice_id": voice_id, "bytes": size, "char_count": len(text)},
    )
    return {
        "ok": True,
        "data": {"path": str(out_path), "voice_id": voice_id, "bytes": size},
        "error": None,
    }
