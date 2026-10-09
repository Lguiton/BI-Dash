"""Worked solution for 03_clean_messy_data.py. Try the exercise first."""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

STATUS = {"completed": "Completed", "complete": "Completed", "done": "Completed", "": "Completed",
          "delayed": "Delayed", "cancelled": "Cancelled", "canceled": "Cancelled"}


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = raw.copy()

    # FIX: whitespace and inconsistent labels (cheap to repair, no information lost)
    for c in ["fact_id", "entity_id", "entity_name", "category", "status"]:
        df[c] = df[c].str.strip()
    df["category"] = df["category"].str.capitalize()
    df["status"] = df["status"].str.lower().map(STATUS)

    # FIX: money formatting ("$1,200.50") -> numbers; unparseable text ("N/A") becomes NaN
    for c in ["revenue", "operational_cost", "baseline_target"]:
        df[c] = pd.to_numeric(df[c].str.replace(r"[$,]", "", regex=True), errors="coerce")
    for c in ["units_processed", "duration_minutes"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # FIX: two date formats -> one real date; impossible dates become NaT
    d1 = pd.to_datetime(df["record_date"], format="%Y-%m-%d", errors="coerce")
    d2 = pd.to_datetime(df["record_date"], format="%m/%d/%Y", errors="coerce")
    df["record_date"] = d1.fillna(d2)

    # DROP (quarantine): rows we cannot trust. Inventing a revenue figure would corrupt the KPIs.
    reasons = pd.Series("", index=df.index)
    reasons[df["record_date"].isna()] += "bad date; "
    reasons[df["revenue"].isna()] += "missing revenue; "
    reasons[df["operational_cost"].isna()] += "missing cost; "
    reasons[df["operational_cost"] < 0] += "negative cost; "
    reasons[df["revenue"] < 0] += "negative revenue; "
    reasons[df["units_processed"].isna()] += "missing units; "
    bad = reasons != ""
    rejected = raw[bad].assign(reject_reason=reasons[bad])

    # DEDUPLICATE: exact repeats of the same fact_id
    good = df[~bad].drop_duplicates(subset="fact_id", keep="first").copy()
    good["units_processed"] = good["units_processed"].astype(int)
    good["duration_minutes"] = good["duration_minutes"].round().astype("Int64")
    good["record_date"] = good["record_date"].dt.date
    return good.reset_index(drop=True), rejected.reset_index(drop=True)


if __name__ == "__main__":
    import importlib

    mod = importlib.import_module("03_clean_messy_data")
    mod.clean_data = clean_data  # run the exercise's own checker against this solution
    from common import OUT, ensure_sample

    raw = pd.read_csv(ensure_sample(messy=True), dtype=str, keep_default_na=False)
    clean, rejected = clean_data(raw)
    problems = mod.check(clean, raw)
    print(f"Clean {len(clean):,} | rejected {len(rejected):,} | problems: {problems or 'none'}")
    print(rejected["reject_reason"].value_counts().to_string())
    clean.assign(record_date=pd.to_datetime(clean["record_date"]).dt.strftime("%Y-%m-%d")).to_csv(OUT / "operations_cleaned.csv", index=False)
