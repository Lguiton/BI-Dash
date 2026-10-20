"""Real checks for code: compile and run C, simulate Verilog. Used by the Computer Engineering lab, the Autopilot and the Work Room.

Safety: code runs in a throw-away folder with a time limit, a memory limit, a trimmed environment and capped output. Verilog is scanned first and
anything that could reach outside the simulation ($system, file access, includes) is refused. The Work Room and Autopilot only compile C
automatically; running C happens only when the owner presses the button in the lab. Run only code you have looked at."""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile

TIMEOUT = 8
OUT_CAP = 12_000
MAX_SRC = 60_000


class CodeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


_WIN_DIRS = [r"C:\iverilog\bin", r"C:\Program Files\iverilog\bin", r"C:\msys64\ucrt64\bin", r"C:\msys64\mingw64\bin", r"C:\MinGW\bin"]
INSTALL = {"gcc": "Install a C compiler: in WSL run  sudo apt install build-essential ; on Windows install MSYS2 or MinGW-w64 and make sure gcc is on PATH.",
           "iverilog": "Install the free Verilog simulator: in WSL run  sudo apt install iverilog ; on Windows get it from bleyer.org/icarus and tick 'add to PATH'."}


def _tool(name: str) -> str | None:
    p = shutil.which(name)
    if p:
        return p
    if os.name == "nt":
        for d in _WIN_DIRS:
            for ext in (".exe", ""):
                f = os.path.join(d, name + ext)
                if os.path.isfile(f):
                    return f
    return None


def available() -> dict:
    return {"gcc": bool(_tool("gcc")), "iverilog": bool(_tool("iverilog") and _tool("vvp"))}


def _limits(cap_memory: bool = True):  # pragma: no cover - runs in the child process on Linux only
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT, TIMEOUT))
        if cap_memory:                    # the address-space cap breaks the sanitizers, which reserve a huge virtual range
            resource.setrlimit(resource.RLIMIT_AS, (1 << 30, 1 << 30))
        resource.setrlimit(resource.RLIMIT_FSIZE, (5 << 20, 5 << 20))
        resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    except Exception:  # noqa: BLE001
        pass


def _sh(cmd: list[str], cwd: str, stdin: str = "", timeout: int = TIMEOUT, cap_memory: bool = True) -> dict:
    env = {"PATH": os.environ.get("PATH", ""), "LANG": "C", "HOME": cwd, "TMPDIR": cwd}
    if not cap_memory:
        env["ASAN_OPTIONS"] = "max_allocation_size_mb=256:detect_leaks=0"
    if os.name == "nt":
        env["SystemRoot"] = os.environ.get("SystemRoot", "")
    try:
        p = subprocess.run(cmd, cwd=cwd, input=stdin.encode(), capture_output=True, timeout=timeout, env=env,
                           preexec_fn=(lambda: _limits(cap_memory)) if os.name == "posix" else None,
                           creationflags=0x08000000 if os.name == "nt" else 0)
        return {"code": p.returncode, "out": p.stdout.decode("utf-8", "replace")[:OUT_CAP], "err": p.stderr.decode("utf-8", "replace")[:OUT_CAP], "timeout": False}
    except subprocess.TimeoutExpired as e:
        return {"code": None, "out": (e.stdout or b"").decode("utf-8", "replace")[:OUT_CAP], "err": (e.stderr or b"").decode("utf-8", "replace")[:OUT_CAP], "timeout": True}


def _issues(text: str) -> list[dict]:
    out = []
    for ln in text.splitlines():
        m = re.search(r":(\d+)(?::\d+)?:\s*(warning|error|fatal error|note):\s*(.+)$", ln)
        if m and m.group(2) != "note":
            out.append({"line": int(m.group(1)), "level": "error" if "error" in m.group(2) else "warning", "text": m.group(3)[:200]})
    return out[:30]


def _plain_c(msg: str) -> str:
    table = [("implicit declaration", "A function is used before it is declared (missing #include or prototype)."),
             ("unused variable", "A variable is declared but never used."),
             ("format", "A printf/scanf format does not match its argument type, which is a classic source of wrong output or crashes."),
             ("may be used uninitialized", "A variable may be read before it has a value."),
             ("comparison of integer expressions of different signedness", "A signed and an unsigned number are compared, which can give surprising results for negatives."),
             ("array subscript", "An array index may run past the end of the array."),
             ("control reaches end of non-void", "A function that should return a value can finish without returning one."),
             ("expected", "A syntax error: something is missing, often a semicolon, bracket or brace.")]
    low = msg.lower()
    return next((v for k, v in table if k in low), "")


def c_check(source: str, stdin: str = "", run: bool = False, std: str = "c11") -> dict:
    """Compile with strict warnings; with run=True also run it (sanitizers on when available) and return the output."""
    source = source or ""
    if not source.strip():
        raise CodeError("Paste the C source first.")
    if len(source) > MAX_SRC:
        raise CodeError("That source is over 60,000 characters. Paste one file at a time.")
    gcc = _tool("gcc")
    if not gcc:
        raise CodeError("No C compiler found on this computer. " + INSTALL["gcc"], 501)
    with tempfile.TemporaryDirectory(prefix="bi_c_") as d:
        src = os.path.join(d, "main.c")
        open(src, "w", encoding="utf-8").write(source)
        base = [gcc, f"-std={std}", "-Wall", "-Wextra", "-Wpedantic", "-Wshadow", "-Wformat=2", "-Wconversion", "-O1", "-g"]
        syntax = _sh(base + ["-fsyntax-only", src], d)
        issues = _issues(syntax["err"])
        for i in issues:
            i["plain"] = _plain_c(i["text"])
        errors = [i for i in issues if i["level"] == "error"]
        res: dict = {"compiled": not errors and syntax["code"] == 0, "issues": issues, "errors": len(errors), "warnings": len(issues) - len(errors), "ran": False, "sanitizers": False}
        if not res["compiled"] and not errors:
            res["raw"] = syntax["err"][:1500]
        if res["compiled"] and run:
            exe = os.path.join(d, "a.out" if os.name != "nt" else "a.exe")
            built = _sh(base + ["-fsanitize=address,undefined", "-fno-omit-frame-pointer", src, "-o", exe, "-lm"], d)
            res["sanitizers"] = built["code"] == 0
            if built["code"] != 0:
                built = _sh(base + [src, "-o", exe, "-lm"], d)
            if built["code"] != 0:
                res["compiled"], res["raw"] = False, built["err"][:1500]
            else:
                r = _sh([exe], d, stdin or "", cap_memory=not res["sanitizers"])
                san = re.search(r"(AddressSanitizer|runtime error|LeakSanitizer)[^\n]*", r["err"])
                res.update(ran=True, exit_code=r["code"], stdout=r["out"], stderr=r["err"][:3000], timed_out=r["timeout"],
                           sanitizer_finding=san.group(0)[:300] if san else None)
        res["plain"] = _c_plain(res, run)
        return res


def _c_plain(res: dict, run: bool) -> str:
    if not res["compiled"]:
        return f"It does not compile: {res['errors']} error(s). Fix the first one and recompile; later errors are often caused by it."
    bits = [f"It compiles with {res['warnings']} warning(s)."]
    if res["warnings"]:
        bits.append("Treat warnings as bugs until you can explain each one.")
    if res.get("ran"):
        if res.get("timed_out"):
            bits.append("It was stopped after the time limit: look for an endless loop or a wait for input that never comes.")
        elif res.get("sanitizer_finding"):
            bits.append(f"The runtime checker found a real fault: {res['sanitizer_finding']}")
        elif res.get("exit_code"):
            bits.append(f"It ran and exited with code {res['exit_code']} (non-zero usually means failure).")
        else:
            bits.append("It ran cleanly" + (" with memory and undefined-behavior checks on." if res.get("sanitizers") else "."))
    elif not run:
        bits.append("It was checked but not run. Use the lab tool to run it.")
    return " ".join(bits)


_BAD_V = re.compile(r"\$(system|fopen|fclose|fwrite|fdisplay|fscanf|fgets|fread|readmem[bh]|writemem[bh]|dumpfile|dumpvars|value\$plusargs|test\$plusargs)\b|`include\b|\bimport\s+\"DPI", re.I)
_MOD = re.compile(r"^\s*module\s+(\w+)\s*(#\s*\(.*?\))?\s*(\((.*?)\))?\s*;", re.S | re.M)


def _modules(src: str) -> list[dict]:
    out = []
    for m in _MOD.finditer(src):
        out.append({"name": m.group(1), "ports": bool((m.group(4) or "").strip())})
    return out


def verilog_sim(source: str, top: str = "", sim: bool = True) -> dict:
    """Compile with Icarus Verilog and run the testbench. A testbench is a module with no ports that drives the design and calls $finish."""
    source = source or ""
    if not source.strip():
        raise CodeError("Paste the Verilog source (the design and, ideally, its testbench) first.")
    if len(source) > MAX_SRC:
        raise CodeError("That source is over 60,000 characters. Paste fewer modules.")
    bad = _BAD_V.search(source)
    if bad:
        raise CodeError(f"This simulator refuses '{bad.group(0)}': it could reach outside the simulation (files, shell, includes). Remove it, or use a plain testbench with $display.")
    iv, vvp = _tool("iverilog"), _tool("vvp")
    if not iv or not vvp:
        raise CodeError("The Verilog simulator (Icarus Verilog) is not installed. " + INSTALL["iverilog"], 501)
    mods = _modules(source)
    if not mods:
        raise CodeError("No 'module ... ;' found. A Verilog file defines at least one module.")
    benches = [m for m in mods if not m["ports"]]
    tb = next((m["name"] for m in benches if re.search(r"tb|test|bench", m["name"], re.I)), benches[0]["name"] if benches else "")
    top = (top or "").strip() or tb or mods[-1]["name"]
    with tempfile.TemporaryDirectory(prefix="bi_v_") as d:
        f = os.path.join(d, "design.sv")
        open(f, "w", encoding="utf-8").write(source)
        out = os.path.join(d, "sim.vvp")
        comp = _sh([iv, "-g2012", "-Wall", "-s", top, "-o", out, f], d)
        issues = _issues(comp["err"]) or [{"line": 0, "level": "error" if comp["code"] else "warning", "text": ln[:200]} for ln in comp["err"].splitlines() if ln.strip()][:20]
        errors = [i for i in issues if i["level"] == "error"]
        res: dict = {"modules": [m["name"] for m in mods], "top": top, "has_testbench": bool(tb), "compiled": comp["code"] == 0, "issues": issues, "ran": False}
        if comp["code"] != 0:
            res["plain"] = f"It does not compile ({len(errors) or 'some'} error(s)). Fix the first error; later ones are often caused by it."
            return res
        if not sim:
            res["plain"] = "It compiles. It was not simulated."
            return res
        if not tb and top == mods[-1]["name"]:
            res["plain"] = ("It compiles, but there is no testbench (a module with no ports that applies inputs and checks outputs), so nothing was simulated. "
                            "Compiling only proves the syntax is valid, not that the logic is right.")
            return res
        r = _sh([vvp, out], d)
        text = r["out"]
        lines = text.splitlines()
        fails = [ln for ln in lines if re.search(r"\b(fail|error|mismatch|wrong|unexpected)\b", ln, re.I)]
        passes = [ln for ln in lines if re.search(r"\b(pass|ok|success|all tests)\b", ln, re.I)]
        xs = [ln for ln in lines if re.search(r"\bx\b|=x|'bx|z\b", ln, re.I) and re.search(r"[0-9a-z_]=[xz]|'b[xz]|\b[01]*[xz][01xz]*\b", ln, re.I)]
        res.update(ran=True, output=text[:6000], timed_out=r["timeout"], finished="$finish" in r["err"] or r["code"] == 0 and not r["timeout"],
                   fail_lines=fails[:10], pass_lines=passes[:5], unknown_value_lines=xs[:5], lines=len(lines))
        if r["timeout"]:
            res["plain"] = "The simulation hit the time limit. A clock that never stops is the usual cause: end the testbench with $finish after the last check."
        elif fails:
            res["plain"] = f"The testbench reported {len(fails)} failing line(s). Compare the first one with the expected value; the first failure usually explains the rest."
        elif not lines:
            res["plain"] = "It simulated but printed nothing, so it proves nothing. Add $display checks that print PASS or FAIL for each expected output."
        else:
            res["plain"] = "It simulated with no failure lines." + (" Some values show x (unknown): an input or register was never set, often a missing reset." if xs else "") + \
                           " This proves only the cases the testbench checks; add edge cases (reset, overflow, back-to-back inputs)."
        return res


FENCE = re.compile(r"```\s*([A-Za-z+#]*)\s*\n(.*?)```", re.S)


def verify_blocks(text: str, limit: int = 3) -> list[dict]:
    """Check code blocks inside an agent's answer. C is only compiled (never run); Verilog is simulated when it has a testbench."""
    out = []
    for lang, body in FENCE.findall(text or ""):
        lg = lang.lower()
        try:
            if lg in ("c",) and "main" in body:
                r = c_check(body, run=False)
                out.append({"lang": "C", "status": "ok" if r["compiled"] and not r["warnings"] else "warn" if r["compiled"] else "fail", "plain": r["plain"], "issues": r["issues"][:5]})
            elif lg in ("verilog", "systemverilog", "sv", "v") and "module" in body:
                r = verilog_sim(body)
                bad = (not r["compiled"]) or bool(r.get("fail_lines")) or r.get("timed_out")
                out.append({"lang": "Verilog", "status": "fail" if bad else "ok" if r.get("ran") else "warn", "plain": r["plain"], "output": (r.get("output") or "")[:600]})
        except CodeError as e:
            out.append({"lang": lang or "code", "status": "skipped", "plain": e.message})
        if len(out) >= limit:
            break
    return out


def which_python() -> str:
    return sys.executable
