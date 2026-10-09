"""Download the warehouse in different file formats, for practice with other tools.

DuckDB allows only one process to open a database file for writing, so while the API is running,
Tableau / Python / Superset can't open the .duckdb file directly. These exports are the supported
way to get the data into other tools.
"""
import csv
import io
import json
import xml.etree.ElementTree as ET
from typing import Literal

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.services.db import fetch_all, get_cursor
from app.services.sql_lab import _json_value

router = APIRouter(prefix="/api/export", tags=["export"])

DATASETS = {
    "operations": ("v_operations_flat", "One row per fact with entity and date attributes already joined (what Tableau/Power BI prefer)."),
    "facts": ("fact_operations", "The raw fact table (star schema center)."),
    "entities": ("dim_entities", "The entity dimension table."),
    "dates": ("dim_date", "The generated date dimension."),
}
FORMATS = {
    "csv": "text/csv", "tsv": "text/tab-separated-values", "json": "application/json",
    "xml": "application/xml",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "parquet": "application/vnd.apache.parquet",
}


def _rows(table: str) -> tuple[list[str], list[dict]]:
    with get_cursor() as cur:
        rows = fetch_all(cur, f"SELECT * FROM {table} ORDER BY 1, 2" if table != "dim_entities" else f"SELECT * FROM {table} ORDER BY 1")
    cols = list(rows[0].keys()) if rows else []
    if not rows:
        with get_cursor() as cur:
            cols = [d[0] for d in cur.execute(f"SELECT * FROM {table} LIMIT 0").description]
    return cols, rows


def _delimited(cols, rows, delim: str) -> bytes:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delim, lineterminator="\n")
    w.writerow(cols)
    for r in rows:
        w.writerow(["" if r[c] is None else _json_value(r[c]) for c in cols])
    return buf.getvalue().encode("utf-8")


def _xml(name: str, cols, rows) -> bytes:
    root = ET.Element("dataset", {"name": name})
    for r in rows:
        el = ET.SubElement(root, "row")
        for c in cols:
            child = ET.SubElement(el, c)
            if r[c] is not None:
                child.text = str(_json_value(r[c]))
    return b'<?xml version="1.0" encoding="UTF-8"?>\n' + ET.tostring(root, encoding="utf-8")


def _xlsx(name: str, cols, rows) -> bytes:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError:
        raise HTTPException(501, "XLSX export needs openpyxl: pip install openpyxl")
    wb = Workbook()
    ws = wb.active
    ws.title = name[:31]
    ws.append(cols)
    for c in ws[1]:
        c.font = Font(bold=True)
    ws.freeze_panes = "A2"
    for r in rows:
        ws.append([r[c] for c in cols])  # native dates/numbers stay typed in Excel
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


def _parquet(cols, rows) -> bytes:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        raise HTTPException(501, "Parquet export needs pyarrow: pip install pyarrow")
    table = pa.Table.from_pylist(rows) if rows else pa.table({c: [] for c in cols})
    out = io.BytesIO()
    pq.write_table(table, out, compression="snappy")
    return out.getvalue()


@router.get("/datasets")
def list_datasets():
    return {"datasets": [{"id": k, "table": v[0], "description": v[1]} for k, v in DATASETS.items()],
            "formats": list(FORMATS)}


@router.get("/{dataset}")
def export_dataset(dataset: str, fmt: Literal["csv", "tsv", "json", "xml", "xlsx", "parquet"] = Query("csv", alias="format")):
    if dataset not in DATASETS:
        raise HTTPException(404, f"Unknown dataset. Choose one of: {', '.join(DATASETS)}")
    table = DATASETS[dataset][0]
    cols, rows = _rows(table)
    if fmt == "csv":
        body = _delimited(cols, rows, ",")
    elif fmt == "tsv":
        body = _delimited(cols, rows, "\t")
    elif fmt == "json":
        body = json.dumps([{c: _json_value(r[c]) for c in cols} for r in rows], indent=1).encode("utf-8")
    elif fmt == "xml":
        body = _xml(dataset, cols, rows)
    elif fmt == "xlsx":
        body = _xlsx(dataset, cols, rows)
    else:
        body = _parquet(cols, rows)
    return Response(body, media_type=FORMATS[fmt],
                    headers={"Content-Disposition": f'attachment; filename="bi_{dataset}.{fmt}"'})
