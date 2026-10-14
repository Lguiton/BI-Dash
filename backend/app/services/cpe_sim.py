"""Small simulators for computer engineering: a logic circuit, a tiny CPU, a DC circuit solver and a cache.

These are teaching simulators written from scratch. They run what you type, show every step, and have deliberate limits (listed in each
SLIPS or NOT_BUILT). They are not Logisim, a Verilog simulator, SPICE or a cycle-accurate model of a real processor.
"""
from __future__ import annotations

import math
import re

import numpy as np

from app.services.cpe_lab import CpeError


# ================================================================ logic circuit simulator
_GATES = {"AND": lambda a: int(all(a)), "OR": lambda a: int(any(a)), "NAND": lambda a: 1 - int(all(a)), "NOR": lambda a: 1 - int(any(a)),
          "XOR": lambda a: sum(a) % 2, "XNOR": lambda a: 1 - sum(a) % 2, "NOT": lambda a: 1 - a[0], "BUF": lambda a: a[0]}
_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def logic_circuit(netlist: str, stimulus: str, cycles: int = 8) -> dict:
    """Netlist lines: INPUT A B | Y = AND(A, B) | Q = DFF(D) (rising-edge flip-flop, starts at 0). Stimulus lines: A: 0 1 1 0 (repeats)."""
    if not isinstance(cycles, int) or isinstance(cycles, bool) or not 1 <= cycles <= 64:
        raise CpeError("Cycles must be a whole number from 1 to 64.")
    inputs, gates, ffs = [], {}, {}
    for ln in (netlist or "").splitlines():
        ln = ln.split("#")[0].strip()
        if not ln:
            continue
        if ln.upper().startswith("INPUT"):
            for n in ln.split()[1:]:
                if not _NAME.match(n):
                    raise CpeError(f"'{n}' is not a valid signal name.")
                inputs.append(n)
            continue
        m = re.fullmatch(r"([A-Za-z_]\w*)\s*=\s*([A-Za-z]+)\s*\(([^)]*)\)", ln)
        if not m:
            raise CpeError(f"Line '{ln}': use 'Y = AND(A, B)' or 'Q = DFF(D)'.")
        out, kind, args = m.group(1), m.group(2).upper(), [a.strip() for a in m.group(3).split(",") if a.strip()]
        if out in gates or out in ffs or out in inputs:
            raise CpeError(f"Signal '{out}' is defined twice.")
        if kind == "DFF":
            if len(args) != 1:
                raise CpeError(f"{out}: DFF takes exactly one input (D).")
            ffs[out] = args[0]
        elif kind in _GATES:
            need = 1 if kind in ("NOT", "BUF") else 2
            if len(args) < need or (need == 1 and len(args) != 1):
                raise CpeError(f"{out}: {kind} needs {'one input' if need == 1 else 'at least two inputs'}.")
            if len(args) > 8:
                raise CpeError(f"{out}: at most 8 inputs.")
            gates[out] = (kind, args)
        else:
            raise CpeError(f"Unknown gate '{kind}'. Use AND, OR, NOT, NAND, NOR, XOR, XNOR, BUF or DFF.")
    if not inputs and not ffs:
        raise CpeError("Declare at least one input with 'INPUT A B'.")
    if len(gates) + len(ffs) > 200:
        raise CpeError("At most 200 gates and flip-flops.")
    known = set(inputs) | set(gates) | set(ffs)
    for src in [a for _, args in gates.values() for a in args] + list(ffs.values()):
        if src not in known and src not in ("0", "1"):
            raise CpeError(f"Signal '{src}' is used but never defined.")
    # order combinational gates (detect loops)
    order, state = [], {}

    def visit(n, path):
        if n in inputs or n in ffs or n in ("0", "1"):
            return
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            raise CpeError("Feedback loop without a flip-flop: " + " -> ".join(path + [n]) + ". Break the loop with a DFF (latches built from gates are not simulated).")
        state[n] = 1
        for a in gates[n][1]:
            visit(a, path + [n])
        state[n] = 2
        order.append(n)
    for g in gates:
        visit(g, [])
    stim = {}
    for ln in (stimulus or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ":" not in ln:
            raise CpeError(f"Stimulus line '{ln}': use 'A: 0 1 1 0'.")
        nm, vals = ln.split(":", 1)
        nm = nm.strip()
        if nm not in inputs:
            raise CpeError(f"'{nm}' is not a declared input.")
        v = vals.split()
        if not v or any(x not in ("0", "1") for x in v):
            raise CpeError(f"Stimulus for {nm} must be 0s and 1s.")
        stim[nm] = [int(x) for x in v]
    ff_state = {f: 0 for f in ffs}
    rows = []
    for t in range(cycles):
        env = {"0": 0, "1": 1}
        for i in inputs:
            s = stim.get(i, [0])
            env[i] = s[t % len(s)]
        env.update(ff_state)
        for g in order:
            k, args = gates[g]
            env[g] = _GATES[k]([env[a] for a in args])
        rows.append({"cycle": t, **{k: v for k, v in env.items() if k not in ("0", "1")}})
        ff_state = {f: env[d] for f, d in ffs.items()}
    names = inputs + list(ffs) + [g for g in gates]
    wave = {n: "".join("▔" if r[n] else "▁" for r in rows) for n in names}
    return {"signals": names, "rows": rows, "waveform": wave, "gates": len(gates), "flip_flops": len(ffs),
            "lesson": "Gates settle instantly; a flip-flop copies its input only at the clock tick, so its output lags by one cycle. That one-cycle memory is how counters and registers work."}


LOGIC_SAMPLES = {
    "adder": ("INPUT A B CIN\nX1 = XOR(A, B)\nS = XOR(X1, CIN)\nA1 = AND(A, B)\nA2 = AND(X1, CIN)\nCOUT = OR(A1, A2)", "A: 0 0 0 0 1 1 1 1\nB: 0 0 1 1 0 0 1 1\nCIN: 0 1 0 1 0 1 0 1"),
    "counter": ("INPUT EN\nN0 = NOT(Q0)\nD0 = XOR(Q0, EN)\nT1 = AND(Q0, EN)\nD1 = XOR(Q1, T1)\nQ0 = DFF(D0)\nQ1 = DFF(D1)", "EN: 1"),
}


# ================================================================ tiny CPU
class _Halt(Exception):
    pass


def _imm(tok: str, line: int) -> int:
    try:
        v = int(tok, 0)
    except ValueError:
        raise CpeError(f"Line {line}: '{tok}' is not a number.")
    if not -128 <= v <= 255:
        raise CpeError(f"Line {line}: {v} does not fit in 8 bits.")
    return v & 0xFF


_REG = {"R0": 0, "R1": 1, "R2": 2, "R3": 3}
_ALU = {"ADD", "SUB", "AND", "OR", "XOR", "CMP"}


def _parse_prog(src: str):
    prog, labels = [], {}
    for n, raw in enumerate((src or "").splitlines(), 1):
        ln = raw.split(";")[0].strip()
        if not ln:
            continue
        while ":" in ln:
            lab, ln = ln.split(":", 1)
            lab = lab.strip().upper()
            if not _NAME.match(lab):
                raise CpeError(f"Line {n}: bad label '{lab}'.")
            if lab in labels:
                raise CpeError(f"Line {n}: label '{lab}' is defined twice.")
            labels[lab] = len(prog)
            ln = ln.strip()
        if not ln:
            continue
        parts = ln.replace(",", " ").split()
        op, args = parts[0].upper(), [a.upper() if a.upper() in _REG else a for a in parts[1:]]
        prog.append((op, args, n, raw.strip()))
    if not prog:
        raise CpeError("Write at least one instruction.")
    if len(prog) > 128:
        raise CpeError("At most 128 instructions.")
    return prog, labels


def cpu_run(source: str, max_steps: int = 500) -> dict:
    """8-bit machine: R0-R3, 64 bytes of memory, flags Z N C. LDI LD ST ADD SUB AND OR XOR CMP MOV INC DEC JMP JZ JNZ JC HALT."""
    if not isinstance(max_steps, int) or isinstance(max_steps, bool) or not 1 <= max_steps <= 2000:
        raise CpeError("Max steps must be 1 to 2000.")
    prog, labels = _parse_prog(source)
    reg, mem, pc, flags = [0] * 4, [0] * 64, 0, {"Z": 0, "N": 0, "C": 0}
    trace, cycles, halted = [], 0, False

    def r(a, n):
        if a not in _REG:
            raise CpeError(f"Line {n}: '{a}' is not a register (R0 to R3).")
        return _REG[a]

    def addr(tok, n):
        t = tok.strip("[]")
        v = _imm(t, n)
        if not 0 <= v < 64:
            raise CpeError(f"Line {n}: memory address {v} is outside 0 to 63.")
        return v

    def setf(res, carry=None):
        flags["Z"], flags["N"] = int((res & 0xFF) == 0), int((res & 0x80) != 0)
        if carry is not None:
            flags["C"] = int(carry)

    def jump(tok, n):
        t = tok.upper()
        if t not in labels:
            raise CpeError(f"Line {n}: unknown label '{tok}'.")
        return labels[t]
    steps = 0
    while steps < max_steps:
        if not 0 <= pc < len(prog):
            break
        op, a, n, raw = prog[pc]
        before, npc, cost, taken = list(reg), pc + 1, 1, None
        if op == "HALT":
            halted = True
            trace.append({"step": steps + 1, "pc": pc, "line": n, "instr": raw, "regs": list(reg), "flags": dict(flags), "cycles": cycles + 1})
            cycles += 1
            break
        if op == "LDI":
            reg[r(a[0], n)] = _imm(a[1], n)
        elif op == "MOV":
            reg[r(a[0], n)] = reg[r(a[1], n)]
        elif op == "LD":
            reg[r(a[0], n)] = mem[addr(a[1], n)]
            cost = 2
        elif op == "ST":
            mem[addr(a[0], n)] = reg[r(a[1], n)]
            cost = 2
        elif op in _ALU:
            d, s = reg[r(a[0], n)], reg[r(a[1], n)]
            if op == "ADD":
                t = d + s
                res, c = t & 0xFF, t > 255
            elif op in ("SUB", "CMP"):
                t = d - s
                res, c = t & 0xFF, t < 0
            elif op == "AND":
                res, c = d & s, None
            elif op == "OR":
                res, c = d | s, None
            else:
                res, c = d ^ s, None
            setf(res, c)
            if op != "CMP":
                reg[r(a[0], n)] = res
        elif op in ("INC", "DEC"):
            i = r(a[0], n)
            t = reg[i] + (1 if op == "INC" else -1)
            reg[i] = t & 0xFF
            setf(reg[i])
        elif op == "JMP":
            npc = jump(a[0], n)
            taken, cost = True, 3
        elif op in ("JZ", "JNZ", "JC"):
            cond = flags["Z"] if op == "JZ" else (1 - flags["Z"]) if op == "JNZ" else flags["C"]
            taken = bool(cond)
            if taken:
                npc, cost = jump(a[0], n), 3
        else:
            raise CpeError(f"Line {n}: unknown instruction '{op}'.")
        steps += 1
        cycles += cost
        trace.append({"step": steps, "pc": pc, "line": n, "instr": raw, "regs": list(reg), "flags": dict(flags), "cycles": cycles, "branch_taken": taken,
                      "changed": [f"R{i}" for i in range(4) if reg[i] != before[i]]})
        pc = npc
    ended = "halted" if halted else "ran off the end" if pc >= len(prog) else f"stopped at {max_steps} steps (possible endless loop)"
    pipe = _pipeline(trace, prog)
    return {"ended": ended, "steps": steps, "cycles": cycles, "registers": reg, "flags": flags, "memory_used": {i: v for i, v in enumerate(mem) if v}, "trace": trace[:300],
            "trace_truncated": len(trace) > 300, "pipeline": pipe,
            "lesson": "Every instruction is fetched, decoded and executed. Branches cost extra cycles here because the next instruction is unknown until the compare finishes."}


def _pipeline(trace, prog) -> dict:
    """Count stalls of a classic 5-stage pipeline for the executed sequence. Assumptions are stated in the result."""
    def writes(op, a):
        return a[0] if op in ("LDI", "MOV", "LD", "ADD", "SUB", "AND", "OR", "XOR", "INC", "DEC") and a and a[0] in _REG else None

    def reads(op, a):
        if op in ("MOV",):
            return [a[1]] if len(a) > 1 else []
        if op in ("ADD", "SUB", "AND", "OR", "XOR", "CMP"):
            return [x for x in a[:2] if x in _REG]
        if op == "ST":
            return [a[1]] if len(a) > 1 and a[1] in _REG else []
        if op in ("INC", "DEC"):
            return [a[0]] if a else []
        return []
    seq = [(prog[t["pc"]][0], prog[t["pc"]][1], t.get("branch_taken")) for t in trace]
    no_fwd = fwd = branch = 0
    for i, (op, a, tk) in enumerate(seq):
        rd = reads(op, a)
        for dist in (1, 2):
            if i - dist >= 0:
                pop, pa, _ = seq[i - dist]
                w = writes(pop, pa)
                if w and w in rd:
                    no_fwd += 3 - dist if dist == 1 else 1
                    if dist == 1 and pop == "LD":
                        fwd += 1
                    break
        if tk:
            branch += 2
    n = len(seq)
    base = 4 + n if n else 0
    return {"instructions": n, "ideal_cycles": base, "stalls_without_forwarding": no_fwd, "stalls_with_forwarding": fwd, "branch_penalty_cycles": branch,
            "cycles_without_forwarding": base + no_fwd + branch, "cycles_with_forwarding": base + fwd + branch,
            "assumptions": "Classic 5-stage pipeline (fetch, decode, execute, memory, write-back), registers written in the first half of write-back and read in the second half, branches resolved in execute (2 lost cycles when taken). A teaching model, not a real processor."}


CPU_SAMPLES = {
    "sum": "; add 1 to 5\n LDI R0, 0\n LDI R1, 5\nLOOP: ADD R0, R1\n DEC R1\n JNZ LOOP\n ST [0], R0\n HALT",
    "multiply": "; 6 x 7 by repeated addition\n LDI R0, 0\n LDI R1, 6\n LDI R2, 7\nAGAIN: ADD R0, R2\n DEC R1\n JNZ AGAIN\n ST [1], R0\n HALT",
}


# ================================================================ DC circuit solver
_SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "meg": 1e6, "g": 1e9}


def _si(tok: str, ln: str) -> float:
    t = tok.strip().lower()
    m = re.fullmatch(r"([+-]?\d*\.?\d+(?:e[+-]?\d+)?)(p|n|u|meg|m|k|g)?", t)
    if not m:
        raise CpeError(f"Line '{ln}': '{tok}' is not a value (examples: 100, 4.7k, 1u, 2meg).")
    return float(m.group(1)) * _SI.get(m.group(2), 1.0)


def _parse_net(text: str):
    els, nodes = [], set()
    names = set()
    for ln in (text or "").splitlines():
        ln = ln.split("*")[0].split(";")[0].strip()
        if not ln:
            continue
        p = ln.split()
        if len(p) != 4:
            raise CpeError(f"Line '{ln}': use 'name node1 node2 value', for example 'R1 in out 1k'.")
        nm, a, b, val = p
        k = nm[0].upper()
        if k not in "RVIC":
            raise CpeError(f"Line '{ln}': names start with R (resistor), V (voltage source), I (current source) or C (capacitor).")
        if nm.upper() in names:
            raise CpeError(f"'{nm}' is defined twice.")
        names.add(nm.upper())
        v = _si(val, ln)
        if k in "RC" and v <= 0:
            raise CpeError(f"{nm}: value must be above 0.")
        if a == b:
            raise CpeError(f"{nm}: both ends are the same node.")
        els.append((nm, k, a, b, v))
        nodes.update((a, b))
    if not els:
        raise CpeError("Enter at least one component.")
    if len(els) > 60:
        raise CpeError("At most 60 components.")
    if "0" not in nodes:
        raise CpeError("Use node 0 as ground (the reference).")
    return els, sorted(nodes - {"0"})


def _solve(els, nodes, dt=None, vprev=None):
    idx = {n: i for i, n in enumerate(nodes)}
    vs = [e for e in els if e[1] == "V"]
    size = len(nodes) + len(vs)
    A, z = np.zeros((size, size)), np.zeros(size)

    def stamp(a, b, g):
        for x, y, s in ((a, a, g), (b, b, g), (a, b, -g), (b, a, -g)):
            if x != "0" and y != "0":
                A[idx[x], idx[y]] += s
    for nm, k, a, b, v in els:
        if k == "R":
            stamp(a, b, 1 / v)
        elif k == "C":
            if dt is None:
                stamp(a, b, 1e-12)  # open circuit at DC
            else:
                g = v / dt
                stamp(a, b, g)
                vp = (0 if a == "0" else vprev[idx[a]]) - (0 if b == "0" else vprev[idx[b]])
                if a != "0":
                    z[idx[a]] += g * vp
                if b != "0":
                    z[idx[b]] -= g * vp
        elif k == "I":
            if a != "0":
                z[idx[a]] -= v
            if b != "0":
                z[idx[b]] += v
    for j, (nm, k, a, b, v) in enumerate(vs):
        row = len(nodes) + j
        if a != "0":
            A[row, idx[a]] += 1
            A[idx[a], row] += 1
        if b != "0":
            A[row, idx[b]] -= 1
            A[idx[b], row] -= 1
        z[row] = v
    try:
        x = np.linalg.solve(A, z)
    except np.linalg.LinAlgError:
        raise CpeError("The circuit cannot be solved: a node may be floating (no path to ground), or voltage sources conflict or form a loop.")
    return x, vs


def circuit_dc(net: str) -> dict:
    els, nodes = _parse_net(net)
    x, vs = _solve(els, nodes)
    volt = {"0": 0.0, **{n: float(x[i]) for i, n in enumerate(nodes)}}
    rows = []
    tot_r = 0.0
    for nm, k, a, b, v in els:
        dv = volt[a] - volt[b]
        if k == "R":
            i = dv / v
        elif k == "I":
            i = v
        elif k == "V":
            i = float(x[len(nodes) + [e[0] for e in vs].index(nm)])
        else:
            i = 0.0
        p = dv * i  # power absorbed: positive means the part uses power, negative means it supplies power
        rows.append({"name": nm, "kind": {"R": "resistor", "V": "voltage source", "I": "current source", "C": "capacitor (open at DC)"}[k], "voltage_v": float(f"{dv:.6g}"), "current_a": float(f"{i:.6g}"), "power_absorbed_w": float(f"{p:.6g}")})
        if k == "R":
            tot_r += p
    balance = sum(r["power_absorbed_w"] for r in rows)
    return {"node_voltages": {k: float(f"{v:.6g}") for k, v in volt.items()}, "components": rows, "power_dissipated_w": float(f"{tot_r:.6g}"), "power_balance_w": float(f"{balance:.3g}"),
            "method": "Nodal analysis: for each node the currents leaving add to zero (Kirchhoff's current law), solved as a set of linear equations.",
            "note": "Voltage is first node minus second. Current flows from the first node to the second through a part (for a voltage source it is the current entering its first node, so it is negative when the source supplies power). Negative power means the part supplies power.",
            "lesson": "Every circuit with resistors and sources is a set of linear equations. Check the answer: the powers must add to zero (what sources supply equals what resistors use)."}


def circuit_transient(net: str, t_end: float, steps: int = 200) -> dict:
    els, nodes = _parse_net(net)
    if not isinstance(t_end, (int, float)) or isinstance(t_end, bool) or t_end <= 0:
        raise CpeError("End time must be above 0 seconds.")
    if not isinstance(steps, int) or isinstance(steps, bool) or not 10 <= steps <= 1000:
        raise CpeError("Steps must be 10 to 1000.")
    dt = t_end / steps
    v = np.zeros(len(nodes))
    series = {n: [0.0] for n in nodes}
    times = [0.0]
    for s in range(steps):
        x, _ = _solve(els, nodes, dt, v)
        v = x[:len(nodes)]
        times.append((s + 1) * dt)
        for i, n in enumerate(nodes):
            series[n].append(float(v[i]))
    keep = max(1, steps // 40)
    pick = list(range(0, steps + 1, keep))
    caps = [e for e in els if e[1] == "C"]
    tau = None
    rs = [e[4] for e in els if e[1] == "R"]
    if len(caps) == 1 and rs:
        tau = float(f"{sum(rs) * caps[0][4]:.4g}") if len(rs) == 1 else None
    return {"times_s": [float(f"{times[i]:.6g}") for i in pick], "nodes": {n: [float(f"{series[n][i]:.5g}") for i in pick] for n in nodes}, "final": {n: float(f"{series[n][-1]:.5g}") for n in nodes},
            "time_constant_s": tau, "method": "Backward Euler: each capacitor becomes a resistor with a memory of its last voltage. Small steps keep it accurate; with 200 steps the error on a first-order circuit is a few percent.",
            "lesson": "A capacitor charges toward the supply by 63% in one time constant (R x C)."}


NET_SAMPLES = {"divider": "V1 in 0 12\nR1 in out 10k\nR2 out 0 10k", "bridge": "V1 a 0 10\nR1 a b 100\nR2 a c 200\nR3 b 0 300\nR4 c 0 100\nR5 b c 50",
               "rc": "V1 in 0 5\nR1 in out 1k\nC1 out 0 100u"}


# ================================================================ cache trace simulator
def cache_trace(trace: str, cache_bytes: int, block_bytes: int, ways: int, policy: str = "LRU") -> dict:
    for nm, v in (("Cache size", cache_bytes), ("Block size", block_bytes), ("Ways", ways)):
        if isinstance(v, bool) or not isinstance(v, int) or v < 1 or v & (v - 1):
            raise CpeError(f"{nm} must be a power of two.")
    if policy not in ("LRU", "FIFO"):
        raise CpeError("Policy must be LRU or FIFO.")
    blocks = cache_bytes // block_bytes
    if blocks < ways or blocks < 1:
        raise CpeError("The cache has fewer blocks than ways.")
    sets = blocks // ways
    addrs = []
    for tok in re.split(r"[\s,]+", (trace or "").strip()):
        if not tok:
            continue
        try:
            addrs.append(int(tok, 16) if tok.lower().startswith("0x") else int(tok))
        except ValueError:
            raise CpeError(f"'{tok}' is not an address (use decimal or 0x hex).")
    if not addrs or len(addrs) > 5000:
        raise CpeError("Give 1 to 5000 addresses.")
    sc = [[] for _ in range(sets)]  # each: list of block numbers, most recent last
    fa: list[int] = []  # fully associative LRU of the same total size
    seen, rows = set(), []
    hits = comp = cap = conf = 0
    for a in addrs:
        if a < 0:
            raise CpeError("Addresses cannot be negative.")
        blk = a // block_bytes
        s = blk % sets
        line = sc[s]
        fa_hit = blk in fa
        if fa_hit:
            fa.remove(blk)
        fa.append(blk)
        if len(fa) > blocks:
            fa.pop(0)
        if blk in line:
            hits += 1
            if policy == "LRU":
                line.remove(blk)
                line.append(blk)
            rows.append({"address": a, "block": blk, "set": s, "result": "hit"})
        else:
            if blk not in seen:
                kind = "compulsory"
                comp += 1
            elif fa_hit:
                kind = "conflict"
                conf += 1
            else:
                kind = "capacity"
                cap += 1
            line.append(blk)
            if len(line) > ways:
                line.pop(0)
            rows.append({"address": a, "block": blk, "set": s, "result": "miss", "kind": kind})
        seen.add(blk)
    n = len(addrs)
    return {"accesses": n, "hits": hits, "misses": n - hits, "hit_rate_pct": round(100 * hits / n, 1), "sets": sets, "ways": ways, "compulsory": comp, "capacity": cap, "conflict": conf,
            "first_rows": rows[:60], "method": f"{policy} replacement. A miss is conflict if a fully associative cache of the same size would have hit, capacity if even that would miss, compulsory if the block was never seen.",
            "lesson": "Compulsory misses cannot be avoided, capacity misses need a bigger cache, and conflict misses need more ways or a better mapping."}


CACHE_SAMPLE = "0 64 128 192 0 64 128 192 256 0 4 68"

SLIPS = [
    "Simulators here: the logic simulator treats gates as instant and flip-flops as ideal (no setup time, hold time or glitches), and it refuses latches built from cross-coupled gates because those are a feedback loop. Real circuits have delay.",
    "Simulators here: the CPU is an invented 8-bit machine, not a real instruction set, and the pipeline numbers are a simple counting model. Use it to understand hazards, not to predict a real chip.",
    "Simulators here: the transient solver uses backward Euler with a fixed step, so fast circuits need more steps. It handles resistors, capacitors and sources only (no inductors, diodes or transistors).",
]
NOT_BUILT = ["Inductors, diodes, transistors and AC analysis (SPICE-style), and Verilog or VHDL.",
             "A real instruction set (RISC-V, ARM) and cycle-accurate timing.",
             "Waveform viewers beyond a text trace."]


def reference() -> dict:
    return {"logic_samples": {k: {"netlist": v[0], "stimulus": v[1]} for k, v in LOGIC_SAMPLES.items()}, "cpu_samples": CPU_SAMPLES, "net_samples": NET_SAMPLES, "cache_sample": CACHE_SAMPLE, "slips": SLIPS, "not_built": NOT_BUILT,
            "instructions": "LDI Rd,imm | MOV Rd,Rs | LD Rd,[addr] | ST [addr],Rs | ADD SUB AND OR XOR CMP Rd,Rs | INC DEC Rd | JMP JZ JNZ JC label | HALT"}
