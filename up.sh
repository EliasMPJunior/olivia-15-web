#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

case "${1:-}" in
  '') compose_file="docker/docker-compose.yml" ;;
  --prod) compose_file="docker/docker-compose.prod.yml" ;;
  -h|--help)
    printf 'Uso: %s [--prod]\n' "$0"
    exit 0
    ;;
  *)
    printf 'Argumento desconhecido: %s\nUso: %s [--prod]\n' "$1" "$0" >&2
    exit 2
    ;;
esac
if [ "$#" -gt 1 ]; then
  printf 'Uso: %s [--prod]\n' "$0" >&2
  exit 2
fi

export OLIVIA_PORT="${OLIVIA_PORT:-8001}"
if [ -f .env ]; then
  docker compose --env-file .env --file "$compose_file" up -d --build --wait
else
  docker compose --file "$compose_file" up -d --build --wait
fi
printf '\n Olívia 15 iniciada com %s (porta local %s).\n' "$compose_file" "$OLIVIA_PORT"
