#!/bin/sh
# Entrypoint for the backend image. `api` migrates the database then serves; `worker` runs the scheduler.
set -e

case "${1:-api}" in
  api)
    echo "[entrypoint] applying database migrations"
    alembic upgrade head
    echo "[entrypoint] starting API"
    exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
    ;;
  worker)
    echo "[entrypoint] starting worker"
    exec python -m app.worker
    ;;
  *)
    exec "$@"
    ;;
esac
