#!/usr/bin/env bash
# Start backend (FastAPI) and frontend (Vite) dev servers together.
# Visit http://localhost:5180 in your browser.

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cleanup() {
  echo "Shutting down…"
  kill $BACK_PID $FRONT_PID 2>/dev/null || true
}
trap cleanup INT TERM

./venv/bin/python -m uvicorn backend.main:app --reload --port 8765 &
BACK_PID=$!

(cd frontend && ./node_modules/.bin/vite) &
FRONT_PID=$!

echo
echo "Backend  → http://localhost:8765  (pid $BACK_PID)"
echo "Frontend → http://localhost:5180  (pid $FRONT_PID)"
echo "API docs → http://localhost:8765/docs"
echo

wait
