"""Safe, read-only SQL execution for the SQL Lab, plus the graded exercises."""
import datetime as dt
import decimal
import re
import threading
import time
from dataclasses import dataclass

import duckdb

from app.services.db import _root, get_cursor

MAX_SQL_CHARS = 10_000
MAX_ROWS = 1000
TIMEOUT_SECONDS = 5.0

_EXPLAIN_OK = re.compile(r"^\s*explain\s+(analyze\s+)?(\([^)]*\)\s*)?(select|with|from|values|\()", re.IGNORECASE)


class SqlLabError(Exception):
    """A problem with the user's query, safe to show verbatim."""


def _clean_error(e: Exception) -> str:
    msg = str(e).strip()
    # DuckDB errors include a "LINE n:" caret diagram; keep it, it's useful for learning.
    return msg[:1500]


def validate_readonly(sql: str) -> str:
    sql = (sql or "").strip()
    if not sql:
        raise SqlLabError("Write a query first.")
    if len(sql) > MAX_SQL_CHARS:
        raise SqlLabError(f"Query is too long (limit {MAX_SQL_CHARS:,} characters).")
    try:
        stmts = _root().extract_statements(sql)
    except Exception as e:  # syntax errors surface here
        raise SqlLabError(_clean_error(e)) from None
    if len(stmts) != 1:
        raise SqlLabError("Run one statement at a time (remove the extra ';' statements).")
    kind = stmts[0].type
    if kind == duckdb.StatementType.SELECT:
        return sql
    if kind == duckdb.StatementType.EXPLAIN and _EXPLAIN_OK.match(sql):
        return sql  # EXPLAIN ANALYZE *executes* its query, so it must wrap a SELECT
    raise SqlLabError(
        "The lab is read-only: only SELECT queries (including WITH, DESCRIBE, SUMMARIZE and "
        "EXPLAIN SELECT) are allowed. To change data, use the CSV import."
    )


def _json_value(v):
    if v is None or isinstance(v, (bool, int, str)):
        return v
    if isinstance(v, float):
        return v if v == v and v not in (float("inf"), float("-inf")) else None
    if isinstance(v, decimal.Decimal):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime, dt.time)):
        return v.isoformat()
    if isinstance(v, dt.timedelta):
        return str(v)
    return str(v)


@dataclass
class QueryResult:
    columns: list[str]
    rows: list[list]
    row_count: int
    truncated: bool
    elapsed_ms: float


def run_query(sql: str, max_rows: int = MAX_ROWS, timeout: float | None = None) -> QueryResult:
    sql = validate_readonly(sql)
    timeout = TIMEOUT_SECONDS if timeout is None else timeout
    with get_cursor() as cur:
        timer = threading.Timer(timeout, cur.interrupt)
        timer.start()
        t0 = time.perf_counter()
        try:
            res = cur.execute(sql)
            columns = [d[0] for d in res.description]
            fetched = res.fetchmany(max_rows + 1)
        except duckdb.InterruptException:
            raise SqlLabError(f"Query cancelled: it ran longer than {timeout:g} seconds. Add filters or a LIMIT.") from None
        except Exception as e:
            raise SqlLabError(_clean_error(e)) from None
        finally:
            timer.cancel()
        elapsed = (time.perf_counter() - t0) * 1000
    truncated = len(fetched) > max_rows
    fetched = fetched[:max_rows]
    return QueryResult(columns, [[_json_value(v) for v in r] for r in fetched], len(fetched), truncated, round(elapsed, 1))


def get_schema() -> list[dict]:
    with get_cursor() as cur:
        rows = cur.execute(
            """
            SELECT t.table_name, t.table_type, c.column_name, c.data_type
            FROM information_schema.tables t
            JOIN information_schema.columns c USING (table_schema, table_name)
            WHERE t.table_schema = 'main' AND t.table_name <> 'app_meta'
            ORDER BY t.table_type, t.table_name, c.ordinal_position
            """
        ).fetchall()
        out: dict[str, dict] = {}
        for table, ttype, col, dtype in rows:
            o = out.setdefault(table, {"name": table, "kind": "view" if ttype == "VIEW" else "table", "columns": []})
            o["columns"].append({"name": col, "type": dtype})
        for o in out.values():
            o["row_count"] = cur.execute(f'SELECT COUNT(*) FROM "{o["name"]}"').fetchone()[0]
    return sorted(out.values(), key=lambda o: (o["kind"] != "table", o["name"]))


# ---------------------------------------------------------------------------
# Exercises. Each has a reference query; a learner's answer is graded by comparing
# its RESULT with the reference's result (column names and formatting don't matter).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Exercise:
    id: str
    title: str
    level: int  # 1 easy .. 3 hard
    concepts: list[str]
    prompt: str
    hint: str
    solution: str
    ordered: bool = False  # does row order matter for grading?


EXERCISES: list[Exercise] = [
    Exercise("totals", "Headline totals", 1, ["SUM", "aggregation"],
             "Return three numbers in one row: total revenue, total operational cost, and total profit (revenue minus cost) across all of fact_operations.",
             "SUM() collapses many rows into one. Profit is SUM(revenue - operational_cost).",
             "SELECT SUM(revenue) AS revenue, SUM(operational_cost) AS cost, SUM(revenue - operational_cost) AS profit\nFROM fact_operations"),
    Exercise("status-counts", "Records per status", 1, ["GROUP BY", "COUNT"],
             "How many records are there for each status? Return two columns: status and the count.",
             "Group by the column you want one row per value of, then COUNT(*).",
             "SELECT status, COUNT(*) AS records\nFROM fact_operations\nGROUP BY status"),
    Exercise("top-days", "Three best revenue days", 1, ["GROUP BY", "ORDER BY", "LIMIT"],
             "Return the 3 dates with the highest total revenue (across all entities that day): the date and that day's revenue, highest first.",
             "Aggregate per record_date, then ORDER BY the aggregate DESC and LIMIT 3.",
             "SELECT record_date, SUM(revenue) AS revenue\nFROM fact_operations\nGROUP BY record_date\nORDER BY revenue DESC\nLIMIT 3", ordered=True),
    Exercise("by-category", "Revenue and profit by category", 2, ["JOIN", "GROUP BY"],
             "Return each entity category with its total revenue and total profit. Category lives in dim_entities, so you need a JOIN.",
             "JOIN fact_operations f to dim_entities e ON f.entity_id = e.entity_id, then GROUP BY e.category.",
             "SELECT e.category, SUM(f.revenue) AS revenue, SUM(f.revenue - f.operational_cost) AS profit\nFROM fact_operations f\nJOIN dim_entities e ON f.entity_id = e.entity_id\nGROUP BY e.category"),
    Exercise("monthly", "Monthly revenue", 2, ["DATE_TRUNC", "GROUP BY", "ORDER BY"],
             "Return one row per calendar month with the first day of that month, total revenue and total profit, oldest month first.",
             "DATE_TRUNC('month', record_date) turns every date into the first of its month.",
             "SELECT DATE_TRUNC('month', record_date)::DATE AS month,\n       SUM(revenue) AS revenue,\n       SUM(revenue - operational_cost) AS profit\nFROM fact_operations\nGROUP BY 1\nORDER BY 1", ordered=True),
    Exercise("weekend", "Weekend vs weekday", 2, ["JOIN", "dim_date", "AVG"],
             "Using dim_date, compare weekends with weekdays: return is_weekend and the average revenue per record for each.",
             "Join fact_operations to dim_date on record_date = date_key, then GROUP BY is_weekend.",
             "SELECT d.is_weekend, AVG(f.revenue) AS avg_revenue\nFROM fact_operations f\nJOIN dim_date d ON f.record_date = d.date_key\nGROUP BY d.is_weekend"),
    Exercise("budget", "Who is over their cost budget?", 2, ["JOIN", "HAVING", "calculated columns"],
             "baseline_target is each entity's cost budget per record. Return entities whose average cost per record is above budget: entity name, average cost per record, budget, and percent over budget (e.g. 28.6). Biggest overrun first.",
             "AVG(operational_cost) vs baseline_target. Filter on an aggregate with HAVING, not WHERE.",
             "SELECT e.name, AVG(f.operational_cost) AS avg_cost, e.baseline_target AS budget,\n       (AVG(f.operational_cost) / e.baseline_target - 1) * 100 AS pct_over\nFROM fact_operations f\nJOIN dim_entities e ON f.entity_id = e.entity_id\nGROUP BY e.name, e.baseline_target\nHAVING AVG(f.operational_cost) > e.baseline_target\nORDER BY pct_over DESC", ordered=True),
    Exercise("below-avg-margin", "Entities below the overall margin", 3, ["subquery", "HAVING"],
             "Return the names of entities whose profit margin (total profit / total revenue) is lower than the margin of the whole business.",
             "Compute the overall margin in a scalar subquery and compare it in HAVING.",
             "SELECT e.name\nFROM fact_operations f\nJOIN dim_entities e ON f.entity_id = e.entity_id\nGROUP BY e.name\nHAVING SUM(f.revenue - f.operational_cost) / SUM(f.revenue) <\n       (SELECT SUM(revenue - operational_cost) / SUM(revenue) FROM fact_operations)"),
    Exercise("moving-avg", "7-day moving average", 3, ["window functions", "CTE", "frame clause"],
             "Return each date with its total revenue's 7-day moving average (the day itself plus the 6 days before it), oldest first. Columns: date, moving average.",
             "First build daily totals in a CTE. Then AVG(daily_revenue) OVER (ORDER BY record_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW).",
             "WITH daily AS (\n  SELECT record_date, SUM(revenue) AS revenue\n  FROM fact_operations\n  GROUP BY record_date\n)\nSELECT record_date,\n       AVG(revenue) OVER (ORDER BY record_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS moving_avg\nFROM daily\nORDER BY record_date", ordered=True),
    Exercise("rank-in-category", "Rank entities within each category", 3, ["window functions", "RANK", "PARTITION BY"],
             "For each category, rank its entities by total profit (1 = most profitable). Columns: category, entity name, total profit, rank. Order by category, then rank.",
             "Aggregate first (in a CTE), then RANK() OVER (PARTITION BY category ORDER BY profit DESC).",
             "WITH p AS (\n  SELECT e.category, e.name, SUM(f.revenue - f.operational_cost) AS profit\n  FROM fact_operations f\n  JOIN dim_entities e ON f.entity_id = e.entity_id\n  GROUP BY e.category, e.name\n)\nSELECT category, name, profit,\n       RANK() OVER (PARTITION BY category ORDER BY profit DESC) AS rnk\nFROM p\nORDER BY category, rnk", ordered=True),
    Exercise("running-profit", "Cumulative profit", 3, ["window functions", "running total"],
             "Return each date with that day's total profit and the running (cumulative) total of profit up to and including that day, oldest first.",
             "SUM(daily_profit) OVER (ORDER BY record_date) gives a running total.",
             "WITH daily AS (\n  SELECT record_date, SUM(revenue - operational_cost) AS profit\n  FROM fact_operations\n  GROUP BY record_date\n)\nSELECT record_date, profit,\n       SUM(profit) OVER (ORDER BY record_date) AS cumulative_profit\nFROM daily\nORDER BY record_date", ordered=True),
    Exercise("mom-growth", "Month-over-month growth", 3, ["LAG", "CTE", "growth rate"],
             "Return each month (first day), its revenue, and the percent change versus the previous month (NULL for the first month). Oldest first.",
             "LAG(revenue) OVER (ORDER BY month) fetches the previous month's value. Growth % = (this / previous - 1) * 100.",
             "WITH m AS (\n  SELECT DATE_TRUNC('month', record_date)::DATE AS month, SUM(revenue) AS revenue\n  FROM fact_operations\n  GROUP BY 1\n)\nSELECT month, revenue,\n       (revenue / LAG(revenue) OVER (ORDER BY month) - 1) * 100 AS growth_pct\nFROM m\nORDER BY month", ordered=True),
    Exercise("non-additive", "Margin: ratio of sums", 2, ["non-additive measures", "GROUP BY", "ratios"],
             "Margin % is a NON-additive measure: you must sum profit and sum revenue first, then divide. Return each category with its true margin percent (total profit / total revenue * 100). Do NOT average per-row margins.",
             "Divide the SUMs, not the rows: SUM(revenue - operational_cost) / SUM(revenue) * 100. AVG of per-row margins gives a different (wrong) answer whenever row sizes differ.",
             "SELECT e.category,\n       SUM(f.revenue - f.operational_cost) / SUM(f.revenue) * 100 AS margin_pct\nFROM fact_operations f\nJOIN dim_entities e ON f.entity_id = e.entity_id\nGROUP BY e.category"),
    Exercise("ytd", "Year-to-date revenue", 3, ["time intelligence", "YTD", "window functions"],
             "Time intelligence: for each date, return its total revenue and the year-to-date (YTD) revenue, which is the running total that restarts every January 1. Oldest first.",
             "Build daily totals in a CTE, then SUM(revenue) OVER (PARTITION BY YEAR(record_date) ORDER BY record_date). The PARTITION BY is what resets it each year.",
             "WITH daily AS (\n  SELECT record_date, SUM(revenue) AS revenue\n  FROM fact_operations\n  GROUP BY record_date\n)\nSELECT record_date, revenue,\n       SUM(revenue) OVER (PARTITION BY YEAR(record_date) ORDER BY record_date) AS ytd_revenue\nFROM daily\nORDER BY record_date", ordered=True),
    Exercise("dedupe", "Spot duplicates (data quality)", 2, ["data quality", "HAVING", "deduplication"],
             "Data prep: find (record_date, entity_id) combinations that appear more than once in fact_operations. Return the date, entity_id and how many times it appears. (On clean data this returns no rows, which is a good sign.)",
             "GROUP BY the business key, then HAVING COUNT(*) > 1.",
             "SELECT record_date, entity_id, COUNT(*) AS n\nFROM fact_operations\nGROUP BY record_date, entity_id\nHAVING COUNT(*) > 1"),
    Exercise("cost-spikes", "Hunt for cost spikes", 3, ["CTE", "JOIN", "anomaly detection"],
             "Find records where the cost was more than 2x that entity's own average cost per record. Return date, entity name and cost, ordered by date then entity name.",
             "Compute each entity's average cost in a CTE, join it back to the facts, and filter on cost > 2 * avg.",
             "WITH avg_cost AS (\n  SELECT entity_id, AVG(operational_cost) AS avg_cost\n  FROM fact_operations\n  GROUP BY entity_id\n)\nSELECT f.record_date, e.name, f.operational_cost\nFROM fact_operations f\nJOIN avg_cost a ON f.entity_id = a.entity_id\nJOIN dim_entities e ON f.entity_id = e.entity_id\nWHERE f.operational_cost > 2 * a.avg_cost\nORDER BY f.record_date, e.name", ordered=True),
]
EXERCISES.sort(key=lambda e: e.level)  # stable: easy -> hard, keeping the authored order within a level
EXERCISES_BY_ID = {e.id: e for e in EXERCISES}


def _norm(v):
    if isinstance(v, float):
        return round(v, 2)
    return v


def _norm_rows(rows: list[list], ordered: bool) -> list[tuple]:
    out = [tuple(_norm(v) for v in r) for r in rows]
    return out if ordered else sorted(out, key=lambda r: tuple((x is None, str(x)) for x in r))


def check_answer(ex: Exercise, user_sql: str) -> dict:
    """Run the learner's query and the reference, and compare the RESULTS."""
    user = run_query(user_sql, max_rows=5000)  # raises SqlLabError for bad/unsafe SQL
    ref = run_query(ex.solution, max_rows=5000)
    preview = {"columns": user.columns, "rows": user.rows[:10], "row_count": user.row_count}
    if len(user.columns) != len(ref.columns):
        return {"correct": False, "message": f"Your query returns {len(user.columns)} column(s); this exercise expects {len(ref.columns)}.", **preview}
    if user.row_count != ref.row_count:
        return {"correct": False, "message": f"Your query returns {user.row_count} row(s); expected {ref.row_count}.", **preview}
    a, b = _norm_rows(user.rows, ex.ordered), _norm_rows(ref.rows, ex.ordered)
    if a == b:
        return {"correct": True, "message": "Correct. Your result matches the reference answer.", **preview}
    if not ex.ordered and sorted(map(str, a)) != sorted(map(str, b)):
        msg = "Right shape, but some values differ. Check your aggregates, filters and joins."
    elif ex.ordered and sorted(map(str, a)) == sorted(map(str, b)):
        msg = "The right rows, but in the wrong order. Check your ORDER BY."
    else:
        msg = "Right shape, but some values differ. Check your aggregates, filters and joins."
    return {"correct": False, "message": msg, **preview}
