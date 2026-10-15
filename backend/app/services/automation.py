"""The Today list and the small automatic chores. Nothing here sends anything to anyone and nothing costs AI tokens.

* today(): what needs you right now (follow-ups, overdue invoices with a reminder already written, late jobs, overdue work, a running
  timer left on, jobs ready to close, a backup reminder). Built from your own data every time you open Home.
* Recurring jobs: "every month on the 1st, create this job with these steps". Checked when the app runs (the computer is not always on, so a
  job that was due while it was off is created the next time it runs, once per period).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.services import backups, clients, state, workspaces, worklog

TIMER_WARN_SECONDS = 2 * 3600
BACKUP_STALE_DAYS = 7
SOON_DAYS = 3
EVERY = ("weekly", "monthly")


class AutoError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# ---------------------------------------------------------------- reminder text (a template; you read it and send it yourself)
def reminder_text(inv: dict, client: dict | None, settings: dict) -> str:
    who = ((client or {}).get("contact") or (client or {}).get("name") or "there").strip()
    biz = (settings.get("business") or "").strip()
    pay = (settings.get("pay_to") or "").strip()
    total = clients.inv_total(inv)
    return (f"Hi {who},\n\nA quick reminder that invoice {inv['number']} for ${total:,.2f} was due on {inv['due']}. "
            "If you have already paid it, thank you, and please ignore this note. "
            + (f"Otherwise you can pay by: {pay}. " if pay else "")
            + "If anything is unclear or you need more time, just reply and we will sort it out.\n\nThanks,\n" + (biz or "Lamarcus"))


def _backup_note() -> dict | None:
    if workspaces.active() != "real":
        return None
    try:
        cf = backups.copy_folder()
        if not cf["folder"]:
            return {"message": "No outside backup folder is set. Pick a USB drive or another disk in Settings so your client data survives a dead computer.", "where": "/settings"}
        last = (cf["last"] or "")[:10]
        if not last:
            return {"message": "Your outside backup copy has not run yet. Check the drive is plugged in.", "where": "/settings"}
        age = (date.today() - date.fromisoformat(last)).days
        if age >= BACKUP_STALE_DAYS:
            return {"message": f"Your last outside backup copy was {age} days ago. Plug in the drive and take a backup.", "where": "/settings"}
    except Exception:  # noqa: BLE001 - a reminder must never break the Today list
        return None
    return None


def today(now: date | None = None) -> dict:
    t = now or date.today()
    ov = clients.overview(t)
    d = clients._load()
    cl = {c["id"]: c for c in d["clients"]}
    overdue = [{"id": i["id"], "number": i["number"], "client": i["client"], "total": i["total"], "days_late": i["days_late"], "due": i["due"],
                "draft": reminder_text(i, cl.get(i["client_id"]), d["settings"])} for i in ov["overdue"]]
    jobs = clients.open_jobs(t)
    soon = (t + timedelta(days=SOON_DAYS)).isoformat()
    jobs_due = [j for j in jobs if j["late"] or (j["due"] and j["status"] == "active" and j["due"] <= soon)]
    wl = worklog.listing()
    work_due = [{"id": i["id"], "title": i["title"], "due": i["due"], "overdue": i["overdue"], "client": i["client"]} for i in wl["items"] if i["overdue"] or i["due_today"]]
    running = worklog._running()
    timer = None
    if running:
        timer = {"id": running["id"], "title": running["title"], "elapsed": running["elapsed"], "warn": running["elapsed"] >= TIMER_WARN_SECONDS}
    ready = []
    for j in jobs:
        if j["status"] != "active":
            continue
        items = worklog.for_job(j["id"])
        if items and all(i["status"] == "done" for i in items):
            ready.append({"id": j["id"], "title": j["title"], "client": j["client"]})
    backup = _backup_note()
    out = {"date": t.isoformat(), "sample": ov["sample"], "followups": ov["followups_due"], "overdue_invoices": overdue, "jobs_due": jobs_due, "work_due": work_due,
           "timer": timer, "ready_to_close": ready, "backup": backup, "unbilled_hours": ov["unbilled_hours"], "unbilled_amount": ov["unbilled_amount"],
           "note": "Reminders are drafts for you to read and send yourself. Nothing is sent automatically."}
    out["count"] = len(out["followups"]) + len(overdue) + len(jobs_due) + len(work_due) + len(ready) + (1 if backup else 0) + (1 if timer and timer["warn"] else 0)
    return out


# ---------------------------------------------------------------- recurring jobs
def _ws() -> str:
    return workspaces.active()


def _load() -> list[dict]:
    return list(state.setting_get(_ws(), "recurring", []) or [])


def _save(rows: list[dict]) -> None:
    state.setting_set(_ws(), "recurring", rows)


def recurring_list() -> list[dict]:
    names = {c["id"]: c["name"] for c in clients._load()["clients"]}
    return [{**r, "client": names.get(r["client_id"], "(deleted client)")} for r in _load()]


def _period(every: str, t: date) -> str:
    return t.strftime("%Y-%m") if every == "monthly" else f"{t.isocalendar().year}-W{t.isocalendar().week:02d}"


def recurring_add(b: dict) -> dict:
    every = b.get("every")
    if every not in EVERY:
        raise AutoError("Choose weekly or monthly.")
    try:
        cid = int(b.get("client_id"))
    except (TypeError, ValueError):
        raise AutoError("Choose a client.") from None
    if not any(c["id"] == cid for c in clients._load()["clients"]):
        raise AutoError("No such client.", 404)
    title = str(b.get("title") or "").strip()[:120]
    if not title:
        raise AutoError("Give the job a title.")
    try:
        day = int(b.get("day") if b.get("day") is not None else (1 if every == "monthly" else 0))
    except (TypeError, ValueError):
        raise AutoError("The day must be a number.") from None
    if every == "monthly" and not 1 <= day <= 28:
        raise AutoError("For monthly, pick a day from 1 to 28 so every month has it.")
    if every == "weekly" and not 0 <= day <= 6:
        raise AutoError("For weekly, pick a weekday from 0 (Monday) to 6 (Sunday).")
    try:
        quote = float(b.get("quote") or 0)
    except (TypeError, ValueError):
        raise AutoError("The quote must be a number.") from None
    if not 0 <= quote <= 1e7:
        raise AutoError("The quote is out of range.")
    items = [str(x).strip()[:140] for x in (b.get("items") or []) if str(x).strip()][:10]
    rows = _load()
    r = {"id": max([x["id"] for x in rows], default=0) + 1, "client_id": cid, "title": title, "quote": quote, "every": every, "day": day, "items": items, "active": True, "last_run": ""}
    _save(rows + [r])
    state.audit("recurring.add", title[:80])
    return r


def recurring_update(rid: int, b: dict) -> dict:
    rows = _load()
    r = next((x for x in rows if x["id"] == rid), None)
    if not r:
        raise AutoError("No such recurring job.", 404)
    if "active" in b:
        r["active"] = bool(b["active"])
    _save(rows)
    return r


def recurring_delete(rid: int) -> dict:
    rows = _load()
    if not any(x["id"] == rid for x in rows):
        raise AutoError("No such recurring job.", 404)
    _save([x for x in rows if x["id"] != rid])
    return {"deleted": rid}


def _due(r: dict, t: date) -> bool:
    if not r["active"] or r["last_run"] == _period(r["every"], t):
        return False
    return t.day >= r["day"] if r["every"] == "monthly" else t.weekday() >= r["day"]


def run_recurring(now: date | None = None) -> list[dict]:
    """Create the jobs that are due. Once per period per recurring job, so running it twice does nothing the second time."""
    t = now or date.today()
    rows, made = _load(), []
    for r in rows:
        if not _due(r, t):
            continue
        if not any(c["id"] == r["client_id"] for c in clients._load()["clients"]):
            continue
        job = clients.add_job({"client_id": r["client_id"], "title": f"{r['title']} ({t.strftime('%b %Y') if r['every'] == 'monthly' else 'week of ' + t.isoformat()})",
                               "quote": r["quote"], "status": "active", "due": (t + timedelta(days=7)).isoformat()})
        for k, text in enumerate(r["items"]):
            worklog.add({"title": text, "job_id": job["id"], "status": "doing" if k == 0 else "todo"})
        r["last_run"] = _period(r["every"], t)
        made.append({"recurring_id": r["id"], "job_id": job["id"], "title": job["title"]})
        state.audit("recurring.run", job["title"][:80])
    if made:
        _save(rows)
    return made


def tick() -> list[str]:
    try:
        return ["recurring-jobs"] if run_recurring() else []
    except Exception:  # noqa: BLE001 - a chore failing must never stop the scheduler
        return []
