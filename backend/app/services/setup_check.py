"""First-run checklist: a short list of "have you set this up yet?" items, each computed from what is actually in the
active workspace (nothing is stored as ticked). An item turns green when the thing really exists."""
from __future__ import annotations

from app.services import backups, providers, state, workspaces


def _count(sql: str, params=()) -> int:
    row = state.one(sql, params)
    return int(next(iter(row.values()))) if row else 0


def items() -> list[dict]:
    ws = workspaces.active()
    from app.services.db import get_cursor
    try:
        with get_cursor() as cur:
            n = cur.execute("SELECT COUNT(*) FROM fact_operations").fetchone()[0]
    except Exception:  # noqa: BLE001
        n = 0
    sources = _count("SELECT COUNT(*) FROM sources WHERE workspace=?", (ws,))
    try:
        from app.routers import kpis
        n_kpi = len(kpis._list())
    except Exception:  # noqa: BLE001
        n_kpi = 0
    mode = workspaces.settings(ws).get("ai_mode", "off")
    has_key = any(providers.api_key(p) for p in providers.INFO)
    try:
        n_backup = len([b for b in backups.list_backups(ws) if not b["kind"].startswith("safety")])
    except Exception:  # noqa: BLE001
        n_backup = 0
    n_dq = _count("SELECT COUNT(*) FROM dq_rules WHERE workspace=?", (ws,))
    n_pipe = _count("SELECT COUNT(*) FROM pipelines WHERE workspace=?", (ws,))
    return [
        {"id": "data", "title": "Load your data", "done": n > 0 or sources > 0, "href": "/sources",
         "detail": f"{n:,} records in {ws}" if n else "Import a CSV or connect a source."},
        {"id": "ai", "title": "Choose what the AI may see", "done": mode != "off" or has_key, "href": "/settings",
         "detail": f"AI mode is '{mode}'" + ("; a provider key is set." if has_key else "; no provider key found in backend/.env.")},
        {"id": "backup", "title": "Take a backup", "done": n_backup > 0, "href": "/tracks/engineering",
         "detail": f"{n_backup} backup(s)" if n_backup else "No backup yet."},
        {"id": "kpi", "title": "Define a KPI with a target", "done": n_kpi > 0, "href": "/kpis",
         "detail": f"{n_kpi} KPI(s)" if n_kpi else "Pick a metric and a target."},
        {"id": "dq", "title": "Add a data-quality rule", "done": n_dq > 0, "href": "/quality",
         "detail": f"{n_dq} rule(s)" if n_dq else "Rules catch bad data early."},
        {"id": "pipeline", "title": "Build a pipeline", "done": n_pipe > 0, "href": "/pipelines",
         "detail": f"{n_pipe} pipeline(s)" if n_pipe else "Chain refresh, rules and backup."},
    ]


def status() -> dict:
    it = items()
    done = sum(1 for i in it if i["done"])
    return {"workspace": workspaces.active(), "items": it, "done": done, "total": len(it), "complete": done == len(it)}
