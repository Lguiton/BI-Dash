#!/usr/bin/env bash
# One-time setup on Mac / Linux / WSL. Needs Python 3.11+ and Node 20+ already installed.
set -e
cd "$(dirname "$0")/.."
command -v python3 >/dev/null || { echo "Python 3.11+ is required (https://www.python.org/downloads/)."; exit 1; }
command -v node >/dev/null || { echo "Node 20+ is required (https://nodejs.org/)."; exit 1; }
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)' || { echo "Python 3.11 or newer is required."; exit 1; }
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q --upgrade pip
pip install -r backend/requirements.txt
[ -f backend/.env ] || { [ -f backend/.env.example ] && cp backend/.env.example backend/.env && echo "Created backend/.env (add AI keys there if you want them; leave blank otherwise)."; }
cd frontend
npm install
npm run build
echo
echo "Done. Start it with: installer/start.sh   then open http://localhost:3012"
