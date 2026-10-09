"""Company engagement: one job, many disciplines.

Imagine being hired to take a company from "we have an idea and some data" to "it runs, it is governed and it is reported on".
That takes eight different disciplines. This module is the project plan for that job: four phases, a list of deliverables
per discipline, and a link to the dashboard where each one is done.

A deliverable is detected as done when the workspace's own data proves it (for example 8+ requirements exist, or a backup
has been taken). Deliverables the app cannot measure are ticked by hand. Nothing here is invented: a count of zero is shown as zero.
"""
from __future__ import annotations

import json
import re
from datetime import date, timedelta

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


def _meta_all() -> dict:
    raw = state.kv_get(f"company_meta:{_ws()}")
    return json.loads(raw) if raw else {}


def set_meta(did: str, note: str | None, due: str | None) -> dict:
    """A free-text note and an optional due date for one deliverable."""
    if did not in IDS:
        raise CoError("No such deliverable.", 404)
    due = (due or "").strip()
    if due:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", due):
            raise CoError("Use a date like 2026-11-15.")
        try:
            date.fromisoformat(due)
        except ValueError:
            raise CoError("That date doesn't exist.") from None
    allm = _meta_all()
    cur = {"note": str(note or "").strip()[:600], "due": due}
    if cur["note"] or cur["due"]:
        allm[did] = cur
    else:
        allm.pop(did, None)
    state.kv_set(f"company_meta:{_ws()}", json.dumps(allm))
    state.audit("company_meta", f"{did}: note/due updated")
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
    meta = _meta_all()
    today = date.today()
    overdue = due_soon = 0
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
            m = meta.get(did, {})
            due = m.get("due", "")
            late = bool(due) and not is_done and date.fromisoformat(due) < today
            soon = bool(due) and not is_done and not late and date.fromisoformat(due) <= today + timedelta(days=7)
            overdue += late
            due_soon += soon
            items.append({"id": did, "discipline": disc, "title": title, "why": why, "href": href, "auto": bool(key), "detected": auto,
                          "manual": did in manual, "done": is_done, "detail": detail, "note": m.get("note", ""), "due": due, "overdue": late, "due_soon": soon})
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
            "overdue": overdue, "due_soon": due_soon,
            "note": "Deliverables marked 'detected' are proven by this workspace's own data. The rest are ticked by you. Progress belongs to the active workspace, so Practice and Real keep separate plans."}


# ------------------------------------------------------------------ weekly snapshots and the brief
def _flat(ov: dict) -> list[dict]:
    return [i for p in ov["phases"] for i in p["deliverables"]]


def snapshot(kind: str = "manual") -> dict:
    """Save where the plan stands right now, so next week there is something to compare against."""
    ov = overview()
    data = {"done_ids": [i["id"] for i in _flat(ov) if i["done"]], "overdue_ids": [i["id"] for i in _flat(ov) if i["overdue"]],
            "disciplines": [{"id": d["id"], "done": d["done"], "total": d["total"]} for d in ov["disciplines"]]}
    brief = diff_text(ov, latest())
    cur = state.run("INSERT INTO company_snapshots (workspace, at, kind, done, total, pct, data, brief) VALUES (?,?,?,?,?,?,?,?)",
                    (_ws(), state.now(), kind, ov["done"], ov["total"], ov["pct"], json.dumps(data), brief))
    state.run("DELETE FROM company_snapshots WHERE workspace = ? AND id NOT IN (SELECT id FROM company_snapshots WHERE workspace = ? ORDER BY id DESC LIMIT 60)", (_ws(), _ws()))
    state.audit("company_snapshot", f"{kind}: {ov['done']}/{ov['total']}")
    return {"id": cur.lastrowid, "at": state.now(), "kind": kind, "done": ov["done"], "total": ov["total"], "pct": ov["pct"], "brief": brief, "ai": False}


def snapshots(limit: int = 12) -> list[dict]:
    rows = state.rows("SELECT id, at, kind, done, total, pct, brief FROM company_snapshots WHERE workspace = ? ORDER BY id DESC LIMIT ?", (_ws(), int(limit)))
    for r in rows:
        r["ai"] = r["brief"].startswith("[AI] ") if r["brief"] else False
        if r["ai"]:
            r["brief"] = r["brief"][5:]
    return rows


def latest() -> dict | None:
    return state.one("SELECT id, at, done, total, pct, data FROM company_snapshots WHERE workspace = ? ORDER BY id DESC LIMIT 1", (_ws(),))


def _titles() -> dict[str, str]:
    return {d[0]: d[3] for d in PLAYBOOK}


def diff_data(ov: dict, prev: dict | None) -> dict:
    """What changed since the last snapshot. Pure numbers and deliverable titles: nothing from your rows."""
    titles = _titles()
    now_done = {i["id"] for i in _flat(ov) if i["done"]}
    over = [i for i in _flat(ov) if i["overdue"]]
    if not prev:
        return {"first": True, "done": ov["done"], "total": ov["total"], "pct": ov["pct"], "newly_done": [], "reopened": [],
                "overdue": [{"title": i["title"], "due": i["due"]} for i in over], "next": (ov["next"] or {}).get("title")}
    before = set(json.loads(prev["data"]).get("done_ids", []))
    return {"first": False, "since": prev["at"], "done": ov["done"], "total": ov["total"], "pct": ov["pct"], "pct_change": ov["pct"] - prev["pct"],
            "newly_done": [titles[i] for i in sorted(now_done - before) if i in titles], "reopened": [titles[i] for i in sorted(before - now_done) if i in titles],
            "overdue": [{"title": i["title"], "due": i["due"]} for i in over], "next": (ov["next"] or {}).get("title")}


def diff_text(ov: dict, prev: dict | None) -> str:
    d = diff_data(ov, prev)
    lines = [f"Engagement plan: {d['done']}/{d['total']} deliverables done ({d['pct']}%)."]
    if d["first"]:
        lines.append("This is the first snapshot, so there is nothing to compare against yet.")
    else:
        ch = d["pct_change"]
        lines.append(f"Since {d['since']}: {'+' if ch >= 0 else ''}{ch} percentage points.")
        if d["newly_done"]:
            lines.append("Finished: " + "; ".join(d["newly_done"]) + ".")
        if d["reopened"]:
            lines.append("No longer done (the data changed): " + "; ".join(d["reopened"]) + ".")
        if not d["newly_done"] and not d["reopened"]:
            lines.append("Nothing new was finished.")
    if d["overdue"]:
        lines.append("Overdue: " + "; ".join(f"{o['title']} (due {o['due']})" for o in d["overdue"]) + ".")
    if d["next"]:
        lines.append(f"Next up: {d['next']}.")
    return " ".join(lines)


def ai_brief(adapters: dict | None = None) -> dict:
    """Ask the AI to write a short status note from the numbers above. It sees counts and deliverable titles only, never your rows."""
    from app.services import ai_policy, llm_router
    if not ai_policy.describe()["allowed"]:
        raise CoError("AI is switched off for this workspace. The plain-language brief above works without it. Turn AI on in Settings to use this.", 403)
    snap = latest() or None
    ov = overview()
    # compare against the snapshot BEFORE the one we are about to store
    data = diff_data(ov, snap)
    system = ("You write a short weekly status note for a solo consultant about their own project plan. Use only the facts in the JSON. "
              "Do not invent numbers, dates or progress. 4 to 6 sentences: where things stand, what moved, what is overdue, the single next step. Plain language.")
    prompt = "Plan changes (JSON):\n" + json.dumps({**data, "brief": brief_get()}, default=str)
    try:
        r = llm_router.complete(system, prompt, "medium", "auto", adapters)
    except Exception as e:  # noqa: BLE001
        raise CoError(str(e), getattr(e, "status", 502)) from None
    s = snapshot("manual")
    state.run("UPDATE company_snapshots SET brief = ? WHERE id = ?", ("[AI] " + r["text"], s["id"]))
    state.audit("company_ai_brief", f"{r['provider']}")
    return {**s, "brief": r["text"], "ai": True, "provider": r["provider"], "model": r["model"]}


def weekly_due() -> bool:
    last = latest()
    if not last:
        return True
    from datetime import datetime, timezone
    age = datetime.now(timezone.utc) - datetime.strptime(last["at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return age >= timedelta(days=7)
