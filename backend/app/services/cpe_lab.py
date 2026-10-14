"""Computer engineering practice tools: number systems, logic, DC circuits and computer architecture.

Built from a computer-engineering course deck (computer technology, networking, logic, DC circuits, digital electronics, operating systems,
architecture). Every calculator shows its working so you can check it by hand. Thresholds and notes marked 'rule of thumb' are not standards.
"""
from __future__ import annotations

import itertools
import math
import re
import struct


class CpeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _num(v, name, lo=None, hi=None, integer=False):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
        raise CpeError(f"{name} must be a number.")
    if integer and v != int(v):
        raise CpeError(f"{name} must be a whole number.")
    if lo is not None and v < lo:
        raise CpeError(f"{name} must be at least {lo}.")
    if hi is not None and v > hi:
        raise CpeError(f"{name} must be at most {hi}.")
    return int(v) if integer else float(v)


# ---------------------------------------------------------------- number systems
_DIGITS = "0123456789abcdefghijklmnopqrstuvwxyz"


def convert(text: str, base: int, bits: int = 8) -> dict:
    base = _num(base, "Base", 2, 36, True)
    bits = _num(bits, "Bits", 2, 64, True)
    t = (text or "").strip().lower().replace("_", "").replace(" ", "")
    neg = t.startswith("-")
    t = t.lstrip("-+")
    if not t or any(c not in _DIGITS[:base] for c in t):
        raise CpeError(f"'{text}' is not a valid base-{base} number.")
    n = int(t, base) * (-1 if neg else 1)
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    out = {"decimal": n, "binary": ("-" if n < 0 else "") + bin(abs(n))[2:], "octal": ("-" if n < 0 else "") + oct(abs(n))[2:],
           "hex": ("-" if n < 0 else "") + hex(abs(n))[2:].upper(), "bits": bits, "signed_range": [lo, hi], "unsigned_range": [0, (1 << bits) - 1]}
    steps = []
    if n < 0:
        if n < lo:
            out["twos_complement"] = None
            steps.append(f"{n} does not fit in {bits} bits signed (smallest is {lo}).")
        else:
            tc = (1 << bits) + n
            out["twos_complement"] = format(tc, f"0{bits}b")
            ones = format((~(-n)) & ((1 << bits) - 1), f"0{bits}b")
            steps += [f"Write {-n} in {bits} bits: {format(-n, f'0{bits}b')}", f"Invert every bit (one's complement): {ones}", f"Add 1: {out['twos_complement']}"]
    else:
        if n > hi:
            steps.append(f"{n} does not fit in {bits} bits signed (largest is {hi}); as unsigned it fits only up to {(1 << bits) - 1}.")
            out["twos_complement"] = format(n, f"0{bits}b") if n < (1 << bits) else None
        else:
            out["twos_complement"] = format(n, f"0{bits}b")
            steps.append(f"A non-negative number that fits is its plain binary, padded to {bits} bits: {out['twos_complement']}")
    out["steps"] = steps
    out["lesson"] = "One's complement only inverts the bits. Two's complement inverts then adds 1; that is what computers store for negatives."
    return out


def signed_add(a: int, b: int, bits: int = 8, subtract: bool = False) -> dict:
    bits = _num(bits, "Bits", 2, 64, True)
    a, b = _num(a, "A", integer=True), _num(b, "B", integer=True)
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    for nm, v in (("A", a), ("B", b)):
        if not lo <= v <= hi:
            raise CpeError(f"{nm} does not fit in {bits} bits signed ({lo} to {hi}).")
    true = a - b if subtract else a + b
    mask = (1 << bits) - 1
    raw = ((a & mask) + ((-b if subtract else b) & mask)) & mask
    res = raw - (1 << bits) if raw >> (bits - 1) else raw
    ov = not lo <= true <= hi
    return {"a_bits": format(a & mask, f"0{bits}b"), "b_bits": format(b & mask, f"0{bits}b"), "result_bits": format(raw, f"0{bits}b"), "result": res, "true_value": true,
            "overflow": ov, "verdict": f"Overflow: the true answer {true} does not fit in {bits} bits, so the stored result {res} is wrong." if ov else f"Fits: {res}.",
            "lesson": "Overflow in signed arithmetic happens when two numbers of the same sign give a result of the opposite sign."}


def ieee754(x: float, double: bool = False) -> dict:
    x = _num(x, "Value")
    fmt, ifmt, eb, mb, bias = (">d", ">Q", 11, 52, 1023) if double else (">f", ">I", 8, 23, 127)
    try:
        raw = struct.unpack(ifmt, struct.pack(fmt, x))[0]
    except OverflowError:
        raise CpeError("That value is too large for this format (it would become infinity).")
    total = 1 + eb + mb
    s = raw >> (eb + mb)
    e = (raw >> mb) & ((1 << eb) - 1)
    m = raw & ((1 << mb) - 1)
    back = struct.unpack(fmt, struct.pack(ifmt, raw))[0]
    kind = "zero" if e == 0 and m == 0 else "subnormal" if e == 0 else "normal"
    return {"format": "float64" if double else "float32", "sign": s, "exponent_bits": format(e, f"0{eb}b"), "mantissa_bits": format(m, f"0{mb}b"), "exponent_value": e - bias if kind == "normal" else None,
            "kind": kind, "stored_value": back, "error": back - x, "hex": format(raw, f"0{total // 4}X"),
            "lesson": "Most decimals (0.1) cannot be stored exactly in binary, so the stored value is the nearest one. Never compare floats with ==."}


# ---------------------------------------------------------------- Boolean logic
_TOK = re.compile(r"\s*(NAND|NOR|XNOR|XOR|AND|OR|NOT|[A-Za-z]|[01]|[()~!&|^+*'])", re.I)


def _tokens(s: str):
    s, i, out = s.strip(), 0, []
    while i < len(s):
        m = _TOK.match(s, i)
        if not m:
            raise CpeError(f"Unexpected text near '{s[i:i + 8]}'.")
        out.append(m.group(1))
        i = m.end()
    return out


class _P:
    PRI = {"OR": 1, "NOR": 1, "XOR": 2, "XNOR": 2, "AND": 3, "NAND": 3}

    def __init__(self, toks):
        norm = []
        for t in toks:
            u = t.upper()
            norm.append({"+": "OR", "|": "OR", "*": "AND", "&": "AND", "^": "XOR", "~": "NOT", "!": "NOT"}.get(u, u if len(u) > 1 else t))
        # implicit AND between adjacent operands: AB means A AND B; a trailing ' means NOT
        out = []
        for i, t in enumerate(norm):
            if t == "'":
                out.append(("POST",))
                continue
            if out and self._is_operand_end(out[-1]) and self._is_operand_start(t):
                out.append("AND")
            out.append(t)
        self.t, self.i = out, 0

    @staticmethod
    def _is_operand_end(t):
        return t == ")" or t == ("POST",) or (isinstance(t, str) and (t in "01" or (len(t) == 1 and t.isalpha())))

    @staticmethod
    def _is_operand_start(t):
        return t == "(" or t == "NOT" or (isinstance(t, str) and (t in "01" or (len(t) == 1 and t.isalpha())))

    def peek(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def take(self):
        v = self.peek()
        self.i += 1
        return v

    def expr(self, minp=1):
        left = self.unary()
        while True:
            op = self.peek()
            if not isinstance(op, str) or op not in self.PRI or self.PRI[op] < minp:
                return left
            self.take()
            right = self.expr(self.PRI[op] + 1)
            left = (op, left, right)

    def unary(self):
        t = self.take()
        if t == "NOT":
            node = ("NOT", self.unary())
        elif t == "(":
            node = self.expr()
            if self.take() != ")":
                raise CpeError("A bracket is not closed.")
        elif isinstance(t, str) and t in ("0", "1"):
            node = ("CONST", int(t))
        elif isinstance(t, str) and len(t) == 1 and t.isalpha():
            node = ("VAR", t.upper())
        else:
            raise CpeError("The expression is incomplete or has an operator in the wrong place.")
        while self.peek() == ("POST",):
            self.take()
            node = ("NOT", node)
        return node


def _parse(text: str):
    if not text or not text.strip():
        raise CpeError("Type a Boolean expression, for example A AND (B OR NOT C).")
    p = _P(_tokens(text))
    node = p.expr()
    if p.i != len(p.t):
        raise CpeError("There is extra text after the end of the expression.")
    return node


def _vars(n, acc):
    if n[0] == "VAR":
        acc.add(n[1])
    elif n[0] != "CONST":
        for c in n[1:]:
            _vars(c, acc)
    return acc


def _ev(n, env):
    k = n[0]
    if k == "VAR":
        return env[n[1]]
    if k == "CONST":
        return n[1]
    if k == "NOT":
        return 1 - _ev(n[1], env)
    a, b = _ev(n[1], env), _ev(n[2], env)
    return {"AND": a & b, "OR": a | b, "XOR": a ^ b, "NAND": 1 - (a & b), "NOR": 1 - (a | b), "XNOR": 1 - (a ^ b)}[k]


def _qm(minterms: list[int], n: int) -> list[str]:
    if not minterms:
        return []
    if len(minterms) == 1 << n:
        return ["-" * n]
    groups = {format(m, f"0{n}b") for m in minterms}
    primes = set()
    cur = groups
    while cur:
        nxt, used = set(), set()
        for a, b in itertools.combinations(sorted(cur), 2):
            d = [i for i in range(n) if a[i] != b[i]]
            if len(d) == 1:
                nxt.add(a[:d[0]] + "-" + a[d[0] + 1:])
                used.update((a, b))
        primes |= cur - used
        cur = nxt

    def covers(p, m):
        return all(c == "-" or c == b for c, b in zip(p, format(m, f"0{n}b")))
    chosen, left = [], set(minterms)
    primes = sorted(primes)
    for m in minterms:
        c = [p for p in primes if covers(p, m)]
        if len(c) == 1 and c[0] not in chosen:
            chosen.append(c[0])
    for p in chosen:
        left -= {m for m in left if covers(p, m)}
    while left:
        best = max(primes, key=lambda p: (sum(1 for m in left if covers(p, m)), p.count("-")))
        chosen.append(best)
        left -= {m for m in left if covers(best, m)}
    return sorted(set(chosen))


def _term(p: str, names: list[str]) -> str:
    return "".join(f"{names[i]}{'' if c == '1' else chr(39)}" for i, c in enumerate(p) if c != "-") or "1"


def logic(text: str) -> dict:
    node = _parse(text)
    names = sorted(_vars(node, set()))
    if len(names) > 6:
        raise CpeError("Use at most 6 variables.")
    if not names:
        names = ["A"]
    rows, minterms = [], []
    for i, vals in enumerate(itertools.product((0, 1), repeat=len(names))):
        out = _ev(node, dict(zip(names, vals)))
        rows.append({"inputs": list(vals), "output": out})
        if out:
            minterms.append(i)
    primes = _qm(minterms, len(names))
    sop = " + ".join(_term(p, names) for p in primes) if primes else "0"
    kind = "always 1 (a tautology)" if len(minterms) == len(rows) else "always 0 (a contradiction)" if not minterms else "depends on the inputs"
    return {"variables": names, "rows": rows, "minterms": minterms, "minimal_sum_of_products": sop, "terms": len(primes), "result_is": kind,
            "notation": "A' means NOT A, AB means A AND B, + means OR.",
            "lesson": "A minimal sum of products uses fewer gates. Karnaugh maps find the same groups by eye; this finds them by the Quine-McCluskey method."}


def equivalent(a: str, b: str) -> dict:
    na, nb = _parse(a), _parse(b)
    names = sorted(_vars(na, set()) | _vars(nb, set())) or ["A"]
    if len(names) > 6:
        raise CpeError("Use at most 6 variables.")
    diff = []
    for vals in itertools.product((0, 1), repeat=len(names)):
        env = dict(zip(names, vals))
        if _ev(na, env) != _ev(nb, env):
            diff.append({"inputs": dict(zip(names, vals)), "first": _ev(na, env), "second": _ev(nb, env)})
    return {"equivalent": not diff, "variables": names, "differences": diff[:8],
            "verdict": "The two expressions are equivalent (same output for every input)." if not diff else f"Not equivalent: they differ in {len(diff)} of {2 ** len(names)} input rows.",
            "lesson": "De Morgan: NOT(A AND B) = NOT A OR NOT B, and NOT(A OR B) = NOT A AND NOT B. Try both."}


# ---------------------------------------------------------------- DC circuits
def ohm(v=None, i=None, r=None, p=None) -> dict:
    given = {k: x for k, x in (("v", v), ("i", i), ("r", r), ("p", p)) if x not in (None, "")}
    if len(given) != 2:
        raise CpeError("Fill in exactly two of voltage, current, resistance and power.")
    for k, x in given.items():
        given[k] = _num(x, {"v": "Voltage", "i": "Current", "r": "Resistance", "p": "Power"}[k])
    g = given
    if "v" in g and "i" in g:
        V, I = g["v"], g["i"]
        if I == 0:
            raise CpeError("Current of 0 gives no resistance value.")
        R, P = V / I, V * I
    elif "v" in g and "r" in g:
        V, R = g["v"], g["r"]
        if R == 0:
            raise CpeError("Resistance cannot be 0.")
        I = V / R
        P = V * I
    elif "i" in g and "r" in g:
        I, R = g["i"], g["r"]
        V, P = I * R, I * I * R
    elif "v" in g and "p" in g:
        V, P = g["v"], g["p"]
        if V == 0:
            raise CpeError("Voltage of 0 cannot give a power.")
        I = P / V
        R = V / I if I else math.inf
    elif "i" in g and "p" in g:
        I, P = g["i"], g["p"]
        if I == 0:
            raise CpeError("Current of 0 cannot give a power.")
        V = P / I
        R = V / I
    else:
        P, R = g["p"], g["r"]
        if R <= 0 or P < 0:
            raise CpeError("Power must be 0 or more and resistance more than 0.")
        I = math.sqrt(P / R)
        V = I * R
    return {"voltage_v": V, "current_a": I, "resistance_ohm": R, "power_w": P,
            "working": ["V = I x R", "P = V x I = I^2 x R = V^2 / R"],
            "lesson": "Power rises with the square of current: double the current and a wire or resistor gets four times as hot."}


def resistors(kind: str, values: list) -> dict:
    if kind not in ("series", "parallel"):
        raise CpeError("Kind must be series or parallel.")
    if not isinstance(values, list) or len(values) < 2 or len(values) > 20:
        raise CpeError("Give 2 to 20 resistor values.")
    vs = [_num(x, "Each resistor", 0.0) for x in values]
    if kind == "series":
        tot = sum(vs)
        w = "R = R1 + R2 + ..."
    else:
        if any(x == 0 for x in vs):
            tot, w = 0.0, "A 0 ohm branch shorts the others: total is 0."
        else:
            tot, w = 1 / sum(1 / x for x in vs), "1/R = 1/R1 + 1/R2 + ..."
    return {"total_ohm": tot, "working": w, "lesson": "Series adds. Parallel is always smaller than the smallest branch."}


def divider(vin: float, r1: float, r2: float, load: float | None = None) -> dict:
    vin, r1, r2 = _num(vin, "Input voltage"), _num(r1, "R1", 0.0), _num(r2, "R2", 0.0)
    if r1 + r2 == 0:
        raise CpeError("R1 and R2 cannot both be 0.")
    out = vin * r2 / (r1 + r2)
    res = {"unloaded_v": out, "formula": "Vout = Vin x R2 / (R1 + R2)", "current_a": vin / (r1 + r2)}
    if load not in (None, ""):
        rl = _num(load, "Load", 0.0)
        r2l = 0.0 if rl == 0 else (r2 * rl / (r2 + rl) if r2 + rl else 0)
        res["loaded_v"] = vin * r2l / (r1 + r2l) if r1 + r2l else 0.0
        res["note"] = "A load in parallel with R2 pulls the output down. Keep the load at least 10 times R2 (rule of thumb)."
    return res


def led_resistor(supply: float, forward: float, current_ma: float) -> dict:
    s, f, i = _num(supply, "Supply"), _num(forward, "LED forward voltage", 0.0), _num(current_ma, "Current (mA)", 0.1) / 1000
    if s <= f:
        raise CpeError("The supply must be higher than the LED's forward voltage.")
    r = (s - f) / i
    std = [10, 12, 15, 18, 22, 27, 33, 39, 47, 56, 68, 82]
    nxt = next((round(b * 10 ** e) for e in range(0, 7) for b in std if b * 10 ** e >= r), None)
    return {"exact_ohm": r, "next_standard_ohm_E12": nxt, "resistor_power_w": (s - f) * i, "working": "R = (Vsupply - Vf) / I",
            "lesson": "Round the resistor up to the next standard value so the current is never above the limit. Pick a resistor rated for at least twice its power."}


def rc_time(r: float, c_uf: float, v: float = 12.0) -> dict:
    r, c, v = _num(r, "Resistance", 0.0), _num(c_uf, "Capacitance (uF)", 0.0) * 1e-6, _num(v, "Voltage", 0.0)
    tau = r * c
    return {"tau_s": tau, "to_63pct_s": tau, "to_95pct_s": 3 * tau, "to_99pct_s": 4.6 * tau, "peak_current_a": v / r if r else None, "energy_stored_j": 0.5 * c * v * v,
            "lesson": "A capacitor charges to about 63% in one time constant and is nearly full after five."}


_COL = ["black", "brown", "red", "orange", "yellow", "green", "blue", "violet", "grey", "white"]
_MUL = {**{c: 10 ** i for i, c in enumerate(_COL)}, "gold": 0.1, "silver": 0.01}
_TOL = {"brown": 1, "red": 2, "green": 0.5, "blue": 0.25, "violet": 0.1, "grey": 0.05, "gold": 5, "silver": 10}


def color_code(b1: str, b2: str, mult: str, tol: str = "gold") -> dict:
    b1, b2, mult, tol = (str(x).strip().lower() for x in (b1, b2, mult, tol))
    if b1 not in _COL or b2 not in _COL:
        raise CpeError("Digit bands must be black, brown, red, orange, yellow, green, blue, violet, grey or white.")
    if mult not in _MUL:
        raise CpeError("Unknown multiplier colour.")
    if tol not in _TOL:
        raise CpeError("Unknown tolerance colour.")
    val = (_COL.index(b1) * 10 + _COL.index(b2)) * _MUL[mult]
    t = _TOL[tol]
    return {"ohms": val, "tolerance_pct": t, "low": val * (1 - t / 100), "high": val * (1 + t / 100), "lesson": "First two bands are digits, the third is how many zeros, the fourth is tolerance."}


# ---------------------------------------------------------------- computer architecture
def amat(hit_time: float, miss_rate_pct: float, miss_penalty: float) -> dict:
    h, m, p = _num(hit_time, "Hit time", 0.0), _num(miss_rate_pct, "Miss rate", 0.0, 100) / 100, _num(miss_penalty, "Miss penalty", 0.0)
    return {"amat": h + m * p, "formula": "AMAT = hit time + miss rate x miss penalty", "lesson": "A 5% miss rate with a 100-cycle penalty adds 5 cycles to every access on average."}


def cache_split(address_bits: int, cache_bytes: int, block_bytes: int, ways: int = 1) -> dict:
    a = _num(address_bits, "Address bits", 4, 64, True)
    c, b, w = (_num(x, n, 1, integer=True) for x, n in ((cache_bytes, "Cache size"), (block_bytes, "Block size"), (ways, "Ways")))
    for nm, v in (("Cache size", c), ("Block size", b), ("Ways", w)):
        if v & (v - 1):
            raise CpeError(f"{nm} must be a power of two.")
    lines = c // b
    if lines < w:
        raise CpeError("Fewer blocks than ways: reduce the ways or enlarge the cache.")
    sets = lines // w
    off, idx = int(math.log2(b)), int(math.log2(sets))
    tag = a - off - idx
    if tag < 0:
        raise CpeError("The address is too small for this cache.")
    return {"offset_bits": off, "index_bits": idx, "tag_bits": tag, "blocks": lines, "sets": sets, "organisation": "direct-mapped" if w == 1 else ("fully associative" if sets == 1 else f"{w}-way set associative"),
            "lesson": "Address = tag | index | offset. The offset picks the byte in a block, the index picks the set, the tag proves it is the right block."}


def cpu_time(instructions: float, cpi: float, clock_ghz: float) -> dict:
    n, c, g = _num(instructions, "Instructions", 1.0), _num(cpi, "CPI", 0.01), _num(clock_ghz, "Clock (GHz)", 0.001)
    t = n * c / (g * 1e9)
    return {"seconds": t, "mips": n / t / 1e6, "formula": "Time = instructions x CPI / clock rate", "lesson": "A higher clock does not help if CPI rises with it. Compare programs by time, not by MHz or MIPS."}


def amdahl(parallel_pct: float, speedup_part: float) -> dict:
    p, s = _num(parallel_pct, "Improved share", 0.0, 100) / 100, _num(speedup_part, "Speedup of that part", 1.0)
    total = 1 / ((1 - p) + p / s)
    return {"overall_speedup": total, "limit_if_part_infinitely_fast": 1 / (1 - p) if p < 1 else None, "formula": "Speedup = 1 / ((1 - p) + p / s)",
            "lesson": "The part you did not improve caps the gain. With 90% improved, the best possible speedup is 10, however fast that part gets."}


def pipeline(stages: int, instructions: int, stall_cycles: float = 0.0) -> dict:
    k, n, st = _num(stages, "Stages", 1, 64, True), _num(instructions, "Instructions", 1, integer=True), _num(stall_cycles, "Stall cycles", 0.0)
    pip = k + (n - 1) + st
    seq = k * n
    return {"pipelined_cycles": pip, "sequential_cycles": seq, "speedup": seq / pip, "ideal_limit": k,
            "working": "Pipelined = k + (n - 1) + stalls; sequential = k x n (all stages the same length)",
            "lesson": "The speedup approaches k only for long runs with no stalls. Hazards (data, control, structural) add stall cycles; deeper pipelines make each branch miss costlier."}


def raid(level: int, disks: int, size_tb: float) -> dict:
    d, s = _num(disks, "Disks", 1, 64, True), _num(size_tb, "Disk size (TB)", 0.001)
    lv = _num(level, "RAID level", integer=True)
    need = {0: 2, 1: 2, 5: 3, 6: 4, 10: 4}
    if lv not in need:
        raise CpeError("Supported levels: 0, 1, 5, 6, 10.")
    if d < need[lv] or (lv == 10 and d % 2):
        raise CpeError(f"RAID {lv} needs at least {need[lv]} disks" + (" and an even number." if lv == 10 else "."))
    usable = {0: d * s, 1: s, 5: (d - 1) * s, 6: (d - 2) * s, 10: d / 2 * s}[lv]
    tol = {0: "none", 1: f"{d - 1} disks", 5: "1 disk", 6: "2 disks", 10: "1 disk per mirror pair (at least 1)"}[lv]
    return {"usable_tb": usable, "raw_tb": d * s, "failures_survived": tol,
            "lesson": "RAID keeps the system running when a disk fails. It is not a backup: deletion, ransomware and fire hit every disk at once."}


SAMPLE = {"logic": "A AND B OR A AND NOT B", "logic_b": "A", "bin": "-45"}
SLIPS = [
    "Computer engineering deck: the 'one's complement' steps end with 'add 1'. That is the two's complement step. One's complement stops after inverting the bits.",
    "Computer engineering deck: IPv6 slide says 'IPSec is mandatory'. It was required in the first IPv6 specification, but later standards made it a recommendation. IPv6 does not secure traffic by itself, and 'no NAT needed' does not mean no firewall.",
    "Computer engineering deck: IPv4 classes A, B and C are taught as how addresses are handed out. Classful addressing was replaced by CIDR in the 1990s; today you read the prefix length. Class A also includes 127.x.x.x, which is loopback, not a normal network.",
    "Computer engineering deck: 'earth is zero potential, so ground is the reference' is a simplification. A circuit's 0 V reference is chosen, and in a vehicle it is the chassis, which is not connected to earth. Voltage only means something between two points.",
    "Computer engineering deck: pipelining is shown as 'the deeper the pipeline, the greater the parallelism and faster throughput'. Deeper pipelines raise the clock but also the cost of every branch miss and hazard, so there is a best depth, not 'deeper is faster'.",
    "Computer engineering deck: the pipeline speedup is stated as non-pipelined time over pipelined time without saying that the unpipelined time per task is assumed to equal k times the clock. If stages are uneven, the slowest stage sets the clock.",
]
NOT_BUILT = ["Real hardware: soldering, a breadboard, an oscilloscope, FPGA or microcontroller boards. These tools check your arithmetic; the circuit still has to be built and measured.",
             "A full CPU or logic simulator with waveforms (use Logisim, Digital or a Verilog simulator).",
             "I read the deck's outline and sampled its text. It has 843 pages, so every slide has not been checked."]


def reference() -> dict:
    return {"sample": SAMPLE, "slips": SLIPS, "not_built": NOT_BUILT}
