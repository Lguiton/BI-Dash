"""Health and performance monitoring: our own small take on Prometheus + Grafana.

A middleware times every request and keeps counts per route IN MEMORY (they reset when the backend restarts, and say so).
`/metrics` serves the same numbers in the Prometheus text format so a real Prometheus can scrape them; `/api/ops` serves a summary for the Ops page.
Nothing here stores request bodies, query strings or IP addresses.
"""
from __future__ import annotations

import threading
import time
from collections import deque

STARTED = time.time()
_lock = threading.Lock()
_routes: dict[tuple[str, str], dict] = {}
KEEP = 300        # latest durations kept per route, for percentiles


def record(method: str, route: str, status: int, seconds: float) -> None:
    with _lock:
        r = _routes.setdefault((method, route), {"count": 0, "errors": 0, "client_errors": 0, "total": 0.0, "max": 0.0, "recent": deque(maxlen=KEEP)})
        r["count"] += 1
        r["total"] += seconds
        r["max"] = max(r["max"], seconds)
        r["recent"].append(seconds)
        if status >= 500:
            r["errors"] += 1
        elif status >= 400:
            r["client_errors"] += 1


def reset() -> None:
    with _lock:
        _routes.clear()


def _pct(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    return s[min(len(s) - 1, int(round(p * (len(s) - 1))))]


def snapshot() -> list[dict]:
    with _lock:
        out = []
        for (m, route), r in _routes.items():
            rec = list(r["recent"])
            out.append({"method": m, "route": route, "count": r["count"], "errors": r["errors"], "client_errors": r["client_errors"],
                        "avg_ms": round(1000 * r["total"] / r["count"], 1), "p95_ms": round(1000 * _pct(rec, 0.95), 1), "max_ms": round(1000 * r["max"], 1)})
    return out


def prometheus() -> str:
    lines = ["# HELP bi_uptime_seconds Seconds since the backend started.", "# TYPE bi_uptime_seconds gauge", f"bi_uptime_seconds {time.time() - STARTED:.0f}",
             "# HELP bi_http_requests_total Requests handled, by route and method (resets on restart).", "# TYPE bi_http_requests_total counter"]
    snap = snapshot()
    esc = lambda s: s.replace("\\", "\\\\").replace('"', '\\"')
    for r in snap:
        lines.append(f'bi_http_requests_total{{method="{r["method"]}",route="{esc(r["route"])}"}} {r["count"]}')
    lines += ["# HELP bi_http_errors_total Server errors (5xx), by route.", "# TYPE bi_http_errors_total counter"]
    for r in snap:
        lines.append(f'bi_http_errors_total{{method="{r["method"]}",route="{esc(r["route"])}"}} {r["errors"]}')
    lines += ["# HELP bi_http_request_p95_seconds 95th percentile of the latest requests, by route.", "# TYPE bi_http_request_p95_seconds gauge"]
    for r in snap:
        lines.append(f'bi_http_request_p95_seconds{{method="{r["method"]}",route="{esc(r["route"])}"}} {r["p95_ms"] / 1000:.4f}')
    return "\n".join(lines) + "\n"


def summary() -> dict:
    from app.services import alerts, expectations, pipelines, sources, state, workspaces
    from app.config import db_path
    snap = snapshot()
    total = sum(r["count"] for r in snap)
    errors = sum(r["errors"] for r in snap)
    api = [r for r in snap if r["route"].startswith("/api")]

    def size(p):
        try:
            return p.stat().st_size
        except OSError:
            return 0
    base = db_path()
    files = {"practice": size(base), "real": size(workspaces.path_of("real")) if hasattr(workspaces, "path_of") else 0, "state": size(base.with_name(f"{base.stem}_state.sqlite"))}
    ai = state.rows("SELECT provider, COUNT(*) AS calls, ROUND(AVG(seconds), 2) AS avg_seconds, MAX(seconds) AS max_seconds, "
                    "COALESCE(SUM(input_tokens),0) AS tin, COALESCE(SUM(output_tokens),0) AS tout, SUM(CASE WHEN ok=1 THEN 0 ELSE 1 END) AS failed "
                    "FROM ai_log WHERE created_at >= datetime('now', '-14 days') GROUP BY provider ORDER BY calls DESC")
    pipes = pipelines.list_pipelines()
    srcs = sources.list_sources()
    return {
        "uptime_seconds": int(time.time() - STARTED), "requests": total, "server_errors": errors,
        "error_rate_pct": round(100 * errors / total, 2) if total else 0.0,
        "slowest": sorted(api, key=lambda r: -r["p95_ms"])[:8], "busiest": sorted(api, key=lambda r: -r["count"])[:8],
        "failing": [r for r in sorted(snap, key=lambda r: -r["errors"]) if r["errors"]][:8],
        "files": files, "ai": ai,
        "pipelines": {"total": len(pipes), "failing": sum(1 for p in pipes if p["last_ok"] is False)},
        "sources": {"total": len(srcs), "failing": sum(1 for s in srcs if s.get("last_status") == "error")},
        "quality": {"tables_failing": len(expectations.latest_failures())},
        "alerts": {"count": len(alerts.current())},
        "note": "Request numbers are kept in memory and reset when the backend restarts. AI timing covers calls made since update 13. Failed AI calls aren't logged.",
    }


def llm_summary(days: int = 7) -> dict:
    """LLM monitoring from the AI question log: latency, tokens and (only if prices are set) cost, per provider and per day."""
    from app.services import state, usage
    days = max(1, min(int(days), 90))
    rows = state.rows("SELECT substr(created_at,1,10) AS day, created_at, provider, model, COALESCE(tier, kind, '') AS tier, track, question, seconds, "
                      "COALESCE(input_tokens,0) AS tin, COALESCE(output_tokens,0) AS tout, ok FROM ai_log "
                      "WHERE created_at >= datetime('now', ?) ORDER BY id DESC", (f"-{days} days",))
    timed = [r for r in rows if r["seconds"] not in (None, "")]
    for r in timed:
        r["seconds"] = float(r["seconds"])
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["provider"] or "unknown", []).append(r)
    prov = []
    for p, rs in by.items():
        ts = sorted(float(r["seconds"]) for r in rs if r["seconds"] not in (None, ""))
        tin, tout = sum(r["tin"] for r in rs), sum(r["tout"] for r in rs)
        prov.append({"provider": p, "calls": len(rs), "failed": sum(1 for r in rs if not r["ok"]), "timed_calls": len(ts),
                     "avg_s": round(sum(ts) / len(ts), 2) if ts else None, "p95_s": round(_pct(ts, 95), 2) if ts else None, "max_s": round(ts[-1], 2) if ts else None,
                     "tokens_in": tin, "tokens_out": tout, "cost_usd": usage._cost(p, tin, tout) if p in usage.PROVIDERS else None})
    prov.sort(key=lambda r: -r["calls"])
    daily: dict[str, dict] = {}
    for r in rows:
        d = daily.setdefault(r["day"], {"day": r["day"], "calls": 0, "secs": [], "tokens": 0})
        d["calls"] += 1
        d["tokens"] += r["tin"] + r["tout"]
        if r["seconds"] not in (None, ""):
            d["secs"].append(float(r["seconds"]))
    series = [{"day": d["day"], "calls": d["calls"], "tokens": d["tokens"], "avg_s": round(sum(d["secs"]) / len(d["secs"]), 2) if d["secs"] else None} for d in sorted(daily.values(), key=lambda x: x["day"])]
    slow = sorted(timed, key=lambda r: -r["seconds"])[:8]
    priced = [p["cost_usd"] for p in prov if p["cost_usd"] is not None]
    return {"days": days, "calls": len(rows), "providers": prov, "daily": series,
            "slowest": [{"at": r["created_at"], "provider": r["provider"], "model": r["model"], "seconds": r["seconds"], "tier": r["tier"], "question": (r["question"] or "")[:100]} for r in slow],
            "total_cost_usd": round(sum(priced), 4) if priced else None,
            "note": "Built from the AI question log. Calls made before update 13 have no timing. Calls that failed before an answer came back are not logged, so the error count here is a floor, not the true rate. Cost shows only if you set BI_PRICE_* prices."}
