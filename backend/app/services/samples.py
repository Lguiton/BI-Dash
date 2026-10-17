"""Sample-work page for prospects: a separate, self-contained page built from clearly labelled practice work with made-up data.

Rules built into the code, not left to memory: every item carries a 'Sample' label, items cannot hold emails or phone numbers
(no client data), there is no testimonial or review item type, and the page makes no outside requests. Nothing is sent or published
from here: you download one HTML file and decide where it goes."""
from __future__ import annotations

import html
import json
import re
import secrets

from app.services import state, workspaces

KINDS = {"before_after": "Before and after", "quote": "Sample quote", "checklist": "Job checklist", "dashboard": "Sample dashboard"}
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?<!\d)(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
_REVIEWISH = re.compile(r"testimonial|5[- ]?star|five[- ]star|\bclient (?:said|says)\b|\bcustomer (?:said|says)\b|\brated (?:us|me)\b|\bhighly recommend", re.I)
LABEL = "Sample · practice work · made-up data"


class SampleError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _key() -> str:
    return f"samples:{workspaces.active()}"


def _blank() -> dict:
    return {"profile": {"name": "", "headline": "IT repair, networking, security and business reporting", "about": "", "area": "Henderson and Las Vegas, Nevada", "contact": "", "services": []}, "items": []}


def _load() -> dict:
    raw = state.kv_get(_key())
    try:
        d = json.loads(raw) if raw else {}
    except ValueError:
        d = {}
    b = _blank()
    b["profile"].update(d.get("profile") or {})
    b["items"] = d.get("items") or []
    return b


def _save(d: dict) -> None:
    state.kv_set(_key(), json.dumps(d))


def _t(v, name: str, limit: int, required: bool = False) -> str:
    s = str(v or "").strip()
    if required and not s:
        raise SampleError(f"Add {name}.")
    if len(s) > limit:
        raise SampleError(f"Keep {name} under {limit} characters.")
    return s


def _clean_text(s: str, what: str) -> str:
    if _EMAIL.search(s) or _PHONE.search(s):
        raise SampleError(f"{what} has an email address or phone number. Sample work must not hold real contact details. Remove it.")
    if _REVIEWISH.search(s):
        raise SampleError(f"{what} reads like a review or testimonial. This page shows sample work only: no reviews, no quotes from clients.")
    return s


def get() -> dict:
    d = _load()
    return {**d, "kinds": KINDS, "label": LABEL, "rules": rules(), "starters": [{"n": i, "title": s["title"], "kind": s["kind"]} for i, s in enumerate(STARTERS)]}


def rules() -> list[str]:
    return ["Every item is labelled as a sample made from practice work and made-up data.", "No client names, emails, phone numbers or real data.", "No reviews or testimonials. Add real ones only after real clients give them in writing, and then outside this tool.",
            "Nothing is published or sent from here. You download one file and choose where it goes.", "Do not claim certifications, results or years you cannot prove."]


def set_profile(b: dict) -> dict:
    d = _load()
    p = d["profile"]
    p["name"] = _clean_text(_t(b.get("name"), "the business name", 80), "The name") if b.get("name") else p.get("name", "")
    p["headline"] = _clean_text(_t(b.get("headline", p["headline"]), "the headline", 140), "The headline")
    p["about"] = _clean_text(_t(b.get("about", p["about"]), "the about text", 1200), "The about text")
    p["area"] = _t(b.get("area", p["area"]), "the service area", 120)
    c = _t(b.get("contact", p["contact"]), "the contact line", 160)
    p["contact"] = c                                    # contact is YOURS and is the one place an email or phone is allowed
    sv = b.get("services", p["services"])
    if not isinstance(sv, list) or len(sv) > 10:
        raise SampleError("List up to 10 services.")
    p["services"] = [{"name": _clean_text(_t(x.get("name"), "a service name", 60, True), "A service name"), "blurb": _clean_text(_t(x.get("blurb"), "a service description", 240), "A service description")} for x in sv if isinstance(x, dict)]
    _save(d)
    return get()


def _item(b: dict, cur: dict | None = None) -> dict:
    kind = str(b.get("kind", "")).strip()
    if kind not in KINDS:
        raise SampleError("Pick a type: " + ", ".join(KINDS.values()) + ".")
    it = {"id": (cur or {}).get("id") or secrets.token_hex(4), "kind": kind, "title": _clean_text(_t(b.get("title"), "a title", 100, True), "The title"), "summary": _clean_text(_t(b.get("summary"), "the summary", 400), "The summary")}
    if kind == "before_after":
        for k, lim in (("before", 500), ("after", 500), ("what_i_did", 700)):
            it[k] = _clean_text(_t(b.get(k), k.replace("_", " "), lim, True), k.replace("_", " ").capitalize())
    elif kind == "quote":
        rows = b.get("lines")
        if not isinstance(rows, list) or not rows or len(rows) > 20:
            raise SampleError("Add 1 to 20 quote lines.")
        out, tot = [], 0.0
        for x in rows:
            try:
                q, r = float(x.get("qty")), float(x.get("rate"))
            except (TypeError, ValueError, AttributeError):
                raise SampleError("Each quote line needs a number for quantity and for rate.") from None
            if q <= 0 or r < 0 or q > 10000 or r > 1_000_000:
                raise SampleError("Quantity must be above zero and rates must not be negative.")
            out.append({"desc": _clean_text(_t(x.get("desc"), "a line description", 120, True), "A line"), "qty": q, "rate": r, "amount": round(q * r, 2)})
            tot += q * r
        it["lines"], it["total"] = out, round(tot, 2)
        it["terms"] = _clean_text(_t(b.get("terms"), "the terms", 400), "The terms")
    elif kind == "checklist":
        st = b.get("steps")
        if not isinstance(st, list) or not st or len(st) > 40:
            raise SampleError("Add 1 to 40 checklist steps.")
        it["steps"] = [_clean_text(_t(x, "a step", 200, True), "A step") for x in st]
    else:
        k = b.get("kpis")
        if not isinstance(k, list) or not k or len(k) > 8:
            raise SampleError("Add 1 to 8 numbers for the sample dashboard.")
        it["kpis"] = [{"label": _clean_text(_t(x.get("label"), "a label", 50, True), "A label"), "value": _clean_text(_t(x.get("value"), "a value", 30, True), "A value")} for x in k]
        it["takeaway"] = _clean_text(_t(b.get("takeaway"), "the takeaway", 400), "The takeaway")
    return it


def add_item(b: dict) -> dict:
    d = _load()
    if len(d["items"]) >= 30:
        raise SampleError("Keep the page to 30 samples or fewer.")
    d["items"].append(_item(b))
    _save(d)
    return get()


def update_item(iid: str, b: dict) -> dict:
    d = _load()
    i = next((k for k, x in enumerate(d["items"]) if x["id"] == iid), None)
    if i is None:
        raise SampleError("That sample was not found.", 404)
    d["items"][i] = _item(b, d["items"][i])
    _save(d)
    return get()


def delete_item(iid: str) -> dict:
    d = _load()
    n = len(d["items"])
    d["items"] = [x for x in d["items"] if x["id"] != iid]
    if len(d["items"]) == n:
        raise SampleError("That sample was not found.", 404)
    _save(d)
    return get()


def move_item(iid: str, direction: int) -> dict:
    d = _load()
    i = next((k for k, x in enumerate(d["items"]) if x["id"] == iid), None)
    if i is None:
        raise SampleError("That sample was not found.", 404)
    j = i + (1 if direction > 0 else -1)
    if 0 <= j < len(d["items"]):
        d["items"][i], d["items"][j] = d["items"][j], d["items"][i]
        _save(d)
    return get()


STARTERS = [
    {"kind": "before_after", "title": "Slow laptop that took minutes to start", "summary": "A practice repair on my own test machine.", "before": "Took about four minutes to reach the desktop. The fan ran loud and the drive was almost full.",
     "after": "Reaches the desktop in under a minute. Drive has 40% free space, startup list trimmed, updates current.", "what_i_did": "Checked drive health first, backed up, removed unneeded startup programs, cleared old files, ran system updates, and confirmed temperatures were normal."},
    {"kind": "quote", "title": "Home network refresh (sample quote)", "summary": "Shows how I price and explain work. Numbers are made up.", "lines": [{"desc": "Site check and Wi-Fi survey", "qty": 1, "rate": 85}, {"desc": "Router and access point setup", "qty": 2, "rate": 85}, {"desc": "Cable run and labelling", "qty": 1.5, "rate": 85}],
     "terms": "Written quote before any work. Changes in scope are priced and agreed first. Parts at cost."},
    {"kind": "checklist", "title": "Small-office security check", "summary": "The checklist I follow, shown with practice data only.", "steps": ["Confirm who is allowed to access what", "Check every device has current updates", "Confirm backups ran and test one restore", "Turn on multi-factor sign-in for email and admin accounts", "Review firewall rules and remove unused ones", "Change default passwords and store them in a password manager", "Write down what was checked and what still needs attention"]},
    {"kind": "dashboard", "title": "Sample monthly sales dashboard", "summary": "Made-up numbers to show how a report reads.", "kpis": [{"label": "Revenue", "value": "$18,400"}, {"label": "Orders", "value": "212"}, {"label": "Average order", "value": "$86.79"}, {"label": "Repeat customers", "value": "38%"}], "takeaway": "Revenue rose in the last two weeks, led by repeat customers. This is sample data, not a real business."},
]


def add_starter(n: int) -> dict:
    if not 0 <= n < len(STARTERS):
        raise SampleError("No such starter.", 404)
    return add_item(STARTERS[n])


# ------------------------------------------------------------------ the downloadable page
def _e(s) -> str:
    return html.escape(str(s), quote=True)


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _card(it: dict) -> str:
    h = [f'<article class="card"><div class="tag">{_e(LABEL)}</div><h3>{_e(it["title"])}</h3>']
    if it.get("summary"):
        h.append(f'<p class="sum">{_e(it["summary"])}</p>')
    k = it["kind"]
    if k == "before_after":
        h.append(f'<div class="ba"><div><h4>Before</h4><p>{_e(it["before"])}</p></div><div><h4>After</h4><p>{_e(it["after"])}</p></div></div><h4>What I did</h4><p>{_e(it["what_i_did"])}</p>')
    elif k == "quote":
        rows = "".join(f'<tr><td>{_e(x["desc"])}</td><td class="n">{x["qty"]:g}</td><td class="n">{_money(x["rate"])}</td><td class="n">{_money(x["amount"])}</td></tr>' for x in it["lines"])
        h.append(f'<table><thead><tr><th>Item</th><th class="n">Qty</th><th class="n">Rate</th><th class="n">Amount</th></tr></thead><tbody>{rows}</tbody><tfoot><tr><td colspan="3">Total</td><td class="n">{_money(it["total"])}</td></tr></tfoot></table>')
        if it.get("terms"):
            h.append(f'<p class="sum">{_e(it["terms"])}</p>')
    elif k == "checklist":
        h.append("<ul class=\"chk\">" + "".join(f"<li>{_e(s)}</li>" for s in it["steps"]) + "</ul>")
    else:
        h.append('<div class="kpis">' + "".join(f'<div><b>{_e(x["value"])}</b><span>{_e(x["label"])}</span></div>' for x in it["kpis"]) + "</div>")
        if it.get("takeaway"):
            h.append(f'<p>{_e(it["takeaway"])}</p>')
    h.append("</article>")
    return "".join(h)


CSS = """:root{--bg:#fff;--fg:#14202b;--mut:#5b6b78;--line:#d9e0e6;--card:#f6f8fa;--acc:#1f5f8b}
@media(prefers-color-scheme:dark){:root{--bg:#10171d;--fg:#e8eef3;--mut:#9fb0bd;--line:#2b3946;--card:#17212a;--acc:#6db3e0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Segoe UI,Roboto,sans-serif}
main{max-width:860px;margin:0 auto;padding:32px 16px 56px}h1{font-size:2rem;margin:0 0 4px}h2{margin:40px 0 12px;font-size:1.25rem}h3{margin:6px 0}h4{margin:12px 0 2px;font-size:.85rem;text-transform:uppercase;letter-spacing:.04em;color:var(--mut)}
.lead{font-size:1.1rem;color:var(--mut);margin:0 0 12px}.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 0 16px}
.tag{display:inline-block;font-size:.72rem;border:1px solid var(--acc);color:var(--acc);border-radius:999px;padding:1px 10px}.sum{color:var(--mut);margin:4px 0 8px}
.ba{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:600px){.ba{grid-template-columns:1fr}}
table{width:100%;border-collapse:collapse;margin:8px 0}th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left}.n{text-align:right}tfoot td{font-weight:700;border-bottom:0}
.chk{list-style:none;padding:0;margin:8px 0}.chk li{padding:4px 0 4px 26px;position:relative}.chk li::before{content:"\\2713";position:absolute;left:4px;color:var(--acc)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:10px;margin:8px 0}.kpis div{border:1px solid var(--line);border-radius:10px;padding:10px;background:var(--bg)}.kpis b{display:block;font-size:1.3rem}.kpis span{color:var(--mut);font-size:.85rem}
.sv{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}footer{margin-top:40px;border-top:1px solid var(--line);padding-top:16px;color:var(--mut);font-size:.9rem}"""


def render_html() -> str:
    d = _load()
    p = d["profile"]
    name = p["name"] or "Sample work"
    parts = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(name)}: sample work</title><style>{CSS}</style></head><body><main>',
             f"<header><h1>{_e(name)}</h1><p class=\"lead\">{_e(p['headline'])}</p>"]
    if p["area"]:
        parts.append(f"<p>Serving {_e(p['area'])}.</p>")
    if p["about"]:
        parts.append(f"<p>{_e(p['about'])}</p>")
    parts.append("</header>")
    if p["services"]:
        parts.append('<h2>What I do</h2><div class="sv">' + "".join(f'<div class="card"><h3>{_e(s["name"])}</h3><p class="sum">{_e(s["blurb"])}</p></div>' for s in p["services"]) + "</div>")
    if d["items"]:
        parts.append("<h2>Sample work</h2><p class=\"sum\">Everything below is practice work with made-up data, shown to explain how I work. It is not the work or information of any client.</p>")
        parts += [_card(it) for it in d["items"]]
    parts.append('<footer><p>Sample and practice work with made-up data. No client information is shown on this page.</p>')
    if p["contact"]:
        parts.append(f"<p>Contact: {_e(p['contact'])}</p>")
    parts.append("</footer></main></body></html>")
    return "".join(parts)
