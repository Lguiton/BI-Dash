"""Data governance for the active workspace: a catalog with owners and classifications, a PII scan, retention rules,
lineage, a controls checklist and an access summary.

The PII scan reports where personal data probably is and how sure it is. It never returns the values themselves.
It is a detector, not a guarantee: names it doesn't recognise and free text can still hide personal data.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

from app.services import backups, state, workspaces
from app.services.db import fetch_all, get_cursor

CLASSES = ("public", "internal", "confidential", "restricted")
SYSTEM_TABLES = {"app_meta", "user_tables", "kpi_definitions", "dim_entities_scd", "dim_date"}
NAME_RULES = [
    ("email", re.compile(r"e[-_]?mail", re.I)), ("phone", re.compile(r"phone|mobile|(^|_)tel(_|$)|cell", re.I)),
    ("national id", re.compile(r"ssn|social_?sec|national_?id|tax_?id|passport|driver.?s?_?lic", re.I)),
    ("birth date", re.compile(r"dob|birth", re.I)), ("address", re.compile(r"address|street|postal|zip_?code|(^|_)zip$", re.I)),
    ("person name", re.compile(r"first_?name|last_?name|full_?name|surname|customer_?name|patient|resident_?name", re.I)),
    ("financial", re.compile(r"salary|wage|income|card_?(num|no)|cc_?num|iban|account_?(num|no)|routing", re.I)),
    ("card number", re.compile(r"(^|_)(credit_?|debit_?)?card($|_)|pan$", re.I)),
    ("network id", re.compile(r"ip_?addr|(^|_)ip$|mac_?addr", re.I)),
    ("health", re.compile(r"diagnos|medication|icd|condition|treatment|allerg", re.I)),
]
VALUE_RULES = [
    ("email", re.compile(r"^[\w.+-]+@[\w-]+\.[\w.-]+$")),
    ("phone", re.compile(r"^\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}$")),
    ("national id", re.compile(r"^\d{3}-\d{2}-\d{4}$")),
    ("network id", re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")),
]
MAX_SAMPLE = 2000


class GovError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    return workspaces.active()


def _q(n: str) -> str:
    return '"' + n.replace('"', '""') + '"'


def luhn(s: str) -> bool:
    d = [int(c) for c in s if c.isdigit()]
    if not 13 <= len(d) <= 19:
        return False
    tot = 0
    for i, n in enumerate(reversed(d)):
        if i % 2:
            n *= 2
            n -= 9 if n > 9 else 0
        tot += n
    return tot % 10 == 0


def _objects(cur) -> dict[str, dict]:
    rows = fetch_all(cur, """SELECT t.table_name AS name, t.table_type AS ttype, c.column_name AS col, c.data_type AS dtype
        FROM information_schema.tables t JOIN information_schema.columns c USING (table_schema, table_name)
        WHERE t.table_schema = 'main' AND t.table_name <> 'app_meta' ORDER BY t.table_type, t.table_name, c.ordinal_position""")
    out: dict[str, dict] = {}
    for r in rows:
        o = out.setdefault(r["name"], {"name": r["name"], "kind": "view" if r["ttype"] == "VIEW" else "table", "columns": []})
        o["columns"].append({"name": r["col"], "type": r["dtype"]})
    return out


def pii_scan() -> dict:
    blocked = set(workspaces.settings(_ws())["blocked_columns"])
    findings = []
    with get_cursor() as cur:
        objs = _objects(cur)
        for o in objs.values():
            if o["kind"] != "table" or o["name"] in SYSTEM_TABLES:
                continue
            for c in o["columns"]:
                hits: dict[str, dict] = {}
                for cat, rx in NAME_RULES:
                    if rx.search(c["name"]):
                        hits[cat] = {"category": cat, "evidence": f"the column name looks like {cat}", "confidence": "medium"}
                if c["type"].upper() in ("VARCHAR", "TEXT"):
                    vals = [r[0] for r in cur.execute(f"SELECT {_q(c['name'])} FROM {_q(o['name'])} WHERE {_q(c['name'])} IS NOT NULL LIMIT {MAX_SAMPLE}").fetchall()]
                    n = len(vals)
                    if n:
                        for cat, rx in VALUE_RULES:
                            m = sum(1 for v in vals if rx.match(str(v).strip()))
                            if m and m / n >= 0.3:
                                h = hits.setdefault(cat, {"category": cat, "evidence": "", "confidence": "medium"})
                                h["evidence"] = f"{round(100 * m / n)}% of sampled values look like {cat}" + ("; the column name agrees" if h["evidence"] else "")
                                h["confidence"] = "high"
                        digits = [v for v in vals if re.fullmatch(r"[\d -]{13,23}", str(v).strip())]
                        m = sum(1 for v in digits if luhn(str(v)))
                        if m and m / n >= 0.3:
                            h = hits.setdefault("card number", {"category": "card number", "evidence": "", "confidence": "high"})
                            h["evidence"] = f"{round(100 * m / n)}% of sampled values pass the card-number checksum"
                elif c["type"].upper() in ("BIGINT", "HUGEINT", "INTEGER"):          # card numbers import as plain integers
                    vals = [str(r[0]) for r in cur.execute(f"SELECT {_q(c['name'])} FROM {_q(o['name'])} WHERE {_q(c['name'])} IS NOT NULL LIMIT {MAX_SAMPLE}").fetchall()]
                    m = sum(1 for v in vals if luhn(v))
                    if vals and m / len(vals) >= 0.3:
                        h = hits.setdefault("card number", {"category": "card number", "evidence": "", "confidence": "high"})
                        h["evidence"] = f"{round(100 * m / len(vals))}% of sampled values pass the card-number checksum"
                        h["confidence"] = "high"
                for h in hits.values():
                    findings.append({"table": o["name"], "column": c["name"], **h, "protected_from_ai": c["name"].lower() in blocked})
    order = {"high": 0, "medium": 1}
    findings.sort(key=lambda f: (order[f["confidence"]], f["table"], f["column"]))
    return {"findings": findings, "unprotected": sum(1 for f in findings if not f["protected_from_ai"]),
            "note": "Values are never returned. This looks at column names and a sample of up to 2,000 values per text column; "
                    "it can miss personal data hidden in free text or oddly named columns, so treat a clean result as 'nothing obvious', not 'nothing'."}


def protect(columns: list[str]) -> dict:
    if not columns:
        raise GovError("Pick at least one column.")
    with get_cursor() as cur:
        have = {c["name"].lower() for o in _objects(cur).values() for c in o["columns"]}
    unknown = [c for c in columns if c.lower() not in have]
    if unknown:
        raise GovError(f"Not a column in this workspace: {', '.join(unknown)}.", 404)
    cur_set = workspaces.settings(_ws())
    new = workspaces.update_settings(_ws(), {"blocked_columns": [*cur_set["blocked_columns"], *columns]})
    state.audit("gov_protect", f"blocked from AI: {', '.join(columns)[:200]}")
    return {"blocked_columns": new["blocked_columns"]}


# ------------------------------------------------------------------ catalog
def _meta() -> dict[str, dict]:
    return {r["asset"]: r for r in state.rows("SELECT * FROM gov_assets WHERE workspace = ?", (_ws(),))}


def catalog() -> dict:
    meta = _meta()
    pii = {}
    for f in pii_scan()["findings"]:
        pii.setdefault(f["table"], []).append(f)
    out = []
    with get_cursor() as cur:
        for o in _objects(cur).values():
            m = meta.get(o["name"], {})
            rows = cur.execute(f"SELECT COUNT(*) FROM {_q(o['name'])}").fetchone()[0]
            comp = dup = None
            if o["kind"] == "table" and rows and len(o["columns"]) <= 80:
                parts = ", ".join(f"COUNT({_q(c['name'])})" for c in o["columns"])
                counts = cur.execute(f"SELECT {parts} FROM {_q(o['name'])}").fetchone()
                comp = round(100 * sum(counts) / (rows * len(o["columns"])), 1)
                dup = rows - cur.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {_q(o['name'])})").fetchone()[0]
            eligible = None
            if m.get("retention_days") and m.get("retention_column"):
                cutoff = (datetime.now(timezone.utc) - timedelta(days=m["retention_days"])).date().isoformat()
                try:
                    eligible = cur.execute(f"SELECT COUNT(*) FROM {_q(o['name'])} WHERE {_q(m['retention_column'])} < CAST(? AS DATE)", [cutoff]).fetchone()[0]
                except Exception:    # noqa: BLE001 - the column was removed since the rule was saved
                    eligible = None
            has_pii = o["name"] in pii
            out.append({"name": o["name"], "kind": o["kind"], "system": o["name"] in SYSTEM_TABLES, "rows": rows, "columns": [c for c in o["columns"]],
                        "owner": m.get("owner") or "", "steward": m.get("steward") or "", "description": m.get("description") or "",
                        "classification": m.get("classification") or "", "retention_days": m.get("retention_days"), "retention_column": m.get("retention_column") or "",
                        "completeness_pct": comp, "duplicate_rows": dup, "retention_eligible_rows": eligible, "pii_columns": len(pii.get(o["name"], [])),
                        "suggested_classification": "confidential" if has_pii else "internal"})
    return {"assets": out, "classes": CLASSES,
            "classes_help": {"public": "Fine to share with anyone.", "internal": "Business data, not for outsiders.", "confidential": "Personal or commercially sensitive.",
                             "restricted": "Would cause serious harm if leaked (health, financial identifiers)."}}


def save_asset(name: str, data: dict) -> dict:
    with get_cursor() as cur:
        objs = _objects(cur)
    if name not in objs:
        raise GovError("No such table or view.", 404)
    cls = data.get("classification") or None
    if cls and cls not in CLASSES:
        raise GovError(f"classification must be one of {', '.join(CLASSES)}.")
    days = data.get("retention_days")
    col = (data.get("retention_column") or "").strip() or None
    if days in ("", None):
        days = None
    else:
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise GovError("retention_days must be a whole number.") from None
        if not 1 <= days <= 36500:
            raise GovError("retention_days must be between 1 and 36,500.")
        if not col:
            raise GovError("Choose which date column the retention rule counts from.")
    if col:
        cinfo = next((c for c in objs[name]["columns"] if c["name"] == col), None)
        if not cinfo:
            raise GovError(f"'{col}' is not a column of {name}.")
        if not (cinfo["type"].upper() == "DATE" or cinfo["type"].upper().startswith("TIMESTAMP")):
            raise GovError(f"'{col}' is not a date column.")
    state.run("""INSERT INTO gov_assets (workspace, asset, owner, steward, description, classification, retention_days, retention_column) VALUES (?,?,?,?,?,?,?,?)
                 ON CONFLICT(workspace, asset) DO UPDATE SET owner=excluded.owner, steward=excluded.steward, description=excluded.description,
                 classification=excluded.classification, retention_days=excluded.retention_days, retention_column=excluded.retention_column""",
              (_ws(), name, str(data.get("owner", ""))[:60], str(data.get("steward", ""))[:60], str(data.get("description", ""))[:300], cls, days, col))
    state.audit("gov_asset_save", f"{name}: {cls or 'unclassified'}")
    return {"saved": name}


# ------------------------------------------------------------------ lineage, controls, access
def lineage() -> dict:
    edges, nodes = [], {}

    def node(n, kind): nodes.setdefault(n, {"id": n, "kind": kind})
    with get_cursor() as cur:
        objs = _objects(cur)
        for n, o in objs.items():
            node(n, o["kind"])
        try:
            for v in fetch_all(cur, "SELECT view_name, sql FROM duckdb_views() WHERE schema_name = 'main' AND internal = false"):
                for t in objs:
                    if t != v["view_name"] and re.search(rf"\b{re.escape(t)}\b", v["sql"] or "") and objs[t]["kind"] == "table":
                        edges.append({"from": t, "to": v["view_name"], "kind": "view reads table"})
        except Exception:    # noqa: BLE001
            pass
        try:
            for u in fetch_all(cur, "SELECT table_name, source FROM user_tables"):
                src = u["source"] or "upload"
                node(src, "source")
                edges.append({"from": src, "to": u["table_name"], "kind": "loaded by"})
        except Exception:    # noqa: BLE001
            pass
    for s in state.rows("SELECT name, kind, config, target FROM sources WHERE workspace = ?", (_ws(),)):
        node(f"source: {s['name']}", "source")
        edges.append({"from": f"source: {s['name']}", "to": s["target"], "kind": f"refreshed from {s['kind']}"})
    mode = workspaces.settings(_ws())["ai_mode"]
    consumers = [{"name": "Dashboards and reports", "reads": "fact_operations, dim_entities, v_operations_flat"},
                 {"name": "Exports (CSV, Excel, Parquet...)", "reads": "operations, facts, entities, dates"},
                 {"name": "Scheduled email report", "reads": "the filtered KPI view"},
                 {"name": "AI Lab", "reads": "everything not blocked" if mode == "full" else "summaries only" if mode == "aggregate" else "nothing (AI is off)"}]
    seen, uniq = set(), []
    for e in edges:
        k = (e["from"], e["to"], e["kind"])
        if k not in seen:
            seen.add(k)
            uniq.append(e)
    return {"nodes": list(nodes.values()), "edges": uniq, "consumers": consumers,
            "pipeline": "Pipeline monitor: landing files -> bronze -> silver (validated) -> gold (marts); bad rows go to quarantine."}


def controls() -> dict:
    cat = catalog()
    own = [a for a in cat["assets"] if a["kind"] == "table" and not a["system"]]
    pii = pii_scan()
    ws = _ws()
    mode = workspaces.settings(ws)["ai_mode"]
    bl = backups.list_backups(ws)
    recent_audit = state.one("SELECT COUNT(*) AS n FROM audit WHERE at >= ?", ((datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S"),))["n"]

    def pct(n, d): return f"{n} of {d}"
    owned, classed = sum(1 for a in own if a["owner"]), sum(1 for a in own if a["classification"])
    unprot = pii["unprotected"]
    items = [
        {"id": "owners", "title": "Every table has an owner", "ok": bool(own) and owned == len(own), "detail": pct(owned, len(own)) if own else "no tables yet", "fix": "Assign an owner in the catalog."},
        {"id": "classified", "title": "Every table is classified", "ok": bool(own) and classed == len(own), "detail": pct(classed, len(own)) if own else "no tables yet", "fix": "Choose public, internal, confidential or restricted."},
        {"id": "pii_ai", "title": "Personal data is kept from the AI", "ok": unprot == 0 or mode == "off", "detail": "AI is off" if mode == "off" and unprot else f"{unprot} unprotected column(s)" if unprot else "no personal data detected",
         "fix": "Block the flagged columns from the AI, or switch AI off."},
        {"id": "ai_mode", "title": "AI access is a deliberate choice", "ok": ws == "practice" or mode in ("off", "aggregate"), "detail": f"mode: {mode}", "fix": "In Real, prefer off or summaries only."},
        {"id": "backup", "title": "A backup exists from the last 7 days", "ok": bool(bl) and (datetime.now(timezone.utc) - datetime.strptime(bl[0]["created_at"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)).days < 7,
         "detail": f"latest {bl[0]['created_at']} UTC" if bl else "none", "fix": "Back up now and turn on the daily backup."},
        {"id": "retention", "title": "Tables with personal data have a retention rule", "ok": all(a["retention_days"] for a in own if a["pii_columns"]), "detail": "all set" if all(a["retention_days"] for a in own if a["pii_columns"]) else "some missing",
         "fix": "Decide how long you may keep it and set it in the catalog."},
        {"id": "quality", "title": "Tables are at least 95% complete", "ok": all((a["completeness_pct"] or 100) >= 95 for a in own), "detail": "all above 95%" if all((a["completeness_pct"] or 100) >= 95 for a in own) else "some below 95%", "fix": "Fix gaps at the source."},
        {"id": "audit", "title": "Activity is being logged", "ok": recent_audit > 0, "detail": f"{recent_audit} events in 30 days", "fix": "Use the app; imports, exports and AI questions are logged automatically."},
    ]
    return {"controls": items, "in_place": sum(1 for i in items if i["ok"]), "total": len(items)}


def access_summary() -> dict:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
    rows = state.rows("SELECT action, COUNT(*) AS n, SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END) AS failed FROM audit WHERE workspace = ? AND at >= ? GROUP BY action ORDER BY n DESC", (_ws(), since))
    leaving = [r for r in rows if r["action"] in ("export", "email_report", "ai_ask")]
    return {"since": since, "by_action": rows, "failed_total": sum(r["failed"] or 0 for r in rows), "data_leaving": leaving,
            "ai": {"mode": workspaces.settings(_ws())["ai_mode"], "blocked_columns": workspaces.settings(_ws())["blocked_columns"]},
            "note": "'Data leaving' counts exports, emailed reports and AI questions: the three ways data goes beyond this computer."}
