"""Workflow builder: chain simple steps (filter, pick columns, new column, group, sort, limit) over one table.

It is our own small, free take on a visual workflow tool. You build the chain; the app writes the SQL and the equivalent pandas
code for you, runs it, and shows how many rows survive each step. Everything is checked against the table's real columns and every
value is passed as a bound parameter, so a workflow can only ever read: it cannot change or delete data. "Save as table" is the one
action that writes, and it writes a NEW imported table (it never touches a built-in one).
"""
from __future__ import annotations

import json
from decimal import Decimal

from app.config import MAX_TABLE_ROWS
from app.services import datasets, state
from app.services.db import get_cursor

MAX_STEPS = 12
PREVIEW_ROWS = 200
BUILTIN = ("fact_operations", "dim_entities", "v_operations_flat")
STEP_KINDS = ("filter", "select", "derive", "aggregate", "sort", "limit")
OPS = {"=": "=", "!=": "<>", ">": ">", ">=": ">=", "<": "<", "<=": "<="}
PD_OPS = {"=": "==", "!=": "!=", ">": ">", ">=": ">=", "<": "<", "<=": "<="}
ARITH = ("+", "-", "*", "/")
AGGS = {"sum": "SUM", "avg": "AVG", "min": "MIN", "max": "MAX", "count": "COUNT", "median": "MEDIAN", "distinct": "COUNT(DISTINCT"}
PD_AGGS = {"sum": "sum", "avg": "mean", "min": "min", "max": "max", "count": "count", "median": "median", "distinct": "nunique"}


class WorkflowError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


q = datasets.q


def _ws() -> str:
    from app.services import workspaces
    return workspaces.active()


def sources() -> list[dict]:
    out = [{"table": t, "label": t, "kind": "built-in"} for t in BUILTIN]
    out += [{"table": t["table_name"], "label": t["label"], "kind": "imported"} for t in datasets.list_tables()]
    return out


def _columns(table: str) -> dict[str, str]:
    allowed = {s["table"] for s in sources()}
    if table not in allowed:
        raise WorkflowError(f"'{table}' isn't a table you can use here. Pick one from the list.", 404)
    with get_cursor() as cur:
        rows = cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_schema='main' AND table_name = ? ORDER BY ordinal_position", [table]).fetchall()
    if not rows:
        raise WorkflowError(f"'{table}' has no columns.")
    return {r[0]: r[1] for r in rows}


def _need(cols: dict, name, what="column", kinds: tuple[str, ...] | None = None) -> str:
    if not isinstance(name, str) or name not in cols:
        raise WorkflowError(f"Unknown {what} '{name}'. Available: {', '.join(cols)}.")
    if kinds and datasets.kind_of(cols[name]) not in kinds:
        raise WorkflowError(f"'{name}' is {datasets.kind_of(cols[name])}; this step needs {' or '.join(kinds)}.")
    return name


def _num(v, what: str) -> float:
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise WorkflowError(f"{what} must be a number.") from None
    if f != f or f in (float("inf"), float("-inf")):
        raise WorkflowError(f"{what} must be a finite number.")
    return f


def _compile(steps: list[dict]) -> dict:
    """Validate and turn the steps into a chain of CTEs. Returns ctes [(name, sql)], params per step, output columns."""
    if not isinstance(steps, list) or not steps:
        raise WorkflowError("Add a source step first.")
    if len(steps) > MAX_STEPS + 1:
        raise WorkflowError(f"Use at most {MAX_STEPS} steps after the source.")
    src = steps[0]
    if not isinstance(src, dict) or src.get("kind") != "source":
        raise WorkflowError("The first step must be the source table.")
    table = src.get("table")
    cols = _columns(table)
    ctes = [("s0", f"SELECT * FROM {q(table)}", [])]
    pandas = [f"df = con.sql({json.dumps(f'SELECT * FROM {q(table)}')}).df()"]
    notes = [f"Start from table {table} ({len(cols)} columns)."]
    for i, st in enumerate(steps[1:], start=1):
        if not isinstance(st, dict) or st.get("kind") not in STEP_KINDS:
            raise WorkflowError(f"Step {i}: unknown step type. Use one of {', '.join(STEP_KINDS)}.")
        k, prev, params = st["kind"], f"s{i - 1}", []
        try:
            if k == "filter":
                c = _need(cols, st.get("column"))
                op = st.get("op")
                kind = datasets.kind_of(cols[c])
                if op in ("is_null", "not_null"):
                    cond = f"{q(c)} IS {'NOT ' if op == 'not_null' else ''}NULL"
                    pandas.append(f"df = df[df[{c!r}].{'notna' if op == 'not_null' else 'isna'}()]")
                    notes.append(f"Keep rows where {c} is {'filled' if op == 'not_null' else 'blank'}.")
                elif op == "contains":
                    v = str(st.get("value", ""))
                    if not v:
                        raise WorkflowError("Give a word to look for.")
                    cond = f"CAST({q(c)} AS VARCHAR) ILIKE ?"
                    params = [f"%{v}%"]
                    pandas.append(f"df = df[df[{c!r}].astype(str).str.contains({v!r}, case=False, regex=False)]")
                    notes.append(f"Keep rows where {c} contains '{v}'.")
                elif op in OPS:
                    raw = st.get("value")
                    if kind == "number":
                        val = _num(raw, f"The value for {c}")
                        cond, params = f"{q(c)} {OPS[op]} ?", [val]
                    elif kind == "date":
                        if not isinstance(raw, str) or not raw.strip():
                            raise WorkflowError(f"Give a date for {c}, like 2026-01-31.")
                        cond, params = f"{q(c)} {OPS[op]} CAST(? AS {cols[c]})", [raw.strip()]
                        val = raw.strip()
                    else:
                        val = str(raw if raw is not None else "")
                        cond, params = f"CAST({q(c)} AS VARCHAR) {OPS[op]} ?", [val]
                    shown = val if kind == "number" else repr(val)
                    pandas.append(f"df = df[df[{c!r}] {PD_OPS[op]} {shown}]" if kind != "date"
                                  else f"df = df[pd.to_datetime(df[{c!r}]) {PD_OPS[op]} pd.Timestamp({val!r})]")
                    notes.append(f"Keep rows where {c} {op} {val}.")
                else:
                    raise WorkflowError("Pick a comparison: =, !=, >, >=, <, <=, contains, is_null or not_null.")
                sql = f"SELECT * FROM {prev} WHERE {cond}"
            elif k == "select":
                want = st.get("columns")
                if not isinstance(want, list) or not want:
                    raise WorkflowError("Pick at least one column to keep.")
                want = list(dict.fromkeys(_need(cols, c) for c in want))
                sql = f"SELECT {', '.join(q(c) for c in want)} FROM {prev}"
                cols = {c: cols[c] for c in want}
                pandas.append(f"df = df[{want!r}]")
                notes.append(f"Keep only {', '.join(want)}.")
            elif k == "derive":
                name = datasets.slug(str(st.get("name") or ""), "new_column")
                if name in cols:
                    raise WorkflowError(f"A column called '{name}' already exists. Pick another name.")
                a = _need(cols, st.get("a"), "column", ("number",))
                op = st.get("op")
                if op not in ARITH:
                    raise WorkflowError("Pick +, -, * or /.")
                if st.get("b_column"):
                    b = _need(cols, st["b_column"], "column", ("number",))
                    rhs, rhs_py, params = q(b), f"df[{b!r}]", []
                    if op == "/":
                        rhs = f"NULLIF({q(b)}, 0)"
                    shown_b = b
                else:
                    bv = _num(st.get("b_value"), "The number")
                    if op == "/" and bv == 0:
                        raise WorkflowError("Can't divide by zero.")
                    rhs, rhs_py, params, shown_b = "?", repr(bv), [bv], str(bv)
                sql = f"SELECT *, {q(a)} {op} {rhs} AS {q(name)} FROM {prev}"
                cols = {**cols, name: "DOUBLE"}
                pandas.append(f"df[{name!r}] = df[{a!r}] {op} {rhs_py}" + ("   # division by 0 gives inf in pandas, NULL in SQL" if op == "/" else ""))
                notes.append(f"New column {name} = {a} {op} {shown_b}.")
            elif k == "aggregate":
                group = [_need(cols, g) for g in (st.get("group_by") or [])]
                measures = st.get("measures") or []
                if not measures:
                    raise WorkflowError("Add at least one measure (for example sum of revenue).")
                sel, out_cols, pd_named = [q(g) for g in group], {g: cols[g] for g in group}, []
                for m in measures:
                    agg = m.get("agg")
                    if agg not in AGGS:
                        raise WorkflowError(f"Unknown calculation '{agg}'. Use {', '.join(AGGS)}.")
                    col = m.get("column")
                    if col in (None, "", "*"):
                        if agg != "count":
                            raise WorkflowError("Only 'count' can run over all rows. Pick a column for the others.")
                        label, expr, typ = "rows", "COUNT(*)", "BIGINT"
                        pd_named.append(("rows", None, "size"))
                    else:
                        _need(cols, col, "column", ("number",) if agg in ("sum", "avg", "median") else None)
                        label = f"{agg}_{col}"[:60]
                        expr = f"COUNT(DISTINCT {q(col)})" if agg == "distinct" else f"{AGGS[agg]}({q(col)})"
                        typ = "BIGINT" if agg in ("count", "distinct") else ("DOUBLE" if agg in ("sum", "avg", "median") else cols[col])
                        pd_named.append((label, col, PD_AGGS[agg]))
                    if label in out_cols:
                        raise WorkflowError(f"Two outputs would both be called '{label}'. Remove the duplicate.")
                    sel.append(f"{expr} AS {q(label)}")
                    out_cols[label] = typ
                sql = f"SELECT {', '.join(sel)} FROM {prev}" + (f" GROUP BY {', '.join(q(g) for g in group)}" if group else "")
                cols = out_cols
                if group:
                    named = ", ".join(f"{n}=({c!r}, {a!r})" if c else f"{n}=({group[0]!r}, 'size')" for n, c, a in pd_named)
                    pandas.append(f"df = df.groupby({group!r}, as_index=False).agg({named})")
                else:
                    items = ", ".join(f"{n!r}: " + (f"len(df)" if not c else f"df[{c!r}].{a}()") for n, c, a in pd_named)
                    pandas.append(f"df = pd.DataFrame([{{{items}}}])")
                notes.append(("Group by " + ", ".join(group) + ": " if group else "Over all rows: ") + ", ".join(n for n, _, _ in pd_named) + ".")
            elif k == "sort":
                c = _need(cols, st.get("column"))
                desc = bool(st.get("desc"))
                sql = f"SELECT * FROM {prev} ORDER BY {q(c)} {'DESC' if desc else 'ASC'} NULLS LAST"
                pandas.append(f"df = df.sort_values({c!r}, ascending={not desc})")
                notes.append(f"Sort by {c}, {'largest first' if desc else 'smallest first'}.")
            else:  # limit
                n = int(_num(st.get("n"), "The row count"))
                if not 1 <= n <= 100_000:
                    raise WorkflowError("Row limit must be between 1 and 100,000.")
                sql = f"SELECT * FROM {prev} LIMIT {n}"
                pandas.append(f"df = df.head({n})")
                notes.append(f"Keep the first {n} rows.")
        except WorkflowError as e:
            raise WorkflowError(f"Step {i} ({k}): {e}", e.status) from e
        ctes.append((f"s{i}", sql, params))
    return {"ctes": ctes, "columns": cols, "pandas": pandas, "notes": notes}


def _lit(v) -> str:
    if isinstance(v, (int, float)):
        return repr(v)
    return "'" + str(v).replace("'", "''") + "'"


def _show_sql(ctes) -> str:
    parts = []
    for name, sql, params in ctes:
        for p in params:
            sql = sql.replace("?", _lit(p), 1)
        parts.append(f"{name} AS (\n  {sql}\n)")
    return "WITH " + ",\n".join(parts) + f"\nSELECT * FROM {ctes[-1][0]}"


def _with(ctes, upto: int):
    sub = ctes[:upto + 1]
    return "WITH " + ", ".join(f"{n} AS ({s})" for n, s, _ in sub), [p for _, _, ps in sub for p in ps]


def explain(steps: list[dict]) -> dict:
    c = _compile(steps)
    return {"sql": _show_sql(c["ctes"]), "pandas": "import duckdb, pandas as pd\ncon = duckdb.connect('bi_warehouse.duckdb', read_only=True)\n" + "\n".join(c["pandas"]),
            "notes": c["notes"], "columns": [{"name": n, "type": t, "kind": datasets.kind_of(t)} for n, t in c["columns"].items()]}


def run(steps: list[dict], limit: int = PREVIEW_ROWS) -> dict:
    c = _compile(steps)
    limit = max(1, min(int(limit), 1000))
    last = len(c["ctes"]) - 1
    with get_cursor() as cur:
        counts = []
        for i in range(len(c["ctes"])):
            w, ps = _with(c["ctes"], i)
            counts.append(cur.execute(f"{w} SELECT COUNT(*) FROM s{i}", ps).fetchone()[0])
        w, ps = _with(c["ctes"], last)
        res = cur.execute(f"{w} SELECT * FROM s{last} LIMIT {limit}", ps)
        names = [d[0] for d in res.description]
        rows = [[datasets._json(v) for v in r] for r in res.fetchall()]
    out = explain(steps)
    out.update({"rows": rows, "names": names, "row_counts": counts, "total_rows": counts[-1], "truncated": counts[-1] > len(rows)})
    return out


def save_as_table(steps: list[dict], name: str, replace: bool = False) -> dict:
    """Run the whole chain and store the result as a NEW imported table (visible in My data and the hub)."""
    c = _compile(steps)
    last = len(c["ctes"]) - 1
    w, ps = _with(c["ctes"], last)
    with get_cursor() as cur:
        res = cur.execute(f"{w} SELECT * FROM s{last} LIMIT {MAX_TABLE_ROWS + 1}", ps)
        header = [d[0] for d in res.description]
        data = res.fetchall()
    if not data:
        raise WorkflowError("The workflow returned no rows, so there is nothing to save.")
    if len(data) > MAX_TABLE_ROWS:
        raise WorkflowError(f"The result is larger than {MAX_TABLE_ROWS:,} rows. Add a limit or a filter.")
    rows = [[None if v is None else (format(v, "f") if isinstance(v, Decimal) else str(v)) for v in r] for r in data]
    mode = "create"
    if replace:
        # a pipeline re-runs the same workflow, so it may refresh ITS OWN table; it can never overwrite one you uploaded
        have = datasets.table_name_for(name)
        reg = next((t for t in datasets.list_tables() if t["table_name"] == have), None)
        if reg and reg["source"] != "workflow":
            raise WorkflowError(f"'{have}' was imported from {reg['source']}, not made by a workflow, so it won't be overwritten. Pick another name.", 409)
        mode = "replace" if reg else "create"
    try:
        out = datasets.import_rows(header, rows, name, mode, source="workflow")
    except datasets.DataError as e:
        raise WorkflowError(e.message, e.status) from e
    return out


# ---- saved workflows (per workspace, in the app-state file) ----
def list_saved() -> list[dict]:
    rows = state.rows("SELECT id, name, steps, updated_at FROM workflows WHERE workspace = ? ORDER BY updated_at DESC", (_ws(),))
    for r in rows:
        r["steps"] = json.loads(r["steps"])
    return rows


def save(name: str, steps: list[dict], wid: int | None = None) -> dict:
    name = (name or "").strip()[:80]
    if not name:
        raise WorkflowError("Give the workflow a name.")
    _compile(steps)                       # only valid workflows are saved
    now = state.now()
    if wid:
        if not state.one("SELECT id FROM workflows WHERE id = ? AND workspace = ?", (wid, _ws())):
            raise WorkflowError("No such saved workflow.", 404)
        state.run("UPDATE workflows SET name = ?, steps = ?, updated_at = ? WHERE id = ?", (name, json.dumps(steps), now, wid))
        return {"id": wid, "name": name}
    if len(list_saved()) >= 100:
        raise WorkflowError("You have 100 saved workflows. Delete some first.")
    cur = state.run("INSERT INTO workflows (workspace, name, steps, created_at, updated_at) VALUES (?,?,?,?,?)", (_ws(), name, json.dumps(steps), now, now))
    return {"id": int(cur.lastrowid), "name": name}


def delete(wid: int) -> None:
    if not state.one("SELECT id FROM workflows WHERE id = ? AND workspace = ?", (wid, _ws())):
        raise WorkflowError("No such saved workflow.", 404)
    state.run("DELETE FROM workflows WHERE id = ?", (wid,))
