"""Work log: a short to-do list of what you are working on, with a running log under each item so you can see where you left off.

Each item has a status (to do, doing, waiting, done), an optional client and due date, a "where I left off" note, and a time-stamped log.
Changing the status writes a log line by itself. Nothing is deleted when you finish an item; it moves to Done.
Passwords, keys and tokens in notes are blanked before they are stored.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone

from app.services import clients, state, workspaces
from app.services.fixlog import hide_secrets

STATUSES = {"todo": "To do", "doing": "Doing", "waiting": "Waiting", "done": "Done"}
ORDER = {"doing": 0, "todo": 1, "waiting": 2, "done": 3}
MAX_LOG = 200
MAX_TIMER_HOURS = 12      # one timer run longer than this is capped (you forgot to stop it); the note says so and you can edit the time entry


class WorkError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    return workspaces.active()


def _txt(v, name: str, limit: int, required: bool = False) -> str:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v or "")).strip()[:limit]
    if required and not s:
        raise WorkError(f"Add a {name}.")
    return hide_secrets(s)[0]


def _due(v) -> str:
    s = str(v or "").strip()
    if not s:
        return ""
    try:
        return date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        raise WorkError("Due date must look like 2026-10-31.") from None


def _secs_since(ts: str) -> int:
    try:
        t = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return 0
    return max(0, int((datetime.now(timezone.utc) - t).total_seconds()))


def _job(jid) -> dict | None:
    """The job and its client name, or None when there is no such job (it may have been deleted)."""
    if not jid:
        return None
    try:
        j = next((x for x in clients._load()["jobs"] if x["id"] == int(jid)), None)
        if not j:
            return None
        c = next((x for x in clients._load()["clients"] if x["id"] == j["client_id"]), None)
        return {"id": j["id"], "title": j["title"], "client": c["name"] if c else ""}
    except (TypeError, ValueError):
        return None


def _row(r) -> dict:
    d = dict(r)
    d["seconds"] = int(d.get("seconds") or 0)
    d["running"] = bool(d.get("timer_start"))
    d["elapsed"] = d["seconds"] + (_secs_since(d["timer_start"]) if d["running"] else 0)
    d["job"] = _job(d.get("job_id"))
    d["log"] = json.loads(d.get("log") or "[]")
    d["status_label"] = STATUSES.get(d["status"], d["status"])
    today = date.today().isoformat()
    d["overdue"] = bool(d["due"]) and d["status"] != "done" and d["due"] < today
    d["due_today"] = bool(d["due"]) and d["status"] != "done" and d["due"] == today
    return d


def _get(wid: int) -> dict:
    r = state.one("SELECT * FROM work_items WHERE id=? AND workspace=?", (int(wid), _ws()))
    if not r:
        raise WorkError("That item was not found.", 404)
    return _row(r)


def _save(wid: int, d: dict, log: list) -> dict:
    state.run("UPDATE work_items SET title=?, client=?, status=?, due=?, note=?, log=?, updated_at=?, done_at=?, job_id=?, timer_start=?, seconds=? WHERE id=? AND workspace=?",
              (d["title"], d["client"], d["status"], d["due"], d["note"], json.dumps(log[-MAX_LOG:]), state.now(), d.get("done_at"), d.get("job_id"), d.get("timer_start"),
               int(d.get("seconds") or 0), wid, _ws()))
    return _get(wid)


def _check_job(v) -> int | None:
    if v in (None, "", 0, "0"):
        return None
    try:
        jid = int(v)
    except (TypeError, ValueError):
        raise WorkError("That job was not found.") from None
    if not _job(jid):
        raise WorkError("That job was not found.", 404)
    return jid


def listing(include_done: bool = False) -> dict:
    rows = [_row(r) for r in state.rows("SELECT * FROM work_items WHERE workspace=? ORDER BY id DESC", (_ws(),))]
    open_ = sorted([r for r in rows if r["status"] != "done"], key=lambda r: (ORDER[r["status"]], r["due"] or "9999", -r["id"]))
    done = [r for r in rows if r["status"] == "done"][:20]
    counts = {k: sum(1 for r in rows if r["status"] == k) for k in STATUSES}
    return {"items": open_ + (done if include_done else []), "done_recent": done if not include_done else [], "counts": counts,
            "overdue": sum(1 for r in open_ if r["overdue"]), "due_today": sum(1 for r in open_ if r["due_today"]),
            "note": "Notes are for you. Passwords and keys are blanked before saving."}


def add(b: dict) -> dict:
    status = b.get("status") or "todo"
    if status not in STATUSES:
        raise WorkError("Status must be one of: " + ", ".join(STATUSES) + ".")
    now = state.now()
    jid = _check_job(b.get("job_id"))
    job = _job(jid)
    client = _txt(b.get("client"), "client", 80) or (job["client"] if job else "")
    entry = {"at": now, "text": "Added" + (f" as {STATUSES[status].lower()}" if status != "todo" else "") + (f" for job: {job['title']}" if job else "")}
    cur = state.run("INSERT INTO work_items (workspace, title, client, status, due, note, log, created_at, updated_at, done_at, job_id, seconds) VALUES (?,?,?,?,?,?,?,?,?,?,?,0)",
                    (_ws(), _txt(b.get("title"), "title", 140, True), client, status, _due(b.get("due")), _txt(b.get("note"), "note", 1000),
                     json.dumps([entry]), now, now, now if status == "done" else None, jid))
    state.audit("worklog_add", str(b.get("title"))[:80])
    return _get(int(cur.lastrowid))


def update(wid: int, b: dict) -> dict:
    d = _get(wid)
    log = list(d["log"])
    now = state.now()
    if "title" in b:
        d["title"] = _txt(b["title"], "title", 140, True)
    if "client" in b:
        d["client"] = _txt(b["client"], "client", 80)
    if "due" in b:
        d["due"] = _due(b["due"])
    if "job_id" in b:
        new = _check_job(b["job_id"])
        if new != d.get("job_id"):
            d["job_id"] = new
            j = _job(new)
            log.append({"at": now, "text": f"Linked to job: {j['title']}" if j else "Unlinked from its job"})
    if "note" in b and _txt(b["note"], "note", 1000) != d["note"]:
        d["note"] = _txt(b["note"], "note", 1000)
        log.append({"at": now, "text": "Left off: " + (d["note"] or "(cleared)")[:200]})
    if "status" in b and b["status"] != d["status"]:
        if b["status"] not in STATUSES:
            raise WorkError("Status must be one of: " + ", ".join(STATUSES) + ".")
        if b["status"] == "done" and d.get("timer_start"):
            stop_timer(int(wid))                # finishing an item stops its timer and books the time first
            d = _get(wid)
            log = list(d["log"])
        d["status"] = b["status"]
        d["done_at"] = now if b["status"] == "done" else None
        log.append({"at": now, "text": f"Marked {STATUSES[b['status']].lower()}"})
    return _save(int(wid), d, log)


def add_log(wid: int, text: str) -> dict:
    d = _get(wid)
    t = _txt(text, "note", 500, True)
    return _save(int(wid), d, list(d["log"]) + [{"at": state.now(), "text": t}])


def delete(wid: int) -> dict:
    _get(wid)
    state.run("DELETE FROM work_items WHERE id=? AND workspace=?", (int(wid), _ws()))
    return {"deleted": int(wid)}


# ------------------------------------------------------------------ timer: start and stop, kept on the server so it survives a reload or a closed laptop
def _running() -> dict | None:
    r = state.one("SELECT * FROM work_items WHERE workspace=? AND timer_start IS NOT NULL AND timer_start != ''", (_ws(),))
    return _row(r) if r else None


def start_timer(wid: int) -> dict:
    d = _get(wid)
    if d["running"]:
        raise WorkError("The timer is already running on this item.", 409)
    other = _running()
    if other:
        raise WorkError(f"A timer is already running on '{other['title']}'. Stop it first.", 409)
    if d["status"] == "done":
        raise WorkError("Reopen this item before starting its timer.", 409)
    now = state.now()
    log = list(d["log"]) + [{"at": now, "text": "Timer started"}]
    if d["status"] != "doing":
        log.append({"at": now, "text": "Marked doing"})
        d["status"] = "doing"
    d["timer_start"] = now
    return _save(int(wid), d, log)


def stop_timer(wid: int) -> dict:
    """Stop the timer. With a linked job the time becomes a billable time entry on that job; without one it is only kept on the item."""
    d = _get(wid)
    if not d["running"]:
        raise WorkError("The timer is not running on this item.", 409)
    raw = _secs_since(d["timer_start"])
    cap = MAX_TIMER_HOURS * 3600
    secs = min(raw, cap)
    capped = raw > cap
    hours = round(secs / 3600, 2)
    now = state.now()
    mins = f"{secs // 3600}h {secs % 3600 // 60:02d}m"
    note = f"Timer stopped: {mins}" + (f" (capped at {MAX_TIMER_HOURS} h because it ran {raw // 3600} h; edit the time entry if that is wrong)" if capped else "")
    added = 0.0
    job = d["job"]
    if job and hours >= 0.01:
        try:
            clients.add_time({"job_id": job["id"], "hours": hours, "note": f"Timer: {d['title']}"[:200], "billable": True})
            added = hours
            note += f". {hours:g} h added to job '{job['title']}' (billable)."
        except clients.ClientError:
            note += ". The job could not be found, so no time was added."
    elif job:
        note += ". Under 0.01 h, so no time entry was made."
    else:
        note += ". Not linked to a job, so no time was added to an invoice."
    d["seconds"] = int(d["seconds"]) + secs
    d["timer_start"] = None
    out = _save(int(wid), d, list(d["log"]) + [{"at": now, "text": note}])
    out["added_hours"], out["capped"] = added, capped
    return out


def for_job(jid: int) -> list[dict]:
    return [_row(r) for r in state.rows("SELECT * FROM work_items WHERE workspace=? AND job_id=? ORDER BY id", (_ws(), int(jid)))]


def stop_running_for_job(jid: int) -> float:
    """Closing a job stops any running timer on its items first, so that time is billed. Returns the hours added."""
    added = 0.0
    for it in for_job(jid):
        if it["running"]:
            added += stop_timer(it["id"]).get("added_hours", 0.0)
    return round(added, 2)


def complete_for_job(jid: int) -> int:
    n = 0
    for it in for_job(jid):
        if it["status"] != "done":
            update(it["id"], {"status": "done"})
            n += 1
    return n
