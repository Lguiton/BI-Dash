"""Morning briefing: one email with today's calendar, dashboard numbers that moved the wrong way, alerts and job follow-ups.

Your computer isn't always on, so the schedule is a catch-up, not a clock: if the app is running at the send hour it sends then;
if it starts later the same day, it sends once on start (until 9 pm). If it never runs that day, that day's briefing is skipped.
Hosting the app online (the deploy kit) is what makes it fire every morning regardless of your computer.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.services import alerts, biz_packs, mailer, state, workspaces
from app.services.db import get_cursor

DEFAULTS = {"enabled": False, "hour": 7, "last_sent": "", "last_attempt": 0.0}
LATEST_HOUR = 21
RETRY_SECONDS = 1800


class BriefingError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def config() -> dict:
    return {**DEFAULTS, **(state.setting_get(workspaces.active(), "briefing", {}) or {})}


def _save(cfg: dict) -> dict:
    state.setting_set(workspaces.active(), "briefing", cfg)
    return cfg


def update_config(body: dict) -> dict:
    cfg = config()
    if "enabled" in body:
        cfg["enabled"] = bool(body["enabled"])
    if "hour" in body:
        try:
            h = int(body["hour"])
        except (TypeError, ValueError):
            raise BriefingError("The hour must be a whole number from 0 to 20.") from None
        if not 0 <= h < LATEST_HOUR:
            raise BriefingError(f"The hour must be from 0 to {LATEST_HOUR - 1}.")
        cfg["hour"] = h
    if cfg["enabled"] and not mailer.configured():
        raise BriefingError("Email isn't set up, so the briefing can't be switched on. Set BI_SMTP_HOST, BI_SMTP_USER, BI_SMTP_PASSWORD and BI_REPORT_TO in backend/.env, restart, then try again.", 503)
    state.audit("briefing_config", f"enabled={cfg['enabled']} hour={cfg['hour']}")
    return _save(cfg)


def _now() -> datetime:
    tz = os.environ.get("BI_TZ")
    try:
        return datetime.now(ZoneInfo(tz)) if tz else datetime.now()
    except Exception:  # noqa: BLE001 - a bad BI_TZ falls back to the machine's clock
        return datetime.now()


def _calendar(today: date) -> list[dict]:
    """Events from whichever table a Calendar source loaded (it has title, start, end, all_day columns)."""
    try:
        with get_cursor() as cur:
            rows = cur.execute("""SELECT table_name FROM information_schema.columns WHERE table_schema = 'main' AND column_name IN ('title','start','end','all_day')
                                  GROUP BY table_name HAVING COUNT(DISTINCT column_name) = 4""").fetchall()
            if not rows:
                return []
            t = rows[0][0]
            tom = today + timedelta(days=1)
            ev = cur.execute(f'SELECT title, "start", "end", all_day, location FROM "{t}" WHERE SUBSTR(CAST("start" AS VARCHAR),1,10) IN (?, ?) ORDER BY "start" LIMIT 14',
                             [today.isoformat(), tom.isoformat()]).fetchall()
    except Exception:  # noqa: BLE001 - a missing or odd calendar table never blocks the briefing
        return []
    return [{"title": r[0], "start": str(r[1]), "all_day": str(r[3]).lower() in ("yes", "true", "1"), "when": "today" if str(r[1])[:10] == today.isoformat() else "tomorrow",
             "location": r[4] or ""} for r in ev]


def _follow_ups(today: date) -> list[dict]:
    """Job-search follow-ups still open, and repair customers due a check-in call."""
    out: list[dict] = []
    for pid, sql, fmt in (
        ("job-search", """SELECT company, role_type, stage, follow_up FROM biz_job_search WHERE follow_up IS NOT NULL AND follow_up <= ?
                          AND stage IN ('Applied','Screen','Interview') ORDER BY follow_up LIMIT 8""",
         lambda r: {"what": f"{r[0]}, {r[1]} ({r[2]}), follow up by {r[3]}"}),
        ("repair-jobs", """SELECT device_type, fault, status, follow_up FROM biz_repair_jobs WHERE follow_up IS NOT NULL AND follow_up <= ?
                           AND status IN ('Completed','Warranty return') ORDER BY follow_up LIMIT 8""",
         lambda r: {"what": f"Customer check-in: {r[0]} ({r[1]}), due {r[3]}"}),
    ):
        try:
            if biz_packs.installed(pid) is None:
                continue
            with get_cursor() as cur:
                out += [fmt(r) for r in cur.execute(sql, [today]).fetchall()]
        except Exception:  # noqa: BLE001
            continue
    return out


def build(now: datetime | None = None) -> dict:
    now = now or _now()
    today = now.date()
    sections: list[tuple[str, list[str]]] = []
    ev = _calendar(today)
    if ev:
        sections.append(("Calendar", [f"{'Today' if e['when'] == 'today' else 'Tomorrow'}: " + ("all day" if e["all_day"] else e["start"][11:16]) + f"  {e['title']}" + (f" ({e['location']})" if e["location"] else "") for e in ev]))
    fu = _follow_ups(today)
    if fu:
        sections.append(("Follow-ups due", [f["what"] for f in fu]))
    try:
        lim = alerts.config()["biz_change_pct"]
        moved = biz_packs.wrong_way(30, lim)[:6]
    except Exception:  # noqa: BLE001
        moved = []
    if moved:
        sections.append(("Numbers moving the wrong way (last 30 days vs the 30 before)", [f"{m['dept']} ({m['industry']}): {m['kpi']} {m['change_pct']:+.1f}%" for m in moved]))
    try:
        al = alerts.current()[:6]
    except Exception:  # noqa: BLE001
        al = []
    if al:
        sections.append(("Alerts", [f"{'RED ' if a['level'] == 'red' else ''}{a['title']}" for a in al]))
    try:
        from app.services import health_check
        hc = health_check.run(now.replace(tzinfo=None))["needs_attention"]
    except Exception:  # noqa: BLE001
        hc = []
    if hc:
        sections.append(("System health", [f"{c['name']}: {c['detail']}" for c in hc[:5]]))
    n = sum(len(v) for _, v in sections)
    lines = [f"Good morning. Briefing for {today.strftime('%A, %B %d')} ({workspaces.active()} workspace).", ""]
    if not sections:
        lines.append("Nothing needs attention today.")
    for title, items in sections:
        lines += [title.upper()] + [f"  - {i}" for i in items] + [""]
    lines.append("Sent by your BI dashboard. Open it to see the detail.")
    return {"subject": f"Morning briefing: {n} item(s) for {today.strftime('%a %b %d')}" if n else f"Morning briefing: all clear, {today.strftime('%a %b %d')}",
            "body": "\n".join(lines), "items": n, "sections": [{"title": t, "items": v} for t, v in sections]}


def send_now(smtp_factory=None, now: datetime | None = None) -> dict:
    b = build(now)
    try:
        to = mailer.send(b["subject"], b["body"], smtp_factory)
    except mailer.MailError as e:
        state.audit("briefing_send", f"failed: {e.message}", ok=False)
        raise BriefingError(e.message, e.status) from e
    state.audit("briefing_send", f"{b['items']} item(s)")
    return {"sent_to": to, "subject": b["subject"], "items": b["items"]}


def tick(now: datetime | None = None, smtp_factory=None, clock=None) -> list[str]:
    """Called by the scheduler every few seconds. Sends at most once a day, from the send hour until 9 pm, retrying a failure every 30 minutes."""
    cfg = config()
    if not cfg["enabled"]:
        return []
    now = now or _now()
    today = now.date().isoformat()
    if cfg["last_sent"] == today or not (cfg["hour"] <= now.hour < LATEST_HOUR):
        return []
    t = (clock or __import__("time").time)()
    if t - float(cfg.get("last_attempt") or 0) < RETRY_SECONDS:
        return []
    cfg["last_attempt"] = t
    try:
        send_now(smtp_factory, now)
        cfg["last_sent"] = today
        _save(cfg)
        return ["briefing"]
    except BriefingError:
        _save(cfg)
        return []


def status() -> dict:
    cfg = config()
    return {**{k: cfg[k] for k in ("enabled", "hour", "last_sent")}, "email_ready": mailer.configured(), "latest_hour": LATEST_HOUR,
            "how": "Sends at the chosen hour if the app is running, or once when it starts later the same day (until 9 pm). If the app isn't running at all that day, no briefing is sent."}
