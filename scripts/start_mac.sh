#!/usr/bin/env bash
# Build (if needed) and run the FinAlly container on http://localhost:8000
# Usage: scripts/start_mac.sh [--build] [--no-open]
set -euo pipefail

IMAGE="finally:latest"
CONTAINER="finally"
PORT="8000"
VOLUME="finally-data"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

FORCE_BUILD=false
OPEN_BROWSER=true
for arg in "$@"; do
  case "$arg" in
    --build) FORCE_BUILD=true ;;
    --no-open) OPEN_BROWSER=false ;;
    *) echo "Unknown option: $arg"; echo "Usage: $0 [--build] [--no-open]"; exit 1 ;;
  esac
done

if [ ! -f .env ]; then
  echo "No .env found. Copying .env.example to .env — add your OPENROUTER_API_KEY."
  cp .env.example .env
fi

if [ "$FORCE_BUILD" = true ] || ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
  echo "Building $IMAGE ..."
  docker build -t "$IMAGE" .
fi

# Remove any previous container (running or stopped) so this is safe to re-run.
if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  echo "Removing existing container $CONTAINER ..."
  docker rm -f "$CONTAINER" >/dev/null
fi

echo "Starting $CONTAINER ..."
docker run -d \
  --name "$CONTAINER" \
  -p "${PORT}:8000" \
  -v "${VOLUME}:/app/db" \
  --env-file .env \
  --restart unless-stopped \
  "$IMAGE" >/dev/null

URL="http://localhost:${PORT}"
echo "FinAlly is starting at ${URL}"
echo "Logs:  docker logs -f ${CONTAINER}"
echo "Stop:  scripts/stop_mac.sh"

if [ "$OPEN_BROWSER" = true ] && command -v open >/dev/null 2>&1; then
  open "$URL"
fi
