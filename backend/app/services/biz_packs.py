"""Industry x department business dashboards (not the practice sample packs in packs.py).

A pack is one department's dashboard for one industry: a small table (one row per record), KPI cards, a trend
and breakdowns. Every pack runs on the same engine, so a new industry is a new entry in CATALOG, not new code.
Load sample data to see it work, or import your own CSV with the same columns. SQL comes only from CATALOG
(never from a request), and each pack lives in its own table named biz_<id>.
"""
import csv
import io
import random
import re
from datetime import date, timedelta

from app.services.db import fetch_all, get_cursor

MAX_ROWS = 200_000
MAX_CSV_BYTES = 8_000_000


class PackError(Exception):
    pass


def _p(id_, industry, dept, title, about, dims, nums, kpis, trend, breakdowns, rows=600, dates=()):
    return {"dates": list(dates), "custom": False, "id": id_, "industry": industry, "dept": dept, "title": title, "about": about, "dims": dims,
            "nums": nums, "kpis": kpis, "trend": trend, "breakdowns": breakdowns, "rows": rows}


# dims: name -> values.  nums: name -> (lo, hi, decimals).  kpis: (label, SQL, unit, direction)
CATALOG: list[dict] = [
    _p("snf-admissions", "Skilled nursing", "Admissions", "Admissions and census",
       "Referrals in, admissions, discharges and bed fill for a facility.",
       {"referral_source": ["Hospital", "Physician", "Family", "Hospice", "Other"], "payer": ["Medicare", "Medicaid", "Private", "VA"],
        "outcome": ["Admitted", "Admitted", "Admitted", "Declined", "Pending"]},
       {"days_to_decision": (0, 9, 0), "daily_rate": (240, 520, 2), "length_of_stay": (3, 90, 0)},
       [("Referrals", "COUNT(*)", "count", "higher"),
        ("Admit rate", "100.0*SUM(CASE WHEN outcome='Admitted' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "higher"),
        ("Avg days to decision", "AVG(days_to_decision)", "num", "lower"),
        ("Avg daily rate", "AVG(daily_rate)", "usd", "higher")],
       ("Referrals", "COUNT(*)"), ["referral_source", "payer", "outcome"]),
    _p("snf-staffing", "Skilled nursing", "Staffing (HR)", "Staffing and overtime",
       "Hours worked, overtime and agency use by role and shift.",
       {"role": ["RN", "LPN", "CNA", "Dietary", "Housekeeping"], "shift": ["Day", "Evening", "Night"], "employment": ["Employee", "Employee", "Agency"]},
       {"hours": (4, 12, 1), "overtime_hours": (0, 4, 1), "hourly_cost": (16, 62, 2)},
       [("Hours worked", "SUM(hours)", "num", "higher"),
        ("Overtime share", "100.0*SUM(overtime_hours)/NULLIF(SUM(hours),0)", "pct", "lower"),
        ("Agency share", "100.0*SUM(CASE WHEN employment='Agency' THEN hours ELSE 0 END)/NULLIF(SUM(hours),0)", "pct", "lower"),
        ("Labor cost", "SUM(hours*hourly_cost)", "usd", "lower")],
       ("Labor cost", "SUM(hours*hourly_cost)"), ["role", "shift", "employment"]),
    _p("snf-billing", "Skilled nursing", "Finance", "Billing and collections",
       "Billed vs collected by payer, with denials.",
       {"payer": ["Medicare", "Medicaid", "Private", "VA"], "status": ["Paid", "Paid", "Paid", "Denied", "Open"]},
       {"billed": (800, 9000, 2), "collected": (0, 8000, 2), "days_to_pay": (5, 90, 0)},
       [("Billed", "SUM(billed)", "usd", "higher"), ("Collected", "SUM(collected)", "usd", "higher"),
        ("Collection rate", "100.0*SUM(collected)/NULLIF(SUM(billed),0)", "pct", "higher"),
        ("Denial rate", "100.0*SUM(CASE WHEN status='Denied' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "lower")],
       ("Billed", "SUM(billed)"), ["payer", "status"]),
    _p("retail-sales", "Retail", "Sales", "Store sales",
       "Revenue, orders and basket size by store and category.",
       {"store": ["Downtown", "Mall", "Online", "Outlet"], "category": ["Apparel", "Home", "Electronics", "Beauty", "Grocery"], "channel": ["In store", "In store", "Web", "App"]},
       {"orders": (1, 40, 0), "revenue": (20, 2400, 2), "cost": (10, 1700, 2)},
       [("Revenue", "SUM(revenue)", "usd", "higher"), ("Orders", "SUM(orders)", "count", "higher"),
        ("Avg order value", "SUM(revenue)/NULLIF(SUM(orders),0)", "usd", "higher"),
        ("Gross margin", "100.0*(SUM(revenue)-SUM(cost))/NULLIF(SUM(revenue),0)", "pct", "higher")],
       ("Revenue", "SUM(revenue)"), ["store", "category", "channel"]),
    _p("retail-inventory", "Retail", "Operations", "Inventory health",
       "Stock levels, stock-outs and reorder pressure by category.",
       {"category": ["Apparel", "Home", "Electronics", "Beauty", "Grocery"], "warehouse": ["East", "West", "Central"], "flag": ["OK", "OK", "OK", "Low", "Out of stock"]},
       {"on_hand": (0, 500, 0), "units_sold": (0, 120, 0), "unit_cost": (2, 180, 2)},
       [("Stock value", "SUM(on_hand*unit_cost)", "usd", "higher"), ("Units sold", "SUM(units_sold)", "count", "higher"),
        ("Stock-out rate", "100.0*SUM(CASE WHEN flag='Out of stock' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "lower"),
        ("Low or out", "100.0*SUM(CASE WHEN flag<>'OK' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "lower")],
       ("Units sold", "SUM(units_sold)"), ["category", "warehouse", "flag"]),
    _p("retail-marketing", "Retail", "Marketing", "Campaign performance",
       "Spend, clicks and revenue per campaign and channel.",
       {"channel": ["Email", "Search", "Social", "Display"], "campaign": ["Spring", "Summer", "Back to school", "Holiday", "Always on"]},
       {"spend": (20, 900, 2), "clicks": (30, 4000, 0), "conversions": (0, 120, 0), "revenue": (0, 6000, 2)},
       [("Spend", "SUM(spend)", "usd", "lower"), ("Revenue", "SUM(revenue)", "usd", "higher"),
        ("ROAS", "SUM(revenue)/NULLIF(SUM(spend),0)", "num", "higher"),
        ("Cost per conversion", "SUM(spend)/NULLIF(SUM(conversions),0)", "usd", "lower")],
       ("Revenue", "SUM(revenue)"), ["channel", "campaign"]),
    _p("logi-ops", "Logistics and delivery", "Operations", "Deliveries and on-time rate",
       "Stops, on-time delivery and late reasons by route and driver.",
       {"route": ["North", "South", "East", "West", "Metro"], "driver": ["A", "B", "C", "D", "E", "F"], "result": ["On time", "On time", "On time", "Late", "Failed"]},
       {"stops": (5, 60, 0), "miles": (10, 160, 1), "minutes": (60, 540, 0)},
       [("Stops", "SUM(stops)", "count", "higher"),
        ("On-time rate", "100.0*SUM(CASE WHEN result='On time' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "higher"),
        ("Stops per hour", "60.0*SUM(stops)/NULLIF(SUM(minutes),0)", "num", "higher"),
        ("Miles per stop", "SUM(miles)/NULLIF(SUM(stops),0)", "num", "lower")],
       ("Stops", "SUM(stops)"), ["route", "driver", "result"]),
    _p("logi-finance", "Logistics and delivery", "Finance", "Earnings, expenses and mileage",
       "Per-shift earnings, costs and miles: net, hourly and per-mile. Works for a driver or a small fleet.",
       {"platform": ["Instacart", "DoorDash", "Uber Eats", "Direct"], "vehicle": ["Car A", "Car B"]},
       {"earnings": (20, 220, 2), "tips": (0, 80, 2), "fuel": (3, 40, 2), "other_costs": (0, 15, 2), "miles": (10, 140, 1), "hours": (1, 9, 1)},
       [("Gross", "SUM(earnings+tips)", "usd", "higher"), ("Costs", "SUM(fuel+other_costs)", "usd", "lower"),
        ("Net", "SUM(earnings+tips-fuel-other_costs)", "usd", "higher"),
        ("Net per hour", "SUM(earnings+tips-fuel-other_costs)/NULLIF(SUM(hours),0)", "usd", "higher"),
        ("Net per mile", "SUM(earnings+tips-fuel-other_costs)/NULLIF(SUM(miles),0)", "usd", "higher")],
       ("Net", "SUM(earnings+tips-fuel-other_costs)"), ["platform", "vehicle"]),
    _p("logi-support", "Logistics and delivery", "Support", "Customer issues",
       "Tickets by type, with resolution time and satisfaction.",
       {"type": ["Late", "Damaged", "Missing", "Billing", "Other"], "priority": ["Low", "Normal", "Normal", "High"], "state": ["Resolved", "Resolved", "Resolved", "Open"]},
       {"hours_to_resolve": (1, 96, 1), "csat": (1, 5, 0)},
       [("Tickets", "COUNT(*)", "count", "lower"), ("Avg hours to resolve", "AVG(hours_to_resolve)", "num", "lower"),
        ("Satisfaction (1-5)", "AVG(csat)", "num", "higher"),
        ("Still open", "100.0*SUM(CASE WHEN state='Open' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "lower")],
       ("Tickets", "COUNT(*)"), ["type", "priority", "state"]),
    _p("saas-sales", "Software (SaaS)", "Sales", "Pipeline and wins",
       "Deals by stage and source, win rate and average deal size.",
       {"source": ["Inbound", "Outbound", "Partner", "Referral"], "stage": ["Won", "Lost", "Lost", "Open", "Open"], "segment": ["SMB", "Mid-market", "Enterprise"]},
       {"deal_value": (500, 60000, 0), "days_open": (1, 120, 0)},
       [("Deals", "COUNT(*)", "count", "higher"),
        ("Win rate", "100.0*SUM(CASE WHEN stage='Won' THEN 1 ELSE 0 END)/NULLIF(SUM(CASE WHEN stage IN ('Won','Lost') THEN 1 ELSE 0 END),0)", "pct", "higher"),
        ("Won value", "SUM(CASE WHEN stage='Won' THEN deal_value ELSE 0 END)", "usd", "higher"),
        ("Open pipeline", "SUM(CASE WHEN stage='Open' THEN deal_value ELSE 0 END)", "usd", "higher")],
       ("Deal value", "SUM(deal_value)"), ["source", "stage", "segment"]),
    _p("saas-finance", "Software (SaaS)", "Finance", "Recurring revenue",
       "MRR, new, expansion and churn by plan.",
       {"plan": ["Starter", "Pro", "Business", "Enterprise"], "region": ["NA", "EU", "APAC"]},
       {"mrr": (20, 4000, 2), "new_mrr": (0, 800, 2), "churned_mrr": (0, 500, 2)},
       [("MRR", "SUM(mrr)", "usd", "higher"), ("New MRR", "SUM(new_mrr)", "usd", "higher"),
        ("Churned MRR", "SUM(churned_mrr)", "usd", "lower"),
        ("Net new", "SUM(new_mrr-churned_mrr)", "usd", "higher")],
       ("MRR", "SUM(mrr)"), ["plan", "region"]),
    _p("saas-support", "Software (SaaS)", "Support", "Support queue",
       "Tickets, first response and satisfaction by product area.",
       {"area": ["Billing", "Login", "Reports", "API", "Integrations"], "priority": ["Low", "Normal", "Normal", "High", "Urgent"], "state": ["Resolved", "Resolved", "Resolved", "Open"]},
       {"first_response_min": (2, 600, 0), "hours_to_resolve": (1, 120, 1), "csat": (1, 5, 0)},
       [("Tickets", "COUNT(*)", "count", "lower"), ("Avg first response (min)", "AVG(first_response_min)", "num", "lower"),
        ("Avg hours to resolve", "AVG(hours_to_resolve)", "num", "lower"), ("Satisfaction (1-5)", "AVG(csat)", "num", "higher")],
       ("Tickets", "COUNT(*)"), ["area", "priority", "state"]),
    _p("prof-hr", "Professional services", "HR", "Hiring pipeline",
       "Candidates by role and stage, time to hire and source.",
       {"role": ["Analyst", "Engineer", "Designer", "Sales", "Operations"], "stage": ["Applied", "Screen", "Interview", "Offer", "Hired", "Rejected"], "source": ["Job board", "Referral", "Recruiter", "Direct"]},
       {"days_in_process": (1, 60, 0), "offer_amount": (0, 140000, 0)},
       [("Candidates", "COUNT(*)", "count", "higher"),
        ("Hired", "SUM(CASE WHEN stage='Hired' THEN 1 ELSE 0 END)", "count", "higher"),
        ("Avg days in process", "AVG(days_in_process)", "num", "lower"),
        ("Rejection rate", "100.0*SUM(CASE WHEN stage='Rejected' THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "lower")],
       ("Candidates", "COUNT(*)"), ["role", "stage", "source"]),
    _p("prof-finance", "Professional services", "Finance", "Billable hours and invoices",
       "Hours billed, utilization, invoices and days to get paid.",
       {"client": ["Acme", "Birch", "Cedar", "Delta", "Ember"], "service": ["Consulting", "Audit", "Advisory", "Training"], "invoice": ["Paid", "Paid", "Paid", "Overdue", "Sent"]},
       {"billable_hours": (1, 12, 1), "available_hours": (6, 10, 1), "rate": (80, 260, 2)},
       [("Billed", "SUM(billable_hours*rate)", "usd", "higher"),
        ("Utilization", "100.0*SUM(billable_hours)/NULLIF(SUM(available_hours),0)", "pct", "higher"),
        ("Avg rate", "SUM(billable_hours*rate)/NULLIF(SUM(billable_hours),0)", "usd", "higher"),
        ("Overdue share", "100.0*SUM(CASE WHEN invoice='Overdue' THEN billable_hours*rate ELSE 0 END)/NULLIF(SUM(billable_hours*rate),0)", "pct", "lower")],
       ("Billed", "SUM(billable_hours*rate)"), ["client", "service", "invoice"]),
    _p("job-search", "Personal", "Job search", "Job-search pipeline",
       "Applications by source and stage, response and interview rates, and the follow-ups that are due.",
       {"company": ["Acme Health", "Birch Analytics", "Cedar Logistics", "Delta Care", "Ember Retail", "Fjord Systems", "Granite Labs", "Harbor Co"],
        "role_type": ["BI developer", "Data analyst", "Systems architect", "Operations analyst"],
        "source": ["LinkedIn", "Indeed", "Referral", "Company site", "Recruiter"],
        "stage": ["Applied", "Applied", "Applied", "Screen", "Interview", "Offer", "Rejected", "Ghosted"]},
       {"days_to_response": (0, 30, 0), "interviews": (0, 4, 0)},
       [("Applications", "COUNT(*)", "count", "higher"),
        ("Response rate", "100.0*SUM(CASE WHEN stage NOT IN ('Applied','Ghosted') THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "higher"),
        ("Interview rate", "100.0*SUM(CASE WHEN stage IN ('Interview','Offer') THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "higher"),
        ("Offers", "SUM(CASE WHEN stage='Offer' THEN 1 ELSE 0 END)", "count", "higher"),
        ("Avg days to response", "AVG(CASE WHEN stage NOT IN ('Applied','Ghosted') THEN days_to_response END)", "num", "lower")],
       ("Applications", "COUNT(*)"), ["source", "stage", "role_type"], rows=60, dates=["follow_up"]),
    _p("repair-jobs", "Repair and IT services", "Service jobs", "Repair and service jobs",
       "Every repair, install and support job: what broke, what it cost, how long it took, what you earned, and which customers need a check-in call.",
       {"device_type": ["Laptop", "Desktop", "Phone", "Tablet", "Router / network", "Printer", "Game console", "Car electronics", "EV charger", "Small appliance"],
        "fault": ["Won't power on", "Cracked screen", "Battery", "Overheating", "Slow or malware", "No network", "Water damage", "Wiring or short", "Data recovery", "Software setup"],
        "service": ["Bench repair", "On-site IT", "Remote support", "Diagnostic only", "Data cleanup"],
        "status": ["Completed", "Completed", "Completed", "Completed", "In progress", "Waiting parts", "Waiting customer", "Unrepairable", "Warranty return"]},
       {"labor_hours": (0.25, 6, 2), "parts_cost": (0, 120, 2), "price": (60, 500, 2), "days_to_fix": (0, 14, 0)},
       [("Jobs", "COUNT(*)", "count", "higher"), ("Revenue", "SUM(price)", "usd", "higher"),
        ("Profit after parts", "SUM(price - parts_cost)", "usd", "higher"),
        ("Profit per labor hour", "SUM(price - parts_cost)/NULLIF(SUM(labor_hours),0)", "usd", "higher"),
        ("Avg days to fix", "AVG(days_to_fix)", "num", "lower"),
        ("Unfixed or returned", "100.0*SUM(CASE WHEN status IN ('Unrepairable','Warranty return') THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "lower")],
       ("Revenue", "SUM(price)"), ["device_type", "fault", "service", "status"], dates=["follow_up"]),
    _p("repair-parts", "Repair and IT services", "Parts and stock", "Parts and stock",
       "What you use and what you hold: parts spend, units used, unit cost by supplier, and the lines that have fallen to their reorder point.",
       {"part": ["Laptop battery", "Screen", "SSD", "RAM stick", "Charger / PSU", "Network cable", "Router", "Fuse / relay", "Connector kit", "Thermal paste"],
        "supplier": ["Supplier A", "Supplier B", "Supplier C", "Local shop"],
        "movement": ["Used on a job", "Used on a job", "Used on a job", "Restocked", "Returned to supplier"]},
       {"qty": (1, 10, 0), "unit_cost": (2, 90, 2), "on_hand": (0, 25, 0), "reorder_point": (2, 6, 0)},
       [("Parts spend", "SUM(qty*unit_cost)", "usd", "lower"), ("Units moved", "SUM(qty)", "count", "higher"),
        ("Avg unit cost", "AVG(unit_cost)", "usd", "lower"),
        ("Low-stock share", "100.0*SUM(CASE WHEN on_hand <= reorder_point THEN 1 ELSE 0 END)/NULLIF(COUNT(*),0)", "pct", "lower")],
       ("Spend", "SUM(qty*unit_cost)"), ["part", "supplier", "movement"]),
]
BY_ID = {p["id"]: p for p in CATALOG}


def custom_defs() -> list[dict]:
    from app.services import state, workspaces
    return list(state.setting_get(workspaces.active(), "biz_custom", []) or [])


def all_packs() -> list[dict]:
    return CATALOG + custom_defs()


def find(pid: str) -> dict | None:
    return BY_ID.get(pid) or next((p for p in custom_defs() if p["id"] == pid), None)


def _get(pid: str) -> dict:
    p = find(pid)
    if not p:
        raise PackError(f"No pack called '{pid}'.")
    return p


def _table(pid: str) -> str:
    return "biz_" + _get(pid)["id"].replace("-", "_")


def columns(p: dict) -> list[tuple[str, str]]:
    return [("record_date", "DATE")] + [(d, "VARCHAR") for d in p["dims"]] + [(n, "DOUBLE") for n in p["nums"]] + [(d, "DATE") for d in p.get("dates", [])]


def _create(cur, p: dict) -> None:
    cols = ", ".join(f"{n} {t}" for n, t in columns(p))
    cur.execute(f"CREATE TABLE IF NOT EXISTS {_table(p['id'])} ({cols})")


def installed(pid: str) -> int | None:
    t = _table(pid)
    with get_cursor() as cur:
        if not cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = ?", [t]).fetchone()[0]:
            return None
        return int(cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])


def catalog() -> list[dict]:
    return [{"id": p["id"], "industry": p["industry"], "dept": p["dept"], "title": p["title"], "about": p["about"],
             "rows": installed(p["id"]), "columns": [n for n, _ in columns(p)], "custom": bool(p.get("custom")),
             "dates": p.get("dates", []), "can_sample": not p.get("custom")} for p in all_packs()]


def _sample_rows(p: dict, today: date) -> list[list]:
    rnd = random.Random(p["id"])
    out = []
    n = p["rows"]
    offsets = sorted((int(rnd.random() ** 0.8 * 120) for _ in range(n)), reverse=True)  # uneven daily volume
    for off in offsets:
        day = today - timedelta(days=off)
        row: list = [day]
        for vals in p["dims"].values():
            row.append(rnd.choice(vals))
        # a mild weekly rhythm so trends are not flat noise
        k = 1.0 + 0.25 * ((day.weekday() >= 4) - (day.weekday() == 1))
        for lo, hi, dec in p["nums"].values():
            v = (lo + (hi - lo) * rnd.random() ** 1.3) * k
            v = min(v, hi * 1.25)
            row.append(round(v, dec) if dec else float(round(v)))
        for _d in p.get("dates", []):
            row.append(None if rnd.random() < 0.2 else day + timedelta(days=rnd.randint(2, 14)))
        out.append(row)
    return out


def _insert(cur, p: dict, rows: list[list]) -> None:
    cols = [n for n, _ in columns(p)]
    import pandas as pd  # bulk insert: DuckDB's row-by-row executemany is ~100x slower
    df = pd.DataFrame(rows, columns=cols)
    cur.register("_pack_rows", df)
    try:
        cur.execute(f"INSERT INTO {_table(p['id'])} ({', '.join(cols)}) SELECT {', '.join(cols)} FROM _pack_rows")
    finally:
        cur.unregister("_pack_rows")


def _practice_only() -> None:
    from app.services import workspaces
    if workspaces.active() != "practice":
        raise PackError("Sample data is for the Practice workspace only, so made-up rows never mix with your real data. Import your CSV instead.")


def install_sample(pid: str) -> dict:
    p = _get(pid)
    if p.get("custom"):
        raise PackError("Sample data only exists for the built-in dashboards. Import or add your own rows.")
    _practice_only()
    with get_cursor() as cur:
        _create(cur, p)
        cur.execute(f"DELETE FROM {_table(pid)}")
        _insert(cur, p, _sample_rows(p, date.today()))
    return {"rows": installed(pid)}


def clear(pid: str) -> dict:
    _get(pid)
    with get_cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {_table(pid)}")
    return {"cleared": pid}


def template_csv(pid: str) -> str:
    p = _get(pid)
    names = [n for n, _ in columns(p)]
    sample = _sample_rows(p, date.today())[:3]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(names)
    w.writerows(sample)
    return buf.getvalue()


def _parse_csv(p: dict, text: str) -> tuple[list[list], list[str]]:
    """Check every line against the pack's columns. Returns the valid rows and up to 8 notes about skipped lines. Writes nothing."""
    if len(text.encode("utf-8", "ignore")) > MAX_CSV_BYTES:
        raise PackError("That file is too large (8 MB max).")
    rd = csv.DictReader(io.StringIO(text.lstrip("\ufeff")))
    want = ["record_date"] + list(p["dims"]) + list(p["nums"])
    got = [(h or "").strip().lower() for h in (rd.fieldnames or [])]
    missing = [c for c in want if c not in got]
    if missing:
        raise PackError("Missing columns: " + ", ".join(missing) + ". Download the template for the exact header.")
    rows, errors, skipped = [], [], 0
    for ln, raw in enumerate(rd, start=2):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in raw.items()}
        try:
            d = date.fromisoformat(r["record_date"][:10])
            vals: list = [d] + [r[x] for x in p["dims"]]
            for x in p["nums"]:
                vals.append(float(r[x].replace(",", "").replace("$", "")))
            if any(v != v or v in (float("inf"), float("-inf")) for v in vals[1 + len(p["dims"]):]):
                raise ValueError("number is not finite")
            for x in p.get("dates", []):
                vals.append(date.fromisoformat(r[x][:10]) if r.get(x) else None)
        except (ValueError, KeyError) as e:
            skipped += 1
            if len(errors) < 8:
                errors.append(f"Line {ln}: {e}")
            continue
        rows.append(vals)
        if len(rows) > MAX_ROWS:
            raise PackError(f"Too many rows ({MAX_ROWS:,} max).")
    if not rows:
        raise PackError("No valid rows. " + " ".join(errors[:3]))
    _parse_csv.skipped = skipped  # type: ignore[attr-defined]
    return rows, errors


def import_csv(pid: str, text: str, replace: bool = False) -> dict:
    from app.services import state
    p = _get(pid)
    rows, errors = _parse_csv(p, text)
    with get_cursor() as cur:
        _create(cur, p)
        if replace:
            cur.execute(f"DELETE FROM {_table(pid)}")
        _insert(cur, p, rows)
    state.audit("biz_import", f"{pid}: {len(rows)} rows{' (replaced)' if replace else ''}")
    return {"imported": len(rows), "skipped_notes": errors, "rows": installed(pid)}


def _window_kpis(cur, p: dict, t: str, days: int) -> list[dict]:
    """The same KPI numbers the dashboard shows, computed on any table (used by the sandbox preview)."""
    mn, mx = cur.execute(f"SELECT MIN(record_date), MAX(record_date) FROM {t}").fetchone()
    if mx is None:
        return [{"label": k[0], "unit": k[2], "value": None} for k in p["kpis"]]
    where, par = ("record_date >= ? AND record_date <= ?", [mx - timedelta(days=days - 1), mx]) if days > 0 else ("TRUE", [])
    return [{"label": label, "unit": unit, "value": _fmt_num(cur.execute(f"SELECT {sql} FROM {t} WHERE {where}", par).fetchone()[0])} for label, sql, unit, _ in p["kpis"]]


def _before_kpis(p: dict, pid: str, days: int) -> list[dict]:
    with get_cursor() as cur:
        return _window_kpis(cur, p, _table(pid), days)


def preview_import(pid: str, text: str, replace: bool = False, days: int = 30) -> dict:
    """SANDBOX: try an import on a throw-away in-memory copy and report what would happen. Your real data is not touched."""
    import duckdb
    import pandas as pd
    p = _get(pid)
    rows, errors = _parse_csv(p, text)
    skipped = getattr(_parse_csv, "skipped", len(errors))
    cols = [n for n, _ in columns(p)]
    t = "sandbox_" + p["id"].replace("-", "_")
    current = installed(pid) or 0
    con = duckdb.connect(":memory:")
    try:
        con.execute(f"CREATE TABLE {t} ({', '.join(f'{n} {ty}' for n, ty in columns(p))})")
        old_df = None
        if current:
            with get_cursor() as cur:
                old_df = cur.execute(f"SELECT {', '.join(cols)} FROM {_table(pid)}").df()
        new_df = pd.DataFrame(rows, columns=cols)
        if old_df is not None and not replace:
            con.register("_old", old_df)
            con.execute(f"INSERT INTO {t} SELECT * FROM _old")
            con.unregister("_old")
        con.register("_new", new_df)
        con.execute(f"INSERT INTO {t} SELECT * FROM _new")
        con.unregister("_new")
        after = _window_kpis(con, p, t, days)
        total_after = int(con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
        before = _before_kpis(p, pid, days) if current else [{"label": k[0], "unit": k[2], "value": None} for k in p["kpis"]]
        dups = 0
        if old_df is not None and len(old_df):
            key = ["record_date"] + list(p["dims"]) + list(p["nums"])
            merged = new_df[key].astype(str).merge(old_df[key].astype(str).drop_duplicates(), on=key, how="inner")
            dups = int(len(merged))
    finally:
        con.close()
    kpis = []
    for b, a in zip(before, after):
        ch = None if b["value"] in (None, 0) or a["value"] is None else round(100.0 * (a["value"] - b["value"]) / abs(b["value"]), 1)
        kpis.append({"label": a["label"], "unit": a["unit"], "before": b["value"], "after": a["value"], "change_pct": ch})
    dmin, dmax = min(r[0] for r in rows), max(r[0] for r in rows)
    warnings = []
    if replace and current:
        warnings.append(f"This replaces {current:,} existing rows with {len(rows):,}." + (" You are removing more rows than you are adding." if len(rows) < current else ""))
    if skipped and skipped > 0.2 * (skipped + len(rows)):
        warnings.append(f"{skipped:,} lines would be skipped, more than 20% of the file. Check the format.")
    if dups:
        warnings.append(f"{dups:,} new rows are exact copies of rows already loaded. Importing again would double count them." + ("" if replace else " Tick 'Replace existing rows' if this is the same data."))
    if dmax > date.today() + timedelta(days=1):
        warnings.append(f"Some dates are in the future (latest {dmax}).")
    big = [k for k in kpis if k["change_pct"] is not None and abs(k["change_pct"]) >= 50]
    if big:
        warnings.append("These numbers would move by 50% or more: " + ", ".join(f"{k['label']} {k['change_pct']:+.1f}%" for k in big) + ". Confirm that is expected.")
    return {"ok": True, "rows_valid": len(rows), "rows_skipped": skipped, "skipped_notes": errors, "current_rows": current, "resulting_rows": total_after, "replace": replace,
            "new_dates": [str(dmin), str(dmax)], "duplicates": dups, "warnings": warnings, "kpis": kpis, "window_days": days,
            "sample": [dict(zip(cols, [str(v) if v is not None else "" for v in r])) for r in rows[:5]],
            "verdict": "Safe to apply." if not warnings else "Review the warnings before you apply."}


def _fmt_num(v):
    return None if v is None else round(float(v), 2)


def dashboard(pid: str, days: int = 30) -> dict:
    p = _get(pid)
    t = _table(pid)
    if installed(pid) is None:
        raise PackError("No data in this pack yet. Load sample data or import a CSV.")
    with get_cursor() as cur:
        mn, mx = cur.execute(f"SELECT MIN(record_date), MAX(record_date) FROM {t}").fetchone()
        if mx is None:
            raise PackError("This pack has no rows.")
        if days > 0:
            start = mx - timedelta(days=days - 1)
            pend = start - timedelta(days=1)
            pstart = pend - timedelta(days=days - 1)
            where, par = "record_date >= ? AND record_date <= ?", [start, mx]
        else:
            where, par, pstart, pend = "TRUE", [], None, None
        kpis = []
        for label, sql, unit, direction in p["kpis"]:
            v = cur.execute(f"SELECT {sql} FROM {t} WHERE {where}", par).fetchone()[0]
            prev = None
            if pstart and mn <= pstart:  # only compare when the earlier window is fully covered by the data
                prev = cur.execute(f"SELECT {sql} FROM {t} WHERE record_date >= ? AND record_date <= ?", [pstart, pend]).fetchone()[0]
            change = None if v is None or prev in (None, 0) else round(100.0 * (float(v) - float(prev)) / abs(float(prev)), 1)
            good = None if change is None else (change >= 0) == (direction == "higher")
            kpis.append({"label": label, "unit": unit, "direction": direction, "value": _fmt_num(v),
                         "previous": _fmt_num(prev), "change_pct": change, "good": good})
        tl, tsql = p["trend"]
        trend = fetch_all(cur, f"SELECT CAST(record_date AS VARCHAR) AS day, {tsql} AS value FROM {t} WHERE {where} GROUP BY 1 ORDER BY 1", par)
        trend = [{"day": r["day"], "value": _fmt_num(r["value"])} for r in trend]
        breaks = []
        for dim in p["breakdowns"]:
            rows = fetch_all(cur, f"SELECT {dim} AS name, {tsql} AS value FROM {t} WHERE {where} GROUP BY 1 ORDER BY 2 DESC", par)
            breaks.append({"dim": dim, "rows": [{"name": r["name"], "value": _fmt_num(r["value"])} for r in rows]})
        n = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {where}", par).fetchone()[0]
    return {"id": pid, "title": p["title"], "industry": p["industry"], "dept": p["dept"], "days": days, "as_of": str(mx),
            "records": int(n), "kpis": kpis, "trend_label": tl, "trend": trend, "breakdowns": breaks}


def _plain(sql: str) -> str:
    """Turn a KPI's SQL into plain words (best effort); the exact SQL is always shown too."""
    t = " ".join(sql.split())
    for a, b in ((r"SUM\(([^()]+)\)", r"the total of \1"), (r"AVG\(([^()]+)\)", r"the average of \1"), (r"COUNT\(\*\)", "the number of records"), (r"COUNT\(DISTINCT ([^()]+)\)", r"the number of different \1"),
                 (r"MAX\(([^()]+)\)", r"the highest \1"), (r"MIN\(([^()]+)\)", r"the lowest \1"), (r"NULLIF\([^,]+, ?0\)", "that total"), (r"100\.0 ?\*", "as a percent:"), (r"100 ?\*", "as a percent:")):
        t = re.sub(a, b, t, flags=re.I)
    return t.replace("_", " ").replace(" / ", " divided by ").replace("*", " times ").replace(" - ", " minus ")


def explain(pid: str, kpi: str, days: int = 30) -> dict:
    """Explain one number: what it measures, how it is calculated, how it moved, what moved it and its best and worst day. No AI, only your data."""
    p = _get(pid)
    row = next((k for k in p["kpis"] if k[0].lower() == kpi.lower()), None)
    if row is None:
        raise PackError("That number isn't on this dashboard.")
    label, sql, unit, direction = row
    t = _table(pid)
    d = dashboard(pid, days)
    k = next(x for x in d["kpis"] if x["label"] == label)
    with get_cursor() as cur:
        mn, mx = cur.execute(f"SELECT MIN(record_date), MAX(record_date) FROM {t}").fetchone()
        has_prev = days > 0 and k["previous"] is not None
        cur_where, cur_par = ("record_date >= ? AND record_date <= ?", [mx - timedelta(days=days - 1), mx]) if days > 0 else ("TRUE", [])
        movers = []
        if has_prev:
            start = mx - timedelta(days=days - 1)
            pend = start - timedelta(days=1)
            pstart = pend - timedelta(days=days - 1)
            for dim in p["breakdowns"]:
                a = {r["g"]: r["v"] for r in fetch_all(cur, f"SELECT {dim} AS g, {sql} AS v FROM {t} WHERE {cur_where} GROUP BY 1", cur_par)}
                b = {r["g"]: r["v"] for r in fetch_all(cur, f"SELECT {dim} AS g, {sql} AS v FROM {t} WHERE record_date >= ? AND record_date <= ? GROUP BY 1", [pstart, pend])}
                for g in set(a) | set(b):
                    va, vb = float(a.get(g) or 0), float(b.get(g) or 0)
                    movers.append({"dim": dim, "name": g, "now": round(va, 2), "before": round(vb, 2), "change": round(va - vb, 2)})
            movers.sort(key=lambda m: -abs(m["change"]))
        daily = fetch_all(cur, f"SELECT CAST(record_date AS VARCHAR) AS day, {sql} AS v FROM {t} WHERE {cur_where} GROUP BY 1 HAVING {sql} IS NOT NULL ORDER BY 1", cur_par)
    hi = max(daily, key=lambda r: r["v"]) if daily else None
    lo = min(daily, key=lambda r: r["v"]) if daily else None
    goodword = "higher is better" if direction == "higher" else "lower is better"
    parts = [f"{label} is {_fmt_num(k['value'])} {'USD' if unit == 'usd' else ('%' if unit == 'pct' else '')}".strip() + f" for the {'last ' + str(days) + ' days' if days else 'whole data set'} ending {d['as_of']}."]
    if k["change_pct"] is not None:
        parts.append(f"That is {k['change_pct']:+.1f}% against the previous {days} days ({_fmt_num(k['previous'])}), which is {'good' if k['good'] else 'worse'} because {goodword}.")
    elif days:
        parts.append("There is not a full earlier period in the data, so no comparison is possible yet.")
    top = [m for m in movers if m["change"] != 0][:3]
    if top:
        parts.append("Biggest movers: " + "; ".join(f"{m['name']} ({m['dim'].replace('_', ' ')}) {m['change']:+,.2f}" for m in top) + ".")
    return {"id": pid, "kpi": label, "unit": unit, "direction": direction, "goodword": goodword, "value": k["value"], "previous": k["previous"], "change_pct": k["change_pct"], "good": k["good"],
            "records": d["records"], "as_of": d["as_of"], "days": days, "formula": " ".join(sql.split()), "in_words": _plain(sql), "best_day": hi, "worst_day": lo,
            "movers": movers[:6], "summary": " ".join(parts)}


ATTENTION_PCT = 10.0


def overview(days: int = 30) -> dict:
    """Roll up every pack that has data: per-pack headline KPIs plus a list of KPIs moving the wrong way."""
    cards, attention, good, bad = [], [], 0, 0
    for p in all_packs():
        if not installed(p["id"]):
            continue
        d = dashboard(p["id"], days)
        for k in d["kpis"]:
            if k["good"] is True:
                good += 1
            elif k["good"] is False:
                bad += 1
                if abs(k["change_pct"] or 0) >= ATTENTION_PCT:
                    attention.append({"pack": p["id"], "industry": p["industry"], "dept": p["dept"], "kpi": k["label"],
                                      "unit": k["unit"], "value": k["value"], "change_pct": k["change_pct"]})
        cards.append({"id": p["id"], "industry": p["industry"], "dept": p["dept"], "title": p["title"], "records": d["records"],
                      "as_of": d["as_of"], "kpis": d["kpis"][:3], "trend_label": d["trend_label"], "trend": d["trend"]})
    attention.sort(key=lambda a: -abs(a["change_pct"] or 0))
    return {"days": days, "packs": len(cards), "available": len(all_packs()), "improving": good, "worsening": bad,
            "attention": attention[:12], "cards": cards}


def install_all_samples() -> dict:
    _practice_only()
    for p in CATALOG:
        install_sample(p["id"])
    return {"installed": len(CATALOG)}


def wrong_way(days: int = 30, min_pct: float = 15.0) -> list[dict]:
    """Every KPI on every loaded dashboard that moved the wrong way by at least min_pct versus the previous period."""
    out = []
    for p in all_packs():
        if not installed(p["id"]):
            continue
        try:
            d = dashboard(p["id"], days)
        except PackError:
            continue
        for k in d["kpis"]:
            if k["good"] is False and k["change_pct"] is not None and abs(k["change_pct"]) >= min_pct:
                out.append({"pack": p["id"], "industry": p["industry"], "dept": p["dept"], "kpi": k["label"], "unit": k["unit"],
                            "value": k["value"], "previous": k["previous"], "change_pct": k["change_pct"], "as_of": d["as_of"]})
    return sorted(out, key=lambda a: -abs(a["change_pct"]))


# ---------------------------------------------------------------- quick add
def form_spec(pid: str) -> dict:
    """What a quick-add form needs: each field's type, a default, and the values already in use (so it can offer them)."""
    p = _get(pid)
    seen: dict[str, list[str]] = {d: list(dict.fromkeys(v)) for d, v in p["dims"].items()} if isinstance(p["dims"], dict) else {d: [] for d in p["dims"]}
    if installed(pid) is not None:
        with get_cursor() as cur:
            for d in p["dims"]:
                rows = cur.execute(f"SELECT {d}, COUNT(*) c FROM {_table(pid)} WHERE {d} IS NOT NULL GROUP BY 1 ORDER BY c DESC LIMIT 40").fetchall()
                seen[d] = list(dict.fromkeys([r[0] for r in rows] + seen.get(d, [])))[:40]
    fields = [{"name": "record_date", "type": "date", "default": date.today().isoformat(), "required": True}]
    fields += [{"name": d, "type": "text", "options": seen.get(d, []), "required": True} for d in p["dims"]]
    fields += [{"name": n, "type": "number", "required": True} for n in p["nums"]]
    fields += [{"name": d, "type": "date", "required": False} for d in p.get("dates", [])]
    return {"id": pid, "title": p["title"], "fields": fields}


def add_row(pid: str, values: dict) -> dict:
    p = _get(pid)
    if installed(pid) is not None and installed(pid) >= MAX_ROWS:
        raise PackError(f"This dashboard already has {MAX_ROWS:,} rows.")
    v = {str(k).lower(): x for k, x in (values or {}).items()}
    try:
        d = date.fromisoformat(str(v.get("record_date") or date.today().isoformat())[:10])
    except ValueError:
        raise PackError("record_date must look like 2026-10-13.") from None
    if d > date.today() + timedelta(days=366) or d < date(2000, 1, 1):
        raise PackError("That date looks wrong.")
    row: list = [d]
    for x in p["dims"]:
        t = str(v.get(x, "")).strip()
        if not t:
            raise PackError(f"'{x}' can't be empty.")
        if len(t) > 80:
            raise PackError(f"'{x}' is too long (80 characters max).")
        row.append(t)
    for x in p["nums"]:
        try:
            n = float(str(v.get(x, "")).replace(",", "").replace("$", ""))
        except ValueError:
            raise PackError(f"'{x}' must be a number.") from None
        if n != n or n in (float("inf"), float("-inf")) or abs(n) > 1e12:
            raise PackError(f"'{x}' must be a normal number.")
        row.append(n)
    for x in p.get("dates", []):
        t = str(v.get(x) or "").strip()
        try:
            row.append(date.fromisoformat(t[:10]) if t else None)
        except ValueError:
            raise PackError(f"'{x}' must look like 2026-10-13.") from None
    with get_cursor() as cur:
        _create(cur, p)
        _insert(cur, p, [row])
    return {"added": 1, "rows": installed(pid)}


def browse(pid: str, q: str = "", sort: str = "record_date", direction: str = "desc", limit: int = 50, offset: int = 0) -> dict:
    """Data browser: search, sort and page through the rows behind one dashboard. Columns come from the catalog only."""
    p = _get(pid)
    cols = [c for c, _ in columns(p)]
    if installed(pid) is None:
        return {"columns": cols, "rows": [], "total": 0, "matched": 0, "limit": limit, "offset": 0}
    if sort not in cols:
        sort = "record_date"
    d = "ASC" if str(direction).lower() == "asc" else "DESC"
    limit, offset = max(1, min(int(limit), 200)), max(0, int(offset))
    where, args = "", []
    q = (q or "").strip()[:80]
    if q:
        where = "WHERE " + " OR ".join(f"CAST({c} AS VARCHAR) ILIKE ?" for c in cols)
        args = [f"%{q}%"] * len(cols)
    t = _table(pid)
    with get_cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        matched = cur.execute(f"SELECT COUNT(*) FROM {t} {where}", args).fetchone()[0]
        rows = cur.execute(f"SELECT rowid, {', '.join(cols)} FROM {t} {where} ORDER BY {sort} {d}, rowid LIMIT {limit} OFFSET {offset}", args).fetchall()
    return {"columns": cols, "rows": [{"id": r[0], "values": [str(x) if x is not None and not isinstance(x, (int, float)) else x for x in r[1:]]} for r in rows],
            "total": total, "matched": matched, "limit": limit, "offset": offset}


def delete_row(pid: str, row_id: int) -> dict:
    _get(pid)
    if installed(pid) is None:
        raise PackError("There are no rows to delete.")
    with get_cursor() as cur:
        before = installed(pid)
        cur.execute(f"DELETE FROM {_table(pid)} WHERE rowid = ?", [int(row_id)])
    return {"deleted": before - installed(pid), "rows": installed(pid)}


# ---------------------------------------------------------------- dashboards built from any CSV
MAX_CUSTOM = 12
RESERVED = {"select", "from", "where", "group", "order", "by", "table", "user", "value", "values", "date", "time", "year", "month", "day", "end", "case", "when", "then",
            "else", "and", "or", "not", "null", "in", "is", "like", "limit", "offset", "join", "on", "as", "all", "any", "count", "sum", "avg", "min", "max", "name", "type",
            "key", "index", "set", "update", "delete", "insert", "create", "drop", "union", "having", "distinct", "primary", "default", "check", "column", "row", "rows", "desc", "asc"}
_MONEY = re.compile(r"(revenue|cost|price|amount|spend|earn|pay|fee|salary|income|sales|profit|tip|fuel|budget|expense|total_due|balance)", re.I)


def _ident(name: str, used: set[str]) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", str(name).strip().lower()).strip("_")[:40] or "col"
    if s[0].isdigit() or s in RESERVED:
        s = "c_" + s
    base, i = s, 2
    while s in used or s == "record_date":
        s, i = f"{base}_{i}", i + 1
    used.add(s)
    return s


def _label(ident: str) -> str:
    return ident.replace("_", " ").strip().capitalize()


def create_custom(csv_text: str, name: str, date_column: str | None = None, lower_is_better: list[str] | None = None) -> dict:
    """Make a new dashboard from any CSV: finds the date column, the numbers and the categories, builds KPIs and charts, loads the rows."""
    import pandas as pd
    from app.services import state, workspaces
    name = (name or "").strip()
    if not 2 <= len(name) <= 50:
        raise PackError("Give the dashboard a name (2 to 50 characters).")
    if len((csv_text or "").encode("utf-8", "ignore")) > MAX_CSV_BYTES:
        raise PackError("That file is too large (8 MB max).")
    existing = custom_defs()
    if len(existing) >= MAX_CUSTOM:
        raise PackError(f"You already have {MAX_CUSTOM} custom dashboards. Remove one first.")
    try:
        df = pd.read_csv(io.StringIO((csv_text or "").lstrip("﻿")), dtype=str, keep_default_na=False, nrows=MAX_ROWS + 1)
    except Exception as e:  # noqa: BLE001 - any parse failure is a user-facing message
        raise PackError(f"Couldn't read that as a CSV: {str(e)[:120]}") from None
    if len(df) < 5 or len(df.columns) < 2:
        raise PackError("Need a header row, at least 2 columns and 5 rows of data.")
    if len(df) > MAX_ROWS:
        raise PackError(f"Too many rows ({MAX_ROWS:,} max).")
    df.columns = [str(c).strip() for c in df.columns]
    notes: list[str] = []

    def num_share(s):
        x = pd.to_numeric(s.str.replace(r"[,$%\s]", "", regex=True).replace("", None), errors="coerce")
        return x.notna().sum() / max(1, (s != "").sum()), x

    def date_share(s):
        x = pd.to_datetime(s.replace("", None), errors="coerce", format="mixed")
        return x.notna().sum() / max(1, (s != "").sum()), x

    dcol = date_column if date_column in df.columns else None
    if date_column and not dcol:
        raise PackError(f"'{date_column}' isn't a column. Columns: {', '.join(df.columns)}.")
    if not dcol:
        for c in df.columns:
            if num_share(df[c])[0] > 0.9 and not re.search(r"date|day|time|when|period", c, re.I):
                continue
            if date_share(df[c])[0] >= 0.9:
                dcol = c
                break
    if not dcol:
        raise PackError("Couldn't find a date column. Say which column holds the date.")
    dates = date_share(df[dcol])[1]
    keep = dates.notna()
    if keep.sum() < 5:
        raise PackError("Fewer than 5 rows have a usable date.")
    if (~keep).sum():
        notes.append(f"Skipped {int((~keep).sum())} row(s) with no usable date.")
    df, dates = df[keep], dates[keep]
    used: set[str] = set()
    nums, dims, mapping = {}, {}, {}
    for c in df.columns:
        if c == dcol:
            continue
        share, vals = num_share(df[c])
        if share >= 0.9 and len(nums) < 8:
            ident = _ident(c, used)
            nums[ident], mapping[ident] = vals.fillna(0.0), c
        elif df[c].nunique() <= 30 and (df[c] != "").mean() > 0.5 and len(dims) < 4:
            ident = _ident(c, used)
            dims[ident], mapping[ident] = df[c].replace("", "(blank)").str.slice(0, 80), c
        else:
            notes.append(f"Left out '{c}': text with too many different values, or more columns than a dashboard can use.")
    if not nums and not dims:
        raise PackError("No numeric columns or category columns found to build a dashboard from.")
    lower = {_ident(x, set()) for x in (lower_is_better or [])}
    kpis = [("Records", "COUNT(*)", "count", "higher")]
    for n in nums:
        unit = "usd" if _MONEY.search(n) else "num"
        d = "lower" if n in lower or any(_ident(x, set()) == n for x in (lower_is_better or [])) else "higher"
        kpis += [(f"{_label(n)} (total)", f"SUM({n})", unit, d), (f"{_label(n)} (average)", f"AVG({n})", unit, d)]
    first = next(iter(nums), None)
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:24] or "dash"
    pid, k = f"custom-{base}", 2
    taken = {p["id"] for p in all_packs()}
    while pid in taken:
        pid, k = f"custom-{base}-{k}", k + 1
    spec = {"id": pid, "industry": "Custom", "dept": name, "title": name, "about": f"Built from your CSV ({len(df):,} rows). Date: {dcol}.",
            "dims": {d: [] for d in dims}, "nums": {n: (0, 0, 2) for n in nums}, "kpis": [list(x) for x in kpis],
            "trend": [(_label(first) + " (total)") if first else "Records", f"SUM({first})" if first else "COUNT(*)"],
            "breakdowns": list(dims)[:3], "rows": 0, "dates": [], "custom": True, "source_columns": mapping, "date_column": dcol}
    out = pd.DataFrame({"record_date": dates.dt.date})
    for d, v in dims.items():
        out[d] = v.values
    for n, v in nums.items():
        out[n] = v.values.astype(float)
    state.setting_set(workspaces.active(), "biz_custom", existing + [spec])      # saved first: the table helpers look the dashboard up by id
    try:
        with get_cursor() as cur:
            _create(cur, spec)
            _insert(cur, spec, out.values.tolist())
    except Exception:
        state.setting_set(workspaces.active(), "biz_custom", existing)
        raise
    state.audit("biz_custom_create", f"{pid}: {len(out)} rows")
    return {"id": pid, "rows": int(len(out)), "date_column": dcol, "measures": list(nums), "categories": list(dims), "notes": notes}


def delete_custom(pid: str) -> dict:
    from app.services import state, workspaces
    p = find(pid)
    if not p or not p.get("custom"):
        raise PackError("Only custom dashboards can be deleted.")
    clear(pid)
    state.setting_set(workspaces.active(), "biz_custom", [x for x in custom_defs() if x["id"] != pid])
    state.audit("biz_custom_delete", pid)
    return {"deleted": pid}
