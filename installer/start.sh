#!/usr/bin/env bash
# Starts the backend (8020) and the dashboard (3012). Press Ctrl+C to stop both.
cd "$(dirname "$0")/.."
. .venv/bin/activate
(cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8020) &
BE=$!
trap 'kill $BE 2>/dev/null' EXIT INT TERM
cd frontend && npx next start -p 3012
