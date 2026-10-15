"""Clients, jobs, hours, invoices and follow-ups for your own freelance work, plus a handoff pack you can give a paying client.

Stored per workspace in the state file, so Practice (fake) and Real clients never mix. Amounts are plain arithmetic you can check:
an invoice line is quantity x rate, an invoice total is the sum of its lines. Nothing here sends anything anywhere; invoices and packs
are files you hand over yourself. In Practice every invoice and pack is stamped SAMPLE so it cannot be mistaken for a real one."""
from __future__ import annotations

import html
import io
import json
import re
import zipfile
from datetime import date, datetime, timedelta

from app.services import state, workspaces

JOB_STATUS = ("lead", "quoted", "active", "done", "lost")
INV_STATUS = ("draft", "sent", "paid", "void")


class ClientError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _key() -> str:
    return f"clients:{workspaces.active()}"


def _load() -> dict:
    raw = state.kv_get(_key())
    d = json.loads(raw) if raw else {}
    for k in ("clients", "jobs", "time", "invoices", "followups", "packs"):
        d.setdefault(k, [])
    d.setdefault("next", {})
    d.setdefault("settings", {"rate": 75.0, "terms_days": 14, "business": "", "pay_to": ""})
    return d


def _save(d: dict) -> None:
    state.kv_set(_key(), json.dumps(d))


def _nid(d: dict, kind: str) -> int:
    d["next"][kind] = d["next"].get(kind, 0) + 1
    return d["next"][kind]


def _txt(v, name, limit=200, required=False) -> str:
    s = re.sub(r"[\x00-\x08\x0b-\x1f]", " ", str(v or "")).strip()[:limit]
    if required and not s:
        raise ClientError(f"{name} is required.")
    return s


def _num(v, name, lo=0.0, hi=1e7, default=0.0) -> float:
    if v in (None, ""):
        return default
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ClientError(f"{name} must be a number.") from None
    if not lo <= x <= hi:
        raise ClientError(f"{name} must be between {lo:g} and {hi:g}.")
    return x


def _date(v, name, default=None) -> str | None:
    if not v:
        return default
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date().isoformat()
    except ValueError:
        raise ClientError(f"{name} must be a date like 2026-10-31.") from None


def _find(d: dict, kind: str, i: int) -> dict:
    for r in d[kind]:
        if r["id"] == i:
            return r
    raise ClientError("Not found.", 404)


def sample() -> bool:
    return workspaces.active() != "real"


# ------------------------------------------------------------------ settings and clients


def settings(changes: dict | None = None) -> dict:
    d = _load()
    if changes:
        s = d["settings"]
        s["rate"] = _num(changes.get("rate", s["rate"]), "rate", 0, 10000, 75)
        s["terms_days"] = int(_num(changes.get("terms_days", s["terms_days"]), "terms_days", 0, 365, 14))
        s["business"] = _txt(changes.get("business", s["business"]), "business", 80)
        s["pay_to"] = _txt(changes.get("pay_to", s["pay_to"]), "pay_to", 200)
        _save(d)
    return d["settings"]


def add_client(b: dict) -> dict:
    d = _load()
    c = {"id": _nid(d, "client"), "name": _txt(b.get("name"), "name", 80, True), "contact": _txt(b.get("contact"), "contact", 80), "email": _txt(b.get("email"), "email", 120),
         "notes": _txt(b.get("notes"), "notes", 1000), "tables": [], "created": date.today().isoformat(), "archived": False}
    d["clients"].append(c)
    _save(d)
    state.audit("client.add", f"id {c['id']}")
    return c


def update_client(cid: int, b: dict) -> dict:
    d = _load()
    c = _find(d, "clients", cid)
    for k, lim in (("name", 80), ("contact", 80), ("email", 120), ("notes", 1000)):
        if k in b:
            c[k] = _txt(b[k], k, lim, k == "name")
    if "archived" in b:
        c["archived"] = bool(b["archived"])
    if "tables" in b:
        c["tables"] = [_txt(t, "table", 80) for t in (b["tables"] or [])][:50]
    _save(d)
    return c


def delete_client(cid: int) -> dict:
    d = _load()
    _find(d, "clients", cid)
    for kind, f in (("jobs", "client_id"), ("invoices", "client_id"), ("followups", "client_id"), ("packs", "client_id")):
        d[kind] = [r for r in d[kind] if r.get(f) != cid]
    jobs = {j["id"] for j in d["jobs"]}
    d["time"] = [t for t in d["time"] if t["job_id"] in jobs]
    d["clients"] = [c for c in d["clients"] if c["id"] != cid]
    _save(d)
    state.audit("client.delete", f"id {cid}")
    return {"deleted": cid}


# ------------------------------------------------------------------ jobs, time, follow-ups


def add_job(b: dict) -> dict:
    d = _load()
    _find(d, "clients", int(b.get("client_id") or 0))
    st = b.get("status") or "lead"
    if st not in JOB_STATUS:
        raise ClientError("status must be one of: " + ", ".join(JOB_STATUS) + ".")
    j = {"id": _nid(d, "job"), "client_id": int(b["client_id"]), "title": _txt(b.get("title"), "title", 120, True), "status": st, "quote": _num(b.get("quote"), "quote"), "rate": _num(b.get("rate"), "rate", 0, 10000, 0) or None,
         "due": _date(b.get("due"), "due"), "notes": _txt(b.get("notes"), "notes", 1000), "created": date.today().isoformat()}
    d["jobs"].append(j)
    _save(d)
    return j


def update_job(jid: int, b: dict) -> dict:
    d = _load()
    j = _find(d, "jobs", jid)
    if "status" in b:
        if b["status"] not in JOB_STATUS:
            raise ClientError("status must be one of: " + ", ".join(JOB_STATUS) + ".")
        j["status"] = b["status"]
    if "title" in b:
        j["title"] = _txt(b["title"], "title", 120, True)
    if "quote" in b:
        j["quote"] = _num(b["quote"], "quote")
    if "rate" in b:
        j["rate"] = _num(b["rate"], "rate", 0, 10000, 0) or None
    if "due" in b:
        j["due"] = _date(b["due"], "due")
    if "notes" in b:
        j["notes"] = _txt(b["notes"], "notes", 1000)
    _save(d)
    return j


def delete_job(jid: int) -> dict:
    d = _load()
    _find(d, "jobs", jid)
    d["jobs"] = [j for j in d["jobs"] if j["id"] != jid]
    d["time"] = [t for t in d["time"] if t["job_id"] != jid]
    _save(d)
    return {"deleted": jid}


def add_time(b: dict) -> dict:
    d = _load()
    j = _find(d, "jobs", int(b.get("job_id") or 0))
    t = {"id": _nid(d, "time"), "job_id": j["id"], "date": _date(b.get("date"), "date", date.today().isoformat()), "hours": _num(b.get("hours"), "hours", 0.01, 24, 0), "note": _txt(b.get("note"), "note", 200),
         "billable": b.get("billable", True) is not False, "invoice_id": None}
    if not t["hours"]:
        raise ClientError("hours must be more than 0.")
    d["time"].append(t)
    _save(d)
    return t


def delete_time(tid: int) -> dict:
    d = _load()
    t = _find(d, "time", tid)
    if t["invoice_id"]:
        raise ClientError("That time is already on an invoice. Void the invoice first.", 409)
    d["time"] = [x for x in d["time"] if x["id"] != tid]
    _save(d)
    return {"deleted": tid}


def add_followup(b: dict) -> dict:
    d = _load()
    _find(d, "clients", int(b.get("client_id") or 0))
    f = {"id": _nid(d, "follow"), "client_id": int(b["client_id"]), "job_id": b.get("job_id") or None, "due": _date(b.get("due"), "due", (date.today() + timedelta(days=3)).isoformat()), "note": _txt(b.get("note"), "note", 200, True), "done": False}
    d["followups"].append(f)
    _save(d)
    return f


def update_followup(fid: int, b: dict) -> dict:
    d = _load()
    f = _find(d, "followups", fid)
    if "done" in b:
        f["done"] = bool(b["done"])
    if "due" in b:
        f["due"] = _date(b["due"], "due")
    _save(d)
    return f


def delete_followup(fid: int) -> dict:
    d = _load()
    _find(d, "followups", fid)
    d["followups"] = [f for f in d["followups"] if f["id"] != fid]
    _save(d)
    return {"deleted": fid}


# ------------------------------------------------------------------ invoices


def inv_total(inv: dict) -> float:
    return round(sum(round(l["qty"] * l["rate"], 2) for l in inv["lines"]), 2)


def unbilled(client_id: int | None = None) -> list[dict]:
    d = _load()
    jobs = {j["id"]: j for j in d["jobs"]}
    out = []
    for t in d["time"]:
        j = jobs.get(t["job_id"])
        if t["billable"] and not t["invoice_id"] and j and (client_id is None or j["client_id"] == client_id):
            out.append({**t, "job_title": j["title"], "client_id": j["client_id"]})
    return out


def create_invoice(b: dict) -> dict:
    """Build an invoice from the client's unbilled billable time (grouped by job: hours x rate), plus any extra lines you type."""
    d = _load()
    cid = int(b.get("client_id") or 0)
    _find(d, "clients", cid)
    s = d["settings"]
    jobs = {j["id"]: j for j in d["jobs"]}
    lines, used = [], []
    if b.get("from_time", True):
        by: dict[int, list[dict]] = {}
        for t in d["time"]:
            j = jobs.get(t["job_id"])
            if t["billable"] and not t["invoice_id"] and j and j["client_id"] == cid and (not b.get("job_id") or j["id"] == int(b["job_id"])):
                by.setdefault(j["id"], []).append(t)
        for jid, ts in by.items():
            hrs = round(sum(t["hours"] for t in ts), 2)
            lines.append({"desc": f"{jobs[jid]['title']} ({hrs:g} h)", "qty": hrs, "rate": jobs[jid]["rate"] or s["rate"]})
            used += [t["id"] for t in ts]
    for x in b.get("extra") or []:
        lines.append({"desc": _txt(x.get("desc"), "desc", 120, True), "qty": _num(x.get("qty"), "qty", 0.01, 100000, 1), "rate": _num(x.get("rate"), "rate", 0, 1e7, 0)})
    if not lines:
        raise ClientError("Nothing to invoice: there is no unbilled billable time and no extra lines.")
    n = _nid(d, "invoice")
    issued = _date(b.get("issued"), "issued", date.today().isoformat())
    inv = {"id": n, "number": f"INV-{n:04d}", "client_id": cid, "issued": issued, "due": _date(b.get("due"), "due", (date.fromisoformat(issued) + timedelta(days=s["terms_days"])).isoformat()),
           "lines": lines, "status": "draft", "paid_date": None, "notes": _txt(b.get("notes"), "notes", 300)}
    for t in d["time"]:
        if t["id"] in used:
            t["invoice_id"] = n
    d["invoices"].append(inv)
    _save(d)
    state.audit("invoice.create", inv["number"])
    return {**inv, "total": inv_total(inv)}


def set_invoice(iid: int, status: str, paid_date: str | None = None) -> dict:
    if status not in INV_STATUS:
        raise ClientError("status must be one of: " + ", ".join(INV_STATUS) + ".")
    d = _load()
    inv = _find(d, "invoices", iid)
    if inv["status"] == "void":
        raise ClientError("A void invoice can't be changed.", 409)
    inv["status"] = status
    inv["paid_date"] = (_date(paid_date, "paid_date", date.today().isoformat())) if status == "paid" else None
    if status == "void":
        for t in d["time"]:
            if t["invoice_id"] == iid:
                t["invoice_id"] = None
    _save(d)
    state.audit("invoice.status", f"{inv['number']} {status}")
    return {**inv, "total": inv_total(inv)}


def invoice_html(iid: int) -> str:
    d = _load()
    inv = _find(d, "invoices", iid)
    c = _find(d, "clients", inv["client_id"])
    s, e = d["settings"], html.escape
    rows = "".join(f"<tr><td>{e(l['desc'])}</td><td class=n>{l['qty']:g}</td><td class=n>${l['rate']:,.2f}</td><td class=n>${l['qty'] * l['rate']:,.2f}</td></tr>" for l in inv["lines"])
    banner = "<p class=sample>SAMPLE: made in the Practice workspace. Not a real invoice.</p>" if sample() else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(inv['number'])}</title><style>body{{font:15px/1.5 system-ui,Arial,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#1b1f1d}}
table{{border-collapse:collapse;width:100%;margin:1rem 0}}td,th{{padding:.4rem .5rem;border-bottom:1px solid #ddd;text-align:left}}.n{{text-align:right;font-variant-numeric:tabular-nums}}.sample{{background:#fff3cd;border:1px solid #e0b000;padding:.5rem;font-weight:600}}
.tot{{font-size:1.2rem;font-weight:700}}</style></head><body>{banner}<h1>Invoice {e(inv['number'])}</h1><p>{e(s['business'])}</p><p><b>Bill to:</b> {e(c['name'])}{' · ' + e(c['contact']) if c['contact'] else ''}<br>
<b>Issued:</b> {e(inv['issued'])} &nbsp; <b>Due:</b> {e(inv['due'])} &nbsp; <b>Status:</b> {e(inv['status'])}</p>
<table><tr><th>Description</th><th class=n>Qty</th><th class=n>Rate</th><th class=n>Amount</th></tr>{rows}</table><p class="n tot">Total ${inv_total(inv):,.2f}</p>
{('<p>' + e(inv['notes']) + '</p>') if inv['notes'] else ''}{('<p><b>Pay to:</b> ' + e(s['pay_to']) + '</p>') if s['pay_to'] else ''}</body></html>"""


# ------------------------------------------------------------------ overview


def overview(today: date | None = None) -> dict:
    d = _load()
    t = today or date.today()
    ti = t.isoformat()
    inv_open = [i for i in d["invoices"] if i["status"] == "sent"]
    overdue = [i for i in inv_open if i["due"] < ti]
    month = ti[:7]
    cname = {c["id"]: c["name"] for c in d["clients"]}
    unb = unbilled()
    jobs = {j["id"]: j for j in d["jobs"]}
    rate = d["settings"]["rate"]
    unb_amt = round(sum(x["hours"] * (jobs[x["job_id"]]["rate"] or rate) for x in unb), 2)
    due_fu = sorted([f for f in d["followups"] if not f["done"] and f["due"] <= ti], key=lambda f: f["due"])
    return {"sample": sample(), "clients": len([c for c in d["clients"] if not c["archived"]]), "jobs_active": len([j for j in d["jobs"] if j["status"] == "active"]),
            "pipeline": round(sum(j["quote"] for j in d["jobs"] if j["status"] in ("lead", "quoted")), 2),
            "outstanding": round(sum(inv_total(i) for i in inv_open), 2), "overdue": [{**i, "total": inv_total(i), "client": cname.get(i["client_id"], "?"), "days_late": (t - date.fromisoformat(i["due"])).days} for i in overdue],
            "paid_this_month": round(sum(inv_total(i) for i in d["invoices"] if i["status"] == "paid" and (i["paid_date"] or "").startswith(month)), 2),
            "unbilled_hours": round(sum(x["hours"] for x in unb), 2), "unbilled_amount": unb_amt,
            "followups_due": [{**f, "client": cname.get(f["client_id"], "?")} for f in due_fu], "settings": d["settings"],
            "note": "Unbilled amount uses each job's rate, or your default rate. Paid this month counts invoices marked paid in the current month."}


def open_jobs(today: date | None = None) -> list[dict]:
    """Jobs still in play (lead, quoted, active), soonest due first, with the client name and hours so far."""
    d = _load()
    ti = (today or date.today()).isoformat()
    cname = {c["id"]: c["name"] for c in d["clients"] if not c["archived"]}
    out = []
    for j in d["jobs"]:
        if j["status"] not in ("lead", "quoted", "active") or j["client_id"] not in cname:
            continue
        hrs = round(sum(t["hours"] for t in d["time"] if t["job_id"] == j["id"]), 2)
        out.append({"id": j["id"], "title": j["title"], "status": j["status"], "client_id": j["client_id"], "client": cname[j["client_id"]],
                    "quote": j["quote"], "hours": hrs, "due": j["due"], "late": bool(j["due"] and j["due"] < ti and j["status"] == "active")})
    out.sort(key=lambda x: (x["due"] is None, x["due"] or "", x["id"]))
    return out


def client_view(cid: int) -> dict:
    d = _load()
    c = _find(d, "clients", cid)
    jobs = [j for j in d["jobs"] if j["client_id"] == cid]
    jid = {j["id"] for j in jobs}
    hrs = {j["id"]: round(sum(t["hours"] for t in d["time"] if t["job_id"] == j["id"]), 2) for j in jobs}
    return {"client": c, "jobs": [{**j, "hours": hrs[j["id"]]} for j in jobs], "time": [t for t in d["time"] if t["job_id"] in jid], "invoices": [{**i, "total": inv_total(i)} for i in d["invoices"] if i["client_id"] == cid],
            "followups": [f for f in d["followups"] if f["client_id"] == cid], "packs": [p for p in d["packs"] if p["client_id"] == cid], "unbilled": unbilled(cid)}


def list_clients() -> list[dict]:
    d = _load()
    return [{**c, "jobs": len([j for j in d["jobs"] if j["client_id"] == c["id"]])} for c in d["clients"]]


# ------------------------------------------------------------------ handoff pack


def handoff_pack(cid: int, notes: dict, pack_id: str | None = None, days: int = 30, model_ids: list[str] | None = None, include_invoices: bool = True) -> tuple[bytes, dict]:
    """A zip you hand to the client: report.html (from a business dashboard, if you pick one), summary, invoices, model verdicts and your own notes on what was done, how to use it and its limits."""
    d = _load()
    c = _find(d, "clients", cid)
    e = html.escape
    files: dict[str, str] = {}
    stamp = "SAMPLE DATA (Practice workspace): not a client deliverable.\n\n" if sample() else ""
    prepared = d["settings"]["business"]
    if pack_id:
        from app.services import biz_report
        files["report.html"] = biz_report.to_html(biz_report.build(pack_id, days, c["name"], prepared))
    jobs = [j for j in d["jobs"] if j["client_id"] == cid]
    lines = [f"# Work summary for {c['name']}", "", stamp.strip(), "", "| Job | Status | Hours | Quote |", "|---|---|---|---|"]
    for j in jobs:
        h = round(sum(t["hours"] for t in d["time"] if t["job_id"] == j["id"]), 2)
        lines.append(f"| {j['title']} | {j['status']} | {h:g} | ${j['quote']:,.2f} |")
    if c["tables"]:
        lines += ["", "Data tables used: " + ", ".join(c["tables"])]
    if model_ids:
        from app.services import biz_models
        ms = [m for m in biz_models.list_models() if m["id"] in model_ids]
        if ms:
            lines += ["", "## Models", ""] + [f"- {m['label']}: predicts {m['target']}; verdict: {m['verdict']}" for m in ms] + ["", "A model is only as good as the data behind it. Re-check it as new data arrives."]
    files["summary.md"] = "\n".join(lines) + "\n"
    if include_invoices:
        for i in d["invoices"]:
            if i["client_id"] == cid and i["status"] != "void":
                files[f"invoice_{i['number']}.html"] = invoice_html(i["id"])
    n = {k: _txt(notes.get(k), k, 3000) for k in ("done", "how_to_use", "limits", "next")}
    files["notes.md"] = f"# Notes for {c['name']}\n\n{stamp}## What was done\n{n['done'] or '(not filled in)'}\n\n## How to use it\n{n['how_to_use'] or '(not filled in)'}\n\n## Limits and assumptions\n{n['limits'] or '(not filled in)'}\n\n## Suggested next steps\n{n['next'] or '(not filled in)'}\n"
    files["README.txt"] = f"Handoff pack for {c['name']}\nMade {date.today().isoformat()}{' by ' + prepared if prepared else ''}.\n\n" + stamp + "\n".join(f"- {k}" for k in sorted(files)) + "\n\nOpen the .html files in any web browser. Print to PDF from the browser if you want a PDF.\n"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in files.items():
            z.writestr(name, body)
    rec = {"id": _nid(d, "pack"), "client_id": cid, "made": date.today().isoformat(), "files": sorted(files), "sample": sample()}
    d["packs"].append(rec)
    _save(d)
    state.audit("handoff.pack", f"client {cid}, {len(files)} files")
    return buf.getvalue(), rec


# ------------------------------------------------------------------ one job: totals, and closing it
def job_totals(jid: int) -> dict:
    """Hours and money for one job, so the job page and the close step use the same arithmetic."""
    d = _load()
    j = _find(d, "jobs", jid)
    c = next((x for x in d["clients"] if x["id"] == j["client_id"]), None)
    rate = j["rate"] or d["settings"]["rate"]
    times = sorted([t for t in d["time"] if t["job_id"] == jid], key=lambda t: (t["date"], t["id"]))
    inv = {i["id"]: i for i in d["invoices"]}
    hours = round(sum(t["hours"] for t in times), 2)
    unb = round(sum(t["hours"] for t in times if t["billable"] and not t["invoice_id"]), 2)
    inv_ids = sorted({t["invoice_id"] for t in times if t["invoice_id"]})
    return {"job": j, "client": c, "rate": rate, "time": [{**t, "invoice": inv[t["invoice_id"]]["number"] if t["invoice_id"] in inv else None} for t in times],
            "hours": hours, "unbilled_hours": unb, "unbilled_amount": round(unb * rate, 2),
            "invoices": [{"id": i, "number": inv[i]["number"], "status": inv[i]["status"], "total": inv_total(inv[i])} for i in inv_ids if i in inv], "sample": sample()}


def close_job(jid: int, bill: str = "time") -> dict:
    """Mark the job done and optionally invoice it. bill='time' invoices unbilled billable hours; 'quote' invoices the quoted price as one line; 'none' only closes."""
    if bill not in ("time", "quote", "none"):
        raise ClientError("bill must be 'time', 'quote' or 'none'.")
    t = job_totals(jid)
    j = t["job"]
    invoice, why = None, ""
    if bill == "time":
        if t["unbilled_hours"] > 0:
            invoice = create_invoice({"client_id": j["client_id"], "job_id": jid})
        else:
            why = "There was no unbilled billable time, so nothing was invoiced."
    elif bill == "quote":
        if not j["quote"] or j["quote"] <= 0:
            raise ClientError("This job has no quoted price. Add one, or choose to bill the hours.")
        invoice = create_invoice({"client_id": j["client_id"], "from_time": False, "extra": [{"desc": f"{j['title']} (fixed price)", "qty": 1, "rate": j["quote"]}]})
    d = _load()
    _find(d, "jobs", jid)["status"] = "done"
    _save(d)
    state.audit("job.close", f"id {jid} bill={bill}" + (f" {invoice['number']}" if invoice else ""))
    return {"job": update_job(jid, {"status": "done"}), "invoice": invoice, "note": why}
