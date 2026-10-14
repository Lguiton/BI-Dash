"""Big data practice sized to THIS computer.

Real big data (a cluster, Hadoop, Spark across many machines) can't run on one PC, and you don't need it to learn the ideas.
This lab generates millions of made-up rows with DuckDB, which streams from disk instead of loading everything into memory, then
compares row files (CSV) with columnar files (Parquet) and with Parquet split into folders by month (partitioning).

Safety: row count is capped by free disk space, DuckDB gets a memory limit and 2 threads, everything is written under one folder
that "Clean up" deletes, and only one job runs at a time.
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

import duckdb

from app.config import db_path
from app.services.datasets import DataError

MAX_ROWS = 20_000_000
BYTES_PER_ROW = 170          # CSV (~95) + Parquet (~30) + partitioned Parquet (~35), rounded up
DISK_SAFETY = 2.0            # keep this many times the estimate free
PRESETS = [100_000, 1_000_000, 5_000_000, 10_000_000]
MEMORY_LIMIT = "1GB"
THREADS = 2
REGIONS = ["West", "East", "North", "South", "Central"]
PRODUCTS = ["Widget", "Gadget", "Service", "Subscription", "Add-on", "Bundle"]

_lock = threading.Lock()
_job: dict = {"status": "idle", "step": "", "progress": 0, "error": None, "result": None}


def folder() -> Path:
    return db_path().parent / "bigdata_lab"


def _machine() -> dict:
    ram = None
    try:
        for line in Path("/proc/meminfo").read_text().splitlines():
            if line.startswith("MemTotal:"):
                ram = int(line.split()[1]) * 1024
    except OSError:
        pass
    base = folder().parent
    base.mkdir(parents=True, exist_ok=True)
    du = shutil.disk_usage(base)
    return {"cpus": os.cpu_count(), "ram_bytes": ram, "disk_free_bytes": du.free, "disk_total_bytes": du.total}


def max_rows_for_disk(free: int) -> int:
    return int(max(0, min(MAX_ROWS, free / (BYTES_PER_ROW * DISK_SAFETY))))


def _size(p: Path) -> int:
    if p.is_file():
        return p.stat().st_size
    return sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) if p.exists() else 0


def _files() -> dict:
    f = folder()
    parts = f / "parts"
    return {"parquet": f / "orders.parquet", "csv": f / "orders.csv", "parts": parts}


def state() -> dict:
    m = _machine()
    cap = max_rows_for_disk(m["disk_free_bytes"])
    fs = _files()
    exists = fs["parquet"].exists() and fs["csv"].exists() and fs["parts"].exists()
    existing = None
    if exists:
        c = duckdb.connect()
        try:
            n = c.execute(f"SELECT COUNT(*) FROM read_parquet('{fs['parquet']}')").fetchone()[0]
        finally:
            c.close()
        existing = {"rows": int(n), "csv_bytes": _size(fs["csv"]), "parquet_bytes": _size(fs["parquet"]), "partitioned_bytes": _size(fs["parts"]),
                    "partition_files": len(list(fs["parts"].rglob("*.parquet"))), "partitions": len([d for d in fs["parts"].iterdir() if d.is_dir()])}
    return {"machine": m, "max_rows": cap, "hard_cap": MAX_ROWS,
            "presets": [{"rows": r, "estimate_bytes": r * BYTES_PER_ROW, "ok": r <= cap} for r in PRESETS], "memory_limit": MEMORY_LIMIT, "threads": THREADS,
            "dataset": existing, "job": dict(_job),
            "honest_note": ("This computer can practice the ideas of big data (data bigger than comfortable, columnar files, partitions, sampling, parallel scans) at millions of rows. "
                            "A real cluster (Hadoop, Spark on many machines) only pays off when data no longer fits one machine's disk or time budget, typically hundreds of GB and up.")}


def _con() -> duckdb.DuckDBPyConnection:
    c = duckdb.connect()
    c.execute(f"SET memory_limit='{MEMORY_LIMIT}'")
    c.execute(f"SET threads={THREADS}")
    tmp = folder() / "tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    c.execute(f"SET temp_directory='{tmp}'")
    return c


def _set(step: str, progress: int) -> None:
    _job["step"], _job["progress"] = step, progress


def _run(target, *args) -> None:
    def wrapper():
        try:
            _job["result"] = target(*args)
            _job["status"] = "done"
        except Exception as e:  # report to the page instead of dying silently in a thread
            _job["status"], _job["error"] = "error", f"{e.__class__.__name__}: {e}"[:300]
        finally:
            _set("", 100 if _job["status"] == "done" else _job["progress"])

    with _lock:
        if _job["status"] == "running":
            raise DataError("A big-data job is already running. Wait for it to finish.", 409)
        _job.update(status="running", step="starting", progress=0, error=None, result=None)
    threading.Thread(target=wrapper, daemon=True).start()


def start_generate(rows: int) -> dict:
    if rows < 10_000:
        raise DataError("Use at least 10,000 rows (below that there is nothing 'big' to see).")
    m = _machine()
    cap = max_rows_for_disk(m["disk_free_bytes"])
    if rows > MAX_ROWS:
        raise DataError(f"The limit is {MAX_ROWS:,} rows.")
    if rows > cap:
        raise DataError(f"{rows:,} rows needs about {rows * BYTES_PER_ROW / 1e9:.1f} GB and I keep {DISK_SAFETY:g}x that free. This computer has {m['disk_free_bytes'] / 1e9:.1f} GB free, "
                        f"so the most I'll make is {cap:,} rows. Free up disk space or pick fewer rows.")
    _run(_generate, rows)
    return {"started": True, "rows": rows}


def _generate(rows: int) -> dict:
    fs = _files()
    shutil.rmtree(folder(), ignore_errors=True)
    folder().mkdir(parents=True, exist_ok=True)
    c = _con()
    t0 = time.perf_counter()
    try:
        _set("making rows (Parquet)", 5)
        c.execute("SELECT setseed(0.42)")
        c.execute(f"""
            COPY (SELECT i AS order_id,
                         DATE '2024-01-01' + CAST(floor(random() * 731) AS INTEGER) AS order_date,
                         'C' || CAST(1 + floor(random() * 50000) AS INTEGER) AS customer_id,
                         ({REGIONS!r})[1 + CAST(floor(random() * {len(REGIONS)}) AS INTEGER)] AS region,
                         ({PRODUCTS!r})[1 + CAST(floor(random() * {len(PRODUCTS)}) AS INTEGER)] AS product,
                         1 + CAST(floor(random() * 9) AS INTEGER) AS qty,
                         round(5 + random() * 495, 2) AS price
                  FROM range(1, {rows + 1}) r(i))
            TO '{fs['parquet']}' (FORMAT PARQUET, COMPRESSION ZSTD)""")
        _set("writing the same rows as CSV", 40)
        c.execute(f"COPY (SELECT * FROM read_parquet('{fs['parquet']}')) TO '{fs['csv']}' (FORMAT CSV, HEADER)")
        _set("splitting Parquet into one folder per month", 70)
        c.execute(f"""COPY (SELECT *, strftime(order_date, '%Y-%m') AS month FROM read_parquet('{fs['parquet']}'))
                      TO '{fs['parts']}' (FORMAT PARQUET, COMPRESSION ZSTD, PARTITION_BY (month))""")
    finally:
        c.close()
        shutil.rmtree(folder() / "tmp", ignore_errors=True)
    return {"rows": rows, "seconds": round(time.perf_counter() - t0, 1)}


QUERIES = [
    ("Total by region (scan 3 columns)", "SELECT region, SUM(qty * price) AS revenue, COUNT(*) AS n FROM {t} GROUP BY region ORDER BY region"),
    ("One month only (a filter)", "SELECT COUNT(*) AS n, ROUND(SUM(qty * price), 2) AS revenue FROM {t} WHERE order_date >= DATE '2024-03-01' AND order_date < DATE '2024-04-01'"),
    ("Distinct customers", "SELECT COUNT(DISTINCT customer_id) AS customers FROM {t}"),
    ("Average price (1 column)", "SELECT ROUND(AVG(price), 4) AS avg_price FROM {t}"),
]


def start_benchmark() -> dict:
    if not _files()["parquet"].exists():
        raise DataError("Make the data first.", 400)
    _run(_benchmark)
    return {"started": True}


def _time(c, sql: str) -> tuple[float, list]:
    best, res = None, None
    for _ in range(2):  # run twice: the first read warms the disk cache, the second is the steadier number
        t = time.perf_counter()
        res = c.execute(sql).fetchall()
        dt = time.perf_counter() - t
        best = dt if best is None else min(best, dt)
    return best, res


def _benchmark() -> dict:
    fs = _files()
    sources = {"csv": f"read_csv('{fs['csv']}', header=true, auto_detect=true)", "parquet": f"read_parquet('{fs['parquet']}')",
               "partitioned": f"read_parquet('{fs['parts']}/*/*.parquet', hive_partitioning=true)"}
    c = _con()
    rows = int(c.execute(f"SELECT COUNT(*) FROM read_parquet('{fs['parquet']}')").fetchone()[0])
    out, agree = [], True
    try:
        for qi, (name, tmpl) in enumerate(QUERIES):
            row = {"query": name, "ms": {}, "result": None}
            ref = None
            for k, src in sources.items():
                sql = tmpl.format(t=src)
                if k == "partitioned" and "order_date >=" in sql:
                    sql = tmpl.format(t=src).replace("WHERE order_date", "WHERE month = '2024-03' AND order_date")  # lets DuckDB skip other months' folders
                _set(f"timing: {name} on {k}", 10 + int(80 * (qi * 3 + list(sources).index(k)) / (len(QUERIES) * 3)))
                dt, res = _time(c, sql)
                row["ms"][k] = round(dt * 1000, 1)
                norm = [tuple(round(v, 2) if isinstance(v, float) else v for v in r) for r in res]
                if ref is None:
                    ref, row["result"] = norm, [list(r) for r in norm[:6]]
                elif [tuple(round(v, 1) if isinstance(v, float) else v for v in r) for r in norm] != [tuple(round(v, 1) if isinstance(v, float) else v for v in r) for r in ref]:
                    agree = False
            row["speedup_parquet"] = round(row["ms"]["csv"] / row["ms"]["parquet"], 1) if row["ms"]["parquet"] else None
            out.append(row)
        # approximate answers: a 1% sample is far cheaper and often close enough
        _set("timing: a 1% sample", 92)
        t = time.perf_counter()
        exact = c.execute(f"SELECT AVG(qty * price) FROM read_parquet('{fs['parquet']}')").fetchone()[0]
        t_exact = time.perf_counter() - t
        t = time.perf_counter()
        approx = c.execute(f"SELECT AVG(qty * price) FROM read_parquet('{fs['parquet']}') USING SAMPLE 1 PERCENT (system, 42)").fetchone()[0]
        if approx is None:  # small files have too few row groups for a block sample to pick any; sample row by row instead
            approx = c.execute(f"SELECT AVG(qty * price) FROM read_parquet('{fs['parquet']}') USING SAMPLE 1 PERCENT (bernoulli, 42)").fetchone()[0]
        t_approx = time.perf_counter() - t
    finally:
        c.close()
    files = state()["dataset"]
    return {"rows": rows, "queries": out, "all_formats_agree": agree,
            "sample": {"exact": round(float(exact), 4), "approx": round(float(approx), 4), "error_pct": round(abs(approx - exact) / exact * 100, 3),
                       "exact_ms": round(t_exact * 1000, 1), "sample_ms": round(t_approx * 1000, 1)},
            "sizes": files, "compression_vs_csv": round(files["csv_bytes"] / files["parquet_bytes"], 1) if files and files["parquet_bytes"] else None,
            "partition_note": f"Partitioned into {files['partitions']} month folders; the one-month query read one of them." if files else ""}


def job() -> dict:
    return dict(_job)


def cleanup() -> dict:
    if _job["status"] == "running":
        raise DataError("A job is running; wait for it to finish.", 409)
    freed = _size(folder())
    shutil.rmtree(folder(), ignore_errors=True)
    _job.update(status="idle", step="", progress=0, error=None, result=None)
    return {"freed_bytes": freed}
