"""Prompt files loaded from disk at module import time."""

from pathlib import Path

_HERE = Path(__file__).parent


def load_prompt(name: str) -> str:
    p = _HERE / name
    if not p.exists():
        raise FileNotFoundError(f"Prompt missing: {p}")
    return p.read_text(encoding="utf-8")
