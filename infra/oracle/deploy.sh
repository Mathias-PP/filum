#!/usr/bin/env bash
# Déploiement sur la VM Oracle : à lancer depuis ~/filum/infra/oracle.
# Usage : ./deploy.sh
set -euo pipefail

cd "$(dirname "$0")"

git pull --ff-only
docker compose build backend
docker compose up -d
docker image prune -f

echo "--- Attente du healthcheck backend..."
for i in $(seq 1 30); do
  if curl -fsS http://localhost:80/health >/dev/null 2>&1 || docker exec philum-backend curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
    echo "OK — backend up."
    exit 0
  fi
  sleep 2
done
echo "ÉCHEC — backend injoignable après 60s. Logs :"
docker logs --tail 50 philum-backend
exit 1
