"""Lists and serves the starter Jupyter notebooks in python_practice/notebooks/ for the Python tab."""
import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/python", tags=["python"])
DIR = Path(__file__).resolve().parents[3] / "python_practice" / "notebooks"

CONCEPTS = {
    "00_start_here": ["Loading data", "info / describe"],
    "01_file_formats": ["CSV / TSV / JSON / XML / XLSX", "Parquet", "Typed vs untyped formats"],
    "02_pandas_explore": ["Additive vs non-additive measures", "Weighted margin", "Time intelligence"],
    "03_clean_messy_data": ["Data preparation", "Fix / drop / quarantine", "Data quality"],
    "04_etl_vs_elt": ["ETL vs ELT", "SQL inside the warehouse (DuckDB)"],
    "05_forecast": ["Predictive analytics", "Backtesting", "MAPE", "Seasonality"],
    "10_analyst_case_study": ["Cost vs budget", "Weighted margin", "Analyst write-up"],
    "11_hypothesis_testing": ["Welch t-test", "Permutation test", "Bootstrap CI", "Pseudo-replication"],
    "12_clustering_entities": ["KMeans", "Silhouette score", "PCA", "Segmentation"],
    "13_ml_regression": ["Time-based split", "Pipelines", "Leakage", "Permutation importance"],
    "14_ml_classification": ["Class imbalance", "Precision / recall / F1", "Threshold tuning"],
    "15_mlflow_tracking": ["Experiment tracking", "MLflow runs", "Reproducibility"],
    "06_visualization": ["Chart choice", "Z-pattern layout", "Design checks"],
    "07_spark": ["Apache Spark", "DataFrame API vs Spark SQL", "Lazy evaluation"],
}


def _meta(path: Path) -> dict:
    nb = json.loads(path.read_text(encoding="utf-8"))
    first_md = next((c for c in nb["cells"] if c["cell_type"] == "markdown"), None)
    lines = "".join(first_md["source"]).splitlines() if first_md else []
    title = lines[0].lstrip("# ").strip() if lines else path.stem
    summary = next((ln for ln in lines[1:] if ln.strip()), "")
    return {"file": path.name, "title": title, "summary": summary,
            "concepts": CONCEPTS.get(path.stem, []), "cells": len(nb["cells"]),
            "needs_java": path.stem == "07_spark"}


@router.get("/notebooks")
def notebooks():
    files = sorted(DIR.glob("*.ipynb"))
    return {"notebooks": [_meta(p) for p in files], "folder": "python_practice/notebooks"}


@router.get("/notebooks/{name}")
def download(name: str):
    # whitelist against the directory listing: no path traversal is possible
    match = next((p for p in DIR.glob("*.ipynb") if p.name == name), None)
    if not match:
        raise HTTPException(404, "Notebook not found.")
    return FileResponse(match, media_type="application/x-ipynb+json", filename=match.name)
