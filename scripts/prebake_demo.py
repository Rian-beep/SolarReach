"""Pre-bake the EC2M 7EB CodeNode demo so the live demo never blocks on a
slow / flaky API call.

What this does (idempotent — safe to re-run):

  1. Read MONGO_URI from env (or .env.local) and connect to Atlas.
  2. Identify the CodeNode demo lead + the top-12 EC2M 7EB leads by
     composite_score.
  3. For each lead, ensure the API has cached flux + panels (POST /lead/<id>/flux_overlay
     and /panels) and warmed Opus org-chart inference (POST /lead/<id>/build_org).
  4. Drive the real Sonnet pitch generator via POST /lead/<id>/pitch which
     persists the PPTX (and PDF when LibreOffice is on PATH).
  5. For the CodeNode lead specifically, synthesise an ElevenLabs TTS voice
     pitch from the generated deck headline so the rehearsal tab can play
     audio without re-hitting the live ConvAI session.
  6. Copy every artifact into data/demo-bundle/<slug>/ + write a manifest.

The script never crashes the run on a single failed lead — failures are
captured in the manifest so the demo runner can decide whether to fall back.

Usage:
    cd <repo>
    export MONGO_URI=$(grep ^MONGO_URI= .env.local | sed 's/^MONGO_URI=//')
    python scripts/prebake_demo.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
BUNDLE_ROOT = REPO_ROOT / "data" / "demo-bundle"
PITCHES_DIR = Path(os.environ.get("SOLARREACH_PITCHES_DIR", "/tmp/decks"))
FLUX_DIR = Path("/tmp/flux")
API_BASE = os.environ.get("API_BASE", "http://localhost:8000")
CLIENT_ID = "client-greensolar-uk"
CODENODE_LEAD_ID = "lead_codenode_demo"
CODENODE_SLUG = "codenode"
EC2M_TOP_N = 12
HTTP_TIMEOUT = 120.0  # /pitch through Sonnet can take a while

# ElevenLabs default "George" voice — same one the demo TTS smoke uses.
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
ELEVENLABS_MODEL = os.environ.get("ELEVENLABS_MODEL", "eleven_turbo_v2_5")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("prebake_demo")


# ─── env loading ──────────────────────────────────────────────────────────────


def _load_dotenv() -> None:
    """Best-effort .env.local merge so the script can be run without sourcing."""
    env_path = REPO_ROOT / ".env.local"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        # Only fill empties — never override an explicit env var.
        if k and not os.environ.get(k):
            os.environ[k] = v


# ─── helpers ──────────────────────────────────────────────────────────────────


def _slugify(value: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", value).strip("_").lower()
    return s or "lead"


def _slug_for_lead(lead: dict[str, Any]) -> str:
    if lead["_id"] == CODENODE_LEAD_ID:
        return CODENODE_SLUG
    return _slugify(lead["_id"])


def _bundle_dir(slug: str) -> Path:
    d = BUNDLE_ROOT / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def _existing_manifest(slug: str) -> dict[str, Any] | None:
    p = _bundle_dir(slug) / "manifest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return None


def _is_complete(manifest: dict[str, Any] | None, want_voice: bool) -> bool:
    if not manifest:
        return False
    artefacts = manifest.get("artefacts") or {}
    if not artefacts.get("pitch_pptx"):
        return False
    if not artefacts.get("flux_overlay_png"):
        return False
    if not artefacts.get("panels_json"):
        return False
    panel_count = manifest.get("panel_count") or 0
    if panel_count < 6:
        return False
    if want_voice and not artefacts.get("voice_pitch_mp3"):
        # Only treat voice as required if the caller still wants it.
        return False
    return True


async def _get_spend(http: httpx.AsyncClient) -> int:
    try:
        r = await http.get(f"{API_BASE}/lead/spend/session")
        r.raise_for_status()
        return int(r.json().get("spent_cents", 0))
    except Exception as e:  # noqa: BLE001
        log.warning("spend fetch failed: %s", e)
        return 0


def _resolve_pitch_filename(url: str | None) -> str | None:
    if not url:
        return None
    prefix = "/static/pitches/"
    if url.startswith(prefix):
        return url[len(prefix):]
    return None


# ─── pre-bake stages ─────────────────────────────────────────────────────────


async def _ensure_flux_panels(http: httpx.AsyncClient, lead_id: str) -> dict[str, Any]:
    out: dict[str, Any] = {}
    # /flux_overlay first — caches inside Mongo for 24h, idempotent.
    try:
        r = await http.post(f"{API_BASE}/lead/{lead_id}/flux_overlay", timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        out["flux"] = r.json()
    except Exception as e:  # noqa: BLE001
        out["flux_error"] = f"{type(e).__name__}: {e}"
    try:
        r = await http.post(f"{API_BASE}/lead/{lead_id}/panels", timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        out["panels"] = r.json()
    except Exception as e:  # noqa: BLE001
        out["panels_error"] = f"{type(e).__name__}: {e}"
    return out


async def _build_org(http: httpx.AsyncClient, lead_id: str) -> dict[str, Any]:
    try:
        r = await http.post(f"{API_BASE}/lead/{lead_id}/build_org", timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:  # noqa: BLE001
        return {"error": f"{type(e).__name__}: {e}"}


async def _generate_pitch(
    http: httpx.AsyncClient, lead_id: str, *, max_attempts: int = 3
) -> dict[str, Any]:
    """Call /pitch and retry up to max_attempts if the route stubs out (used_real=False).

    Sonnet occasionally bubbles up a transient BadRequestError on long pitches;
    re-running consistently lands a real generation on the second attempt.
    """
    last: dict[str, Any] = {}
    for attempt in range(1, max_attempts + 1):
        try:
            r = await http.post(
                f"{API_BASE}/lead/{lead_id}/pitch",
                json={"client_id": CLIENT_ID},
                timeout=HTTP_TIMEOUT,
            )
            r.raise_for_status()
            last = r.json()
        except Exception as e:  # noqa: BLE001
            last = {"error": f"{type(e).__name__}: {e}"}
            await asyncio.sleep(1.5)
            continue
        if last.get("used_real"):
            last["attempts"] = attempt
            return last
        # Backoff briefly then retry — the stub fallback is what we want to escape.
        await asyncio.sleep(1.5 * attempt)
    last["attempts"] = max_attempts
    return last


def _copy_artifact(src: Path, dst: Path) -> Path | None:
    if not src.exists() or not src.is_file():
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return dst


async def _tts_voice_pitch(
    http: httpx.AsyncClient,
    text: str,
    out_path: Path,
) -> dict[str, Any]:
    """Synthesise one TTS clip via ElevenLabs. Soft-fails to a skip record."""
    api_key = os.environ.get("ELEVENLABS_API_KEY", "")
    if not api_key:
        return {"skipped": True, "reason": "no_elevenlabs_api_key"}
    if not text.strip():
        return {"skipped": True, "reason": "empty_pitch_text"}
    body = {
        "text": text,
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": {"stability": 0.4, "similarity_boost": 0.75},
    }
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    try:
        r = await http.post(url, headers=headers, json=body, timeout=60.0)
        if r.status_code != 200:
            return {
                "skipped": True,
                "reason": f"elevenlabs_{r.status_code}",
                "body": r.text[:300],
            }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(r.content)
        return {"ok": True, "bytes": len(r.content), "voice_id": ELEVENLABS_VOICE_ID}
    except Exception as e:  # noqa: BLE001
        return {"skipped": True, "reason": f"{type(e).__name__}: {e}"}


def _voice_pitch_text(lead: dict[str, Any], pitch_payload: dict[str, Any]) -> str:
    """Build a short voice script from the generated deck JSON.

    Falls back to a plain template if the deck hasn't materialised. Kept
    intentionally short (~30s of speech) so we never blow the ElevenLabs
    free-tier credit during pre-bake.
    """
    deck = pitch_payload.get("deck_json") or {}
    title = (deck.get("title") or {}).get("headline") or "a tailored solar proposal"
    company = (lead.get("owner") or {}).get("company_name") or "your team"
    address = lead.get("address") or "your London site"
    dm = lead.get("decision_maker") or {}
    dm_name = dm.get("name", "there")
    intro = (
        f"Hi {dm_name}, this is the SolarReach AI sales agent calling on behalf of "
        f"GreenSolar UK. I'm an AI — and I have a pre-baked solar proposal ready "
        f"for {company} at {address}. Headline: {title}. "
        "If you have ninety seconds I'd love to walk you through the rooftop yield, "
        "payback period, and ESG impact our model produced for you. "
        "Otherwise we can email the deck and follow up next week."
    )
    return intro


# ─── main per-lead pipeline ──────────────────────────────────────────────────


async def prebake_one(
    http: httpx.AsyncClient,
    lead: dict[str, Any],
    *,
    do_voice: bool,
    spend_before: int,
) -> dict[str, Any]:
    lead_id = lead["_id"]
    slug = _slug_for_lead(lead)
    bundle = _bundle_dir(slug)
    log.info("prebake start lead=%s slug=%s", lead_id, slug)

    existing = _existing_manifest(slug)
    if _is_complete(existing, want_voice=do_voice):
        log.info("  ↳ already complete — skipping (idempotent)")
        return existing  # type: ignore[return-value]

    record: dict[str, Any] = {
        "lead_id": lead_id,
        "slug": slug,
        "address": lead.get("address"),
        "postcode": lead.get("postcode"),
        "owner": (lead.get("owner") or {}).get("company_name"),
        "composite_score": (lead.get("scores") or {}).get("composite_score"),
        "stages": {},
        "artefacts": {},
        "errors": [],
    }

    # Stage 1 — flux + panels
    flux_panels = await _ensure_flux_panels(http, lead_id)
    record["stages"]["flux_panels"] = flux_panels
    panel_count = ((flux_panels.get("panels") or {}).get("panel_count")) or 0
    record["panel_count"] = int(panel_count)

    # Stage 2 — org chart (Opus)
    org = await _build_org(http, lead_id)
    record["stages"]["build_org"] = org
    if "error" in org:
        record["errors"].append(f"build_org: {org['error']}")

    # Stage 3 — pitch (Sonnet → PPTX/PDF)
    pitch_payload = await _generate_pitch(http, lead_id)
    record["stages"]["pitch"] = {
        "used_real": pitch_payload.get("used_real"),
        "cost_cents": pitch_payload.get("cost_cents"),
        "pptx_url": pitch_payload.get("pptx_url"),
        "pdf_url": pitch_payload.get("pdf_url"),
    }
    if "error" in pitch_payload:
        record["errors"].append(f"pitch: {pitch_payload['error']}")

    # Copy artefacts → bundle dir.
    pptx_name = _resolve_pitch_filename(pitch_payload.get("pptx_url"))
    if pptx_name:
        copied = _copy_artifact(PITCHES_DIR / pptx_name, bundle / "pitch.pptx")
        if copied:
            record["artefacts"]["pitch_pptx"] = str(copied.relative_to(REPO_ROOT))
            record["artefacts"]["pitch_pptx_bytes"] = copied.stat().st_size
    pdf_name = _resolve_pitch_filename(pitch_payload.get("pdf_url"))
    if pdf_name:
        copied = _copy_artifact(PITCHES_DIR / pdf_name, bundle / "pitch.pdf")
        if copied:
            record["artefacts"]["pitch_pdf"] = str(copied.relative_to(REPO_ROOT))
            record["artefacts"]["pitch_pdf_bytes"] = copied.stat().st_size

    # Flux PNG.
    flux_png_src = FLUX_DIR / f"{lead_id}.png"
    copied = _copy_artifact(flux_png_src, bundle / "flux_overlay.png")
    if copied:
        record["artefacts"]["flux_overlay_png"] = str(copied.relative_to(REPO_ROOT))
        record["artefacts"]["flux_overlay_bytes"] = copied.stat().st_size

    # Panels JSON.
    panels_payload = flux_panels.get("panels") or {}
    if panels_payload:
        panels_path = bundle / "panels.json"
        panels_path.write_text(json.dumps(panels_payload, indent=2), encoding="utf-8")
        record["artefacts"]["panels_json"] = str(panels_path.relative_to(REPO_ROOT))
        record["artefacts"]["panels_json_bytes"] = panels_path.stat().st_size

    # Deck JSON for inspection.
    deck_json = pitch_payload.get("deck_json")
    if deck_json:
        deck_path = bundle / "deck.json"
        deck_path.write_text(json.dumps(deck_json, indent=2), encoding="utf-8")
        record["artefacts"]["deck_json"] = str(deck_path.relative_to(REPO_ROOT))

    emails = pitch_payload.get("emails")
    if emails:
        emails_path = bundle / "emails.json"
        emails_path.write_text(json.dumps(emails, indent=2), encoding="utf-8")
        record["artefacts"]["emails_json"] = str(emails_path.relative_to(REPO_ROOT))

    # Stage 4 — voice TTS (CodeNode only).
    if do_voice:
        voice_text = _voice_pitch_text(lead, pitch_payload)
        voice_out = bundle / "voice_pitch.mp3"
        if voice_out.exists():
            log.info("  ↳ voice mp3 already exists, skipping TTS")
            voice_record = {"ok": True, "skipped": "exists", "bytes": voice_out.stat().st_size}
        else:
            voice_record = await _tts_voice_pitch(http, voice_text, voice_out)
        record["stages"]["voice"] = voice_record
        if voice_record.get("ok") and voice_out.exists():
            record["artefacts"]["voice_pitch_mp3"] = str(voice_out.relative_to(REPO_ROOT))
            record["artefacts"]["voice_pitch_text"] = voice_text
            record["artefacts"]["voice_pitch_bytes"] = voice_out.stat().st_size
        elif voice_record.get("skipped"):
            record["errors"].append(f"voice: {voice_record.get('reason')}")

    # Spend delta for this lead (server-side audit-log truth).
    spend_after = await _get_spend(http)
    record["cost_cents_delta"] = max(0, spend_after - spend_before)
    record["spend_after_cents"] = spend_after
    record["completed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    # Persist manifest for this lead.
    (bundle / "manifest.json").write_text(
        json.dumps(record, indent=2, default=str), encoding="utf-8"
    )
    log.info(
        "  ↳ done lead=%s panels=%s pptx=%s pdf=%s voice=%s cost_delta=%s",
        lead_id,
        record.get("panel_count"),
        bool(record["artefacts"].get("pitch_pptx")),
        bool(record["artefacts"].get("pitch_pdf")),
        bool(record["artefacts"].get("voice_pitch_mp3")),
        record["cost_cents_delta"],
    )
    return record


# ─── lead selection ──────────────────────────────────────────────────────────


async def select_target_leads() -> list[dict[str, Any]]:
    """Pick the CodeNode lead + top-N EC2M 7EB leads by composite_score."""
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_uri = os.environ.get("MONGO_URI")
    if not mongo_uri:
        raise SystemExit("MONGO_URI is empty — set it before running")

    db_name = os.environ.get("MONGO_DB", "solarreach")
    client = AsyncIOMotorClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        db = client[db_name]
        codenode = await db.leads.find_one({"_id": CODENODE_LEAD_ID})
        if not codenode:
            raise SystemExit(
                f"{CODENODE_LEAD_ID} not in atlas — run scripts/ingest_real_demo.py first"
            )
        cur = (
            db.leads.find(
                {"postcode": {"$regex": r"^EC2M\s*7EB$", "$options": "i"}}
            )
            .sort([("scores.composite_score", -1), ("_id", 1)])
            .limit(EC2M_TOP_N + 1)  # +1 to account for codenode possibly being in here
        )
        ec2m = await cur.to_list(length=EC2M_TOP_N + 1)
        seen = {codenode["_id"]}
        ordered = [codenode]
        for lead in ec2m:
            if lead["_id"] in seen:
                continue
            ordered.append(lead)
            seen.add(lead["_id"])
            if len(ordered) >= EC2M_TOP_N + 1:
                break
        return ordered
    finally:
        client.close()


# ─── entrypoint ──────────────────────────────────────────────────────────────


async def main() -> int:
    _load_dotenv()
    BUNDLE_ROOT.mkdir(parents=True, exist_ok=True)

    leads = await select_target_leads()
    log.info(
        "selected %d leads for prebake (codenode + top %d EC2M 7EB)",
        len(leads),
        EC2M_TOP_N,
    )

    async with httpx.AsyncClient() as http:
        # Confirm API reachable up front so we fail fast.
        try:
            r = await http.get(f"{API_BASE}/health", timeout=5.0)
            r.raise_for_status()
        except Exception as e:  # noqa: BLE001
            raise SystemExit(
                f"API not reachable at {API_BASE} ({type(e).__name__}: {e}). "
                "Start it with `make dev` or `cd packages/api && uv run uvicorn app.main:app --reload`."
            )

        spend_start = await _get_spend(http)
        log.info("spend baseline: %d cents", spend_start)

        results: list[dict[str, Any]] = []
        for idx, lead in enumerate(leads):
            spend_before = await _get_spend(http)
            do_voice = lead["_id"] == CODENODE_LEAD_ID
            try:
                rec = await prebake_one(
                    http, lead, do_voice=do_voice, spend_before=spend_before
                )
            except Exception as e:  # noqa: BLE001 — keep going so partial bundle still useful
                log.exception("prebake failed for %s: %s", lead["_id"], e)
                rec = {
                    "lead_id": lead["_id"],
                    "slug": _slug_for_lead(lead),
                    "errors": [f"unhandled: {type(e).__name__}: {e}"],
                }
            results.append(rec)
            log.info("[%d/%d] done %s", idx + 1, len(leads), lead["_id"])

        spend_end = await _get_spend(http)

    total_delta = max(0, spend_end - spend_start)
    bundle_manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "api_base": API_BASE,
        "spend_start_cents": spend_start,
        "spend_end_cents": spend_end,
        "spend_delta_cents": total_delta,
        "spend_delta_gbp": round(total_delta / 100, 4),
        "lead_count": len(leads),
        "codenode_lead_id": CODENODE_LEAD_ID,
        "leads": [
            {
                "lead_id": r.get("lead_id"),
                "slug": r.get("slug"),
                "address": r.get("address"),
                "postcode": r.get("postcode"),
                "owner": r.get("owner"),
                "composite_score": r.get("composite_score"),
                "panel_count": r.get("panel_count"),
                "artefacts": r.get("artefacts", {}),
                "errors": r.get("errors", []),
            }
            for r in results
        ],
    }
    (BUNDLE_ROOT / "manifest.json").write_text(
        json.dumps(bundle_manifest, indent=2, default=str), encoding="utf-8"
    )

    print(
        f"\nprebake complete — {len(results)} leads, spend delta "
        f"{total_delta} cents (~£{total_delta/100:.2f})\n"
        f"bundle root: {BUNDLE_ROOT.relative_to(REPO_ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
