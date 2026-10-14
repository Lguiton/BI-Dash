"""Full stack software tools: CRUD scaffold writer, API contract writer, code review report, deploy runbook, and a feature-based quote helper.

All output is text for you to read, edit and paste. Nothing is written to disk or deployed. Names are validated so a bad table or field name cannot become code."""
from __future__ import annotations

import html
import json
import math
import re
import time

from app.services import code_check, script_gen

E = html.escape
NAME = re.compile(r"^[a-z][a-z0-9_]{0,40}$")
PYT = {"text": "str", "integer": "int", "number": "float", "decimal": "float", "date": "date", "timestamp": "datetime", "bool": "bool"}
JST = {"text": "string", "integer": "number", "number": "number", "decimal": "number", "date": "string", "timestamp": "string", "bool": "boolean"}
HTMLT = {"text": "text", "integer": "number", "number": "number", "decimal": "number", "date": "date", "timestamp": "datetime-local", "bool": "checkbox"}


class FsError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _cols(cols) -> list[dict]:
    if not isinstance(cols, list) or not cols:
        raise FsError("Add at least one field.")
    out, seen = [], set()
    for c in cols[:30]:
        n, t = str(c.get("name") or ""), c.get("type", "text")
        if not NAME.match(n):
            raise FsError(f"Field name '{n}' must be lowercase letters, numbers and underscores, starting with a letter.")
        if n in seen or n == "id":
            raise FsError(f"'{n}' is repeated or reserved: every table gets an id automatically.")
        if t not in PYT:
            raise FsError("Field type must be one of: " + ", ".join(PYT) + ".")
        seen.add(n)
        out.append({"name": n, "type": t, "required": bool(c.get("required"))})
    return out


def scaffold(table: str, fields: list[dict], dialect: str = "sqlite") -> dict:
    if not NAME.match(table or ""):
        raise FsError("Table name must be lowercase letters, numbers and underscores, starting with a letter.")
    cs = _cols(fields)
    ddl = script_gen.create_table(dialect, table, [{"name": "id", "type": "integer", "primary": True}] + [{"name": c["name"], "type": c["type"], "nullable": not c["required"]} for c in cs])["code"]
    cls = "".join(w.title() for w in table.split("_"))
    needs_date = any(c["type"] in ("date", "timestamp") for c in cs)
    model = "\n".join(f"    {c['name']}: {PYT[c['type']]}" + ("" if c["required"] else " | None = None") for c in sorted(cs, key=lambda c: not c["required"]))
    names = [c["name"] for c in cs]
    api = f'''from datetime import date, datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sqlite3

router = APIRouter(prefix="/api/{table}", tags=["{table}"])
DB = "app.db"   # change to your database path


class {cls}In(BaseModel):
{model}


def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con


@router.get("")
def list_items(limit: int = 100, offset: int = 0):
    with db() as con:
        rows = con.execute("SELECT * FROM {table} ORDER BY id DESC LIMIT ? OFFSET ?", (min(limit, 500), offset)).fetchall()
    return [dict(r) for r in rows]


@router.get("/{{item_id}}")
def get_item(item_id: int):
    with db() as con:
        r = con.execute("SELECT * FROM {table} WHERE id = ?", (item_id,)).fetchone()
    if not r:
        raise HTTPException(404, "Not found")
    return dict(r)


@router.post("", status_code=201)
def create_item(body: {cls}In):
    with db() as con:
        cur = con.execute("INSERT INTO {table} ({', '.join(names)}) VALUES ({', '.join('?' for _ in names)})", ({', '.join('body.' + n for n in names)},))
    return {{"id": cur.lastrowid}}


@router.put("/{{item_id}}")
def update_item(item_id: int, body: {cls}In):
    with db() as con:
        cur = con.execute("UPDATE {table} SET {', '.join(n + ' = ?' for n in names)} WHERE id = ?", ({', '.join('body.' + n for n in names)}, item_id))
    if cur.rowcount == 0:
        raise HTTPException(404, "Not found")
    return {{"id": item_id}}


@router.delete("/{{item_id}}")
def delete_item(item_id: int):
    with db() as con:
        cur = con.execute("DELETE FROM {table} WHERE id = ?", (item_id,))
    if cur.rowcount == 0:
        raise HTTPException(404, "Not found")
    return {{"deleted": item_id}}
'''
    form = f'<form id="{table}-form">\n' + "\n".join(f'  <label>{E(c["name"].replace("_", " ").title())}\n    <input name="{c["name"]}" type="{HTMLT[c["type"]]}"{" required" if c["required"] else ""}></label>' for c in cs) + f'\n  <button type="submit">Save</button>\n</form>\n<script>\ndocument.getElementById("{table}-form").addEventListener("submit", async (e) => {{\n  e.preventDefault();\n  const f = new FormData(e.target);\n  const body = Object.fromEntries(f.entries());\n  const r = await fetch("/api/{table}", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify(body) }});\n  if (!r.ok) {{ alert("Could not save"); return; }}\n  e.target.reset();\n}});\n</script>\n'
    files = [{"path": f"{table}.sql", "language": "sql", "code": ddl}, {"path": f"routers/{table}.py", "language": "python", "code": api}, {"path": f"{table}_form.html", "language": "html", "code": form}]
    return {"files": files, "explain": [f"A table, five API calls (list, get, create, update, delete) and a plain HTML form for {table}.", "Every database value is passed as a bound parameter, never pasted into the SQL text.",
                                          "Number fields in the form arrive as text: the API converts them, and rejects anything that is not a number."],
            "run_first": ["Run the SQL on a test database.", f"Register the router in your app: app.include_router({table}.router).", "Add your own login check before exposing this to anyone: the scaffold has none."],
            "verify": f"Open /docs in your FastAPI app and try POST /api/{table} with sample data, then GET it back.",
            "caution": "A starting point, not a finished feature. It has no login, no input limits beyond types, and no paging beyond a simple limit. Add those before real users touch it." + (" Dates are sent as text in ISO form (2026-01-31)." if needs_date else "")}


# ------------------------------------------------------------------ API contract
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")


def api_contract(title: str, endpoints: list[dict]) -> dict:
    if not endpoints:
        raise FsError("Add at least one endpoint.")
    paths: dict = {}
    md = [f"# {re.sub(r'[^A-Za-z0-9 _.-]', '', title or 'API')[:80] or 'API'}\n"]
    for e in endpoints[:60]:
        m, p = str(e.get("method", "")).upper(), str(e.get("path", ""))
        if m not in METHODS:
            raise FsError("Method must be one of: " + ", ".join(METHODS) + ".")
        if not re.fullmatch(r"/[A-Za-z0-9_\-/{}]{0,100}", p):
            raise FsError(f"Path '{p}' must start with / and use letters, numbers, - _ / and {{id}}.")
        req = {f["name"]: f.get("type", "text") for f in (e.get("request") or []) if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,40}", str(f.get("name", "")))}
        res = {f["name"]: f.get("type", "text") for f in (e.get("response") or []) if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,40}", str(f.get("name", "")))}
        summ = re.sub(r"[\x00-\x1f]", " ", str(e.get("summary") or ""))[:160]
        schema = lambda d: {"type": "object", "properties": {k: {"type": JST.get(v, "string")} for k, v in d.items()}}  # noqa: E731
        op = {"summary": summ, "responses": {"200": {"description": "OK", "content": {"application/json": {"schema": schema(res)}}}, "400": {"description": "Bad input"}, "401": {"description": "Not signed in"}, "404": {"description": "Not found"}}}
        if req and m in ("POST", "PUT", "PATCH"):
            op["requestBody"] = {"required": True, "content": {"application/json": {"schema": schema(req)}}}
        paths.setdefault(p, {})[m.lower()] = op
        md.append(f"## {m} {p}\n{summ}\n")
        if req:
            md.append("**Send:** " + ", ".join(f"`{k}` ({v})" for k, v in req.items()) + "\n")
        md.append("**Get back:** " + (", ".join(f"`{k}` ({v})" for k, v in res.items()) or "nothing specific") + "\n\n**Errors:** 400 bad input, 401 not signed in, 404 not found\n")
        sample = {k: ("text" if v == "text" else 1 if JST.get(v) == "number" else True if v == "bool" else "2026-01-31") for k, v in req.items()}
        md.append(f"**Example:**\n```\ncurl -X {m} https://your-site{p}" + (f" -H 'Content-Type: application/json' -d '{json.dumps(sample)}'" if req and m in ("POST", "PUT", "PATCH") else "") + "\n```\n")
    spec = {"openapi": "3.0.3", "info": {"title": title or "API", "version": "0.1.0"}, "paths": paths}
    return {"markdown": "\n".join(md), "openapi": spec, "caution": "A contract written before the code. Keep it in the repo and update it in the same change as the code, or it will lie."}


# ------------------------------------------------------------------ code review report
def review_report(code: str, language: str = "auto", project: str = "") -> str:
    try:
        r = code_check.check(code, language)
    except code_check.CodeError as e:
        raise FsError(e.message) from None
    rows = "".join(f"<tr><td>{E(str(f['line'] or ''))}</td><td>{E(f['severity'])}</td><td>{E(f['message'])}</td><td>{E(f.get('hint') or '')}</td></tr>" for f in r["findings"]) or "<tr><td colspan=4>Nothing found</td></tr>"
    manual = ["Does each function do one thing, and is its name honest?", "Are user inputs validated before they reach a database, a file or a command?", "Are secrets (keys, passwords) kept out of the code?", "Is there a test for the behavior that matters most?", "What happens when the network, disk or database fails?", "Would someone new understand this in 10 minutes?"]
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Code review</title><style>body{{font-family:system-ui,sans-serif;max-width:860px;margin:24px auto;padding:0 16px}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{border:1px solid #ccc;padding:5px;text-align:left}}h2{{font-size:15px;border-bottom:1px solid #ccc}}</style></head><body>"
            f"<h1>Code review: {E(project[:80] or 'untitled')}</h1><p>{E(r['language'])} &middot; {r['lines']} lines &middot; {E(time.strftime('%Y-%m-%d'))}</p><h2>Automatic checks</h2><p>{E(r['says'])}</p>"
            f"<table><tr><th>Line</th><th>Level</th><th>Finding</th><th>Suggestion</th></tr>{rows}</table><h2>Questions for a person to answer</h2><ul>{''.join('<li>&#9744; ' + E(m) + '</li>' for m in manual)}</ul>"
            f"<p style='font-size:12px;color:#555'>{E(r['caution'])} The automatic checks find common mistakes only; they do not review design or security in depth.</p></body></html>")


# ------------------------------------------------------------------ deploy runbook
def runbook(kind: str = "web_app", host: str = "vps", domain: str = "") -> dict:
    if kind not in ("web_app", "api", "static_site"):
        raise FsError("kind must be web_app, api or static_site.")
    if host not in ("vps", "paas", "docker"):
        raise FsError("host must be vps, paas or docker.")
    if domain and not re.fullmatch(r"[A-Za-z0-9.\-]{3,100}", domain):
        raise FsError("Enter the domain like example.com.")
    sec = [("Before the first deploy", ["All secrets are in environment variables, not in the code or the repository", "The app runs from a clean checkout on a second machine", "Tests pass", "Debug mode is off", "Database backups are on and one restore has been tried"]),
           ("Server and network", {"vps": ["Server updated, SSH by key only, password login off", "Firewall allows only 22, 80 and 443", "App runs as a normal user, not root", "App restarts by itself after a reboot (systemd)"],
                                   "paas": ["Environment variables set in the host's dashboard", "Spending limit set on the account", "Health check path configured"],
                                   "docker": ["Image built from a pinned base image", "Container runs as a non-root user", "Only the needed port is exposed", "Volumes hold the data, so redeploys do not erase it"]}[host]),
           ("Web", ([f"DNS for {domain} points at the server", "HTTPS certificate installed and renewing automatically"] if domain else ["HTTPS certificate installed and renewing automatically"]) + ["HTTP redirects to HTTPS", "Security headers set (HSTS, no framing, content type)"] + ([] if kind == "static_site" else ["Login, if any, is rate limited", "Error pages do not show stack traces"])),
           ("Go live", ["Take a backup first", "Deploy at a quiet time", "Click through the main path yourself", "Watch the logs for 15 minutes"]),
           ("If it breaks (rollback)", ["Know the previous version's tag or commit before you start", "Redeploy that version", "If the database changed, restore the backup taken just before", "Write down what happened and fix it before trying again"]),
           ("After", ["Uptime monitoring pointed at the site, alerting your phone", "Disk space and error alerts", "A calendar reminder to renew the domain", "Written handoff for the client: where it runs, who pays, how to get help"])]
    md = [f"# Deploy runbook: {kind.replace('_', ' ')} on {host}" + (f" ({domain})" if domain else "") + "\n"]
    for t, items in sec:
        md.append(f"## {t}\n" + "\n".join(f"- [ ] {i}" for i in items) + "\n")
    return {"markdown": "\n".join(md), "caution": "A checklist, not a guarantee. Adjust it to your host's real steps and keep it with the project."}


# ------------------------------------------------------------------ quote helper
def quote(features: list[dict], rate: float, buffer_pct: float = 20, discount_pct: float = 0, deposit_pct: float = 40) -> dict:
    if not features:
        raise FsError("Add at least one feature.")
    try:
        rt, bf, ds, dp = float(rate), float(buffer_pct), float(discount_pct), float(deposit_pct)
    except (TypeError, ValueError):
        raise FsError("Rate, buffer and discount must be numbers.") from None
    if rt <= 0 or not 0 <= bf <= 100 or not 0 <= ds <= 50 or not 0 <= dp <= 100:
        raise FsError("Check the numbers: rate above 0, buffer 0-100%, discount 0-50%, deposit 0-100%.")
    rows, lo, hi = [], 0.0, 0.0
    for i, f in enumerate(features[:60], 1):
        try:
            a, b = float(f["hours_low"]), float(f["hours_high"])
        except (KeyError, TypeError, ValueError):
            raise FsError(f"Feature {i} needs low and high hour estimates.") from None
        if not 0 <= a <= b:
            raise FsError(f"Feature {i}: the low estimate cannot be more than the high estimate.")
        lo, hi = lo + a, hi + b
        rows.append({"name": re.sub(r"[\x00-\x1f]", " ", str(f.get("name") or f"Feature {i}"))[:80], "hours_low": a, "hours_high": b})
    hl, hh = lo * (1 + bf / 100), hi * (1 + bf / 100)
    pl, ph = hl * rt * (1 - ds / 100), hh * rt * (1 - ds / 100)
    fixed = round(math.ceil((pl + ph) / 2 / 50) * 50)
    return {"features": rows, "hours_before_buffer": [round(lo, 1), round(hi, 1)], "hours_with_buffer": [round(hl, 1), round(hh, 1)], "price_range": [round(pl, 2), round(ph, 2)], "suggested_fixed_price": fixed,
            "payments": [{"when": "On signing", "amount": round(fixed * dp / 100, 2)}, {"when": "Midpoint", "amount": round(fixed * (100 - dp) / 200, 2)}, {"when": "Final delivery", "amount": round(fixed - round(fixed * dp / 100, 2) - round(fixed * (100 - dp) / 200, 2), 2)}],
            "says": f"{lo:g} to {hi:g} hours of work; with a {bf:g}% buffer for meetings, fixes and changes that is {hl:.0f} to {hh:.0f} hours, or ${pl:,.0f} to ${ph:,.0f}. A fixed quote of ${fixed:,} sits near the middle.",
            "caution": "The buffer exists because unknowns always cost time. If the scope is vague, quote the high end or sell a paid discovery phase first. Put exclusions and a change process in the statement of work."}
