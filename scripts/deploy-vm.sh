#!/usr/bin/env bash
# Deploy PlantSpec Quickviewer to the Alchemy VM (local service on :8082).
#
# Run from your Mac after pushing changes:
#   ./scripts/deploy-vm.sh
#
# Optional env:
#   ALCHEMY_VM=ds-alchemy
#   ALCHEMY_ZONE=asia-south2-b
#   ALCHEMY_PROJECT=unique-bonbon-427911-r4
#   PLANTSPEC_BRANCH=main
#   PLANTSPEC_REMOTE=origin
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VM="${ALCHEMY_VM:-ds-alchemy}"
ZONE="${ALCHEMY_ZONE:-asia-south2-b}"
PROJECT="${ALCHEMY_PROJECT:-unique-bonbon-427911-r4}"
BRANCH="${PLANTSPEC_BRANCH:-main}"
REMOTE="${PLANTSPEC_REMOTE:-origin}"
VM_DIR="/home/mati/plantspec-quickviewer"
PORT=8082

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

echo "==> Deploy PlantSpec Quickviewer → $VM ($PROJECT / $ZONE)"
echo "    branch=$BRANCH remote=$REMOTE dir=$VM_DIR port=$PORT"
echo ""

gcloud compute ssh "$VM" \
  --zone="$ZONE" \
  --project="$PROJECT" \
  --command="bash -lc $(printf '%q' "
    set -euo pipefail
    cd '$VM_DIR'
    git fetch '$REMOTE' '$BRANCH'
    git checkout '$BRANCH'
    git pull '$REMOTE' '$BRANCH'
    if [[ ! -d .venv ]]; then
      python3 -m venv .venv
    fi
    source .venv/bin/activate
    pip install -q -r requirements-cloud.txt
    pkill -f 'uvicorn api.main:app.*$PORT' || true
    sleep 1
    nohup uvicorn api.main:app --host 127.0.0.1 --port $PORT > /tmp/plantspec.log 2>&1 &
    sleep 3
    echo '--- health ---'
    curl -sS http://127.0.0.1:$PORT/api/health
    echo
    echo '--- summary (first 160 chars) ---'
    curl -sS http://127.0.0.1:$PORT/api/summary | head -c 160
    echo
    echo '--- log tail ---'
    tail -5 /tmp/plantspec.log || true
  ")"

echo ""
echo "==> Done. Open Alchemy → Farmer Intelligence → PlantSpec Quickviewer (hard refresh)."
