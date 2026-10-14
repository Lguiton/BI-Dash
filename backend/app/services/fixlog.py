"""Fix log: every fix you make is written down so the next time the same problem shows up you can find what was tried and what worked.

Used for IT repair, cybersecurity and network work. It is a searchable record plus write-ups you can hand to a client. The search matches the
words you use (and close spellings and related words); it does not understand meaning, so a record is only as findable as it is well written.
Passwords, keys and tokens are blanked before anything is stored.
"""
from __future__ import annotations

import html
import json
import re

from app.services import state, workspaces

AREAS = {"it": "IT repair", "security": "Cybersecurity", "network": "Network"}
RESULTS = {"fixed": "Fixed", "workaround": "Workaround only", "not_fixed": "Not fixed yet"}


class FixError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    return workspaces.active()


# ------------------------------------------------------------------ secrets are blanked before storage
_SECRETS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?(-----END [A-Z ]*PRIVATE KEY-----|$)"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"(?i)\b(password|passwd|pwd|passcode|pin|secret|api[_ -]?key|token|bearer)\b(\s*(?:is|was|=|:)\s*)(\S{4,})"),
    re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"),
]


def hide_secrets(text: str) -> tuple[str, int]:
    n = 0

    def sub_kv(m):
        nonlocal n
        n += 1
        return f"{m.group(1)}{m.group(2)}[hidden]"

    def sub_all(m):
        nonlocal n
        n += 1
        return "[hidden]"

    out = _SECRETS[2].sub(sub_kv, text)
    for rx in (_SECRETS[0], _SECRETS[1], _SECRETS[3]):
        out = rx.sub(sub_all, out)
    return out, n


def _txt(v, name: str, limit: int, counter: list, required: bool = False) -> str:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(v or "")).strip()
    if required and not s:
        raise FixError(f"Add a {name}.")
    s = s[:limit]
    s, n = hide_secrets(s)
    counter[0] += n
    return s


def _clean(b: dict) -> tuple[dict, int]:
    c = [0]
    area = b.get("area") or "it"
    if area not in AREAS:
        raise FixError("Area must be one of: " + ", ".join(AREAS) + ".")
    result = b.get("result") or "fixed"
    if result not in RESULTS:
        raise FixError("Result must be one of: " + ", ".join(RESULTS) + ".")
    steps_in = b.get("steps") or []
    if isinstance(steps_in, str):
        steps_in = steps_in.splitlines()
    if not isinstance(steps_in, list):
        raise FixError("Steps must be a list.")
    steps = [x for x in (_txt(s, "step", 300, c) for s in steps_in[:40]) if x]
    tags_in = b.get("tags") or []
    if isinstance(tags_in, str):
        tags_in = re.split(r"[,\n]", tags_in)
    tags = [t for t in (re.sub(r"[^a-z0-9 _-]", "", str(t).lower()).strip()[:24] for t in tags_in[:10]) if t]
    try:
        minutes = int(float(b.get("minutes") or 0))
    except (TypeError, ValueError):
        raise FixError("Minutes must be a number.") from None
    if not 0 <= minutes <= 10000:
        raise FixError("Minutes must be between 0 and 10000.")
    tid = b.get("ticket_id")
    out = {"area": area, "title": _txt(b.get("title"), "short title", 120, c, True), "category": _txt(b.get("category"), "category", 60, c),
           "device": _txt(b.get("device"), "device", 120, c), "symptoms": _txt(b.get("symptoms"), "symptoms", 1200, c), "cause": _txt(b.get("cause"), "cause", 1200, c),
           "steps": steps, "result": result, "minutes": minutes, "tools": _txt(b.get("tools"), "tools", 300, c), "prevention": _txt(b.get("prevention"), "prevention", 800, c),
           "client": _txt(b.get("client"), "client", 80, c), "ticket_id": int(tid) if tid not in (None, "", 0) else None, "tags": tags}
    return out, c[0]


def _row(r: dict) -> dict:
    r["steps"] = json.loads(r["steps"] or "[]")
    r["tags"] = json.loads(r["tags"] or "[]")
    r["area_label"] = AREAS.get(r["area"], r["area"])
    r["result_label"] = RESULTS.get(r["result"], r["result"])
    return r


def add(b: dict) -> dict:
    d, masked = _clean(b)
    now = state.now()
    cur = state.run("INSERT INTO fix_log (workspace, area, title, category, device, symptoms, cause, steps, result, minutes, tools, prevention, client, ticket_id, tags, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (_ws(), d["area"], d["title"], d["category"], d["device"], d["symptoms"], d["cause"], json.dumps(d["steps"]), d["result"], d["minutes"], d["tools"], d["prevention"], d["client"],
                     d["ticket_id"], json.dumps(d["tags"]), now, now))
    fid = int(cur.lastrowid)
    state.audit("fixlog_add", f"{d['area']}: {d['title']}")
    if d["ticket_id"]:
        _note_ticket(d["ticket_id"], f"Saved to the fix log (#{fid}).")
    rec = get(fid)
    rec["masked"] = masked
    return rec


def _note_ticket(tid: int, text: str) -> None:
    try:
        from app.services import itlab
        itlab.update_ticket(tid, note=text)
    except Exception:  # the ticket may be gone; the fix record still stands
        pass


def get(fid: int) -> dict:
    r = state.one("SELECT * FROM fix_log WHERE id = ? AND workspace = ?", (fid, _ws()))
    if not r:
        raise FixError("No such fix record.", 404)
    return _row(r)


def update(fid: int, b: dict) -> dict:
    cur = get(fid)
    merged = {**cur, **{k: v for k, v in b.items() if k in cur}}
    d, masked = _clean(merged)
    state.run("UPDATE fix_log SET area=?, title=?, category=?, device=?, symptoms=?, cause=?, steps=?, result=?, minutes=?, tools=?, prevention=?, client=?, ticket_id=?, tags=?, updated_at=? WHERE id=?",
              (d["area"], d["title"], d["category"], d["device"], d["symptoms"], d["cause"], json.dumps(d["steps"]), d["result"], d["minutes"], d["tools"], d["prevention"], d["client"],
               d["ticket_id"], json.dumps(d["tags"]), state.now(), fid))
    state.audit("fixlog_update", f"#{fid}")
    rec = get(fid)
    rec["masked"] = masked
    return rec


def delete(fid: int) -> None:
    get(fid)
    state.run("DELETE FROM fix_log WHERE id = ?", (fid,))
    state.audit("fixlog_delete", f"#{fid}")


def listing(area: str | None = None) -> dict:
    sql, args = "SELECT * FROM fix_log WHERE workspace = ?", [_ws()]
    if area:
        if area not in AREAS:
            raise FixError("Unknown area.")
        sql += " AND area = ?"
        args.append(area)
    rows = [_row(r) for r in state.rows(sql + " ORDER BY id DESC", args)]
    by_result: dict[str, int] = {}
    for r in rows:
        by_result[r["result"]] = by_result.get(r["result"], 0) + 1
    timed = [r["minutes"] for r in rows if r["minutes"]]
    return {"fixes": rows, "areas": AREAS, "results": RESULTS,
            "stats": {"total": len(rows), "by_result": by_result, "avg_minutes": round(sum(timed) / len(timed)) if timed else None},
            "note": "Passwords, keys and tokens are blanked before saving. Write what you did, not what the secret was."}


# ------------------------------------------------------------------ finding a past fix
def _tokens(s: str) -> list[str]:
    from app.services.repair_search import _tok
    return _tok(s)


def search(q: str, area: str | None = None, limit: int = 8) -> dict:
    """Past fixes that share words with the question, best first. Also the built-in guides for the same words."""
    from app.services.repair_search import RELATED
    words = _tokens(q)[:12]
    if not words:
        return {"query": q, "fixes": [], "guides": []}
    exp = set(words)
    for w in words:
        exp.update(RELATED.get(w, []))
    weights = {"title": 5, "symptoms": 4, "tags": 3, "device": 2, "cause": 2, "category": 1.5, "steps": 1}
    out = []
    for r in listing(area)["fixes"]:
        parts = {"title": r["title"], "symptoms": r["symptoms"], "tags": " ".join(r["tags"]), "device": r["device"], "cause": r["cause"], "category": r["category"], "steps": " ".join(r["steps"])}
        toks = {k: set(_tokens(v)) for k, v in parts.items()}
        score, hit = 0.0, set()
        for w in exp:
            for part, wt in weights.items():
                if w in toks[part]:
                    score += wt * (1 if w in words else 0.5)
                    hit.add(w)
        if score:
            if r["result"] == "fixed":
                score *= 1.2
            out.append({**r, "score": round(score, 1), "matched": sorted(hit)[:6]})
    out.sort(key=lambda r: (-r["score"], -r["id"]))
    guides: list[dict] = []
    try:
        if area == "security":
            from app.services import sec_fixes
            guides = [{"id": g["id"], "title": g["title"], "area": g.get("area", "")} for g in sec_fixes.search(q, 5)]
        elif area in (None, "it", "network"):
            from app.services import repair_search
            guides = [{"id": g["id"], "title": g["title"], "area": g["area"]} for g in repair_search.search(q, 5)["results"]]
    except Exception:  # guides are a bonus; the fix log search must not fail because of them
        guides = []
    return {"query": q, "fixes": out[:limit], "guides": guides}


# ------------------------------------------------------------------ start a record from a ticket
def draft_from_ticket(tid: int) -> dict:
    from app.services import itlab
    try:
        t = itlab.get_ticket(tid)
    except itlab.ItError as e:
        raise FixError(e.message, e.status) from e
    steps = [c["text"] for c in t["checklist"] if c["done"]]
    for e in t["timeline"]:
        x = e["text"]
        if x.startswith(("Opened.", "Status:", "Priority changed", "Saved to the fix log")):
            if x.startswith("Opened.") and len(x) > 8:
                symptoms = x[8:].strip()
            continue
        steps.append(x)
    first = next((e["text"][8:].strip() for e in t["timeline"] if e["text"].startswith("Opened.")), "")
    area = "network" if t["category"] == "network" else "it"
    return {"area": area, "title": t["title"], "category": t["category_label"], "device": "", "symptoms": first, "cause": "", "steps": steps, "result": "fixed" if not t["is_open"] else "workaround",
            "minutes": 0, "tools": "", "prevention": "", "client": t["requester"], "ticket_id": tid, "tags": [t["category"]]}


# ------------------------------------------------------------------ write-ups
def _lines(r: dict, client: bool) -> list[tuple[str, str | list[str]]]:
    if client:
        return [("Problem", r["symptoms"] or r["title"]), ("What was done", r["steps"]), ("Result", r["result_label"]), ("How to avoid it next time", r["prevention"])]
    return [("Device or system", r["device"]), ("Category", r["category"]), ("Symptoms", r["symptoms"]), ("Cause", r["cause"]), ("Steps taken", r["steps"]), ("Result", r["result_label"]),
            ("Time spent", f"{r['minutes']} minutes" if r["minutes"] else ""), ("Tools or parts", r["tools"]), ("Prevention", r["prevention"]), ("Client", r["client"]),
            ("Tags", ", ".join(r["tags"]))]


def markdown(fid: int, client: bool = False) -> str:
    r = get(fid)
    out = [f"# {r['title']}", f"*{r['area_label']} · logged {r['created_at'][:10]}*", ""]
    for h, v in _lines(r, client):
        if not v:
            continue
        out.append(f"## {h}")
        out.extend(f"{i}. {s}" for i, s in enumerate(v, 1)) if isinstance(v, list) else out.append(v)
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def page(fid: int, client: bool = False) -> str:
    r = get(fid)
    body = [f"<h1>{html.escape(r['title'])}</h1><p class='m'>{html.escape(r['area_label'])} · logged {html.escape(r['created_at'][:10])}</p>"]
    for h, v in _lines(r, client):
        if not v:
            continue
        body.append(f"<h2>{html.escape(h)}</h2>")
        body.append("<ol>" + "".join(f"<li>{html.escape(s)}</li>" for s in v) + "</ol>" if isinstance(v, list) else f"<p>{html.escape(v)}</p>")
    return _wrap(r["title"], "".join(body))


def _wrap(title: str, body: str) -> str:
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>" + html.escape(title) + "</title>"
            "<style>body{font:15px/1.5 system-ui,sans-serif;max-width:46rem;margin:2rem auto;padding:0 1rem;color:#111}h1{font-size:1.5rem}h2{font-size:1rem;margin:1.2rem 0 .3rem;color:#1f3a5f}"
            ".m{color:#555;font-size:.85rem}section{border-top:1px solid #ccc;margin-top:1.5rem;padding-top:.5rem}@media print{section{break-inside:avoid}}</style></head><body>" + body + "</body></html>")


def export_all(area: str | None = None) -> str:
    """The whole knowledge base as one printable page, newest first."""
    rows = listing(area)["fixes"]
    if not rows:
        raise FixError("There are no fix records to export yet.")
    parts = [f"<h1>Fix log{' - ' + html.escape(AREAS[area]) if area else ''}</h1><p class='m'>{len(rows)} record{'s' if len(rows) != 1 else ''}</p>"]
    for r in rows:
        sec = [f"<section><h2 style='font-size:1.15rem;margin-top:0'>{html.escape(r['title'])}</h2><p class='m'>{html.escape(r['area_label'])} · {html.escape(r['result_label'])} · {html.escape(r['created_at'][:10])}</p>"]
        for h, v in _lines(r, False):
            if not v or h in ("Category", "Time spent", "Tags", "Result"):
                continue
            sec.append(f"<p><strong>{html.escape(h)}.</strong> " + ("</p><ol>" + "".join(f"<li>{html.escape(s)}</li>" for s in v) + "</ol>" if isinstance(v, list) else f"{html.escape(v)}</p>"))
        sec.append("</section>")
        parts.append("".join(sec))
    return _wrap("Fix log", "".join(parts))
