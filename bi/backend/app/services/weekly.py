"""Weekly report: a plain-language "what changed" paragraph (last 7 days of data vs the 7 before) that is built from rules,
not from an AI, plus an optional weekly email. "Last 7 days" means the 7 days ending on the newest record, so it still
makes sense for data that isn't from today. Email needs the same SMTP settings as the other emails."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services import mailer, state, workspaces
from app.services.db import get_cursor

DEFAULTS = {"enabled": False, "weekday": 0, "last_sent": ""}
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
MOVE_PCT = 5.0


class WeeklyError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def config() -> dict:
    return {**DEFAULTS, **(state.setting_get(workspaces.active(), "weekly_report", {}) or {})}


def save_config(body: dict) -> dict:
    c = config()
    if "enabled" in body:
        c["enabled"] = bool(body["enabled"])
    if "weekday" in body:
        try:
            w = int(body["weekday"])
        except (TypeError, ValueError):
            raise WeeklyError("weekday must be 0 (Monday) to 6 (Sunday).") from None
        if not 0 <= w <= 6:
            raise WeeklyError("weekday must be 0 (Monday) to 6 (Sunday).")
        c["weekday"] = w
    if c["enabled"] and not mailer.configured():
        raise WeeklyError("Email isn't set up yet, so the weekly email can't be switched on. Set BI_SMTP_HOST, BI_SMTP_USER, BI_SMTP_PASSWORD and BI_REPORT_TO in backend/.env, restart, then try again.", 503)
    state.setting_set(workspaces.active(), "weekly_report", c)
    state.audit("weekly_report_config", f"enabled={c['enabled']} weekday={DAYS[c['weekday']]}")
    return c


_SQL = """SELECT COUNT(*), COALESCE(SUM(f.revenue),0), COALESCE(SUM(f.operational_cost),0), COALESCE(SUM(f.units_processed),0),
 COALESCE(SUM(CASE WHEN f.status IS NOT NULL AND f.status <> 'Completed' THEN 1 ELSE 0 END),0), COUNT(f.status)
 FROM fact_operations f WHERE f.record_date >= ? AND f.record_date <= ?"""


def _window(cur, start, end) -> dict:
    n, rev, cost, units, bad, withstatus = cur.execute(_SQL, [start, end]).fetchone()
    return {"records": n, "revenue": rev, "cost": cost, "profit": rev - cost, "units": units,
            "margin_pct": (100.0 * (rev - cost) / rev) if rev else None, "problem_pct": (100.0 * bad / withstatus) if withstatus else None}


def _pct(a, b):
    return None if not b else 100.0 * (a - b) / abs(b)


def what_changed() -> dict:
    with get_cursor() as cur:
        mx = cur.execute("SELECT MAX(record_date) FROM fact_operations").fetchone()[0]
        if mx is None:
            raise WeeklyError("There is no data yet, so there is nothing to compare.")
        end = mx
        start = end - timedelta(days=6)
        p_end, p_start = start - timedelta(days=1), start - timedelta(days=7)
        this, last = _window(cur, start, end), _window(cur, p_start, p_end)
        ent = cur.execute("""SELECT f.entity_id, COALESCE(SUM(CASE WHEN f.record_date >= ? THEN f.revenue END),0),
            COALESCE(SUM(CASE WHEN f.record_date < ? THEN f.revenue END),0) FROM fact_operations f
            WHERE f.record_date >= ? AND f.record_date <= ? GROUP BY 1""", [start, start, p_start, end]).fetchall()
    rows = []
    for key, label, kind in (("revenue", "Revenue", "usd"), ("cost", "Operational cost", "usd"), ("profit", "Net profit", "usd"),
                             ("margin_pct", "Net margin", "pts"), ("units", "Units", "n"), ("records", "Records", "n"),
                             ("problem_pct", "Non-completed rate", "pts")):
        a, b = this[key], last[key]
        change = None if a is None or b is None else (a - b if kind == "pts" else _pct(a, b))
        rows.append({"key": key, "label": label, "kind": kind, "this": a, "last": b, "change": change})
    lines = []
    if not last["records"]:
        lines.append("There is no earlier week in the data to compare with, so these are this week's totals only.")
    else:
        movers = [r for r in rows if r["change"] is not None and abs(r["change"]) >= (1.0 if r["kind"] == "pts" else MOVE_PCT)]
        if not movers:
            lines.append("Nothing moved much: every measure is within a few percent of the week before.")
        for r in sorted(movers, key=lambda r: -abs(r["change"]))[:4]:
            good_up = r["key"] not in ("cost", "problem_pct")
            up = r["change"] > 0
            tone = "good news" if up == good_up else "worth a look"
            unit = " points" if r["kind"] == "pts" else "%"
            lines.append(f"{r['label']} {'rose' if up else 'fell'} {abs(r['change']):.1f}{unit} versus the week before ({tone}).")
        diffs = [(e, a - b) for e, a, b in ent if a or b]
        if diffs:
            up = max(diffs, key=lambda x: x[1])
            dn = min(diffs, key=lambda x: x[1])
            if up[1] > 0:
                lines.append(f"Biggest revenue gain: {up[0]} (+${up[1]:,.0f}).")
            if dn[1] < 0:
                lines.append(f"Biggest revenue drop: {dn[0]} (-${abs(dn[1]):,.0f}).")
    return {"window": {"from": str(start), "to": str(end), "previous_from": str(p_start), "previous_to": str(p_end)},
            "rows": rows, "paragraph": " ".join(lines),
            "note": "Rules compare two 7-day windows. They say what moved, not why. Check the data before acting."}


def _text(d: dict) -> str:
    w = d["window"]
    out = [f"What changed: {w['from']} to {w['to']} (vs {w['previous_from']} to {w['previous_to']})", "", d["paragraph"], ""]
    for r in d["rows"]:
        def f(v):
            if v is None:
                return "n/a"
            return f"${v:,.0f}" if r["kind"] == "usd" else (f"{v:.1f}" if r["kind"] == "pts" else f"{v:,.0f}")
        ch = "n/a" if r["change"] is None else (f"{r['change']:+.1f} pts" if r["kind"] == "pts" else f"{r['change']:+.1f}%")
        out.append(f"{r['label']}: {f(r['this'])} (before {f(r['last'])}, {ch})")
    out += ["", d["note"]]
    return "\n".join(out)


def send_now(smtp_factory=None) -> dict:
    d = what_changed()
    to = mailer.send(f"Weekly report ({workspaces.active()})", _text(d), smtp_factory=smtp_factory)
    c = config()
    c["last_sent"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state.setting_set(workspaces.active(), "weekly_report", c)
    state.audit("weekly_report_sent", ", ".join(to))
    return {"sent_to": to}


def due(now: datetime | None = None) -> bool:
    c = config()
    now = now or datetime.now(timezone.utc)
    return bool(c["enabled"] and mailer.configured() and now.weekday() == c["weekday"] and c["last_sent"] != now.strftime("%Y-%m-%d"))


def tick() -> list[str]:
    if due():
        c = config()                      # mark the attempt first so a failing mail server isn't retried every minute
        c["last_sent"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        state.setting_set(workspaces.active(), "weekly_report", c)
        try:
            send_now()
            return ["weekly_report"]
        except Exception:  # noqa: BLE001
            return []
    return []
