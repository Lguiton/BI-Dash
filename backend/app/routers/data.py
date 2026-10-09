"""My data: import any CSV/Excel/JSON file as a table, profile it, chart it, or map it onto the operations dashboards."""
import csv
import io
import json

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile

from app.config import MAX_TABLE_UPLOAD_BYTES
from app.routers import ingest
from app.services import backups, datasets, state

router = APIRouter(prefix="/api/data", tags=["data"])

OPS_FIELDS = [
    {"field": "record_date", "required": True, "hint": "The date of each record"},
    {"field": "entity_id", "required": True, "hint": "What the row belongs to (store, region, customer tier...)"},
    {"field": "revenue", "required": True, "hint": "Money in"},
    {"field": "operational_cost", "required": True, "hint": "Money out"},
    {"field": "units_processed", "required": True, "hint": "A count: orders, users, units"},
    {"field": "fact_id", "required": False, "hint": "Unique row id (made up if missing)"},
    {"field": "entity_name", "required": False, "hint": "Display name"},
    {"field": "category", "required": False, "hint": "Group for the entity"},
    {"field": "duration_minutes", "required": False, "hint": "Time taken"},
    {"field": "status", "required": False, "hint": "e.g. Completed"},
    {"field": "baseline_target", "required": False, "hint": "Target for the entity"},
]


async def _read(file: UploadFile) -> bytes:
    raw = await file.read(MAX_TABLE_UPLOAD_BYTES + 1)
    if len(raw) > MAX_TABLE_UPLOAD_BYTES:
        raise HTTPException(413, f"File is larger than {MAX_TABLE_UPLOAD_BYTES // (1024 * 1024)} MB.")
    return raw


def _guard(fn, *a, **k):
    try:
        return fn(*a, **k)
    except datasets.DataError as e:
        raise HTTPException(e.status, e.message) from e


def _suggest(header: list[str]) -> dict[str, str]:
    """Guess which source column feeds each operations field, using the same aliases as the strict importer."""
    out: dict[str, str] = {}
    for h in header:
        key = ingest._norm_header(h)
        if key in {f["field"] for f in OPS_FIELDS} and key not in out:
            out[key] = h
    return out


@router.post("/preview")
async def preview(file: UploadFile = File(...), sheet: str | None = Form(None)):
    raw = await _read(file)
    res = _guard(datasets.preview, raw, file.filename or "data.csv", sheet)
    res["operations"] = {"fields": OPS_FIELDS, "suggested": _suggest(res["header"])}
    return res


@router.post("/import")
async def import_table(file: UploadFile = File(...), table: str | None = Form(None), mode: str = Form("replace"), sheet: str | None = Form(None)):
    raw = await _read(file)
    name = file.filename or "data.csv"
    if mode == "replace":
        backups.safety_backup("before-table-replace")
    try:
        res = _guard(datasets.import_file, raw, name, table, mode, sheet)
    except HTTPException as e:
        state.audit("import_table", f"{name}: {e.detail}", ok=False)
        raise
    state.audit("import_table", f"{name} -> {res['table']}: {res['rows']} rows ({mode})")
    return res


@router.post("/map-operations")
async def map_operations(file: UploadFile = File(...), mapping: str = Form(...), defaults: str = Form("{}"),
                         mode: str = Form("append"), sheet: str | None = Form(None)):
    """Load any file into the operations dashboards by saying which column is which. Missing required fields can use a fixed value."""
    if mode not in ("append", "replace"):
        raise HTTPException(400, "mode must be append or replace.")
    try:
        mp, df = json.loads(mapping), json.loads(defaults)
    except ValueError as e:
        raise HTTPException(400, "mapping and defaults must be JSON objects.") from e
    raw = await _read(file)
    header, rows, _ = _guard(datasets.read_table, raw, file.filename or "data.csv", sheet)
    allowed = {f["field"] for f in OPS_FIELDS}
    index = {h: i for i, h in enumerate(header)}
    targets = []
    for f in OPS_FIELDS:
        name = f["field"]
        src = mp.get(name)
        if src and src not in index:
            raise HTTPException(400, f"Column '{src}' is not in the file.")
        if src or str(df.get(name, "")).strip() != "":
            targets.append((name, src, str(df.get(name, "")).strip()))
        elif f["required"]:
            raise HTTPException(400, f"'{name}' needs a source column or a fixed value.")
    if set(mp) - allowed or set(df) - allowed:
        raise HTTPException(400, "Unknown target field in mapping.")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([t[0] for t in targets])
    for r in rows:
        w.writerow([(r[index[src]] if src and r[index[src]] is not None else dflt) if src else dflt for _, src, dflt in targets])
    if mode == "replace":
        backups.safety_backup("before-replace-import")
    name = file.filename or "data.csv"
    try:
        res = ingest.load_operations_text(buf.getvalue(), mode)
    except ingest.IngestError as e:
        state.audit("import_operations", f"{name} (mapped): rejected, {len(e.errors)} problem(s)", ok=False)
        raise HTTPException(400, {"message": e.message, "errors": e.errors, "truncated": e.truncated}) from e
    state.audit("import_operations", f"{name} (mapped): {res['rows_loaded']} rows ({mode})")
    return res


@router.get("/tables")
def tables():
    return {"tables": datasets.list_tables()}


@router.get("/tables/{table}/profile")
def table_profile(table: str):
    return _guard(datasets.profile, table)


@router.get("/tables/{table}/rows")
def table_rows(table: str, limit: int = Query(20, ge=1, le=200), offset: int = Query(0, ge=0)):
    return _guard(datasets.sample_rows, table, limit, offset)


@router.delete("/tables/{table}")
def table_delete(table: str):
    backups.safety_backup("before-table-delete")
    _guard(datasets.delete_table, table)
    state.audit("delete_table", table)
    return {"deleted": table}


@router.get("/tables/{table}/chart")
def table_chart(table: str, kind: str = Query("aggregate"), x: str | None = None, y: str | None = None, agg: str = "sum",
                bucket: str | None = None, group: str | None = None, by: str | None = None, bins: int = 20, limit: int = 30):
    if kind == "aggregate":
        if not x:
            raise HTTPException(400, "x is required.")
        return _guard(datasets.aggregate, table, x, y, agg, bucket, group, limit)
    if kind == "histogram":
        if not x:
            raise HTTPException(400, "x is required.")
        return _guard(datasets.histogram, table, x, bins)
    if kind == "box":
        if not x:
            raise HTTPException(400, "x is required.")
        return _guard(datasets.box, table, x, by)
    if kind == "scatter":
        if not x or not y:
            raise HTTPException(400, "x and y are required.")
        return _guard(datasets.scatter, table, x, y)
    raise HTTPException(400, "kind must be aggregate, histogram, box or scatter.")
