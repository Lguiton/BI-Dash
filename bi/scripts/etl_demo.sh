#!/usr/bin/env bash
# Shell-scripting practice: a tiny end-to-end ETL pipeline, driven from the command line.
#
#   generate messy data  ->  clean it with Python  ->  upload to the dashboard API  ->  verify
#
# Needs: the backend running on port 8020 (uvicorn app.main:app --port 8020), plus python and curl.
# Run from the project root:   bash scripts/etl_demo.sh
# WARNING: it loads data in REPLACE mode, which wipes whatever is currently in the dashboard.
set -euo pipefail

API="${BI_API_URL:-http://localhost:8020}"
PY="${PYTHON:-python3}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

step() { printf '\n\033[1m== %s\033[0m\n' "$1"; }
fail() { printf 'ERROR: %s\n' "$1" >&2; exit 1; }

step "0. Is the API up?"
curl -fsS "$API/health" >/dev/null 2>&1 || fail "API not reachable at $API. Start the backend first."
echo "yes: $API"

if [[ "${1:-}" != "--yes" ]]; then
  read -r -p "This REPLACES all data in the dashboard. Continue? [y/N] " ans
  [[ "$ans" =~ ^[Yy]$ ]] || { echo "Cancelled."; exit 0; }
fi

step "1. Extract: generate a messy export (this stands in for a real source system)"
"$PY" scripts/generate_sample_data.py --messy

step "2. Transform: clean it (python_practice/solutions/03_clean_messy_data_solution.py)"
(cd python_practice && "$PY" solutions/03_clean_messy_data_solution.py)
CLEAN="python_practice/_out/operations_cleaned.csv"
[[ -s "$CLEAN" ]] || fail "cleaned file missing"
echo "cleaned rows: $(( $(wc -l < "$CLEAN") - 1 ))"

step "3. Load: upload to the dashboard (replace mode)"
curl -fsS -X POST "$API/api/ingest/csv?mode=replace" -F "file=@${CLEAN};type=text/csv"
echo

step "4. Verify: compare the API's numbers with the file we just loaded"
API_ROWS=$(curl -fsS "$API/api/analytics/summary" | "$PY" -c "import sys,json; print(json.load(sys.stdin)['record_count'])")
FILE_ROWS=$(( $(wc -l < "$CLEAN") - 1 ))
echo "rows in API: $API_ROWS | rows in file: $FILE_ROWS"
[[ "$API_ROWS" == "$FILE_ROWS" ]] && echo "OK: counts match" || fail "row counts differ"

echo
echo "Done. Open the dashboard, then try the SQL Lab exercises on this bigger dataset."
echo "Ideas: add 'set -x' to watch each command; pipe the summary through 'python -m json.tool'; schedule this with cron."
