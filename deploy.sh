#!/usr/bin/env bash
# Deploy PlantSpec Quickviewer demo as Cloud Run service ds-plantspec-quickviewer.
#
# Optional:
#   PROJECT_ID=unique-bonbon-427911-r4 REGION=asia-south2 SERVICE=ds-plantspec-quickviewer
#   MIN_INSTANCES=0 MEMORY=512Mi
#
# After deploy, set on Alchemy VM:
#   DS_PLANTSPEC_QUICKVIEWER_URL=<printed URL>
# Grant Cloud Run Invoker to ds-polygon-invoker@..., then restart alchemy-backend.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ID="${PROJECT_ID:-unique-bonbon-427911-r4}"
REGION="${REGION:-asia-south2}"
SERVICE="${SERVICE:-ds-plantspec-quickviewer}"
MEMORY="${MEMORY:-512Mi}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"

for _bin in \
  "$(command -v gcloud 2>/dev/null || true)" \
  "/opt/homebrew/share/google-cloud-sdk/bin/gcloud" \
  "/opt/homebrew/bin/gcloud" \
  "$HOME/google-cloud-sdk/bin/gcloud"
do
  if [[ -n "$_bin" && -x "$_bin" ]]; then
    export PATH="$(dirname "$_bin"):$PATH"
    break
  fi
done

if ! command -v gcloud >/dev/null 2>&1; then
  echo "ERROR: gcloud not found. Install Google Cloud SDK, then: gcloud auth login"
  exit 1
fi

echo "==> Deploying $SERVICE to $PROJECT_ID / $REGION (memory=$MEMORY, min-instances=$MIN_INSTANCES)"
cd "$ROOT"
gcloud run deploy "$SERVICE" \
  --project="$PROJECT_ID" \
  --source . \
  --region="$REGION" \
  --memory="$MEMORY" \
  --cpu=1 \
  --timeout=120s \
  --concurrency=20 \
  --max-instances=3 \
  --min-instances="$MIN_INSTANCES" \
  --no-allow-unauthenticated

URL="$(gcloud run services describe "$SERVICE" --project="$PROJECT_ID" --region="$REGION" --format='value(status.url)')"
echo ""
echo "==> Deployed: $URL"
echo ""
echo "Alchemy VM:"
echo "  export DS_PLANTSPEC_QUICKVIEWER_URL=$URL"
echo "  sudo systemctl restart alchemy-backend"
echo ""
echo "Smoke:"
echo "  TOKEN=\$(gcloud auth print-identity-token)"
echo "  curl -sS -H \"Authorization: Bearer \$TOKEN\" \"$URL/api/health\""
echo "  curl -sS -H \"Authorization: Bearer \$TOKEN\" \"$URL/api/summary\" | head"
