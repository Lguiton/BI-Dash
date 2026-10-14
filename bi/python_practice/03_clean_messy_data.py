"""03 - Data preparation exercise: clean a messy export.   (YOU write clean_data)

Setup:
    python ../scripts/generate_sample_data.py --messy     # makes data_samples/operations_messy.csv
Then complete clean_data() below and run:  python 03_clean_messy_data.py
The checker tells you what is still wrong. When it passes, your cleaned file imports into the dashboard.
A worked solution is in solutions/03_clean_messy_data_solution.py (try first!).

The problems in the file (all found in real-world exports):
  - revenue / operational_cost with "$" and thousands separators, "N/A" text, blanks, negative costs
  - dates in two formats, and some impossible dates (2026-13-45)
  - category typos in case/spacing ("LOGISTICS", " fleet"), entity_id with stray spaces
  - status written many ways ("completed", "COMPLETE", "Done", blank)
  - exact duplicate rows
Decide per problem: FIX it, DROP the row, or QUARANTINE it. Document why (an analyst's real job).
"""
import pandas as pd

from common import OUT, banner, ensure_sample

REQUIRED = ["fact_id", "record_date", "entity_id", "revenue", "operational_cost", "units_processed"]


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (clean_rows, rejected_rows). `raw` was read with dtype=str so nothing is silently converted.

    Tips: s.str.strip(), s.str.replace(r"[$,]", "", regex=True), pd.to_numeric(s, errors="coerce"),
          pd.to_datetime(s, format="%Y-%m-%d", errors="coerce"), df.drop_duplicates(subset=...)
    The returned clean_rows must have real dtypes: record_date as date, numbers as float/int.
    """
    raise NotImplementedError("Write clean_data(): see the tips in the docstring")


def check(clean: pd.DataFrame, raw: pd.DataFrame) -> list[str]:
    problems = []
    if clean[REQUIRED].isna().any().any():
        problems.append("Required columns still contain missing values")
    if clean["fact_id"].duplicated().any():
        problems.append("Duplicate fact_ids remain")
    if (clean["operational_cost"] < 0).any() or (clean["revenue"] < 0).any():
        problems.append("Negative revenue/cost remains")
    if not pd.api.types.is_datetime64_any_dtype(pd.to_datetime(clean["record_date"], errors="coerce")) or \
            pd.to_datetime(clean["record_date"], errors="coerce").isna().any():
        problems.append("Some record_dates are not valid dates")
    if clean["category"].nunique() > 3:
        problems.append(f"Category has {clean['category'].nunique()} spellings; expected 3 (Express, Fleet, Logistics)")
    if (clean["entity_id"] != clean["entity_id"].str.strip()).any() or clean["entity_id"].nunique() != 10:
        problems.append("entity_id still has stray whitespace (expected exactly 10 clean ids)")
    if set(clean["status"].unique()) - {"Completed", "Delayed", "Cancelled"}:
        problems.append("Status labels are not standardized to Completed / Delayed / Cancelled")
    if len(clean) < 0.9 * raw["fact_id"].nunique():
        problems.append("You dropped more than 10% of the unique records; most problems are fixable instead of droppable")
    return problems


if __name__ == "__main__":
    path = ensure_sample(messy=True)
    raw = pd.read_csv(path, dtype=str, keep_default_na=False)
    banner(f"Raw file: {len(raw):,} rows, {raw['fact_id'].nunique():,} unique fact_ids")
    clean, rejected = clean_data(raw)
    problems = check(clean, raw)
    print(f"Clean: {len(clean):,} rows | Rejected: {len(rejected):,} rows")
    if problems:
        print("\nNot there yet:")
        for p in problems:
            print("  x", p)
        raise SystemExit(1)
    out = OUT / "operations_cleaned.csv"
    clean.assign(record_date=pd.to_datetime(clean["record_date"]).dt.strftime("%Y-%m-%d")).to_csv(out, index=False)
    rejected.to_csv(OUT / "operations_rejected.csv", index=False)
    print(f"\nAll checks passed. Wrote {out}\nNow import it with the dashboard's 'Import data (CSV)' panel (Replace).")
