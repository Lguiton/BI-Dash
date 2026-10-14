"""Project calendar and simple automations for the board.

Calendar: items with a start date and duration appear as bars across calendar days; sprints appear as bands.
Automations: "if this, then that" rules over your own board. They are checked when you press Preview or Run (not in the background),
and Preview shows exactly what would change before anything does. No external apps are involved.
  triggers: overdue (start + duration is before today and the item isn't done), stuck (in doing/review for N+ days)
  actions:  set_priority (1 to 5), add_note (text), move_status (to a status)
"""
from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta

from app.services import pm, state

TRIGGERS = {"overdue": "Item is past its planned end and not done", "stuck": "Item has been in doing or review for N or more days"}
ACTIONS = {"set_priority": "Set priority (1 is highest)", "add_note": "Append a note to the item", "move_status": "Move the item to a status"}
MAX_RULES = 20
MAX_SPAN_DAYS = 120


def _day(v) -> date | None:
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date() if v else None
    except ValueError:
        return None


def _month(m: str | None) -> tuple[date, date]:
    try:
        first = datetime.strptime((m or "")[:7], "%Y-%m").date() if m else pm.today().replace(day=1)
    except ValueError:
        raise pm.PmError("month must look like 2026-10.") from None
    last = first.replace(day=calendar.monthrange(first.year, first.month)[1])
    return first, last


def end_of(it: dict) -> date | None:
    s = _day(it.get("start_date"))
    if not s:
        return None
    return s + timedelta(days=max(0, int(round(float(it.get("duration_days") or 1))) - 1))


def calendar_view(month: str | None = None) -> dict:
    first, last = _month(month)
    items = pm.list_items()
    sprints = pm.list_sprints()
    days = {(first + timedelta(days=i)).isoformat(): {"date": (first + timedelta(days=i)).isoformat(), "items": [], "sprints": []} for i in range((last - first).days + 1)}
    unscheduled = 0
    for it in items:
        s, e = _day(it.get("start_date")), end_of(it)
        if not s:
            unscheduled += 1
            continue
        if (e - s).days > MAX_SPAN_DAYS:
            e = s + timedelta(days=MAX_SPAN_DAYS)
        if e < first or s > last:
            continue
        d = max(s, first)
        while d <= min(e, last):
            days[d.isoformat()]["items"].append({"id": it["id"], "title": it["title"], "status": it["status"], "kind": it["kind"], "starts": d == s, "ends": d == e,
                                                 "overdue": bool(e < pm.today() and it["status"] != "done")})
            d += timedelta(days=1)
    for sp in sprints:
        s, e = _day(sp.get("start_date")), _day(sp.get("end_date"))
        if not s or not e:
            continue
        d = max(s, first)
        while d <= min(e, last):
            days[d.isoformat()]["sprints"].append({"id": sp["id"], "name": sp["name"]})
            d += timedelta(days=1)
    lead = first.weekday()                                   # Monday first
    return {"month": first.strftime("%Y-%m"), "label": first.strftime("%B %Y"), "lead_blanks": lead, "today": pm.today().isoformat(), "days": list(days.values()),
            "unscheduled": unscheduled, "note": "Bars come from each item's start date and duration. Items without a start date are not shown (set one on the board)."}


# ------------------------------------------------------------------ automations
def _ws() -> str:
    return pm._ws()


def list_rules() -> dict:
    rows = state.rows("SELECT * FROM pm_rules WHERE workspace = ? ORDER BY id", (_ws(),))
    for r in rows:
        r["enabled"] = bool(r["enabled"])
    return {"rules": rows, "triggers": TRIGGERS, "actions": ACTIONS, "statuses": list(pm.STATUSES),
            "note": "Rules run only when you press Preview or Run. Preview changes nothing."}


def add_rule(name: str, trigger: str, action: str, value: str, days: int = 0) -> dict:
    name = (name or "").strip()[:80]
    if not name:
        raise pm.PmError("Give the rule a name.")
    if trigger not in TRIGGERS:
        raise pm.PmError(f"trigger must be one of {', '.join(TRIGGERS)}.")
    if action not in ACTIONS:
        raise pm.PmError(f"action must be one of {', '.join(ACTIONS)}.")
    value = str(value or "").strip()[:200]
    if action == "set_priority":
        if value not in {"1", "2", "3", "4", "5"}:
            raise pm.PmError("Priority must be a whole number from 1 to 5.")
    elif action == "move_status":
        if value not in pm.STATUSES:
            raise pm.PmError(f"Status must be one of {', '.join(pm.STATUSES)}.")
    elif not value:
        raise pm.PmError("Write the note text.")
    days = int(days or 0)
    if trigger == "stuck" and not 1 <= days <= 365:
        raise pm.PmError("For 'stuck', give the number of days (1 to 365).")
    if state.one("SELECT COUNT(*) AS n FROM pm_rules WHERE workspace = ?", (_ws(),))["n"] >= MAX_RULES:
        raise pm.PmError(f"That's {MAX_RULES} rules, the limit. Delete one first.")
    cur = state.run("INSERT INTO pm_rules (workspace, name, trigger, days, action, value, enabled, created_at) VALUES (?,?,?,?,?,?,1,?)",
                    (_ws(), name, trigger, days if trigger == "stuck" else 0, action, value, state.now()))
    state.audit("pm_rule_add", name)
    return state.one("SELECT * FROM pm_rules WHERE id = ?", (cur.lastrowid,))


def set_enabled(rid: int, enabled: bool) -> None:
    if not state.one("SELECT id FROM pm_rules WHERE id = ? AND workspace = ?", (rid, _ws())):
        raise pm.PmError("No such rule.", 404)
    state.run("UPDATE pm_rules SET enabled = ? WHERE id = ?", (1 if enabled else 0, rid))


def delete_rule(rid: int) -> None:
    if not state.one("SELECT id FROM pm_rules WHERE id = ? AND workspace = ?", (rid, _ws())):
        raise pm.PmError("No such rule.", 404)
    state.run("DELETE FROM pm_rules WHERE id = ?", (rid,))


def _matches(rule: dict, it: dict, today: date) -> bool:
    if it["status"] == "done":
        return False
    if rule["trigger"] == "overdue":
        e = end_of(it)
        return bool(e and e < today)
    if rule["trigger"] == "stuck":
        st = _day(it.get("started_at"))
        return it["status"] in ("doing", "review") and bool(st) and (today - st).days >= int(rule["days"] or 1)
    return False


def evaluate(apply: bool = False) -> dict:
    today = pm.today()
    rules = [r for r in state.rows("SELECT * FROM pm_rules WHERE workspace = ? AND enabled = 1 ORDER BY id", (_ws(),))]
    changes = []
    for it in pm.list_items():
        cur = dict(it)
        for r in rules:
            if not _matches(r, cur, today):
                continue
            tag = f"[rule: {r['name']}]"
            if r["action"] == "set_priority":
                if str(cur.get("priority")) == r["value"]:
                    continue
                change = {"priority": int(r["value"])}
                text = f"priority {cur.get('priority')} -> {r['value']}"
            elif r["action"] == "move_status":
                if cur["status"] == r["value"]:
                    continue
                change = {"status": r["value"]}
                text = f"status {cur['status']} -> {r['value']}"
            else:
                if tag in (cur.get("notes") or ""):
                    continue
                change = {"notes": ((cur.get("notes") or "") + f"\n{tag} {r['value']}").strip()}
                text = f"note added: {r['value']}"
            changes.append({"item_id": it["id"], "title": it["title"], "rule": r["name"], "change": text})
            cur.update(change)
            if apply:
                pm.update_item(it["id"], change)
    if apply and changes:
        state.audit("pm_rules_run", f"{len(changes)} change(s)")
    return {"applied": apply, "changes": changes, "rules_checked": len(rules),
            "note": "Preview changes nothing." if not apply else f"{len(changes)} change(s) were made."}
