"""Systems analysis: requirements and traceability, a data dictionary built from the live schema, process analysis of the
operations data, feasibility scoring, and the standard calculators (queueing, availability, cost-benefit, capacity).

Formulas
  M/M/1: rho = lam/mu, L = rho/(1-rho), Lq = rho^2/(1-rho), W = 1/(mu-lam), Wq = rho/(mu-lam)
  M/M/c (Erlang C): a = lam/mu, rho = a/c, C = [a^c/c! / (1-rho)] / [sum_{k<c} a^k/k! + a^c/c! / (1-rho)],
                    Wq = C/(c*mu - lam), W = Wq + 1/mu, P(wait > t) = C * exp(-(c*mu - lam) * t)
  Availability: serial = product of parts; parallel = 1 - product of (1 - part); error budget = (1 - SLO) * window
  NPV = sum CF_t/(1+r)^t, ROI = (net benefit - investment)/investment, IRR = rate where NPV = 0
"""
from __future__ import annotations

import json
import math
import statistics

from app.services import state, workspaces
from app.services.db import fetch_all, fetch_one, get_cursor

REQ_KINDS = ("functional", "non-functional", "constraint")
REQ_PRIORITY = ("must", "should", "could", "wont")
REQ_STATUS = ("proposed", "approved", "built", "tested", "rejected")


class SaError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    return workspaces.active()


def _r(v, n=3):
    return None if v is None else round(v, n)


# ------------------------------------------------------------------ requirements
def list_requirements() -> list[dict]:
    return state.rows("SELECT * FROM sa_requirements WHERE workspace = ? ORDER BY code", (_ws(),))


def save_requirement(data: dict, rid: int | None = None) -> dict:
    title = str(data.get("title", "")).strip()
    if not title:
        raise SaError("Give the requirement a title.")
    kind, pr, st = data.get("kind") or "functional", data.get("priority") or "should", data.get("status") or "proposed"
    for val, allowed, name in ((kind, REQ_KINDS, "kind"), (pr, REQ_PRIORITY, "priority"), (st, REQ_STATUS, "status")):
        if val not in allowed:
            raise SaError(f"{name} must be one of {', '.join(allowed)}.")
    vals = (title[:200], kind, pr, st, str(data.get("source", ""))[:80], str(data.get("acceptance", ""))[:400], str(data.get("test_ref", ""))[:160])
    if rid is None:
        n = 1 + max((int(r["code"].split("-")[1]) for r in list_requirements() if r["code"].startswith("REQ-") and r["code"][4:].isdigit()), default=0)
        cur = state.run("INSERT INTO sa_requirements (workspace, code, title, kind, priority, status, source, acceptance, test_ref, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (_ws(), f"REQ-{n:03d}", *vals, state.now()[:10]))
        rid = cur.lastrowid
    else:
        if not state.one("SELECT 1 FROM sa_requirements WHERE id = ? AND workspace = ?", (rid, _ws())):
            raise SaError("No such requirement.", 404)
        state.run("UPDATE sa_requirements SET title=?, kind=?, priority=?, status=?, source=?, acceptance=?, test_ref=? WHERE id=?", (*vals, rid))
    state.audit("sa_requirement_save", title[:80])
    return state.one("SELECT * FROM sa_requirements WHERE id = ?", (rid,))


def delete_requirement(rid: int) -> None:
    state.run("DELETE FROM sa_requirements WHERE id = ? AND workspace = ?", (rid, _ws()))


def traceability(reqs: list[dict]) -> dict:
    live = [r for r in reqs if r["status"] != "rejected"]
    needs_test = [r for r in live if r["status"] in ("built", "tested")]
    gaps = [{"code": r["code"], "title": r["title"], "problem": "built but no test is linked"} for r in needs_test if not r["test_ref"]]
    gaps += [{"code": r["code"], "title": r["title"], "problem": "marked tested but no test is linked"} for r in live if r["status"] == "tested" and not r["test_ref"] and
             not any(g["code"] == r["code"] for g in gaps)]
    gaps += [{"code": r["code"], "title": r["title"], "problem": "no acceptance criterion written"} for r in live if r["status"] in ("approved", "built", "tested") and not r["acceptance"]]
    gaps += [{"code": r["code"], "title": r["title"], "problem": "a must-have that is still only proposed"} for r in live if r["priority"] == "must" and r["status"] == "proposed"]
    by_status = {s: sum(1 for r in reqs if r["status"] == s) for s in REQ_STATUS}
    cov = 100 * sum(1 for r in needs_test if r["test_ref"]) / len(needs_test) if needs_test else None
    return {"total": len(reqs), "by_status": by_status, "by_kind": {k: sum(1 for r in reqs if r["kind"] == k) for k in REQ_KINDS},
            "test_coverage_pct": _r(cov, 1), "gaps": gaps,
            "note": "Coverage counts built or tested requirements that name a test. A requirement with no test can't be shown to be met."}


def load_example_requirements() -> int:
    if _ws() != "practice":
        raise SaError("The example is only for the Practice workspace.", 409)
    if list_requirements():
        raise SaError("This workspace already has requirements.", 409)
    rows = [
        ("Import any CSV or Excel file without fixed column names", "functional", "must", "tested", "Founder", "A file with columns tier, mrr loads as its own table with detected types", "tests/test_data.py::test_import_profile_and_charts"),
        ("A failed import never leaves half-loaded data", "non-functional", "must", "tested", "Founder", "A file with one bad row changes nothing and lists the problem lines", "tests/test_ingest.py"),
        ("Practice and Real data are stored separately", "constraint", "must", "tested", "Founder", "Switching workspaces shows different tables; deleting in one leaves the other intact", "tests/test_data.py::test_workspaces_isolated"),
        ("Saved sources refresh on a schedule", "functional", "should", "tested", "Founder", "A due source runs and records its result; a failure doesn't stop the scheduler", "tests/test_sources.py::test_url_source_refresh_and_shrink_guard"),
        ("A refresh that would delete most of a table is refused", "non-functional", "must", "tested", "Founder", "New data under 50% of the old row count is rejected and the table is untouched", "tests/test_sources.py::test_url_source_refresh_and_shrink_guard"),
        ("The AI can be limited or switched off per workspace", "functional", "must", "tested", "Founder", "Off returns 403; blocked columns are rejected in queries and results", "tests/test_ai_policy.py"),
        ("Restore a backup and undo the restore", "functional", "should", "tested", "Founder", "Restoring first saves a safety copy", "tests/test_backups.py::test_backup_restore_roundtrip"),
        ("Page loads in under 2 seconds on 100,000 rows", "non-functional", "should", "approved", "Founder", "", ""),
        ("Users sign in with their own account", "functional", "wont", "proposed", "Founder", "", ""),
        ("Reports can be emailed on a schedule", "functional", "could", "built", "Founder", "A scheduled email arrives with the Excel report attached", ""),
    ]
    for t, k, p, s, src, acc, tr in rows:
        save_requirement({"title": t, "kind": k, "priority": p, "status": s, "source": src, "acceptance": acc, "test_ref": tr})
    return len(rows)


# ------------------------------------------------------------------ data dictionary and ER diagram
DESCRIPTIONS = {
    "fact_operations": {"_": "One row per operational record (the fact table).", "fact_id": "Unique id of the record.", "record_date": "Day the activity happened.",
                        "entity_id": "Which entity it belongs to; joins to dim_entities.", "revenue": "Money in, in dollars.", "operational_cost": "Money out, in dollars.",
                        "units_processed": "Count of units handled.", "duration_minutes": "Time the record took.", "status": "Completed, Pending, and so on."},
    "dim_entities": {"_": "One row per entity (store, zone, account...). The dimension table.", "entity_id": "Unique id.", "name": "Display name.",
                     "category": "Group the entity belongs to.", "baseline_target": "Cost budget per record."},
    "dim_date": {"_": "Generated calendar, one row per day in the data range."},
    "v_operations_flat": {"_": "Facts joined to entities and dates in one wide view, for BI tools."},
    "user_tables": {"_": "Registry of tables imported through My data."},
}
RELATIONSHIPS = [("fact_operations", "entity_id", "dim_entities", "entity_id", "many facts belong to one entity")]


def _type_kind(t: str) -> str:
    t = t.upper()
    return "number" if (t in ("BIGINT", "INTEGER", "SMALLINT", "TINYINT", "DOUBLE", "FLOAT", "REAL", "HUGEINT") or t.startswith("DECIMAL")) else \
        "date" if (t == "DATE" or t.startswith("TIMESTAMP")) else "bool" if t == "BOOLEAN" else "text"


def data_dictionary() -> dict:
    with get_cursor() as cur:
        objs = fetch_all(cur, """SELECT t.table_name AS name, t.table_type AS ttype, c.column_name AS col, c.data_type AS dtype, c.is_nullable AS nullable
            FROM information_schema.tables t JOIN information_schema.columns c USING (table_schema, table_name)
            WHERE t.table_schema = 'main' AND t.table_name NOT IN ('app_meta') ORDER BY t.table_type, t.table_name, c.ordinal_position""")
        pks = {}
        try:
            for r in fetch_all(cur, "SELECT table_name, constraint_type, constraint_column_names AS cols FROM duckdb_constraints() WHERE constraint_type IN ('PRIMARY KEY','UNIQUE')"):
                for c in r["cols"]:
                    pks.setdefault((r["table_name"], c), r["constraint_type"])
        except Exception:    # noqa: BLE001 - older DuckDB builds: carry on without key flags
            pass
        tables: dict[str, dict] = {}
        for o in objs:
            t = tables.setdefault(o["name"], {"name": o["name"], "kind": "view" if o["ttype"] == "VIEW" else "table", "columns": []})
            t["columns"].append({"name": o["col"], "type": o["dtype"], "nullable": o["nullable"] == "YES", "key": pks.get((o["name"], o["col"])),
                                 "description": DESCRIPTIONS.get(o["name"], {}).get(o["col"], "")})
        for t in tables.values():
            q = '"' + t["name"].replace('"', '""') + '"'
            t["rows"] = cur.execute(f"SELECT COUNT(*) FROM {q}").fetchone()[0]
            t["description"] = DESCRIPTIONS.get(t["name"], {}).get("_", "")
            if t["kind"] == "table" and t["rows"] and len(t["columns"]) <= 80:
                parts = ", ".join(f'COUNT("{c["name"]}") AS n{i}, approx_count_distinct("{c["name"]}") AS d{i}' for i, c in enumerate(t["columns"]))
                st = fetch_one(cur, f"SELECT {parts} FROM {q}")
                for i, c in enumerate(t["columns"]):
                    c["null_pct"] = _r(100 * (1 - st[f"n{i}"] / t["rows"]), 1)
                    c["distinct"] = st[f"d{i}"]
        rels = []
        for ft, fc, pt, pc, text in RELATIONSHIPS:
            if ft in tables and pt in tables:
                orphans = cur.execute(f'SELECT COUNT(*) FROM "{ft}" f WHERE f."{fc}" IS NOT NULL AND NOT EXISTS (SELECT 1 FROM "{pt}" p WHERE p."{pc}" = f."{fc}")').fetchone()[0]
                rels.append({"from_table": ft, "from_column": fc, "to_table": pt, "to_column": pc, "meaning": text, "orphans": orphans, "valid": orphans == 0})
    lines = ["erDiagram"]
    for t in tables.values():
        if t["kind"] != "table":
            continue
        lines.append(f"  {t['name']} {{")
        for c in t["columns"][:25]:
            ty = "".join(ch for ch in c["type"].split("(")[0].lower() if ch.isalnum()) or "text"
            lines.append(f"    {ty} {c['name']}{' PK' if c['key'] == 'PRIMARY KEY' else ''}")
        lines.append("  }")
    for r in rels:
        lines.append(f'  {r["to_table"]} ||--o{{ {r["from_table"]} : "{r["from_column"]}"')
    return {"tables": list(tables.values()), "relationships": rels, "mermaid": "\n".join(lines)}


# ------------------------------------------------------------------ process analysis of the operations data
def process_analysis() -> dict:
    with get_cursor() as cur:
        meta = fetch_one(cur, "SELECT COUNT(*) AS n, COUNT(duration_minutes) AS with_duration, COUNT(DISTINCT record_date) AS days FROM fact_operations")
        if not meta["n"] or not meta["with_duration"]:
            return {"available": False, "reason": "Needs operations records with duration_minutes to analyse the process."}
        ov = fetch_one(cur, """SELECT AVG(duration_minutes) AS avg, MEDIAN(duration_minutes) AS p50, quantile_cont(duration_minutes, 0.85) AS p85,
            quantile_cont(duration_minutes, 0.95) AS p95, STDDEV_SAMP(duration_minutes) AS sd, SUM(units_processed) AS units, SUM(duration_minutes) AS minutes
            FROM fact_operations WHERE duration_minutes IS NOT NULL""")
        ents = fetch_all(cur, """SELECT COALESCE(e.name, f.entity_id) AS entity, COUNT(*) AS records, AVG(f.duration_minutes) AS avg_min,
            quantile_cont(f.duration_minutes, 0.85) AS p85_min, SUM(f.units_processed) AS units, SUM(f.duration_minutes) AS minutes,
            SUM(f.operational_cost) / NULLIF(SUM(f.units_processed), 0) AS cost_per_unit,
            100.0 * AVG(CASE WHEN f.status = 'Completed' THEN 1.0 ELSE 0.0 END) AS completion_pct
            FROM fact_operations f LEFT JOIN dim_entities e ON e.entity_id = f.entity_id WHERE f.duration_minutes IS NOT NULL
            GROUP BY 1 HAVING COUNT(*) >= 2 ORDER BY p85_min DESC LIMIT 12""")
        statuses = fetch_all(cur, "SELECT COALESCE(status, 'Unknown') AS status, COUNT(*) AS n FROM fact_operations GROUP BY 1 ORDER BY 2 DESC")
    for e in ents:
        e["units_per_hour"] = _r(60 * e["units"] / e["minutes"], 2) if e["minutes"] else None
    cv = ov["sd"] / ov["avg"] if ov["avg"] and ov["sd"] is not None else None
    per_day = meta["n"] / meta["days"] if meta["days"] else None
    bn = ents[0] if ents else None
    lam_day = per_day
    wip = lam_day * ov["avg"] / 1440 if lam_day else None
    return {"available": True, "records": meta["n"], "days": meta["days"],
            "duration": {"avg": _r(ov["avg"], 1), "p50": _r(ov["p50"], 1), "p85": _r(ov["p85"], 1), "p95": _r(ov["p95"], 1), "cv": _r(cv, 2)},
            "variability": None if cv is None else ("high: results are hard to predict" if cv > 1 else "moderate" if cv > 0.5 else "low: steady process"),
            "entities": ents, "statuses": statuses,
            "bottleneck": None if not bn else {"entity": bn["entity"], "p85_min": _r(bn["p85_min"], 1), "why": "slowest 85th-percentile duration: a process is only as fast as its slowest common case"},
            "littles_law": {"arrivals_per_day": _r(lam_day, 1), "avg_minutes": _r(ov["avg"], 1), "avg_in_progress": _r(wip, 2),
                            "reading": "Average work in progress = arrival rate x average time in the system (Little's law)."},
            "queue_inputs": {"arrivals_per_day": _r(lam_day, 1), "service_minutes": _r(ov["avg"], 1)}}


# ------------------------------------------------------------------ calculators
def mm1(lam: float, mu: float) -> dict:
    if lam <= 0 or mu <= 0:
        raise SaError("Arrival and service rates must be above zero.")
    rho = lam / mu
    if rho >= 1:
        return {"stable": False, "utilization": _r(rho), "reason": f"Arrivals ({lam:g}) are at or above capacity ({mu:g}). The queue grows without limit."}
    return {"stable": True, "utilization": _r(rho), "avg_in_system": _r(rho / (1 - rho)), "avg_in_queue": _r(rho * rho / (1 - rho)),
            "avg_time_in_system": _r(1 / (mu - lam), 4), "avg_wait": _r(rho / (mu - lam), 4)}


def erlang_c(lam: float, mu: float, c: int) -> dict:
    if lam <= 0 or mu <= 0 or c < 1:
        raise SaError("Arrival rate, service rate and servers must all be above zero.")
    if c > 500:
        raise SaError("Up to 500 servers.")
    a = lam / mu
    rho = a / c
    if rho >= 1:
        return {"stable": False, "utilization": _r(rho), "reason": f"{c} server(s) can't keep up: offered load is {a:.2f} servers' worth."}
    s = sum(a ** k / math.factorial(k) for k in range(c))
    top = a ** c / math.factorial(c) / (1 - rho)
    pw = top / (s + top)
    wq = pw / (c * mu - lam)
    return {"stable": True, "servers": c, "utilization": _r(rho), "offered_load": _r(a), "p_wait": _r(pw), "avg_wait": _r(wq, 4), "avg_time_in_system": _r(wq + 1 / mu, 4),
            "avg_in_queue": _r(lam * wq), "avg_in_system": _r(lam * (wq + 1 / mu)), "decay": c * mu - lam}


def p_wait_longer(lam: float, mu: float, c: int, t: float) -> float | None:
    r = erlang_c(lam, mu, c)
    return None if not r["stable"] else _r(r["p_wait"] * math.exp(-r["decay"] * t), 4)


def queue(lam: float, mu: float, servers: int, target_wait: float | None = None) -> dict:
    out = mm1(lam, mu) if servers == 1 else erlang_c(lam, mu, servers)
    out["model"] = "M/M/1" if servers == 1 else f"M/M/{servers} (Erlang C)"
    if out.get("stable") and target_wait is not None and target_wait >= 0:
        out["p_wait_over_target"] = p_wait_longer(lam, mu, servers, target_wait) if servers > 1 else _r((lam / mu) * math.exp(-(mu - lam) * target_wait), 4)
    need = None
    if target_wait is not None and target_wait >= 0:
        for c in range(max(1, math.ceil(lam / mu)), 501):
            r = erlang_c(lam, mu, c) if c > 1 else mm1(lam, mu)
            if r.get("stable") and r["avg_wait"] <= target_wait:
                need = c
                break
    out["servers_for_target_wait"] = need
    out["units_note"] = "Use the same time unit for both rates (per hour, per minute...). Waits come back in that unit."
    return out


def availability(slo: float, window_days: float = 30, used_minutes: float = 0, parts: list[float] | None = None, mode: str = "serial") -> dict:
    if not 0 < slo < 100:
        raise SaError("The SLO is a percentage between 0 and 100 (for example 99.9).")
    if window_days <= 0:
        raise SaError("The window must be above zero days.")
    total = window_days * 1440
    budget = total * (1 - slo / 100)
    table = [{"period": n, "downtime_minutes": _r(m * (1 - slo / 100), 2)} for n, m in (("per day", 1440), ("per week", 10080), ("per 30 days", 43200), ("per year", 525600))]
    out = {"slo": slo, "window_days": window_days, "error_budget_minutes": _r(budget, 2), "used_minutes": used_minutes,
           "remaining_minutes": _r(budget - used_minutes, 2), "burn_pct": _r(100 * used_minutes / budget, 1) if budget else None,
           "allowed_downtime": table, "status": "budget exhausted: freeze risky changes" if used_minutes >= budget else "within budget"}
    if parts:
        if any(not 0 < p <= 100 for p in parts):
            raise SaError("Each component availability must be above 0 and at most 100.")
        fr = [p / 100 for p in parts]
        comb = math.prod(fr) if mode == "serial" else 1 - math.prod(1 - f for f in fr)
        out["composite"] = {"mode": mode, "availability_pct": _r(100 * comb, 5), "meets_slo": 100 * comb >= slo,
                            "note": "Serial: every part must be up, so availability drops. Parallel (redundant): any one part up is enough, so it rises."}
    return out


def cost_benefit(initial: float, annual_benefit: float, annual_cost: float, years: int, rate_pct: float) -> dict:
    if years < 1 or years > 30:
        raise SaError("Years must be between 1 and 30.")
    if initial < 0 or annual_benefit < 0 or annual_cost < 0:
        raise SaError("Costs and benefits can't be negative.")
    r = rate_pct / 100
    net = annual_benefit - annual_cost
    cfs = [-initial] + [net] * years
    npv = sum(cf / (1 + r) ** t for t, cf in enumerate(cfs))

    def f(x): return sum(cf / (1 + x) ** t for t, cf in enumerate(cfs))
    irr = None
    if net > 0 and initial > 0 and f(-0.99) * f(10) < 0:
        lo, hi = -0.99, 10.0
        for _ in range(200):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
        irr = (lo + hi) / 2
    cum, dpay = -initial, None
    for t in range(1, years + 1):
        prev = cum
        cum += net / (1 + r) ** t
        if dpay is None and cum >= 0 > prev:
            dpay = (t - 1) + (-prev) / (net / (1 + r) ** t)
    pvb = sum(annual_benefit / (1 + r) ** t for t in range(1, years + 1))
    pvc = initial + sum(annual_cost / (1 + r) ** t for t in range(1, years + 1))
    simple = initial / net if net > 0 else None
    return {"annual_net": _r(net, 2), "npv": _r(npv, 2), "roi_pct": _r(100 * (net * years - initial) / initial, 1) if initial else None,
            "irr_pct": _r(100 * irr, 2) if irr is not None else None, "payback_years": _r(simple, 2) if simple and simple <= years else None,
            "discounted_payback_years": _r(dpay, 2), "benefit_cost_ratio": _r(pvb / pvc, 3) if pvc else None,
            "verdict": "Worth doing on these numbers (NPV above zero)." if npv > 0 else "Doesn't pay back at this discount rate over this period.",
            "cashflows": [{"year": t, "cash": _r(cf, 2), "cumulative_discounted": _r(sum(c / (1 + r) ** k for k, c in enumerate(cfs[:t + 1])), 2)} for t, cf in enumerate(cfs)]}


def capacity(load: float, cap: float, growth_pct: float, headroom_pct: float = 80) -> dict:
    if load <= 0 or cap <= 0:
        raise SaError("Load and capacity must be above zero.")
    if load >= cap:
        return {"months_to_full": 0, "months_to_threshold": 0, "reason": "Already at or over capacity."}
    g = growth_pct / 100
    if g <= 0:
        return {"months_to_full": None, "months_to_threshold": None, "reason": "No growth: the load never reaches capacity."}
    thr = cap * headroom_pct / 100
    return {"months_to_full": _r(math.log(cap / load) / math.log(1 + g), 1),
            "months_to_threshold": 0 if load >= thr else _r(math.log(thr / load) / math.log(1 + g), 1), "headroom_pct": headroom_pct, "growth_pct": growth_pct,
            "projection": [{"month": m, "load": _r(load * (1 + g) ** m, 2)} for m in range(0, 25, 2)],
            "note": "Compound monthly growth. Plan to add capacity when you reach the headroom threshold, not when you hit 100%."}


# ------------------------------------------------------------------ feasibility (TELOS)
CRITERIA = (("technical", "Technical", "Can we build it with the skills and tools we have?"), ("economic", "Economic", "Do the benefits outweigh the cost?"),
            ("legal", "Legal", "Any contract, privacy or compliance problem?"), ("operational", "Operational", "Will people actually use it and run it?"),
            ("schedule", "Schedule", "Can it be done in the time available?"))


def feasibility_get() -> dict:
    raw = state.kv_get(f"sa_feasibility:{_ws()}")
    saved = json.loads(raw) if raw else {}
    rows = []
    for key, label, q in CRITERIA:
        s = saved.get(key, {})
        rows.append({"key": key, "label": label, "question": q, "score": s.get("score"), "weight": s.get("weight", 1), "note": s.get("note", "")})
    scored = [r for r in rows if r["score"] is not None and r["weight"] > 0]
    wsum = sum(r["weight"] for r in scored)
    total = sum(r["score"] * r["weight"] for r in scored) / wsum if wsum else None
    worst = min(scored, key=lambda r: r["score"]) if scored else None
    verdict = None
    if total is not None:
        verdict = ("Feasible" if total >= 3.8 and worst["score"] >= 3 else "Feasible with changes" if total >= 3 else "Not feasible as proposed")
    return {"rows": rows, "weighted_score": _r(total, 2), "verdict": verdict, "weakest": None if not worst else worst["label"],
            "scale": "Score 1 (a serious problem) to 5 (no concerns). A single score below 3 needs a plan even if the average looks good."}


def feasibility_save(data: dict) -> dict:
    out = {}
    for key, _, _ in CRITERIA:
        v = data.get(key)
        if not v:
            continue
        try:
            s, w = (None if v.get("score") in (None, "") else float(v["score"])), float(v.get("weight", 1))
        except (TypeError, ValueError):
            raise SaError("Scores and weights must be numbers.") from None
        if s is not None and not 1 <= s <= 5:
            raise SaError("Scores run from 1 to 5.")
        if not 0 <= w <= 10:
            raise SaError("Weights run from 0 to 10.")
        out[key] = {"score": s, "weight": w, "note": str(v.get("note", ""))[:200]}
    state.kv_set(f"sa_feasibility:{_ws()}", json.dumps(out))
    state.audit("sa_feasibility_save", "TELOS scores updated")
    return feasibility_get()


def overview() -> dict:
    reqs = list_requirements()
    return {"requirements": reqs, "traceability": traceability(reqs), "enums": {"kinds": REQ_KINDS, "priority": REQ_PRIORITY, "status": REQ_STATUS},
            "feasibility": feasibility_get()}
