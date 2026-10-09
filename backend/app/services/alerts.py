"""Alerts: the app looks at your own data and tells you when something needs attention, instead of waiting for you to look.

Checks (all computed from this workspace, nothing external): a KPI is red, the backup is stale or missing, a restore drill failed
or was never run, an integrity check fails, a data source failed its last refresh, the newest record is old, deliverables are overdue.
Alerts are always visible in the dashboard. Email is optional: it needs SMTP set up (the same settings as the emailed report),
and you switch it on per workspace. The same alert is emailed at most once per cooldown so your inbox doesn't fill up.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from app.services import drill, mailer, state, workspaces

DEFAULTS = {"enabled": False, "email": False, "stale_days": 7, "backup_days": 3, "cooldown_hours": 24}
COOLDOWN_CHOICES = (1, 6, 24, 72, 168)


class AlertError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def config() -> dict:
    return {**DEFAULTS, **(state.setting_get(workspaces.active(), "alerts", {}) or {})}


def save_config(body: dict) -> dict:
    cur = config()
    for k in ("enabled", "email"):
        if k in body:
            cur[k] = bool(body[k])
    for k, lo, hi in (("stale_days", 1, 365), ("backup_days", 1, 90), ("cooldown_hours", 1, 168)):
        if k in body:
            try:
                v = int(body[k])
            except (TypeError, ValueError):
                raise AlertError(f"{k} must be a whole number.") from None
            if not lo <= v <= hi:
                raise AlertError(f"{k} must be between {lo} and {hi}.")
            cur[k] = v
    if cur["email"] and not mailer.configured():
        raise AlertError("Email isn't set up yet, so it can't be switched on. Set BI_SMTP_HOST, BI_SMTP_USER, BI_SMTP_PASSWORD and BI_REPORT_TO in backend/.env, restart, then try again.", 503)
    state.setting_set(workspaces.active(), "alerts", cur)
    state.audit("alerts_config", f"enabled={cur['enabled']} email={cur['email']}")
    return cur


def _a(aid: str, level: str, title: str, detail: str, href: str) -> dict:
    return {"id": aid, "level": level, "title": title, "detail": detail, "href": href}


def _safe(fn):
    try:
        return fn() or []
    except Exception:  # noqa: BLE001  one broken check must not hide the others
        return []


def _kpis(cfg):
    from app.routers import kpis
    return [_a(f"kpi:{k['id']}", "red", f"KPI off target: {k['name']}", f"{k['label']} is {k['value']} against a target of {k['target']}.", "/kpis")
            for k in kpis._list() if k["status"] == "bad"]


def _backup(cfg):
    from app.services import backups
    ws = workspaces.active()
    from app.services.db import get_cursor
    with get_cursor() as cur:
        n = cur.execute("SELECT COUNT(*) FROM fact_operations").fetchone()[0]
    real_like = ws == "real" or n > 0
    bl = [b for b in backups.list_backups(ws) if not b["kind"].startswith("safety")]
    if not real_like:
        return []
    if not bl:
        return [_a("backup:none", "red", "No backup exists", f"The {ws} workspace holds {n:,} records and has never been backed up.", "/tracks/engineering")]
    age = datetime.now(timezone.utc) - datetime.strptime(bl[0]["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    if age > timedelta(days=cfg["backup_days"]):
        return [_a("backup:stale", "warn", "Backup is out of date", f"The newest backup is {age.days} day(s) old (limit {cfg['backup_days']}).", "/tracks/engineering")]
    return []


def _drill(cfg):
    from app.services import backups
    if not backups.list_backups():
        return []
    h = drill.history()
    if h and not h[0]["ok"]:
        return [_a("drill:failed", "red", "The last restore drill FAILED", h[0]["reading"], "/tracks/engineering")]
    if not h:
        return [_a("drill:never", "warn", "Backups have never been test-restored", "Run a restore drill to prove a backup works.", "/tracks/engineering")]
    age = datetime.now(timezone.utc) - datetime.strptime(h[0]["at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return [_a("drill:old", "warn", "Restore drill is overdue", f"The last drill was {age.days} days ago.", "/tracks/engineering")] if age.days > 30 else []


def _integrity(cfg):
    from app.services import dba
    from app.services.db import get_cursor
    with get_cursor() as cur:
        bad = [c for c in dba.integrity_checks(cur) if not c["ok"] and "unused" not in c["detail"]]
    return [_a(f"integrity:{c['name'][:30]}", "red", f"Integrity check failed: {c['name']}", c["detail"], "/tracks/engineering") for c in bad]


def _sources(cfg):
    from app.services import sources
    return [_a(f"source:{s['id']}", "red", f"Data source failed: {s['name']}", (s.get("last_message") or "The last refresh failed.")[:200], "/sources")
            for s in sources.list_sources() if s.get("enabled") and s.get("last_status") == "error"]


def _stale(cfg):
    if workspaces.active() != "real":
        return []                                   # Practice data is a fixed sample: being old is normal
    from app.services.db import get_cursor
    with get_cursor() as cur:
        mx = cur.execute("SELECT MAX(record_date) FROM fact_operations").fetchone()[0]
    if mx is None:
        return []
    days = (date.today() - mx).days
    return [_a("data:stale", "warn", "Data looks stale", f"The newest record is {days} day(s) old (limit {cfg['stale_days']}).", "/data")] if days > cfg["stale_days"] else []


def _overdue(cfg):
    from app.services import company
    return [_a(f"overdue:{i['id']}", "warn", f"Overdue: {i['title']}", f"Due {i['due']}.", "/company")
            for p in company.overview()["phases"] for i in p["deliverables"] if i["overdue"]]


def current() -> list[dict]:
    cfg = config()
    out: list[dict] = []
    for fn in (_kpis, _backup, _drill, _integrity, _sources, _stale, _overdue):
        out += _safe(lambda fn=fn: fn(cfg))
    return sorted(out, key=lambda a: 0 if a["level"] == "red" else 1)


def _sent_key() -> str:
    return f"alerts_sent:{workspaces.active()}"


def check(send: bool = False, smtp_factory=None) -> dict:
    """Run every check. With send=True, email the alerts not already emailed within the cooldown."""
    cfg = config()
    alerts = current()
    emailed: list[str] = []
    problem = None
    if send and cfg["email"] and alerts:
        raw = state.kv_get(_sent_key())
        sent = json.loads(raw) if raw else {}
        now = datetime.now(timezone.utc)
        cool = timedelta(hours=cfg["cooldown_hours"])
        fresh = [a for a in alerts if a["id"] not in sent or now - datetime.fromisoformat(sent[a["id"]]) >= cool]
        if fresh:
            lines = [f"{'RED ' if a['level'] == 'red' else 'WARN'} {a['title']}: {a['detail']}" for a in fresh]
            body = f"Your {workspaces.active()} workspace needs attention:\n\n" + "\n".join(lines) + "\n\nOpen the dashboard to see them. This message is sent at most once per alert every " + f"{cfg['cooldown_hours']} hour(s)."
            try:
                mailer.send(f"BI dashboard: {len(fresh)} alert(s), {sum(1 for a in fresh if a['level'] == 'red')} red", body, smtp_factory)
                for a in fresh:
                    sent[a["id"]] = now.isoformat()
                emailed = [a["id"] for a in fresh]
                state.audit("alerts_email", f"{len(fresh)} alert(s) emailed")
            except mailer.MailError as e:
                problem = e.message
                state.audit("alerts_email", f"failed: {e.message}", ok=False)
        live_ids = {a["id"] for a in alerts}
        sent = {k: v for k, v in sent.items() if k in live_ids}      # an alert that cleared can fire again if it returns
        state.kv_set(_sent_key(), json.dumps(sent))
    state.kv_set(f"alerts_last:{workspaces.active()}", json.dumps({"at": state.now(), "count": len(alerts)}))
    return {"alerts": alerts, "red": sum(1 for a in alerts if a["level"] == "red"), "emailed": emailed, "email_problem": problem, "checked_at": state.now()}


def status() -> dict:
    return {"config": config(), "email_ready": mailer.configured(), "options": {"cooldown_hours": list(COOLDOWN_CHOICES)}, **check(False)}
