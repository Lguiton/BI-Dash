"""Project and product management: work items, sprints, risks and OKRs, and the standard metrics computed from them.

Everything is stored per workspace in the state file (so Practice and Real never mix). The metric functions are pure: they take
plain lists and a date, so they can be checked by hand.

Formulas (all standard):
  RICE = reach x impact x confidence / effort          WSJF = (value + time criticality + risk reduction) / job size
  Velocity = story points completed per sprint        Cycle time = started -> done, lead time = created -> done
  Little's law: average WIP = throughput x average cycle time
  Critical path: earliest/latest start and finish, float = LS - ES
  Earned value: PV, EV, AC, CPI = EV/AC, SPI = EV/PV, EAC = BAC/CPI, ETC = EAC - AC, VAC = BAC - EAC, TCPI = (BAC - EV)/(BAC - AC)
  Risk exposure (expected monetary value) = probability x impact
"""
from __future__ import annotations

import json
import statistics
from datetime import date, datetime, timedelta

from app.services import state, workspaces

KINDS = ("epic", "story", "task", "bug", "milestone")
STATUSES = ("backlog", "todo", "doing", "review", "done")
MOSCOW = ("must", "should", "could", "wont")
RISK_STATUS = ("open", "mitigating", "closed", "occurred")
ITEM_FIELDS = ("kind", "title", "status", "priority", "owner", "sprint_id", "points", "reach", "impact", "confidence", "effort", "value",
               "time_crit", "risk_red", "moscow", "start_date", "duration_days", "deps", "planned_cost", "actual_cost",
               "created_at", "started_at", "done_at", "notes")
NUMERIC = {"priority", "sprint_id", "points", "reach", "impact", "confidence", "effort", "value", "time_crit", "risk_red", "duration_days", "planned_cost", "actual_cost"}
DATES = {"start_date", "created_at", "started_at", "done_at"}


class PmError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def today() -> date:
    return date.today()


def _d(v) -> date | None:
    if not v:
        return None
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        raise PmError(f"'{v}' is not a date (use YYYY-MM-DD).") from None


def _ws() -> str:
    return workspaces.active()


# ------------------------------------------------------------------ storage
def _clean_item(data: dict, partial: bool) -> dict:
    out: dict = {}
    for k in ITEM_FIELDS:
        if k not in data:
            continue
        v = data[k]
        if k in NUMERIC:
            if v in (None, ""):
                v = None
            else:
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    raise PmError(f"{k} must be a number.") from None
                if v < 0:
                    raise PmError(f"{k} can't be negative.")
                if k in ("priority", "sprint_id"):
                    v = int(v)
        elif k in DATES:
            v = _d(v).isoformat() if v else None
        elif k == "deps":
            ids = v if isinstance(v, list) else [x for x in str(v or "").replace(";", ",").split(",") if x.strip()]
            try:
                v = json.dumps(sorted({int(x) for x in ids}))
            except (TypeError, ValueError):
                raise PmError("deps must be item ids like 3, 5.") from None
        elif isinstance(v, str):
            v = v.strip()
        out[k] = v
    if "kind" in out and out["kind"] not in KINDS:
        raise PmError(f"kind must be one of {', '.join(KINDS)}.")
    if "status" in out and out["status"] not in STATUSES:
        raise PmError(f"status must be one of {', '.join(STATUSES)}.")
    if out.get("moscow") not in (None, "") + MOSCOW and "moscow" in out:
        raise PmError(f"moscow must be one of {', '.join(MOSCOW)}.")
    if "moscow" in out and out["moscow"] == "":
        out["moscow"] = None
    if "confidence" in out and out["confidence"] is not None and out["confidence"] > 1:
        raise PmError("confidence is a fraction between 0 and 1 (0.8 = 80%).")
    if not partial and not out.get("title"):
        raise PmError("Give the item a title.")
    if "title" in out and not out["title"]:
        raise PmError("Give the item a title.")
    return out


def _row_item(r: dict) -> dict:
    r = dict(r)
    r["deps"] = json.loads(r["deps"] or "[]")
    return r


def list_items() -> list[dict]:
    return [_row_item(r) for r in state.rows("SELECT * FROM pm_items WHERE workspace = ? ORDER BY priority, id", (_ws(),))]


def get_item(iid: int) -> dict:
    r = state.one("SELECT * FROM pm_items WHERE id = ? AND workspace = ?", (iid, _ws()))
    if not r:
        raise PmError("No such item.", 404)
    return _row_item(r)


def create_item(data: dict) -> dict:
    d = _clean_item(data, partial=False)
    d.setdefault("kind", "story")
    d.setdefault("status", "backlog")
    d.setdefault("created_at", today().isoformat())
    if d["status"] in ("doing", "review", "done"):
        d.setdefault("started_at", d["created_at"])
    if d["status"] == "done":
        d.setdefault("done_at", today().isoformat())
    d["workspace"] = _ws()
    cols = list(d)
    cur = state.run(f"INSERT INTO pm_items ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", [d[c] for c in cols])
    state.audit("pm_item_create", d["title"][:80])
    return get_item(cur.lastrowid)


def update_item(iid: int, data: dict) -> dict:
    old = get_item(iid)
    d = _clean_item(data, partial=True)
    new_status = d.get("status", old["status"])
    if new_status != old["status"]:
        t = today().isoformat()
        if new_status in ("doing", "review", "done") and not (d.get("started_at") or old["started_at"]):
            d["started_at"] = t
        if new_status == "done":
            d.setdefault("done_at", t)
        elif old["status"] == "done":
            d["done_at"] = None
        if new_status in ("backlog", "todo"):
            d["started_at"] = None
    if "deps" in d and iid in json.loads(d["deps"]):
        raise PmError("An item can't depend on itself.")
    if d:
        state.run(f"UPDATE pm_items SET {', '.join(f'{k} = ?' for k in d)} WHERE id = ? AND workspace = ?", [*d.values(), iid, _ws()])
        state.audit("pm_item_update", f"#{iid} {old['title'][:60]}: {', '.join(d)}")
    return get_item(iid)


def delete_item(iid: int) -> None:
    it = get_item(iid)
    state.run("DELETE FROM pm_items WHERE id = ? AND workspace = ?", (iid, _ws()))
    for o in list_items():       # nothing may keep depending on a deleted item
        if iid in o["deps"]:
            state.run("UPDATE pm_items SET deps = ? WHERE id = ?", (json.dumps([x for x in o["deps"] if x != iid]), o["id"]))
    state.audit("pm_item_delete", it["title"][:80])


def list_sprints() -> list[dict]:
    return state.rows("SELECT * FROM pm_sprints WHERE workspace = ? ORDER BY start_date, id", (_ws(),))


def save_sprint(data: dict, sid: int | None = None) -> dict:
    name = str(data.get("name", "")).strip()
    s, e = _d(data.get("start_date")), _d(data.get("end_date"))
    if not name or not s or not e:
        raise PmError("A sprint needs a name, a start date and an end date.")
    if e < s:
        raise PmError("The sprint can't end before it starts.")
    if sid is None:
        cur = state.run("INSERT INTO pm_sprints (workspace, name, start_date, end_date, goal) VALUES (?,?,?,?,?)", (_ws(), name, s.isoformat(), e.isoformat(), str(data.get("goal", ""))[:200]))
        sid = cur.lastrowid
    else:
        if not state.one("SELECT 1 FROM pm_sprints WHERE id = ? AND workspace = ?", (sid, _ws())):
            raise PmError("No such sprint.", 404)
        state.run("UPDATE pm_sprints SET name=?, start_date=?, end_date=?, goal=? WHERE id=?", (name, s.isoformat(), e.isoformat(), str(data.get("goal", ""))[:200], sid))
    state.audit("pm_sprint_save", name)
    return state.one("SELECT * FROM pm_sprints WHERE id = ?", (sid,))


def delete_sprint(sid: int) -> None:
    state.run("UPDATE pm_items SET sprint_id = NULL WHERE sprint_id = ? AND workspace = ?", (sid, _ws()))
    state.run("DELETE FROM pm_sprints WHERE id = ? AND workspace = ?", (sid, _ws()))


def list_risks() -> list[dict]:
    return state.rows("SELECT * FROM pm_risks WHERE workspace = ? ORDER BY probability * impact_usd DESC, id", (_ws(),))


def save_risk(data: dict, rid: int | None = None) -> dict:
    title = str(data.get("title", "")).strip()
    try:
        p, imp = float(data.get("probability")), float(data.get("impact_usd", 0))
    except (TypeError, ValueError):
        raise PmError("probability (0-1) and impact_usd must be numbers.") from None
    if not title:
        raise PmError("Give the risk a title.")
    if not 0 <= p <= 1:
        raise PmError("probability is a fraction between 0 and 1 (0.3 = 30%).")
    if imp < 0:
        raise PmError("impact_usd can't be negative.")
    status = data.get("status") or "open"
    if status not in RISK_STATUS:
        raise PmError(f"status must be one of {', '.join(RISK_STATUS)}.")
    vals = (title[:120], p, imp, status, str(data.get("owner", ""))[:60], str(data.get("mitigation", ""))[:300])
    if rid is None:
        cur = state.run("INSERT INTO pm_risks (workspace, title, probability, impact_usd, status, owner, mitigation, created_at) VALUES (?,?,?,?,?,?,?,?)", (_ws(), *vals, today().isoformat()))
        rid = cur.lastrowid
    else:
        if not state.one("SELECT 1 FROM pm_risks WHERE id = ? AND workspace = ?", (rid, _ws())):
            raise PmError("No such risk.", 404)
        state.run("UPDATE pm_risks SET title=?, probability=?, impact_usd=?, status=?, owner=?, mitigation=? WHERE id=?", (*vals, rid))
    state.audit("pm_risk_save", title[:80])
    return state.one("SELECT * FROM pm_risks WHERE id = ?", (rid,))


def delete_risk(rid: int) -> None:
    state.run("DELETE FROM pm_risks WHERE id = ? AND workspace = ?", (rid, _ws()))


def list_okrs() -> list[dict]:
    return state.rows("SELECT * FROM pm_okrs WHERE workspace = ? ORDER BY objective, id", (_ws(),))


def save_okr(data: dict, oid: int | None = None) -> dict:
    obj, kr = str(data.get("objective", "")).strip(), str(data.get("kr", "")).strip()
    if not obj or not kr:
        raise PmError("An OKR needs an objective and a key result.")
    try:
        a, t, c = (float(data.get(k)) for k in ("start_value", "target_value", "current_value"))
    except (TypeError, ValueError):
        raise PmError("start_value, target_value and current_value must be numbers.") from None
    if a == t:
        raise PmError("The target must differ from the starting value.")
    vals = (obj[:120], kr[:160], a, t, c, str(data.get("owner", ""))[:60])
    if oid is None:
        cur = state.run("INSERT INTO pm_okrs (workspace, objective, kr, start_value, target_value, current_value, owner) VALUES (?,?,?,?,?,?,?)", (_ws(), *vals))
        oid = cur.lastrowid
    else:
        if not state.one("SELECT 1 FROM pm_okrs WHERE id = ? AND workspace = ?", (oid, _ws())):
            raise PmError("No such key result.", 404)
        state.run("UPDATE pm_okrs SET objective=?, kr=?, start_value=?, target_value=?, current_value=?, owner=? WHERE id=?", (*vals, oid))
    state.audit("pm_okr_save", f"{obj[:60]}: {kr[:60]}")
    return state.one("SELECT * FROM pm_okrs WHERE id = ?", (oid,))


def delete_okr(oid: int) -> None:
    state.run("DELETE FROM pm_okrs WHERE id = ? AND workspace = ?", (oid, _ws()))


# ------------------------------------------------------------------ pure metrics
def _pct(vals: list[float], q: float) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def _r(v, n=2):
    return None if v is None else round(v, n)


def rice(it: dict) -> float | None:
    if None in (it.get("reach"), it.get("impact"), it.get("confidence"), it.get("effort")) or not it["effort"]:
        return None
    return it["reach"] * it["impact"] * it["confidence"] / it["effort"]


def wsjf(it: dict) -> float | None:
    if None in (it.get("value"), it.get("time_crit"), it.get("risk_red"), it.get("points")) or not it["points"]:
        return None
    return (it["value"] + it["time_crit"] + it["risk_red"]) / it["points"]


def prioritization(items: list[dict]) -> dict:
    open_items = [i for i in items if i["status"] != "done" and i["kind"] != "milestone"]
    rows = []
    for i in open_items:
        rows.append({"id": i["id"], "title": i["title"], "kind": i["kind"], "status": i["status"], "moscow": i["moscow"], "points": i["points"],
                     "rice": _r(rice(i)), "wsjf": _r(wsjf(i))})
    by_rice = sorted([r for r in rows if r["rice"] is not None], key=lambda r: -r["rice"])
    for n, r in enumerate(by_rice, 1):
        r["rice_rank"] = n
    by_w = sorted([r for r in rows if r["wsjf"] is not None], key=lambda r: -r["wsjf"])
    for n, r in enumerate(by_w, 1):
        r["wsjf_rank"] = n
    moscow = {m: {"items": 0, "points": 0.0} for m in MOSCOW}
    unclassified = 0
    for i in open_items:
        if i["moscow"] in moscow:
            moscow[i["moscow"]]["items"] += 1
            moscow[i["moscow"]]["points"] += i["points"] or 0
        else:
            unclassified += 1
    total_pts = sum(v["points"] for v in moscow.values())
    return {"rows": sorted(rows, key=lambda r: (r.get("rice_rank") or 9999, r["id"])), "moscow": moscow, "moscow_unclassified": unclassified,
            "must_share_pct": _r(100 * moscow["must"]["points"] / total_pts, 1) if total_pts else None,
            "unscored": sum(1 for r in rows if r["rice"] is None)}


def flow(items: list[dict], as_of: date) -> dict:
    done = [i for i in items if i["status"] == "done" and i["done_at"] and i["kind"] != "milestone"]
    cycle = [max((_d(i["done_at"]) - _d(i["started_at"])).days, 0) for i in done if i["started_at"]]
    lead = [max((_d(i["done_at"]) - _d(i["created_at"])).days, 0) for i in done if i["created_at"]]
    weeks = []
    monday = as_of - timedelta(days=as_of.weekday())
    for w in range(7, -1, -1):
        s = monday - timedelta(weeks=w)
        e = s + timedelta(days=6)
        weeks.append({"week": s.isoformat(), "done": sum(1 for i in done if s <= _d(i["done_at"]) <= e)})
    wip = [i for i in items if i["status"] in ("doing", "review")]
    last4 = sum(w["done"] for w in weeks[-4:]) / 28.0
    avg_cycle = statistics.fmean(cycle) if cycle else None
    days = [as_of - timedelta(days=n) for n in range(29, -1, -1)]
    cfd = []
    for dd in days:
        n_done = n_doing = n_todo = 0
        for i in items:
            if i["kind"] == "milestone":
                continue
            c = _d(i["created_at"])
            if c is None or c > dd:
                continue
            dn, st = _d(i["done_at"]), _d(i["started_at"])
            if dn and dn <= dd:
                n_done += 1
            elif st and st <= dd:
                n_doing += 1
            else:
                n_todo += 1
        cfd.append({"day": dd.isoformat(), "todo": n_todo, "doing": n_doing, "done": n_done})
    return {"done_count": len(done), "cycle_days": {"avg": _r(avg_cycle, 1), "median": _r(_pct(cycle, .5), 1), "p85": _r(_pct(cycle, .85), 1), "n": len(cycle)},
            "lead_days": {"avg": _r(statistics.fmean(lead), 1) if lead else None, "median": _r(_pct(lead, .5), 1), "p85": _r(_pct(lead, .85), 1), "n": len(lead)},
            "throughput_weekly": weeks, "wip": len(wip),
            "littles_law": {"throughput_per_day": _r(last4, 3), "avg_cycle_days": _r(avg_cycle, 1),
                            "expected_wip": _r(last4 * avg_cycle, 1) if avg_cycle is not None else None, "actual_wip": len(wip)},
            "cfd": cfd}


def sprints_view(items: list[dict], sprints: list[dict], as_of: date) -> dict:
    out, vel = [], []
    for s in sprints:
        mine = [i for i in items if i["sprint_id"] == s["id"] and i["kind"] != "milestone"]
        committed = sum(i["points"] or 0 for i in mine)
        completed = sum((i["points"] or 0) for i in mine if i["status"] == "done")
        ended = _d(s["end_date"]) < as_of
        row = {**s, "committed": committed, "completed": completed, "items": len(mine), "ended": ended,
               "completion_pct": _r(100 * completed / committed, 1) if committed else None}
        out.append(row)
        if ended and committed:
            vel.append(completed)
    recent = vel[-3:]
    avg_vel = statistics.fmean(recent) if recent else None
    active = next((s for s in sprints if _d(s["start_date"]) <= as_of <= _d(s["end_date"])), None)
    burn = None
    if active:
        s0, s1 = _d(active["start_date"]), _d(active["end_date"])
        mine = [i for i in items if i["sprint_id"] == active["id"] and i["kind"] != "milestone"]
        total = sum(i["points"] or 0 for i in mine)
        n = (s1 - s0).days
        pts = []
        for k in range(n + 1):
            dd = s0 + timedelta(days=k)
            rem = None if dd > as_of else total - sum(i["points"] or 0 for i in mine if i["done_at"] and _d(i["done_at"]) <= dd)
            pts.append({"day": dd.isoformat(), "ideal": _r(total * (1 - k / n), 2) if n else 0, "actual": rem})
        today_rem = next((p["actual"] for p in reversed(pts) if p["actual"] is not None), total)
        elapsed = (as_of - s0).days
        ideal_now = total * (1 - elapsed / n) if n else 0
        burn = {"sprint": active["name"], "committed": total, "remaining": today_rem, "points": pts,
                "status": "no points committed" if not total else "ahead of plan" if today_rem < ideal_now - 0.5 else "behind plan" if today_rem > ideal_now + 0.5 else "on plan"}
    remaining = sum((i["points"] or 0) for i in items if i["status"] != "done" and i["kind"] in ("story", "task", "bug"))
    length = statistics.fmean([(_d(s["end_date"]) - _d(s["start_date"])).days + 1 for s in sprints]) if sprints else 14
    fc = None
    if recent and avg_vel:
        def finish(v):
            n = remaining / v if v else None
            return None if n is None else {"sprints": _r(n, 1), "date": (as_of + timedelta(days=round(n * length))).isoformat()}
        fc = {"remaining_points": remaining, "avg_velocity": _r(avg_vel, 1), "likely": finish(avg_vel), "fast": finish(max(recent)), "slow": finish(min(recent) or None),
              "note": "Based on the last three finished sprints. Real delivery varies, so read the range, not one date."}
    return {"sprints": out, "velocity": {"history": vel, "avg_last3": _r(avg_vel, 1)}, "burndown": burn, "forecast": fc}


def critical_path(items: list[dict], as_of: date) -> dict:
    nodes = {i["id"]: i for i in items if (i["duration_days"] or 0) > 0 or i["kind"] == "milestone"}
    for i in nodes.values():
        i["_dur"] = i["duration_days"] or 0
    ignored = sorted({d for i in nodes.values() for d in i["deps"] if d not in nodes})
    deps = {k: [d for d in v["deps"] if d in nodes] for k, v in nodes.items()}
    order, seen, temp = [], set(), set()
    cyc: list[int] = []

    def visit(n):
        if n in seen:
            return
        if n in temp:
            cyc.append(n)
            return
        temp.add(n)
        for d in deps[n]:
            visit(d)
        temp.discard(n)
        seen.add(n)
        order.append(n)

    for n in sorted(nodes):
        visit(n)
    if cyc:
        return {"available": False, "reason": "The dependencies loop back on themselves (" + ", ".join(f"#{c} {nodes[c]['title']}" for c in cyc[:3]) + "). A schedule can't have a cycle."}
    if not nodes:
        return {"available": False, "reason": "Give items a duration in days (and dependencies) to see the critical path."}
    es, ef = {}, {}
    for n in order:
        es[n] = max((ef[d] for d in deps[n]), default=0)
        ef[n] = es[n] + nodes[n]["_dur"]
    total = max(ef.values())
    succ = {n: [m for m in nodes if n in deps[m]] for n in nodes}
    ls, lf = {}, {}
    for n in reversed(order):
        lf[n] = min((ls[m] for m in succ[n]), default=total)
        ls[n] = lf[n] - nodes[n]["_dur"]
    starts = [_d(i["start_date"]) for i in nodes.values() if i["start_date"]]
    base = min(starts) if starts else as_of
    rows = []
    for n in sorted(nodes, key=lambda x: (es[x], x)):
        fl = ls[n] - es[n]
        rows.append({"id": n, "title": nodes[n]["title"], "status": nodes[n]["status"], "duration": nodes[n]["_dur"], "es": es[n], "ef": ef[n], "ls": ls[n], "lf": lf[n],
                     "float": fl, "critical": abs(fl) < 1e-9, "deps": deps[n], "start": (base + timedelta(days=es[n])).isoformat(), "finish": (base + timedelta(days=ef[n])).isoformat()})
    return {"available": True, "duration_days": total, "finish": (base + timedelta(days=total)).isoformat(), "rows": rows,
            "critical": [r["id"] for r in rows if r["critical"]], "unknown_dependencies": ignored, "project_start": base.isoformat()}


def earned_value(items: list[dict], as_of: date) -> dict:
    with_cost = [i for i in items if i["planned_cost"]]
    if not with_cost:
        return {"available": False, "reason": "Give items a planned cost, a start date and a duration to get earned-value numbers."}
    bac = sum(i["planned_cost"] for i in with_cost)
    pv = ev = 0.0
    unscheduled = 0
    for i in with_cost:
        s, dur = _d(i["start_date"]), i["duration_days"]
        if s and dur:
            frac = min(max((as_of - s).days / dur, 0.0), 1.0)
            pv += i["planned_cost"] * frac
        else:
            unscheduled += 1
        if i["status"] == "done":
            ev += i["planned_cost"]            # the 0/100 rule: work earns its value only when finished
    tm, rate = _time_by_item(), get_rate()
    from_time = 0

    def eff(i):
        nonlocal from_time
        h = tm.get(i["id"])
        if rate and h:
            from_time += 1
            return h * rate
        return i["actual_cost"] or 0
    ac = sum(eff(i) for i in items)
    cpi = ev / ac if ac else None
    spi = ev / pv if pv else None
    eac = bac / cpi if cpi else None
    return {"available": True, "as_of": as_of.isoformat(), "bac": _r(bac), "pv": _r(pv), "ev": _r(ev), "ac": _r(ac), "cpi": _r(cpi, 3), "spi": _r(spi, 3),
            "cv": _r(ev - ac), "sv": _r(ev - pv), "eac": _r(eac), "etc": _r(eac - ac) if eac is not None else None, "vac": _r(bac - eac) if eac is not None else None,
            "tcpi": _r((bac - ev) / (bac - ac), 3) if bac != ac else None, "unscheduled_items": unscheduled, "items_costed_from_time": from_time,
            "reading": ("No cost or progress data yet." if cpi is None or spi is None else
                        f"{'Under' if cpi >= 1 else 'Over'} budget (CPI {cpi:.2f}) and {'ahead of' if spi >= 1 else 'behind'} schedule (SPI {spi:.2f})."),
            "rule": "Earned value uses the 0/100 rule: an item counts only when it is done."}


# ------------------------------------------------------------------ time tracking
def get_rate() -> float:
    try:
        return float(state.setting_get(_ws(), "pm_rate", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def set_rate(rate) -> dict:
    try:
        v = float(rate)
    except (TypeError, ValueError):
        raise PmError("The hourly rate must be a number.") from None
    if not 0 <= v <= 10000:
        raise PmError("The hourly rate must be between 0 and 10,000 dollars.")
    state.setting_set(_ws(), "pm_rate", round(v, 2))
    state.audit("pm_rate", f"${v:,.2f}/h")
    return {"rate": round(v, 2)}


def _time_by_item() -> dict[int, float]:
    return {r["item_id"]: r["h"] for r in state.rows("SELECT item_id, SUM(hours) AS h FROM pm_time WHERE workspace = ? AND item_id IS NOT NULL GROUP BY item_id", (_ws(),))}


def time_log(item_id, day: str | None, hours, note: str = "") -> dict:
    try:
        h = float(hours)
    except (TypeError, ValueError):
        raise PmError("Hours must be a number.") from None
    if not 0 < h <= 24:
        raise PmError("Log between 0 and 24 hours per entry.")
    d = _d(day) if day else today()
    if d is None:
        raise PmError("Use a date like 2026-10-09.")
    if d > today():
        raise PmError("You can't log time in the future.")
    if (today() - d).days > 366:
        raise PmError("That date is more than a year ago.")
    iid = None
    if item_id not in (None, ""):
        try:
            iid = int(item_id)
        except (TypeError, ValueError):
            raise PmError("Pick an item from the list.") from None
        get_item(iid)
    cur = state.run("INSERT INTO pm_time (workspace, item_id, day, hours, note, created_at) VALUES (?,?,?,?,?,?)",
                    (_ws(), iid, d.isoformat(), round(h, 2), str(note or "")[:200].strip(), state.now()))
    state.audit("pm_time", f"{h:g}h on {d.isoformat()}")
    return state.one("SELECT * FROM pm_time WHERE id = ?", (cur.lastrowid,))


def time_delete(tid: int) -> None:
    if not state.one("SELECT id FROM pm_time WHERE id = ? AND workspace = ?", (tid, _ws())):
        raise PmError("No such time entry.", 404)
    state.run("DELETE FROM pm_time WHERE id = ? AND workspace = ?", (tid, _ws()))


def time_view() -> dict:
    rate = get_rate()
    items = {i["id"]: i for i in list_items()}
    entries = state.rows("SELECT * FROM pm_time WHERE workspace = ? ORDER BY day DESC, id DESC LIMIT 300", (_ws(),))
    per = _time_by_item()
    by_item = []
    for iid, h in sorted(per.items(), key=lambda kv: -kv[1]):
        it = items.get(iid)
        if not it:
            continue
        cost = h * rate if rate else None
        by_item.append({"item_id": iid, "title": it["title"], "status": it["status"], "hours": _r(h), "cost": _r(cost) if cost is not None else None,
                        "planned_cost": it["planned_cost"], "over_plan": bool(cost is not None and it["planned_cost"] and cost > it["planned_cost"])})
    weeks: dict[str, float] = {}
    for e in state.rows("SELECT day, hours FROM pm_time WHERE workspace = ?", (_ws(),)):
        dd = _d(e["day"])
        if dd:
            monday = (dd - timedelta(days=dd.weekday())).isoformat()
            weeks[monday] = weeks.get(monday, 0) + e["hours"]
    total = sum(e["hours"] for e in state.rows("SELECT hours FROM pm_time WHERE workspace = ?", (_ws(),)))
    unassigned = sum(e["hours"] for e in state.rows("SELECT hours FROM pm_time WHERE workspace = ? AND item_id IS NULL", (_ws(),)))
    for e in entries:
        e["item_title"] = items[e["item_id"]]["title"] if e["item_id"] in items else ("" if e["item_id"] is None else "(deleted item)")
    return {"rate": rate, "entries": entries, "total_hours": _r(total), "unassigned_hours": _r(unassigned), "cost": _r(total * rate) if rate else None,
            "by_item": by_item, "weeks": [{"week": k, "hours": _r(v)} for k, v in sorted(weeks.items())[-12:]],
            "feeds_earned_value": bool(rate and per),
            "note": ("Hours on an item replace the typed actual cost in earned value (hours x rate). Unassigned hours are tracked but not charged to any item."
                     if rate else "Set an hourly rate and logged hours will drive earned value: actual cost = hours x rate.")}


def risk_view(risks: list[dict]) -> dict:
    live = [r for r in risks if r["status"] in ("open", "mitigating")]
    rows = [{**r, "emv": _r(r["probability"] * r["impact_usd"])} for r in risks]
    mx = max((r["impact_usd"] for r in live), default=0) or 1

    def pb(p): return 0 if p < 0.25 else 1 if p < 0.6 else 2
    def ib(v): return 0 if v < mx / 3 else 1 if v < 2 * mx / 3 else 2
    grid = [[0] * 3 for _ in range(3)]          # grid[impact][probability]
    for r in live:
        grid[ib(r["impact_usd"])][pb(r["probability"])] += 1
    return {"risks": rows, "open_count": len(live), "exposure": _r(sum(r["probability"] * r["impact_usd"] for r in live)),
            "matrix": grid, "matrix_note": "Rows: impact (low to high, in thirds of your largest risk). Columns: probability (under 25%, 25-60%, over 60%).",
            "reserve_hint": "Total exposure is the expected cost of everything still open: a starting point for a contingency reserve."}


def okr_view(okrs: list[dict]) -> dict:
    objs: dict[str, list] = {}
    for k in okrs:
        prog = (k["current_value"] - k["start_value"]) / (k["target_value"] - k["start_value"])
        objs.setdefault(k["objective"], []).append({**k, "progress_pct": _r(100 * max(0.0, min(prog, 1.0)), 1)})
    return {"objectives": [{"objective": o, "progress_pct": _r(statistics.fmean(x["progress_pct"] for x in krs), 1), "key_results": krs} for o, krs in objs.items()],
            "note": "Progress is (current - start) / (target - start), capped between 0 and 100%. Around 70% on a stretch goal is considered healthy."}


def overview(as_of: date | None = None) -> dict:
    as_of = as_of or today()
    items, sprints = list_items(), list_sprints()
    by_status = {s: [i for i in items if i["status"] == s] for s in STATUSES}
    return {"as_of": as_of.isoformat(), "items": items, "counts": {s: len(v) for s, v in by_status.items()}, "empty": not items,
            "prioritization": prioritization(items), "flow": flow(items, as_of), "sprint": sprints_view(items, sprints, as_of),
            "schedule": critical_path(items, as_of), "earned_value": earned_value(items, as_of),
            "risks": risk_view(list_risks()), "okrs": okr_view(list_okrs()), "enums": {"kinds": KINDS, "statuses": STATUSES, "moscow": MOSCOW, "risk_status": RISK_STATUS}}


# ------------------------------------------------------------------ product analytics on the workspace's own data
def product_analytics() -> dict:
    """Treat entities as accounts and records as their activity: active accounts, stickiness, status funnel and monthly retention cohorts."""
    from app.services.db import fetch_all, fetch_one, get_cursor
    with get_cursor() as cur:
        meta = fetch_one(cur, "SELECT COUNT(*) AS n, MAX(record_date) AS last, MIN(record_date) AS first FROM fact_operations")
        if not meta["n"]:
            return {"available": False, "reason": "Import operations data to get active-account, funnel and retention numbers."}
        last = meta["last"]
        stick = fetch_one(cur, """WITH d AS (SELECT record_date AS day, COUNT(DISTINCT entity_id) AS dau FROM fact_operations
                WHERE record_date > ? - INTERVAL 30 DAY GROUP BY 1)
            SELECT AVG(dau) AS avg_dau, (SELECT COUNT(DISTINCT entity_id) FROM fact_operations WHERE record_date > ? - INTERVAL 30 DAY) AS mau FROM d""", [last, last])
        weekly = fetch_all(cur, """SELECT strftime(date_trunc('week', record_date), '%Y-%m-%d') AS week, COUNT(DISTINCT entity_id) AS active, COUNT(*) AS records
            FROM fact_operations GROUP BY 1 ORDER BY 1 DESC LIMIT 12""")[::-1]
        funnel = fetch_all(cur, "SELECT COALESCE(status, 'Unknown') AS stage, COUNT(*) AS n FROM fact_operations GROUP BY 1 ORDER BY 2 DESC")
        cohort_rows = fetch_all(cur, """WITH first AS (SELECT entity_id, date_trunc('month', MIN(record_date)) AS cohort FROM fact_operations GROUP BY 1),
              act AS (SELECT DISTINCT entity_id, date_trunc('month', record_date) AS m FROM fact_operations)
            SELECT strftime(f.cohort, '%Y-%m') AS cohort, date_diff('month', f.cohort, a.m) AS k, COUNT(*) AS n
            FROM first f JOIN act a USING (entity_id) GROUP BY 1, 2 ORDER BY 1, 2""")
    cohorts: dict[str, dict[int, int]] = {}
    for r in cohort_rows:
        cohorts.setdefault(r["cohort"], {})[r["k"]] = r["n"]
    matrix = []
    for c in sorted(cohorts)[-8:]:
        base = cohorts[c].get(0, 0)
        matrix.append({"cohort": c, "size": base, "retention": [(_r(100 * cohorts[c][k] / base, 1) if k in cohorts[c] and base else None) for k in range(0, 7)]})
    total = sum(f["n"] for f in funnel)
    stage = [{**f, "share_pct": _r(100 * f["n"] / total, 1)} for f in funnel]
    avg_dau = stick["avg_dau"]
    return {"available": True, "last_day": str(last), "avg_dau": _r(avg_dau, 1), "mau": stick["mau"],
            "stickiness_pct": _r(100 * avg_dau / stick["mau"], 1) if stick["mau"] and avg_dau else None, "weekly_active": weekly, "funnel": stage, "cohorts": matrix,
            "mapping": "Entities stand in for accounts or users, and each record is one unit of activity. A cohort is the month an entity first appears; retention is the share still active k months later.",
            "stickiness_note": "Stickiness = average daily actives / monthly actives. Around 20% is common for business tools."}


# ------------------------------------------------------------------ worked example (Practice only)
def load_example() -> dict:
    if _ws() != "practice":
        raise PmError("The example project is only for the Practice workspace, so it can't be mixed into your real project.", 409)
    if list_items() or list_sprints():
        raise PmError("This workspace already has project data. Delete it first if you want the example.", 409)
    t = today()
    day = lambda n: (t + timedelta(days=n)).isoformat()   # noqa: E731
    s1 = save_sprint({"name": "Sprint 1", "start_date": day(-34), "end_date": day(-21), "goal": "Data model and import"})["id"]
    s2 = save_sprint({"name": "Sprint 2", "start_date": day(-20), "end_date": day(-7), "goal": "Dashboards"})["id"]
    s3 = save_sprint({"name": "Sprint 3", "start_date": day(-6), "end_date": day(7), "goal": "Sources, backups, privacy"})["id"]

    def it(title, kind="story", status="backlog", sprint=None, pts=None, created=-30, started=None, done=None, deps=(), **kw):
        d = dict(title=title, kind=kind, status=status, sprint_id=sprint, points=pts, created_at=day(created), deps=list(deps), **kw)
        if started is not None:
            d["started_at"] = day(started)
        if done is not None:
            d["done_at"] = day(done)
        return create_item(d)["id"]
    a = it("Design the data model", "task", "done", s1, 5, -38, -34, -28, start_date=day(-34), duration_days=3, planned_cost=2400, actual_cost=2600, owner="Lam", moscow="must")
    b = it("CSV import with validation", "story", "done", s1, 8, -38, -28, -22, deps=[a], start_date=day(-28), duration_days=6, planned_cost=4800, actual_cost=5200, owner="Lam", moscow="must", reach=100, impact=3, confidence=0.9, effort=2)
    c = it("KPI dashboard", "story", "done", s2, 8, -30, -20, -13, deps=[b], start_date=day(-20), duration_days=6, planned_cost=4800, actual_cost=4500, owner="Lam", moscow="must", reach=100, impact=3, confidence=0.9, effort=2)
    d = it("Chart gallery", "story", "done", s2, 5, -30, -14, -8, deps=[c], start_date=day(-14), duration_days=5, planned_cost=3000, actual_cost=3300, owner="Lam", moscow="should", reach=80, impact=2, confidence=0.8, effort=1.5)
    e = it("Workspaces: Practice and Real", "story", "doing", s3, 8, -12, -5, None, deps=[c], start_date=day(-5), duration_days=7, planned_cost=4800, actual_cost=3000, owner="Lam", moscow="must", reach=100, impact=3, confidence=0.8, effort=2)
    f = it("Scheduled source refresh", "story", "doing", s3, 5, -12, -3, None, deps=[e], start_date=day(-3), duration_days=6, planned_cost=3000, actual_cost=1200, owner="Lam", moscow="should", reach=60, impact=2, confidence=0.7, effort=1.5)
    g = it("Backups and restore", "story", "todo", s3, 5, -10, None, None, deps=[e], start_date=day(1), duration_days=4, planned_cost=2400, owner="Lam", moscow="must", reach=100, impact=2, confidence=0.9, effort=1)
    h = it("AI privacy modes", "story", "todo", s3, 3, -10, None, None, deps=[e], start_date=day(2), duration_days=3, planned_cost=1800, owner="Lam", moscow="should", reach=40, impact=2, confidence=0.8, effort=1)
    i = it("Fix: dates shown a day early in UTC", "bug", "backlog", None, 2, -2, None, None, moscow="must", value=8, time_crit=13, risk_red=5)
    j = it("Role-based logins", "epic", "backlog", None, 21, -25, None, None, moscow="wont", reach=5, impact=1, confidence=0.5, effort=8, value=5, time_crit=2, risk_red=8)
    k = it("Hosted deployment", "epic", "backlog", None, 13, -25, None, None, deps=[j], moscow="could", reach=20, impact=2, confidence=0.4, effort=5, value=8, time_crit=3, risk_red=13)
    it("Release 1.0", "milestone", "backlog", None, None, -25, deps=[g, h, f], start_date=day(8), duration_days=0, planned_cost=0)
    for ttl, p, imp, own, mit in [("Scheduled refresh overwrites good data with a bad export", 0.3, 8000, "Lam", "Shrink guard plus automatic safety backup"),
                                  ("Single-writer database blocks a command-line refresh", 0.5, 1500, "Lam", "Stop the API first; documented"),
                                  ("AI provider outage during a demo", 0.2, 3000, "Lam", "Three providers with fallback"),
                                  ("Scope creep from hosting and logins", 0.6, 12000, "Lam", "Defer both; decide after Release 1.0")]:
        save_risk({"title": ttl, "probability": p, "impact_usd": imp, "owner": own, "mitigation": mit})
    for kr, a0, tg, cur_ in [("Import works on any CSV the user brings", 0, 10, 8), ("Backend tests passing", 0, 250, 211), ("Pages with no console errors", 0, 14, 14)]:
        save_okr({"objective": "Make the dashboard usable for real data", "kr": kr, "start_value": a0, "target_value": tg, "current_value": cur_, "owner": "Lam"})
    del d, i, k
    return {"items": len(list_items()), "sprints": 3}
