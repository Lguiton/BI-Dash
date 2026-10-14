"""Project and product management tools: SOW/proposal writer, weekly status report (from your board), three-point estimator, user-story writer with
acceptance criteria, now/next/later roadmap, and a decision and retro log.

The estimator is plain PERT arithmetic. The SOW and stories are templates filled from what you type: read them, edit them, and have a lawyer review any contract."""
from __future__ import annotations

import html
import json
import math
import re
import time
import uuid

from app.services import pm, state, workspaces

E = html.escape


class PmToolError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _t(v, n) -> str:
    return re.sub(r"[\x00-\x08\x0b-\x1f]", " ", str(v or "")).strip()[:n]


def _lines(v, n=20, each=300) -> list[str]:
    items = v if isinstance(v, list) else str(v or "").splitlines()
    return [_t(x, each) for x in items if _t(x, each)][:n]


def _kv(name: str, default: dict) -> dict:
    raw = state.kv_get(f"pmtools:{name}:{workspaces.active()}")
    d = json.loads(raw) if raw else {}
    for k, v in default.items():
        d.setdefault(k, v)
    return d


def _kv_set(name: str, d: dict) -> None:
    state.kv_set(f"pmtools:{name}:{workspaces.active()}", json.dumps(d))


def _sample() -> bool:
    return workspaces.active() != "real"


CSS = "body{font-family:system-ui,sans-serif;max-width:780px;margin:24px auto;padding:0 16px;color:#111}h1{font-size:22px}h2{font-size:15px;border-bottom:1px solid #ccc;margin-top:22px;padding-bottom:3px}table{border-collapse:collapse;width:100%;font-size:13px}td,th{border:1px solid #ccc;padding:5px;text-align:left}.sig{display:inline-block;width:46%;margin-top:34px;border-top:1px solid #000;padding-top:4px;font-size:12px}"
BANNER = "<p style='background:#fff3cd;border:1px solid #e0b000;padding:.5rem;font-weight:600'>SAMPLE: from the Practice workspace, not a client document.</p>"


# ------------------------------------------------------------------ SOW
def sow(f: dict) -> str:
    client, project = _t(f.get("client"), 100), _t(f.get("project"), 120)
    if not client or not project:
        raise PmToolError("Give the client's name and the project name.")
    objectives, deliverables = _lines(f.get("objectives")), _lines(f.get("deliverables"))
    if not deliverables:
        raise PmToolError("List at least one deliverable: a vague scope is how projects go wrong.")
    exclusions = _lines(f.get("exclusions")) or ["Anything not listed under Deliverables", "Ongoing support after the final handoff, unless agreed in writing", "Third-party software or hosting fees"]
    assumptions = _lines(f.get("assumptions")) or ["The client provides the data and access within 3 business days of asking", "One named person at the client approves each deliverable", "Feedback on each deliverable arrives within 5 business days"]
    weeks = _t(f.get("weeks"), 10) or "to be agreed"
    model = f.get("price_model", "fixed")
    try:
        price = float(f.get("price") or 0)
        rate = float(f.get("rate") or 0)
        rev = int(f.get("revisions", 2))
    except (TypeError, ValueError):
        raise PmToolError("Price, rate and revisions must be numbers.") from None
    if model == "fixed" and price <= 0:
        raise PmToolError("Enter the fixed price.")
    if model == "hourly" and rate <= 0:
        raise PmToolError("Enter the hourly rate.")
    if model not in ("fixed", "hourly"):
        raise PmToolError("price_model must be fixed or hourly.")
    money = f"A fixed fee of <b>${price:,.2f}</b>, invoiced 40% on signing, 30% at the midpoint, and 30% on final delivery." if model == "fixed" else f"Time at <b>${rate:,.2f} per hour</b>, invoiced every two weeks. Estimates are not a cap unless a cap is written here: {E(_t(f.get('cap'), 60) or 'no cap')}."
    ul = lambda xs: "<ul>" + "".join(f"<li>{E(x)}</li>" for x in xs) + "</ul>"  # noqa: E731
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Statement of work: {E(project)}</title><style>{CSS}</style></head><body>{BANNER if _sample() else ''}"
            f"<h1>Statement of work: {E(project)}</h1><p>Prepared for <b>{E(client)}</b> by {E(_t(f.get('provider'), 100) or 'the provider')} on {time.strftime('%B %d, %Y')}.</p>"
            f"<h2>1. Goal</h2>{ul(objectives) if objectives else '<p>To be written with the client.</p>'}<h2>2. Deliverables</h2>{ul(deliverables)}<h2>3. Not included</h2>{ul(exclusions)}"
            f"<h2>4. Timeline</h2><p>About <b>{E(weeks)}</b> weeks from the date the signed agreement and the first payment are received. Dates move if the client's items below arrive late.</p>"
            f"<h2>5. What we assume</h2>{ul(assumptions)}<h2>6. Price and payment</h2><p>{money}</p><p>Payment is due within 14 days of each invoice.</p>"
            f"<h2>7. Changes</h2><p>Each deliverable includes <b>{rev}</b> round(s) of revisions. Anything outside section 2 is a change request: it is described, priced and approved in writing before work starts.</p>"
            f"<h2>8. Acceptance</h2><p>A deliverable is accepted when the client approves it in writing or 5 business days pass after delivery with no written feedback.</p>"
            f"<h2>9. Ownership and confidentiality</h2><p>The client owns the final deliverables once paid in full. Each side keeps the other's information confidential and uses it only for this project.</p>"
            f"<div><span class='sig'>For {E(client)} &nbsp; Date</span> &nbsp; <span class='sig'>For {E(_t(f.get('provider'), 100) or 'the provider')} &nbsp; Date</span></div>"
            "<p style='font-size:11px;color:#555'>This is a plain-language template, not legal advice. Have a lawyer review it before using it with a client, especially clauses 7 to 9.</p></body></html>")


# ------------------------------------------------------------------ status report
def status_report(project: str = "", client: str = "") -> str:
    o = pm.overview()
    if o["empty"]:
        raise PmToolError("The project board is empty. Add work items in the Project track first (or load the example in Practice).")
    items = o["items"]
    ev = o["earned_value"]
    by = lambda s: [i for i in items if i["status"] == s]  # noqa: E731
    li = lambda xs, f: "".join(f"<li>{E(f(i))}</li>" for i in xs[:12]) or "<li>None</li>"  # noqa: E731
    open_risks = sorted([r for r in o["risks"]["risks"] if r["status"] in ("open", "mitigating")], key=lambda r: -r["emv"])[:5]
    rr = "".join(f"<tr><td>{E(r['title'])}</td><td>{r['probability'] * 100:.0f}%</td><td>${r['impact_usd']:,.0f}</td><td>{E(r.get('mitigation') or '')}</td></tr>" for r in open_risks) or "<tr><td colspan=4>No open risks</td></tr>"
    total = len(items)
    pct = round(100 * len(by("done")) / total) if total else 0
    health = "On track"
    reading = ev.get("reading") or ""
    if ev.get("available") and ((ev.get("cpi") or 1) < 0.9 or (ev.get("spi") or 1) < 0.9):
        health = "At risk"
    elif ev.get("available") and ((ev.get("cpi") or 1) < 0.97 or (ev.get("spi") or 1) < 0.97):
        health = "Watch"
    fin = (o["schedule"] or {}).get("finish")
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>Status report</title><style>{CSS}</style></head><body>{BANNER if _sample() else ''}"
            f"<h1>Weekly status: {E(_t(project, 100) or 'Project')}</h1><p>{E(_t(client, 100))} &middot; as of {E(o['as_of'])}</p>"
            f"<h2>Overall: <b>{health}</b> &middot; {pct}% of items done ({len(by('done'))} of {total})</h2><p>{E(reading)}</p>"
            + (f"<p>Forecast finish from the dependency chain: <b>{E(str(fin))}</b>.</p>" if fin else "")
            + f"<h2>Done</h2><ul>{li(by('done')[-12:], lambda i: i['title'])}</ul><h2>In progress</h2><ul>{li(by('doing') + by('review'), lambda i: i['title'] + (' (' + i['owner'] + ')' if i.get('owner') else ''))}</ul>"
            f"<h2>Next up</h2><ul>{li(by('todo'), lambda i: i['title'])}</ul><h2>Top risks</h2><table><tr><th>Risk</th><th>Chance</th><th>Cost if it happens</th><th>What we are doing</th></tr>{rr}</table>"
            + (f"<h2>Budget</h2><p>Planned value ${ev['pv']:,.0f}, earned ${ev['ev']:,.0f}, spent ${ev['ac']:,.0f}. Forecast total ${ev['eac']:,.0f} against a budget of ${ev['bac']:,.0f}.</p>" if ev.get("available") else "")
            + "<h2>Decisions needed from you</h2><ul><li>(Add here before sending.)</li></ul></body></html>")


# ------------------------------------------------------------------ estimator
def estimate(tasks: list[dict]) -> dict:
    if not isinstance(tasks, list) or not tasks:
        raise PmToolError("Add at least one task.")
    rows, mean_t, var_t = [], 0.0, 0.0
    for i, t in enumerate(tasks[:100], 1):
        try:
            o, m, p = float(t["optimistic"]), float(t["likely"]), float(t["pessimistic"])
        except (KeyError, TypeError, ValueError):
            raise PmToolError(f"Task {i} needs optimistic, likely and pessimistic numbers.") from None
        if not (0 <= o <= m <= p):
            raise PmToolError(f"Task {i}: the numbers must go from best case to worst case (optimistic {o:g}, likely {m:g}, worst {p:g}).")
        mu, sd = (o + 4 * m + p) / 6, (p - o) / 6
        mean_t += mu
        var_t += sd * sd
        rows.append({"name": _t(t.get("name"), 80) or f"Task {i}", "optimistic": o, "likely": m, "pessimistic": p, "expected": round(mu, 2), "sd": round(sd, 2)})
    sd_t = math.sqrt(var_t)
    out = {"tasks": rows, "expected_total": round(mean_t, 1), "sd_total": round(sd_t, 2), "range_80": [round(max(0, mean_t - 1.28 * sd_t), 1), round(mean_t + 1.28 * sd_t, 1)], "range_95": [round(max(0, mean_t - 1.96 * sd_t), 1), round(mean_t + 1.96 * sd_t, 1)],
           "arithmetic": ["Expected per task = (best + 4 x likely + worst) / 6", "Spread per task = (worst - best) / 6", "Total spread = square root of the sum of squared spreads (assumes tasks vary independently)"],
           "quote_tip": f"Quote near the 80% figure ({round(mean_t + 1.28 * sd_t, 1)}), not the expected value: half of all projects come in over their expected value.",
           "caution": "Estimates are only as good as the three numbers. If tasks share a risk (the same unclear requirement), the real spread is wider than shown."}
    return out


# ------------------------------------------------------------------ user stories
CRITERIA = [("Happy path", "Given {ctx}, when {role} {action}, then {result}"), ("Empty or invalid input", "Given {role} gives missing or invalid information, when they try to {action}, then they see a clear message saying what to fix and nothing is saved"),
            ("Permission", "Given a person who is not allowed to {action}, when they try, then it is blocked and the attempt is not recorded as success"), ("Undo or recovery", "Given {role} made a mistake while trying to {action}, when they notice, then they can correct it without contacting support")]


def stories(items: list[dict]) -> dict:
    if not items:
        raise PmToolError("Add at least one feature.")
    out = []
    for i, it in enumerate(items[:30], 1):
        role, want, why = _t(it.get("role"), 60), _t(it.get("want"), 160), _t(it.get("benefit"), 160)
        if not role or not want:
            raise PmToolError(f"Feature {i} needs who it is for and what they want to do.")
        text = f"As {'an' if role[:1].lower() in 'aeiou' else 'a'} {role}, I want to {want.lstrip().removeprefix('to ')}, so that {why or '(why does this matter?)'}."
        action = want.removeprefix("to ")
        crit = [{"name": n, "text": t.format(ctx=_t(it.get("context"), 80) or "they are signed in", role=role, action=action, result=_t(it.get("result"), 100) or "it works as described")} for n, t in CRITERIA]
        flags = []
        if not why:
            flags.append("No benefit given. A story without a reason is hard to prioritize.")
        if re.search(r"\b(and|also|as well as)\b", want):
            flags.append("This may be two stories. Try splitting at 'and'.")
        if len(want.split()) > 25:
            flags.append("Long: a story should fit in one sentence.")
        if re.search(r"\b(fast|easy|better|nice|user-friendly|quick)\b", want + " " + why, re.I):
            flags.append("Vague word (fast, easy, better). Replace it with a number or a test, like 'in under 2 seconds'.")
        out.append({"story": text, "criteria": crit, "flags": flags})
    md = "\n\n".join(f"### {s['story']}\n" + "\n".join(f"- **{c['name']}:** {c['text']}" for c in s["criteria"]) for s in out)
    return {"stories": out, "markdown": md, "note": "These are drafts from templates. Edit the criteria so each one is something a tester could pass or fail."}


# ------------------------------------------------------------------ roadmap
LANES = ("now", "next", "later")


def roadmap_list() -> list[dict]:
    return _kv("roadmap", {"items": []})["items"]


def roadmap_add(title: str, lane: str, why: str = "", owner: str = "") -> dict:
    if lane not in LANES:
        raise PmToolError("lane must be now, next or later.")
    ti = _t(title, 100)
    if not ti:
        raise PmToolError("Give the item a title.")
    d = _kv("roadmap", {"items": []})
    d["items"].append({"id": uuid.uuid4().hex[:8], "title": ti, "lane": lane, "why": _t(why, 200), "owner": _t(owner, 60)})
    _kv_set("roadmap", d)
    return d["items"][-1]


def roadmap_move(rid: str, lane: str) -> dict:
    if lane not in LANES:
        raise PmToolError("lane must be now, next or later.")
    d = _kv("roadmap", {"items": []})
    it = next((x for x in d["items"] if x["id"] == rid), None)
    if not it:
        raise PmToolError("No roadmap item with that id.", 404)
    it["lane"] = lane
    _kv_set("roadmap", d)
    return it


def roadmap_delete(rid: str) -> dict:
    d = _kv("roadmap", {"items": []})
    d["items"] = [x for x in d["items"] if x["id"] != rid]
    _kv_set("roadmap", d)
    return {"deleted": rid}


def roadmap_html(title: str = "Product roadmap") -> str:
    items = roadmap_list()
    cols = "".join("<div style='flex:1;min-width:200px'><h2>" + n.title() + "</h2>" + "".join(f"<div style='border:1px solid #ccc;border-radius:6px;padding:8px;margin:6px 0'><b>{E(i['title'])}</b>" + (f"<br><small>{E(i['why'])}</small>" if i["why"] else "") + (f"<br><small>Owner: {E(i['owner'])}</small>" if i["owner"] else "") + "</div>" for i in items if i["lane"] == n) + "</div>" for n in LANES)
    return f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{E(title)}</title><style>{CSS}</style></head><body>{BANNER if _sample() else ''}<h1>{E(_t(title, 100))}</h1><div style='display:flex;gap:12px;flex-wrap:wrap'>{cols}</div><p style='font-size:12px;color:#555'>Now = being built. Next = decided, not started. Later = an idea we may do. Order within a column is not a promise of dates.</p></body></html>"


# ------------------------------------------------------------------ decision and retro log
def log_add(kind: str, f: dict) -> dict:
    if kind not in ("decision", "retro"):
        raise PmToolError("kind must be decision or retro.")
    d = _kv("log", {"items": []})
    if kind == "decision":
        dec = _t(f.get("decision"), 300)
        if not dec:
            raise PmToolError("Write down what was decided.")
        it = {"kind": kind, "decision": dec, "context": _t(f.get("context"), 500), "options": _t(f.get("options"), 400), "owner": _t(f.get("owner"), 60), "revisit": _t(f.get("revisit"), 20)}
    else:
        if not (_t(f.get("went_well"), 600) or _t(f.get("improve"), 600)):
            raise PmToolError("Write at least one thing that went well or should change.")
        it = {"kind": kind, "went_well": _t(f.get("went_well"), 600), "improve": _t(f.get("improve"), 600), "actions": _t(f.get("actions"), 600)}
    it.update(id=uuid.uuid4().hex[:8], at=time.strftime("%Y-%m-%d"))
    d["items"] = (d["items"] + [it])[-500:]
    _kv_set("log", d)
    return it


def log_list() -> list[dict]:
    return list(reversed(_kv("log", {"items": []})["items"]))


def log_delete(lid: str) -> dict:
    d = _kv("log", {"items": []})
    d["items"] = [x for x in d["items"] if x["id"] != lid]
    _kv_set("log", d)
    return {"deleted": lid}


def log_markdown() -> str:
    out = ["# Decision and retro log\n"]
    for i in reversed(log_list()):
        if i["kind"] == "decision":
            out.append(f"## {i['at']} Decision: {i['decision']}\n- Why: {i['context']}\n- Options considered: {i['options']}\n- Owner: {i['owner']}\n- Revisit: {i['revisit']}\n")
        else:
            out.append(f"## {i['at']} Retro\n- Went well: {i['went_well']}\n- Change: {i['improve']}\n- Actions: {i['actions']}\n")
    return "\n".join(out)
