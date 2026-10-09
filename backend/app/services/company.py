"""Company engagement: one job, many disciplines.

Imagine being hired to take a company from "we have an idea and some data" to "it runs, it is governed and it is reported on".
That takes eight different disciplines. This module is the project plan for that job: four phases, a list of deliverables
per discipline, and a link to the dashboard where each one is done.

A deliverable is detected as done when the workspace's own data proves it (for example 8+ requirements exist, or a backup
has been taken). Deliverables the app cannot measure are ticked by hand. Nothing here is invented: a count of zero is shown as zero.
"""
from __future__ import annotations

import json

from app.services import state, workspaces

DISCIPLINES = [
    ("sysanalyst", "Systems Analyst", "Requirements, process and data model, feasibility, traceability"),
    ("pm", "Project & Product", "Priorities, sprints, schedule, budget, risks, OKRs"),
    ("fullstack", "Full Stack Developer", "API, database access and UI: build the thing"),
    ("engineering", "Data Engineering (+ DBA, Governance)", "Pipelines, database health and backups, data ownership and privacy"),
    ("analyst", "Data Analyst", "KPIs, quality checks and the reports leaders read"),
    ("scientist", "Data Scientist", "Is the pattern real? Statistics and segments"),
    ("ml", "Machine Learning", "Models that beat a baseline, tracked as experiments"),
    ("ai", "AI Engineering", "Assistants over the data, with privacy controls"),
]

# (id, phase, discipline, title, why, href, signal-or-None)
PLAYBOOK = [
    ("req-capture", "discover", "sysanalyst", "Capture 8+ testable requirements", "Everything later is judged against these.", "/tracks/sysanalyst", "reqs8"),
    ("req-feasible", "discover", "sysanalyst", "Score feasibility with TELOS", "Know the weakest dimension before you commit.", "/tracks/sysanalyst", "telos"),
    ("pm-risks", "discover", "pm", "Register the top 3 risks with probability and cost", "Turns worry into a number you can reserve budget for.", "/tracks/pm", "risks3"),
    ("an-kpis", "discover", "analyst", "Define 3+ KPIs with targets", "Success needs a measurable definition before work starts.", "/kpis", "kpis3"),
    ("gov-owners", "discover", "engineering", "Give every table an owner", "Unowned data is nobody's problem until it breaks.", "/tracks/engineering", "owners"),
    ("sa-model", "design", "sysanalyst", "Document the data model (dictionary and ER diagram)", "Builders and analysts need the same picture.", "/tracks/sysanalyst", None),
    ("gov-classify", "design", "engineering", "Classify data and protect personal columns from AI", "Decide what is sensitive before it is copied around.", "/tracks/engineering", "classified"),
    ("pm-prioritise", "design", "pm", "Prioritise the backlog with RICE or WSJF (5+ scored items)", "Build the highest value per effort first.", "/tracks/pm", "scored5"),
    ("fs-api", "design", "fullstack", "Design the API: map endpoints and scaffold the first resource", "Contract first: the UI and the tests both depend on it.", "/tracks/fullstack", None),
    ("fs-slice", "build", "fullstack", "Ship one vertical slice: table, API, screen, test", "Prove the whole stack works before building wide.", "/tracks/fullstack", None),
    ("de-pipeline", "build", "engineering", "Run the pipeline end to end and read the quarantine", "Reliable data in, before any model or report.", "/pipeline", None),
    ("pm-sprint", "build", "pm", "Plan a sprint and assign work to it", "A commitment you can measure velocity against.", "/tracks/pm", "sprint"),
    ("sc-test", "build", "scientist", "Test one business question statistically", "Separate a real effect from noise.", "/tracks/scientist", None),
    ("ml-run", "build", "ml", "Log a model run against a baseline", "A model only counts if it beats the simple guess.", "/ml", "mlrun"),
    ("ai-assist", "build", "ai", "Set AI privacy mode, then ask the data a question", "Useful assistants with known limits.", "/ai", None),
    ("dba-backup", "operate", "engineering", "Take a backup and verify it restores", "A backup you haven't restored is a hope, not a backup.", "/tracks/engineering", "backup"),
    ("dba-health", "operate", "engineering", "Pass every database integrity check", "Catch corruption and orphan rows early.", "/tracks/engineering", "integrity"),
    ("gov-controls", "operate", "engineering", "Reach 6+ of 8 governance controls", "Evidence that data is handled on purpose.", "/tracks/engineering", "controls6"),
    ("pm-evm", "operate", "pm", "Track delivery with earned value", "Know if you are over budget or behind before the client does.", "/tracks/pm", "evm"),
    ("sa-trace", "operate", "sysanalyst", "Trace 80%+ of built requirements to a test", "Proof the system does what was agreed.", "/tracks/sysanalyst", "trace80"),
    ("an-report", "operate", "analyst", "Send the leadership report (PDF or Excel export)", "The numbers only matter once they are read.", "/", None),
    ("fs-release", "operate", "fullstack", "Release checklist: tests green, config reviewed", "Ship on purpose.", "/tracks/fullstack", None),
]
PHASES = [("discover", "Discover", "What is needed, is it feasible, what could go wrong, how is success measured."),
          ("design", "Design", "Model the data, decide the rules, prioritise, define the API."),
          ("build", "Build", "Deliver in slices: pipeline, app, analysis, models, assistants."),
          ("operate", "Operate", "Keep it safe, healthy, on budget and proven against the requirements.")]
IDS = {d[0] for d in PLAYBOOK}


class CoError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    return workspaces.active()


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:  # noqa: BLE001  one broken source must not blank the whole plan
        return default


def _signals() -> dict[str, tuple[bool, str]]:
    from app.routers import kpis as _k  # noqa: F401  (ensures the kpi table helper module is importable)
    from app.services import dba, governance, pm, sysanalysis
    from app.services.db import get_cursor
    out: dict[str, tuple[bool, str]] = {}
    reqs = _safe(sysanalysis.list_requirements, [])
    out["reqs8"] = (len(reqs) >= 8, f"{len(reqs)} requirement(s)")
    f = _safe(sysanalysis.feasibility_get, {}) or {}
    out["telos"] = (f.get("weighted_score") is not None, f"score {f.get('weighted_score')}" if f.get("weighted_score") is not None else "not scored")
    t = _safe(lambda: sysanalysis.traceability(reqs), {}) or {}
    built = (t.get("by_status", {}).get("built", 0) + t.get("by_status", {}).get("tested", 0)) if t else 0
    cov = t.get("test_coverage_pct")
    out["trace80"] = (bool(built) and cov is not None and cov >= 80, f"{cov}% of built requirements have a test" if cov is not None else "no built requirements yet")
    risks = _safe(pm.list_risks, [])
    out["risks3"] = (len(risks) >= 3, f"{len(risks)} risk(s)")
    items = _safe(pm.list_items, [])
    scored = [i for i in items if pm.rice(i) is not None or pm.wsjf(i) is not None]
    out["scored5"] = (len(scored) >= 5, f"{len(scored)} scored item(s)")
    assigned = [i for i in items if i.get("sprint_id")]
    out["sprint"] = (bool(_safe(pm.list_sprints, [])) and bool(assigned), f"{len(assigned)} item(s) in sprints")
    ov = _safe(lambda: pm.earned_value(items, pm.today()), {}) or {}
    out["evm"] = (bool(ov.get("available")), "earned value computed" if ov.get("available") else "needs planned cost, start date and duration")

    def kpi_count():
        with get_cursor() as cur:
            return cur.execute("SELECT COUNT(*) FROM kpi_defs").fetchone()[0]
    n = _safe(kpi_count, 0)
    out["kpis3"] = (n >= 3, f"{n} KPI(s)")
    cat = _safe(governance.catalog, {"assets": []})
    own = [a for a in cat["assets"] if a["kind"] == "table" and not a["system"]]
    owned = sum(1 for a in own if a.get("owner"))
    out["owners"] = (bool(own) and owned == len(own), f"{owned}/{len(own)} tables have an owner")
    classed = sum(1 for a in own if a.get("classification"))
    pii = _safe(governance.pii_scan, {"unprotected": 0}) or {}
    out["classified"] = (bool(own) and classed == len(own) and pii.get("unprotected", 0) == 0, f"{classed}/{len(own)} classified, {pii.get('unprotected', 0)} personal column(s) still visible to AI")
    ctl = _safe(governance.controls, {"in_place": 0, "total": 8}) or {}
    out["controls6"] = (ctl.get("in_place", 0) >= 6, f"{ctl.get('in_place', 0)}/{ctl.get('total', 8)} controls")
    h = _safe(dba.health, {}) or {}
    out["backup"] = ((h.get("backup") or {}).get("count", 0) > 0, f"{(h.get('backup') or {}).get('count', 0)} backup(s)")
    integ = h.get("integrity") or []
    out["integrity"] = (bool(integ) and all(c["ok"] for c in integ), f"{sum(1 for c in integ if c['ok'])}/{len(integ)} checks pass")
    runs = _safe(lambda: state.rows("SELECT COUNT(*) AS n FROM ml_runs WHERE workspace = ?", (_ws(),)), [{"n": 0}])
    out["mlrun"] = (runs[0]["n"] > 0, f"{runs[0]['n']} run(s) logged")
    return out


def _manual() -> set[str]:
    raw = state.kv_get(f"company_done:{_ws()}")
    return set(json.loads(raw)) if raw else set()


def set_done(did: str, done: bool) -> dict:
    if did not in IDS:
        raise CoError("No such deliverable.", 404)
    cur = _manual()
    (cur.add if done else cur.discard)(did)
    state.kv_set(f"company_done:{_ws()}", json.dumps(sorted(cur)))
    return overview()


def brief_get() -> dict:
    raw = state.kv_get(f"company_brief:{_ws()}")
    return json.loads(raw) if raw else {"company": "", "goal": "", "notes": ""}


def brief_save(data: dict) -> dict:
    out = {k: str(data.get(k, ""))[:2000].strip() for k in ("company", "goal", "notes")}
    state.kv_set(f"company_brief:{_ws()}", json.dumps(out))
    state.audit("company_brief", "Engagement brief updated")
    return out


def overview() -> dict:
    sig = _safe(_signals, {}) or {}
    manual = _manual()
    done_items = _safe(lambda: __import__("app.services.study", fromlist=["x"]).done_items(), {}) or {}
    phases = []
    total = done_total = 0
    per_disc: dict[str, dict] = {d[0]: {"id": d[0], "name": d[1], "does": d[2], "total": 0, "done": 0} for d in DISCIPLINES}
    for pid, pname, pdesc in PHASES:
        items = []
        for did, ph, disc, title, why, href, key in PLAYBOOK:
            if ph != pid:
                continue
            auto, detail = sig.get(key, (False, "")) if key else (False, "Tick this yourself when it's done: the app can't measure it.")
            is_done = auto or did in manual
            items.append({"id": did, "discipline": disc, "title": title, "why": why, "href": href, "auto": bool(key), "detected": auto,
                          "manual": did in manual, "done": is_done, "detail": detail})
            total += 1
            done_total += is_done
            per_disc[disc]["total"] += 1
            per_disc[disc]["done"] += is_done
        phases.append({"id": pid, "name": pname, "about": pdesc, "done": sum(1 for i in items if i["done"]), "total": len(items), "deliverables": items})
    from app.routers import tracks as T
    steps = {t["id"]: t["path"] for t in T.TRACKS}
    for d in per_disc.values():
        path = steps.get(d["id"], [])
        d["learning_done"] = sum(1 for s in path if s["id"] in done_items)
        d["learning_total"] = len(path)
        d["href"] = f"/tracks/{d['id']}"
    nxt = next((i for p in phases for i in p["deliverables"] if not i["done"]), None)
    return {"workspace": _ws(), "brief": brief_get(), "phases": phases, "disciplines": list(per_disc.values()),
            "done": done_total, "total": total, "pct": round(100 * done_total / total) if total else 0, "next": nxt,
            "note": "Deliverables marked 'detected' are proven by this workspace's own data. The rest are ticked by you. Progress belongs to the active workspace, so Practice and Real keep separate plans."}
