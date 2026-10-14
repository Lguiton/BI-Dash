"""Graded drill generator for IT fundamentals. A question is rebuilt from its id (kind:seed), so grading
never trusts the browser and needs no stored answer."""
from __future__ import annotations

import json
import random
import re

from app.services import it_fund as F, state, workspaces


class DrillError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    try:
        return workspaces.active()
    except Exception:  # noqa: BLE001
        return "default"


def _bin8(n): return format(n, "08b")


def _q_bin2dec(r):
    n = r.randint(1, 255)
    return f"Convert the binary number {_bin8(n)} to decimal.", str(n), "int", f"Add the places switched on: {F.convert(str(n))['sum']} = {n}."


def _q_dec2bin(r):
    n = r.randint(1, 255)
    return f"Convert decimal {n} to binary (8 bits).", _bin8(n), "bin", f"{n} = {F.convert(str(n))['sum']}, so the bits are {_bin8(n)}."


def _q_hex2dec(r):
    n = r.randint(16, 255)
    return f"Convert the hex number {n:X} to decimal.", str(n), "int", f"{n:X} = {n // 16} x 16 + {n % 16} = {n}."


def _q_dec2hex(r):
    n = r.randint(16, 255)
    return f"Convert decimal {n} to hex.", f"{n:X}", "hex", f"{n} = {n // 16} x 16 + {n % 16}, so the digits are {n // 16:X} and {n % 16:X}."


_MODES = ["644", "600", "640", "750", "755", "700", "664", "444", "777", "1777", "1775", "4755", "2755", "660", "754", "775", "400"]


def _q_oct2sym(r):
    m = r.choice(_MODES)
    return f"Write chmod {m} as nine permission characters (for example rwxr-xr-x).", F._sym_from_octal(m), "sym", f"Per digit r=4, w=2, x=1: {m} gives {F._sym_from_octal(m)}."


def _q_sym2oct(r):
    m = r.choice(_MODES)
    sy = F._sym_from_octal(m)
    return f"What octal mode is {sy}?", m, "oct", f"Add r=4, w=2, x=1 for each group of three{', with a leading special digit for s/t' if len(m) == 4 else ''}: {sy} is {m}."


def _q_who(r):
    m = r.choice(["640", "750", "604", "700", "664", "444", "620"])
    who = r.choice(["owner", "group", "others"])
    act = r.choice([("read", 4), ("write", 2), ("execute", 1)])
    d = int(m[("owner", "group", "others").index(who)])
    return f"With mode {m}, can the {who} {act[0]} the file? Answer yes or no.", "yes" if d & act[1] else "no", "yn", f"The {who} digit is {d}; {act[0]} is worth {act[1]}, and {d} {'includes' if d & act[1] else 'does not include'} it."


def _q_umask(r):
    um = r.choice(["022", "027", "077", "002", "037"])
    kind = r.choice(["file", "directory"])
    base = 0o666 if kind == "file" else 0o777
    res = format(base & ~int(um, 8), "03o")
    return f"With umask {um}, what mode does a new {kind} get?", res, "oct", f"Start at {format(base, 'o')} and remove the umask bits: {res}."


def _q_gate(r):
    g = r.choice(["AND", "OR", "XOR", "NAND", "NOR", "XNOR"])
    a, b = r.randint(0, 1), r.randint(0, 1)
    out = F.GATES[g][1](a, b)
    return f"A = {a}, B = {b}. What does {g} output (0 or 1)?", str(out), "bit", f"{g}: {F.GATES[g][2]}"


def _q_circuit(r):
    expr = r.choice(["(A AND B) OR NOT C", "A XOR B", "NOT (A OR B)", "(A OR B) AND C", "NOT A AND B"])
    t = F.circuit(expr)
    row = r.choice(t["rows"])
    given = ", ".join(f"{n} = {row[n]}" for n in t["inputs"])
    return f"{given}. What is {expr} (0 or 1)?", str(row["out"]), "bit", "Work inside the brackets first, then NOT, then AND, then OR."


def _q_storage(r):
    n = r.choice([0.5, 1, 2, 4, 8])
    u = "TB"
    gib = round(n * 1e12 / 1024 ** 3)
    return f"A drive is sold as {n:g} TB. About how many GiB does the operating system show? (whole number)", str(gib), "num", f"{n:g} x 10^12 bytes / 1024^3 = about {gib} GiB. Nothing is missing: different unit."


KINDS = {
    "bin2dec": ("Binary to decimal", _q_bin2dec), "dec2bin": ("Decimal to binary", _q_dec2bin), "hex2dec": ("Hex to decimal", _q_hex2dec), "dec2hex": ("Decimal to hex", _q_dec2hex),
    "oct2sym": ("chmod number to letters", _q_oct2sym), "sym2oct": ("chmod letters to number", _q_sym2oct), "who": ("Who can do what", _q_who), "umask": ("umask results", _q_umask),
    "gate": ("Logic gates", _q_gate), "circuit": ("Circuits", _q_circuit), "storage": ("Drive sizes", _q_storage),
}


def _build(qid: str) -> dict:
    m = re.fullmatch(r"([a-z0-9]+):(\d{1,9})", qid or "")
    if not m or m.group(1) not in KINDS:
        raise DrillError(f"Unknown question {qid}.", 404)
    kind, seed = m.group(1), int(m.group(2))
    prompt, ans, typ, why = KINDS[kind][1](random.Random(seed * 7919 + sum(map(ord, kind))))
    return {"id": qid, "kind": kind, "prompt": prompt, "answer": ans, "type": typ, "why": why}


def questions(kind: str = "", n: int = 10, seed: int = 0) -> dict:
    if kind and kind not in KINDS:
        raise DrillError("Unknown drill kind.", 404)
    n = max(1, min(int(n), 30))
    rnd = random.Random(seed or None)
    ks = [kind] if kind else list(KINDS)
    out = []
    for i in range(n):
        q = _build(f"{ks[i % len(ks)] if kind else rnd.choice(ks)}:{rnd.randint(1, 10**8)}")
        out.append({"id": q["id"], "kind": q["kind"], "label": KINDS[q["kind"]][0], "prompt": q["prompt"], "type": q["type"]})
    return {"questions": out, "kinds": [{"id": k, "label": v[0]} for k, v in KINDS.items()],
            "tips": "Type the answer only. Binary may include spaces, hex is not case sensitive, and permission strings are nine characters such as rwxr-xr--."}


def _norm_eq(typ: str, given: str, ans: str) -> bool:
    g = (given or "").strip().replace(" ", "").replace("_", "")
    try:
        if typ in ("int", "num"):
            return abs(float(g) - float(ans)) <= (1 if typ == "num" else 0)
        if typ == "bin":
            return bool(re.fullmatch(r"(0b)?[01]+", g, re.I)) and int(g.replace("0b", "").replace("0B", ""), 2) == int(ans, 2)
        if typ == "hex":
            return int(g.replace("0x", "").replace("0X", ""), 16) == int(ans, 16)
        if typ == "oct":
            return g.lstrip("0") == ans.lstrip("0") if len(g) != len(ans) else g == ans
        if typ == "sym":
            return g.lower() == ans.lower() or ("-" + ans) == g
        if typ == "yn":
            return g.lower()[:1] == ans[:1]
        if typ == "bit":
            return g == ans
    except ValueError:
        return False
    return g.lower() == ans.lower()


def _stats() -> dict:
    raw = state.kv_get(f"itdrill_stats:{_ws()}")
    try:
        return json.loads(raw) if raw else {}
    except ValueError:
        return {}


def grade(answers: dict) -> dict:
    if not isinstance(answers, dict) or not answers or len(answers) > 60:
        raise DrillError("Send your answers as {question id: answer}.")
    stats = _stats()
    res, right = [], 0
    for qid, given in answers.items():
        q = _build(qid)
        ok = _norm_eq(q["type"], str(given)[:40], q["answer"])
        right += ok
        st = stats.setdefault(q["kind"], [0, 0])
        st[0] += ok
        st[1] += 1
        res.append({"id": qid, "kind": q["kind"], "ok": ok, "yours": str(given)[:40], "answer": q["answer"], "why": q["why"], "prompt": q["prompt"]})
    state.kv_set(f"itdrill_stats:{_ws()}", json.dumps(stats))
    weak = sorted({r["kind"] for r in res if not r["ok"]})
    return {"right": right, "total": len(res), "pct": round(100 * right / len(res)), "results": res,
            "weak": [KINDS[k][0] for k in weak], "message": ("Practise next: " + ", ".join(KINDS[k][0] for k in weak)) if weak else "No misses. Try a harder mix or another kind."}


def progress() -> dict:
    st = _stats()
    rows = [{"kind": k, "label": v[0], "answered": st.get(k, [0, 0])[1], "pct": round(100 * st[k][0] / st[k][1]) if st.get(k, [0, 0])[1] else None} for k, v in KINDS.items()]
    return {"rows": rows}


def reset() -> dict:
    state.kv_set(f"itdrill_stats:{_ws()}", "{}")
    return {"cleared": True}
