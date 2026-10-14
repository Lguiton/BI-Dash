"""Insights computed from real statistics.

Every number in an insight is calculated here in Python / SQL. Nothing is
estimated or narrated by a language model; the text is a template over
computed values.
"""
import statistics

MIN_POINTS_FOR_ANOMALY = 5
MAD_THRESHOLD = 3.5  # Iglewicz & Hoaglin: |modified z| > 3.5 flags an outlier
# Practical-significance floors: a statistical outlier must also be big enough to matter.
MIN_MARGIN_GAP_POINTS = 5.0   # margin must differ from typical by >= 5 percentage points
MIN_PROFIT_GAP_FRACTION = 0.15  # profit must differ from typical by >= 15%
OVER_BUDGET_PCT = 10.0  # flag entities whose avg cost per record exceeds budget by >= 10%


def modified_z_scores(values: list[float]) -> list[float]:
    """Modified z-scores using median / MAD (robust to the outliers themselves).

    A plain z-score cannot flag anything in short series (max |z| is bounded by
    (n-1)/sqrt(n)); the MAD version can. Returns zeros when MAD is 0.
    """
    med = statistics.median(values)
    mad = statistics.median([abs(v - med) for v in values])
    if mad == 0:
        # fall back to mean absolute deviation, per the standard recipe
        mean_ad = statistics.fmean([abs(v - med) for v in values])
        if mean_ad == 0:
            return [0.0] * len(values)
        return [(v - med) / (1.253314 * mean_ad) for v in values]
    return [0.6745 * (v - med) / mad for v in values]


def pct_change(cur: float | None, prev: float | None) -> float | None:
    if cur is None or prev is None or prev == 0:
        return None
    return round((cur - prev) / abs(prev) * 100, 2)


def _money(v: float) -> str:
    return f"${v:,.0f}" if abs(v) >= 1000 else f"${v:,.2f}"


def build_insights(kpis: dict, prev_kpis: dict | None, daily: list[dict], entities: list[dict]) -> list[dict]:
    out: list[dict] = []

    if not kpis.get("record_count"):
        return [{"analytics_type": "descriptive", "type": "info", "severity": "info", "title": "No data in this view",
                 "detail": "No records match the current filters."}]

    # 1. Period-over-period
    if prev_kpis and prev_kpis.get("record_count"):
        for key, label in (("total_revenue", "Revenue"), ("net_profit", "Net profit")):
            ch = pct_change(kpis[key], prev_kpis[key])
            if ch is not None and abs(ch) >= 5:
                up = ch > 0
                out.append({
                    "analytics_type": "descriptive", "type": "period_change",
                    "severity": "positive" if up else "warning",
                    "title": f"{label} {'up' if up else 'down'} {abs(ch):.1f}% vs previous period",
                    "detail": f"{_money(kpis[key])} now vs {_money(prev_kpis[key])} in the previous period of equal length.",
                })
        m_cur, m_prev = kpis.get("net_margin_pct"), prev_kpis.get("net_margin_pct")
        if m_cur is not None and m_prev is not None and abs(m_cur - m_prev) >= 2:
            d = m_cur - m_prev
            out.append({
                "analytics_type": "descriptive", "type": "margin_change",
                "severity": "positive" if d > 0 else "warning",
                "title": f"Net margin {'improved' if d > 0 else 'slipped'} {abs(d):.1f} points",
                "detail": f"{m_cur:.1f}% now vs {m_prev:.1f}% previously.",
            })

    # 2. Revenue trend via least-squares slope over the daily series
    if len(daily) >= 5:
        xs = list(range(len(daily)))
        ys = [d["revenue"] for d in daily]
        slope, _ = statistics.linear_regression(xs, ys)
        mean_rev = statistics.fmean(ys)
        if mean_rev > 0:
            rel = slope / mean_rev * 100
            if abs(rel) >= 1:
                out.append({
                    "analytics_type": "descriptive", "type": "trend",
                    "severity": "positive" if rel > 0 else "warning",
                    "title": f"Daily revenue trending {'up' if rel > 0 else 'down'} ~{abs(rel):.1f}% per day",
                    "detail": f"Linear fit over {len(daily)} days: {_money(slope)} per day against a {_money(mean_rev)} daily average.",
                })

    # 3. Daily anomalies (profit and margin) via modified z-score.
    #    One insight per day, even if both metrics are off, to avoid near-duplicates.
    if len(daily) >= MIN_POINTS_FOR_ANOMALY:
        series = {
            "profit": [d["profit"] for d in daily],
            "margin": [(d["profit"] / d["revenue"] * 100) if d["revenue"] else 0.0 for d in daily],
        }
        by_date: dict[str, list[dict]] = {}
        for name, vals in series.items():
            med = statistics.median(vals)
            for d, v, z in zip(daily, vals, modified_z_scores(vals)):
                gap_ok = (abs(v - med) >= MIN_MARGIN_GAP_POINTS) if name == "margin" \
                    else (abs(v - med) >= MIN_PROFIT_GAP_FRACTION * abs(med))
                if abs(z) > MAD_THRESHOLD and gap_ok:
                    fmt = _money if name == "profit" else (lambda x: f"{x:.1f}%")
                    by_date.setdefault(d["date"], []).append(
                        {"name": name, "high": z > 0, "text": f"{name} {fmt(v)} vs typical {fmt(med)} (modified z {z:+.1f})"})
        for date_, hits in sorted(by_date.items()):
            high = all(h["high"] for h in hits)
            names = " and ".join(h["name"] for h in hits)
            out.append({
                "analytics_type": "diagnostic", "type": "anomaly",
                "severity": "positive" if high else "warning",
                "title": f"Unusual daily {names} on {date_}",
                "detail": "; ".join(h["text"] for h in hits).capitalize() + ".",
                "date": date_,
            })

    # 4. Entity highlights
    ranked = [e for e in entities if e.get("revenue")]
    if len(ranked) >= 2:
        best = max(ranked, key=lambda e: e["profit"])
        worst_margin = min(ranked, key=lambda e: e["margin_pct"])
        out.append({
            "analytics_type": "descriptive", "type": "entity_top", "severity": "info",
            "title": f"{best['entity_name']} is the top profit contributor",
            "detail": f"{_money(best['profit'])} profit, {best['profit'] / kpis['net_profit'] * 100:.0f}% of the total."
                      if kpis["net_profit"] else f"{_money(best['profit'])} profit.",
        })
        if worst_margin["entity_id"] != best["entity_id"] and worst_margin["margin_pct"] + 5 < kpis["net_margin_pct"]:
            out.append({
                "analytics_type": "diagnostic", "type": "entity_low_margin", "severity": "warning",
                "title": f"{worst_margin['entity_name']} has the thinnest margin",
                "detail": f"{worst_margin['margin_pct']:.1f}% vs {kpis['net_margin_pct']:.1f}% overall.",
            })

    # 5. Cost budget (baseline_target is a per-record cost budget)
    for e in sorted(entities, key=lambda e: -(e.get("vs_baseline_pct") or 0)):
        v = e.get("vs_baseline_pct")
        if v is not None and v >= OVER_BUDGET_PCT:
            out.append({
                "analytics_type": "diagnostic", "type": "over_budget", "severity": "warning",
                "title": f"{e['entity_name']} is {v:.1f}% over its cost budget",
                "detail": f"Average cost per record {_money(e['avg_cost_per_record'])} vs a budget of {_money(e['baseline_target'])}.",
            })

    if not out:
        out.append({"analytics_type": "descriptive", "type": "info", "severity": "info", "title": "Nothing unusual detected",
                    "detail": "No notable changes, trends or outliers in this view."})
    return out
