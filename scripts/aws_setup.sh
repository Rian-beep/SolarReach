#!/usr/bin/env bash
# scripts/aws_setup.sh — idempotently provision the SolarReach S3 bucket.
#
# What this does:
#   1. Creates bucket `solarreach-artifacts` in `eu-west-2` (skip if exists).
#   2. Sets server-side encryption (SSE-S3 / AES256).
#   3. Sets a public-read CORS policy for the demo (browser overlays + PPTX).
#      For production, replace with a signed-URL-only origin allowlist.
#   4. Sets lifecycle rule: artifacts older than 30 days → Glacier Deep Archive.
#
# Idempotent: every step is "create-or-update" — re-running is safe.
#
# Usage:
#   AWS_PROFILE=solarreach scripts/aws_setup.sh
#   # or, with explicit region/bucket overrides:
#   BUCKET=my-bucket REGION=eu-west-1 scripts/aws_setup.sh
#
# Required IAM permissions for the running principal:
#   s3:CreateBucket, s3:PutBucketCors, s3:PutBucketEncryption,
#   s3:PutLifecycleConfiguration, s3:GetBucketLocation, s3:HeadBucket
set -euo pipefail

BUCKET="${BUCKET:-solarreach-artifacts}"
REGION="${REGION:-eu-west-2}"

# tmp dir for the JSON policy bodies — cleaned on exit.
TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

aws_cli() { aws --region "$REGION" "$@"; }

echo "[aws-setup] bucket=$BUCKET region=$REGION"

# ─── 1. Create bucket if it doesn't exist ──────────────────────────────

# `head-bucket` returns 0 when accessible, non-zero when missing or denied.
# We treat any non-zero as "needs create"; AWS will reject if the name is
# globally taken by someone else, which is the right failure mode.
if aws_cli s3api head-bucket --bucket "$BUCKET" >/dev/null 2>&1; then
    echo "[aws-setup] bucket exists, skipping create"
else
    echo "[aws-setup] creating bucket"
    # us-east-1 is the only region that doesn't accept LocationConstraint.
    if [[ "$REGION" == "us-east-1" ]]; then
        aws_cli s3api create-bucket --bucket "$BUCKET"
    else
        aws_cli s3api create-bucket \
            --bucket "$BUCKET" \
            --create-bucket-configuration "LocationConstraint=$REGION"
    fi
fi

# ─── 2. Server-side encryption (SSE-S3) ────────────────────────────────

cat > "$TMPDIR/sse.json" <<'JSON'
{
  "Rules": [
    {
      "ApplyServerSideEncryptionByDefault": { "SSEAlgorithm": "AES256" },
      "BucketKeyEnabled": true
    }
  ]
}
JSON
aws_cli s3api put-bucket-encryption \
    --bucket "$BUCKET" \
    --server-side-encryption-configuration "file://$TMPDIR/sse.json"
echo "[aws-setup] SSE-S3 (AES256) enabled"

# ─── 3. Public-read CORS for the demo ──────────────────────────────────
# For the hackathon demo we want browser-side fetches of presigned URLs to
# work cross-origin from the Vite dev server + the deployed frontend. In
# production, narrow `AllowedOrigins` to your trusted hostnames.

cat > "$TMPDIR/cors.json" <<'JSON'
{
  "CORSRules": [
    {
      "AllowedHeaders": ["*"],
      "AllowedMethods": ["GET", "HEAD"],
      "AllowedOrigins": ["*"],
      "ExposeHeaders": ["ETag", "Content-Length", "Content-Type"],
      "MaxAgeSeconds": 3000
    }
  ]
}
JSON
aws_cli s3api put-bucket-cors \
    --bucket "$BUCKET" \
    --cors-configuration "file://$TMPDIR/cors.json"
echo "[aws-setup] CORS configured (demo: AllowedOrigins=*)"

# ─── 4. Lifecycle: → Glacier Deep Archive after 30d ────────────────────

cat > "$TMPDIR/lifecycle.json" <<'JSON'
{
  "Rules": [
    {
      "ID": "solarreach-artifacts-30d-to-deep-archive",
      "Status": "Enabled",
      "Filter": { "Prefix": "" },
      "Transitions": [
        {
          "Days": 30,
          "StorageClass": "DEEP_ARCHIVE"
        }
      ]
    }
  ]
}
JSON
aws_cli s3api put-bucket-lifecycle-configuration \
    --bucket "$BUCKET" \
    --lifecycle-configuration "file://$TMPDIR/lifecycle.json"
echo "[aws-setup] lifecycle rule: 30d → DEEP_ARCHIVE"

echo "[aws-setup] done. bucket s3://$BUCKET ready in $REGION."
