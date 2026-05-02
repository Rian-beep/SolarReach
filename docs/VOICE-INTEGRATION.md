# Voice Integration Handshake

> **Owner:** k-voice-bridge agent
> **Status (2026-05-02):** ElevenLabs provider live, Rian provider stubbed.
> **Trigger:** Run this checklist when Rian's voice branch lands at
> `Rian-beep/solarreach-project1` (or wherever the lib ends up shipping).

---

## TL;DR

The voice surface is provider-agnostic. The router talks to a `VoiceProvider`
protocol, not to ElevenLabs directly. Switching providers is one env-var flip
plus one `try/except` swap inside `RianProjectVoiceProvider.get_signed_url`.

## Probe findings (2026-05-02)

`https://github.com/Rian-beep/solarreach-project1` — cloned and inspected.

* **No voice/TTS/ConvAI module exists yet.** Packages present: `agents`,
  `scoring`, `shared`. No `voice/`, `tts/`, `convai/`, `elevenlabs/` paths.
* **Only voice-shaped surface:** `voice_agent_id: str | None` on the `Account`
  shared model (`packages/shared/py/solarreach_shared/models.py:210`). Comment
  says "ElevenLabs agent id override" — implies Rian intends to drive ElevenLabs
  via that field, not replace it with a different vendor.
* **Conclusion:** When Rian's voice work lands, expect either
  (a) a thin wrapper that resolves an account-specific `voice_agent_id` and
  still talks to ElevenLabs, or (b) a brand-new package that exports a client.
  We support both with the adapter below.

## Architecture (current)

```
VoiceTab.tsx ──GET /voice/signed-url──▶ routers/voice.py
                                            │
                                            ▼
                               services/voice_provider.py
                                       │       │
                                       ▼       ▼
                          ElevenLabsProvider  RianProjectVoiceProvider
                                                       │
                                                       └─▶ [stub] ImportError
                                                            ↓
                                                       returns demo_mode
```

* `routers/voice.py` is dumb — it picks the provider, calls
  `get_signed_url(lead, settings)`, and returns the result verbatim.
* Every provider returns a `SignedUrlResult` dataclass with a `status`
  field (`ok`, `demo_mode`, `disclosure_pending`, `upstream_error`).
* The router only emits HTTP 404 (lead not found). Everything else is 200
  with a `status` so the UI can render gracefully.

## Merge handshake — when Rian confirms ready

### Step 1. Pull his lib

If shipped as a workspace package:

```bash
# Add to packages/api/pyproject.toml dependencies:
"solarreach-voice",
# then:
uv sync   # or: pip install -e packages/voice  (whatever path he uses)
```

If shipped via git URL or PyPI, follow whatever install instructions
he provides.

### Step 2. Swap the stub

Edit `packages/api/app/services/voice_provider.py`. The only block that
changes is inside `RianProjectVoiceProvider.get_signed_url`:

```diff
 try:
-    raise ImportError("solarreach_voice not yet on PYTHONPATH")
+    from solarreach_voice import VoiceClient  # ← real import
+    client = VoiceClient.from_env()
+    url = await client.signed_url(lead_id=lead["_id"])
+    return SignedUrlResult(
+        signed_url=url,
+        agent_id=lead.get("voice_agent_id"),
+        system_prompt_filled=_system_prompt_for(lead),
+        status="ok",
+        message="",
+        metadata={"provider": "rian"},
+    )
 except ImportError as e:
     log.info("Rian voice provider stub: %s", e)
```

(Adjust the import path / call shape to whatever Rian actually exports.)

### Step 3. Flip the env var

```bash
# In .env.local on each dev machine and in deploy config:
VOICE_PROVIDER=rian
```

### Step 4. Run the suite

```bash
cd packages/api && python -m pytest tests/test_voice.py -v
cd packages/web && pnpm typecheck
```

The existing test
`test_voice_signed_url_rian_provider_returns_demo_mode` will need to be
updated — once the stub is gone it should assert `status=ok` (mocking the
`VoiceClient` upstream).

### Step 5. Smoke test

1. Open the drawer, switch to Voice tab on a real lead.
2. Click `[REHEARSE PITCH]` → should connect.
3. The "DEMO MODE" cyan pill should NOT appear.

## Contract notes

* `SignedUrlResult.signed_url` may be `None` for any non-`ok` status.
  The frontend already handles this — see
  `VoiceTab.tsx` (`if (res.status !== "ok" || !res.signed_url) { ... }`).
* `provider` is echoed in the response body so we can debug from the network
  tab whose code path actually ran.
* Rian's lib MUST keep the AI-disclosure invariant. If his client signs URLs
  without enforcing the disclosure prompt server-side, we break
  CONTRACTS § 7.8. Either:
  * keep the disclosure check in `RianProjectVoiceProvider.get_signed_url`
    before calling his client, OR
  * have his lib enforce it and document that fact in this file.

## Possible contract breaks to watch for

| Risk | Detection | Mitigation |
| --- | --- | --- |
| Rian's lib returns a different envelope (e.g. nested under `data.signed_url`) | `KeyError` / `None` in tests | Adapt the field-pull inside `RianProjectVoiceProvider`; keep `SignedUrlResult` shape stable |
| Rian's lib needs MongoDB access | Init failure in `from_env()` | Pass `db` into `get_signed_url(...)` if needed; update the protocol |
| Rian's lib uses synchronous I/O | Blocks event loop | Wrap in `asyncio.to_thread(...)` |
| Different agent-id field on the lead | Wrong agent talks | Resolve `lead.get("voice_agent_id")` first, fallback to `settings.elevenlabs_agent_id` |

## Rollback

If Rian's provider regresses: `VOICE_PROVIDER=elevenlabs` and restart
the API. No code changes required.
