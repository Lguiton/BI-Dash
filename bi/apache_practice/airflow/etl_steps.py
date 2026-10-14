"""The ETL logic behind the Airflow DAG, written as plain Python so you can run and test it
WITHOUT Airflow:   python apache_practice/airflow/etl_steps.py

Airflow's job is orchestration (order, schedule, retries, monitoring), not data crunching.
Keeping the work in ordinary functions and having the DAG just call them is the standard pattern.
Standard library only, so the Airflow workers need no extra packages.
"""
import csv
import io
import json
import os
import urllib.request
import uuid
from pathlib import Path

API = os.environ.get("BI_API_URL", "http://localhost:8020")
WORK = Path(os.environ.get("BI_WORK_DIR", Path(__file__).resolve().parent / "_work"))

REQUIRED = ["fact_id", "record_date", "entity_id", "revenue", "operational_cost"]


def extract(run_id: str = "manual") -> str:
    """E: pull the current flat table from the dashboard API (stand-in for a source system)."""
    WORK.mkdir(parents=True, exist_ok=True)
    path = WORK / f"raw_{run_id}.csv"
    with urllib.request.urlopen(f"{API}/api/export/operations?format=csv", timeout=30) as r:
        path.write_bytes(r.read())
    return str(path)


def transform(raw_path: str, run_id: str = "manual") -> dict:
    """T: drop rows missing required fields, drop duplicate fact_ids, and write a clean CSV."""
    out = WORK / f"clean_{run_id}.csv"
    seen, kept, dropped = set(), [], {"missing_required": 0, "duplicate": 0}
    with open(raw_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        for row in reader:
            if any(not (row.get(k) or "").strip() for k in REQUIRED):
                dropped["missing_required"] += 1
            elif row["fact_id"] in seen:
                dropped["duplicate"] += 1
            else:
                seen.add(row["fact_id"])
                kept.append(row)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(kept)
    return {"path": str(out), "rows_in": len(kept) + sum(dropped.values()), "rows_out": len(kept), "dropped": dropped}


def validate(stats: dict) -> dict:
    """A data-quality gate: raise (so Airflow marks the task failed and stops downstream tasks)."""
    if stats["rows_out"] == 0:
        raise ValueError("Quality gate failed: no rows survived cleaning.")
    lost = 1 - stats["rows_out"] / max(stats["rows_in"], 1)
    if lost > 0.05:
        raise ValueError(f"Quality gate failed: {lost:.1%} of rows were dropped (limit 5%).")
    return stats


def load(clean_path: str, mode: str = "append") -> dict:
    """L: POST the clean CSV to the ingest endpoint (multipart, built by hand to stay stdlib-only)."""
    boundary = uuid.uuid4().hex
    data = Path(clean_path).read_bytes()
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"clean.csv\"\r\n"
            f"Content-Type: text/csv\r\n\r\n").encode() + data + f"\r\n--{boundary}--\r\n".encode()
    req = urllib.request.Request(f"{API}/api/ingest/csv?mode={mode}", data=body, method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def verify(expected_rows: int) -> dict:
    """Check the dashboard now holds at least the rows we just loaded."""
    with urllib.request.urlopen(f"{API}/api/analytics/summary", timeout=30) as r:
        summary = json.loads(r.read())
    if summary["record_count"] < expected_rows:
        raise ValueError(f"Expected at least {expected_rows} records, API reports {summary['record_count']}.")
    return {"record_count": summary["record_count"], "net_margin_pct": summary["net_margin_pct"]}


if __name__ == "__main__":
    raw = extract("local")
    stats = validate(transform(raw, "local"))
    print("transform:", stats)
    print("load:", load(stats["path"], mode="append"))
    print("verify:", verify(stats["rows_out"]))
