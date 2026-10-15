"""Triage checklists: step-by-step lists you tick off on a job.

Three starting lists (a slow database, a messy network rack, a huge data file) written from the reading you gave me, in plain words for small-business jobs.
You start a list on a job, tick items as you go and keep a note; the ticks are saved with the job. Nothing runs commands or contacts anything.
The lists are a first pass from reading, not a standard: change what doesn't fit the job in front of you. Notes are cleaned of passwords and keys."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from app.services import clients, state
from app.services.fixlog import hide_secrets

KEY = "job_checklists"

SRC_DB = ("Written from 'Database Performance at Scale' (Cardeneti Mendes, Sarna, Emelyanov and Dunlop, 2023, CC BY 4.0), mainly chapters 5, 7 and 9 to 11, "
          "and shortened and reworded for small-business databases. The book is about very large databases, so some of its advice (clusters, replicas) is left out.")
SRC_NET = ("Informed by the Patchbox whitepaper on network rack cabling. It is a vendor document, so its statistics and product claims are not used here; "
           "only the problems it describes (overlength cable, strain on ports, airflow, slow maintenance, doors that won't close).")
SRC_FILE = ("Informed by the UltraEdit whitepaper 'Editing Big Data'. It is a vendor document; the advice here is about the file types and limits it describes, "
            "not about any product.")


def _l(sections: list[tuple[str, list[tuple[str, str]]]]) -> list[dict]:
    out = []
    for si, (title, items) in enumerate(sections, 1):
        out.append({"title": title, "items": [{"id": f"s{si}.{ii}", "text": t, "why": w} for ii, (t, w) in enumerate(items, 1)]})
    return out


TEMPLATES: list[dict] = [
    {"id": "slow-database", "title": "Slow database triage", "field": "Data cleanup and engineering", "source": SRC_DB,
     "when": "A client says their database, report or app is slow, or queries take much longer than they used to.",
     "sections": _l([
         ("1. Before you touch anything", [
             ("Make sure there is a recent backup or copy of the database, and write down when it was made.", "A fix attempt must never be the only thing standing between the client and their data."),
             ("Ask what is slow, since when, and what changed (new data, an update, a new app, a new backup or report job).", "Most slowdowns start with a change."),
             ("Ask if it is slow all the time or only at certain times (busy hours, backup time, month end).", "Timing points at competing work, not the database itself."),
             ("Write down a baseline with numbers: how long the slow thing takes now. Use the slowest typical cases, not only the average.", "The book stresses looking at the slow tail (P99), because that is what users feel."),
         ]),
         ("2. Find the bottleneck", [
             ("Check the machine: CPU busy? Memory nearly full? Disk busy or nearly full? Network slow between the app and the database?", "Find which resource is the limit before changing anything."),
             ("Rule out the app side: is the slowness in the database, or in the app, the report tool or the network in between?", "The book warns about client-side bottlenecks and network problems being blamed on the database."),
             ("Check timeouts and retries in the app. Look for the same request being retried over and over.", "Retries can pile more work onto a database that is already struggling."),
             ("Check if the data now fits in memory. If the database grew much larger than the RAM, expect more disk reads.", "Reads that miss the cache go to disk, which is far slower."),
         ]),
         ("3. Look at the work being asked of it", [
             ("Find the slowest and the most repeated queries (the database's slow-query log or the app's report list).", "A few queries usually cause most of the load."),
             ("For each, check how many rows it reads and whether it has a useful index or filter.", "Reading far more rows than needed is the most common cause."),
             ("Check reports and exports that pull everything at once. Page them or run them off-hours.", "Large one-off jobs compete with everyday use."),
             ("Check for background work running at busy times: backups, index rebuilds or cleanups, antivirus scans, updates.", "Chapter 11: even helpful admin work uses resources and hurts when it runs at the wrong time."),
         ]),
         ("4. Make one change at a time", [
             ("Pick one change, say what you expect it to do, and make it on a copy first if you can.", "Changing several things at once hides which one worked."),
             ("Repeat the same test you used for the baseline and write down the new numbers.", "Same test, same conditions, or the comparison means nothing."),
             ("If it did not help, undo it and write that down, then try the next idea.", "Keep the record so you don't repeat dead ends."),
             ("Reschedule backups and heavy jobs to quiet hours if they were colliding with busy times.", "Often the cheapest real fix."),
         ]),
         ("5. Close it out", [
             ("Compare before and after numbers and tell the client in plain words what was wrong and what you changed.", "Clients want the result, not the technical trail."),
             ("Say if the real fix is bigger (more memory, faster disk, a new design) and give a quote for that as a separate job.", "Don't quietly turn a quick fix into a project."),
             ("Set up a simple check or reminder so a repeat slowdown is spotted early.", "The book recommends watching a few key numbers regularly instead of waiting for complaints."),
             ("Write the findings and the change into the job's closing note.", "It is the record you will need next time."),
         ]),
     ])},
    {"id": "network-rack", "title": "Network rack and cabling tidy-up", "field": "Network engineering", "source": SRC_NET,
     "when": "A client's network closet or rack is tangled, hot, hard to maintain or has no documentation, or you are installing new equipment in a rack.",
     "sections": _l([
         ("1. Plan it before touching a cable", [
             ("Agree a time with the client, and tell them there may be short outages while you work.", "Moving cables drops connections."),
             ("Take photos of the rack before you start (front and back).", "Proof of how it was, and a guide to put things back."),
             ("Back up the configuration of switches and routers that you can, and note the passwords are stored safely, not in the notes.", "If a device gets knocked loose or reset, you can restore it."),
             ("Make a port map: what plugs into which switch port and patch panel port. Label before you unplug when you can.", "Without a map, every change is a guess."),
         ]),
         ("2. Safety", [
             ("Heavy equipment (switches, servers, batteries) needs two people or a rack shelf or lift. Don't hold it with one hand while fastening.", "The whitepaper points out injuries and dropped hardware when mounting alone."),
             ("Mind sharp cage nuts and rack edges. Keep spare cage nuts and screws in a pouch, not loose on the floor of the rack.", "Small parts get lost and hands get cut."),
         ]),
         ("3. Tidy the cabling", [
             ("Work one device or one panel at a time so the network is never fully down.", "Easier to undo."),
             ("Replace overlong patch cables with the right length where you can. Bundle only the extra that can't be avoided, loosely.", "Overlength cable is the main cause of tangles and blocked airflow."),
             ("Don't pull cables tight or bend them sharply. Leave a little slack at each port.", "Strain on ports causes loose connections."),
             ("Use Velcro straps rather than tight zip ties, and keep power cables apart from network cables.", "Tight ties can damage cable and slow future changes."),
             ("Label both ends of every cable with the same name, and match it to the port map.", "Troubleshooting becomes minutes instead of hours."),
         ]),
         ("4. Airflow and security", [
             ("Check that cables are not blocking fans or vents, and that hot air can leave the rack.", "Cable clutter can make equipment overheat and fail sooner."),
             ("Make sure the rack or closet door closes and locks.", "The whitepaper notes tangled cables that stop doors closing are a physical security risk."),
         ]),
         ("5. Test and hand over", [
             ("Check every link light and test the important connections: internet, Wi-Fi access points, phones, printers, servers.", "Don't leave until things the client uses work."),
             ("Take after photos and update the port map. Give the client a copy.", "The map is part of what you are selling."),
             ("Note anything you could not fix (old cable, no space, no spare power) and offer it as a follow-up quote.", "Keep scope clear."),
             ("Write the work into the job's closing note.", ""),
         ]),
     ])},
    {"id": "big-file", "title": "Huge data file cleanup", "field": "Data cleanup and engineering", "source": SRC_FILE,
     "when": "A client gives you a very large CSV, SQL dump, log or text file that won't open properly in Excel or a normal editor.",
     "sections": _l([
         ("1. Protect the original", [
             ("Copy the file first and work on the copy. Keep the original untouched.", "A bad edit on a huge file is hard to spot or undo."),
             ("Write down the file name, size, type (CSV, SQL, log, plain text) and where it came from.", "Starts the job record."),
             ("Check you have enough free disk space for the copy and the result (at least the size of the file again, often more).", "Large edits can fail halfway when the disk fills."),
         ]),
         ("2. Look before you change", [
             ("Look at the first and last few lines without opening the whole file (a tool that streams the file, or Python, DuckDB or a command like head).", "A normal editor loads the whole file into memory and may freeze."),
             ("Check the delimiter, the text encoding and whether the first line is a header.", "Wrong settings make everything after look broken."),
             ("Check that rows have the same number of columns, and look for quoted commas or line breaks inside fields.", "Real files are rarely perfectly regular."),
             ("Count the rows. Excel stops at 1,048,576 rows, and large files can slow or crash it well before that.", "If it is bigger, don't use Excel as the working tool."),
         ]),
         ("3. Choose the right tool", [
             ("If you only need to view or search it, use a viewer or editor made for big files.", "Simple jobs don't need a database."),
             ("If you need to filter, join or summarize, load it into DuckDB or SQLite, or process it in chunks with Python.", "Databases are built for large tables and are much faster than a spreadsheet."),
             ("If the client needs it in Excel, split it into pieces that fit, or send them a summary table instead of the raw data.", "Give clients something they can open."),
         ]),
         ("4. Clean it", [
             ("Try each change on a small sample first and check the result by eye.", "Catches mistakes cheaply."),
             ("Apply the changes to the full copy. Keep a short list of exactly what you did (find and replace rules, removed rows, fixed dates).", "You need it to explain and repeat the work."),
             ("Check that row counts before and after make sense, and that totals you can verify still match.", "Silent data loss is the worst failure."),
             ("Look for duplicates and blanks in the key columns, and decide with the client how to handle them.", "Those are business choices, not yours to make alone."),
         ]),
         ("5. Hand it over", [
             ("Save the result as a new file with a clear name and date. Don't overwrite the copy you started from.", ""),
             ("Send only what the client needs, by a safe method, and don't send the original if it holds private data they didn't ask to share.", "Large files with personal data need care."),
             ("Write what you did, the before and after counts, and anything left unresolved into the job's closing note.", ""),
         ]),
     ])},
]
BY_ID = {t["id"]: t for t in TEMPLATES}


class CheckError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _item_ids(t: dict) -> list[str]:
    return [i["id"] for s in t["sections"] for i in s["items"]]


def templates() -> dict:
    return {"templates": [{**t, "total": len(_item_ids(t))} for t in TEMPLATES],
            "note": "A first pass from the reading you gave me, written for small jobs. Change what doesn't fit the job in front of you."}


def _state() -> dict:
    raw = state.kv_get(KEY)
    try:
        d = json.loads(raw) if raw else {}
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def _job(job_id: int) -> dict:
    j = next((j for j in clients._load()["jobs"] if j.get("id") == job_id), None)
    if j is None:
        raise CheckError("No such job.", 404)
    return j


def _tpl(tid: str) -> dict:
    t = BY_ID.get(tid)
    if t is None:
        raise CheckError("No such checklist.", 404)
    return t


def _view(tid: str, st: dict) -> dict:
    t = BY_ID[tid]
    ids = set(_item_ids(t))
    checked = [c for c in st.get("checked", []) if c in ids]
    return {"template_id": tid, "title": t["title"], "checked": checked, "notes": st.get("notes", ""), "started": st.get("started", ""),
            "total": len(ids), "done": len(checked)}


def for_job(job_id: int) -> dict:
    _job(job_id)
    mine = _state().get(str(job_id), {})
    return {"job_id": job_id, "lists": [_view(tid, st) for tid, st in mine.items() if tid in BY_ID]}


def start(job_id: int, tid: str) -> dict:
    _job(job_id)
    _tpl(tid)
    d = _state()
    mine = d.setdefault(str(job_id), {})
    mine.setdefault(tid, {"checked": [], "notes": "", "started": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")})
    state.kv_set(KEY, json.dumps(d))
    return _view(tid, mine[tid])


def save(job_id: int, tid: str, body: dict) -> dict:
    _job(job_id)
    t = _tpl(tid)
    d = _state()
    st = d.get(str(job_id), {}).get(tid)
    if st is None:
        raise CheckError("Start this checklist on the job first.", 404)
    if "checked" in body:
        c = body["checked"]
        ids = set(_item_ids(t))
        if not isinstance(c, list) or any(not isinstance(x, str) or x not in ids for x in c):
            raise CheckError("Those items are not on this checklist.")
        st["checked"] = [i for i in _item_ids(t) if i in set(c)]
    if "notes" in body:
        st["notes"] = hide_secrets(re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(body["notes"] or "")).strip()[:2000])[0]
    state.kv_set(KEY, json.dumps(d))
    return _view(tid, st)


def remove(job_id: int, tid: str) -> dict:
    _job(job_id)
    _tpl(tid)
    d = _state()
    if d.get(str(job_id), {}).pop(tid, None) is None:
        raise CheckError("That checklist isn't on this job.", 404)
    state.kv_set(KEY, json.dumps(d))
    return {"removed": tid}
