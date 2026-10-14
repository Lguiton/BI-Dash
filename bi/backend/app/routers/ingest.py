"""CSV ingestion: validate everything first, then load atomically (all or nothing)."""
import csv
import hashlib
import io
import math
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse

from app.config import MAX_UPLOAD_BYTES, MAX_UPLOAD_ROWS
from app.services import state
from app.services.db import get_cursor

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

REQUIRED = ["record_date", "entity_id", "revenue", "operational_cost", "units_processed"]
OPTIONAL = ["fact_id", "entity_name", "category", "baseline_target", "duration_minutes", "status"]
ALIASES = {
    "date": "record_date", "day": "record_date",
    "entity": "entity_id", "zone": "entity_id", "id": "entity_id",
    "name": "entity_name", "zone_name": "entity_name",
    "cost": "operational_cost", "costs": "operational_cost", "expenses": "operational_cost",
    "units": "units_processed", "volume": "units_processed",
    "duration": "duration_minutes", "minutes": "duration_minutes",
    "target": "baseline_target",
}
DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d")
MAX_REPORTED_ERRORS = 20

TEMPLATE = (
    "record_date,entity_id,entity_name,category,revenue,operational_cost,units_processed,duration_minutes,status,baseline_target\n"
    "2026-10-07,ENT-01,Zone North 89011,Logistics,505.00,118.00,51,255,Completed,120\n"
    "2026-10-07,ENT-02,Zone West Central,Express,410.00,101.00,43,220,Completed,95\n"
)


def _norm_header(h: str) -> str:
    key = h.strip().lower().replace(" ", "_").replace("-", "_")
    return ALIASES.get(key, key)


def _parse_date(s: str) -> date:
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    raise ValueError("unrecognized date (use YYYY-MM-DD or MM/DD/YYYY)")


def _parse_money(s: str, field: str, allow_empty=False) -> float | None:
    s = s.strip().replace("$", "").replace(",", "")
    if s == "":
        if allow_empty:
            return None
        raise ValueError(f"{field} is required")
    v = float(s)  # ValueError -> caught by caller
    if not math.isfinite(v):
        raise ValueError(f"{field} must be a finite number")
    return v


def _parse_int(s: str, field: str, allow_empty=False) -> int | None:
    s = s.strip().replace(",", "")
    if s == "":
        if allow_empty:
            return None
        raise ValueError(f"{field} is required")
    v = float(s)
    if not math.isfinite(v) or v != int(v):
        raise ValueError(f"{field} must be a whole number")
    return int(v)


def parse_csv(text: str) -> tuple[list[dict], dict[str, dict], list[str]]:
    """Return (fact rows, entity attributes by id, error messages)."""
    reader = csv.reader(io.StringIO(text))
    try:
        raw_header = next(reader)
    except StopIteration:
        return [], {}, ["The file is empty."]
    header = [_norm_header(h) for h in raw_header]
    missing = [c for c in REQUIRED if c not in header]
    if missing:
        return [], {}, [f"Missing required column(s): {', '.join(missing)}. "
                        f"Found: {', '.join(h for h in header if h) or '(none)'}."]
    dupes = {h for h in header if h and header.count(h) > 1}
    if dupes:
        return [], {}, [f"Duplicate column(s) after normalizing names: {', '.join(sorted(dupes))}."]

    facts: list[dict] = []
    entities: dict[str, dict] = {}
    errors: list[str] = []
    seen_ids: dict[str, int] = {}
    occurrences: dict[str, int] = {}

    for line_no, row in enumerate(reader, start=2):
        if not any(c.strip() for c in row):
            continue  # skip blank lines
        if len(facts) + len(errors) >= MAX_UPLOAD_ROWS:
            errors.append(f"Too many rows (limit {MAX_UPLOAD_ROWS:,}).")
            break
        rec = {h: (row[i] if i < len(row) else "") for i, h in enumerate(header) if h}
        try:
            record_date = _parse_date(rec["record_date"])
            entity_id = rec["entity_id"].strip()
            if not entity_id:
                raise ValueError("entity_id is required")
            revenue = _parse_money(rec["revenue"], "revenue")
            cost = _parse_money(rec["operational_cost"], "operational_cost")
            if revenue < 0 or cost < 0:
                raise ValueError("revenue and operational_cost cannot be negative")
            units = _parse_int(rec["units_processed"], "units_processed")
            if units < 0:
                raise ValueError("units_processed cannot be negative")
            duration = _parse_int(rec.get("duration_minutes", ""), "duration_minutes", allow_empty=True)
            if duration is not None and duration < 0:
                raise ValueError("duration_minutes cannot be negative")
            baseline = _parse_money(rec.get("baseline_target", ""), "baseline_target", allow_empty=True)
        except ValueError as e:
            msg = str(e)
            if msg.startswith("could not convert"):
                msg = f"not a valid number ({msg.split(': ')[-1]})"
            errors.append(f"Line {line_no}: {msg}")
            continue

        status = rec.get("status", "").strip() or "Completed"
        fact_id = rec.get("fact_id", "").strip()
        if fact_id:
            if fact_id in seen_ids:
                errors.append(f"Line {line_no}: duplicate fact_id '{fact_id}' (first used on line {seen_ids[fact_id]}).")
                continue
            seen_ids[fact_id] = line_no
        else:
            # Deterministic id so re-uploading the same file is idempotent.
            sig = f"{record_date}|{entity_id}|{revenue}|{cost}|{units}|{duration}|{status}"
            n = occurrences.get(sig, 0)
            occurrences[sig] = n + 1
            fact_id = "auto-" + hashlib.sha1(f"{sig}|{n}".encode()).hexdigest()[:12]

        facts.append((fact_id, record_date, entity_id, revenue, cost, units, duration, status))

        ent = entities.setdefault(entity_id, {})
        if rec.get("entity_name", "").strip():
            ent["name"] = rec["entity_name"].strip()
        if rec.get("category", "").strip():
            ent["category"] = rec["category"].strip()
        if baseline is not None:
            ent["baseline_target"] = baseline

    if not facts and not errors:
        errors.append("The file has a header but no data rows.")
    return facts, entities, errors


@router.get("/template", response_class=PlainTextResponse)
def download_template():
    return PlainTextResponse(
        TEMPLATE, media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="bi_upload_template.csv"'},
    )


class IngestError(Exception):
    """The file was rejected before anything was written. `errors` are line-numbered messages safe to show."""
    def __init__(self, message: str, errors: list[str] | None = None, truncated: bool = False):
        super().__init__(message)
        self.message, self.errors, self.truncated = message, errors or [], truncated


def load_operations_text(text: str, mode: str) -> dict:
    """Validate CSV text in the operations layout, then load it all-or-nothing. Shared by the upload, the mapping wizard and sources."""
    facts, entities, errors = parse_csv(text)
    if errors:
        raise IngestError(f"Nothing was imported. {len(errors)} problem(s) found.", errors[:MAX_REPORTED_ERRORS], len(errors) > MAX_REPORTED_ERRORS)

    with get_cursor() as cur:
        cur.execute("BEGIN TRANSACTION")
        try:
            if mode == "replace":
                cur.execute("DELETE FROM fact_operations")
                cur.execute("DELETE FROM dim_entities")
            existing = {r[0] for r in cur.execute("SELECT entity_id FROM dim_entities").fetchall()}
            entities_created = 0
            for eid, attrs in entities.items():
                if eid in existing:
                    sets = {k: v for k, v in attrs.items()}
                    if sets:
                        assigns = ", ".join(f"{k} = ?" for k in sets)  # keys come from our own fixed set
                        cur.execute(f"UPDATE dim_entities SET {assigns} WHERE entity_id = ?", [*sets.values(), eid])
                else:
                    entities_created += 1
                    cur.execute(
                        "INSERT INTO dim_entities VALUES (?, ?, ?, ?)",
                        [eid, attrs.get("name", eid), attrs.get("category", "Uncategorized"), attrs.get("baseline_target")],
                    )
            ids = [f[0] for f in facts]
            already = 0
            if mode == "append" and ids:
                already = cur.execute(
                    "SELECT COUNT(*) FROM fact_operations WHERE fact_id IN (SELECT UNNEST(?))", [ids]
                ).fetchone()[0]
            cur.executemany("INSERT OR REPLACE INTO fact_operations VALUES (?, ?, ?, ?, ?, ?, ?, ?)", facts)
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise

    return {
        "mode": mode,
        "rows_loaded": len(facts),
        "rows_updated": already,
        "rows_new": len(facts) - already,
        "entities_created": entities_created,
        "date_min": str(min(f[1] for f in facts)),
        "date_max": str(max(f[1] for f in facts)),
    }


@router.post("/csv")
async def upload_csv(
    file: UploadFile = File(...),
    mode: Literal["append", "replace"] = Query(
        "append",
        description="append: add/update rows by fact_id. replace: wipe all existing data first.",
    ),
):
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(400, {"message": "File is not UTF-8 text. Export as CSV (UTF-8) and retry.", "errors": []})
    if mode == "replace":
        from app.services import backups
        backups.safety_backup("before-replace-import")
    try:
        res = load_operations_text(text, mode)
    except IngestError as e:
        state.audit("import_operations", f"{file.filename}: rejected, {len(e.errors)} problem(s)", ok=False)
        raise HTTPException(400, {"message": e.message, "errors": e.errors, "truncated": e.truncated})
    state.audit("import_operations", f"{file.filename}: {res['rows_loaded']} rows ({mode})")
    return res
