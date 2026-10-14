"""Export everything: one zip with every table as CSV plus your settings (KPIs, quality rules, pipelines, workflows,
sources, views) as JSON. It is for keeping your own copy or moving machines. It does NOT include secrets: API keys and
passwords live in backend/.env, which is never exported. Data in a zip is not encrypted."""
from __future__ import annotations

import csv
import io
import json
import zipfile

from app.services import datasets, expectations, pipelines, sources, state, views, webreader, workflows, workspaces
from app.services.db import get_cursor

CORE = ("fact_operations", "dim_entities")


def _tables() -> list[str]:
    names = list(CORE) + [t["table_name"] for t in datasets.list_tables()]
    return list(dict.fromkeys(names))


def build() -> bytes:
    ws = workspaces.active()
    buf = io.BytesIO()
    counts = {}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        with get_cursor() as cur:
            for t in _tables():
                try:
                    res = cur.execute(f"SELECT * FROM {datasets.q(t)}")
                except Exception:  # noqa: BLE001  a missing table shouldn't sink the whole export
                    continue
                n = 0
                with z.open(f"tables/{t}.csv", "w") as raw:
                    out = io.TextIOWrapper(raw, encoding="utf-8", newline="")
                    w = csv.writer(out)
                    w.writerow([d[0] for d in res.description])
                    while True:
                        chunk = res.fetchmany(5000)
                        if not chunk:
                            break
                        w.writerows([["" if v is None else v for v in r] for r in chunk])
                        n += len(chunk)
                    out.flush()
                    out.detach()
                counts[t] = n
        try:
            from app.routers import kpis
            kp = [{k: v for k, v in x.items() if k in ("id", "name", "metric", "direction", "target", "warn_pct", "window_days")} for x in kpis._list()]
        except Exception:  # noqa: BLE001
            kp = []
        cfg = {"workspace": ws, "exported_at": state.now(), "kpis": kp, "quality_rules": expectations.list_rules(),
               "pipelines": pipelines.list_pipelines(), "workflows": workflows.list_saved(), "views": views.list_views(),
               "sources": [{k: v for k, v in s.items() if k in ("name", "kind", "config", "target", "interval_minutes", "enabled")} for s in sources.list_sources()],
               "bookmarks": webreader.bookmarks()}
        z.writestr("settings.json", json.dumps(cfg, indent=2, default=str))
        z.writestr("README.txt", f"Export of the '{ws}' workspace made {state.now()} UTC.\n\ntables/    one CSV per table\nsettings.json    KPIs, quality rules, pipelines, workflows, sources, views, bookmarks\n\n"
                   "Not included: API keys and passwords (they live in backend/.env), the app's run history and audit log.\nThe zip is not encrypted; keep it somewhere safe.\n\nRows per table:\n"
                   + "\n".join(f"  {t}: {n:,}" for t, n in counts.items()) + "\n")
    state.audit("export_all", f"{len(counts)} tables")
    return buf.getvalue()
