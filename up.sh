#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
export OLIVIA_PORT="${OLIVIA_PORT:-8001}"
docker compose --file docker/docker-compose.yml up -d --build --wait
printf '\n Olívia 15 está disponível em http://localhost:%s/\n' "$OLIVIA_PORT"
