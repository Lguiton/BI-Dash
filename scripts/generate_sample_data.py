#!/usr/bin/env python3
"""Generate a realistic practice dataset (CSV) for the BI dashboard.

Why: 6 demo rows are too small to practice on. This builds a year of daily
operations data for 10 entities, with weekday/weekend patterns, a growth trend,
random noise, occasional delays/cancellations, and a few injected anomalies
(so the dashboard's insights have something to find).

Usage (from the project root):
    python scripts/generate_sample_data.py                    # clean file -> data_samples/operations_clean.csv
    python scripts/generate_sample_data.py --messy            # dirty file for data-cleaning practice
    python scripts/generate_sample_data.py --days 90 --seed 7 --out my.csv

Then load it with the dashboard's "Import data (CSV)" panel (mode: Replace).
Only the standard library is needed. Same --seed = same data, so results are repeatable.
"""
import argparse
import csv
import random
from datetime import date, timedelta
from pathlib import Path

# id, name, category, base revenue/record, base cost/record, weekend multiplier, cost-budget drift
# drift > 1 means the entity systematically runs over its cost budget (baseline_target).
ENTITIES = [
    ("ENT-01", "Zone North 89011", "Logistics", 500, 120, 1.10, 1.02),
    ("ENT-02", "Zone West Central", "Express", 400, 95, 1.25, 1.00),
    ("ENT-03", "Downtown Corridor", "Fleet", 600, 140, 0.85, 1.28),
    ("ENT-04", "Henderson South", "Logistics", 480, 110, 1.05, 1.04),
    ("ENT-05", "Summerlin", "Express", 550, 125, 1.20, 0.97),
    ("ENT-06", "Strip Core", "Fleet", 720, 190, 1.35, 1.12),
    ("ENT-07", "North Las Vegas", "Logistics", 420, 105, 1.00, 1.01),
    ("ENT-08", "Spring Valley", "Express", 380, 90, 1.15, 0.99),
    ("ENT-09", "Airport Corridor", "Fleet", 650, 160, 0.95, 1.06),
    ("ENT-10", "Boulder Highway", "Logistics", 360, 100, 1.00, 1.18),
]

HEADER = ["fact_id", "record_date", "entity_id", "entity_name", "category", "revenue",
          "operational_cost", "units_processed", "duration_minutes", "status", "baseline_target"]


def generate(days: int, end: date, seed: int) -> list[dict]:
    rng = random.Random(seed)
    start = end - timedelta(days=days - 1)
    rows = []
    n = 0
    # A handful of injected problems, so insights/anomaly detection have real targets.
    anomaly_days = {start + timedelta(days=rng.randrange(days // 4, days)) for _ in range(max(2, days // 60))}
    anomaly_entities = {d: rng.choice(ENTITIES)[0] for d in sorted(anomaly_days)}  # sorted: set order is randomized per run

    for i in range(days):
        d = start + timedelta(days=i)
        weekend = d.weekday() >= 5
        growth = 1 + 0.12 * (i / max(days - 1, 1))  # ~12% growth over the period
        holiday = 0.6 if (d.month, d.day) in {(12, 25), (1, 1), (7, 4), (11, 26)} else 1.0
        for eid, name, cat, rev0, cost0, wk, drift in ENTITIES:
            rev = rev0 * growth * (wk if weekend else 1.0) * holiday * rng.gauss(1.0, 0.08)
            cost = cost0 * drift * (1 + 0.04 * (i / max(days - 1, 1))) * rng.gauss(1.0, 0.06)
            status = rng.choices(["Completed", "Delayed", "Cancelled"], [93, 5, 2])[0]
            if status == "Delayed":
                rev *= 0.9
                cost *= 1.1
            if status == "Cancelled":
                rev = 0.0
                cost *= 0.35
            if anomaly_entities.get(d) == eid:  # injected anomaly: cost spike + revenue crash
                cost *= 2.4
                rev *= 0.5
            units = max(0, round(rev / rng.uniform(8.5, 10.5))) if rev else 0
            duration = round(max(30, units * rng.uniform(4.6, 5.4) + rng.gauss(0, 12)))
            n += 1
            rows.append({
                "fact_id": f"F-{n:06d}", "record_date": d.isoformat(), "entity_id": eid,
                "entity_name": name, "category": cat, "revenue": round(max(rev, 0), 2),
                "operational_cost": round(max(cost, 0), 2), "units_processed": units,
                "duration_minutes": duration, "status": status, "baseline_target": cost0,
            })
    return rows


def make_messy(rows: list[dict], seed: int) -> list[dict]:
    """Corrupt a copy of the data in the ways real exports go wrong. Seeded, so repeatable."""
    rng = random.Random(seed + 1)
    out = []
    for r in rows:
        r = dict(r)
        roll = rng.random()
        if roll < 0.02:
            r["revenue"] = ""                                   # missing value
        elif roll < 0.035:
            r["operational_cost"] = "N/A"                       # text in a numeric column
        elif roll < 0.045:
            r["operational_cost"] = -abs(r["operational_cost"])  # impossible negative
        elif roll < 0.07:
            r["revenue"] = f"${r['revenue']:,.2f}"              # currency formatting
        if rng.random() < 0.05:
            y, m, d = r["record_date"].split("-")
            r["record_date"] = f"{m}/{d}/{y}"                   # different date format
        if rng.random() < 0.004:
            r["record_date"] = "2026-13-45"                     # impossible date
        if rng.random() < 0.05:
            r["category"] = rng.choice([r["category"].upper(), r["category"].lower() + " ", " " + r["category"]])
        if rng.random() < 0.02:
            r["entity_id"] = " " + r["entity_id"] + " "          # stray whitespace
        if rng.random() < 0.02:
            r["status"] = rng.choice(["completed", "COMPLETE", "Done", ""])  # inconsistent labels
        out.append(r)
        if rng.random() < 0.01:
            out.append(dict(r))                                  # exact duplicate row (same fact_id)
    rng.shuffle(out)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=365)
    ap.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 10, 6))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--messy", action="store_true", help="write a dirty file for data-cleaning practice")
    ap.add_argument("--out", type=Path, default=None)
    a = ap.parse_args()

    rows = generate(a.days, a.end_date, a.seed)
    if a.messy:
        rows = make_messy(rows, a.seed)
    out = a.out or Path(__file__).resolve().parent.parent / "data_samples" / (
        "operations_messy.csv" if a.messy else "operations_clean.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HEADER)
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows):,} rows to {out}")


if __name__ == "__main__":
    main()
