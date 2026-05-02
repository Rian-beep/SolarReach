# AWS S3 integration

Owner: A2 (API gateway)
Last reviewed: 2026-05-02

SolarReach uploads three classes of generated artifact to S3 so the demo
survives backend restarts and can be served from a CDN-friendly origin:

| Artifact            | Bucket key                                | Producer                          |
| ------------------- | ----------------------------------------- | --------------------------------- |
| Pitch deck (PPTX)   | `pitches/{lead_id}/{pitch_id}.pptx`       | `routers/leads.py` `pitch`        |
| Pitch deck (PDF)    | `pitches/{lead_id}/{pitch_id}.pdf`        | `routers/leads.py` `pitch`        |
| Voice TTS (mp3)     | `voice/{lead_id}/{ts}.mp3`                | `routers/voice.py` `pitch_audio`  |
| Flux overlay (PNG)  | `flux/{lead_id}.png`                      | `services/solar_api.py` (flux)    |

Local copies are always written first (under `/tmp/decks`, `/tmp/swarm-tts`,
`/tmp/flux`). S3 is upload-best-effort: if AWS env vars are missing or the
upload fails, the API returns the local URL and logs a warning. The route
never 5xxs because of S3.

## Required environment variables

```bash
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=eu-west-2          # default; override per-deploy
S3_BUCKET=solarreach-artifacts # default; override per-deploy
```

If any of `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `S3_BUCKET` is
missing, `S3Storage` flips to local-only mode (`enabled=False`) and emits
one startup warning. No further runtime warnings — every call returns a
`file://` URL pointing at the local copy.

## Required IAM permissions

Attach this policy to the IAM principal whose access keys are stored in
`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SolarReachArtifactsRW",
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::solarreach-artifacts/*"
    },
    {
      "Sid": "SolarReachBucketList",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::solarreach-artifacts"
    }
  ]
}
```

The `aws_setup.sh` script (run once by the operator) needs broader
permissions — see the script header for the bootstrap policy.

## Bucket structure

```
s3://solarreach-artifacts/
├── pitches/
│   └── {lead_id}/
│       ├── {pitch_id}.pptx
│       └── {pitch_id}.pdf
├── voice/
│   └── {lead_id}/
│       └── {ts}.mp3       # ts is YYYYMMDDTHHMMSSZ UTC
└── flux/
    └── {lead_id}.png
```

Keys are scoped per-lead so a re-run replaces (pitch/flux) or accumulates
(voice — useful for A/B-ing TTS takes during demo prep). The lifecycle
rule sweeps everything older than 30 days into Glacier Deep Archive.

## Provisioning

Run once (and only once) by the operator:

```bash
AWS_PROFILE=solarreach scripts/aws_setup.sh
```

The script is idempotent: re-running it updates the encryption / CORS /
lifecycle policies but never destroys data. Bucket creation is skipped
on the second run via `head-bucket`.

## URLs returned to the frontend

`put_object` returns an `S3PutResult` with a `url` field that's always
populated:

- Live mode: `https://solarreach-artifacts.s3.eu-west-2.amazonaws.com/...`
  signed with the access key, expiring in 1 hour.
- No-op mode: `file:///tmp/decks/pitch_xxx.pptx` (the local path the
  caller already wrote).

The frontend prefers the S3 URL when present (`pptx_s3_url`,
`pdf_s3_url`, `audio_s3_url`) and falls back to the `/static/...` URL
served by FastAPI's StaticFiles mount.

To re-sign an expired URL:

```python
from app.services.s3_storage import get_s3_storage
fresh = await get_s3_storage().get_signed_url(key, ttl_sec=3600)
```

## Cost ceiling

S3 Standard tier in eu-west-2 costs ~$0.023/GB/month. The demo workload
generates roughly:

- 50 leads × 5 MB pitch (PPTX + PDF)  ≈ 250 MB
- 50 voice mp3s × 1 MB                 ≈ 50 MB
- 50 flux PNGs × 200 KB                ≈ 10 MB

Total: **~310 MB**, costing **~$0.007/month** (well under £1/mo even with
GET request charges). The 30-day lifecycle to Deep Archive ($0.00099/GB)
makes the long tail effectively free.

## Failure modes

| Failure                           | Behaviour                                      |
| --------------------------------- | ---------------------------------------------- |
| Missing AWS env vars              | Local-only mode, one startup warning           |
| Wrong region                      | First `put_object` warns, returns local URL    |
| Bucket doesn't exist              | First `put_object` warns, returns local URL    |
| Expired access key                | First `put_object` warns, returns local URL    |
| Network partition                 | First `put_object` warns, returns local URL    |
| `aioboto3` not installed          | Clear `RuntimeError` at first S3 call          |

In every soft-failure case, the local copy under `/tmp/...` is intact
and served by the existing StaticFiles mount, so the demo continues
unchanged.
