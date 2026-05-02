"""CLI entrypoint: `python -m swarm.main --objective "..."`.

Loads `.env.local` from the project root if present (without overwriting
already-set env vars). Never prints any keys.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

log = logging.getLogger("solarreach.swarm.cli")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")


def _project_root() -> Path:
    # packages/swarm/swarm/main.py → up 3 levels.
    return Path(__file__).resolve().parents[3]


def _load_dotenv() -> None:
    """Load `.env.local` (or `.env`) without leaking secrets into logs.

    `override=False` would skip vars that the parent shell has set to "" — we
    want those filled. Strategy: read with `dotenv_values`, then `setdefault`
    each entry so genuine real-shell exports still win.
    """
    try:
        from dotenv import dotenv_values
    except Exception:  # noqa: BLE001
        log.info("python-dotenv not installed — skipping .env.local load")
        return
    root = _project_root()
    for candidate in (root / ".env.local", root / ".env"):
        if not candidate.exists():
            continue
        vals = dotenv_values(candidate)
        filled = 0
        for k, v in vals.items():
            if v is None:
                continue
            current = os.environ.get(k, "")
            if not current:  # unset OR empty → take .env value
                os.environ[k] = v
                filled += 1
        log.info("loaded %s vars from %s", filled, candidate.name)


def run(objective: str, target_lead_id: str | None) -> str:
    from .crew import build_crew

    crew = build_crew(objective=objective, target_lead_id=target_lead_id)
    result = crew.kickoff(inputs={"objective": objective, "target_lead_id": target_lead_id or ""})
    return str(result)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SolarReach swarm CLI")
    parser.add_argument("--objective", required=True, help="High-level objective.")
    parser.add_argument(
        "--target-lead-id",
        default=None,
        help="Optional lead_id to focus specialists on.",
    )
    args = parser.parse_args(argv)

    _load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY missing — manager call will fail")

    try:
        out = run(args.objective, args.target_lead_id)
    except Exception as e:  # noqa: BLE001
        log.error("crew failed: %s", type(e).__name__)
        return 2
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
