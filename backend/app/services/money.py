"""Money tools for your own freelance work: who owes you, profit per job, expenses and mileage with a tax set-aside, and thank-you / review asks.

Everything is plain arithmetic you can check against the invoices and time you already logged. Reminders and thank-you notes are drafts
you copy and send yourself; nothing is sent from here. The tax figures are a planning aid, not tax advice: the set-aside is a percent
YOU choose, and the mileage rate is a number YOU keep current (check irs.gov for this year's rate)."""
from __future__ import annotations

import csv
import io
import json
from datetime import date, timedelta

from app.services import clients as cl
from app.services import state, workspaces
from app.services.clients import ClientError, _date, _find, _nid, _num, _txt

CATEGORIES = ("parts", "tools", "software", "vehicle", "phone and internet", "supplies", "advertising", "insurance and fees", "other")
BUCKETS = (("not_due", "Not due yet"), ("1-7", "1 to 7 days late"), ("8-14", "8 to 14 days late"), ("15-30", "15 to 30 days late"), ("31+", "Over 30 days late"))


def _key() -> str:
    return f"money:{workspaces.active()}"


def _load() -> dict:
    raw = state.kv_get(_key())
    try:
        d = json.loads(raw) if raw else {}
    except ValueError:
        d = {}
    for k in ("expenses", "mileage"):
        d.setdefault(k, [])
    d.setdefault("reminded", {})
    d.setdefault("thanked", {})
    d.setdefault("next", {})
    d.setdefault("settings", {})
    s = d["settings"]
    s.setdefault("tax_pct", 25.0)
    s.setdefault("mileage_rate", 0.70)
    s.setdefault("review_url", "")
    return d


def _save(d: dict) -> None:
    state.kv_set(_key(), json.dumps(d))


def settings(changes: dict | None = None) -> dict:
    d = _load()
    if changes:
        s = d["settings"]
        s["tax_pct"] = _num(changes.get("tax_pct", s["tax_pct"]), "Tax set-aside percent", 0, 60, 25)
        s["mileage_rate"] = _num(changes.get("mileage_rate", s["mileage_rate"]), "Mileage rate", 0, 5, 0.70)
        url = _txt(changes.get("review_url", s["review_url"]), "Review link", 300)
        if url and not url.lower().startswith(("https://", "http://")):
            raise ClientError("The review link must start with https://")
        s["review_url"] = url
        _save(d)
    return d["settings"]


# ------------------------------------------------------------------ who owes you


def _bucket(days_late: int) -> str:
    if days_late <= 0:
        return "not_due"
    if days_late <= 7:
        return "1-7"
    if days_late <= 14:
        return "8-14"
    if days_late <= 30:
        return "15-30"
    return "31+"


def receivables(today: date | None = None) -> dict:
    """Invoices marked sent and not yet paid, oldest first, grouped by how late they are. Drafts are listed apart: they were never sent."""
    t = today or date.today()
    d, m = cl._load(), _load()
    cname = {c["id"]: c for c in d["clients"]}
    rows, drafts = [], []
    for i in d["invoices"]:
        c = cname.get(i["client_id"], {"name": "?", "email": ""})
        base = {"id": i["id"], "number": i["number"], "client": c["name"], "client_id": i["client_id"], "email": c.get("email", ""), "total": cl.inv_total(i), "issued": i["issued"], "due": i["due"]}
        if i["status"] == "sent":
            late = (t - date.fromisoformat(i["due"])).days
            rows.append({**base, "days_late": late, "bucket": _bucket(late), "last_reminded": m["reminded"].get(str(i["id"]))})
        elif i["status"] == "draft":
            drafts.append({**base, "age_days": (t - date.fromisoformat(i["issued"])).days})
    rows.sort(key=lambda r: -r["days_late"])
    buckets = [{"id": b, "label": lab, "count": sum(1 for r in rows if r["bucket"] == b), "total": round(sum(r["total"] for r in rows if r["bucket"] == b), 2)} for b, lab in BUCKETS]
    cutoff = (t - timedelta(days=60)).isoformat()
    thanks = []
    for i in d["invoices"]:
        if i["status"] == "paid" and (i["paid_date"] or "") >= cutoff and str(i["id"]) not in m["thanked"]:
            thanks.append({"id": i["id"], "number": i["number"], "client": cname.get(i["client_id"], {"name": "?"})["name"], "total": cl.inv_total(i), "paid_date": i["paid_date"]})
    return {"sample": cl.sample(), "owed": round(sum(r["total"] for r in rows), 2), "late": round(sum(r["total"] for r in rows if r["days_late"] > 0), 2),
            "rows": rows, "buckets": buckets, "drafts": drafts, "draft_total": round(sum(x["total"] for x in drafts), 2),
            "thank_you": thanks, "review_url_set": bool(m["settings"]["review_url"]),
            "note": "Late means past the due date. A draft invoice has not been sent, so it is not counted as owed."}


def reminder(iid: int, today: date | None = None) -> dict:
    """A polite payment reminder you can copy. The tone gets firmer with age but stays factual: no threats and no late fees that you didn't agree to."""
    t = today or date.today()
    d = cl._load()
    inv = _find(d, "invoices", iid)
    if inv["status"] != "sent":
        raise ClientError("Only an invoice marked sent can get a reminder. Mark it sent first." if inv["status"] == "draft" else f"This invoice is {inv['status']}, so it doesn't need a reminder.", 409)
    c = _find(d, "clients", inv["client_id"])
    s = d["settings"]
    late = (t - date.fromisoformat(inv["due"])).days
    total = f"${cl.inv_total(inv):,.2f}"
    who = (c["contact"] or c["name"]).split()[0] if (c["contact"] or c["name"]) else "there"
    sign = s["business"] or "Thank you"
    pay = f"\n\nPayment details: {s['pay_to']}" if s["pay_to"] else ""
    if late <= 0:
        tone, subj = "heads-up", f"Invoice {inv['number']} is due {inv['due']}"
        body = f"Hi {who},\n\nA quick heads-up that invoice {inv['number']} for {total} is due on {inv['due']}. It is attached again in case it got buried.{pay}\n\nThank you for the business.\n\n{sign}"
    elif late <= 7:
        tone, subj = "friendly", f"Reminder: invoice {inv['number']} ({total})"
        body = f"Hi {who},\n\nInvoice {inv['number']} for {total} was due on {inv['due']}, so it is {late} day{'s' if late != 1 else ''} past due. If it has already gone out, thank you and please ignore this.{pay}\n\nLet me know if anything about the invoice needs fixing.\n\n{sign}"
    elif late <= 30:
        tone, subj = "firm", f"Past due: invoice {inv['number']} ({total}), {late} days"
        body = f"Hi {who},\n\nInvoice {inv['number']} for {total} was due on {inv['due']} and is now {late} days past due. Please send payment this week, or reply with the date you expect to pay.{pay}\n\nIf there is a problem with the work or the invoice, tell me and I will sort it out right away.\n\n{sign}"
    else:
        tone, subj = "final", f"Overdue: invoice {inv['number']} ({total}), {late} days"
        body = f"Hi {who},\n\nInvoice {inv['number']} for {total} is {late} days past its due date of {inv['due']}. I need to settle this account: please pay in full by {(t + timedelta(days=7)).isoformat()}, or call me to agree a payment plan.{pay}\n\nI would like to keep working together, so please get in touch.\n\n{sign}"
    return {"invoice_id": iid, "number": inv["number"], "to": c.get("email", ""), "client": c["name"], "days_late": late, "tone": tone, "subject": subj, "body": body,
            "note": "A draft for you to copy and send yourself. Nothing was sent."}


def mark_reminded(iid: int, today: date | None = None) -> dict:
    d = cl._load()
    _find(d, "invoices", iid)
    m = _load()
    m["reminded"][str(iid)] = (today or date.today()).isoformat()
    _save(m)
    return {"invoice_id": iid, "reminded": m["reminded"][str(iid)]}


def thank_you(iid: int) -> dict:
    """A thank-you note for a paid invoice with your review link (if you set one), plus a short ask for a referral."""
    d = cl._load()
    inv = _find(d, "invoices", iid)
    if inv["status"] != "paid":
        raise ClientError("A thank-you goes with a paid invoice. Mark this one paid first.", 409)
    c = _find(d, "clients", inv["client_id"])
    url = _load()["settings"]["review_url"]
    who = (c["contact"] or c["name"]).split()[0] if (c["contact"] or c["name"]) else "there"
    sign = d["settings"]["business"] or "Thank you again"
    ask = f"\n\nIf you were happy with the work, a short review would help a lot: {url}" if url else "\n\nIf you were happy with the work, a short review would help a lot."
    body = f"Hi {who},\n\nThank you for the payment on invoice {inv['number']}, and for trusting me with the work.{ask}\n\nIf you know a neighbor or a business that could use the same help, I would be glad to hear from them.\n\n{sign}"
    return {"invoice_id": iid, "number": inv["number"], "to": c.get("email", ""), "client": c["name"], "subject": f"Thank you ({inv['number']})", "body": body,
            "review_url_set": bool(url), "note": "A draft for you to copy and send yourself. Nothing was sent."}


def mark_thanked(iid: int, today: date | None = None) -> dict:
    d = cl._load()
    _find(d, "invoices", iid)
    m = _load()
    m["thanked"][str(iid)] = (today or date.today()).isoformat()
    _save(m)
    return {"invoice_id": iid, "thanked": m["thanked"][str(iid)]}


# ------------------------------------------------------------------ profit per job


def profit(today: date | None = None) -> dict:
    """For each job: what you charged (from invoices that aren't void), parts bought for it, and the hours you worked, so you can see what an hour really earned."""
    d, m = cl._load(), _load()
    cname = {c["id"]: c["name"] for c in d["clients"]}
    invs = {i["id"]: i for i in d["invoices"] if i["status"] != "void"}
    default_rate = d["settings"]["rate"]
    out = []
    for j in d["jobs"]:
        times = [t for t in d["time"] if t["job_id"] == j["id"]]
        hours = round(sum(t["hours"] for t in times), 2)
        seen: set[tuple[int, int]] = set()
        charged = paid = owed = draft = 0.0
        for iid in {t["invoice_id"] for t in times if t["invoice_id"]} | {i["id"] for i in invs.values() if i["client_id"] == j["client_id"]}:
            inv = invs.get(iid)
            if not inv:
                continue
            for idx, ln in enumerate(inv["lines"]):
                mine = ln["desc"].startswith(f"{j['title']} (") and (ln["desc"].endswith("(fixed price)") or ln["desc"].endswith(" h)"))
                if not mine or (iid, idx) in seen:
                    continue
                if ln["desc"].endswith(" h)") and iid not in {t["invoice_id"] for t in times}:
                    continue            # same title on another job of this client: its hours aren't on this job
                seen.add((iid, idx))
                amt = round(ln["qty"] * ln["rate"], 2)
                charged += amt
                if inv["status"] == "paid":
                    paid += amt
                elif inv["status"] == "sent":
                    owed += amt
                else:
                    draft += amt
        parts = round(sum(e["amount"] for e in m["expenses"] if e.get("job_id") == j["id"]), 2)
        if not (hours or charged or parts):
            continue
        net = round(charged - parts, 2)
        eff = round(net / hours, 2) if hours else None
        flag = ""
        if charged and not hours:
            flag = "No hours logged, so the hourly figure can't be worked out."
        elif eff is not None and charged and eff < 0.75 * default_rate:
            flag = f"Earned ${eff:,.2f} an hour, under 75% of your ${default_rate:,.2f} rate. Quote more next time, or log scope changes."
        elif hours and not charged and j["status"] == "done":
            flag = "Done, but nothing invoiced yet."
        out.append({"job_id": j["id"], "title": j["title"], "client": cname.get(j["client_id"], "?"), "client_id": j["client_id"], "status": j["status"], "hours": hours,
                    "charged": round(charged, 2), "paid": round(paid, 2), "owed": round(owed, 2), "draft": round(draft, 2), "parts": parts, "net": net, "per_hour": eff, "flag": flag})
    out.sort(key=lambda r: (r["per_hour"] is None, r["per_hour"] if r["per_hour"] is not None else 0))
    by_client: dict[str, dict] = {}
    for r in out:
        c = by_client.setdefault(r["client"], {"client": r["client"], "hours": 0.0, "charged": 0.0, "parts": 0.0})
        c["hours"] += r["hours"]
        c["charged"] += r["charged"]
        c["parts"] += r["parts"]
    clients_out = []
    for c in by_client.values():
        net = round(c["charged"] - c["parts"], 2)
        clients_out.append({**c, "hours": round(c["hours"], 2), "charged": round(c["charged"], 2), "parts": round(c["parts"], 2), "net": net, "per_hour": round(net / c["hours"], 2) if c["hours"] else None})
    clients_out.sort(key=lambda c: -c["net"])
    th = round(sum(r["hours"] for r in out), 2)
    tn = round(sum(r["net"] for r in out), 2)
    return {"sample": cl.sample(), "target_rate": default_rate, "jobs": out, "clients": clients_out,
            "totals": {"hours": th, "charged": round(sum(r["charged"] for r in out), 2), "parts": round(sum(r["parts"] for r in out), 2), "net": tn, "per_hour": round(tn / th, 2) if th else None},
            "note": "Charged = invoice lines for the job (not void). Net = charged minus parts you logged for the job. Per hour counts every hour logged, billable or not. Time that isn't on a job (driving, quoting) isn't counted, so real hourly earnings are lower."}


# ------------------------------------------------------------------ expenses, mileage, tax set-aside


def add_expense(b: dict) -> dict:
    d = _load()
    cat = _txt(b.get("category") or "other", "category", 40).lower()
    if cat not in CATEGORIES:
        raise ClientError("category must be one of: " + ", ".join(CATEGORIES) + ".")
    amount = _num(b.get("amount"), "amount", 0.01, 1e7, 0)
    if not amount:
        raise ClientError("amount must be more than 0.")
    job_id = b.get("job_id")
    if job_id not in (None, ""):
        _find(cl._load(), "jobs", int(job_id))
    e = {"id": _nid(d, "expense"), "date": _date(b.get("date"), "date", date.today().isoformat()), "amount": amount, "category": cat, "vendor": _txt(b.get("vendor"), "vendor", 80),
         "note": _txt(b.get("note"), "note", 200), "job_id": int(job_id) if job_id not in (None, "") else None}
    d["expenses"].append(e)
    _save(d)
    return e


def delete_expense(eid: int) -> dict:
    d = _load()
    _find(d, "expenses", eid)
    d["expenses"] = [e for e in d["expenses"] if e["id"] != eid]
    _save(d)
    return {"deleted": eid}


def add_mileage(b: dict) -> dict:
    d = _load()
    miles = _num(b.get("miles"), "miles", 0.1, 5000, 0)
    if not miles:
        raise ClientError("miles must be more than 0.")
    job_id = b.get("job_id")
    if job_id not in (None, ""):
        _find(cl._load(), "jobs", int(job_id))
    r = {"id": _nid(d, "mileage"), "date": _date(b.get("date"), "date", date.today().isoformat()), "miles": miles, "purpose": _txt(b.get("purpose"), "purpose", 160),
         "job_id": int(job_id) if job_id not in (None, "") else None}
    d["mileage"].append(r)
    _save(d)
    return r


def delete_mileage(mid: int) -> dict:
    d = _load()
    _find(d, "mileage", mid)
    d["mileage"] = [r for r in d["mileage"] if r["id"] != mid]
    _save(d)
    return {"deleted": mid}


def _quarter(day: str) -> int:
    return (int(day[5:7]) - 1) // 3 + 1


def _due_dates(year: int) -> list[str]:
    return [f"{year}-04-15", f"{year}-06-15", f"{year}-09-15", f"{year + 1}-01-15"]


def books(year: int | None = None, today: date | None = None) -> dict:
    t = today or date.today()
    year = year or t.year
    if not 2000 <= year <= 2100:
        raise ClientError("year must be between 2000 and 2100.")
    d, m = cl._load(), _load()
    s = m["settings"]
    ys = str(year)
    cname = {c["id"]: c["name"] for c in d["clients"]}
    paid = [i for i in d["invoices"] if i["status"] == "paid" and (i["paid_date"] or "").startswith(ys)]
    exps = [e for e in m["expenses"] if e["date"].startswith(ys)]
    trips = [r for r in m["mileage"] if r["date"].startswith(ys)]
    income = round(sum(cl.inv_total(i) for i in paid), 2)
    spent = round(sum(e["amount"] for e in exps), 2)
    miles = round(sum(r["miles"] for r in trips), 1)
    mile_ded = round(miles * s["mileage_rate"], 2)
    net = round(income - spent - mile_ded, 2)
    set_aside = round(max(0.0, net) * s["tax_pct"] / 100, 2)
    cats = [{"category": c, "total": round(sum(e["amount"] for e in exps if e["category"] == c), 2)} for c in CATEGORIES]
    quarters = []
    for q in (1, 2, 3, 4):
        qi = round(sum(cl.inv_total(i) for i in paid if _quarter(i["paid_date"]) == q), 2)
        qe = round(sum(e["amount"] for e in exps if _quarter(e["date"]) == q), 2)
        qm = round(sum(r["miles"] for r in trips if _quarter(r["date"]) == q) * s["mileage_rate"], 2)
        qn = round(qi - qe - qm, 2)
        quarters.append({"quarter": q, "income": qi, "expenses": qe, "mileage": qm, "net": qn, "set_aside": round(max(0.0, qn) * s["tax_pct"] / 100, 2)})
    due = _due_dates(year)
    nxt = next((x for x in due if x >= t.isoformat()), None)
    return {"sample": cl.sample(), "year": year, "settings": s, "income": income, "expenses_total": spent, "miles": miles, "mileage_deduction": mile_ded, "net": net, "set_aside": set_aside,
            "categories": cats, "quarters": quarters, "due_dates": due, "next_due": nxt,
            "paid": [{"number": i["number"], "client": cname.get(i["client_id"], "?"), "paid_date": i["paid_date"], "total": cl.inv_total(i), "set_aside": round(cl.inv_total(i) * s["tax_pct"] / 100, 2)} for i in sorted(paid, key=lambda i: i["paid_date"] or "")],
            "expenses": sorted(exps, key=lambda e: (e["date"], e["id"]), reverse=True), "mileage_log": sorted(trips, key=lambda r: (r["date"], r["id"]), reverse=True),
            "note": ("Income counts invoices by the date you marked them paid. Net = income minus expenses minus mileage at your rate. The set-aside is your chosen percent of net, to park in a separate account. "
                     "This is a planning aid, not tax advice: self-employment tax and income tax depend on your whole situation. US estimated-tax dates are usually April 15, June 15, September 15 and January 15 "
                     "(they move when one lands on a weekend or holiday); confirm on irs.gov or with a tax preparer. Keep receipts.")}


def _cell(v) -> str:
    s = "" if v is None else str(v)
    return "'" + s if s[:1] in ("=", "+", "-", "@", "\t", "\r") else s


def books_csv(year: int | None = None, today: date | None = None) -> tuple[str, str]:
    b = books(year, today)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["type", "date", "number_or_category", "who_or_note", "amount"])
    for p in b["paid"]:
        w.writerow(["income", p["paid_date"], p["number"], _cell(p["client"]), f"{p['total']:.2f}"])
    for e in b["expenses"][::-1]:
        w.writerow(["expense", e["date"], e["category"], _cell((e["vendor"] + " " + e["note"]).strip()), f"{-e['amount']:.2f}"])
    for r in b["mileage_log"][::-1]:
        w.writerow(["mileage", r["date"], f"{r['miles']:g} miles", _cell(r["purpose"]), f"{-r['miles'] * b['settings']['mileage_rate']:.2f}"])
    w.writerow([])
    w.writerow(["total", "", "net", f"income - expenses - mileage at {b['settings']['mileage_rate']}/mile", f"{b['net']:.2f}"])
    return buf.getvalue(), f"books-{b['year']}.csv"
