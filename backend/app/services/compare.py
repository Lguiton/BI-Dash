"""Practice vs Real, side by side.

Why: Practice is sample data that behaves nicely. Real data is messier. Seeing the same measures next to each other shows
what changes when the data is real (cleanliness, shape, KPI results) and tells you whether your analysis still holds.
Both files are only READ. The workspace that is not active is copied to a scratch folder first, so nothing is locked or changed.
"""
from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import duckdb

from app.services import dba, workspaces
from app.services.db import get_cursor

METRICS = [("records", "Records", "count"), ("entities", "Entities", "count"), ("first_date", "First date", "text"), ("last_date", "Last date", "text"),
           ("revenue", "Revenue", "usd"), ("cost", "Operational cost", "usd"), ("profit", "Net profit", "usd"), ("margin_pct", "Net margin %", "pct"),
           ("units", "Units processed", "count"), ("rev_per_record", "Revenue per record", "usd"), ("completed_pct", "Completed share %", "pct"),
           ("cancelled_pct", "Cancelled share %", "pct"), ("integrity_pass", "Integrity checks passing", "text")]


def _profile(cur) -> dict:
    tables = {r[0]: None for r in cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'main' AND table_type = 'BASE TABLE'").fetchall()}
    for t in tables:
        tables[t] = cur.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
    out = {"tables": tables, "columns": {}, "metrics": {}, "entities": [], "kpis": []}
    if "fact_operations" not in tables:
        return out
    out["columns"] = {t: [r[0] for r in cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema = 'main' AND table_name = ? ORDER BY ordinal_position", [t]).fetchall()]
                      for t in ("fact_operations", "dim_entities") if t in tables}
    r = cur.execute("""SELECT COUNT(*), MIN(record_date), MAX(record_date), SUM(revenue), SUM(operational_cost), SUM(units_processed),
                              AVG(CASE WHEN status = 'Completed' THEN 1.0 ELSE 0 END), AVG(CASE WHEN status = 'Cancelled' THEN 1.0 ELSE 0 END)
                       FROM fact_operations""").fetchone()
    n, d0, d1, rev, cost, units, comp, canc = r
    m = out["metrics"]
    m["records"] = n
    if n:
        rev, cost = float(rev or 0), float(cost or 0)
        m.update(first_date=str(d0), last_date=str(d1), revenue=round(rev, 2), cost=round(cost, 2), profit=round(rev - cost, 2),
                 margin_pct=round(100 * (rev - cost) / rev, 2) if rev else None, units=int(units or 0), rev_per_record=round(rev / n, 2),
                 completed_pct=round(100 * float(comp or 0), 1), cancelled_pct=round(100 * float(canc or 0), 1))
        if "dim_entities" in tables:
            m["entities"] = cur.execute("SELECT COUNT(*) FROM dim_entities").fetchone()[0]
            out["entities"] = [{"name": a, "revenue": round(float(b or 0), 2)} for a, b in cur.execute(
                "SELECT e.name, SUM(f.revenue) FROM fact_operations f JOIN dim_entities e ON e.entity_id = f.entity_id GROUP BY 1 ORDER BY 2 DESC LIMIT 5").fetchall()]
            checks = dba.integrity_checks(cur)
            ok = sum(1 for c in checks if c["ok"] or "unused" in c["detail"])
            m["integrity_pass"] = f"{ok}/{len(checks)}"
    return out


def _on(ws: str, fn):
    """Run fn(cursor) against a workspace's file: the active one through the app's connection, the other on a scratch copy."""
    p = workspaces.path_of(ws)
    if not p.exists():
        return None
    if ws == workspaces.active():
        with get_cursor() as cur:
            return fn(cur)
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / "copy.duckdb"
        shutil.copy2(p, dst)
        wal = p.with_name(p.name + ".wal")
        if wal.exists():
            shutil.copy2(wal, dst.with_name(dst.name + ".wal"))
        con = duckdb.connect(str(dst))
        try:
            return fn(con)
        finally:
            con.close()


def _kpis_on(defs: list[dict]):
    from app.routers import kpis

    def go(cur):
        r = cur.execute("SELECT MAX(record_date), MIN(record_date) FROM fact_operations").fetchone()
        return [{"id": d["id"], **{k: v for k, v in kpis._evaluate(cur, d, r[0], r[1]).items() if k in ("value", "status", "label", "unit")}} for d in defs]
    return go


def _delta(a, b):
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        d = b - a
        return {"abs": round(d, 2), "pct": round(100 * d / a, 1) if a else None}
    return None


def compare() -> dict:
    profs: dict[str, dict | None] = {}
    for ws in workspaces.NAMES:
        try:
            profs[ws] = _on(ws, _profile)
        except Exception as e:  # noqa: BLE001  a damaged or empty file must not break the page
            profs[ws] = {"error": str(e).splitlines()[0][:160], "tables": {}, "columns": {}, "metrics": {}, "entities": [], "kpis": []}
    # the SAME KPI definitions, evaluated on both datasets
    from app.routers import kpis
    try:
        defs = [{k: d[k] for k in ("id", "name", "metric", "direction", "target", "warn_pct", "window_days")} for d in kpis._list()]
    except Exception:  # noqa: BLE001
        defs = []
    kp: dict[str, dict] = {}
    for ws in workspaces.NAMES:
        if profs[ws] and defs and profs[ws]["metrics"].get("records"):
            try:
                kp[ws] = {x["id"]: x for x in (_on(ws, _kpis_on(defs)) or [])}
            except Exception:  # noqa: BLE001
                kp[ws] = {}
        else:
            kp[ws] = {}
    rows = []
    for key, label, unit in METRICS:
        a, b = (profs[w]["metrics"].get(key) if profs[w] else None for w in workspaces.NAMES)
        rows.append({"key": key, "label": label, "unit": unit, "practice": a, "real": b, "delta": _delta(a, b)})
    tabs = sorted({t for p in profs.values() if p for t in p["tables"]})
    table_rows = [{"table": t, "practice": (profs["practice"] or {}).get("tables", {}).get(t), "real": (profs["real"] or {}).get("tables", {}).get(t)} for t in tabs]
    schema = []
    for t in ("fact_operations", "dim_entities"):
        pa = set(((profs["practice"] or {}).get("columns") or {}).get(t, []))
        re_ = set(((profs["real"] or {}).get("columns") or {}).get(t, []))
        if pa and re_ and pa != re_:
            schema.append({"table": t, "only_practice": sorted(pa - re_), "only_real": sorted(re_ - pa)})
    kpi_rows = [{"name": d["name"], "label": kp["practice"].get(d["id"], kp["real"].get(d["id"], {})).get("label", d["metric"]), "target": d["target"], "direction": d["direction"],
                 "practice": kp["practice"].get(d["id"]), "real": kp["real"].get(d["id"])} for d in defs]
    real_has = bool(profs["real"] and profs["real"]["metrics"].get("records"))
    return {"active": workspaces.active(), "exists": {w: bool(profs[w]) for w in workspaces.NAMES}, "real_has_data": real_has, "metrics": rows, "tables": table_rows, "schema_differences": schema,
            "top_entities": {w: (profs[w] or {}).get("entities", []) for w in workspaces.NAMES}, "kpis": kpi_rows,
            "errors": {w: profs[w]["error"] for w in workspaces.NAMES if profs[w] and profs[w].get("error")},
            "note": ("Real has no records yet, so there is nothing to compare. Import your data in My data, then come back." if not real_has else
                     "Practice is sample data, so differences are expected. Look for: a Real dataset that is dirtier (integrity), shaped differently (date range, cancelled share), or that turns your KPIs red."),
            "kpi_note": "KPI rows apply the KPI definitions saved in the ACTIVE workspace to both datasets."}
