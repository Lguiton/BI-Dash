"""A small spreadsheet formula engine: cells, references, ranges, common functions, dependency order and cycle detection."""
from __future__ import annotations

import math
import re

from app.services.data_dbt import DataLabError

MAXC = 600


class Err(Exception):
    def __init__(self, code):
        self.code = code


_CELL = re.compile(r"^\$?([A-Z]{1,2})\$?([0-9]{1,3})$")


def _col(s: str) -> int:
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n


def _addr(c: int, r: int) -> str:
    s = ""
    while c:
        c, m = divmod(c - 1, 26)
        s = chr(65 + m) + s
    return f"{s}{r}"


def _split(a: str):
    m = _CELL.match(a)
    if not m:
        raise Err("#REF!")
    return _col(m.group(1)), int(m.group(2))


_TOK = re.compile(r'\s*(?:(?P<num>\d+\.?\d*(?:[eE][+-]?\d+)?|\.\d+)|(?P<str>"(?:[^"]|"")*")|(?P<rng>\$?[A-Z]{1,2}\$?\d{1,3}:\$?[A-Z]{1,2}\$?\d{1,3})|(?P<ref>\$?[A-Z]{1,2}\$?\d{1,3}(?![A-Za-z(]))|(?P<fn>[A-Za-z_][A-Za-z0-9_.]*(?=\())|(?P<bool>TRUE|FALSE)|(?P<op><=|>=|<>|[-+*/^&=<>(),%]))')


def _lex(s: str):
    out, i = [], 0
    while i < len(s):
        if s[i].isspace():
            i += 1
            continue
        m = _TOK.match(s, i)
        if not m or m.end() == i:
            raise Err("#NAME?")
        i = m.end()
        out.append((m.lastgroup, m.group(m.lastgroup)))
    return out


class _P:
    def __init__(self, toks):
        self.t, self.i = toks, 0

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else (None, None)

    def eat(self, v=None):
        k, x = self.peek()
        if k is None or (v is not None and x != v):
            raise Err("#NAME?")
        self.i += 1
        return k, x

    def parse(self):
        e = self.cmp()
        if self.i != len(self.t):
            raise Err("#NAME?")
        return e

    def cmp(self):
        e = self.cat()
        while self.peek()[1] in ("=", "<>", "<", ">", "<=", ">="):
            op = self.eat()[1]
            e = ("bin", op, e, self.cat())
        return e

    def cat(self):
        e = self.add()
        while self.peek()[1] == "&":
            self.eat()
            e = ("bin", "&", e, self.add())
        return e

    def add(self):
        e = self.mul()
        while self.peek()[1] in ("+", "-"):
            op = self.eat()[1]
            e = ("bin", op, e, self.mul())
        return e

    def mul(self):
        e = self.pw()
        while self.peek()[1] in ("*", "/"):
            op = self.eat()[1]
            e = ("bin", op, e, self.pw())
        return e

    def pw(self):
        e = self.un()
        while self.peek()[1] == "^":
            self.eat()
            e = ("bin", "^", e, self.un())
        return e

    def un(self):
        if self.peek()[1] in ("-", "+"):
            op = self.eat()[1]
            e = self.un()
            return ("neg", e) if op == "-" else e
        e = self.atom()
        while self.peek()[1] == "%":
            self.eat()
            e = ("bin", "/", e, ("num", 100.0))
        return e

    def atom(self):
        k, x = self.eat()
        if k == "num":
            return ("num", float(x))
        if k == "str":
            return ("str", x[1:-1].replace('""', '"'))
        if k == "bool":
            return ("bool", x == "TRUE")
        if k == "ref":
            return ("ref", x.replace("$", ""))
        if k == "rng":
            a, b = x.replace("$", "").split(":")
            return ("rng", a, b)
        if k == "fn":
            self.eat("(")
            args = []
            if self.peek()[1] != ")":
                args.append(self.cmp())
                while self.peek()[1] == ",":
                    self.eat()
                    args.append(self.cmp())
            self.eat(")")
            return ("fn", x.upper(), args)
        if x == "(":
            e = self.cmp()
            self.eat(")")
            return e
        raise Err("#NAME?")


def _refs(ast, out: set):
    if not isinstance(ast, tuple):
        return
    if ast[0] == "ref":
        out.add(ast[1])
    elif ast[0] == "rng":
        (c1, r1), (c2, r2) = _split(ast[1]), _split(ast[2])
        if (c2 - c1 + 1) * (r2 - r1 + 1) > MAXC:
            raise Err("#REF!")
        for c in range(min(c1, c2), max(c1, c2) + 1):
            for r in range(min(r1, r2), max(r1, r2) + 1):
                out.add(_addr(c, r))
    else:
        for a in ast[1:]:
            if isinstance(a, tuple):
                _refs(a, out)
            elif isinstance(a, list):
                for x in a:
                    _refs(x, out)


def _num(v):
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if v is None or v == "":
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(v)
    except (TypeError, ValueError):
        raise Err("#VALUE!") from None


def _text(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, float) and v == int(v) and abs(v) < 1e15:
        return str(int(v))
    return str(v)


def _flat(vals):
    for v in vals:
        if isinstance(v, list):
            yield from _flat(v)
        else:
            yield v


class Sheet:
    def __init__(self, raw: dict[str, str]):
        self.raw, self.ast, self.deps = raw, {}, {}
        self.val: dict[str, object] = {}
        self.busy: set = set()
        for a, t in raw.items():
            if t.startswith("="):
                try:
                    ast = _P(_lex(t[1:])).parse()
                    d: set = set()
                    _refs(ast, d)
                    self.ast[a], self.deps[a] = ast, d
                except Err as e:
                    self.val[a] = e.code
                    self.ast[a], self.deps[a] = None, set()

    def get(self, a):
        if a in self.val:
            v = self.val[a]
            if isinstance(v, str) and v.startswith("#") and a in self.ast:
                return v
            return v
        t = self.raw.get(a)
        if t is None:
            return None
        if a not in self.ast:
            try:
                self.val[a] = float(t) if re.fullmatch(r"-?\d+(\.\d+)?([eE][+-]?\d+)?", t.strip()) else (True if t.upper() == "TRUE" else False if t.upper() == "FALSE" else t)
            except ValueError:
                self.val[a] = t
            return self.val[a]
        if a in self.busy:
            raise Err("#CIRC!")
        self.busy.add(a)
        try:
            try:
                self.val[a] = self.ev(self.ast[a])
            except Err as e:
                self.val[a] = e.code
        finally:
            self.busy.discard(a)
        return self.val[a]

    def cell(self, a):
        v = self.get(a)
        if isinstance(v, str) and v.startswith("#") and a in self.ast:
            raise Err(v)
        return v

    def rng(self, a, b):
        (c1, r1), (c2, r2) = _split(a), _split(b)
        return [[self.cell(_addr(c, r)) for c in range(min(c1, c2), max(c1, c2) + 1)] for r in range(min(r1, r2), max(r1, r2) + 1)]

    def ev(self, n):
        k = n[0]
        if k in ("num", "str", "bool"):
            return n[1]
        if k == "ref":
            return self.cell(n[1])
        if k == "rng":
            return self.rng(n[1], n[2])
        if k == "neg":
            return -_num(self.ev(n[1]))
        if k == "bin":
            op, a, b = n[1], self.ev(n[2]), self.ev(n[3])
            if isinstance(a, list) or isinstance(b, list):
                raise Err("#VALUE!")
            if op == "&":
                return _text(a) + _text(b)
            if op in ("=", "<>", "<", ">", "<=", ">="):
                if isinstance(a, str) != isinstance(b, str):
                    a, b = (0.0, 1.0) if isinstance(b, str) and not isinstance(a, str) else (1.0, 0.0) if isinstance(a, str) else (a, b)
                if isinstance(a, str):
                    a, b = a.lower(), str(b).lower()
                else:
                    a, b = _num(a), _num(b)
                return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op]
            x, y = _num(a), _num(b)
            if op == "+":
                return x + y
            if op == "-":
                return x - y
            if op == "*":
                return x * y
            if op == "/":
                if y == 0:
                    raise Err("#DIV/0!")
                return x / y
            try:
                r = x ** y
            except (OverflowError, ZeroDivisionError):
                raise Err("#NUM!") from None
            if isinstance(r, complex):
                raise Err("#NUM!")
            return r
        return self.fn(n[1], n[2])

    def fn(self, name, args):
        if name == "IF":
            if len(args) not in (2, 3):
                raise Err("#VALUE!")
            c = self.ev(args[0])
            return self.ev(args[1]) if (c if isinstance(c, bool) else _num(c) != 0) else (self.ev(args[2]) if len(args) == 3 else False)
        if name == "IFERROR":
            if len(args) != 2:
                raise Err("#VALUE!")
            try:
                return self.ev(args[0])
            except Err:
                return self.ev(args[1])
        vals = [self.ev(a) for a in args]
        nums = lambda: [float(x) for x in _flat(vals) if isinstance(x, (int, float)) and not isinstance(x, bool)]  # noqa: E731
        if name == "SUM":
            return sum(nums())
        if name == "AVERAGE":
            v = nums()
            if not v:
                raise Err("#DIV/0!")
            return sum(v) / len(v)
        if name == "MIN":
            v = nums()
            return min(v) if v else 0.0
        if name == "MAX":
            v = nums()
            return max(v) if v else 0.0
        if name == "COUNT":
            return float(len(nums()))
        if name == "COUNTA":
            return float(sum(1 for x in _flat(vals) if x not in (None, "")))
        if name in ("AND", "OR"):
            b = [(x if isinstance(x, bool) else _num(x) != 0) for x in _flat(vals) if x is not None]
            return all(b) if name == "AND" else any(b)
        if name == "NOT":
            return not (vals[0] if isinstance(vals[0], bool) else _num(vals[0]) != 0)
        if name in ("ROUND", "ABS", "SQRT", "POWER", "MOD", "INT", "LEN", "UPPER", "LOWER", "CONCAT", "CONCATENATE", "SUMIF", "COUNTIF", "VLOOKUP"):
            return self.fn2(name, vals)
        raise Err("#NAME?")

    def fn2(self, name, v):
        need = {"ROUND": 2, "ABS": 1, "SQRT": 1, "POWER": 2, "MOD": 2, "INT": 1, "LEN": 1, "UPPER": 1, "LOWER": 1}
        if name in need and len(v) != need[name]:
            raise Err("#VALUE!")
        if name == "ROUND":
            x, d = _num(v[0]), int(_num(v[1]))
            f = 10 ** d
            return math.floor(abs(x) * f + 0.5) / f * (1 if x >= 0 else -1)
        if name == "ABS":
            return abs(_num(v[0]))
        if name == "SQRT":
            if _num(v[0]) < 0:
                raise Err("#NUM!")
            return math.sqrt(_num(v[0]))
        if name == "POWER":
            return self.ev(("bin", "^", ("num", _num(v[0])), ("num", _num(v[1]))))
        if name == "MOD":
            if _num(v[1]) == 0:
                raise Err("#DIV/0!")
            return _num(v[0]) - _num(v[1]) * math.floor(_num(v[0]) / _num(v[1]))
        if name == "INT":
            return float(math.floor(_num(v[0])))
        if name == "LEN":
            return float(len(_text(v[0])))
        if name == "UPPER":
            return _text(v[0]).upper()
        if name == "LOWER":
            return _text(v[0]).lower()
        if name in ("CONCAT", "CONCATENATE"):
            return "".join(_text(x) for x in _flat(v))
        if name in ("SUMIF", "COUNTIF"):
            if len(v) < 2 or not isinstance(v[0], list):
                raise Err("#VALUE!")
            crit = v[1]
            rng = list(_flat(v[0]))
            tot = list(_flat(v[2])) if name == "SUMIF" and len(v) > 2 and isinstance(v[2], list) else rng
            op, rhs = "=", crit
            if isinstance(crit, str):
                m = re.match(r"^(<=|>=|<>|<|>|=)(.*)$", crit)
                if m:
                    op, rhs = m.group(1), m.group(2)
            try:
                rn = float(rhs)
            except (TypeError, ValueError):
                rn = None

            def ok(x):
                if rn is not None and isinstance(x, (int, float)) and not isinstance(x, bool):
                    a, b = float(x), rn
                else:
                    a, b = str(x).lower() if x is not None else "", str(rhs).lower()
                return {"=": a == b, "<>": a != b, "<": a < b, ">": a > b, "<=": a <= b, ">=": a >= b}[op] if (rn is not None) == isinstance(a, float) else (op == "<>")
            hits = [i for i, x in enumerate(rng) if ok(x)]
            return float(len(hits)) if name == "COUNTIF" else float(sum(float(tot[i]) for i in hits if i < len(tot) and isinstance(tot[i], (int, float)) and not isinstance(tot[i], bool)))
        if name == "VLOOKUP":
            if len(v) < 3 or not isinstance(v[1], list):
                raise Err("#VALUE!")
            idx = int(_num(v[2]))
            exact = len(v) > 3 and not (v[3] if isinstance(v[3], bool) else _num(v[3]) != 0)
            if not 1 <= idx <= len(v[1][0]):
                raise Err("#REF!")
            key = v[0]
            for row in v[1]:
                if (str(row[0]).lower() == str(key).lower()) if isinstance(key, str) else (isinstance(row[0], (int, float)) and float(row[0]) == _num(key)):
                    return row[idx - 1]
            if not exact and not isinstance(key, str):
                best = None
                for row in v[1]:
                    if isinstance(row[0], (int, float)) and float(row[0]) <= _num(key) and (best is None or row[0] > best[0]):
                        best = row
                if best:
                    return best[idx - 1]
            raise Err("#N/A")
        raise Err("#NAME?")


def evaluate(cells: str) -> dict:
    raw: dict[str, str] = {}
    for ln in (cells or "").splitlines():
        ln = ln.rstrip()
        if not ln.strip():
            continue
        m = re.match(r"^\s*(\$?[A-Za-z]{1,2}\$?\d{1,3})\s*[:=]\s?(.*)$", ln) if not re.match(r"^\s*[A-Za-z]{1,2}\d{1,3}\s*=\s*=", ln) else re.match(r"^\s*([A-Za-z]{1,2}\d{1,3})\s*=\s*(=.*)$", ln)
        if not m:
            raise DataLabError(f"Line '{ln}': write one cell per line, like  A1: 10  or  B1: =A1*2")
        a = m.group(1).replace("$", "").upper()
        if not _CELL.match(a) or _col(re.match(r"[A-Z]+", a).group()) > 26 * 26:
            raise DataLabError(f"'{a}' is not a cell name. Use a column letter and a row number, such as B7.")
        if a in raw:
            raise DataLabError(f"Cell {a} is set twice.")
        raw[a] = m.group(2).strip()
    if not raw:
        raise DataLabError("Enter at least one cell.")
    if len(raw) > 400:
        raise DataLabError("At most 400 cells.")
    sh = Sheet(raw)
    for a in raw:
        sh.get(a)
    graph = {a: sorted(d & set(raw)) for a, d in sh.deps.items()}
    order, seen, st = [], set(), set()
    cycle = []

    def visit(a, path):
        if a in seen:
            return
        if a in st:
            if not cycle:
                cycle.extend(path[path.index(a):] + [a])
            return
        st.add(a)
        for d in graph.get(a, []):
            visit(d, path + [a])
        st.discard(a)
        seen.add(a)
        order.append(a)
    for a in sorted(graph, key=lambda x: (int(re.sub(r"\D", "", x)), _col(re.sub(r"\d", "", x)))):
        visit(a, [])
    cells_out = []
    for a in sorted(raw, key=lambda x: (int(re.sub(r"\D", "", x)), _col(re.sub(r"\d", "", x)))):
        v = sh.val.get(a)
        if isinstance(v, float):
            v = int(v) if v == int(v) and abs(v) < 1e15 else round(v, 12)
        cells_out.append({"cell": a, "input": raw[a], "value": v, "depends_on": sorted(sh.deps.get(a, set()))})
    errs = [c["cell"] for c in cells_out if isinstance(c["value"], str) and c["value"].startswith("#") and raw[c["cell"]].startswith("=")]
    return {"cells": cells_out, "calc_order": order, "errors": errs, "cycle": cycle,
            "lesson": "A spreadsheet is a graph: each formula lists the cells it reads, and the engine calculates those first. A formula that ends up reading itself is a circular reference, which has no answer.",
            "errors_key": {"#DIV/0!": "divide by zero", "#VALUE!": "wrong kind of value, such as text in arithmetic", "#NAME?": "unknown function or unreadable formula", "#REF!": "a bad cell or range", "#NUM!": "an impossible number such as sqrt(-1)", "#N/A": "lookup found nothing", "#CIRC!": "circular reference"}}


SAMPLE = "A1: Item\nB1: Price\nC1: Qty\nA2: Pen\nB2: 1.5\nC2: 10\nA3: Book\nB3: 12\nC3: 3\nA4: Total\nB4: =AVERAGE(B2:B3)\nC4: =SUM(C2:C3)\nD2: =B2*C2\nD3: =B3*C3\nD4: =SUM(D2:D3)\nE2: =IF(D2>20,\"big\",\"small\")\nE3: =VLOOKUP(\"Book\",A2:C3,2,FALSE)\nE4: =D4/(C4-13)\nF1: =IFERROR(E4,\"n/a\")"
SLIPS = ["Spreadsheet tutorials show =A1+A2 with text in a cell as a quiet 0. Excel's + gives #VALUE! for text while SUM skips it; the two behave differently.", "Many posts say 0.1+0.2=0.3 in a sheet. Binary floating point stores 0.30000000000000004, and Excel only hides it by showing 15 digits.", "Lookup guides use VLOOKUP with approximate match by default, which silently returns a wrong row on unsorted data. Ask for an exact match."]
NOT_BUILT = ["Dates, array formulas, named ranges, pivot tables, charts and most of Excel's 400+ functions.", "Editing in a grid; the input is one cell per line."]
