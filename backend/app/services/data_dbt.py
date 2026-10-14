"""dbt-lite: models written as SELECT statements that refer to each other with ref(), compiled into a dependency graph,
built in order in a private in-memory DuckDB, and checked with simple tests. Nothing here touches the app's own data."""
from __future__ import annotations

import csv
import io
import re
from collections import deque

import duckdb

MAX_MODELS, MAX_ROWS, MAX_CHARS = 30, 5000, 60000


class DataLabError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


_NAME = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")
_REF = re.compile(r"\{\{\s*ref\(\s*['\"]([A-Za-z0-9_]+)['\"]\s*\)\s*\}\}")


def _blocks(text: str, kind: str) -> dict[str, str]:
    out: dict[str, str] = {}
    cur = None
    for ln in (text or "").splitlines():
        m = re.match(rf"^\s*--\s*{kind}\s*:\s*(\S+)\s*$", ln, re.I)
        if m:
            cur = m.group(1)
            if not _NAME.match(cur):
                raise DataLabError(f"'{cur}' is not a valid name. Use lowercase letters, digits and underscores.")
            if cur in out:
                raise DataLabError(f"'{cur}' is defined twice.")
            out[cur] = ""
        elif cur is not None:
            out[cur] += ln + "\n"
    return out


def _typed(vals: list[str]):
    out = []
    for kind in (int, float):
        try:
            out = [None if v == "" else kind(v) for v in vals]
            return ("BIGINT" if kind is int else "DOUBLE"), out
        except ValueError:
            continue
    return "VARCHAR", [None if v == "" else v for v in vals]


def _load_seed(con, name: str, body: str):
    rows = list(csv.reader(io.StringIO(body.strip())))
    if len(rows) < 1 or not rows[0]:
        raise DataLabError(f"Seed '{name}' needs a header line and rows of comma-separated values.")
    head = [h.strip() for h in rows[0]]
    if not all(_NAME.match(h) for h in head) or len(set(head)) != len(head):
        raise DataLabError(f"Seed '{name}': column names must be unique lowercase words (letters, digits, underscore).")
    data = rows[1:]
    if len(data) > MAX_ROWS or any(len(r) != len(head) for r in data):
        raise DataLabError(f"Seed '{name}': every row needs {len(head)} values and there can be at most {MAX_ROWS} rows.")
    cols = [_typed([r[i].strip() for r in data]) for i in range(len(head))]
    con.execute(f'CREATE TABLE "{name}" (' + ", ".join(f'"{h}" {c[0]}' for h, c in zip(head, cols)) + ")")
    if data:
        con.executemany(f'INSERT INTO "{name}" VALUES (' + ",".join("?" * len(head)) + ")", [tuple(c[1][i] for c in cols) for i in range(len(data))])


def _is_select(con, sql: str) -> bool:
    try:
        st = con.extract_statements(sql)
    except Exception as e:
        raise DataLabError(f"The SQL could not be read: {str(e)[:300]}") from None
    return len(st) == 1 and st[0].type == duckdb.StatementType.SELECT


def run(seeds: str, models: str, tests: str = "") -> dict:
    if len(seeds or "") + len(models or "") + len(tests or "") > MAX_CHARS:
        raise DataLabError("Too much text; keep it under 60,000 characters.")
    sd, md = _blocks(seeds, "seed"), _blocks(models, "model")
    if not md:
        raise DataLabError("Write at least one model, starting with a line like  -- model: stg_orders")
    if len(md) > MAX_MODELS:
        raise DataLabError(f"At most {MAX_MODELS} models.")
    clash = set(sd) & set(md)
    if clash:
        raise DataLabError(f"'{sorted(clash)[0]}' is both a seed and a model.")
    deps = {}
    for n, sql in md.items():
        if not sql.strip():
            raise DataLabError(f"Model '{n}' is empty.")
        d = []
        for r in _REF.findall(sql):
            if r not in sd and r not in md:
                raise DataLabError(f"Model '{n}' uses ref('{r}'), but there is no seed or model with that name.")
            if r == n:
                raise DataLabError(f"Model '{n}' refers to itself.")
            if r not in d:
                d.append(r)
        if re.search(r"\{\{|\{%", _REF.sub("", sql)):
            raise DataLabError(f"Model '{n}' uses a template this tool does not support. Only ref('name') is supported.")
        deps[n] = d
    indeg = {n: sum(1 for x in deps[n] if x in md) for n in md}
    q = deque(sorted(n for n in md if indeg[n] == 0))
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for v in sorted(md):
            if u in deps[v]:
                indeg[v] -= 1
                if indeg[v] == 0:
                    q.append(v)
    if len(order) != len(md):
        raise DataLabError("The models depend on each other in a circle: " + ", ".join(sorted(set(md) - set(order))) + ". A model graph must have no cycles.")
    con = duckdb.connect(":memory:")
    try:
        con.execute("SET memory_limit='200MB'")
        con.execute("SET threads=1")
        for n, b in sd.items():
            _load_seed(con, n, b)
        con.execute("SET enable_external_access=false")
        built = []
        for n in order:
            sql = _REF.sub(lambda m: f'"{m.group(1)}"', md[n]).strip().rstrip(";")
            if not _is_select(con, sql):
                raise DataLabError(f"Model '{n}' must be a single SELECT statement.")
            try:
                con.execute(f'CREATE TABLE "{n}" AS {sql}')
                cur = con.execute(f'SELECT * FROM "{n}" LIMIT 10')
                cols = [c[0] for c in cur.description]
                rows = [[v if isinstance(v, (int, float, str, bool, type(None))) else str(v) for v in r] for r in cur.fetchall()]
                cnt = con.execute(f'SELECT count(*) FROM "{n}"').fetchone()[0]
            except duckdb.Error as e:
                raise DataLabError(f"Model '{n}' failed: {str(e)[:400]}") from None
            built.append({"model": n, "depends_on": deps[n], "compiled_sql": sql, "rows": cnt, "columns": cols, "preview": rows})
        res = _tests(con, tests, set(sd) | set(md))
    finally:
        con.close()
    down = {n: sorted(m for m in md if n in _closure(m, deps)) for n in list(sd) + list(md)}
    return {"order": order, "seeds": list(sd), "models": built, "tests": res, "tests_failed": sum(1 for t in res if not t["passed"]),
            "downstream": down,
            "lesson": "Each model is just a SELECT. ref() tells the tool which model must be built first, so the graph, the build order and the 'what breaks if I change this' answer all come from the SQL itself. Tests catch a wrong assumption before anyone builds a report on it."}


def _closure(n: str, deps: dict) -> set:
    seen, st = set(), list(deps.get(n, []))
    while st:
        x = st.pop()
        if x not in seen:
            seen.add(x)
            st.extend(deps.get(x, []))
    return seen


def _tests(con, text: str, known: set) -> list[dict]:
    res = []
    for ln in (text or "").splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        m = re.match(r"^(\w+)\.(\w+)\s+(not_null|unique|accepted_values|relationships)\s*(?:\((.*)\))?$", ln) or re.match(r"^(\w+)\s+(row_count_min)\s*\((\d+)\)$", ln)
        if not m:
            raise DataLabError(f"Test '{ln}': use 'model.column not_null', 'model.column unique', 'model.column accepted_values(a,b)', 'model.column relationships(other.column)' or 'model row_count_min(1)'.")
        g = m.groups()
        model = g[0]
        if model not in known:
            raise DataLabError(f"Test '{ln}': there is no model or seed named '{model}'.")
        try:
            if g[1] == "row_count_min":
                n = con.execute(f'SELECT count(*) FROM "{model}"').fetchone()[0]
                res.append({"test": ln, "passed": n >= int(g[2]), "failing": 0 if n >= int(g[2]) else int(g[2]) - n, "detail": f"{n} rows"})
                continue
            col, kind, arg = g[1], g[2], g[3]
            q = f'"{col}"'
            if kind == "not_null":
                f = con.execute(f'SELECT count(*) FROM "{model}" WHERE {q} IS NULL').fetchone()[0]
            elif kind == "unique":
                f = con.execute(f'SELECT coalesce(sum(c - 1), 0) FROM (SELECT count(*) c FROM "{model}" WHERE {q} IS NOT NULL GROUP BY {q} HAVING count(*) > 1)').fetchone()[0]
            elif kind == "accepted_values":
                vals = [v.strip().strip("'\"") for v in (arg or "").split(",") if v.strip()]
                if not vals:
                    raise DataLabError(f"Test '{ln}': give the allowed values.")
                f = con.execute(f'SELECT count(*) FROM "{model}" WHERE {q} IS NOT NULL AND CAST({q} AS VARCHAR) NOT IN ({",".join("?" * len(vals))})', vals).fetchone()[0]
            else:
                om = re.match(r"^(\w+)\.(\w+)$", (arg or "").strip())
                if not om or om.group(1) not in known:
                    raise DataLabError(f"Test '{ln}': relationships needs other_model.column.")
                f = con.execute(f'SELECT count(*) FROM "{model}" a WHERE a.{q} IS NOT NULL AND NOT EXISTS (SELECT 1 FROM "{om.group(1)}" b WHERE b."{om.group(2)}" = a.{q})').fetchone()[0]
        except duckdb.Error as e:
            raise DataLabError(f"Test '{ln}' could not run: {str(e)[:200]}") from None
        res.append({"test": ln, "passed": f == 0, "failing": int(f), "detail": "all rows pass" if f == 0 else f"{int(f)} row(s) break the rule"})
    return res


SAMPLE = {"seeds": "-- seed: raw_orders\nid,customer_id,amount,status\n1,10,25.5,paid\n2,11,40,paid\n3,10,15,refunded\n4,12,,paid\n4,12,30,shipped\n-- seed: raw_customers\nid,name\n10,Ana\n11,Ben\n",
          "models": "-- model: stg_orders\nselect id as order_id, customer_id, amount, status from {{ ref('raw_orders') }}\n-- model: fct_customer_sales\nselect c.name, count(*) as orders, sum(o.amount) as total\nfrom {{ ref('stg_orders') }} o join {{ ref('raw_customers') }} c on c.id = o.customer_id\ngroup by c.name\n",
          "tests": "stg_orders.order_id unique\nstg_orders.amount not_null\nstg_orders.status accepted_values(paid,refunded)\nstg_orders.customer_id relationships(raw_customers.id)\nfct_customer_sales row_count_min(2)"}

SLIPS = ["Intro posts call dbt a database or an ETL tool. It only runs SQL you write inside a database that already holds the data (the T of ELT).",
         "Many examples run unique and not_null tests only on id columns. A passing test shows one rule holds, not that the data is right."]
NOT_BUILT = ["Real dbt: macros, Jinja loops, incremental models, snapshots, packages, docs site and a connection to your warehouse. Use dbt-core for that.", "Models read only the seeds you paste here, not the app's own tables."]


def reference() -> dict:
    from app.services import data_calc, data_flow
    return {"samples": {"dbt": SAMPLE, "calc": data_calc.SAMPLE, "dag": data_flow.DAG_SAMPLE, "stream": data_flow.STREAM_SAMPLE, "cron": "30 2 * * 1-5"},
            "slips": SLIPS + data_calc.SLIPS + data_flow.SLIPS, "not_built": NOT_BUILT + data_calc.NOT_BUILT + data_flow.NOT_BUILT}
