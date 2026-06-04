#!/usr/bin/env bash
# Build production frontend bundle and copy to backend/static for single-server serving.
# After this, run: ./venv/bin/python -m uvicorn backend.main:app --port 8765
# Then visit: http://localhost:8765

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "→ Building frontend…"
(cd frontend && ./node_modules/.bin/vite build)

echo "→ Copying to backend/static…"
rm -rf backend/static
mkdir -p backend/static
cp -R frontend/dist/. backend/static/

echo
echo "✓ Build complete. Run:"
echo "    ./venv/bin/python -m uvicorn backend.main:app --port 8765"
echo "  then open http://localhost:8765"
