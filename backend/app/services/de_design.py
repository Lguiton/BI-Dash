"""Data engineering design helpers: suggest a star schema for a table, and choose a kind of data store.

Both give a starting point from the data's shape. The user decides: names and grain are guesses from the values.
"""
from __future__ import annotations

import re

from app.services.datasets import DataError, q
from app.services.stats_lab import _rows, resolve

NON_ADDITIVE = ("margin", "pct", "percent", "rate", "ratio", "avg", "average", "price", "score", "per_")
DATE_PARTS = {"year", "quarter", "month", "week", "day", "month_name", "day_name", "is_weekend", "weekday"}
KEY_HINT = re.compile(r"(^id$|_id$|_key$|_code$|^key$)", re.I)


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "col"


def suggest_star(source: str) -> dict:
    ident, cols = resolve(source)
    t = q(ident)
    total = int(_rows(f"SELECT COUNT(*) AS n FROM {t}", [])[0]["n"])
    if total == 0:
        raise DataError("This table has no rows to design from.")
    prof = {}
    for c in cols:
        d = int(_rows(f"SELECT COUNT(DISTINCT {q(c)}) AS d FROM {t}", [])[0]["d"])
        prof[c] = d
    keys = [c for c, k in cols.items() if k in ("text", "number") and KEY_HINT.search(c) and 1 < prof[c] < total]
    dates = [c for c, k in cols.items() if k == "date" and prof[c] > 1]
    claimed: set[str] = set(keys) | set(dates)
    if dates:
        claimed |= {c for c in cols if c.lower() in DATE_PARTS}  # calendar parts belong to the date dimension
    dims = []
    for kcol in keys:
        attrs = []
        for c, k in cols.items():
            if c in claimed or k not in ("text", "bool") or prof[c] < 2 or prof[c] > prof[kcol]:
                continue
            both = int(_rows(f"SELECT COUNT(*) AS n FROM (SELECT DISTINCT {q(kcol)}, {q(c)} FROM {t})", [])[0]["n"])
            if both == prof[kcol]:  # each key value has exactly one value of c
                attrs.append(c)
        claimed |= set(attrs)
        dims.append({"name": f"dim_{_slug(kcol).removesuffix('_id').removesuffix('_key') or _slug(kcol)}", "key": kcol, "attributes": attrs, "rows": prof[kcol]})
    for dcol in dates:
        dims.append({"name": "dim_date", "key": dcol, "attributes": ["year", "quarter", "month", "month_name", "day_name", "is_weekend"], "rows": prof[dcol],
                     "note": "Build the calendar attributes from the date, so every report slices time the same way."})
        break
    standalone = [c for c, k in cols.items() if k in ("text", "bool") and c not in claimed and 1 < prof[c] <= max(50, total // 20)]
    for c in standalone:
        dims.append({"name": f"dim_{_slug(c)}", "key": c, "attributes": [], "rows": prof[c], "note": "A small list of values; could also stay on the fact table as a plain column."})
        claimed.add(c)
    measures, other = [], []
    for c, k in cols.items():
        if k != "number" or c in claimed:
            continue
        if prof[c] <= 1:
            other.append({"column": c, "note": "Never changes, so it is an attribute of the whole table, not a measure."})
            continue
        low = c.lower()
        add = not any(w in low for w in NON_ADDITIVE)
        measures.append({"column": c, "additive": add,
                         "note": "Can be summed over any dimension." if add else "Don't add this up. Store its numerator and denominator as measures and divide after summing."})
    warnings = []
    grain = "one row per source record"
    if dates:
        for kcol in keys:
            n = int(_rows(f"SELECT COUNT(*) AS n FROM (SELECT DISTINCT {q(dates[0])}, {q(kcol)} FROM {t})", [])[0]["n"])
            if n == total:
                grain = f"one row per {kcol} per {dates[0]}"
                break
        else:
            warnings.append(f"No key plus {dates[0]} is unique, so the grain is unclear. Decide what one row means before building.")
    if not measures:
        warnings.append("No numeric measures found: a fact table needs something to add up or count.")
    if not dims:
        warnings.append("No dimensions found: add keys or categories to slice by.")
    fk = [f"{d['name'].removeprefix('dim_')}_key" for d in dims]
    ddl = [f"CREATE TABLE fact_{_slug(source)} (" + ", ".join(fk + [m["column"] for m in measures]) + ");"]
    for d in dims:
        ddl.append(f"CREATE TABLE {d['name']} ({d['name'].removeprefix('dim_')}_key, {d['key']}" + "".join(f", {a}" for a in d["attributes"]) + ");")
    return {"source": source, "rows": total, "grain": grain, "fact": f"fact_{_slug(source)}", "dimensions": dims, "measures": measures, "other": other,
            "warnings": warnings, "sketch": ddl,
            "lesson": "A star schema puts the numbers you add up (measures) in a central fact table and the ways you slice them (dimensions) in small tables around it. Decide the grain first: what one fact row means. Each dimension gets a surrogate key; the fact table holds those keys plus the measures. This is a starting point from the shape of your data: you know what the columns mean."}


def choose_store(workload: str = "reporting", data: str = "structured", volume: str = "small", users: str = "few", realtime: bool = False) -> dict:
    ok = {"workload": ("transactions", "reporting", "mixed"), "data": ("structured", "mixed", "raw"), "volume": ("small", "medium", "huge"), "users": ("few", "many")}
    for name, v in (("workload", workload), ("data", data), ("volume", volume), ("users", users)):
        if v not in ok[name]:
            raise DataError(f"{name} must be one of {', '.join(ok[name])}.")
    why = []
    if data == "raw" or (data == "mixed" and volume != "small"):
        pick = "data lake"
        why.append("Raw or varied data (files, logs, images, events) is cheapest to keep as-is in a lake; you decide the structure when you read it.")
        if workload != "transactions":
            why.append("Put a warehouse or lakehouse layer on top for the tables people report from.")
    elif workload == "transactions":
        pick = "operational database"
        why.append("Many small reads and writes that must be correct right now (orders, payments) belong in a transactional database.")
        if users == "many" or realtime:
            why.append("Plan for connection limits and keep heavy reports off it (use a replica or a warehouse).")
    elif workload == "reporting":
        pick = "data warehouse"
        why.append("Cleaned, structured data read in big scans by analysts and dashboards belongs in a warehouse, organized as facts and dimensions.")
    else:
        pick = "database now, warehouse when reports slow it down"
        why.append("Mixed work is fine on one database while it is small; split reporting into a warehouse once reports slow down the transactions.")
    if realtime:
        why.append("Real-time needs a streaming path (events through a queue) next to the batch path; this app only practises batch.")
    if volume == "huge":
        why.append("Huge volume points to distributed storage and processing, which this app can't run (see the Apache lab to practise the ideas).")
    here = {"operational database": "the app's own DuckDB and the Postgres practice folder", "data warehouse": "the gold layer of the medallion pipeline and the star-schema suggester",
            "data lake": "the Big data lab and the pipeline's bronze layer (files kept raw)"}.get(pick, "DuckDB for both, with the pipeline's gold layer for reports")
    return {"recommendation": pick, "reasons": why, "practise_here": here,
            "lesson": "Database for running the business, warehouse for reporting on it, lake for keeping everything raw. Many organizations use all three, connected by pipelines."}


def metadata_view(search: str = "") -> dict:
    """The three kinds of metadata for this database: technical (structures), process (what has run), business (meaning and ownership)."""
    from app.services import dba, governance, pipeline
    cat = governance.catalog()
    mine = [a for a in cat["assets"] if not a["system"]]
    term = search.strip().lower()[:60]
    technical = []
    for a in mine:
        cols = [{"name": c["name"], "type": c.get("type", "")} for c in a["columns"]]
        if term:
            cols = [c for c in cols if term in c["name"].lower()] if term not in a["name"].lower() else cols
            if not cols:
                continue
        technical.append({"table": a["name"], "kind": a["kind"], "rows": a["rows"], "column_count": len(a["columns"]), "columns": cols})
    business = [{"table": a["name"], "owner": a["owner"], "steward": a["steward"], "description": a["description"], "classification": a["classification"]} for a in mine]
    try:
        runs = (pipeline.status().get("history") or [])[:10]
    except Exception:  # noqa: BLE001 - the pipeline needs duckdb files that may not exist yet
        runs = []
    try:
        h = dba.health()
        process = {"database_bytes": h["file"]["size_bytes"], "backups": h["backup"]["count"], "backup_age_hours": h["backup"]["age_hours"], "pipeline_runs": runs}
    except Exception:  # noqa: BLE001
        process = {"pipeline_runs": runs}
    n = len(mine) or 1
    gaps = [f"{b['table']}: no description" for b in business if not b["description"]][:12] + [f"{b['table']}: no owner" for b in business if not b["owner"]][:12]
    return {"search": term, "technical": technical, "business": business, "process": process,
            "coverage": {"tables": len(mine), "described_pct": round(100 * sum(1 for b in business if b["description"]) / n), "owned_pct": round(100 * sum(1 for b in business if b["owner"]) / n)},
            "gaps": gaps,
            "lesson": "Metadata is data about data. Technical metadata describes structures (tables, columns, types, row counts; relational databases keep it in the system catalog). Process metadata records what ran (start and end times, volumes moved, disk use, users) and is how you troubleshoot. Business metadata says what the data means, where it came from and who owns it; a searchable catalog of it is the heart of data governance and lineage."}
