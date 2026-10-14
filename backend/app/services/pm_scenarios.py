"""What-if scenarios for the Project & Product board, and practice cases with hidden answers.

Schedule what-ifs re-run the same critical-path calculation on a COPY of your items with the change applied, and show the difference. Nothing on your
board is changed. Simulation draws each unfinished task's duration from a range (optimistic to pessimistic) 1,000 times to give a spread, not one date.
Product what-ifs re-rank the backlog by RICE with changed assumptions and show what fits in a given capacity.

Honest limits: the schedule uses the durations and dependencies you entered (same convention as the Schedule tab: every task counts, done or not, and people
are not limited, so it will not see a resource clash). The simulation is only as good as the ranges you give it, and it treats tasks as independent, which
makes it a little optimistic when one cause (a sick lead, a late vendor) hits several tasks. RICE is a ranking aid, not a forecast of value."""
from __future__ import annotations

import random
from datetime import date, timedelta

import numpy as np

from app.services import pm
from app.services.pm import PmError

SCHEDULE_KINDS = {
    "slip": "One task takes N more days (item_id, days)",
    "estimate_error": "Every unfinished task runs a percentage longer or shorter (pct)",
    "capacity_loss": "You lose a percentage of your capacity, so unfinished work takes longer (pct)",
    "add_work": "A new task is added (title, duration_days, deps, cost, blocks)",
    "remove": "A task is cut from scope (item_id)",
    "cost_overrun": "Unfinished tasks cost a percentage more (pct)",
}
MAX_CHANGES = 12


def _copy(items: list[dict]) -> list[dict]:
    return [dict(i, deps=list(i.get("deps") or [])) for i in items]


def _num(v, what, lo=-1000.0, hi=100000.0) -> float:
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise PmError(f"{what} must be a number.") from None
    if not lo <= x <= hi:
        raise PmError(f"{what} must be between {lo:g} and {hi:g}.")
    return x


def _find(items: list[dict], iid) -> dict:
    try:
        n = int(iid)
    except (TypeError, ValueError):
        raise PmError("item_id must be a whole number (the # shown on the board).") from None
    for i in items:
        if i["id"] == n:
            return i
    raise PmError(f"There's no item #{n} on the board.", 404)


def apply_changes(items: list[dict], changes: list[dict]) -> tuple[list[dict], list[str]]:
    if not isinstance(changes, list) or not changes:
        raise PmError("Describe at least one change.")
    if len(changes) > MAX_CHANGES:
        raise PmError(f"At most {MAX_CHANGES} changes at a time.")
    out, notes, nid = _copy(items), [], -1
    for c in changes:
        k = c.get("kind")
        if k not in SCHEDULE_KINDS:
            raise PmError("kind must be one of: " + ", ".join(SCHEDULE_KINDS) + ".")
        if k == "slip":
            it = _find(out, c.get("item_id"))
            d = _num(c.get("days"), "days", -365, 3650)
            it["duration_days"] = max(0.0, (it["duration_days"] or 0) + d)
            notes.append(f"'{it['title']}' takes {d:+g} days.")
        elif k in ("estimate_error", "capacity_loss", "cost_overrun"):
            p = _num(c.get("pct"), "pct", -90, 500) if k != "capacity_loss" else _num(c.get("pct"), "pct", 0, 90)
            for it in out:
                if it["status"] == "done":
                    continue
                if k == "estimate_error" and it.get("duration_days"):
                    it["duration_days"] = it["duration_days"] * (1 + p / 100)
                elif k == "capacity_loss" and it.get("duration_days"):
                    it["duration_days"] = it["duration_days"] / (1 - p / 100)
                elif k == "cost_overrun" and it.get("planned_cost"):
                    it["planned_cost"] = it["planned_cost"] * (1 + p / 100)
            notes.append({"estimate_error": f"Unfinished tasks run {p:+g}% in duration.", "capacity_loss": f"Capacity drops {p:g}%, so unfinished tasks take {100 / (100 - p):.2f}x as long.", "cost_overrun": f"Unfinished tasks cost {p:+g}% more."}[k])
        elif k == "remove":
            it = _find(out, c.get("item_id"))
            out = [x for x in out if x["id"] != it["id"]]
            for x in out:
                if it["id"] in x["deps"]:
                    x["deps"] = sorted({d for d in x["deps"] if d != it["id"]} | set(it["deps"]))
            notes.append(f"'{it['title']}' is cut; what depended on it now depends on what it depended on.")
        elif k == "add_work":
            title = str(c.get("title") or "New work").strip()[:80]
            dur = _num(c.get("duration_days"), "duration_days", 0, 3650)
            deps = [_find(out, d)["id"] for d in (c.get("deps") or [])]
            new = {"id": nid, "kind": "task", "title": title, "status": "todo", "duration_days": dur, "deps": deps, "planned_cost": _num(c.get("cost") or 0, "cost", 0, 1e9), "start_date": None, "points": None}
            out.append(new)
            for b in c.get("blocks") or []:
                _find(out, b)["deps"].append(nid)
            notes.append(f"New task '{title}' ({dur:g} days) after {', '.join('#' + str(d) for d in deps) or 'nothing'}" + (f", blocking {', '.join('#' + str(b) for b in c['blocks'])}." if c.get("blocks") else "."))
            nid -= 1
    return out, notes


def _plain_date(s: str | None) -> str:
    return s or "n/a"


def run_schedule(changes: list[dict], as_of: date | None = None) -> dict:
    as_of = as_of or pm.today()
    items = pm.list_items()
    base = pm.critical_path(_copy(items), as_of)
    if not base["available"]:
        raise PmError(base["reason"])
    mod, notes = apply_changes(items, changes)
    scen = pm.critical_path(mod, as_of)
    if not scen["available"]:
        raise PmError(scen["reason"])
    bt = {r["id"]: r for r in base["rows"]}
    st = {r["id"]: r for r in scen["rows"]}
    delta = round(scen["duration_days"] - base["duration_days"], 2)
    newly = [st[i]["title"] for i in scen["critical"] if i not in base["critical"]]
    dropped = [bt[i]["title"] for i in base["critical"] if i in st and i not in scen["critical"]]
    moved = sorted(({"title": st[i]["title"], "float_before": bt[i]["float"] if i in bt else None, "float_after": st[i]["float"], "finish_before": bt[i]["finish"] if i in bt else None, "finish_after": st[i]["finish"]}
                    for i in st if i not in bt or abs(st[i]["finish"] != bt[i]["finish"]) or bt[i]["float"] != st[i]["float"]), key=lambda r: (r["float_after"] if r["float_after"] is not None else 0))[:10]
    cost_b = sum((i.get("planned_cost") or 0) for i in items)
    cost_a = sum((i.get("planned_cost") or 0) for i in mod)
    says = ("The finish date does not move: the change is absorbed by slack." if abs(delta) < 1e-9 else
            f"The project finishes {abs(delta):g} day(s) {'later' if delta > 0 else 'earlier'}: {_plain_date(base['finish'])} becomes {_plain_date(scen['finish'])}.")
    if newly:
        says += " Now on the critical path: " + ", ".join(newly) + "."
    if cost_a != cost_b:
        says += f" Planned cost changes by {cost_a - cost_b:+,.0f}."
    return {"changes": notes, "before": {"days": base["duration_days"], "finish": base["finish"], "critical": [bt[i]["title"] for i in base["critical"]], "cost": round(cost_b, 2)},
            "after": {"days": scen["duration_days"], "finish": scen["finish"], "critical": [st[i]["title"] for i in scen["critical"]], "cost": round(cost_a, 2)}, "delta_days": delta,
            "newly_critical": newly, "no_longer_critical": dropped, "affected": moved, "says": says, "board_changed": False,
            "caution": "Uses your entered durations and dependencies. It does not see people being double-booked."}


# ---------------------------------------------------------------- simulation


def simulate(runs: int = 1000, optimistic_pct: float = 20, pessimistic_pct: float = 50, deadline: str | None = None, changes: list[dict] | None = None, seed: int = 1, as_of: date | None = None) -> dict:
    as_of = as_of or pm.today()
    items = pm.list_items()
    notes: list[str] = []
    if changes:
        items, notes = apply_changes(items, changes)
    if not 100 <= int(runs) <= 5000:
        raise PmError("runs must be between 100 and 5000.")
    opt, pes = _num(optimistic_pct, "optimistic_pct", 0, 90) / 100, _num(pessimistic_pct, "pessimistic_pct", 0, 500) / 100
    base = pm.critical_path(_copy(items), as_of)
    if not base["available"]:
        raise PmError(base["reason"])
    nodes = {i["id"]: i for i in items if (i.get("duration_days") or 0) > 0 or i["kind"] == "milestone"}
    deps = {k: [d for d in v["deps"] if d in nodes] for k, v in nodes.items()}
    order, seen = [], set()

    def visit(n):
        if n in seen:
            return
        seen.add(n)
        for d in deps[n]:
            visit(d)
        order.append(n)
    for n in sorted(nodes):
        visit(n)
    rng = np.random.default_rng(int(seed))
    n = int(runs)
    dur = {}
    for k, v in nodes.items():
        d = float(v.get("duration_days") or 0)
        if v["status"] == "done" or d == 0:
            dur[k] = np.full(n, d)
        else:
            dur[k] = rng.triangular(d * (1 - opt), d, d * (1 + pes), n)
    ef: dict[int, np.ndarray] = {}
    pred: dict[int, np.ndarray] = {}
    for k in order:
        if deps[k]:
            stack = np.vstack([ef[d] for d in deps[k]])
            start = stack.max(axis=0)
            pred[k] = np.array(deps[k])[stack.argmax(axis=0)]
        else:
            start, pred[k] = np.zeros(n), np.full(n, -10**9)
        ef[k] = start + dur[k]
    allef = np.vstack([ef[k] for k in order])
    total = allef.max(axis=0)
    last = np.array(order)[allef.argmax(axis=0)]
    crit_count = {k: 0 for k in order}
    for r in range(n):
        cur = int(last[r])
        while cur in nodes:
            crit_count[cur] += 1
            cur = int(pred[cur][r])
    start_day = date.fromisoformat(base["project_start"])
    q = {p: float(np.percentile(total, p)) for p in (10, 50, 80, 90)}
    fin = {p: (start_day + timedelta(days=int(round(v)))).isoformat() for p, v in q.items()}
    prob = None
    if deadline:
        try:
            dl = date.fromisoformat(deadline)
        except ValueError:
            raise PmError("deadline must be YYYY-MM-DD.") from None
        prob = round(float(np.mean(total <= (dl - start_day).days)) * 100, 1)
    edges = np.linspace(total.min(), total.max(), 11)
    hist = np.histogram(total, bins=edges)[0].tolist()
    top = sorted(((crit_count[k] / n, nodes[k]["title"]) for k in order), reverse=True)[:5]
    plan = base["duration_days"]
    says = (f"Your plan says {plan:g} days, which this simulation reaches only {round(float(np.mean(total <= plan)) * 100)}% of the time. Plan on {q[80]:.0f} days for an 80% chance ({fin[80]}); {q[90]:.0f} days for 90%." if plan else "No duration to compare.")
    if prob is not None:
        says += f" Chance of finishing by {deadline}: {prob}%."
    return {"runs": n, "plan_days": plan, "plan_finish": base["finish"], "p10_days": round(q[10], 1), "p50_days": round(q[50], 1), "p80_days": round(q[80], 1), "p90_days": round(q[90], 1),
            "finish": {"p10": fin[10], "p50": fin[50], "p80": fin[80], "p90": fin[90]}, "deadline": deadline, "chance_by_deadline_pct": prob,
            "histogram": {"edges": [round(float(e), 1) for e in edges], "counts": hist}, "most_often_critical": [{"title": t, "share_pct": round(100 * s)} for s, t in top if s > 0],
            "ranges_used": f"each unfinished task from {int(opt * 100)}% faster to {int(pes * 100)}% slower than its estimate", "changes": notes, "says": says, "board_changed": False,
            "caution": "Only as good as the ranges you chose. Tasks are treated as independent, so a shared cause (a key person out, a late vendor) makes real life riskier than this."}


# ---------------------------------------------------------------- product


def run_product(changes: list[dict] | None = None, capacity: float | None = None, capacity_pct: float = 0.0) -> dict:
    items = [i for i in pm.list_items() if i["status"] != "done" and i["kind"] != "milestone"]
    scored = [i for i in items if pm.rice(i) is not None]
    if len(scored) < 2:
        raise PmError("Score at least two backlog items with reach, impact, confidence and effort (RICE) first.")
    mod = _copy(scored)
    notes = []
    for c in changes or []:
        if c.get("item_id") not in (None, ""):
            it = _find(mod, c["item_id"])
            f = c.get("field")
            if f not in ("reach", "impact", "confidence", "effort"):
                raise PmError("field must be reach, impact, confidence or effort.")
            old = it[f]
            it[f] = float(c["value"]) if c.get("value") is not None else old * _num(c.get("multiplier", 1), "multiplier", 0, 100)
            if f == "confidence":
                it[f] = min(1.0, it[f])
            notes.append(f"'{it['title']}': {f} {old:g} becomes {it[f]:g}.")
        elif c.get("field") in ("effort", "confidence", "reach", "impact") and c.get("pct") is not None:
            p = _num(c["pct"], "pct", -90, 500)
            for it in mod:
                it[c["field"]] = it[c["field"]] * (1 + p / 100)
                if c["field"] == "confidence":
                    it[c["field"]] = min(1.0, it[c["field"]])
            notes.append(f"Every item's {c['field']} changes by {p:+g}%.")
        else:
            raise PmError("A change needs item_id + field + (value or multiplier), or field + pct for everything.")
    rank = lambda xs: {i["id"]: n for n, i in enumerate(sorted(xs, key=lambda x: -(pm.rice(x) or 0)), 1)}   # noqa: E731
    r0, r1 = rank(scored), rank(mod)
    rows = [{"id": i["id"], "title": i["title"], "rice_before": pm._r(pm.rice(i)), "rice_after": pm._r(pm.rice(m)), "rank_before": r0[i["id"]], "rank_after": r1[i["id"]], "moved": r0[i["id"]] - r1[i["id"]]}
            for i, m in zip(scored, mod)]
    rows.sort(key=lambda r: r["rank_after"])
    total_eff = sum(i["effort"] for i in scored)
    cap0 = float(capacity) if capacity else round(total_eff * 0.5, 2)
    cap1 = cap0 * (1 + _num(capacity_pct, "capacity_pct", -90, 500) / 100)

    def fit(xs, cap):
        used, got = 0.0, []
        for x in sorted(xs, key=lambda x: -(pm.rice(x) or 0)):
            if used + x["effort"] <= cap + 1e-9:
                used += x["effort"]
                got.append(x["title"])
        return got, round(used, 2)
    f0, u0 = fit(scored, cap0)
    f1, u1 = fit(mod, cap1)
    says = f"With capacity {cap0:g}: ship {len(f0)} item(s). " + (f"With capacity {cap1:g} and your changes: {len(f1)} item(s). " if (changes or capacity_pct) else "")
    gained, lost = [t for t in f1 if t not in f0], [t for t in f0 if t not in f1]
    if gained:
        says += "Gained: " + ", ".join(gained) + ". "
    if lost:
        says += "Dropped: " + ", ".join(lost) + "."
    return {"changes": notes, "ranking": rows, "capacity_before": cap0, "capacity_after": round(cap1, 2), "ships_before": f0, "ships_after": f1, "effort_used_before": u0, "effort_used_after": u1,
            "says": says.strip(), "board_changed": False, "caution": "RICE ranks by a formula you fed with estimates; garbage in, garbage out. Treat ties and small gaps as ties."}


# ---------------------------------------------------------------- practice cases

CASES = {
    "website": {"title": "Website relaunch", "brief": "A small business is relaunching its website. Durations are in working days and costs in dollars.",
                "tasks": [("Define scope", 3, [], 1500), ("Design mock-ups", 6, [0], 3600), ("Write content", 8, [0], 2400), ("Build pages", 10, [1], 7000), ("Set up hosting", 2, [0], 600),
                          ("Load content", 4, [2, 3], 1600), ("Test and fix", 5, [5, 4], 3000), ("Launch", 1, [6], 500)]},
    "app_mvp": {"title": "Mobile app MVP", "brief": "A two-person team is building a first release of an app.",
                "tasks": [("User research", 5, [], 2500), ("Wireframes", 4, [0], 2000), ("Backend API", 12, [1], 9600), ("App screens", 10, [1], 8000), ("Payments", 6, [2], 4800),
                          ("Connect app to API", 5, [2, 3], 4000), ("Beta test", 7, [5, 4], 3500), ("Store submission", 3, [6], 1500)]},
    "repair_shop": {"title": "Opening a repair counter", "brief": "You are opening a small device-repair counter inside an existing shop.",
                    "tasks": [("Pick the space", 2, [], 400), ("Buy tools and parts", 5, [0], 3000), ("Permits and insurance", 9, [0], 900), ("Fit out the counter", 6, [0], 2400), ("Set up booking and invoicing", 4, [1], 800),
                              ("Write price list", 3, [1], 300), ("Soft launch", 3, [2, 3, 4, 5], 600)]},
}
PRODUCT_CASE = {"title": "Product roadmap choices", "brief": "Eight feature ideas, scored with RICE. Effort is person-weeks. You have a limited team capacity.",
                "features": [("One-click reorder", 800, 2, 0.8, 3), ("Dark mode", 1200, 0.5, 0.9, 2), ("Invoice export", 400, 2, 0.9, 2), ("Referral program", 600, 1, 0.5, 4), ("Mobile app", 1500, 2, 0.5, 12),
                             ("Search upgrade", 1000, 1, 0.8, 5), ("Bulk import", 300, 3, 0.7, 3), ("Team accounts", 500, 2, 0.6, 8)]}


def _case_items(kind: str, seed: int) -> list[dict]:
    spec = CASES[kind]
    rng = random.Random(f"{kind}-{seed}")
    items = []
    for n, (title, dur, deps, cost) in enumerate(spec["tasks"], 1):
        d = max(1, round(dur * rng.uniform(0.8, 1.25)))
        items.append({"id": n, "kind": "task", "title": title, "status": "todo", "duration_days": d, "deps": [x + 1 for x in deps], "planned_cost": round(cost * (d / dur), -1), "start_date": "2026-01-05"})
    return items


def practice(kind: str = "website", seed: int = 1, reveal: bool = False) -> dict:
    if kind == "product_roadmap":
        return _product_case(seed, reveal)
    if kind not in CASES:
        raise PmError("kind must be one of: " + ", ".join([*CASES, "product_roadmap"]) + ".")
    seed = int(seed) % 1000
    items = _case_items(kind, seed)
    cp = pm.critical_path(_copy(items), date(2026, 1, 5))
    by = {r["id"]: r for r in cp["rows"]}
    crit = [by[i]["title"] for i in cp["critical"]]
    slack = sorted((r for r in cp["rows"] if r["float"] > 0), key=lambda r: r["id"])
    qs = [{"q": "What is the shortest possible length of the project, in days?", "answer": f"{cp['duration_days']:g} days (the longest chain of dependent tasks)."},
          {"q": "Which tasks are on the critical path?", "answer": ", ".join(crit) + ". They have zero float: any slip delays the finish."}]
    if slack:
        s = slack[0]
        qs.append({"q": f"'{s['title']}' is not critical. How many days could it slip before it delays the finish?", "answer": f"{s['float']:g} days (its float = latest start minus earliest start)."})
    ct = next(r for r in cp["rows"] if r["critical"] and r["duration"] > 0)
    changed = _copy(items)
    next(i for i in changed if i["id"] == ct["id"])["duration_days"] += 4
    cp2 = pm.critical_path(changed, date(2026, 1, 5))
    qs.append({"q": f"'{ct['title']}' takes 4 days longer. What is the new project length?", "answer": f"{cp2['duration_days']:g} days: a slip on a critical task moves the finish one-for-one."})
    done = [i for i in items[:2]]
    bac = sum(i["planned_cost"] for i in items)
    ev = sum(i["planned_cost"] for i in done)
    ac = round(ev * 1.2, -1)
    qs.append({"q": f"Budget at completion is {bac:,.0f}. The first two tasks are finished and earned {ev:,.0f} of planned value, but cost {ac:,.0f} to do. What is the CPI, and what will the project cost at this rate?",
               "answer": f"CPI = EV/AC = {ev / ac:.2f}. Estimate at completion = BAC/CPI = {bac / (ev / ac):,.0f}."})
    out = {"id": f"{kind}-{seed}", "kind": kind, "title": CASES[kind]["title"], "brief": CASES[kind]["brief"],
           "tasks": [{"id": i["id"], "title": i["title"], "days": i["duration_days"], "after": i["deps"], "cost": i["planned_cost"]} for i in items], "questions": [{"q": q["q"]} for q in qs], "answers_hidden": not reveal}
    if reveal:
        out["questions"] = qs
    return out


def _product_case(seed: int, reveal: bool) -> dict:
    rng = random.Random(f"prod-{seed}")
    feats = [{"id": n, "title": t, "reach": round(r * rng.uniform(0.85, 1.2)), "impact": i, "confidence": c, "effort": e} for n, (t, r, i, c, e) in enumerate(PRODUCT_CASE["features"], 1)]
    for f in feats:
        f["rice"] = round(f["reach"] * f["impact"] * f["confidence"] / f["effort"], 1)
    ranked = sorted(feats, key=lambda f: -f["rice"])
    cap = 12
    used, ship = 0, []
    for f in ranked:
        if used + f["effort"] <= cap:
            used += f["effort"]
            ship.append(f["title"])
    top = ranked[0]
    f2 = [dict(f) for f in feats]
    next(f for f in f2 if f["id"] == top["id"])["effort"] *= 2
    for f in f2:
        f["rice"] = f["reach"] * f["impact"] * f["confidence"] / f["effort"]
    new_top = sorted(f2, key=lambda f: -f["rice"])[0]["title"]
    qs = [{"q": "Rank the features by RICE (reach x impact x confidence / effort). Which is first?", "answer": f"{top['title']} with RICE {top['rice']}."},
          {"q": f"The team can do {cap} person-weeks. Taking features in RICE order and skipping any that no longer fit, what ships?", "answer": ", ".join(ship) + f" ({used} person-weeks)."},
          {"q": f"If '{top['title']}' turns out to need twice the effort, which feature is first then?", "answer": f"{new_top}. Halving a score's divisor changes the order fast; this is why effort estimates deserve scrutiny."}]
    out = {"id": f"product_roadmap-{int(seed) % 1000}", "kind": "product_roadmap", "title": PRODUCT_CASE["title"], "brief": PRODUCT_CASE["brief"], "features": [{k: v for k, v in f.items() if k != "rice"} for f in feats],
           "questions": [{"q": q["q"]} for q in qs], "answers_hidden": not reveal}
    if reveal:
        out["questions"] = qs
    return out


def load_case(kind: str, seed: int = 1) -> dict:
    """Put a practice case on the board so it can be explored in every tab. Practice workspace only."""
    from app.services import workspaces
    if workspaces.active() != "practice":
        raise PmError("Practice cases can only be loaded into the Practice workspace, so they never mix with real projects.", 409)
    if kind not in CASES:
        raise PmError("Only the project cases can be loaded onto the board.")
    items = _case_items(kind, int(seed) % 1000)
    t0 = date(2026, 1, 5)
    ids: dict[int, int] = {}
    for i in items:
        data = {"kind": "task", "title": i["title"], "status": "todo", "duration_days": i["duration_days"], "planned_cost": i["planned_cost"], "start_date": t0.isoformat(), "deps": [ids[d] for d in i["deps"]]}
        ids[i["id"]] = pm.create_item(data)["id"]
    return {"loaded": len(items), "case": CASES[kind]["title"]}


TOOL_PM_SCENARIO = {
    "name": "pm_scenario", "description": "What-if analysis on the user's own Project & Product board (nothing on the board is changed). action 'schedule': changes = list of {kind: slip(item_id, days) | estimate_error(pct) | capacity_loss(pct) | "
    "add_work(title, duration_days, deps, cost, blocks) | remove(item_id) | cost_overrun(pct)} -> finish date, critical path and cost before and after. action 'simulate': 1,000 random schedules from optimistic/pessimistic ranges "
    "(optimistic_pct, pessimistic_pct, optional deadline YYYY-MM-DD, optional changes) -> P50/P80/P90 and chance of meeting the deadline. action 'product': re-rank the RICE backlog (changes: {item_id, field, multiplier|value} or {field, pct}; "
    "capacity, capacity_pct) -> rank moves and what fits. action 'practice': a practice case (kind website|app_mvp|repair_shop|product_roadmap, seed, reveal true to show answers). Always state the caution that comes back.",
    "input_schema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["schedule", "simulate", "product", "practice"]}, "changes": {"type": "array", "items": {"type": "object"}}, "optimistic_pct": {"type": "number"},
                                                      "pessimistic_pct": {"type": "number"}, "deadline": {"type": "string"}, "capacity": {"type": "number"}, "capacity_pct": {"type": "number"}, "kind": {"type": "string"}, "seed": {"type": "integer"}, "reveal": {"type": "boolean"}},
                     "required": ["action"]}}


def tool_result(args: dict) -> str:
    import json
    a = args or {}
    act = a.get("action")
    if act == "schedule":
        r = run_schedule(a.get("changes") or [])
    elif act == "simulate":
        r = simulate(1000, a.get("optimistic_pct", 20), a.get("pessimistic_pct", 50), a.get("deadline"), a.get("changes") or None)
    elif act == "product":
        r = run_product(a.get("changes") or [], a.get("capacity"), a.get("capacity_pct", 0) or 0)
    elif act == "practice":
        r = practice(str(a.get("kind") or "website"), int(a.get("seed") or 1), bool(a.get("reveal")))
    else:
        raise PmError("action must be schedule, simulate, product or practice.")
    return json.dumps(r, default=str)[:8000]
