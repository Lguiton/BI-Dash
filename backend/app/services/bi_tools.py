"""BI tools: a dashboard designer that exports a client-ready page, scheduled client reports that catch up when the computer wakes, alert rules, a data-story page
and a KPI dictionary export.

Everything reads the same numbers the business dashboards show. Scheduled reports and alerts are checked by the app's own scheduler and also on demand, so a computer that
was asleep catches up on the next start. Nothing is emailed or sent anywhere. In Practice every page is stamped SAMPLE."""
from __future__ import annotations

import csv
import html
import io
import json
import re
from datetime import date, timedelta

from app.services import biz_packs, biz_report, state, workspaces


class BiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


E = html.escape
DAYS = (7, 14, 30, 60, 90, 180, 365)
OPS = ("above", "below", "worse_by_pct")


def _sample() -> bool:
    return workspaces.active() != "real"


def _banner() -> str:
    return "<p style='background:#fff3cd;border:1px solid #e0b000;padding:.5rem;font-weight:600'>SAMPLE: from the Practice workspace, not a client deliverable.</p>" if _sample() else ""


def _dash(pid: str, days: int) -> dict:
    if days not in DAYS:
        raise BiError("days must be one of: " + ", ".join(map(str, DAYS)) + ".")
    try:
        return biz_packs.dashboard(pid, days)
    except biz_packs.PackError as e:
        raise BiError(str(e), 404) from None


def _fmt(unit: str, v) -> str:
    return biz_report._fmt(unit, v)


CSS = ("body{font:15px/1.5 system-ui,Segoe UI,Arial,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1b1f1d}h1{margin:.2rem 0}h2{margin-top:1.6rem;border-bottom:2px solid #0f6b4a;padding-bottom:.2rem}"
       ".cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:.8rem}.card{border:1px solid #ddd;border-radius:8px;padding:.7rem}.v{font-size:1.6rem;font-weight:700}"
       ".good{color:#0f6b4a}.bad{color:#b3261e}.sub{color:#555;font-size:.85rem}table{border-collapse:collapse;width:100%}td,th{padding:.3rem .5rem;border-bottom:1px solid #ddd;text-align:left}.n{text-align:right}@media print{body{margin:0}}")


# ------------------------------------------------------------------ 1. dashboard designer


def design(pid: str, days: int = 30, kpis: list[str] | None = None, show_trend: bool = True, breakdowns: int = 2, title: str = "", client: str = "") -> str:
    d = _dash(pid, days)
    ks = [k for k in d["kpis"] if not kpis or k["label"] in kpis]
    if not ks:
        raise BiError("None of the chosen KPIs exist on that dashboard.")
    cards = "".join(f"<div class=card><div class=sub>{E(k['label'])}</div><div class=v>{E(_fmt(k['unit'], k['value']))}</div><div class='sub {'good' if k['good'] else 'bad' if k['good'] is False else ''}'>{E(biz_report._chg(k))} vs before</div></div>" for k in ks)
    bd = "".join(f"<h3>{E(b['dim'].replace('_', ' ').title())}</h3><table>" + "".join(f"<tr><td>{E(str(r['name']))}</td><td class=n>{E(_fmt('num', r['value']))}</td></tr>" for r in b["rows"][:8]) + "</table>" for b in d["breakdowns"][:max(0, min(breakdowns, 5))] if b["rows"])
    tr = f"<h2>{E(d['trend_label'])} over time</h2>{biz_report._spark(d['trend'])}" if show_trend else ""
    ttl = (title or d["title"])[:100]
    who = f"For {E(client[:80])} · " if client else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(ttl)}</title><style>{CSS}</style></head><body>{_banner()}
<h1>{E(ttl)}</h1><p class=sub>{who}as of {E(d['as_of'])}, last {days} days, {d['records']:,} records</p><div class=cards>{cards}</div>{tr}{('<h2>Where it comes from</h2>' + bd) if bd else ''}
<p class=sub>Figures come from the data loaded in this dashboard. A change shows two numbers moved together, not why.</p></body></html>"""


# ------------------------------------------------------------------ 2. scheduled reports


def _key(name: str) -> str:
    return f"bitools:{name}:{workspaces.active()}"


def _load(name: str) -> dict:
    raw = state.kv_get(_key(name))
    d = json.loads(raw) if raw else {}
    d.setdefault("items", [])
    d.setdefault("next", 0)
    return d


def _save(name: str, d: dict) -> None:
    state.kv_set(_key(name), json.dumps(d))


def sched_add(pid: str, days: int = 30, every_days: int = 30, client: str = "", prepared_by: str = "") -> dict:
    _dash(pid, days)
    if not 1 <= int(every_days) <= 365:
        raise BiError("every_days must be between 1 and 365.")
    d = _load("sched")
    d["next"] += 1
    it = {"id": d["next"], "pack": pid, "days": days, "every_days": int(every_days), "client": client[:80], "prepared_by": prepared_by[:80], "enabled": True, "last_run": None, "outputs": []}
    d["items"].append(it)
    _save("sched", d)
    return {k: it[k] for k in ("id", "pack", "days", "every_days", "client")}


def sched_list() -> list[dict]:
    return [{**{k: s[k] for k in ("id", "pack", "days", "every_days", "client", "enabled", "last_run")}, "outputs": [{"date": o["date"]} for o in s["outputs"]], "next_due": (date.fromisoformat(s["last_run"]) + timedelta(days=s["every_days"])).isoformat() if s["last_run"] else "now"} for s in _load("sched")["items"]]


def sched_remove(sid: int) -> dict:
    d = _load("sched")
    d["items"] = [s for s in d["items"] if s["id"] != sid]
    _save("sched", d)
    return {"deleted": sid}


def sched_output(sid: int, day: str) -> str:
    s = next((x for x in _load("sched")["items"] if x["id"] == sid), None)
    o = next((o for o in (s or {}).get("outputs", []) if o["date"] == day), None)
    if not o:
        raise BiError("No report for that date.", 404)
    return o["html"]


def run_due(today: date | None = None, force_id: int | None = None) -> dict:
    """Build every report that is due (or the one you name). A report whose installation has no data yet is skipped with a reason, not an error."""
    t = today or date.today()
    d = _load("sched")
    ran, skipped = [], []
    for s in d["items"]:
        if force_id is not None and s["id"] != force_id:
            continue
        if force_id is None:
            if not s["enabled"]:
                continue
            if s["last_run"] and t < date.fromisoformat(s["last_run"]) + timedelta(days=s["every_days"]):
                continue
        try:
            html_ = biz_report.to_html(biz_report.build(s["pack"], s["days"], s["client"], s["prepared_by"]))
        except biz_packs.PackError as e:
            skipped.append({"id": s["id"], "why": str(e)})
            continue
        s["outputs"] = [o for o in s["outputs"] if o["date"] != t.isoformat()] + [{"date": t.isoformat(), "html": html_}]
        s["outputs"] = s["outputs"][-12:]
        s["last_run"] = t.isoformat()
        ran.append(s["id"])
    _save("sched", d)
    return {"ran": ran, "skipped": skipped}


# ------------------------------------------------------------------ 3. alert rules


def alert_add(pid: str, kpi: str, op: str, value: float, days: int = 30) -> dict:
    if op not in OPS:
        raise BiError("op must be one of: " + ", ".join(OPS) + ".")
    d = _dash(pid, days)
    if kpi not in [k["label"] for k in d["kpis"]]:
        raise BiError("That KPI is not on that dashboard. Choose one of: " + ", ".join(k["label"] for k in d["kpis"]) + ".")
    try:
        v = float(value)
    except (TypeError, ValueError):
        raise BiError("value must be a number.") from None
    a = _load("alerts")
    a["next"] += 1
    it = {"id": a["next"], "pack": pid, "kpi": kpi, "op": op, "value": v, "days": days}
    a["items"].append(it)
    _save("alerts", a)
    return it


def alert_list() -> list[dict]:
    return _load("alerts")["items"]


def alert_remove(aid: int) -> dict:
    a = _load("alerts")
    a["items"] = [x for x in a["items"] if x["id"] != aid]
    _save("alerts", a)
    return {"deleted": aid}


def alert_check() -> dict:
    out, errs = [], []
    cache: dict[tuple, dict] = {}
    for r in _load("alerts")["items"]:
        try:
            d = cache.setdefault((r["pack"], r["days"]), _dash(r["pack"], r["days"]))
        except BiError as e:
            errs.append({"id": r["id"], "why": e.message})
            continue
        k = next((x for x in d["kpis"] if x["label"] == r["kpi"]), None)
        if not k or k["value"] is None:
            errs.append({"id": r["id"], "why": "No value for that KPI right now."})
            continue
        v, ch = float(k["value"]), k["change_pct"]
        hit = (r["op"] == "above" and v > r["value"]) or (r["op"] == "below" and v < r["value"]) or (r["op"] == "worse_by_pct" and k["good"] is False and ch is not None and abs(ch) >= r["value"])
        if hit:
            out.append({"id": r["id"], "pack": r["pack"], "kpi": r["kpi"], "rule": f"{r['op'].replace('_', ' ')} {r['value']:g}", "value": v, "change_pct": ch, "as_of": d["as_of"],
                        "says": f"{r['kpi']} is {_fmt(k['unit'], v)} ({biz_report._chg(k)} vs before), which trips the rule '{r['op'].replace('_', ' ')} {r['value']:g}'."})
    return {"triggered": out, "problems": errs, "rules": len(_load("alerts")["items"]), "note": "Checked against the data loaded now. Rules are checked when you open this page and on each scheduler pass."}


# ------------------------------------------------------------------ 4. data story


def story(pid: str, days: int = 30, headline: str = "", recommendation: str = "", client: str = "") -> str:
    try:
        r = biz_report.build(pid, days, client, "")
    except biz_packs.PackError as e:
        raise BiError(str(e), 404) from None
    moved = [k for k in r["kpis"] if k["change_pct"] is not None]
    top = sorted(moved, key=lambda k: -abs(k["change_pct"]))[:3] or r["kpis"][:3]
    head = (headline or (f"{top[0]['label']} is {_fmt(top[0]['unit'], top[0]['value'])}" + (f", {biz_report._chg(top[0])} vs before" if top[0]["change_pct"] is not None else "")))[:160]
    findings = "".join(f"<div class=card><div class=sub>Finding {i}</div><div class=v>{E(_fmt(k['unit'], k['value']))}</div><div>{E(k['label'])}" + (f"<br><span class='{'good' if k['good'] else 'bad' if k['good'] is False else ''}'>{E(biz_report._chg(k))} vs before</span>" if k["change_pct"] is not None else "") + "</div></div>" for i, k in enumerate(top, 1))
    rec = (recommendation or (r["actions"][0] if r["actions"] else "Keep the data current and review next period."))[:400]
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(head)}</title><style>{CSS}h1{{font-size:2rem}}</style></head><body>{_banner()}
<p class=sub>{E(r['title'])} · {E(r['period'])}{(' · for ' + E(client[:80])) if client else ''}</p><h1>{E(head)}</h1><h2>Three things to know</h2><div class=cards>{findings}</div>
<h2>What it looks like over time</h2>{biz_report._spark(r['trend'])}<h2>What to do next</h2><p>{E(rec)}</p><p class=sub>{E(r['caveat'])}</p></body></html>"""


# ------------------------------------------------------------------ 5. KPI dictionary


def kpi_dictionary() -> list[dict]:
    rows = []
    for p in biz_packs.all_packs():
        for label, sql, unit, direction in p["kpis"]:
            rows.append({"dashboard": p["title"], "kpi": label, "unit": unit, "good_direction": direction, "in_words": biz_packs._plain(sql), "formula": " ".join(sql.split()), "owner": "", "target": ""})
    return rows


def kpi_dictionary_export(fmt: str = "csv", dashboards: list[str] | None = None) -> tuple[str, str]:
    rows = [r for r in kpi_dictionary() if not dashboards or r["dashboard"] in dashboards]
    if fmt == "csv":
        b = io.StringIO()
        w = csv.DictWriter(b, fieldnames=list(rows[0]) if rows else ["dashboard"])
        w.writeheader()
        w.writerows(rows)
        return b.getvalue(), "text/csv"
    if fmt == "html":
        body = "".join("<tr>" + "".join(f"<td>{E(str(r[c]))}</td>" for c in ("dashboard", "kpi", "in_words", "good_direction", "owner", "target")) + "</tr>" for r in rows)
        return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>KPI dictionary</title><style>{CSS}</style></head><body>{_banner()}<h1>KPI dictionary</h1><p class=sub>One agreed definition for each number. Fill in owner and target.</p>"
                f"<table><tr><th>Dashboard</th><th>KPI</th><th>How it is calculated</th><th>Better when</th><th>Owner</th><th>Target</th></tr>{body}</table></body></html>"), "text/html"
    raise BiError("fmt must be csv or html.")
