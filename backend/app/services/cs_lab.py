"""Computer science lab: a Big-O estimator for code you paste, algorithm step-through on your own numbers, and a data structure cheat sheet.
Local and deterministic. It never runs pasted code (Python is parsed, other languages are read as text), and the Big-O result is an estimate that you check."""
from __future__ import annotations

import ast
import re


class CsError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


MAX_CODE = 8000
MAX_ITEMS = 200
MAX_STEPS = 60

# ------------------------------------------------------------------ Big-O estimate
_HALVE = re.compile(r"(//=?\s*2|/=?\s*2|>>=?\s*1|\*=?\s*2\b|<<=?\s*1|mid)")


def _is_halving(node: ast.AST) -> bool:
    return bool(_HALVE.search(ast.unparse(node)))


def _loop_info(body: list[ast.stmt]) -> tuple[int, int]:
    """(plain loop depth, log-loop depth) along the deepest path."""
    best = (0, 0)

    def walk(nodes, plain, logd):
        nonlocal best
        for n in nodes:
            if isinstance(n, (ast.For, ast.AsyncFor, ast.While)):
                log_like = isinstance(n, ast.While) and any(isinstance(x, (ast.AugAssign, ast.Assign)) and _is_halving(x) for x in ast.walk(n))
                p, l = (plain, logd + 1) if log_like else (plain + 1, logd)
                best = max(best, (p, l), key=lambda t: (t[0] + t[1], t[0]))
                walk(n.body + n.orelse, p, l)
            elif isinstance(n, (ast.If, ast.Try, ast.With)):
                kids = []
                for f in ("body", "orelse", "finalbody"):
                    kids += getattr(n, f, []) or []
                for h in getattr(n, "handlers", []) or []:
                    kids += h.body
                walk(kids, plain, logd)
            for c in ast.walk(n):
                if isinstance(c, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)) and c is not n:
                    pass
            if isinstance(n, ast.Expr) or isinstance(n, ast.Assign) or isinstance(n, ast.Return):
                gens = [c for c in ast.walk(n) if isinstance(c, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))]
                if gens:
                    depth = max(len(g.generators) for g in gens)
                    best = max(best, (plain + depth, logd), key=lambda t: (t[0] + t[1], t[0]))
    walk(body, 0, 0)
    return best


def _fmt(plain: int, logd: int, nlogn: bool, exp: bool) -> str:
    if exp:
        return "O(2^n)"
    if nlogn:
        plain, logd, nlogn = plain + 1, logd + 1, False
    parts = []
    if plain:
        parts.append("n" if plain == 1 else f"n^{plain}")
    if logd or nlogn:
        k = logd + (1 if nlogn else 0)
        parts.append("log n" if k == 1 else f"(log n)^{k}")
    return "O(" + (" ".join(parts) if parts else "1") + ")"


def _analyze_py(tree: ast.Module) -> list[dict]:
    rows: list[dict] = []
    funcs = [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    scopes: list[tuple[str, list[ast.stmt], ast.AST | None]] = [(f.name, f.body, f) for f in funcs]
    top = [n for n in tree.body if not isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))]
    if top:
        scopes.insert(0, ("(top-level code)", top, None))
    for name, body, fn in scopes:
        plain, logd = _loop_info(body)
        notes: list[str] = []
        nlogn = False
        exp = False
        calls = [c for n in body for c in ast.walk(n) if isinstance(c, ast.Call)]
        if any((isinstance(c.func, ast.Name) and c.func.id == "sorted") or (isinstance(c.func, ast.Attribute) and c.func.attr == "sort") for c in calls):
            nlogn = True
            notes.append("A sort costs O(n log n).")
        if fn is not None:
            self_calls = [c for c in calls if (isinstance(c.func, ast.Name) and c.func.id == name)]
            memo = any("cache" in ast.unparse(d) or "memo" in ast.unparse(d) for d in fn.decorator_list) or any("memo" in a.arg or "cache" in a.arg for a in fn.args.args)
            if len(self_calls) >= 2 and not memo:
                exp = True
                notes.append("It calls itself two or more times per call with no cache, which grows like O(2^n). Add a cache (functools.lru_cache) or loop instead.")
            elif len(self_calls) >= 2 and memo:
                notes.append("Recursive with two calls, but a cache is present, so it is about O(n).")
                plain = max(plain, 1)
            elif len(self_calls) == 1:
                if any(_is_halving(a) for c in self_calls for a in c.args):
                    logd += 1
                    notes.append("It calls itself on about half the input each time: O(log n).")
                else:
                    plain += 1
                    notes.append("It calls itself once on a smaller input: O(n) deep. Very large inputs can hit Python's recursion limit.")
        # membership test inside a loop on something that may be a list
        for n in body:
            for loop in [x for x in ast.walk(n) if isinstance(x, (ast.For, ast.While))]:
                for cmp in [x for x in ast.walk(loop) if isinstance(x, ast.Compare)]:
                    if any(isinstance(o, (ast.In, ast.NotIn)) for o in cmp.ops):
                        notes.append("An `in` check inside a loop is O(n) on a list but O(1) on a set or dict. If that is a list, switch it to a set.")
                        break
                else:
                    continue
                break
            else:
                continue
            break
        for n in body:
            for loop in [x for x in ast.walk(n) if isinstance(x, (ast.For, ast.While))]:
                if any(isinstance(x, ast.AugAssign) and isinstance(x.op, ast.Add) and isinstance(x.value, (ast.Constant, ast.JoinedStr)) and isinstance(getattr(x.value, "value", ""), str) for x in ast.walk(loop)):
                    notes.append("Building a string with += in a loop can be slow; collect pieces in a list and use ''.join().")
                    break
        rows.append({"name": name, "estimate": _fmt(plain, logd, nlogn, exp), "loop_depth": plain + logd, "notes": list(dict.fromkeys(notes))})
    return rows


def _analyze_text(code: str) -> list[dict]:
    depth = best = 0
    stack: list[int] = []
    for line in code.splitlines():
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" \t"))
        while stack and indent <= stack[-1]:
            stack.pop()
        if re.match(r"\s*(for|while)\b|.*\b(for|while)\s*\(|.*\.(forEach|map|filter|reduce)\(", line):
            stack.append(indent)
            best = max(best, len(stack))
    depth = best
    return [{"name": "(text read, not a full parse)", "estimate": _fmt(depth, 0, False, False), "loop_depth": depth,
             "notes": ["Only loop nesting was read, because this is not valid Python. Recursion and library calls are not checked, so treat this as a rough guide."]}]


def complexity(code: str) -> dict:
    code = (code or "").strip("\n")
    if len(code.strip()) < 5:
        raise CsError("Paste some code first.")
    if len(code) > MAX_CODE:
        raise CsError(f"That is over {MAX_CODE} characters. Paste one function at a time.")
    try:
        rows = _analyze_py(ast.parse(code))
        lang = "Python (parsed, never run)"
    except SyntaxError:
        rows = _analyze_text(code)
        lang = "Not valid Python, read as text"
    return {"language": lang, "functions": rows, "caveat": "An estimate from the code's shape in terms of input size n. It cannot see data sizes or library costs, so confirm with a small timing test.",
            "scale": [{"n": n, "O(n)": n, "O(n log n)": int(n * (n.bit_length() - 1)), "O(n^2)": n * n} for n in (10, 1000, 100000)]}


# ------------------------------------------------------------------ algorithm step-through
def _nums(data) -> list[float]:
    if isinstance(data, str):
        data = [x for x in re.split(r"[,\s;]+", data.strip()) if x]
    try:
        out = [float(x) for x in data]
    except (TypeError, ValueError):
        raise CsError("Use numbers only, separated by commas or spaces.") from None
    if not out:
        raise CsError("Enter some numbers, like 5, 2, 9, 1.")
    if len(out) > MAX_ITEMS:
        raise CsError(f"Use at most {MAX_ITEMS} numbers.")
    return [int(x) if x == int(x) else x for x in out]


class _Log:
    def __init__(self):
        self.steps: list[dict] = []
        self.cmp = 0
        self.swp = 0

    def add(self, desc: str, state: list) -> None:
        if len(self.steps) < MAX_STEPS:
            self.steps.append({"what": desc, "list": list(state)})


SORTS = {
    "bubble": ("Bubble sort", "O(n)", "O(n^2)", "O(n^2)", "Swaps neighbours that are out of order, over and over. Easy to follow, slow on big lists."),
    "insertion": ("Insertion sort", "O(n)", "O(n^2)", "O(n^2)", "Builds a sorted section from the left, sliding each item into place. Good for small or nearly sorted lists."),
    "selection": ("Selection sort", "O(n^2)", "O(n^2)", "O(n^2)", "Finds the smallest remaining item and puts it next. Few swaps, always slow."),
    "merge": ("Merge sort", "O(n log n)", "O(n log n)", "O(n log n)", "Splits the list in half, sorts each half, then merges. Predictable and fast; uses extra memory."),
    "quick": ("Quick sort", "O(n log n)", "O(n log n)", "O(n^2)", "Picks a pivot and splits items smaller and larger. Fast on average; a bad pivot on sorted data is slow."),
}


def sort_steps(algo: str, data) -> dict:
    if algo not in SORTS:
        raise CsError("Pick bubble, insertion, selection, merge or quick.")
    a = _nums(data)
    orig = list(a)
    lg = _Log()
    if algo == "bubble":
        for i in range(len(a)):
            swapped = False
            for j in range(len(a) - 1 - i):
                lg.cmp += 1
                if a[j] > a[j + 1]:
                    a[j], a[j + 1] = a[j + 1], a[j]
                    lg.swp += 1
                    swapped = True
                    lg.add(f"Swap {a[j + 1]} and {a[j]}", a)
            if not swapped:
                break
    elif algo == "insertion":
        for i in range(1, len(a)):
            k, j = a[i], i - 1
            while j >= 0:
                lg.cmp += 1
                if a[j] > k:
                    a[j + 1] = a[j]
                    lg.swp += 1
                    j -= 1
                else:
                    break
            a[j + 1] = k
            lg.add(f"Insert {k} into the sorted part", a)
    elif algo == "selection":
        for i in range(len(a)):
            m = i
            for j in range(i + 1, len(a)):
                lg.cmp += 1
                if a[j] < a[m]:
                    m = j
            if m != i:
                a[i], a[m] = a[m], a[i]
                lg.swp += 1
            lg.add(f"Put the smallest remaining ({a[i]}) in position {i + 1}", a)
    elif algo == "merge":
        def ms(x):
            if len(x) <= 1:
                return x
            mid = len(x) // 2
            l, r = ms(x[:mid]), ms(x[mid:])
            out, i, j = [], 0, 0
            while i < len(l) and j < len(r):
                lg.cmp += 1
                if l[i] <= r[j]:
                    out.append(l[i]); i += 1
                else:
                    out.append(r[j]); j += 1
            out += l[i:] + r[j:]
            lg.add(f"Merge {l} and {r}", out)
            return out
        a = ms(a)
    else:
        def qs(x):
            if len(x) <= 1:
                return x
            p = x[len(x) // 2]
            lo = [v for v in x if v < p]
            eq = [v for v in x if v == p]
            hi = [v for v in x if v > p]
            lg.cmp += len(x) - 1
            lg.add(f"Pivot {p}: smaller {lo}, equal {eq}, larger {hi}", x)
            return qs(lo) + eq + qs(hi)
        a = qs(a)
    n, best, avg, worst, note = SORTS[algo]
    return {"algorithm": n, "input": orig, "sorted": a, "comparisons": lg.cmp, "moves": lg.swp, "steps": lg.steps, "steps_shown": len(lg.steps),
            "best": best, "average": avg, "worst": worst, "note": note, "n": len(orig)}


def search_steps(algo: str, data, target) -> dict:
    a = _nums(data)
    try:
        t = float(target)
    except (TypeError, ValueError):
        raise CsError("The number to find must be a number.") from None
    t = int(t) if t == int(t) else t
    steps, cmp = [], 0
    if algo == "linear":
        found = -1
        for i, v in enumerate(a):
            cmp += 1
            if len(steps) < MAX_STEPS:
                steps.append({"what": f"Check position {i + 1}: {v} {'is' if v == t else 'is not'} {t}", "list": a})
            if v == t:
                found = i
                break
        return {"algorithm": "Linear search", "list": a, "found_at": found + 1 if found >= 0 else None, "comparisons": cmp, "steps": steps, "average": "O(n)",
                "note": "Looks at items one by one. Works on any list."}
    if algo == "binary":
        s = sorted(a)
        lo, hi, found = 0, len(s) - 1, -1
        while lo <= hi:
            mid = (lo + hi) // 2
            cmp += 1
            if len(steps) < MAX_STEPS:
                steps.append({"what": f"Look at the middle (position {mid + 1}) = {s[mid]}; the answer is {'here' if s[mid] == t else 'to the left' if t < s[mid] else 'to the right'}", "list": s[lo:hi + 1]})
            if s[mid] == t:
                found = mid
                break
            if s[mid] < t:
                lo = mid + 1
            else:
                hi = mid - 1
        return {"algorithm": "Binary search", "list": s, "found_at": found + 1 if found >= 0 else None, "comparisons": cmp, "steps": steps, "average": "O(log n)",
                "note": "Needs a sorted list, so your numbers were sorted first. Halves the search each step, so 1,000,000 items take about 20 checks."}
    raise CsError("Pick linear or binary.")


# ------------------------------------------------------------------ cheat sheet
STRUCTURES = [
    {"name": "Array / list", "access": "O(1)", "search": "O(n)", "insert": "O(n)", "use": "Ordered items you read by position."},
    {"name": "Linked list", "access": "O(n)", "search": "O(n)", "insert": "O(1) at a known spot", "use": "Frequent inserts and removals in the middle."},
    {"name": "Stack", "access": "O(n)", "search": "O(n)", "insert": "O(1) push/pop", "use": "Undo, back button, parsing brackets. Last in, first out."},
    {"name": "Queue", "access": "O(n)", "search": "O(n)", "insert": "O(1) add/remove", "use": "Jobs and tickets in order. First in, first out."},
    {"name": "Hash table (dict, set)", "access": "O(1) average", "search": "O(1) average", "insert": "O(1) average", "use": "Fast lookup by key, counting, removing duplicates."},
    {"name": "Binary search tree", "access": "O(log n) if balanced", "search": "O(log n) if balanced", "insert": "O(log n) if balanced", "use": "Sorted data with inserts. Unbalanced can degrade to O(n)."},
    {"name": "Heap", "access": "O(1) smallest/largest", "search": "O(n)", "insert": "O(log n)", "use": "Always get the next most urgent item (priority queue)."},
    {"name": "Graph", "access": "n/a", "search": "O(V+E) BFS/DFS", "insert": "O(1) edge in an adjacency list", "use": "Networks, maps, dependencies, who is connected to whom."},
]
GROWTH = [
    {"big_o": "O(1)", "name": "constant", "example": "Read item 5 of a list"},
    {"big_o": "O(log n)", "name": "logarithmic", "example": "Binary search"},
    {"big_o": "O(n)", "name": "linear", "example": "Scan a list once"},
    {"big_o": "O(n log n)", "name": "linearithmic", "example": "Good sorting (merge sort)"},
    {"big_o": "O(n^2)", "name": "quadratic", "example": "Two nested loops over the same list"},
    {"big_o": "O(2^n)", "name": "exponential", "example": "Naive recursive Fibonacci"},
]


def reference() -> dict:
    return {"structures": STRUCTURES, "growth": GROWTH, "sorts": [{"id": k, "name": v[0], "best": v[1], "average": v[2], "worst": v[3], "note": v[4]} for k, v in SORTS.items()],
            "note": "Big-O describes how work grows as the input n grows, not exact speed."}
