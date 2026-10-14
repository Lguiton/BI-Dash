"""AI usage: how many questions went to which model, at which tier, and how many tokens they used.

Counts come from the AI question log (kept in the state file, so they survive restarts). The daily CAPS in the router are
counted in memory and reset when the backend restarts: the panel shows both so you can see the difference.
Dollar cost is shown only if you set the prices yourself (BI_PRICE_<PROVIDER>_IN / _OUT, dollars per million tokens),
because prices change and a wrong number is worse than no number.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

from app.services import llm_router, state

PROVIDERS = ("google", "openai", "anthropic")
TIERS = ("simple", "medium", "complex")


def _price(provider: str) -> tuple[float, float] | None:
    try:
        pin = float(os.environ.get(f"BI_PRICE_{provider.upper()}_IN", ""))
        pout = float(os.environ.get(f"BI_PRICE_{provider.upper()}_OUT", ""))
        return pin, pout
    except ValueError:
        return None


def _cost(provider: str, tin: int, tout: int) -> float | None:
    p = _price(provider)
    return None if p is None else round(tin / 1e6 * p[0] + tout / 1e6 * p[1], 4)


def summary(days: int = 14) -> dict:
    days = max(1, min(int(days), 90))
    since = (datetime.now(timezone.utc) - timedelta(days=days - 1)).strftime("%Y-%m-%d 00:00:00")
    rows = state.rows("SELECT substr(created_at,1,10) AS day, provider, COALESCE(tier, kind, '') AS tier, track, input_tokens AS tin, output_tokens AS tout, ok "
                      "FROM ai_log WHERE created_at >= ?", (since,))
    st = {r["id"]: r for r in llm_router.status()["providers"]}
    today = [{"provider": p, "label": st[p]["label"], "configured": st[p]["configured"], "used": st[p]["used_today"], "limit": st[p]["daily_limit"],
              "pct": round(100 * st[p]["used_today"] / st[p]["daily_limit"]) if st[p]["daily_limit"] else 0, "model": st[p]["model"]} for p in PROVIDERS]
    daily = {}
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        daily[d] = {"day": d, "total": 0, **{p: 0 for p in PROVIDERS}, "tokens": 0}
    matrix = {t: {p: 0 for p in PROVIDERS} for t in TIERS}
    tokens = {p: [0, 0] for p in PROVIDERS}
    by_track: dict[str, int] = {}
    for r in rows:
        p = r["provider"] if r["provider"] in PROVIDERS else None
        d = daily.get(r["day"])
        if d and p:
            d[p] += 1
            d["total"] += 1
            d["tokens"] += (r["tin"] or 0) + (r["tout"] or 0)
        if p and r["tier"] in matrix:
            matrix[r["tier"]][p] += 1
        if p:
            tokens[p][0] += r["tin"] or 0
            tokens[p][1] += r["tout"] or 0
        if r["track"]:
            by_track[r["track"]] = by_track.get(r["track"], 0) + 1
    total_tokens = sum(a + b for a, b in tokens.values())
    costs = {p: _cost(p, *tokens[p]) for p in PROVIDERS}
    priced = [c for c in costs.values() if c is not None]
    recent = state.rows("SELECT created_at, question, provider, model, COALESCE(tier, kind, '') AS tier, track, input_tokens AS tin, output_tokens AS tout "
                        "FROM ai_log ORDER BY id DESC LIMIT 15")
    return {"days": days, "today": today, "daily": list(daily.values()), "matrix": matrix, "by_track": dict(sorted(by_track.items(), key=lambda kv: -kv[1])),
            "tokens": {p: {"input": tokens[p][0], "output": tokens[p][1], "cost_usd": costs[p]} for p in PROVIDERS}, "total_tokens": total_tokens,
            "total_questions": sum(d["total"] for d in daily.values()), "total_cost_usd": round(sum(priced), 4) if priced else None,
            "cost_note": ("Cost uses the prices you set in backend/.env." if priced else
                          "No prices set, so no dollar figure is shown. Add BI_PRICE_GOOGLE_IN / _OUT (and OPENAI, ANTHROPIC), dollars per million tokens, to see an estimate."),
            "caps_note": "Daily caps are counted in memory and reset when the backend restarts; this history is saved and does not.",
            "recent": recent}
