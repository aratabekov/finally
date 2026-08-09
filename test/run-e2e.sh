#!/usr/bin/env bash
# Build and start the app container with a clean database, run Playwright
# against it, then tear the container down. Idempotent.
set -euo pipefail

cd "$(dirname "$0")"

COMPOSE="docker compose -f docker-compose.test.yml"

cleanup() {
  $COMPOSE down --remove-orphans >/dev/null 2>&1 || true
}
trap cleanup EXIT

cleanup
$COMPOSE up -d --build

echo "waiting for http://localhost:8000/api/health"
for _ in $(seq 1 60); do
  if curl -fsS http://localhost:8000/api/health >/dev/null 2>&1; then
    echo "app is up"
    break
  fi
  sleep 1
done

# Lets the SSE resilience spec drop the server connection for real.
export E2E_CONTAINER=finally-e2e

npx playwright test "$@"
