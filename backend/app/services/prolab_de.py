"""Data engineering depth: streaming and batch sizing, DAG validation, contracts, anomaly checks, warehouse cost, small files."""
from __future__ import annotations

import csv
import io
import math
import re
import statistics

from app.services.prolab import ProError, lab, lines, num, r, ref, tool, txt

T = "engineering"
lab(T, "Data engineering depth: streams, Spark, DAGs, contracts, anomaly checks, cost and lakehouse")


def kafka(a):
    mb_s, size_kb, rep, days = num(a, "events_per_s", lo=0, strict=True), num(a, "event_kb", lo=0, strict=True), int(num(a, "replication", lo=1)), num(a, "retention_days", lo=0, strict=True)
    cons, per_part = int(num(a, "consumers_in_group", lo=1)), num(a, "partition_mb_s", lo=0.1)
    mbps = mb_s * size_kb / 1024
    parts = max(math.ceil(mbps / per_part), cons)
    stor = mbps * 86400 * days * rep / 1024
    return {"ingest_mb_per_s": r(mbps, 2), "partitions_suggested": parts, "storage_gb_with_replication": r(stor, 1), "network_in_mb_per_s_incl_replicas": r(mbps * rep, 2),
            "tips": ["Partitions set the maximum parallelism of one consumer group: keep at least as many partitions as consumers you may need.", "More partitions mean more open files and slower recovery: do not overshoot.", "Choose the key so related events share a partition (order is only kept inside one partition).", "Plan 30 to 50% headroom on disk."]}


tool(T, "kafka_sizing", "Kafka partitions and storage", "Throughput, partitions and disk.", [("events_per_s", "Events per second", 20000), ("event_kb", "Average event size (KB)", 1.5), ("replication", "Replication factor", 3), ("retention_days", "Retention (days)", 7), ("consumers_in_group", "Consumers in the group", 6), ("partition_mb_s", "Safe MB per second per partition", 10)], kafka)


def spark(a):
    gb, tgt, cores, skew = num(a, "data_gb", lo=0, strict=True), num(a, "target_partition_mb", lo=16), int(num(a, "total_cores", lo=1)), num(a, "largest_key_share_pct", lo=0, hi=100) / 100
    parts = max(int(math.ceil(gb * 1024 / tgt)), 1)
    waves = math.ceil(parts / cores)
    big = gb * skew
    return {"partitions": parts, "task_waves": waves, "ideal_multiple_of_cores": math.ceil(parts / cores) * cores, "largest_key_gb": r(big, 2), "skew_risk": "High: one task will run far longer than the rest." if big * 1024 > tgt * 4 else "Low.",
            "tips": ["Aim for 100 to 200 MB per partition after the shuffle.", "Skew: salt the hot key, broadcast the small side of a join, or enable adaptive query execution.", "Too many tiny tasks waste time on scheduling; too few leave cores idle.", "Avoid collect() on big data and Python UDFs where a built-in function exists."]}


tool(T, "spark_partitions", "Spark partitions and skew", "Partition count and skew risk.", [("data_gb", "Data after read/shuffle (GB)", 500), ("target_partition_mb", "Target partition size (MB)", 128), ("total_cores", "Executor cores", 200), ("largest_key_share_pct", "Largest key share of rows (%)", 3)], spark)


def dag(a):
    rows = lines(a, "tasks", "the tasks")
    d, pred = {}, {}
    for p in rows:
        d[p[0]] = float(p[1]) if len(p) > 1 and p[1] else 1.0
        pred[p[0]] = p[2].split() if len(p) > 2 and p[2] else []
    for k, ps in pred.items():
        for x in ps:
            if x not in d:
                raise ProError(f"{k} depends on {x}, which is not a task.")
    indeg = {k: len(v) for k, v in pred.items()}
    succ = {k: [j for j in d if k in pred[j]] for k in d}
    level, order, q = {}, [], [k for k, v in indeg.items() if v == 0]
    for k in q:
        level[k] = 0
    while q:
        k = q.pop(0)
        order.append(k)
        for j in succ[k]:
            indeg[j] -= 1
            level[j] = max(level.get(j, 0), level[k] + 1)
            if indeg[j] == 0:
                q.append(j)
    if len(order) != len(d):
        stuck = sorted(set(d) - set(order))
        raise ProError("The tasks form a cycle among: " + ", ".join(stuck) + ".")
    fin = {}
    for k in order:
        fin[k] = max([fin[x] for x in pred[k]], default=0) + d[k]
    end = max(fin.values())
    path, cur = [], max(fin, key=fin.get)
    while cur:
        path.append(cur)
        ps = pred[cur]
        cur = max(ps, key=lambda x: fin[x]) if ps else None
    levels: dict[int, list[str]] = {}
    for k in order:
        levels.setdefault(level[k], []).append(k)
    orphans = [k for k in d if not pred[k] and not succ[k]]
    return {"valid": True, "run_order": order, "parallel_levels": [{"level": i, "tasks": v} for i, v in sorted(levels.items())], "critical_path": " > ".join(reversed(path)), "shortest_possible_runtime": r(end, 2), "orphan_tasks": orphans or ["none"],
            "tips": ["Make every task safe to rerun (idempotent) and write outputs atomically.", "Set retries with backoff, timeouts and an alert on failure and on lateness.", "Pass dates as parameters, not 'now', so a backfill reproduces history."]}


tool(T, "dag_check", "Pipeline DAG validator", "Cycles, run order, parallel levels and critical path.", [("tasks", "Lines of: task, minutes, depends on (space separated)", "extract_orders,10\nextract_customers,5\nclean_orders,8,extract_orders\njoin,12,clean_orders extract_customers\nquality_checks,3,join\npublish,2,quality_checks", "area")], dag)


def contract(a):
    spec = lines(a, "contract", "the contract")
    raw = txt(a, "sample", "sample CSV", limit=200000)
    rd = csv.DictReader(io.StringIO(raw))
    cols = rd.fieldnames or []
    rows = list(rd)
    if not rows:
        raise ProError("The sample has no data rows.")
    issues = []
    for p in spec:
        if len(p) < 2:
            raise ProError("Each contract line: column, type (int, float, date, text, bool), required?, allowed values.")
        c, ty = p[0], p[1].lower()
        req = len(p) > 2 and p[2].lower() in ("required", "yes", "y", "true", "not null")
        allowed = set(p[3].split("|")) if len(p) > 3 and p[3] else None
        if c not in cols:
            issues.append(f"Column {c} is missing.")
            continue
        bad = nulls = out_of = 0
        for row in rows:
            v = (row.get(c) or "").strip()
            if v == "":
                nulls += 1
                continue
            try:
                if ty == "int":
                    int(v)
                elif ty == "float":
                    float(v)
                elif ty == "date":
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                        raise ValueError
                elif ty == "bool":
                    if v.lower() not in ("true", "false", "0", "1", "yes", "no"):
                        raise ValueError
            except ValueError:
                bad += 1
            if allowed and v not in allowed:
                out_of += 1
        if bad:
            issues.append(f"{c}: {bad} value(s) are not {ty}.")
        if req and nulls:
            issues.append(f"{c}: {nulls} blank value(s) but it is required.")
        if out_of:
            issues.append(f"{c}: {out_of} value(s) outside the allowed list.")
    extra = [c for c in cols if c not in {p[0] for p in spec}]
    if extra:
        issues.append("Columns not in the contract: " + ", ".join(extra) + " (add them or stop sending them).")
    return {"rows_checked": len(rows), "passes": not issues, "issues": issues or ["The sample matches the contract."], "tips": ["Agree the contract with the producer and version it.", "Run this check at ingestion and stop the load on a failure.", "Breaking changes (rename, type change, removal) need notice and a new version."]}


tool(T, "contract_check", "Data contract check", "Check a CSV sample against agreed columns and types.", [("contract", "Lines of: column, type, required, allowed values (a|b)", "id,int,required\namount,float,required\nstatus,text,required,paid|open|void\nday,date,required", "area"), ("sample", "Paste CSV with a header", "id,amount,status,day\n1,10.5,paid,2026-01-02\n2,,open,2026-01-03\n3,7,late,01/04/2026", "area")], contract)


def anomaly(a):
    xs = [float(v) for v in txt(a, "series", "the series").replace("\n", ",").split(",") if v.strip()]
    if len(xs) < 6:
        raise ProError("Give at least 6 values (for example daily row counts).")
    last, hist = xs[-1], xs[:-1]
    med = statistics.median(hist)
    mad = statistics.median(abs(x - med) for x in hist) or 1e-9
    rz = 0.6745 * (last - med) / mad
    mean, sd = statistics.mean(hist), statistics.pstdev(hist) or 1e-9
    z = (last - mean) / sd
    flagged = [i + 1 for i, x in enumerate(xs[:-1]) if abs(0.6745 * (x - med) / mad) > 3.5]
    return {"latest": last, "median_before": r(med, 2), "z_score": r(z, 2), "robust_z_score": r(rz, 2), "latest_is_anomaly": abs(rz) > 3.5, "earlier_outliers_at_positions": flagged or ["none"], "change_pct_vs_median": r(100 * (last - med) / med, 1) if med else None,
            "verdict": "Investigate: the latest value is far outside normal." if abs(rz) > 3.5 else "Within normal variation.", "how": "The robust score uses the median and median absolute deviation, so one earlier spike does not hide the next. Over 3.5 is a common flag. Weekly patterns: compare to the same weekday."}


tool(T, "volume_anomaly", "Freshness and volume anomaly", "Is today's row count unusual?", [("series", "Daily counts, oldest first (comma)", "1020,990,1005,1010,985,1000,1015,430", "area")], anomaly)


def wh(a):
    tb, scan_pct, q, price = num(a, "table_gb", lo=0, strict=True), num(a, "scan_pct", lo=0, hi=100) / 100, num(a, "queries_per_day", lo=0), num(a, "price_per_tb", lo=0)
    store = num(a, "storage_price_per_gb_month", lo=0)
    scanned = tb / 1024 * scan_pct
    daily = scanned * q * price
    return {"tb_scanned_per_query": r(scanned, 4), "query_cost_per_month": r(daily * 30, 2), "storage_cost_per_month": r(tb * store, 2), "total_per_month": r(daily * 30 + tb * store, 2), "if_partitioned_to_5pct": r(tb / 1024 * 0.05 * q * price * 30 + tb * store, 2),
            "tips": ["Select only the columns you need: columnar stores read by column.", "Partition and cluster on the columns you filter by.", "Materialize repeated heavy queries; set cost alerts and per-query limits.", "Prices differ by provider and model: use your own rate."]}


tool(T, "warehouse_cost", "Warehouse scan cost", "Cost of scanning versus storing data.", [("table_gb", "Table size (GB)", 800), ("scan_pct", "Share of the table each query scans (%)", 60), ("queries_per_day", "Queries per day", 300), ("price_per_tb", "Scan price (per TB)", 5), ("storage_price_per_gb_month", "Storage price (per GB-month)", 0.02)], wh)


def small(a):
    n, mb, tgt = num(a, "files", lo=1), num(a, "avg_file_mb", lo=0.001), num(a, "target_file_mb", lo=16)
    total = n * mb
    after = max(1, math.ceil(total / tgt))
    return {"total_gb": r(total / 1024, 2), "files_after_compaction": after, "reduction_x": r(n / after, 1), "list_calls_saved_pct": r(100 * (1 - after / n), 1),
            "tips": ["Thousands of tiny files slow every query: opening a file costs more than reading a few MB.", "Compact on a schedule (OPTIMIZE or rewrite_data_files) and write bigger batches at the source.", "Target 128 to 512 MB per file for Parquet."]}


tool(T, "compaction", "Small files compaction", "Files before and after compaction.", [("files", "Files now", 400000), ("avg_file_mb", "Average file size (MB)", 3), ("target_file_mb", "Target file size (MB)", 256)], small)

ref(T, "lakehouse", "Iceberg and Delta lakehouse", [
    {"title": "What the table format adds to files", "items": ["ACID commits: readers never see half-written data.", "Schema evolution: add, rename and drop columns safely.", "Time travel: query an earlier snapshot or roll back a bad load.", "Partition evolution and hidden partitioning (Iceberg).", "Row-level MERGE, UPDATE and DELETE for slowly changing data and privacy deletes."]},
    {"title": "Housekeeping", "items": ["Compact small files, expire old snapshots, remove orphan files.", "Keep table statistics fresh.", "Medallion layers: bronze raw, silver cleaned, gold business-ready."]}])
ref(T, "streaming", "Windows and watermarks", [
    {"title": "Window types", "head": ["Window", "Shape", "Use"], "rows": [["Tumbling", "Fixed, no overlap", "Counts per minute"], ["Sliding (hopping)", "Fixed, overlapping", "Moving average"], ["Session", "Grouped by gaps of inactivity", "User sessions"]]},
    {"title": "Late data", "items": ["Event time is when it happened; processing time is when you saw it. Use event time for correct answers.", "A watermark says how late data may arrive: events later than that are dropped or sent to a side output.", "Choose lateness by measuring real delays; longer waits mean later results.", "Make sinks idempotent: exactly-once is usually at-least-once plus deduplication."]}])
ref(T, "observability", "Data observability", [
    {"title": "Five checks on every important table", "items": ["Freshness: did it update on time?", "Volume: is the row count normal?", "Schema: did columns change?", "Distribution: nulls, ranges, categories, duplicates.", "Lineage: who depends on this if it breaks?"]},
    {"title": "Running it", "items": ["Alert owners with a link to the failing run and the last good data.", "Quarantine bad rows instead of dropping them silently.", "Track incidents and fix the cause, not just the data."]}])
