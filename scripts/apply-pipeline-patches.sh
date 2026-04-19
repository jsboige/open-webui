#!/usr/bin/env bash
# Apply MyIA-local patches to the shared pipelines container.
# Idempotent: copies patched pipeline files from repo into the pipelines
# container volume, then restarts the container so they load.
#
# Target: myia-open-webui-pipelines-1 (shared across all 7 tenants via the
# open-webui-shared Docker network alias "pipelines").
#
# Usage: bash scripts/apply-pipeline-patches.sh

set -euo pipefail

CONTAINER="myia-open-webui-pipelines-1"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
    echo "ERROR: ${CONTAINER} is not running" >&2
    exit 1
fi

echo "Applying pipeline patches to ${CONTAINER}..."

for patched in "${REPO_DIR}/pipelines/"*.py; do
    [ -f "$patched" ] || continue
    base=$(basename "$patched")
    MSYS_NO_PATHCONV=1 docker cp "$patched" "${CONTAINER}:/app/pipelines/${base}"
    echo "  ✓ ${base}"
done

echo "Restarting ${CONTAINER}..."
docker restart "${CONTAINER}" > /dev/null

echo "Waiting for startup..."
for i in $(seq 1 30); do
    sleep 2
    if docker logs --tail=5 "${CONTAINER}" 2>&1 | grep -q "Uvicorn running"; then
        echo "  ✓ ready"
        exit 0
    fi
done
echo "WARN: container did not report ready within 60s — check logs manually" >&2
