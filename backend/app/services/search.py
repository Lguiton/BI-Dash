"""One search across the whole dashboard: pages, careers, manual steps, plan deliverables, glossary terms and your KPIs.
It only looks at names and short descriptions held in the app (plus your own KPI names). It never reads your records."""
from __future__ import annotations

import re

from app.services import company, manuals

PAGES = [
    ("/", "Dashboard", "revenue cost profit margin charts insights overview home", "Page"),
    ("/company", "Company engagement plan", "plan deliverables phases hired consultant engagement snapshot brief export", "Page"),
    ("/data", "My data", "import csv upload tables explore load", "Page"),
    ("/kpis", "KPIs", "targets goals metrics red amber green builder", "Page"),
    ("/quality", "Data quality", "checks rules validation nulls duplicates", "Page"),
    ("/tracks", "Careers and tracks", "learning paths analyst scientist engineer", "Page"),
    ("/lab", "SQL Lab", "sql query select duckdb practice", "Lab"),
    ("/python", "Python notebooks", "pandas notebooks jupyter python practice", "Lab"),
    ("/apache", "Apache lab", "spark airflow superset", "Lab"),
    ("/ml", "ML Lab", "machine learning model baseline train experiments", "Lab"),
    ("/ai", "AI Lab", "ask assistant gemini openai claude usage routing privacy", "Lab"),
    ("/pipeline", "Pipeline monitor", "etl medallion bronze silver gold quarantine runs", "Lab"),
    ("/schema", "Star schema", "tables columns erd model fact dimension", "Lab"),
    ("/glossary", "Metrics glossary", "definitions formulas terms semantic layer", "Lab"),
    ("/scd", "SCD lab", "slowly changing dimension history type 2", "Lab"),
    ("/quiz", "Quiz", "test yourself questions bi", "Lab"),
    ("/sources", "Sources", "connectors refresh schedule files api database", "Manage"),
    ("/settings", "Settings and backups", "workspace practice real ai privacy backup restore alerts email", "Manage"),
    ("/activity", "Activity log", "audit history changes", "Manage"),
    ("/tracks/engineering", "Restore drill and database admin", "restore drill backup verify dba health integrity checkpoint governance", "Page"),
    ("/ai", "AI usage and agent evals", "usage tokens cost caps tiers evals regression", "Lab"),
    ("/compare", "Practice vs Real", "compare workspaces side by side differences", "Page"),
]


def _tokens(q: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9+#.-]+", q.lower()) if t]


def _score(tokens: list[str], title: str, keys: str, body: str) -> int:
    t, k, b = title.lower(), keys.lower(), body.lower()
    total = 0
    for tok in tokens:
        if t.startswith(tok):
            total += 6
        elif tok in t:
            total += 4
        elif tok in k:
            total += 2
        elif tok in b:
            total += 1
        else:
            return 0                       # every word must match somewhere
    return total


def _index() -> list[dict]:
    from app.routers import glossary, tracks
    out = [{"kind": g, "title": t, "sub": "", "href": h, "keys": k, "body": ""} for h, t, k, g in PAGES]
    for tr in tracks.TRACKS:
        out.append({"kind": "Career", "title": tr["name"], "sub": tr["role"], "href": f"/tracks/{tr['id']}", "keys": "career track path learn", "body": tr["summary"]})
        m = manuals.MANUALS.get(tr["id"])
        for i, s in enumerate(m["steps"] if m else [], 1):
            out.append({"kind": "Manual step", "title": s["title"], "sub": f"{tr['name']}, step {i}", "href": f"/tracks/{tr['id']}?view=manual&step={s['id']}",
                        "keys": "manual how to guide", "body": s["what"]})
    for pid, ph, disc, title, why, href, _sig in company.PLAYBOOK:
        out.append({"kind": "Deliverable", "title": title, "sub": f"Company plan, {ph}", "href": href or "/company", "keys": "deliverable plan company", "body": why})
    for g in glossary.TERMS:
        out.append({"kind": "Glossary", "title": g["term"], "sub": g.get("kind", ""), "href": "/glossary", "keys": g["id"], "body": g.get("definition", "")})
    try:
        from app.routers import kpis
        for k in kpis._list():
            out.append({"kind": "Your KPI", "title": k["name"], "sub": k["label"], "href": "/kpis", "keys": "kpi target", "body": ""})
    except Exception:  # noqa: BLE001  search must work even if the database is busy
        pass
    return out


def search(q: str, limit: int = 12) -> dict:
    limit = max(1, min(int(limit), 30))
    tokens = _tokens(q or "")
    idx = _index()
    if not tokens:
        top = [i for i in idx if i["kind"] in ("Page", "Career")][:limit]
        return {"query": "", "results": [{k: v for k, v in i.items() if k in ("kind", "title", "sub", "href")} for i in top], "total": len(top), "suggested": True}
    scored = [(s, i) for i in idx if (s := _score(tokens, i["title"], i["keys"], i["body"]))]
    scored.sort(key=lambda x: (-x[0], x[1]["title"]))
    return {"query": q, "results": [{k: v for k, v in i.items() if k in ("kind", "title", "sub", "href")} for _, i in scored[:limit]], "total": len(scored), "suggested": False}
