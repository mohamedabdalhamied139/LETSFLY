#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv 2>/dev/null || true
. .venv/bin/activate
python -m pip install -r server/requirements.txt
export PYTHONPATH="$PWD"
if [[ "${LETSFLY_ENV:-development}" == "production" || "${LETSFLY_ENV:-development}" == "prod" ]]; then
  exec python server/run_server.py
else
  exec python server/run_server.py
fi
