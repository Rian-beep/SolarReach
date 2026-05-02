# Security incident — committed-secret rotation log

This file tracks any credential leaked into the git history. Each entry must
be resolved (rotated upstream + history scrubbed if pushed) before the repo
is made public.

## Severity legend

- **CRITICAL** — production-grade key, paid service, billable risk
- **HIGH** — free-tier or limited key with PII access
- **LOW** — sandbox/test credential, no real exposure

---

## INC-2026-05-02-01 — Companies House API key (HIGH)

- **Detected**: 2026-05-02 (audit by Opus 4.7)
- **File**: `docs/agent-log/A7-companies-house.md` (line 99 + 102 in the
  pre-redaction blob)
- **Commit introducing leak**: `603aaeb` (`feat: real Mongo data flow + ErrorBoundary; flip /scan off mock-create path`)
- **Key fingerprint**: UUID-form Companies House key, prefix `81f025d7`,
  length 36 chars. Full value NOT reproduced here.
- **Status of key upstream**: already returning 401 at audit time, so the
  key was either expired/disabled before the leak or revoked since. Treat as
  compromised regardless.
- **Public-repo blast radius**: Companies House is a free, rate-limited UK
  govt API. No PII beyond what is already public in companies-register data.
  No billing exposure. **Rotation still mandatory** before public push.

### Action required (Luke)

1. Sign in: https://developer.company-information.service.gov.uk/manage-applications
2. Revoke the existing key (prefix `81f025d7`).
3. Generate a replacement key.
4. Update `~/.../.env.local` (line 33: `COMPANIES_HOUSE_API_KEY=...`).
5. **Before pushing to public GitHub**: scrub the leaked value from git
   history. The current HEAD has been redacted, but the blob still exists
   in the pack. Use one of:
   ```bash
   # Option A: BFG (recommended, fast)
   bfg --replace-text <(echo '81f025d7-b5eb-41a0-89cd-3d11c8e45700==>REDACTED') .git
   git reflog expire --expire=now --all && git gc --prune=now --aggressive

   # Option B: git-filter-repo
   git filter-repo --replace-text <(echo '81f025d7-b5eb-41a0-89cd-3d11c8e45700==>REDACTED')
   ```
6. Force-push the rewritten history once teammates have rebased onto the
   new tip. Coordinate via the agent-log channel — see `docs/SECURITY.md`.

### Verification

After rotation + scrub:

```bash
git log --all -p | grep -c '81f025d7'   # must print 0
```

---

## Reference: keys present on disk in `.env.local` (NOT committed, but still
on Luke's laptop)

These were verified to live ONLY in `.env.local` (gitignored, never tracked)
at the time of audit. They are NOT in any commit. No rotation strictly
required by this audit, but standard hygiene says: rotate any key that has
been pasted into a chat, screenshot, or shared doc.

| Variable                   | Prefix    | Length | In git? |
|----------------------------|-----------|--------|---------|
| `MONGO_URI`                | mongod    | 146    | no      |
| `ANTHROPIC_API_KEY`        | sk-ant    | 108    | no      |
| `GOOGLE_MAPS_API_KEY`      | AIzaSy    | 39     | no      |
| `VITE_GOOGLE_MAPS_API_KEY` | AIzaSy    | 39     | no      |
| `ELEVENLABS_API_KEY`       | sk_e7d    | 51     | no      |
| `ELEVENLABS_AGENT_ID`      | agent_    | 34     | no      |
| `COMPANIES_HOUSE_API_KEY`  | 81f025    | 36     | **YES — see INC-2026-05-02-01** |
| `VOYAGE_API_KEY`           | al-WSJ    | 46     | no      |

Audit method: `git log --all -p | grep -E "<prefix>"` for each value's
distinguishing prefix. Only the Companies House key matched.
