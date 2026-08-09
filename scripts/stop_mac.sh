#!/usr/bin/env bash
# Stop and remove the FinAlly container. The finally-data volume is preserved.
set -euo pipefail

CONTAINER="finally"

if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER" >/dev/null
  echo "Stopped and removed container $CONTAINER (volume finally-data kept)."
else
  echo "Container $CONTAINER is not present. Nothing to do."
fi
