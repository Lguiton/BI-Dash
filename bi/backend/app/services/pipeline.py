"""Monitor and run the medallion pipeline in data_engineering/ (bronze -> silver -> gold, DuckDB + Parquet).

Reads the lake's Parquet files with a throw-away in-memory DuckDB (never the dashboard's own database), so monitoring
can't lock or change your data. Running it calls medallion.run() exactly as `python medallion.py` does, and records a
history line so you can see runs over time.
"""
from __future__ import annotations

import hashlib
import importlib
import json
import sys
import threading
import time
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DE_DIR = ROOT / "data_engineering"
LAKE = DE_DIR / "lake"
SOURCES = {"clean": ROOT / "data_samples" / "operations_clean.csv", "messy": ROOT / "data_samples" / "operations_messy.csv"}
UPLOADED_EXPORT = DE_DIR / "landing" / "uploaded_export.csv"
HISTORY_MAX = 25
_run_lock = threading.Lock()


class PipelineError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _medallion():
    if not (DE_DIR / "medallion.py").exists():
        raise PipelineError("data_engineering/medallion.py wasn't found. Is the project folder complete?", 404)
    if str(DE_DIR) not in sys.path:
        sys.path.insert(0, str(DE_DIR))
    return importlib.import_module("medallion")


def _count(con, glob: str) -> int:
    try:
        return int(con.execute(f"SELECT count(*) FROM read_parquet('{glob}')").fetchone()[0])
    except Exception:
        return 0


def reconcile(lake: Path) -> dict:
    """Do the business-ready (gold) totals still equal the cleaned (silver) data they were built from?"""
    import duckdb
    silver, daily, ent = (lake / "silver" / "ops.parquet"), (lake / "gold" / "daily.parquet"), (lake / "gold" / "entity.parquet")
    if not (silver.exists() and daily.exists() and ent.exists()):
        return {"ok": False, "detail": "silver or gold files are missing", "rows": []}
    con = duckdb.connect()
    s_rev, s_cost, s_n = con.execute(f"SELECT coalesce(sum(revenue),0), coalesce(sum(operational_cost),0), count(*) FROM read_parquet('{silver.as_posix()}')").fetchone()
    d_rev, d_cost, d_n = con.execute(f"SELECT coalesce(sum(revenue),0), coalesce(sum(cost),0), coalesce(sum(records),0) FROM read_parquet('{daily.as_posix()}')").fetchone()
    e_rev = con.execute(f"SELECT coalesce(sum(revenue),0) FROM read_parquet('{ent.as_posix()}')").fetchone()[0]
    rows = []
    for name, a, b in (("Revenue: silver vs gold by day", s_rev, d_rev), ("Cost: silver vs gold by day", s_cost, d_cost),
                       ("Records: silver vs gold by day", s_n, d_n), ("Revenue: silver vs gold by entity", s_rev, e_rev)):
        a, b = float(a), float(b)
        rows.append({"name": name, "silver": round(a, 2), "gold": round(b, 2), "ok": abs(a - b) <= max(0.01, 1e-9 * abs(a))})
    bad = [r["name"] for r in rows if not r["ok"]]
    return {"ok": not bad, "detail": "gold totals equal silver totals" if not bad else "differences in: " + ", ".join(bad), "rows": rows}


def _last_published(lake: Path) -> dict | None:
    try:
        hist = json.loads((lake / "history.json").read_text())
    except Exception:
        return None
    for e in reversed(hist):
        if e.get("published", True) and not e.get("skipped") and e.get("silver_rows") is not None:
            return e
    return None


def silent_failure_checks(entry: dict, prev: dict | None) -> list[dict]:
    """A run can succeed and still be wrong. Compare this run with the last good one."""
    if not prev or entry.get("reset"):
        return []
    out = []
    ps, ns = prev.get("silver_rows") or 0, entry.get("silver_rows") or 0
    if ps > 0:
        out.append({"name": "Volume steady vs previous run", "ok": ns >= 0.5 * ps, "detail": f"silver {ns:,} rows now, {ps:,} last run"})
    pq, nq = prev.get("quarantined") or 0, entry.get("quarantined") or 0
    pshare = pq / max(pq + ps, 1)
    nshare = nq / max(nq + ns, 1)
    out.append({"name": "Quarantine has not jumped", "ok": nshare <= max(0.1, pshare * 3), "detail": f"{nshare:.1%} rejected now, {pshare:.1%} last run"})
    return out


def gate_checks(lake: Path, entry: dict | None = None, prev: dict | None = None) -> list[dict]:
    """Checks that must pass before a gated run publishes. Freshness is left out: old sample data is still valid data."""
    st = status(lake)
    keep = [c for c in st.get("checks", []) if c["name"] != "Freshness"]
    rec = reconcile(lake)
    return keep + [{"name": "Gold reconciles to silver", "ok": rec["ok"], "detail": rec["detail"]}] + silent_failure_checks(entry or {}, prev)


def status(lake: Path | None = None) -> dict:
    import duckdb
    lake = lake or LAKE
    if not (lake / "state.json").exists():
        return {"exists": False, "message": "The pipeline hasn't run yet. Press Run to build bronze, silver and gold.", "history": _history(lake)}
    state = json.loads((lake / "state.json").read_text())
    con = duckdb.connect()
    p = lambda *a: (lake.joinpath(*a)).as_posix()
    bronze_files = sorted((lake / "bronze").glob("*.parquet"))
    layers = [
        {"layer": "bronze", "label": "Raw, as received", "rows": _count(con, p("bronze", "*.parquet")) if bronze_files else 0, "files": len(bronze_files)},
        {"layer": "silver", "label": "Typed, validated, de-duplicated", "rows": _count(con, p("silver", "ops.parquet")), "files": 1},
        {"layer": "quarantine", "label": "Rejected rows, with a reason", "rows": _count(con, p("silver", "quarantine.parquet")), "files": 1},
        {"layer": "gold", "label": "Business-ready daily totals", "rows": _count(con, p("gold", "daily.parquet")), "files": 2},
    ]
    reasons = []
    if (lake / "silver" / "quarantine.parquet").exists():
        reasons = [{"reason": r, "rows": n} for r, n in con.execute(
            f"SELECT reason, count(*) FROM read_parquet('{p('silver', 'quarantine.parquet')}') GROUP BY 1 ORDER BY 2 DESC").fetchall()]
    newest = state.get("watermark")
    stale = (date.today() - date.fromisoformat(newest)).days if newest else None
    silver = layers[1]["rows"]
    bronze_unique = None
    if bronze_files:
        try:
            bronze_unique = int(con.execute(f"SELECT count(DISTINCT fact_id) FROM read_parquet('{p('bronze', '*.parquet')}')").fetchone()[0])
        except Exception:
            pass
    checks = [
        {"name": "Freshness", "ok": stale is not None and stale <= 2, "detail": f"newest day {newest}, {stale} days old" if newest else "no data"},
        {"name": "Silver has rows", "ok": silver > 0, "detail": f"{silver:,} rows"},
        {"name": "Rows accounted for", "ok": bronze_unique is None or silver + layers[2]["rows"] >= 0.9 * bronze_unique,
         "detail": f"{silver:,} silver + {layers[2]['rows']:,} quarantined from {bronze_unique:,} distinct raw ids" if bronze_unique else "n/a"},
        {"name": "Quarantine under 20%", "ok": silver == 0 or layers[2]["rows"] <= 0.2 * (silver + layers[2]["rows"]),
         "detail": f"{layers[2]['rows']:,} rejected"},
    ]
    rec = reconcile(lake) if silver else {"ok": True, "detail": "n/a", "rows": []}
    checks.append({"name": "Gold reconciles to silver", "ok": rec["ok"], "detail": rec["detail"]})
    return {"exists": True, "watermark": newest, "loads": state.get("loads", 0), "layers": layers, "quarantine_reasons": reasons,
            "checks": checks, "reconciliation": rec["rows"], "history": _history(lake)}


def _history(lake: Path) -> list[dict]:
    try:
        return json.loads((lake / "history.json").read_text())[-HISTORY_MAX:][::-1]
    except Exception:
        return []


def export_uploaded(dest: Path | None = None) -> tuple[Path, int]:
    """Write the dashboard's current data (whatever was imported) to a CSV in the layout the pipeline expects."""
    import csv
    from app.services.db import fetch_all, get_cursor
    dest = dest or UPLOADED_EXPORT
    with get_cursor() as cur:
        rows = fetch_all(cur, """
            SELECT f.fact_id, STRFTIME(f.record_date, '%Y-%m-%d') AS record_date, f.entity_id,
                   COALESCE(e.name, f.entity_id) AS entity_name, COALESCE(e.category, '') AS category,
                   f.revenue, f.operational_cost, f.units_processed, f.duration_minutes, f.status,
                   e.baseline_target
            FROM fact_operations f LEFT JOIN dim_entities e ON f.entity_id = e.entity_id ORDER BY f.record_date, f.fact_id""")
    if not rows:
        raise PipelineError("The dashboard has no data to send through the pipeline. Import a CSV first.", 400)
    dest.parent.mkdir(parents=True, exist_ok=True)
    cols = list(rows[0])
    with dest.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols)
        for r in rows:
            w.writerow(["" if r[c] is None else r[c] for c in cols])
    return dest, len(rows)


def run(source: str = "clean", reset: bool = False, lake: Path | None = None, gate: bool = False, only_if_new: bool = False) -> dict:
    """With gate=True the run happens in a staging copy and replaces the real lake only if every check passes."""
    lake = lake or LAKE
    if source not in SOURCES and source != "uploaded":
        raise PipelineError("source must be 'clean', 'messy' or 'uploaded'.")
    if source == "uploaded":
        path, _ = export_uploaded()
    else:
        path = SOURCES[source]
        if not path.exists():
            raise PipelineError(f"{path.name} wasn't found in data_samples/.", 404)
    sha = hashlib.sha1(path.read_bytes()).hexdigest()[:12]
    prev = _last_published(lake)
    if only_if_new and not reset and prev and prev.get("source_sha") == sha:
        return {"at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "source": source, "skipped": True, "source_sha": sha,
                "message": "No new data since the last run, so nothing was run."}
    if not _run_lock.acquire(blocking=False):
        raise PipelineError("A pipeline run is already in progress.", 409)
    try:
        import shutil
        m = _medallion()
        t0 = time.perf_counter()
        work = lake
        if gate:
            work = lake.with_name(lake.name + "_staging")
            shutil.rmtree(work, ignore_errors=True)
            if lake.exists() and not reset:
                shutil.copytree(lake, work)
        stats = m.run(path, work, reset=reset)
        entry = {"at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "source": source, "reset": reset,
                 "seconds": round(time.perf_counter() - t0, 2), "source_sha": sha, **{k: stats.get(k) for k in
                 ("bronze_rows", "silver_rows", "quarantined", "gold_rows", "watermark_before", "watermark_after")}}
        if gate:
            checks = gate_checks(work, entry, prev)
            failed = [f"{c['name']}: {c['detail']}" for c in checks if not c["ok"]]
            entry.update({"gate": True, "published": not failed, "blocked_reasons": failed})
            if failed:
                shutil.rmtree(work, ignore_errors=True)  # the real lake is untouched
            else:
                shutil.rmtree(lake, ignore_errors=True)
                work.rename(lake)
        hist = []
        try:
            hist = json.loads((lake / "history.json").read_text())
        except Exception:
            pass
        lake.mkdir(parents=True, exist_ok=True)
        (lake / "history.json").write_text(json.dumps((hist + [entry])[-HISTORY_MAX:], indent=1))
        return entry
    finally:
        _run_lock.release()
