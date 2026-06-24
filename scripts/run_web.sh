#!/usr/bin/env bash
# Lance la plateforme web Zéphyr (FastAPI) en local.
#   ./scripts/run_web.sh            # http://127.0.0.1:8000
#   PORT=9000 ./scripts/run_web.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
# Installe les extras nécessaires (web + CAO + viz) au premier lancement.
uv sync --extra app --extra cao --extra viz --extra climate --extra pdf

echo "→ Zéphyr sur http://127.0.0.1:${PORT}  (Ctrl+C pour arrêter)"
exec uv run --extra app --extra cao --extra viz --extra climate --extra pdf \
  uvicorn app.web:app --host 127.0.0.1 --port "${PORT}" --reload
