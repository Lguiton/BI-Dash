"""Email the dashboard report on a schedule.  Needs the backend running and SMTP set up in backend/.env.

    python scripts/send_report.py                 # PDF to everyone in BI_REPORT_TO
    python scripts/send_report.py --format xlsx --days 7   # Excel report of the last 7 days

Schedule it:
  Linux/WSL cron (every Monday 8am):   0 8 * * 1  cd /path/to/project && python scripts/send_report.py --days 7
  Windows Task Scheduler:               run  wsl python scripts/send_report.py --days 7   weekly
The backend must be running at that time (or start it first in the same task).
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta

API = os.environ.get("BI_API_URL", "http://localhost:8020")

ap = argparse.ArgumentParser()
ap.add_argument("--format", choices=["xlsx", "pdf"], default="pdf")
ap.add_argument("--days", type=int, default=0, help="only the last N days of data (0 = everything)")
a = ap.parse_args()

qs = ""
if a.days > 0:
    try:   # anchor on the newest day IN the data, not today, so a stale dataset still produces a report
        with urllib.request.urlopen(f"{API}/api/analytics/meta", timeout=10) as r:
            newest = date.fromisoformat(json.load(r)["max_date"])
        qs = f"?date_from={newest - timedelta(days=a.days - 1)}&date_to={newest}"
    except Exception as e:
        sys.exit(f"Couldn't read the data range from {API}: {e}")

req = urllib.request.Request(f"{API}/api/report/email{qs}", data=json.dumps({"format": a.format}).encode(),
                             headers={"Content-Type": "application/json"}, method="POST")
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        print("sent to", ", ".join(json.load(r)["sent_to"]))
except urllib.error.HTTPError as e:
    sys.exit(f"Failed ({e.code}): {json.load(e).get('detail', e.reason)}")
except OSError as e:
    sys.exit(f"Can't reach the backend at {API}: {e}")
