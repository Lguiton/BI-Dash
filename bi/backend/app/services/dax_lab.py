"""DAX practice lab: a small, honest subset of DAX evaluated over a sample table (or your pasted CSV).

This is not the DAX engine. It parses a subset (aggregations, DIVIDE, arithmetic, CALCULATE with simple column
filters, measure references, IF/ROUND/ABS) and evaluates it with the filter-context rules of DAX: every output
row is a filter context, and CALCULATE filters on a column REPLACE the context's filter on that column. Anything
outside the subset is refused with the SQL pattern that does the same job. Nothing is ever executed except
read-only aggregate queries on an in-memory copy of the data.
"""
from __future__ import annotations

import csv
import io
import random
import re
from datetime import date

import duckdb


class DaxError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


MAX_ROWS, MAX_COLS, MAX_GROUPS, MAX_MEASURES, MAX_FORMULA = 5000, 15, 200, 12, 600


# ------------------------------------------------------------------ data
def sample_rows() -> list[dict]:
    rnd = random.Random(7)
    rows = []
    countries = {"USA": 1.3, "Australia": 1.0, "Singapore": 0.9, "UAE": 0.8, "UK": 0.7}
    cats = {"Air": 1.2, "Sea": 1.0, "Road": 0.8}
    for m in range(24):
        y, mo = 2024 + m // 12, m % 12 + 1
        season = 1 + 0.15 * (1 if mo in (11, 12) else 0) - 0.05 * (1 if mo in (2, 3) else 0)
        for c, cf in countries.items():
            for k, kf in cats.items():
                amt = round(2000 * cf * kf * season * (1 + 0.012 * m) * rnd.uniform(0.9, 1.1), 2)
                rows.append({"Date": date(y, mo, 1).isoformat(), "Country": c, "Category": k, "Amount": amt, "Cost": round(amt * rnd.uniform(0.55, 0.72), 2)})
    return rows


def _load(csv_text: str | None):
    con = duckdb.connect(":memory:")
    if csv_text and csv_text.strip():
        try:
            rows = list(csv.reader(io.StringIO(csv_text.strip())))
        except csv.Error as e:
            raise DaxError(f"Couldn't read that CSV: {e}") from None
        if len(rows) < 2:
            raise DaxError("The CSV needs a header row and at least one data row.")
        head = [h.strip() for h in rows[0]]
        if len(head) > MAX_COLS or len(rows) - 1 > MAX_ROWS or len(set(head)) != len(head) or any(not h for h in head):
            raise DaxError(f"Use unique, non-empty column names, at most {MAX_COLS} columns and {MAX_ROWS} rows.")
        cols = list(zip(*[(r + [""] * len(head))[:len(head)] for r in rows[1:]]))
        types = []
        for c in cols:
            vals = [v.strip() for v in c if v.strip() != ""]
            if vals and all(re.fullmatch(r"-?\d+", v) for v in vals):
                types.append("BIGINT")
            elif vals and all(re.fullmatch(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", v) for v in vals):
                types.append("DOUBLE")
            elif vals and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in vals):
                types.append("DATE")
            else:
                types.append("VARCHAR")
        con.execute("CREATE TABLE Data (" + ", ".join(f'"{h}" {t}' for h, t in zip(head, types)) + ")")
        for r in rows[1:]:
            r = (r + [""] * len(head))[:len(head)]
            try:
                con.execute("INSERT INTO Data VALUES (" + ",".join("?" * len(head)) + ")", [None if v.strip() == "" else v.strip() for v in r])
            except duckdb.Error as e:
                raise DaxError(f"A row doesn't fit its column type: {str(e)[:120]}") from None
        return con, "Data", dict(zip(head, types)), len(rows) - 1
    con.execute("CREATE TABLE Sales (\"Date\" DATE, \"Country\" VARCHAR, \"Category\" VARCHAR, \"Amount\" DOUBLE, \"Cost\" DOUBLE)")
    rs = sample_rows()
    con.executemany("INSERT INTO Sales VALUES (?,?,?,?,?)", [(r["Date"], r["Country"], r["Category"], r["Amount"], r["Cost"]) for r in rs])
    return con, "Sales", {"Date": "DATE", "Country": "VARCHAR", "Category": "VARCHAR", "Amount": "DOUBLE", "Cost": "DOUBLE"}, len(rs)


# ------------------------------------------------------------------ parser
_TOK = re.compile(r"""\s*(?:
    (?P<str>"(?:[^"]|"")*")
  | (?P<col>(?:'(?P<tq>[^']+)'|(?P<tn>[A-Za-z_][A-Za-z0-9_]*))\[(?P<cn>[^\]]+)\])
  | (?P<ref>\[(?P<rn>[^\]]+)\])
  | (?P<num>\d+(?:\.\d+)?)
  | (?P<id>[A-Za-z_][A-Za-z0-9_.]*)
  | (?P<op><>|>=|<=|&&|\|\||[-+*/(),=<>{}])
)""", re.X)

UNSUPPORTED = {
    "TOTALYTD": "SELECT month, SUM(x) OVER (PARTITION BY year ORDER BY month) FROM monthly (a running total that restarts each year).",
    "DATESYTD": "A window SUM(x) OVER (PARTITION BY year ORDER BY date).",
    "SAMEPERIODLASTYEAR": "LAG(total, 12) OVER (ORDER BY month) on monthly totals, or a self-join on date + INTERVAL 1 YEAR.",
    "DATEADD": "date + INTERVAL n unit in a self-join, or LAG() over the period.",
    "PARALLELPERIOD": "LAG(total, n) over the periods.",
    "FILTER": "A WHERE clause, or SUM(x) FILTER (WHERE ...). Inside CALCULATE use simple filters such as Sales[Country] = \"USA\".",
    "ALL": "Remove a GROUP BY or WHERE condition: compute the total in a separate subquery or window (SUM(x) OVER ()).",
    "ALLEXCEPT": "A window partitioned only by the columns you keep: SUM(x) OVER (PARTITION BY kept_cols).",
    "ALLSELECTED": "A window over the rows currently shown: SUM(x) OVER ().",
    "VALUES": "SELECT DISTINCT column FROM table.", "DISTINCT": "SELECT DISTINCT column FROM table.",
    "SELECTEDVALUE": "A scalar subquery, or the group-by column itself (it returns one value, not a table).",
    "SUMX": "SUM(expression) over rows: SELECT SUM(a * b) FROM t.", "AVERAGEX": "AVG(expression) over rows.", "COUNTX": "COUNT(expression) over rows.",
    "MAXX": "MAX(expression) over rows.", "MINX": "MIN(expression) over rows.", "RANKX": "RANK() OVER (ORDER BY measure DESC).",
    "RELATED": "A JOIN to the dimension table.", "RELATEDTABLE": "A JOIN from the dimension to the fact table.",
    "SWITCH": "CASE WHEN ... THEN ... END.", "VAR": "A CTE or a subquery that names the intermediate result.", "RETURN": "The final SELECT after your CTEs.",
    "CALCULATETABLE": "A subquery or CTE with the same WHERE.", "SUMMARIZE": "SELECT cols, aggregates FROM t GROUP BY cols.", "ADDCOLUMNS": "SELECT *, new_expression AS name FROM t.",
    "EARLIER": "A window function or a correlated subquery.", "USERELATIONSHIP": "A JOIN on the alternate key.", "CONCATENATE": "The || operator.", "FORMAT": "strftime() / printf().",
    "KEEPFILTERS": "An AND of the new condition with the existing WHERE.",
}
_AGGS = {"SUM", "AVERAGE", "MIN", "MAX", "COUNT", "DISTINCTCOUNT"}


def _tokens(src: str) -> list[tuple]:
    out, pos = [], 0
    src = src.strip()
    while pos < len(src):
        m = _TOK.match(src, pos)
        if not m or m.end() == pos:
            raise DaxError(f"I can't read the formula near '{src[pos:pos + 12]}'.")
        pos = m.end()
        if m.group("str") is not None:
            out.append(("str", m.group("str")[1:-1].replace('""', '"')))
        elif m.group("col") is not None:
            out.append(("col", m.group("tq") or m.group("tn"), m.group("cn")))
        elif m.group("ref") is not None:
            out.append(("ref", m.group("rn")))
        elif m.group("num") is not None:
            out.append(("num", float(m.group("num"))))
        elif m.group("id") is not None:
            out.append(("id", m.group("id")))
        else:
            out.append(("op", m.group("op")))
    return out


class _P:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def eat(self):
        self.i += 1
        return self.t[self.i - 1]

    def isop(self, *ops):
        t = self.peek()
        return t is not None and t[0] == "op" and t[1] in ops

    def expect(self, op):
        if not self.isop(op):
            raise DaxError(f"Expected '{op}' but found {self._show()}.")
        self.eat()

    def _show(self):
        t = self.peek()
        return "the end of the formula" if t is None else f"'{t[1] if t[0] in ('op', 'id') else t[0]}'"

    def parse(self):
        n = self.expr()
        if self.peek() is not None:
            raise DaxError(f"Unexpected {self._show()}. Check commas and brackets.")
        return n

    def expr(self):
        return self.or_()

    def or_(self):
        a = self.and_()
        while self.isop("||"):
            self.eat()
            a = ("or", a, self.and_())
        return a

    def and_(self):
        a = self.cmp()
        while self.isop("&&"):
            self.eat()
            a = ("and", a, self.cmp())
        return a

    def cmp(self):
        a = self.add()
        if self.isop("=", "<>", "<", ">", "<=", ">="):
            op = self.eat()[1]
            return ("cmp", op, a, self.add())
        t = self.peek()
        if t and t[0] == "id" and t[1].upper() == "IN":
            self.eat()
            self.expect("{")
            vals = []
            while True:
                vals.append(self.add())
                if self.isop(","):
                    self.eat()
                    continue
                break
            self.expect("}")
            return ("in", a, vals)
        return a

    def add(self):
        a = self.mul()
        while self.isop("+", "-"):
            op = self.eat()[1]
            a = ("bin", op, a, self.mul())
        return a

    def mul(self):
        a = self.unary()
        while self.isop("*", "/"):
            op = self.eat()[1]
            a = ("bin", op, a, self.unary())
        return a

    def unary(self):
        if self.isop("-"):
            self.eat()
            return ("neg", self.unary())
        if self.isop("+"):
            self.eat()
            return self.unary()
        return self.primary()

    def primary(self):
        t = self.peek()
        if t is None:
            raise DaxError("The formula ends too early.")
        if t[0] == "num":
            self.eat()
            return ("num", t[1])
        if t[0] == "str":
            self.eat()
            return ("str", t[1])
        if t[0] == "col":
            self.eat()
            return ("col", t[1], t[2])
        if t[0] == "ref":
            self.eat()
            return ("ref", t[1])
        if t[0] == "op" and t[1] == "(":
            self.eat()
            n = self.expr()
            self.expect(")")
            return n
        if t[0] == "id":
            self.eat()
            name = t[1].upper()
            if not self.isop("("):
                if name in ("TRUE", "FALSE"):
                    return ("num", 1.0 if name == "TRUE" else 0.0)
                if name == "BLANK":
                    return ("blank",)
                return ("table", t[1])
            self.eat()
            args = []
            if not self.isop(")"):
                while True:
                    args.append(self.expr())
                    if self.isop(","):
                        self.eat()
                        continue
                    break
            self.expect(")")
            if name == "BLANK":
                return ("blank",)
            return ("call", name, args)
        raise DaxError(f"Unexpected {self._show()}.")


def parse(src: str):
    if not src or not src.strip():
        raise DaxError("Write a formula first.")
    if len(src) > MAX_FORMULA:
        raise DaxError(f"Keep each formula under {MAX_FORMULA} characters.")
    s = src.strip()
    if re.match(r"^\s*(var|let)\b", s, re.I):
        raise DaxError("VAR/RETURN isn't supported here. " + UNSUPPORTED["VAR"])
    return _P(_tokens(s)).parse()


# ------------------------------------------------------------------ evaluation
class _Ctx:
    def __init__(self, con, table, cols):
        self.con, self.table, self.cols = con, table, cols
        self.measures: dict[str, tuple] = {}
        self.cache: dict = {}
        self.notes: list[str] = []
        self.stack: list[str] = []

    def col(self, node):
        _, tbl, c = node
        if tbl.lower() != self.table.lower():
            raise DaxError(f"Table '{tbl}' isn't loaded. This lab has one table: {self.table}.")
        for k in self.cols:
            if k.lower() == c.lower():
                return k
        raise DaxError(f"{self.table} has no column '{c}'. Columns: {', '.join(self.cols)}.")

    def numeric(self, c):
        return any(x in self.cols[c].upper() for x in ("INT", "DOUBLE", "DECIMAL", "FLOAT", "REAL"))

    def agg(self, fn, c, filt):
        where, params = [], []
        for key, (op, val) in sorted(filt.items()):
            lhs = f'year("{key[5:]}")' if key.startswith("YEAR:") else (f'month("{key[6:]}")' if key.startswith("MONTH:") else f'"{key}"')
            if op == "in":
                where.append(f"{lhs} IN ({','.join('?' * len(val))})")
                params += list(val)
            else:
                where.append(f"{lhs} {op} ?")
                params.append(val)
        w = (" WHERE " + " AND ".join(where)) if where else ""
        k = (fn, c, w, tuple(params))
        if k in self.cache:
            return self.cache[k]
        expr = {"SUM": f'SUM("{c}")', "AVERAGE": f'AVG("{c}")', "MIN": f'MIN("{c}")', "MAX": f'MAX("{c}")', "COUNT": f'COUNT("{c}")',
                "DISTINCTCOUNT": f'COUNT(DISTINCT "{c}")', "COUNTROWS": "COUNT(*)"}[fn]
        try:
            v = self.con.execute(f'SELECT {expr} FROM "{self.table}"{w}', params).fetchone()[0]
        except duckdb.Error as e:
            raise DaxError(f"The data refused that filter: {str(e)[:120]}") from None
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        if fn in ("COUNT", "DISTINCTCOUNT", "COUNTROWS") and v is None:
            v = 0
        self.cache[k] = v
        return v


def _lit(c: _Ctx, node, col):
    if node[0] == "num":
        v = node[1]
        return int(v) if v == int(v) and "INT" in c.cols[col].upper() else v
    if node[0] == "str":
        return node[1]
    if node[0] == "neg" and node[1][0] == "num":
        return -node[1][1]
    raise DaxError("A filter compares a column with a plain number or text, for example Sales[Country] = \"USA\".")


def _filters(c: _Ctx, node) -> dict:
    """Turn one CALCULATE filter argument into {column key: (op, value)}."""
    if node[0] == "and":
        a, b = _filters(c, node[1]), _filters(c, node[2])
        for k in b:
            if k in a:
                c.notes.append(f"Two filters on {k.split(':')[-1]} in one argument: the later one wins.")
        return {**a, **b}
    if node[0] == "or":
        a, b = _filters(c, node[1]), _filters(c, node[2])
        if len(a) == 1 and len(b) == 1 and list(a)[0] == list(b)[0] and all(v[0] in ("=", "in") for v in (*a.values(), *b.values())):
            k = list(a)[0]
            vals = [*(a[k][1] if a[k][0] == "in" else [a[k][1]]), *(b[k][1] if b[k][0] == "in" else [b[k][1]])]
            return {k: ("in", vals)}
        raise DaxError("OR across different columns isn't supported here. Use IN {...} for several values of one column.")
    if node[0] in ("cmp", "in"):
        lhs = node[2] if node[0] == "cmp" else node[1]
        key = None
        if lhs[0] == "col":
            key = c.col(lhs)
        elif lhs[0] == "call" and lhs[1] in ("YEAR", "MONTH") and len(lhs[2]) == 1 and lhs[2][0][0] == "col":
            key = f"{lhs[1]}:{c.col(lhs[2][0])}"
        if key is None:
            raise DaxError("Put a column (or YEAR/MONTH of a date column) on the left of the filter.")
        base = key.split(":")[-1]
        if node[0] == "in":
            return {key: ("in", [_lit(c, v, base) for v in node[2]])}
        op = {"=": "=", "<>": "<>", "<": "<", ">": ">", "<=": "<=", ">=": ">="}[node[1]]
        return {key: (op, _lit(c, node[3], base))}
    raise DaxError("A CALCULATE filter looks like Sales[Country] = \"USA\", Sales[Amount] > 1000 or Sales[Category] IN {\"Air\", \"Sea\"}.")


def _num(v):
    return 0.0 if v is None else v


def ev(c: _Ctx, node, ctx: dict):
    k = node[0]
    if k == "num":
        return node[1]
    if k == "str":
        return node[1]
    if k == "blank":
        return None
    if k == "neg":
        v = ev(c, node[1], ctx)
        return None if v is None else -v
    if k == "ref":
        name = next((m for m in c.measures if m.lower() == node[1].lower()), None)
        if name is None:
            raise DaxError(f"No measure named [{node[1]}]. Define it in the list above, or write a column as Table[Column].")
        if name in c.stack:
            raise DaxError("Measures refer to each other in a circle: " + " -> ".join([*c.stack, name]))
        c.stack.append(name)
        try:
            return ev(c, c.measures[name], ctx)
        finally:
            c.stack.pop()
    if k == "col":
        raise DaxError(f"{node[1]}[{node[2]}] on its own is a whole column. Wrap it in SUM(), AVERAGE(), MIN(), MAX(), COUNT() or DISTINCTCOUNT().")
    if k == "bin":
        a, b = ev(c, node[2], ctx), ev(c, node[3], ctx)
        op = node[1]
        if op in "+-":
            if a is None and b is None:
                return None
            a, b = _num(a), _num(b)
            return a + b if op == "+" else a - b
        if a is None or b is None:
            return None
        if op == "*":
            return a * b
        if b == 0:
            c.notes.append("A '/' divided by zero: DAX returns infinity or an error. Use DIVIDE(a, b) to get a blank instead.")
            return None
        return a / b
    if k in ("cmp", "in", "and", "or"):
        if k == "cmp":
            a, b = ev(c, node[2], ctx), ev(c, node[3], ctx)
            if a is None or b is None:
                return False if node[1] != "<>" else True
            return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[node[1]]
        if k == "and":
            return bool(ev(c, node[1], ctx)) and bool(ev(c, node[2], ctx))
        if k == "or":
            return bool(ev(c, node[1], ctx)) or bool(ev(c, node[2], ctx))
        raise DaxError("IN is only supported inside CALCULATE filters.")
    if k == "call":
        name, args = node[1], node[2]
        if name in _AGGS:
            if len(args) != 1 or args[0][0] != "col":
                raise DaxError(f"{name} takes one column, for example {name}(Sales[Amount]).")
            col = c.col(args[0])
            if name in ("SUM", "AVERAGE") and not c.numeric(col):
                raise DaxError(f"{name} needs a number column, but {col} is {c.cols[col]}.")
            return c.agg(name, col, ctx)
        if name == "COUNTROWS":
            if len(args) != 1 or args[0][0] != "table" or args[0][1].lower() != c.table.lower():
                raise DaxError(f"COUNTROWS takes the table name, for example COUNTROWS({c.table}).")
            return c.agg("COUNTROWS", next(iter(c.cols)), ctx)
        if name == "DIVIDE":
            if len(args) not in (2, 3):
                raise DaxError("DIVIDE(numerator, denominator [, alternate]).")
            a, b = ev(c, args[0], ctx), ev(c, args[1], ctx)
            alt = ev(c, args[2], ctx) if len(args) == 3 else None
            if b is None or b == 0:
                return alt
            return None if a is None else a / b
        if name == "CALCULATE":
            if not args:
                raise DaxError("CALCULATE(expression, filter, ...).")
            new = dict(ctx)
            for f in args[1:]:
                for key, pred in _filters(c, f).items():
                    if key in new and new[key] != pred:
                        c.notes.append(f"CALCULATE replaced the existing filter on {key.split(':')[-1]} (this is how DAX behaves).")
                    new[key] = pred
            return ev(c, args[0], new)
        if name == "IF":
            if len(args) not in (2, 3):
                raise DaxError("IF(condition, then [, else]).")
            return ev(c, args[1], ctx) if ev(c, args[0], ctx) else (ev(c, args[2], ctx) if len(args) == 3 else None)
        if name in ("ROUND", "ABS"):
            if (name == "ROUND" and len(args) != 2) or (name == "ABS" and len(args) != 1):
                raise DaxError("ROUND(number, digits) or ABS(number).")
            v = ev(c, args[0], ctx)
            if v is None:
                return None
            return round(v, int(ev(c, args[1], ctx))) if name == "ROUND" else abs(v)
        if name in UNSUPPORTED:
            raise DaxError(f"{name} isn't supported in this lab. The SQL way: {UNSUPPORTED[name]}")
        raise DaxError(f"{name} isn't a function this lab knows. Supported: SUM, AVERAGE, MIN, MAX, COUNT, COUNTROWS, DISTINCTCOUNT, DIVIDE, CALCULATE, IF, ROUND, ABS.")
    if k == "table":
        raise DaxError(f"'{node[1]}' is a table name. Use it inside COUNTROWS({node[1]}), or write a column as {node[1]}[Column] and a measure as [Name].")
    raise DaxError("I can't evaluate that.")


def _validate(c: _Ctx, node):
    """Walk once with an empty context so errors surface before grouping."""
    ev(c, node, {})


def run(measures: list[dict], group_by: list[str] | None = None, csv_text: str | None = None) -> dict:
    if not isinstance(measures, list) or not measures:
        raise DaxError("Add at least one measure, for example Total Sales = SUM(Sales[Amount]).")
    if len(measures) > MAX_MEASURES:
        raise DaxError(f"Use at most {MAX_MEASURES} measures.")
    group_by = group_by or []
    if len(group_by) > 2:
        raise DaxError("Group by at most two columns.")
    con, table, cols, nrows = _load(csv_text)
    try:
        c = _Ctx(con, table, cols)
        names = []
        for m in measures:
            nm = (m.get("name") or "").strip()
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 _%]{0,39}", nm):
                raise DaxError("A measure name starts with a letter and uses letters, digits, spaces, _ or %.")
            if any(nm.lower() == x.lower() for x in names):
                raise DaxError(f"Two measures are called '{nm}'.")
            names.append(nm)
            c.measures[nm] = parse(m.get("formula") or "")
        gcols = []
        for g in group_by:
            hit = next((k for k in cols if k.lower() == (g or "").lower()), None)
            if hit is None:
                raise DaxError(f"Can't group by '{g}'. Columns: {', '.join(cols)}.")
            gcols.append(hit)
        for nm in names:
            c.stack = [nm]
            _validate(c, c.measures[nm])
        c.notes = []
        groups = [()]
        if gcols:
            sel = ", ".join(f'"{g}"' for g in gcols)
            groups = con.execute(f'SELECT DISTINCT {sel} FROM "{table}" ORDER BY {sel} LIMIT {MAX_GROUPS + 1}').fetchall()
            if len(groups) > MAX_GROUPS:
                raise DaxError(f"That groups into more than {MAX_GROUPS} rows. Group by a column with fewer distinct values.")
        rows = []
        for gv in groups:
            ctx = {g: ("=", v.isoformat() if hasattr(v, "isoformat") else v) for g, v in zip(gcols, gv)}
            row = {g: (v.isoformat() if hasattr(v, "isoformat") else v) for g, v in zip(gcols, gv)}
            for nm in names:
                c.stack = [nm]
                v = ev(c, c.measures[nm], ctx)
                row[nm] = round(v, 4) if isinstance(v, float) else v
            rows.append(row)
        notes = list(dict.fromkeys(c.notes))
        return {"table": table, "rows_in_table": nrows, "columns": cols, "group_by": gcols, "measures": names, "rows": rows, "notes": notes,
                "how": "Each output row is a filter context (the group values). A measure is evaluated once per row: aggregates read only the rows that pass the context, and CALCULATE adds or replaces filters first.",
                "limit": "A subset of DAX evaluated here, not the Power BI engine: no relationships, no time intelligence, no row context or iterators. Results match Power BI for the supported formulas, and unsupported ones are refused rather than guessed."}
    finally:
        con.close()


# ------------------------------------------------------------------ reference
EXAMPLES = [
    ("Total Sales", "SUM(Sales[Amount])", "SELECT SUM(Amount) FROM Sales", "The simplest measure: an aggregation that respects whatever filters the report applies."),
    ("Total Cost", "SUM(Sales[Cost])", "SELECT SUM(Cost) FROM Sales", ""),
    ("Gross Profit", "[Total Sales] - [Total Cost]", "SELECT SUM(Amount) - SUM(Cost) FROM Sales", "Measures can be built from measures."),
    ("Profit Margin %", "DIVIDE([Gross Profit], [Total Sales], 0)", "SELECT (SUM(Amount) - SUM(Cost)) / NULLIF(SUM(Amount), 0) FROM Sales", "DIVIDE avoids the divide-by-zero error. Never average a margin column: divide the sums."),
    ("Air Sales", "CALCULATE([Total Sales], Sales[Category] = \"Air\")", "SELECT SUM(Amount) FILTER (WHERE Category = 'Air') FROM Sales", "CALCULATE changes the filter context, then evaluates the expression."),
    ("USA or UK Sales", "CALCULATE([Total Sales], Sales[Country] IN {\"USA\", \"UK\"})", "SELECT SUM(Amount) FILTER (WHERE Country IN ('USA','UK')) FROM Sales", ""),
    ("Sales 2025", "CALCULATE([Total Sales], YEAR(Sales[Date]) = 2025)", "SELECT SUM(Amount) FILTER (WHERE year(Date) = 2025) FROM Sales", "Fine for one year; a calendar table with time intelligence is the usual way in Power BI."),
    ("Share of USA", "DIVIDE([Total Sales], CALCULATE([Total Sales], Sales[Country] = \"USA\"))", "SELECT SUM(Amount) / SUM(Amount) FILTER (WHERE Country='USA') FROM Sales", "Group by Country to see why: for each row, the second term REPLACES the Country filter, so it always returns the USA total."),
    ("Transactions", "COUNTROWS(Sales)", "SELECT COUNT(*) FROM Sales", ""),
    ("Active Countries", "DISTINCTCOUNT(Sales[Country])", "SELECT COUNT(DISTINCT Country) FROM Sales", ""),
    ("Big Deal Count", "CALCULATE(COUNTROWS(Sales), Sales[Amount] > 4000)", "SELECT COUNT(*) FILTER (WHERE Amount > 4000) FROM Sales", ""),
]

REFERENCE = {
    "objects": [
        ("Measure", "Calculated when the report asks, using the current filters. Nothing is stored. Use it for totals, ratios and KPIs: this is the default choice."),
        ("Calculated column", "Calculated once per row and stored in the model, so it grows the file. Use it for something you must slice or filter by, such as an age band."),
        ("Calculated table", "A whole table built by a formula. Use it for a calendar or a helper list, not for everyday numbers."),
    ],
    "context": [
        ("Filter context", "The set of filters in effect for one number: slicers, the row and column of a visual, and CALCULATE filters. Every cell in a table or chart has its own."),
        ("Row context", "'This row' while a calculated column or an iterator (SUMX) walks the table. Row context does not filter other tables by itself."),
        ("CALCULATE", "Takes the current filter context, adds or replaces filters, then evaluates the expression. A filter on a column replaces any existing filter on that same column."),
    ],
    "dax_to_sql": [
        ("SUM / AVERAGE / MIN / MAX", "SUM / AVG / MIN / MAX"), ("COUNTROWS(T)", "COUNT(*)"), ("DISTINCTCOUNT(T[c])", "COUNT(DISTINCT c)"),
        ("DIVIDE(a, b, alt)", "COALESCE(a / NULLIF(b, 0), alt)"), ("CALCULATE(x, T[c] = v)", "x FILTER (WHERE c = v), or a WHERE"), ("IF(c, a, b)", "CASE WHEN c THEN a ELSE b END"),
        ("SWITCH(...)", "CASE WHEN ... END"), ("TOTALYTD(x, date)", "SUM(x) OVER (PARTITION BY year ORDER BY date)"), ("SAMEPERIODLASTYEAR", "LAG(x, 12) over months"),
        ("RELATED(T[c])", "JOIN to the dimension table"), ("VALUES / DISTINCT", "SELECT DISTINCT"), ("ALL(T)", "ignore the filters: SUM(x) OVER ()"),
    ],
    "practices": [
        "Write measures, not calculated columns, for numbers you add up.", "Divide the sums for a ratio (DIVIDE([Profit], [Sales])); never average a ratio column.",
        "Use DIVIDE instead of / so a zero denominator gives a blank, not an error.", "Name measures clearly, add descriptions, and keep them in one measure table so people can find them.",
        "Use VAR to name intermediate results and avoid repeating an expression.", "Test a measure in a table with a slicer, check the totals against the source, and test blanks and zeros.",
        "Keep the model a star schema: one fact table, dimension tables, one-to-many relationships; time intelligence needs a proper date table.",
    ],
}

SLIPS = [
    "The 'Common DAX Functions' box lists YTD under time intelligence. There is no function called YTD: the functions are TOTALYTD and DATESYTD.",
    "SELECTEDVALUE is grouped with the table functions. It returns a single value (a scalar), not a table.",
    "'Calculated Table: used for complex logic' is loose: it is for building a table (a calendar or a helper), not for complex logic in general.",
]


def reference() -> dict:
    sec = {k: ([{"item": a, "note": b} for a, b in v] if k != "practices" else v) for k, v in REFERENCE.items()}
    return {"examples": [{"name": n, "dax": d, "sql": q, "note": t} for n, d, q, t in EXAMPLES], "sections": sec,
            "unsupported": [{"function": k, "sql": v} for k, v in sorted(UNSUPPORTED.items())], "slips": SLIPS,
            "not_built": ["The Power BI engine, relationships between tables, a date table and real time intelligence, row context and iterators (SUMX). They need the model Power BI keeps; use DAX Studio or Power BI Desktop for those.", "Power BI Desktop and the Power BI service themselves are closed, Windows-first software and aren't replaced here."]}
