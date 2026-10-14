"""Data lineage for a KPI: which table and columns it reads, and which of YOUR workflows, quality rules, pipelines and
sources touch those tables. It is computed from definitions held in this app (the KPI's formula, saved workflows,
rules, pipelines, sources). It can't see anything outside the app, such as a spreadsheet you built from an export."""
from __future__ import annotations

import re

from app.services import expectations, pipelines, sources, workflows


class LineageError(Exception):
    def __init__(self, message: str, status: int = 404):
        super().__init__(message)
        self.message, self.status = message, status


ALIASES = {"f": "fact_operations", "e": "dim_entities"}


def columns_in(sql: str) -> list[dict]:
    out: dict[tuple, dict] = {}
    for a, c in re.findall(r"\b([fe])\.([a-z_]+)", sql):
        out[(ALIASES[a], c)] = {"table": ALIASES[a], "column": c}
    return sorted(out.values(), key=lambda x: (x["table"], x["column"]))


def _touches(table: str, tables: set[str]) -> bool:
    return table in tables


def kpi(kid: str) -> dict:
    from app.routers import kpis
    k = next((x for x in kpis._list() if x["id"] == kid), None)
    if not k:
        raise LineageError("No such KPI.")
    formula = kpis.METRICS[k["metric"]][1]
    cols = columns_in(formula)
    tables = {c["table"] for c in cols}
    wf = []
    for w in workflows.list_saved():
        src = (w["steps"][0] or {}).get("table") if w.get("steps") else None
        if src in tables:
            wf.append({"id": w["id"], "name": w["name"], "table": src})
    rules = [{"id": r["id"], "table": r["table"], "text": r["text"]} for r in expectations.list_rules() if r["table"] in tables]
    pipes = []
    wf_ids = {w["id"] for w in wf}
    src_list = sources.list_sources()
    for p in pipelines.list_pipelines():
        why = []
        for t in p["tasks"]:
            if t["kind"] == "dq" and t.get("ref") in tables:
                why.append(f"quality rules on {t['ref']}")
            elif t["kind"] == "workflow" and t.get("ref") in wf_ids:
                why.append("a workflow that reads it")
            elif t["kind"] == "source":
                s = next((x for x in src_list if x["id"] == t.get("ref")), None)
                if s and (s.get("target") in tables):
                    why.append(f"source '{s['name']}'")
        if why:
            pipes.append({"id": p["id"], "name": p["name"], "because": sorted(set(why))})
    srcs = [{"id": s["id"], "name": s["name"], "kind": s["kind"]} for s in src_list
            if s.get("target") in tables]
    return {"kpi": {"id": k["id"], "name": k["name"], "metric": k["metric"], "formula": formula, "status": k["status"]},
            "tables": sorted(tables), "columns": cols, "workflows": wf, "rules": rules, "pipelines": pipes, "sources": srcs,
            "note": "Built from definitions inside this app. It can't see exports or sheets you made outside it."}
