"""Prescriptive analytics: rule-based recommendations with the arithmetic shown.

Each recommendation says what to do, the estimated dollar impact, and exactly how that estimate
was computed, so you can check it. These are decision-support rules, not predictions.
"""

MIN_RECORDS = 4


def _money(v: float) -> str:
    return f"${v:,.0f}"


def build_recommendations(entities: list[dict], weekday_rows: list[dict]) -> list[dict]:
    recs: list[dict] = []

    # 1. Bring over-budget entities back to their cost budget.
    for e in entities:
        bt, avg, n = e.get("baseline_target"), e.get("avg_cost_per_record"), e.get("records", 0)
        if bt and avg and n >= MIN_RECORDS and avg > bt * 1.05:
            saving = (avg - bt) * n
            recs.append({
                "priority_value": saving, "entity": e["entity_name"], "kind": "cost_control",
                "title": f"Bring {e['entity_name']} back to its cost budget",
                "action": f"Audit cost drivers at {e['entity_name']} (avg {_money(avg)} per record vs a {_money(bt)} budget).",
                "impact_usd": round(saving, 2),
                "basis": f"({avg:,.2f} avg cost - {bt:,.2f} budget) x {n} records in this selection.",
            })

    # 2. Lift the weakest-margin entity in each category toward its category's best peer.
    by_cat: dict[str, list[dict]] = {}
    for e in entities:
        if e.get("revenue") and e.get("records", 0) >= MIN_RECORDS:
            by_cat.setdefault(e["category"], []).append(e)
    for cat, group in by_cat.items():
        if len(group) < 2:
            continue
        best = max(group, key=lambda g: g["margin_pct"])
        worst = min(group, key=lambda g: g["margin_pct"])
        gap = best["margin_pct"] - worst["margin_pct"]
        if gap >= 5:
            gain = worst["revenue"] * gap / 100
            recs.append({
                "priority_value": gain, "entity": worst["entity_name"], "kind": "margin_gap",
                "title": f"Close the margin gap at {worst['entity_name']}",
                "action": f"Study how {best['entity_name']} earns {best['margin_pct']:.1f}% margin in {cat} versus {worst['margin_pct']:.1f}% here.",
                "impact_usd": round(gain, 2),
                "basis": f"{worst['revenue']:,.0f} revenue x {gap:.1f} margin points.",
            })

    # 3. Shift capacity toward days where an entity earns more per record.
    ent_name = {e["entity_id"]: e["entity_name"] for e in entities}
    rows: dict[str, dict] = {}
    for r in weekday_rows:
        rows.setdefault(r["entity_id"], {})["weekend" if r["is_weekend"] else "weekday"] = r
    for eid, d in rows.items():
        wk, we = d.get("weekday"), d.get("weekend")
        if not wk or not we or min(wk["records"], we["records"]) < MIN_RECORDS or not wk["avg_revenue"]:
            continue
        lift = we["avg_revenue"] / wk["avg_revenue"] - 1
        if abs(lift) >= 0.15:
            better, worse = ("weekend", "weekday") if lift > 0 else ("weekday", "weekend")
            hi, lo = (we, wk) if lift > 0 else (wk, we)
            # Moving 10% of the lower-yield day's records to the higher-yield day.
            gain = 0.10 * lo["records"] * (hi["avg_revenue"] - lo["avg_revenue"])
            recs.append({
                "priority_value": gain, "entity": ent_name.get(eid, eid), "kind": "capacity",
                "title": f"Weight capacity toward {better}s at {ent_name.get(eid, eid)}",
                "action": f"{ent_name.get(eid, eid)} earns {abs(lift) * 100:.0f}% more revenue per record on {better}s than {worse}s.",
                "impact_usd": round(gain, 2),
                "basis": f"Shift 10% of {lo['records']} {worse} records x ({hi['avg_revenue']:,.2f} - {lo['avg_revenue']:,.2f}) revenue per record.",
            })

    recs.sort(key=lambda r: -r["priority_value"])
    for r in recs:
        del r["priority_value"]
    return recs[:6]
