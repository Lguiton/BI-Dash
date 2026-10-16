"""One page per job: the client, the quote, hours, work-log items, fixes for that client and invoices, plus a client-ready summary when the job is done.

This only gathers what the app already has. The summary lists what YOU wrote (job notes, log lines you added by hand, fixes written for the client);
status changes and timer lines are left out. It never sends anything: you download it and hand it over yourself. In Practice it is stamped SAMPLE."""
from __future__ import annotations

import html

from app.services import clients, fixlog, jobsteps, jobfield, worklog

SYSTEM_LOG = ("Added", "Marked ", "Timer ", "Left off:", "Linked to job", "Unlinked from")


def overview(jid: int) -> dict:
    t = clients.job_totals(jid)
    cname = (t["client"] or {}).get("name", "")
    fixes = []
    if cname:
        fixes = [f for f in fixlog.listing()["fixes"] if (f.get("client") or "").strip().lower() == cname.strip().lower()]
    items = worklog.for_job(jid)
    ready = bool(items) and all(i["status"] == "done" for i in items) and t["job"]["status"] != "done"
    t["job"] = {**t["job"], "field_info": jobfield.of_job(t["job"])}
    return {**t, "work_items": items, "ready_to_close": ready,
            "fixes": [{"id": f["id"], "title": f["title"], "area": f["area_label"], "result": f["result_label"], "created_at": f["created_at"]} for f in fixes[:20]],
            "fixes_note": f"Fixes logged with the client name '{cname}'." if cname else ""}


def close(jid: int, bill: str = "time") -> dict:
    added = worklog.stop_running_for_job(jid)
    res = clients.close_job(jid, bill)
    res["items_closed"] = worklog.complete_for_job(jid)
    res["timer_hours_added"] = added
    return res


def _summary_parts(jid: int) -> dict:
    """What a client summary says, for the PDF (the web page above builds the same content as HTML)."""
    o = overview(jid)
    done = []
    if (o["job"].get("notes") or "").strip():
        done.append(o["job"]["notes"].strip())
    for it in o["work_items"]:
        manual = [x["text"] for x in it["log"] if not x["text"].startswith(SYSTEM_LOG)]
        done.append(it["title"] + (": " + "; ".join(manual) if manual else ""))
    fixes = [fixlog.get(f["id"]) for f in o["fixes"]]
    note = ""
    try:
        from app.services import prep
        dr = prep._drafts().get(f"job:{jid}")
        if dr and dr.get("status") == "accepted" and dr.get("text"):
            note = dr["text"]
    except Exception:  # noqa: BLE001 - the summary still works without it
        pass
    return {"o": o, "done": done or ["Work completed as agreed."], "fixes": fixes, "note": note}


def summary_pdf(jid: int) -> tuple[bytes, str]:
    from app.services import pdfdocs
    p = _summary_parts(jid)
    o = p["o"]
    j, c = o["job"], o["client"] or {}
    blocks: list[tuple] = [("h", "What was done"), ("bullets", p["done"])]
    if p["note"]:
        blocks += [("h", "Closing note"), ("p", p["note"])]
    if p["fixes"]:
        blocks.append(("h", "Fixes and write-ups"))
        for rec in p["fixes"]:
            blocks.append(("p", rec["title"]))
            if rec["symptoms"]:
                blocks.append(("kv", [("Problem", rec["symptoms"])]))
            if rec["steps"]:
                blocks.append(("bullets", rec["steps"]))
            blocks.append(("kv", [("Result", rec["result_label"])] + ([("How to avoid it next time", rec["prevention"])] if rec["prevention"] else [])))
    if o["invoices"]:
        blocks += [("h", "Invoices"), ("bullets", [f"{i['number']} ({i['status']}): ${i['total']:,.2f}" for i in o["invoices"]])]
    blocks += [("sp", 8), ("small", "Please keep this summary for your records. Questions? Contact me and mention the job title above.")]
    sub = f"For {c.get('name', '')} - started {j['created']} - status: {j['status']} - {o['hours']:g} hours recorded"
    return pdfdocs.build(f"Job summary: {j['title']}", blocks, subtitle=sub, sample=o["sample"]), f"job-summary-{jid}.pdf"


def summary_html(jid: int) -> str:
    o = overview(jid)
    j, c, e = o["job"], o["client"] or {}, html.escape
    done = []
    if (j.get("notes") or "").strip():
        done.append(j["notes"].strip())
    for it in o["work_items"]:
        manual = [x["text"] for x in it["log"] if not x["text"].startswith(SYSTEM_LOG)]
        done.append(it["title"] + (": " + "; ".join(manual) if manual else ""))
    fixes_html = ""
    for f in o["fixes"]:
        rec = fixlog.get(f["id"])
        steps = "".join(f"<li>{e(s)}</li>" for s in rec["steps"])
        fixes_html += (f"<h3>{e(rec['title'])}</h3>" + (f"<p><b>Problem:</b> {e(rec['symptoms'])}</p>" if rec["symptoms"] else "") + (f"<ul>{steps}</ul>" if steps else "")
                       + f"<p><b>Result:</b> {e(rec['result_label'])}</p>" + (f"<p><b>How to avoid it next time:</b> {e(rec['prevention'])}</p>" if rec["prevention"] else ""))
    note = ""
    try:
        from app.services import prep
        dr = prep._drafts().get(f"job:{jid}")
        if dr and dr.get("status") == "accepted" and dr.get("text"):
            note = "<h2>Closing note</h2><p>" + e(dr["text"]).replace("\n", "<br>") + "</p>"
    except Exception:  # noqa: BLE001 - the summary still works without it
        pass
    banner = "<p class=sample>SAMPLE: made in the Practice workspace.</p>" if o["sample"] else ""
    lis = "".join(f"<li>{e(x)}</li>" for x in done) or "<li>Work completed as agreed.</li>"
    inv = "".join(f"<li>{e(i['number'])} ({e(i['status'])}): ${i['total']:,.2f}</li>" for i in o["invoices"])
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Job summary: {e(j['title'])}</title><style>body{{font:15px/1.5 system-ui,Arial,sans-serif;max-width:760px;margin:2rem auto;padding:0 1rem;color:#111}}
h1{{font-size:1.5rem}}h2{{font-size:1.1rem;margin-top:1.6rem;border-bottom:1px solid #ddd}}h3{{font-size:1rem;margin-bottom:.2rem}}.sample{{background:#fff3cd;padding:.4rem .6rem;border-radius:4px}}.m{{color:#555}}</style></head><body>{banner}
<h1>Job summary: {e(j['title'])}</h1><p class=m>For {e(c.get('name', ''))} · started {e(j['created'])} · status: {e(j['status'])} · {o['hours']:g} hours recorded</p>
<h2>What was done</h2><ul>{lis}</ul>{note}{('<h2>Fixes and write-ups</h2>' + fixes_html) if fixes_html else ''}{('<h2>Invoices</h2><ul>' + inv + '</ul>') if inv else ''}
<p class=m>Please keep this summary for your records. Questions? Contact me and mention the job title above.</p></body></html>"""


def quick_start(title: str, client: str = "", client_id: int | None = None, field: str | None = None, steps: bool = True, due: str | None = None, quote: float | None = None) -> dict:
    """Start a job from one line: finds the client by name (or makes one), makes an active job and the field's usual steps (the first ready to time).
    The field is the one you pick, else a guess from the title. With no template for the field, or steps=False, it makes one step named after the job. Nothing is sent anywhere."""
    title = (title or "").strip()
    if not title:
        raise clients.ClientError("Type what the job is.")
    d = clients._load()
    cid = int(client_id or 0)
    if not cid:
        name = (client or "").strip()
        if not name:
            raise clients.ClientError("Pick a client or type a new client name.")
        hit = next((c for c in d["clients"] if not c["archived"] and c["name"].strip().lower() == name.lower()), None)
        cid = hit["id"] if hit else clients.add_client({"name": name})["id"]
    f = field or jobfield.guess(title)
    body = {"client_id": cid, "title": title, "status": "active", "field": f}
    if due:
        body["due"] = due
    if quote:
        body["quote"] = quote
    job = clients.add_job(body)
    names = jobsteps.for_job(title, f) if steps else []
    items = [worklog.add({"title": n, "status": "doing" if i == 0 else "todo", "job_id": job["id"]}) for i, n in enumerate(names)]
    if not items:
        items = [worklog.add({"title": title, "status": "doing", "job_id": job["id"]})]
    return {"job": job, "work_item": items[0], "work_items": items, "field": jobfield.of_job(job)}
