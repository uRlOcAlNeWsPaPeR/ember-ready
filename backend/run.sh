#!/usr/bin/env bash
# One-command local setup + run.
set -e
cd "$(dirname "$0")"

if [ ! -d venv ]; then
  python3 -m venv venv
fi

source venv/bin/activate
pip install -q -r requirements-dev.txt

echo "Starting EmberReady at http://localhost:8000 ..."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
