"""Single-source-of-truth audits: systems connectivity, metrics, documents and key-person risk.

From a manufacturing data-management whitepaper (five tactics: connect systems, use the right metrics, structure technical
documents, make compliance independent of one person, get an outside view). Each audit reads rows you type and points at
the weak spots. It cannot see your real systems, and an audit that finds nothing only means your list was clean.
"""
from __future__ import annotations

import re
import statistics
from collections import defaultdict
from datetime import date, datetime


class AuditError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


MAX_ROWS = 300


def _today() -> date:
    return date.today()


def _rows(text: str, cols: int, what: str, min_cols: int | None = None) -> list[list[str]]:
    out = []
    for ln in (text or "").splitlines():
        if not ln.strip() or ln.strip().startswith("#"):
            continue
        parts = [p.strip() for p in ln.split("|")]
        if len(parts) < (min_cols or cols):
            raise AuditError(f"'{ln.strip()[:60]}' needs {min_cols or cols} parts separated by |. Format: {what}")
        out.append((parts + [""] * cols)[:cols])
    if not out:
        raise AuditError(f"Add at least one row. Format: {what}")
    if len(out) > MAX_ROWS:
        raise AuditError(f"Keep it to {MAX_ROWS} rows.")
    return out


def _split(t: str) -> list[str]:
    return [x.strip() for x in t.split(",") if x.strip()]


# ------------------------------------------------------------------ 1 systems connectivity
SYS_FMT = "system | information it holds (add * to the one that is the master) | where it sends data: target:auto or target:manual"
_SHEET = re.compile(r"excel|sheet|spreadsheet|csv|access|\.xls|word|email|shared drive|paper", re.I)


def systems(text: str) -> dict:
    rows = _rows(text, 3, SYS_FMT, 2)
    names = [r[0] for r in rows]
    if len({n.lower() for n in names}) != len(names):
        raise AuditError("A system name appears twice.")
    holds: dict[str, set[str]] = {}
    masters: dict[str, list[str]] = defaultdict(list)
    flows, inbound = [], defaultdict(int)
    known = {n.lower(): n for n in names}
    for name, ents, feeds in rows:
        s = set()
        for e in _split(ents):
            clean = e.rstrip("*").strip().lower()
            s.add(clean)
            if e.endswith("*"):
                masters[clean].append(name)
        holds[name] = s
        for f in _split(feeds):
            tgt, _, mode = f.partition(":")
            mode = (mode or "").strip().lower()
            if mode not in ("auto", "manual"):
                raise AuditError(f"'{f}' in {name}: say target:auto or target:manual.")
            tgt = tgt.strip()
            if tgt.lower() not in known:
                raise AuditError(f"'{name}' sends to '{tgt}', which is not in your list of systems.")
            flows.append({"from": name, "to": known[tgt.lower()], "mode": mode})
            inbound[known[tgt.lower()]] += 1
    manual = [f for f in flows if f["mode"] == "manual"]
    islands = [n for n in names if not any(f["from"] == n for f in flows) and inbound[n] == 0]
    dup: dict[str, list[str]] = defaultdict(list)
    for n, s in holds.items():
        for e in s:
            dup[e].append(n)
    shared = {e: ns for e, ns in dup.items() if len(ns) > 1}
    no_master = sorted(e for e in shared if not masters.get(e))
    many_masters = sorted(e for e in masters if len(masters[e]) > 1)
    sheets = [n for n in names if _SHEET.search(n)]
    priorities = []
    for f in manual:
        common = sorted(holds[f["from"]] & holds[f["to"]])
        priorities.append({"flow": f"{f['from']} -> {f['to']}", "shared_information": common, "score": 2 + len(common) + (1 if _SHEET.search(f["from"] + f["to"]) else 0)})
    priorities.sort(key=lambda p: -p["score"])
    return {"systems": len(names), "flows": len(flows), "manual_transfers": manual, "isolated_systems": islands,
            "information_in_several_systems": [{"information": e, "systems": ns, "master": masters.get(e, [None])[0]} for e, ns in sorted(shared.items())],
            "no_designated_master": no_master, "conflicting_masters": many_masters, "spreadsheet_or_informal_systems": sheets, "integration_priorities": priorities[:5],
            "verdict": f"{len(manual)} manual transfer(s), {len(islands)} isolated system(s), {len(no_master)} item(s) held in several systems with no master.",
            "lesson": "Connecting systems is not the same as one source of truth. For each piece of information, name the one system that owns it; the others copy from it."}


# ------------------------------------------------------------------ 2 metric audit
MET_FMT = "metric | report it appears in | owner | decision it supports | reviewed (weekly, monthly, quarterly or never)"
REVIEW = {"daily", "weekly", "monthly", "quarterly", "yearly", "never", ""}


def metrics(text: str) -> dict:
    rows = _rows(text, 5, MET_FMT, 2)
    issues, by_metric, by_decision = [], defaultdict(list), defaultdict(list)
    for m, rep, owner, dec, rev in rows:
        rev = rev.lower()
        if rev not in REVIEW:
            raise AuditError(f"'{rev}' for {m}: reviewed must be daily, weekly, monthly, quarterly, yearly or never.")
        key = re.sub(r"[^a-z0-9]+", " ", m.lower()).strip()
        by_metric[key].append((m, rep))
        if dec:
            by_decision[dec.lower()].append(m)
        if not dec:
            issues.append({"metric": m, "problem": "Supports no decision. Drop it or name the decision.", "severity": "high"})
        if not owner:
            issues.append({"metric": m, "problem": "No owner. Nobody can explain or defend the number.", "severity": "high"})
        if rev in ("never", ""):
            issues.append({"metric": m, "problem": "Never reviewed. A number nobody looks at is noise.", "severity": "medium"})
        if not rep:
            issues.append({"metric": m, "problem": "Not in any report, so nobody can see it.", "severity": "medium"})
    dups = [{"metric": v[0][0], "reports": sorted({r for _, r in v if r})} for v in by_metric.values() if len({r for _, r in v}) > 1]
    for d in dups:
        issues.append({"metric": d["metric"], "problem": f"Appears in {len(d['reports'])} reports ({', '.join(d['reports'])}). Check they use one definition.", "severity": "medium"})
    crowded = {d: ms for d, ms in by_decision.items() if len(ms) > 5}
    for d, ms in crowded.items():
        issues.append({"metric": d, "problem": f"{len(ms)} metrics for one decision. Pick the few that move it.", "severity": "low"})
    keep = sorted({m for m, rep, owner, dec, rev in rows if dec and owner and rev.lower() not in ("never", "")})
    unreviewed_reports = sorted({rep for m, rep, o, d, rev in rows if rep} - {rep for m, rep, o, d, rev in rows if rep and rev.lower() not in ("never", "")})
    rank = {"high": 0, "medium": 1, "low": 2}
    issues.sort(key=lambda i: rank[i["severity"]])
    return {"metrics": len(rows), "keep": keep, "keep_count": len(keep), "issues": issues, "duplicate_metrics": dups, "reports_nobody_reviews": unreviewed_reports,
            "verdict": f"Keep {len(keep)} of {len(rows)} metrics as they are; {len(rows) - len(keep)} need a decision, an owner or a review habit.",
            "lesson": "Start from the decisions, then choose the few metrics that support them, then remove reports that serve neither."}


# ------------------------------------------------------------------ 3 documents
DOC_FMT = "title | owner | location | version | last review (YYYY-MM-DD)"
_NOISE = re.compile(r"\b(final|copy|new|old|latest|draft|backup|v\d+|rev\d*|version ?\d+|\(\d+\)|\d{4}-\d{2}-\d{2}|\d{8})\b", re.I)


def _norm(t: str) -> str:
    t = re.sub(r"\(\d+\)", " ", t.lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", _NOISE.sub(" ", t))).strip()


def documents(text: str, stale_days: int = 365) -> dict:
    rows = _rows(text, 5, DOC_FMT, 2)
    issues, groups = [], defaultdict(list)
    for t, owner, loc, ver, rev in rows:
        groups[_norm(t)].append((t, loc, ver))
        if not owner:
            issues.append({"document": t, "problem": "No owner."})
        if not loc:
            issues.append({"document": t, "problem": "No defined location."})
        if not ver:
            issues.append({"document": t, "problem": "No version recorded."})
        if _NOISE.search(t) or re.search(r"\(\d+\)", t):
            issues.append({"document": t, "problem": "Title carries version words (final, copy, v2, a date). Put the version in a field, not the name."})
        if rev:
            try:
                age = (_today() - datetime.strptime(rev, "%Y-%m-%d").date()).days
            except ValueError:
                raise AuditError(f"'{rev}' for {t}: use a date like 2026-03-31.") from None
            if age > stale_days:
                issues.append({"document": t, "problem": f"Last reviewed {age} days ago."})
        else:
            issues.append({"document": t, "problem": "Never reviewed."})
    versions = [{"document": v[0][0], "copies": [{"title": t, "location": l, "version": ver} for t, l, ver in v]} for k, v in groups.items() if len(v) > 1 and k]
    for v in versions:
        issues.append({"document": v["document"], "problem": f"{len(v['copies'])} copies of the same document. Which one is current?"})
    return {"documents": len(rows), "issues": issues, "duplicate_or_multi_version": versions, "locations": sorted({r[2] for r in rows if r[2]}),
            "verdict": f"{len(issues)} issue(s) across {len(rows)} documents; {len(versions)} document(s) exist in more than one copy.",
            "lesson": "Every critical document needs one location, one owner and one current version."}


def search_cost(people: int, searches_per_day: float, minutes_each: float, hourly_cost: float, working_days: int = 230) -> dict:
    for name, v, lo, hi in (("people", people, 1, 100_000), ("searches per day", searches_per_day, 0, 500), ("minutes each", minutes_each, 0, 600), ("hourly cost", hourly_cost, 0, 10_000), ("working days", working_days, 1, 366)):
        if not isinstance(v, (int, float)) or isinstance(v, bool) or not lo <= v <= hi:
            raise AuditError(f"{name.capitalize()} must be a number from {lo} to {hi}.")
    hours = people * searches_per_day * minutes_each / 60 * working_days
    return {"hours_per_year": round(hours, 1), "cost_per_year": round(hours * hourly_cost, 2), "full_time_equivalents": round(hours / (working_days * 8), 2),
            "note": "Your own estimate multiplied out. Time a real retrieval test in two departments before quoting it."}


# ------------------------------------------------------------------ 4 key-person
KEY_FMT = "responsibility | primary person | backup person | documented (yes or no) | next audit or deadline (YYYY-MM-DD, optional)"


def key_person(text: str) -> dict:
    rows = _rows(text, 5, KEY_FMT, 2)
    per = defaultdict(list)
    issues, soon = [], []
    for resp, prim, back, doc, due in rows:
        doc_l = doc.lower()
        if doc_l not in ("yes", "no", ""):
            raise AuditError(f"'{doc}' for {resp}: documented must be yes or no.")
        d = None
        if due:
            try:
                d = datetime.strptime(due, "%Y-%m-%d").date()
            except ValueError:
                raise AuditError(f"'{due}' for {resp}: use a date like 2026-12-01.") from None
        risk = []
        if not prim:
            risk.append("no primary person")
        if not back or back.lower() == prim.lower():
            risk.append("no separate backup")
        if doc_l != "yes":
            risk.append("not documented")
        per[prim or "(nobody)"].append({"responsibility": resp, "backup": back, "documented": doc_l == "yes", "risks": risk})
        if risk:
            issues.append({"responsibility": resp, "primary": prim or "(nobody)", "risks": risk})
        if d and risk:
            days = (d - _today()).days
            if days <= 90:
                soon.append({"responsibility": resp, "due": due, "days_left": days, "risks": risk})
    leave = []
    for p, items in sorted(per.items(), key=lambda kv: -len(kv[1])):
        exposed = [i for i in items if i["risks"]]
        leave.append({"person": p, "holds": len(items), "exposed_if_they_left": [i["responsibility"] for i in exposed], "exposed_count": len(exposed)})
    top = max(leave, key=lambda x: x["holds"]) if leave else None
    counts = [x["holds"] for x in leave]
    return {"responsibilities": len(rows), "at_risk": issues, "if_this_person_left_tomorrow": leave, "deadlines_within_90_days_at_risk": sorted(soon, key=lambda x: x["days_left"]),
            "most_concentrated": top["person"] if top and top["holds"] > max(2, statistics.median(counts) * 2) else None,
            "verdict": f"{len(issues)} of {len(rows)} responsibilities lack a backup or documentation.",
            "succession_questions": ["If this person left tomorrow, who could run the next audit?", "Where is the procedure written, and has anyone else followed it?", "What would the auditor ask for first, and who knows where it is?"],
            "lesson": "A system that works only because one person remembers is a risk, however well that person does the job."}


# ------------------------------------------------------------------ reference
SAMPLE = {
    "systems": "CRM | customers*, contacts | ERP:auto, Quotes spreadsheet:manual\nERP | customers, orders*, inventory, invoices | Accounting:manual\nAccounting | invoices, customers | \nQuotes spreadsheet | quotes*, customers | \nShop-floor tablet app | work orders | \nQuality shared drive | specs | ",
    "metrics": "On-time delivery | Weekly ops pack | Ops manager | Which orders to expedite | weekly\nScrap rate | Weekly ops pack | Quality lead | Which lines to inspect | monthly\nScrap rate | Quality report | | | never\nOrders booked | Sales dashboard | | | never\nMachine utilisation | | | Whether to buy a machine | quarterly",
    "documents": "Welding procedure WP-12 | Quality lead | Quality shared drive | 3 | 2026-02-10\nWelding procedure WP-12 final v2 | | Desktop | | \nCustomer spec - Acme | Sales | Email | 1 | 2023-01-15\nISO audit checklist | Quality lead | Quality shared drive | 4 | 2026-06-01",
    "key_person": "ISO certification audits | Priya | | no | 2026-12-01\nCalibration records | Priya | Tom | yes | \nSupplier approval | Priya | | no | \nCustomer complaints | Tom | Priya | yes | \nMachine maintenance plan | Sam | | no | 2026-11-10",
}
SLIPS = [
    "Data management whitepaper: it is titled '5 steps to create a single source of truth', but none of the five steps creates one. A single source of truth needs a named system of record for each piece of information, data ownership, quality rules and a way to retire the copies. Connecting systems (step 1) still leaves copies that can disagree. The audits here check for a designated master.",
    "Data management whitepaper: the fifth tactic is to hire an outside specialist, and the document ends with an offer from the author's own consultancy. It is a sales document. The first four tactics do not need a consultant, and 'benchmark against industry standards' never says which standard (for manufacturers, usually ISO 9001 and any customer or sector scheme).",
    "Data management whitepaper: claims such as employees 'spending valuable time searching' and 'the strongest businesses focus on a small number of indicators' give no figure, source or count. Measure your own search time before you quote a cost.",
    "Data management whitepaper: it leaves out the topics that make a single source of truth safe: who may see and change each record (access control), backup and retention of the documents, and data quality checks.",
    "Data management whitepaper: 'Information Organisational Chart' is used without being defined. A practical meaning is a map of who owns, stores and may change each kind of information.",
    "Data management whitepaper: 'conformity' (meeting a standard) and 'compliance' (meeting a rule or law) are used as if they were one thing. An audit asks for evidence of both, but they have different owners and different consequences.",
]
NOT_BUILT = ["Connecting real ERP, CRM, accounting or shop-floor systems, or document management software (SharePoint, M-Files and similar): needs your systems. This app helps you plan and audit; it cannot integrate them.",
             "An independent external review (tactic 5): a person, not a tool. A checklist of what to ask them is in the manual step."]


def reference() -> dict:
    return {"tactics": ["Connect your core business systems", "Use historical data to drive performance", "Create structure around technical documentation", "Strengthen conformity and compliance systems", "Seek independent operational perspective"],
            "formats": {"systems": SYS_FMT, "metrics": MET_FMT, "documents": DOC_FMT, "key_person": KEY_FMT}, "slips": SLIPS, "not_built": NOT_BUILT}
