#!/usr/bin/env bash
# Launch the PEL Foundry demo.  Opens on http://127.0.0.1:5050
set -e
cd "$(dirname "$0")"

PY=python3
if ! $PY -c "import flask, openpyxl, pypdf, docx" 2>/dev/null; then
  echo "Installing dependencies…"
  $PY -m pip install --quiet -r requirements.txt
fi

# The LLM backend is read from .env (MAGICA_API_KEY, or ANTHROPIC_API_KEY).
# Without a key the demo still runs structured-file ingestion via the offline matcher.
echo "Starting PEL Foundry demo on http://127.0.0.1:5050  (Ctrl-C to stop)"
exec $PY backend/app.py
