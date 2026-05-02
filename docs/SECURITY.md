# Security policy — SolarReach hackathon repo

Owner: Luke Dudley (lukejazzdudley@gmail.com)
Last reviewed: 2026-05-02

This is a hackathon prototype. The bar is "safe to push to a public GitHub
repo and demo on stage" — not enterprise-grade. Where that bar disagrees
with normal production hygiene, the looser rule is called out explicitly.

## 1. Secret-handling rules

### 1.1 What is a secret

Anything that grants access to a paid or rate-limited service, or to PII,
or to data we don't own. Concretely:

- API keys (Anthropic, Google, ElevenLabs, Voyage, Resend, Hunter, etc.)
- DB connection strings that include a password (any `mongodb+srv://` with
  embedded credentials)
- OAuth tokens, signed JWTs, Companies House keys, Met Office keys
- Anything matching the regexes in `.githooks/pre-commit` (sk-ant-, AIza,
  sk_, mongodb+srv://USER:PASS, etc.)

### 1.2 Where secrets live

- **Local dev**: `.env.local` at repo root (gitignored). Copy from
  `.env.example` and fill in. Never copy from `.env.local.template` —
  that file is the contract template, not a secret store.
- **CI**: GitHub Actions secrets, scoped to the workflow that needs them.
- **Demo machine**: same `.env.local`, exported via `set -a; source
  .env.local; set +a` in `scripts/start-api.sh`.

### 1.3 What never goes in git

- `.env`, `.env.local`, `.env.*.local` (covered by `.gitignore`)
- Govt zip extracts (`*.zip`, `data/raw/`)
- Voice transcripts containing personally identifiable lead data
  (covered by `outbox/` in `.gitignore`)
- Screenshots that include the API key bar of a service console

### 1.4 What goes in `.env.example`

Variable name, a comment explaining what it is and where to get it, and a
placeholder VALUE that cannot be mistaken for a real key. Use the form
`sk-ant-...` or `AIza...` — three characters of prefix followed by `...`.
Never paste a partial real key, even five chars of one, because it leaks
the keyspace prefix.

## 2. Pre-commit secret scanner

A pre-commit hook lives at `.githooks/pre-commit`. It is enabled in the
contributor's clone with:

```bash
git config core.hooksPath .githooks
```

The hook runs on every `git commit` and rejects the commit if it sees:

- An Anthropic key (`sk-ant-` followed by 50+ key-shaped chars)
- A Google API key (`AIza` followed by 35 key-shaped chars)
- An ElevenLabs key (`sk_` followed by 32+ hex chars)
- A Mongo Atlas SRV URI with embedded password
- A Companies House UUID-form key

If `gitleaks` or `trufflehog` is installed in `$PATH`, the hook will also
invoke that tool. Neither is required — the regex pass is a hard gate.

The hook does NOT scan files matched by `.gitignore`. It does scan
already-tracked files when their content changes, so accidental paste of
a key into a tracked doc is caught.

## 3. Key rotation procedure

When a key needs rotating (leak detected, departing teammate, or routine
hygiene every 30 days during the hackathon period):

1. **Generate replacement** in the upstream provider's console.
2. **Update `.env.local`** locally.
3. **Update each teammate's `.env.local`** via the agent-log channel — DM
   the new value, never paste into the repo or a public channel.
4. **If the old key was ever in git**:
   - Open a `docs/SECURITY-INCIDENT.md` entry (see template in that file).
   - Revoke the old key upstream **before** rewriting history.
   - Use `bfg` or `git filter-repo` to scrub the value from history.
   - Coordinate force-push so all teammates rebase.
5. **Verify** with: `git log --all -p | grep -c <old-key-prefix>` returns 0.

## 4. Incident response — who to contact

| Severity | What                                              | Contact                                             |
|----------|---------------------------------------------------|-----------------------------------------------------|
| CRITICAL | Anthropic / OpenAI / Google billing key in public repo | Luke (lukejazzdudley@gmail.com), within 1h. Revoke first, ask questions later. |
| HIGH     | Free-tier UK govt key, sandbox Mongo URI           | Luke, within 24h. Document in `SECURITY-INCIDENT.md`. |
| LOW      | Test fixture, dummy value (`sk-ant-fake-*`)        | No action. Confirm prefix matches "fake" in commit. |

For incidents during the hackathon judging window (deadline 2026-05-02
17:00), Luke is on-site — escalate in person before opening any console.

## 5. What this policy does NOT cover

- Production-grade key vault (Vault, AWS Secrets Manager, Doppler) — out
  of scope for the hackathon. Post-finalist, migrate to one before any
  paying customer gets onboarded.
- Per-service IAM roles. The Anthropic and Google keys are user-scoped
  and shared across the team. Acceptable for a 5-person hackathon team,
  unacceptable for production.
- Network-level secrets (TLS certs, VPN configs). The demo runs on
  localhost and over the conference wifi. No certs in repo.

## 6. Audit trail

| Date       | Auditor                  | Outcome                             |
|------------|--------------------------|-------------------------------------|
| 2026-05-02 | Opus 4.7 (Luke's session) | 1 leak found (INC-2026-05-02-01).   |
