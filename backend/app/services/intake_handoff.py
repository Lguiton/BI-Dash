"""After Intake finishes, suggest which dashboards fit the file and build a short brief so the chosen dashboard's agent can start on it. Local rules, no AI."""
from __future__ import annotations

import re

from app.services import intake

TRACKS = {
    "analyst": ("Analyst", "reports, trends and a dashboard from dated numbers"),
    "scientist": ("Data Scientist", "patterns, correlations and anomalies"),
    "ml": ("Machine Learning", "an honestly tested prediction model"),
    "engineering": ("Data Engineer", "cleaning, pipelines and data quality"),
    "ai": ("AI Engineer", "text and document work with AI"),
    "pm": ("Project Manager", "tasks, status and deadlines"),
    "sysanalyst": ("Systems Analyst", "requirements, data dictionary and fit"),
    "security": ("Cybersecurity", "logs, sign-in failures and risky activity"),
    "network": ("Network", "addresses, devices, traffic and capture files"),
    "itsupport": ("IT Support", "tickets, devices and event logs"),
    "cpe": ("Computer Engineer", "sensor, hardware and firmware data"),
}
KEYS = {
    "security": r"ip|src|dest|attack|threat|severity|firewall|auth|login|failed|user_?agent|alert|cve|vuln|honeypot|malware",
    "network": r"vlan|subnet|mac|latency|bandwidth|packet|ping|port|switch|router|ssid|rssi|throughput|dns",
    "itsupport": r"ticket|asset|hostname|device|event_?id|level|helpdesk|incident|serial|os_?version|patch",
    "pm": r"task|milestone|due|owner|assignee|sprint|status|priority|deadline|budget_hours",
    "cpe": r"voltage|current|sensor|firmware|temperature|rpm|torque|sample_?rate|signal",
    "analyst": r"revenue|sales|amount|price|cost|total|profit|qty|quantity|units|order|invoice|customer",
}
FILEHINT = {"security": r"auth|firewall|syslog|honeypot|access|secure", "network": r"pcap|netflow|snmp|dhcp|dns", "itsupport": r"ticket|asset|inventory|evtx|event", "pm": r"task|project|sprint|roadmap", "sysanalyst": r"requirement|spec|process|brd|use.?case"}


def _facts(run: dict) -> dict:
    st = next((s for s in run["stages"] if s["key"] == "structure"), {}).get("details", {})
    cols = [c["name"] for c in st.get("columns", [])]
    ctx = run.get("ctx", {})
    return {"cols": cols, "rows": st.get("rows") or ctx.get("rows") or 0, "free": bool(st.get("unstructured")), "date": ctx.get("date_col"), "num": ctx.get("num_cols", []), "text": ctx.get("text_cols", []),
            "table": ctx.get("work_table"), "target": run.get("options", {}).get("target"), "file": run.get("file", "")}


def suggest(rid: str) -> dict:
    run = intake.get(rid)
    f = _facts(run)
    score: dict[str, float] = {k: 0.0 for k in TRACKS}
    why: dict[str, list[str]] = {k: [] for k in TRACKS}

    def add(k: str, pts: float, reason: str) -> None:
        score[k] += pts
        if reason not in why[k]:
            why[k].append(reason)
    blob = " ".join(f["cols"]).lower()
    for k, pat in KEYS.items():
        hits = sorted({c for c in f["cols"] if re.search(pat, c.lower())})
        if hits:
            add(k, min(4, len(hits)) * 1.5, "columns like " + ", ".join(hits[:3]))
    for k, pat in FILEHINT.items():
        if re.search(pat, f["file"].lower()):
            add(k, 3, "the file name looks like " + TRACKS[k][0].lower() + " data")
    if f["date"] and f["num"]:
        add("analyst", 4, "it has dates and numbers to trend")
    if len(f["num"]) >= 3:
        add("scientist", 3, f"{len(f['num'])} numeric columns to compare")
    if f["rows"] >= 50 and f["num"]:
        add("ml", 1.5, "enough rows to try a model" + (f", predicting {f['target']}" if f["target"] else ""))
    if f["target"]:
        add("ml", 4, f"you named a target ({f['target']})")
    if f["free"] or (f["text"] and not f["num"]):
        add("ai", 3, "mostly text, which suits document and text work")
        add("sysanalyst", 1.5, "text content can hold requirements or process notes")
    if run["stages"] and any(s["key"] == "clean" and s["details"].get("left_for_a_human") for s in run["stages"]):
        add("engineering", 3, "some data problems need a person to decide")
    if f["rows"] and f["rows"] < 50:
        add("analyst", 1, "a small file: quick summary and checks first")
    add("engineering", 1, "check and keep the data clean")
    if not any(s > 3 for s in score.values()):
        add("analyst", 2, "a good first look at any table")
    ranked = sorted(score, key=lambda k: -score[k])[:4]
    out = []
    for k in ranked:
        if score[k] <= 0:
            continue
        name, does = TRACKS[k]
        out.append({"track": k, "name": name, "does": does, "why": why[k][:3] or ["a general fit"], "href": f"/tracks/{k}?view=tools&run={rid}"})
    return {"run": rid, "file": f["file"], "table": f["table"], "suggestions": out,
            "note": "Suggestions come from column names, types and the file name. You choose; the file goes along either way."}


def brief(rid: str, track: str) -> dict:
    if track not in TRACKS:
        raise intake.IntakeError("Unknown dashboard.", 404)
    from app.services import datasets
    run = intake.get(rid)
    f = _facts(run)
    t = f["table"]
    lines = [f"Working file: {f['file']} (Intake run {rid})", f"Stored as table '{t}': {f['rows']} rows, {len(f['cols'])} columns." if t else "The file has not been stored yet (test run only)."]
    clean = next((s for s in run["stages"] if s["key"] == "clean"), None)
    if clean:
        lines.append("Cleaning: " + clean["summary"])
    dic = next((s for s in run["stages"] if s["key"] == "dictionary"), None)
    if dic and dic["details"].get("dictionary"):
        lines.append("Columns: " + "; ".join(f"{c['column']} ({c['type']}, {c['role']}, {c['missing_pct']}% missing)" for c in dic["details"]["dictionary"][:25]))
    pv = next((s for s in run["stages"] if s["key"] == "privacy"), None)
    if pv and pv["details"].get("findings"):
        cols = sorted({x["column"] for x in pv["details"]["findings"]})
        lines.append("Personal-data columns (kept out of AI): " + ", ".join(cols))
    sample = ""
    if t:
        try:
            prof = datasets.profile(t)
            blocked = set(sorted({x["column"] for x in pv["details"]["findings"]})) if pv and pv["details"].get("findings") else set()
            keep = [c["name"] for c in prof["columns"] if c["name"] not in blocked][:12]
            rows = datasets.sample_rows(t, 25)["rows"]
            if rows:
                sample = "First rows:\n" + ",".join(keep) + "\n" + "\n".join(",".join("" if r.get(c) is None else str(r.get(c)) for c in keep) for r in rows)
        except Exception:  # noqa: BLE001
            sample = ""
    name, does = TRACKS[track]
    ask = f"I just uploaded {f['file']}. As the {name} agent, look at what is in it and tell me what you would do first, what looks wrong, and what to check. Keep it practical."
    return {"track": track, "name": name, "table": t, "text": "\n".join(lines + ([sample] if sample else []))[:11000], "ask": ask}
