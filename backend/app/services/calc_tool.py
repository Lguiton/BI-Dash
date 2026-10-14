"""Calculator tool for the Mathematician and CFO agents: exact arithmetic, statistics, combinatorics, finance and unit-free formulas.

Expressions are parsed with `ast` and only whitelisted nodes and functions run, so nothing in here can reach files, imports or the network."""
from __future__ import annotations

import ast
import math
import operator
import statistics

MAX_LEN = 400
MAX_LIST = 5000
MAX_EXP = 10_000


class CalcError(Exception):
    pass


def _irr(flows, lo=-0.99, hi=10.0):
    f = lambda r: sum(c / (1 + r) ** i for i, c in enumerate(flows))  # noqa: E731
    if f(lo) * f(hi) > 0:
        raise CalcError("irr: no sign change, so there is no rate that makes the net value zero.")
    for _ in range(200):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if f(lo) * f(mid) > 0 else (lo, mid)
    return (lo + hi) / 2


def _pmt(rate, n, pv, fv=0):
    if n <= 0:
        raise CalcError("pmt: n must be positive.")
    return -(pv + fv / (1 + rate) ** n) / n if rate == 0 else -rate * (pv * (1 + rate) ** n + fv) / ((1 + rate) ** n - 1)


def _mode(x):
    return statistics.multimode(x)[0]


FUNCS = {
    "sqrt": math.sqrt, "cbrt": math.cbrt, "exp": math.exp, "ln": math.log, "log": lambda x, b=10: math.log(x, b), "log2": math.log2, "log10": math.log10,
    "sin": math.sin, "cos": math.cos, "tan": math.tan, "asin": math.asin, "acos": math.acos, "atan": math.atan, "atan2": math.atan2,
    "degrees": math.degrees, "radians": math.radians, "abs": abs, "round": round, "floor": math.floor, "ceil": math.ceil, "min": min, "max": max, "sum": sum,
    "factorial": math.factorial, "comb": math.comb, "perm": math.perm, "gcd": math.gcd, "lcm": math.lcm, "hypot": math.hypot, "pow": pow,
    "mean": statistics.fmean, "median": statistics.median, "mode": _mode, "stdev": statistics.stdev, "pstdev": statistics.pstdev,
    "variance": statistics.variance, "pvariance": statistics.pvariance, "len": len,
    "pmt": _pmt, "fv": lambda r, n, pmt, pv=0: -(pv * (1 + r) ** n + pmt * (((1 + r) ** n - 1) / r if r else n)),
    "pv": lambda r, n, pmt, fv=0: -(fv / (1 + r) ** n + pmt * ((1 - (1 + r) ** -n) / r if r else n)),
    "npv": lambda r, flows: sum(c / (1 + r) ** i for i, c in enumerate(flows)), "irr": _irr,
    "cagr": lambda start, end, years: (end / start) ** (1 / years) - 1,
    "pct_change": lambda old, new: (new - old) / old * 100, "margin": lambda revenue, cost: (revenue - cost) / revenue * 100,
    "markup": lambda cost, price: (price - cost) / cost * 100, "breakeven": lambda fixed, price, var: fixed / (price - var),
    "zscore": lambda x, m, s: (x - m) / s, "corr": statistics.correlation, "slope": lambda x, y: statistics.linear_regression(x, y).slope,
    "intercept": lambda x, y: statistics.linear_regression(x, y).intercept,
    "norm_cdf": lambda x, m=0, s=1: statistics.NormalDist(m, s).cdf(x), "norm_inv": lambda p, m=0, s=1: statistics.NormalDist(m, s).inv_cdf(p),
}
NAMES = {"pi": math.pi, "e": math.e, "tau": math.tau}
BIN = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
UN = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def _ev(n):
    if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)) and not isinstance(n.value, bool):
        return n.value
    if isinstance(n, ast.Name) and n.id in NAMES:
        return NAMES[n.id]
    if isinstance(n, (ast.List, ast.Tuple)):
        if len(n.elts) > MAX_LIST:
            raise CalcError("That list is too long.")
        return [_ev(x) for x in n.elts]
    if isinstance(n, ast.UnaryOp) and type(n.op) in UN:
        return UN[type(n.op)](_ev(n.operand))
    if isinstance(n, ast.BinOp) and type(n.op) in BIN:
        a, b = _ev(n.left), _ev(n.right)
        if isinstance(n.op, ast.Pow) and (abs(b) > MAX_EXP or (isinstance(a, int) and isinstance(b, int) and abs(a) > 1 and b * math.log10(abs(a)) > 300)):
            raise CalcError("That power is too large to compute.")
        return BIN[type(n.op)](a, b)
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id in FUNCS and not n.keywords:
        args = [_ev(a) for a in n.args]
        if n.func.id == "factorial" and (not isinstance(args[0], int) or args[0] > 2000):
            raise CalcError("factorial needs a whole number up to 2000.")
        if n.func.id in ("comb", "perm") and any(isinstance(a, int) and a > 100000 for a in args):
            raise CalcError("Those numbers are too large.")
        return FUNCS[n.func.id](*args)
    raise CalcError("Only numbers, + - * / // % **, parentheses, lists like [1,2,3], pi, e, and the listed functions are allowed.")


def calculate(expr: str) -> dict:
    expr = (expr or "").strip()
    if not expr:
        raise CalcError("Give an expression, e.g. 1200*(1+0.05)**3")
    if len(expr) > MAX_LEN:
        raise CalcError(f"Keep it under {MAX_LEN} characters.")
    try:
        v = _ev(ast.parse(expr.replace("^", "**").replace(",,", ","), mode="eval").body)
    except CalcError:
        raise
    except SyntaxError:
        raise CalcError("That isn't a valid expression.") from None
    except ZeroDivisionError:
        raise CalcError("Division by zero.") from None
    except (ValueError, TypeError, OverflowError, statistics.StatisticsError, IndexError) as e:
        raise CalcError(f"Can't compute that: {e}") from None
    if isinstance(v, float):
        v = float(f"{v:.12g}")
    return {"expression": expr, "result": v}


def function_list() -> list[str]:
    return sorted(FUNCS)


TOOL_CALC = {"name": "calculate", "description": "Exact calculator. ALWAYS use it for any arithmetic, percentage, statistic, forecast step, interest or ROI figure instead of working it out yourself. "
             "Operators + - * / // % ** (or ^), parentheses, lists [1,2,3], constants pi, e. Functions: " + ", ".join(function_list()) + ". Example: pmt(0.06/12, 60, 25000) or npv(0.1,[-1000,400,500,600]).",
             "input_schema": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"], "additionalProperties": False}}
