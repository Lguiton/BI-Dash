"""Systems Design: turn a plain description of a system into a first design, with the arithmetic shown.

Everything here is rule-based and deterministic. It proposes a sensible starting design from the numbers you give; it does not measure anything,
and a design decision always stays yours. Prices are a rough, editable assumption table, not a quote. Nothing in this module touches your data."""
from __future__ import annotations

import math
import re

KINDS = {
    "booking": "Booking / appointments (a repair shop, salon, clinic)",
    "inventory": "Inventory / stock tracking",
    "dashboard": "Reporting dashboard for a business",
    "marketplace": "Marketplace with listings and orders",
    "chat": "Chat / messaging",
    "custom": "Something else (you name the main things it stores)",
}
NEEDS = ["auth", "payments", "files", "realtime", "reports", "email", "search"]
UPTIME = {"99": 0.99, "99.5": 0.995, "99.9": 0.999, "99.99": 0.9999}
PRICE = {"vps_small": (6, 30), "vps_mid": (24, 100), "vps_large": (48, 250), "db_base": 15, "db_per_gb": 0.115, "object_per_gb": 0.023, "backup_per_gb": 0.05, "egress_per_gb": 0.05, "monitor": 0, "email_provider": 10}


class DesignError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _num(v, name, lo, hi, default):
    if v in (None, ""):
        return default
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise DesignError(f"{name} must be a number.") from None
    if not lo <= x <= hi:
        raise DesignError(f"{name} must be between {lo:g} and {hi:g}.")
    return x


def norm(spec: dict) -> dict:
    s = spec or {}
    kind = s.get("kind") or "custom"
    if kind not in KINDS:
        raise DesignError("kind must be one of: " + ", ".join(KINDS) + ".")
    up = str(s.get("uptime") or "99.5")
    if up not in UPTIME:
        raise DesignError("uptime must be one of: " + ", ".join(UPTIME) + ".")
    needs = [n for n in (s.get("needs") or []) if n in NEEDS]
    ents = [re.sub(r"[^a-z0-9_]", "_", e.strip().lower()).strip("_") for e in str(s.get("entities") or "").split(",") if e.strip()][:8]
    return {"name": str(s.get("name") or "My system")[:60], "kind": kind, "users": int(_num(s.get("users"), "users", 1, 100_000_000, 50)), "active_pct": _num(s.get("active_pct"), "active_pct", 0.1, 100, 30),
            "actions_per_user_day": _num(s.get("actions_per_user_day"), "actions_per_user_day", 0.1, 5000, 20), "peak_factor": _num(s.get("peak_factor"), "peak_factor", 1, 100, 5),
            "record_kb": _num(s.get("record_kb"), "record_kb", 0.01, 100_000, 2), "new_records_per_day": _num(s.get("new_records_per_day"), "new_records_per_day", 0, 1e9, 100),
            "retention_months": int(_num(s.get("retention_months"), "retention_months", 1, 240, 36)), "uptime": up, "needs": needs, "team": int(_num(s.get("team"), "team", 1, 500, 1)),
            "entities": ents, "budget_month": _num(s.get("budget_month"), "budget_month", 0, 1e7, 0)}


# ------------------------------------------------------------------ capacity


def capacity(spec: dict) -> dict:
    s = norm(spec)
    dau = s["users"] * s["active_pct"] / 100
    req_day = dau * s["actions_per_user_day"]
    avg = req_day / 86400
    peak = avg * s["peak_factor"]
    per_year_gb = s["new_records_per_day"] * s["record_kb"] * 365 / 1e6
    total_gb = per_year_gb * s["retention_months"] / 12 * 1.5          # 1.5 = indexes and overhead
    egress_gb = req_day * 30 * 20 / 1e6                                  # 20 KB average response
    ha = UPTIME[s["uptime"]] >= 0.999

    def servers(pk):
        for key in ("vps_small", "vps_mid", "vps_large"):
            cost, rps = PRICE[key]
            if pk <= rps * 0.6:                                          # run at 60% at peak, keep headroom
                return key, 2 if ha else 1
        return "vps_large", max(2 if ha else 1, math.ceil(pk / (PRICE["vps_large"][1] * 0.6)))

    def cost(pk, gb, eg):
        key, n = servers(pk)
        c = {"servers": PRICE[key][0] * n, "database": PRICE["db_base"] + PRICE["db_per_gb"] * gb, "backups": PRICE["backup_per_gb"] * gb * 2, "bandwidth": PRICE["egress_per_gb"] * eg}
        if "files" in s["needs"]:
            c["file storage"] = PRICE["object_per_gb"] * gb * 0.5
        if "email" in s["needs"]:
            c["email service"] = PRICE["email_provider"]
        c = {k: round(v, 2) for k, v in c.items()}
        return {"server_size": key, "server_count": n, "lines": c, "total": round(sum(c.values()), 2)}

    now, x10 = cost(peak, total_gb, egress_gb), cost(peak * 10, total_gb * 10, egress_gb * 10)
    math_lines = [f"Daily active users = {s['users']:,} users x {s['active_pct']:g}% = {dau:,.0f}",
                  f"Requests per day = {dau:,.0f} x {s['actions_per_user_day']:g} actions = {req_day:,.0f}",
                  f"Average requests per second = {req_day:,.0f} / 86,400 = {avg:.3f}",
                  f"Peak requests per second = {avg:.3f} x peak factor {s['peak_factor']:g} = {peak:.2f}",
                  f"New data per year = {s['new_records_per_day']:,.0f} records/day x {s['record_kb']:g} KB x 365 = {per_year_gb:.2f} GB",
                  f"Stored over {s['retention_months']} months, with 1.5x for indexes = {total_gb:.2f} GB",
                  f"Bandwidth out per month = {req_day:,.0f} x 30 days x about 20 KB = {egress_gb:.1f} GB"]
    verdict = "one small server is plenty" if peak < 5 else "a single modest server is fine" if peak < 60 else "plan for several servers and a cache"
    over = s["budget_month"] and now["total"] > s["budget_month"]
    return {"inputs": s, "dau": round(dau), "requests_per_day": round(req_day), "avg_rps": round(avg, 3), "peak_rps": round(peak, 2), "storage_gb": round(total_gb, 2), "egress_gb_month": round(egress_gb, 1),
            "arithmetic": math_lines, "cost": now, "cost_at_10x": x10, "verdict": f"At these numbers {verdict}.",
            "budget": (f"Estimated ${now['total']:.0f}/month is over your ${s['budget_month']:.0f} budget." if over else None),
            "assumptions": ["Prices are rough list prices for small cloud servers, databases and storage; real prices differ by provider and region.",
                            "A small server is assumed to handle about 30 requests/second, a mid one 100, a large one 250 (simple pages with a database call). Test your own app to find your real number.",
                            "Peak factor is how many times busier your busiest moment is than the average. Guess honestly, then measure."],
            "caution": "These are estimates from the numbers you typed in, not measurements."}


# ------------------------------------------------------------------ design


T = {
    "booking": {"customers": ["name text not null", "phone text", "email text"], "services": ["name text not null", "minutes integer", "price numeric(10,2)"],
                "bookings": ["customer_id integer references customers(id)", "service_id integer references services(id)", "starts_at timestamp not null", "status text default 'booked'", "notes text"]},
    "inventory": {"items": ["sku text unique not null", "name text not null", "reorder_level integer default 0"], "locations": ["name text not null"], "suppliers": ["name text not null", "email text"],
                  "stock_moves": ["item_id integer references items(id)", "location_id integer references locations(id)", "qty integer not null", "reason text", "moved_at timestamp default current_timestamp"]},
    "dashboard": {"sources": ["name text not null", "kind text", "last_loaded timestamp"], "datasets": ["source_id integer references sources(id)", "name text not null", "row_count integer"],
                  "reports": ["name text not null", "definition text", "created_at timestamp default current_timestamp"]},
    "marketplace": {"listings": ["seller_id integer references users(id)", "title text not null", "price numeric(10,2) not null", "status text default 'active'"],
                    "orders": ["buyer_id integer references users(id)", "listing_id integer references listings(id)", "total numeric(10,2)", "status text default 'new'"]},
    "chat": {"rooms": ["name text not null", "created_at timestamp default current_timestamp"], "memberships": ["room_id integer references rooms(id)", "user_id integer references users(id)"],
             "messages": ["room_id integer references rooms(id)", "sender_id integer references users(id)", "body text not null", "sent_at timestamp default current_timestamp"]},
}
FLOWS = {
    "booking": [("Customer", "Web app", "Pick a service and a time"), ("Web app", "API", "POST /bookings"), ("API", "Database", "Check the slot is free, then insert"), ("API", "Email service", "Send confirmation"), ("API", "Web app", "Show the confirmed booking")],
    "inventory": [("Staff", "Web app", "Scan or type a part number"), ("Web app", "API", "POST /stock_moves"), ("API", "Database", "Record the move, recompute stock"), ("API", "Web app", "Show new level; warn if below reorder level")],
    "dashboard": [("Owner", "Web app", "Upload or refresh data"), ("Web app", "API", "POST /datasets"), ("API", "Database", "Validate and load"), ("Web app", "API", "GET /reports/{id}"), ("API", "Web app", "Charts and totals")],
    "marketplace": [("Buyer", "Web app", "Click buy"), ("Web app", "API", "POST /orders"), ("API", "Payment provider", "Charge the card"), ("API", "Database", "Save the order once payment succeeds"), ("API", "Email service", "Receipt to buyer and seller")],
    "chat": [("Sender", "Web app", "Type a message"), ("Web app", "API", "POST /messages (or over a socket)"), ("API", "Database", "Save the message"), ("API", "Web app", "Push it to everyone in the room")],
    "custom": [("User", "Web app", "Does something"), ("Web app", "API", "Calls the API"), ("API", "Database", "Reads or writes"), ("API", "Web app", "Shows the result")],
}


def design(spec: dict) -> dict:
    s = norm(spec)
    cap = capacity(s)
    needs, peak = set(s["needs"]), cap["peak_rps"]
    comps = [{"id": "client", "label": "Browser / phone", "layer": "client"}, {"id": "app", "label": "Web app (UI)", "layer": "app"}, {"id": "api", "label": "API server", "layer": "app"},
             {"id": "db", "label": "Database", "layer": "data"}, {"id": "backup", "label": "Nightly backup", "layer": "data"}]
    edges = [("client", "app", "pages"), ("app", "api", "JSON calls"), ("api", "db", "SQL"), ("db", "backup", "copy")]
    why = {"client": "How people reach it.", "app": "The screens people use.", "api": "One place that holds the rules, so every screen behaves the same.", "db": "The single source of truth.", "backup": "A copy somewhere else, tested by restoring it."}

    def add(i, label, layer, w, e):
        comps.append({"id": i, "label": label, "layer": layer})
        why[i] = w
        edges.extend(e)

    if "auth" in needs or s["users"] > 1:
        add("auth", "Sign-in / sessions", "app", "Who is allowed to do what.", [("api", "auth", "check token")])
    if peak > 40 or "reports" in needs:
        add("cache", "Cache", "data", "Keeps repeated reads off the database.", [("api", "cache", "hot reads")])
    if "files" in needs:
        add("files", "File storage", "data", "Uploads belong in file storage, not in database rows.", [("api", "files", "upload/download")])
    if "realtime" in needs:
        add("ws", "Live updates (websocket)", "app", "Pushes changes without the screen asking.", [("client", "ws", "live"), ("ws", "api", "events")])
    if "search" in needs:
        add("search", "Search index", "data", "Fast text search without scanning every row.", [("api", "search", "query"), ("db", "search", "index feed")])
    if needs & {"email", "reports"} or peak > 40:
        add("queue", "Job queue + worker", "app", "Slow work (email, big reports) runs in the background so the screen stays quick.", [("api", "queue", "enqueue")])
    if "payments" in needs:
        add("pay", "Payment provider", "external", "Never store card numbers yourself; the provider holds them.", [("api", "pay", "charge")])
    if "email" in needs:
        add("mail", "Email service", "external", "Confirmations and receipts.", [("queue" if any(c["id"] == "queue" for c in comps) else "api", "mail", "send")])
    add("mon", "Logs + health check", "app", "You find out it is down before customers tell you.", [("api", "mon", "logs")])
    tables = dict(T.get(s["kind"], {}))
    if s["kind"] == "custom":
        tables = {e: ["name text not null", "created_at timestamp default current_timestamp"] for e in (s["entities"] or ["records"])}
    if "auth" in needs or s["users"] > 1 or s["kind"] in ("marketplace", "chat"):
        tables = {"users": ["email text unique not null", "name text", "role text default 'user'", "password_hash text not null"], **tables}
    tables["audit_log"] = ["who text", "action text", "logged_at timestamp default current_timestamp", "detail text"]
    ddl = []
    for t, cols in tables.items():
        ddl.append(f"create table {t} (\n  id integer primary key,\n  " + ",\n  ".join(cols) + "\n);")
    api = []
    for t in tables:
        if t in ("audit_log", "users"):
            continue
        api += [f"GET /{t}", f"POST /{t}", f"GET /{t}/{{id}}", f"PATCH /{t}/{{id}}", f"DELETE /{t}/{{id}}"]
    if "auth" in needs or s["users"] > 1:
        api = ["POST /login", "POST /logout"] + api
    seq = [{"from": a, "to": b, "message": m} for a, b, m in FLOWS.get(s["kind"], FLOWS["custom"])]
    return {"inputs": s, "summary": f"{s['name']}: {len(comps)} parts, {len(tables)} tables, {len(api)} API calls. {cap['verdict']}", "components": [dict(c, why=why[c["id"]]) for c in comps],
            "edges": [{"from": a, "to": b, "label": l} for a, b, l in edges], "tables": {t: c for t, c in tables.items()}, "ddl": "\n\n".join(ddl), "api": api, "sequence": seq, "capacity": cap,
            "next_steps": ["Paste the SQL into the Code Workbench to check it, or into a scratch database to try it.", "Run the review below and fix anything marked high.", "Build one vertical slice first: one table, its API, one screen, one test."],
            "caution": "This is a starting design from rules and your numbers. Change it where you know your business better."}


# ------------------------------------------------------------------ trade-offs and review


def tradeoffs(spec: dict) -> dict:
    s = norm(spec)
    cap = capacity(s)
    peak, needs = cap["peak_rps"], set(s["needs"])
    cards = [
        {"topic": "Database", "choice": "One relational database (Postgres, or SQLite/DuckDB while it is just you)" if s["users"] < 50 else "One managed Postgres",
         "why": "Your data has relationships (customers, orders, items) and you need correct totals.", "gives_up": "Scaling writes across many machines is harder. You will not need that until you have very large traffic.", "revisit_when": "Peak writes stay above a few hundred per second."},
        {"topic": "Shape of the app", "choice": "One app (a monolith)" if s["team"] < 6 else "A monolith with clear modules", "why": f"With {s['team']} {'person' if s['team'] == 1 else 'people'}, separate services mostly add things to run and break.",
         "gives_up": "You deploy everything together.", "revisit_when": "Different parts need to scale or be released independently."},
        {"topic": "Servers", "choice": "One server plus backups" if UPTIME[s["uptime"]] < 0.999 else "Two servers behind a load balancer", "why": f"A {s['uptime']}% target allows about {round((1 - UPTIME[s['uptime']]) * 8766, 1)} hours of downtime a year.",
         "gives_up": "One server means an outage while it restarts or fails." if UPTIME[s["uptime"]] < 0.999 else "Roughly double the server cost and more to configure.", "revisit_when": "Customers start to depend on it during business hours."},
        {"topic": "Reads", "choice": "Add a cache" if peak > 40 else "No cache yet", "why": f"Peak is about {peak:.1f} requests/second." + (" That is high enough that repeated reads add up." if peak > 40 else " A database handles this easily."),
         "gives_up": "A cache can show slightly old data." if peak > 40 else "Nothing yet; extra moving parts avoided.", "revisit_when": "Pages slow down under real use (measure first)."},
        {"topic": "Slow work", "choice": "Background queue" if needs & {"email", "reports"} else "Do it inside the request", "why": "Emails and big reports make the screen wait if done inline." if needs & {"email", "reports"} else "No slow work was listed.",
         "gives_up": "A queue is one more thing to run and watch." if needs & {"email", "reports"} else "If slow jobs appear later, move them out.", "revisit_when": "Any request takes more than about 2 seconds."},
        {"topic": "Live updates", "choice": "Websocket" if "realtime" in needs else "Plain page refresh / polling every few seconds", "why": "You marked live updates as needed." if "realtime" in needs else "Polling is much simpler and good enough for most business screens.",
         "gives_up": "Websockets need sticky connections and more care when scaling." if "realtime" in needs else "Updates arrive a few seconds late.", "revisit_when": "Users need changes in under a second."}]
    return {"cards": cards, "caution": "These are defaults for your numbers. A trade-off is a choice with a cost, so pick on purpose."}


def review(spec: dict) -> dict:
    s = norm(spec)
    d = design(s)
    cap = d["capacity"]
    needs, f = set(s["needs"]), []
    ids = {c["id"] for c in d["components"]}
    ha = UPTIME[s["uptime"]] >= 0.999
    n = cap["cost"]["server_count"]

    def add(sev, title, detail, fix):
        f.append({"severity": sev, "title": title, "detail": detail, "fix": fix})
    if ha and n < 2:
        add("high", "Single point of failure", f"The target is {s['uptime']}% but the plan has one server.", "Run two servers behind a load balancer, or lower the target to what one server can honestly deliver.")
    add("high" if s["users"] > 1 else "medium", "Backups are only useful if restored", "The design has a nightly backup, but nothing says it has ever been restored.", "Schedule a monthly restore test into a scratch database and keep one copy off-site.")
    if s["users"] > 1 and "auth" not in needs:
        add("high", "Several users but no sign-in listed", "Without sign-in everyone sees and can change everything.", "Add sign-in, roles (owner, staff, read-only) and an audit log.")
    if "payments" in needs:
        add("high", "Payments", "Card data is regulated.", "Use a payment provider's hosted checkout so card numbers never reach your server, and verify payment webhooks.")
    if "files" in needs:
        add("medium", "Uploads", "Uploaded files can carry viruses or be huge.", "Limit size and type, store outside the web folder, and serve through checked download links.")
    if "queue" not in ids and (needs & {"email", "reports"}):
        add("medium", "Slow work inside requests", "Email or reports are done while the user waits.", "Move them to a background job.")
    if cap["cost_at_10x"]["server_count"] > n or cap["cost_at_10x"]["server_size"] != cap["cost"]["server_size"]:
        add("medium", "At 10 times the load", f"Peak would be about {cap['peak_rps'] * 10:.1f} requests/second and cost about ${cap['cost_at_10x']['total']:.0f}/month, with {cap['cost_at_10x']['server_count']} x {cap['cost_at_10x']['server_size']}.", "Fine for now. Add load testing before any launch that could bring that surge.")
    else:
        add("info", "At 10 times the load", f"The same size of server still copes (about ${cap['cost_at_10x']['total']:.0f}/month).", "No change needed yet.")
    if cap["storage_gb"] > 50:
        add("medium", "Data keeps growing", f"About {cap['storage_gb']:.0f} GB over {s['retention_months']} months.", "Decide what gets archived or deleted, and when.")
    if s["budget_month"] and cap["cost"]["total"] > s["budget_month"]:
        add("medium", "Over budget", cap["budget"] or "", "Cut optional parts (cache, second server) or raise the budget.")
    add("medium", "Secrets and settings", "Passwords, API keys and database addresses must not live in code.", "Keep them in environment variables, never in a repo.")
    add("info", "Monitoring", "A health check and logs are in the design.", "Add an alert to your phone when the health check fails twice in a row.")
    order = {"high": 0, "medium": 1, "info": 2}
    f.sort(key=lambda x: order[x["severity"]])
    return {"findings": f, "counts": {k: sum(1 for x in f if x["severity"] == k) for k in order}, "caution": "This reviews only the design you described. It cannot see the real system."}


# ------------------------------------------------------------------ practice


CASES = {
    "url_shortener": {"title": "Design a URL shortener", "prompt": "People paste a long link and get a short one. 1 million new links a day, 100 clicks per link per day on average, links kept for 5 years.",
                      "numbers": {"users": 1_000_000, "active_pct": 100, "actions_per_user_day": 100, "record_kb": 0.5, "new_records_per_day": 1_000_000, "retention_months": 60, "peak_factor": 3},
                      "checklist": [("ids", "A way to make short unique codes (counter + base62, or hash with collision check)", ["base62", "counter", "hash", "unique", "collision"], "Two links must never get the same code."),
                                    ("reads", "Reads far outnumber writes, so cache the code-to-link lookup", ["cache", "redis", "read-heavy", "read heavy", "reads"], "100 clicks per link means reads dominate."),
                                    ("store", "A simple key-value or indexed table keyed by code", ["table", "key-value", "key value", "index", "primary key"], "Lookups are always by code."),
                                    ("redirect", "Use a redirect (301/302) and say which and why", ["301", "302", "redirect"], "301 can be cached by browsers; 302 lets you count clicks."),
                                    ("abuse", "Handle abuse: malware links, rate limits, expiry", ["abuse", "rate limit", "malware", "expire", "expiry", "block"], "Short links hide the destination."),
                                    ("scale", "Do the arithmetic: writes per second, storage over 5 years", ["per second", "rps", "gb", "tb", "storage"], "Numbers justify the design.")]},
    "booking": {"title": "Design a booking system for a repair shop", "prompt": "Customers book a drop-off slot online. 40 bookings a day, 3 staff, 2 locations, text reminders the day before.",
                "numbers": {"users": 2000, "active_pct": 5, "actions_per_user_day": 10, "record_kb": 2, "new_records_per_day": 40, "retention_months": 60, "peak_factor": 8},
                "checklist": [("double", "Prevent double-booking the same slot (a database constraint or lock)", ["double", "unique", "constraint", "lock", "transaction"], "Two people clicking at once must not both win."),
                              ("tz", "Time zones and business hours", ["time zone", "timezone", "hours", "utc"], "Store UTC, show local."),
                              ("remind", "Reminders run as a scheduled background job", ["reminder", "queue", "job", "cron", "scheduler"], "Not inside a web request."),
                              ("cancel", "Cancel and reschedule flow", ["cancel", "reschedule"], "Real customers change their minds."),
                              ("privacy", "Protect customer phone numbers and emails", ["privacy", "encrypt", "access", "role", "auth"], "Personal data needs access control."),
                              ("backup", "Backups", ["backup", "restore"], "A lost bookings table is a lost day.")]},
    "chat": {"title": "Design a small team chat app", "prompt": "50 teams, up to 20 people each, messages should appear instantly, history searchable, keep 2 years.",
             "numbers": {"users": 1000, "active_pct": 60, "actions_per_user_day": 80, "record_kb": 1, "new_records_per_day": 48000, "retention_months": 24, "peak_factor": 6},
             "checklist": [("push", "Real-time delivery (websocket or server-sent events)", ["websocket", "socket", "sse", "server-sent", "push"], "Polling feels slow for chat."),
                           ("order", "Message ordering and no lost messages", ["order", "sequence", "ack", "retry", "idempotent"], "Messages must arrive once and in order."),
                           ("rooms", "Rooms and membership checks on every message", ["room", "member", "permission", "auth"], "Only members can read a room."),
                           ("history", "Store history and paginate it", ["history", "paginate", "pagination", "cursor", "index"], "Do not load 2 years at once."),
                           ("search", "Search over history", ["search", "full-text", "full text", "index"], "Needs an index, not a table scan."),
                           ("offline", "Users who are offline catch up when they return", ["offline", "catch up", "unread", "sync"], "Phones disconnect constantly.")]},
}


def practice(kind: str, reveal: bool = False) -> dict:
    c = CASES.get(kind)
    if not c:
        raise DesignError("kind must be one of: " + ", ".join(CASES) + ".")
    out = {"kind": kind, "title": c["title"], "prompt": c["prompt"], "numbers": c["numbers"], "kinds": list(CASES), "how": "Write your design in plain sentences, then grade it. Grading looks for the key ideas; it cannot judge how good your reasoning is."}
    if reveal:
        out["checklist"] = [{"id": i, "label": lb, "why": w} for i, lb, _k, w in c["checklist"]]
    return out


def grade(kind: str, answer: str) -> dict:
    c = CASES.get(kind)
    if not c:
        raise DesignError("kind must be one of: " + ", ".join(CASES) + ".")
    a = (answer or "").lower()
    if len(a.split()) < 15:
        raise DesignError("Write at least a few sentences of design first.")
    hits, misses = [], []
    for i, label, kws, why in c["checklist"]:
        (hits if any(k in a for k in kws) else misses).append({"id": i, "label": label, "why": why})
    pct = round(100 * len(hits) / len(c["checklist"]))
    nums = bool(re.search(r"\d", a))
    return {"kind": kind, "score": pct, "hits": hits, "misses": misses, "used_numbers": nums,
            "says": f"You covered {len(hits)} of {len(c['checklist'])} key ideas." + ("" if nums else " You gave no numbers; estimate load and storage."),
            "caution": "This checks for key ideas by keyword. A high score does not prove the design is good, and a different valid design may score lower."}


# ------------------------------------------------------------------ agent tool


TOOL_SYS_DESIGN = {"name": "sys_design", "description": "Systems design helper (rule-based, shows its arithmetic). action 'design': spec -> components, edges, tables with SQL, API calls, sequence, capacity. 'capacity': requests per second, storage, bandwidth, "
                   "monthly cost now and at 10x. 'tradeoffs': decision cards. 'review': single points of failure, security and growth findings. 'practice': kind url_shortener|booking|chat (reveal true for the checklist). "
                   "spec fields: name, kind (booking|inventory|dashboard|marketplace|chat|custom), users, active_pct, actions_per_user_day, peak_factor, record_kb, new_records_per_day, retention_months, uptime (99|99.5|99.9|99.99), "
                   "needs (auth,payments,files,realtime,reports,email,search), team, entities (comma list for custom), budget_month. Always repeat the caution that comes back.",
                   "input_schema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["design", "capacity", "tradeoffs", "review", "practice"]}, "spec": {"type": "object"}, "kind": {"type": "string"}, "reveal": {"type": "boolean"}},
                                    "required": ["action"]}}


def tool_result(args: dict) -> str:
    import json
    a = args or {}
    act = a.get("action")
    fn = {"design": design, "capacity": capacity, "tradeoffs": tradeoffs, "review": review}.get(act)
    if fn:
        r = fn(a.get("spec") or {})
        if act == "design":
            r = {k: v for k, v in r.items() if k != "capacity"} | {"capacity_summary": r["capacity"]["arithmetic"] + [r["capacity"]["verdict"]]}
    elif act == "practice":
        r = practice(str(a.get("kind") or "booking"), bool(a.get("reveal")))
    else:
        raise DesignError("action must be design, capacity, tradeoffs, review or practice.")
    return json.dumps(r, default=str)[:8000]
