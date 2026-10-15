"""Extra items for the Today panel on Home: leads waiting on you, unbilled work, drafts, quotes waiting for a yes, thank-yous and the business backup.
Read-only. The existing panel keeps overdue invoices, follow-ups, late jobs and timers; this adds the rest."""
from __future__ import annotations

from datetime import date

from app.services import bizbackup, leads, money
from app.services import clients as cl


def build(today: date | None = None) -> dict:
    t = today or date.today()
    ti = t.isoformat()
    ov = cl.overview(t)
    jobs = cl.open_jobs(t)
    rec = money.receivables(t)
    ld = leads.due(t)
    try:
        bk = bizbackup.status()
    except Exception:  # noqa: BLE001 - the page still loads without the backup line
        bk = {"warning": "", "last": None}
    late_jobs = [j for j in jobs if j["late"]]
    due_today = [j for j in jobs if j["due"] == ti]
    active = [j for j in jobs if j["status"] == "active"]
    quoted = [j for j in jobs if j["status"] == "quoted"]
    # The Home page's Today panel already lists overdue invoices, follow-ups, late jobs and timers, so this list holds only what it doesn't.
    todo: list[dict] = []
    if ld:
        todo.append({"text": f"{len(ld)} lead{'s' if len(ld) != 1 else ''} {'need' if len(ld) != 1 else 'needs'} a next step: {', '.join(x['name'] for x in ld[:3])}.", "href": "/leads", "tone": "warn"})
    if ov["unbilled_amount"] > 0:
        todo.append({"text": f"${ov['unbilled_amount']:,.2f} of finished hours haven't been invoiced ({ov['unbilled_hours']:g} h).", "href": "/clients", "tone": "warn"})
    if rec["draft_total"] > 0:
        todo.append({"text": f"{len(rec['drafts'])} draft invoice{'s' if len(rec['drafts']) != 1 else ''} (${rec['draft_total']:,.2f}) not sent yet.", "href": "/money", "tone": "warn"})
    if quoted:
        todo.append({"text": f"{len(quoted)} quote{'s' if len(quoted) != 1 else ''} waiting for a yes: {', '.join(j['title'] for j in quoted[:3])}.", "href": f"/job?id={quoted[0]['id']}", "tone": "muted"})
    if rec["thank_you"]:
        todo.append({"text": f"{len(rec['thank_you'])} paid job{'s' if len(rec['thank_you']) != 1 else ''} with no thank-you or review ask yet.", "href": "/money", "tone": "muted"})
    if bk.get("warning"):
        todo.append({"text": bk["warning"], "href": "/settings", "tone": "warn"})
    return {"sample": cl.sample(), "date": ti, "todo": todo[:8], "jobs": {"late": late_jobs, "today": due_today, "active": active[:8], "quoted": quoted[:5]},
            "money": {"owed": rec["owed"], "late": rec["late"], "paid_this_month": ov["paid_this_month"], "unbilled_amount": ov["unbilled_amount"], "top_owed": rec["rows"][:3], "pipeline": ov["pipeline"]},
            "followups": ov["followups_due"], "leads_due": ld[:5], "backup": bk}
