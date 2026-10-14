"""Slowly Changing Dimension (SCD) practice sandbox.

Two copies of the entity dimension are kept next to the real one:
  scd_type1  one row per entity; a change OVERWRITES the old value (history is lost)
  scd_type2  one row per entity *version* with valid_from / valid_to / is_current (history is kept)

Change an entity's category here and compare "revenue by category" under both: Type 1 rewrites the
past (all of an entity's history moves to the new category), Type 2 keeps old facts under the old
category because facts are joined on the date range that was valid when they happened.
Your real dim_entities table is never modified. Both tables are visible in SQL Lab for practice.
"""
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.db import fetch_all, get_cursor

router = APIRouter(prefix="/api/scd", tags=["scd"])

BEGINNING = "1900-01-01"
FOREVER = "9999-12-31"


def _create_tables(cur) -> None:
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS scd_type1 (
            entity_id VARCHAR PRIMARY KEY, name VARCHAR, category VARCHAR
        );
        CREATE TABLE IF NOT EXISTS scd_type2 (
            surrogate_key INTEGER PRIMARY KEY, entity_id VARCHAR, name VARCHAR, category VARCHAR,
            valid_from DATE, valid_to DATE, is_current BOOLEAN
        );
        """
    )


def _populate(cur) -> None:
    cur.execute(
        "INSERT INTO scd_type1 SELECT entity_id, name, category FROM dim_entities"
    )
    cur.execute(
        f"""
        INSERT INTO scd_type2
        SELECT ROW_NUMBER() OVER (ORDER BY entity_id), entity_id, name, category,
               DATE '{BEGINNING}', DATE '{FOREVER}', TRUE
        FROM dim_entities
        """
    )


def ensure_tables() -> None:
    """Create the sandbox tables; fill them from dim_entities if they are empty."""
    with get_cursor() as cur:
        _create_tables(cur)
        if cur.execute("SELECT COUNT(*) FROM scd_type1").fetchone()[0] == 0:
            _populate(cur)


def _state(cur) -> dict:
    t1 = fetch_all(cur, "SELECT entity_id, name, category FROM scd_type1 ORDER BY entity_id")
    t2 = fetch_all(
        cur,
        """SELECT surrogate_key, entity_id, name, category,
                  STRFTIME(valid_from, '%Y-%m-%d') AS valid_from, STRFTIME(valid_to, '%Y-%m-%d') AS valid_to, is_current
           FROM scd_type2 ORDER BY entity_id, valid_from""",
    )
    return {"type1": t1, "type2": t2, "beginning": BEGINNING, "forever": FOREVER}


@router.get("/state")
def state():
    ensure_tables()
    with get_cursor() as cur:
        return _state(cur)


class Change(BaseModel):
    entity_id: str = Field(min_length=1, max_length=64)
    new_category: str = Field(min_length=1, max_length=40)
    effective_date: date


@router.post("/change")
def change(body: Change):
    ensure_tables()
    cat = body.new_category.strip()
    if not cat:
        raise HTTPException(422, "Category can't be blank.")
    with get_cursor() as cur:
        cur.execute("BEGIN TRANSACTION")
        try:
            row = cur.execute(
                "SELECT surrogate_key, category, valid_from FROM scd_type2 WHERE entity_id = ? AND is_current",
                [body.entity_id],
            ).fetchone()
            if not row:
                raise HTTPException(404, f"Unknown entity '{body.entity_id}'.")
            sk, old_cat, valid_from = row
            if cat == old_cat:
                raise HTTPException(400, f"{body.entity_id} is already in '{cat}'.")
            if body.effective_date <= valid_from:
                raise HTTPException(
                    400, f"Effective date must be after the current version started ({valid_from}).")
            # Type 1: overwrite in place
            cur.execute("UPDATE scd_type1 SET category = ? WHERE entity_id = ?", [cat, body.entity_id])
            # Type 2: close the current version the day before, then insert the new version
            cur.execute(
                "UPDATE scd_type2 SET valid_to = ?, is_current = FALSE WHERE surrogate_key = ?",
                [body.effective_date - timedelta(days=1), sk],
            )
            new_sk = cur.execute("SELECT COALESCE(MAX(surrogate_key), 0) + 1 FROM scd_type2").fetchone()[0]
            cur.execute(
                f"""INSERT INTO scd_type2
                    SELECT ?, entity_id, name, ?, ?, DATE '{FOREVER}', TRUE FROM scd_type2 WHERE surrogate_key = ?""",
                [new_sk, cat, body.effective_date, sk],
            )
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
        return _state(cur)


@router.post("/reset")
def reset():
    """Throw away all changes and re-copy the current dim_entities."""
    with get_cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS scd_type1")
        cur.execute("DROP TABLE IF EXISTS scd_type2")
        _create_tables(cur)
        _populate(cur)
        return _state(cur)


@router.get("/compare")
def compare():
    """Revenue by category computed two ways. Same facts, different answers once something changed."""
    ensure_tables()
    with get_cursor() as cur:
        t1 = fetch_all(
            cur,
            """SELECT COALESCE(d.category, 'Unknown') AS category, ROUND(SUM(f.revenue), 2) AS revenue, COUNT(*) AS records
               FROM fact_operations f LEFT JOIN scd_type1 d ON f.entity_id = d.entity_id
               GROUP BY 1 ORDER BY 1""",
        )
        t2 = fetch_all(
            cur,
            """SELECT COALESCE(d.category, 'Unknown') AS category, ROUND(SUM(f.revenue), 2) AS revenue, COUNT(*) AS records
               FROM fact_operations f
               LEFT JOIN scd_type2 d ON f.entity_id = d.entity_id AND f.record_date BETWEEN d.valid_from AND d.valid_to
               GROUP BY 1 ORDER BY 1""",
        )
        versions = cur.execute("SELECT COUNT(*) - COUNT(DISTINCT entity_id) FROM scd_type2").fetchone()[0]
    cats = sorted({r["category"] for r in t1} | {r["category"] for r in t2})
    a = {r["category"]: r for r in t1}
    b = {r["category"]: r for r in t2}
    rows = []
    for c in cats:
        r1 = a.get(c, {"revenue": 0, "records": 0})
        r2 = b.get(c, {"revenue": 0, "records": 0})
        rows.append({"category": c, "type1_revenue": r1["revenue"], "type2_revenue": r2["revenue"],
                     "type1_records": r1["records"], "type2_records": r2["records"],
                     "difference": round(r1["revenue"] - r2["revenue"], 2)})
    return {"rows": rows, "changes_made": versions,
            "total_type1": round(sum(r["type1_revenue"] for r in rows), 2),
            "total_type2": round(sum(r["type2_revenue"] for r in rows), 2)}
