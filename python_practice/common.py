"""Shared helpers for the practice scripts.

load_operations() returns the same tidy DataFrame whether the dashboard's API is running
(it downloads the data from http://localhost:8020) or not (it reads/creates data_samples/operations_clean.csv).
That also sidesteps DuckDB's one-process-at-a-time file lock: scripts never open the .duckdb file.
"""
import io
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import matplotlib
import pandas as pd

if "ipykernel" not in sys.modules:  # scripts write PNG files; notebooks keep their inline charts
    matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "_out"
OUT.mkdir(exist_ok=True)
API = os.environ.get("BI_API_URL", "http://localhost:8020")
SAMPLES = ROOT / "data_samples"


def ensure_sample(messy: bool = False) -> Path:
    path = SAMPLES / ("operations_messy.csv" if messy else "operations_clean.csv")
    if not path.exists():
        cmd = [sys.executable, str(ROOT / "scripts" / "generate_sample_data.py")] + (["--messy"] if messy else [])
        subprocess.run(cmd, check=True)
    return path


def _standardize(df: pd.DataFrame) -> pd.DataFrame:
    df = df.rename(columns={"cost_budget_per_record": "baseline_target"})
    df["record_date"] = pd.to_datetime(df["record_date"])
    if "profit" not in df:
        df["profit"] = df["revenue"] - df["operational_cost"]
    df["margin"] = df["profit"] / df["revenue"].where(df["revenue"] > 0)
    df["is_weekend"] = df["record_date"].dt.dayofweek >= 5
    df["day_name"] = df["record_date"].dt.day_name()
    keep = ["fact_id", "record_date", "entity_id", "entity_name", "category", "baseline_target", "revenue",
            "operational_cost", "profit", "margin", "units_processed", "duration_minutes", "status",
            "is_weekend", "day_name"]
    return df[[c for c in keep if c in df.columns]].sort_values(["record_date", "entity_id"]).reset_index(drop=True)


def load_operations(quiet: bool = False) -> pd.DataFrame:
    try:
        with urllib.request.urlopen(f"{API}/api/export/operations?format=csv", timeout=3) as r:
            df = pd.read_csv(io.BytesIO(r.read()))
        source = f"API at {API}"
    except Exception:
        df = pd.read_csv(ensure_sample())
        source = "data_samples/operations_clean.csv (API not reachable)"
    if not quiet:
        print(f"[data] {len(df):,} rows from {source}\n")
    return _standardize(df)


def daily_revenue(df: pd.DataFrame) -> pd.Series:
    """Total revenue per calendar day (a pandas Series indexed by date)."""
    return df.groupby("record_date")["revenue"].sum()


def banner(title: str) -> None:
    print("\n" + "=" * 78 + f"\n{title}\n" + "=" * 78)


def check(label: str, condition: bool, hint: str = "") -> bool:
    """Notebook self-check: prints a pass/fail line and never raises, so 'Run all' keeps going."""
    print(("PASS  " if condition else "TRY AGAIN  ") + label + ("" if condition or not hint else f"\n      hint: {hint}"))
    return bool(condition)
