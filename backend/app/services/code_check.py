"""Code Workbench checks: look at pasted code and say what is wrong, WITHOUT running it.

Python is parsed with the standard `ast` module (never executed). JavaScript is syntax-checked with `node --check` when Node is installed (it parses, it does not
run), otherwise by bracket matching. HTML is walked with the standard parser. JSON is parsed. SQL is parsed by DuckDB's own parser (`json_serialize_sql`), which
reads the statement but does not run it.

Each finding has a line, a severity (error = it will not work, warning = probably a bug or a risk, info = style) and a plain-language reason.
Honest limits: this is a quick reviewer, not a full linter. It finds common mistakes, not every one, and a clean result does not mean the code is correct.
Fixes are suggestions you read and paste yourself; nothing here changes a file."""
from __future__ import annotations

import ast
import builtins
import difflib
import html.parser
import json
import os
import re
import shutil
import subprocess
import tempfile

LANGS = ("python", "javascript", "html", "json", "sql")
MAX_CHARS = 60_000
MAX_FINDINGS = 60


class CodeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _f(line, sev, code, msg, hint="", col=None):
    return {"line": line, "col": col, "severity": sev, "code": code, "message": msg, "hint": hint}


def detect(code: str) -> str:
    s = code.lstrip()
    if s.startswith(("<!doctype", "<!DOCTYPE", "<html", "<div", "<body", "<head", "<p", "<ul", "<table", "<form", "<section", "<script", "<style")):
        return "html"
    if s[:1] in "{[":
        try:
            json.loads(code)
            return "json"
        except ValueError:
            pass
    if re.match(r"(?is)\s*(select|insert|update|delete|create|drop|with|alter|explain)\b", s):
        return "sql"
    if re.search(r"(?m)^\s*(def |class |import |from \w+ import |print\()", code):
        return "python"
    if re.search(r"\b(const|let|function|=>|console\.log|document\.)", code):
        return "javascript"
    return "python"


# ---------------------------------------------------------------- python


def _names_bound(tree: ast.AST) -> set[str]:
    b: set[str] = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__spec__", "__builtins__"}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            b.add(n.name)
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                b.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.arg):
            b.add(n.arg)
        elif isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)):
            b.add(n.id)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            b.add(n.name)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            b.update(n.names)
        elif isinstance(n, ast.MatchAs) and n.name:
            b.add(n.name)
    return b


def check_python(code: str) -> list[dict]:
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return [_f(e.lineno or 1, "error", "syntax", f"Syntax error: {e.msg}.", "Check the line above too: a missing bracket or colon is often reported on the next line.", e.offset)]
    out: list[dict] = []
    bound = _names_bound(tree)
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)} | {n.value.id for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name)}
    allnames = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in bound:
            out.append(_f(n.lineno, "error", "undefined-name", f"'{n.id}' is used but never defined or imported.", "Typo, or a missing import/assignment?", n.col_offset))
    dunder_all = {e.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in n.targets) and isinstance(n.value, (ast.List, ast.Tuple)) for e in n.value.elts if isinstance(e, ast.Constant)}
    for n in ast.walk(tree):
        if isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                nm = (a.asname or a.name).split(".")[0]
                if nm != "*" and nm not in used and nm not in dunder_all:
                    out.append(_f(n.lineno, "warning", "unused-import", f"'{nm}' is imported but never used.", "Remove it, or use it."))
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in n.args.defaults + [x for x in n.args.kw_defaults if x]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    out.append(_f(d.lineno, "warning", "mutable-default", "A list/dict/set as a default argument is shared between calls.", "Use None as the default and create the list inside the function."))
            assigned: dict[str, int] = {}
            loaded = {x.id for x in ast.walk(n) if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Load)}
            for x in ast.walk(n):
                if isinstance(x, ast.Name) and isinstance(x.ctx, ast.Store) and x.id != "_" and not x.id.startswith("_"):
                    assigned.setdefault(x.id, x.lineno)
            gl = {nm for g in ast.walk(n) if isinstance(g, (ast.Global, ast.Nonlocal)) for nm in g.names}
            for nm, ln in assigned.items():
                if nm not in loaded and nm not in gl:
                    out.append(_f(ln, "info", "unused-variable", f"'{nm}' is assigned in '{n.name}' but never used.", "Delete it, or use it."))
        if isinstance(n, ast.ExceptHandler) and n.type is None:
            out.append(_f(n.lineno, "warning", "bare-except", "A bare 'except:' also catches Ctrl-C and real bugs.", "Use 'except Exception:' or name the error you expect."))
        if isinstance(n, ast.Compare):
            for op, c in zip(n.ops, n.comparators):
                if isinstance(op, (ast.Eq, ast.NotEq)) and isinstance(c, ast.Constant) and c.value is None:
                    out.append(_f(n.lineno, "warning", "compare-none", "Compare to None with 'is' / 'is not', not '==' / '!='.", "Write: x is None"))
                if isinstance(op, (ast.Is, ast.IsNot)) and isinstance(c, ast.Constant) and isinstance(c.value, (str, int, float)) and not isinstance(c.value, bool):
                    out.append(_f(n.lineno, "warning", "is-literal", "'is' compares identity, not value; with a number or string it gives unreliable results.", "Use ==."))
        if isinstance(n, ast.Assert) and isinstance(n.test, ast.Tuple) and n.test.elts:
            out.append(_f(n.lineno, "warning", "assert-tuple", "assert on a tuple is always true.", "Remove the parentheses around the condition and message."))
        if isinstance(n, ast.Call):
            fn = ast.unparse(n.func) if hasattr(ast, "unparse") else ""
            if fn in ("eval", "exec"):
                out.append(_f(n.lineno, "warning", "eval-exec", f"{fn}() runs text as code; with any outside input that is a security hole.", "Use ast.literal_eval for data, or a lookup table of allowed functions."))
            if fn in ("os.system", "os.popen"):
                out.append(_f(n.lineno, "warning", "shell-command", f"{fn}() runs a shell command from a string.", "Use subprocess.run([...]) with a list and no shell."))
            if fn.startswith("subprocess.") and any(k.arg == "shell" and isinstance(k.value, ast.Constant) and k.value.value is True for k in n.keywords):
                out.append(_f(n.lineno, "warning", "shell-true", "shell=True lets a crafted input run extra commands.", "Pass a list of arguments and leave shell off."))
            if fn in ("pickle.loads", "pickle.load", "yaml.load"):
                out.append(_f(n.lineno, "warning", "unsafe-load", f"{fn} can run code hidden in the data.", "Only load data you made yourself; prefer json (or yaml.safe_load)."))
            if fn.endswith(".execute") and n.args:
                a = n.args[0]
                if isinstance(a, ast.JoinedStr) or (isinstance(a, ast.BinOp) and isinstance(a.op, (ast.Add, ast.Mod))) or (isinstance(a, ast.Call) and isinstance(a.func, ast.Attribute) and a.func.attr == "format"):
                    out.append(_f(n.lineno, "warning", "sql-injection", "A SQL string is built by joining text. Anyone who controls that text can change the query.", "Use placeholders: execute('... WHERE id = ?', [value])."))
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant) and isinstance(n.value.value, str) and len(n.value.value) >= 6:
            for t in n.targets:
                if isinstance(t, ast.Name) and re.search(r"(password|passwd|secret|api_?key|token)", t.id, re.I):
                    out.append(_f(n.lineno, "warning", "hardcoded-secret", f"'{t.id}' looks like a secret typed into the code.", "Read it from an environment variable so it never lands in a file or a repo."))
    seen, dedup = set(), []
    for o in out:
        k = (o["line"], o["code"], o["message"])
        if k not in seen:
            seen.add(k)
            dedup.append(o)
    return dedup


# ---------------------------------------------------------------- javascript


def _brackets(code: str) -> list[dict]:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[tuple[str, int]] = []
    i, line, n = 0, 1, len(code)
    while i < n:
        c = code[i]
        if c == "\n":
            line += 1
        elif c in "\"'`":
            q, start = c, line
            i += 1
            while i < n and code[i] != q:
                if code[i] == "\\":
                    i += 1
                if i < n and code[i] == "\n":
                    line += 1
                    if q != "`":
                        return [_f(start, "error", "syntax", "A string is opened but not closed on the same line.", "Close the quote, or use a template string (backticks) for several lines.")]
                i += 1
        elif c == "/" and code[i:i + 2] == "//":
            while i < n and code[i] != "\n":
                i += 1
            continue
        elif c == "/" and code[i:i + 2] == "/*":
            j = code.find("*/", i + 2)
            line += code[i:j if j > 0 else n].count("\n")
            i = (j + 2) if j > 0 else n
            continue
        elif c in "([{":
            stack.append((c, line))
        elif c in pairs:
            if not stack or stack[-1][0] != pairs[c]:
                return [_f(line, "error", "syntax", f"Unexpected '{c}'.", "There is a missing or extra bracket before this line.")]
            stack.pop()
        i += 1
    if stack:
        return [_f(stack[-1][1], "error", "syntax", f"'{stack[-1][0]}' is never closed.", "Add the matching closing bracket.")]
    return []


def check_javascript(code: str) -> list[dict]:
    out: list[dict] = []
    node = shutil.which("node")
    parsed = False
    if node:
        ext = ".mjs" if re.search(r"(?m)^\s*(import|export)\s", code) else ".js"
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "snippet" + ext)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(code)
            try:
                r = subprocess.run([node, "--check", p], capture_output=True, text=True, timeout=6, cwd=d, env={"PATH": os.environ.get("PATH", "")})          # parse only, nothing is run
                parsed = True
                if r.returncode != 0:
                    err = r.stderr.splitlines()
                    m = re.search(r":(\d+)\s*$", err[0]) if err else None
                    msg = next((x for x in err if re.match(r"\w*Error", x)), "Syntax error")
                    out.append(_f(int(m.group(1)) if m else 1, "error", "syntax", msg.strip(), "Look at this line and the one above it."))
            except (subprocess.TimeoutExpired, OSError):
                parsed = False
    if not parsed:
        out += _brackets(code)
    if any(o["severity"] == "error" for o in out):
        return out
    lines = code.splitlines()
    for i, ln in enumerate(lines, 1):
        s = ln.split("//")[0]
        if re.search(r"\beval\s*\(|new\s+Function\s*\(", s):
            out.append(_f(i, "warning", "eval", "eval()/new Function() runs text as code.", "Avoid it; call a normal function instead."))
        if re.search(r"\.(innerHTML|outerHTML)\s*[+]?=", s) or "document.write(" in s:
            out.append(_f(i, "warning", "xss", "Writing HTML from a string can run injected scripts if any of it comes from a user.", "Use textContent for text, or build elements with createElement."))
        if re.search(r"[^=!<>]==[^=]|!=[^=]", s) and not re.search(r"['\"`].*(==|!=).*['\"`]", s):
            out.append(_f(i, "info", "loose-equality", "'==' / '!=' convert types before comparing.", "Use === / !== unless you want that."))
        if re.match(r"\s*var\s", s):
            out.append(_f(i, "info", "var", "'var' is function-scoped and easy to misuse.", "Use const (or let if it changes)."))
        if re.search(r"(password|secret|api_?key|token)\s*[:=]\s*['\"][^'\"]{6,}['\"]", s, re.I):
            out.append(_f(i, "warning", "hardcoded-secret", "This looks like a secret typed into the code.", "Keep secrets on the server in an environment variable, never in browser code."))
    return out


# ---------------------------------------------------------------- html


VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
OPTIONAL_END = {"p", "li", "td", "th", "tr", "dt", "dd", "option", "thead", "tbody", "tfoot"}


class _Html(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[tuple[str, int]] = []
        self.out: list[dict] = []
        self.ids: dict[str, int] = {}
        self.seen = {"doctype": False, "html": False, "title": False, "lang": False, "h1": 0}

    def handle_decl(self, decl):
        if decl.lower().startswith("doctype"):
            self.seen["doctype"] = True

    def handle_starttag(self, tag, attrs):
        ln = self.getpos()[0]
        a = dict(attrs)
        if tag == "html":
            self.seen["html"] = True
            self.seen["lang"] = "lang" in a
        if tag == "title":
            self.seen["title"] = True
        if tag == "h1":
            self.seen["h1"] += 1
        if tag == "img" and "alt" not in a:
            self.out.append(_f(ln, "warning", "img-alt", "An image has no alt text, so screen readers and broken-image views show nothing.", 'Add alt="what the picture shows" (alt="" if purely decorative).'))
        if tag == "a" and a.get("target") == "_blank" and "noopener" not in (a.get("rel") or ""):
            self.out.append(_f(ln, "warning", "blank-noopener", 'A link that opens a new tab without rel="noopener" lets that page control this one.', 'Add rel="noopener noreferrer".'))
        for k, v in attrs:
            if k.startswith("on") and v:
                self.out.append(_f(ln, "info", "inline-handler", f"Inline '{k}' handlers mix code into the page and get blocked by strict security policies.", "Attach the event in a script with addEventListener."))
            if k in ("href", "src") and (v or "").strip().lower().startswith("javascript:"):
                self.out.append(_f(ln, "warning", "js-url", "A javascript: link runs code from the address.", "Use a button with an event listener."))
        if "id" in a:
            if a["id"] in self.ids:
                self.out.append(_f(ln, "error", "dup-id", f"id=\"{a['id']}\" is used twice (first on line {self.ids[a['id']]}). An id must be unique.", "Rename one, or use a class."))
            self.ids[a["id"]] = ln
        if tag in VOID:
            return
        self.stack.append((tag, ln))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        ln = self.getpos()[0]
        if tag in VOID:
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                for t, l in self.stack[i + 1:]:
                    if t not in OPTIONAL_END:
                        self.out.append(_f(l, "error", "unclosed-tag", f"<{t}> opened here is never closed before </{tag}> on line {ln}.", f"Add </{t}>."))
                del self.stack[i:]
                return
        self.out.append(_f(ln, "error", "stray-end-tag", f"</{tag}> closes something that was never opened.", "Delete it, or add the opening tag."))


def check_html(code: str) -> list[dict]:
    p = _Html()
    p.feed(code)
    p.close()
    out = p.out
    for t, l in p.stack:
        if t not in OPTIONAL_END and t not in ("html", "body", "head"):
            out.append(_f(l, "error", "unclosed-tag", f"<{t}> is never closed.", f"Add </{t}>."))
    if "<html" in code.lower():
        if not p.seen["doctype"]:
            out.append(_f(1, "info", "doctype", "No <!doctype html> at the top, so browsers use quirks mode.", "Add <!doctype html> as the first line."))
        if not p.seen["lang"]:
            out.append(_f(1, "info", "html-lang", '<html> has no lang attribute (screen readers pick the voice from it).', '<html lang="en">'))
        if not p.seen["title"]:
            out.append(_f(1, "info", "title", "The page has no <title>.", "Add <title>…</title> in <head>."))
    if p.seen["h1"] > 1:
        out.append(_f(1, "info", "multiple-h1", f"{p.seen['h1']} <h1> headings; most pages should have one.", "Use <h2> for sections."))
    return out


# ---------------------------------------------------------------- json, sql


def check_json(code: str) -> list[dict]:
    try:
        json.loads(code)
        return []
    except ValueError as e:
        line = getattr(e, "lineno", 1)
        hint = "JSON needs double quotes, no trailing commas and no comments."
        return [_f(line, "error", "syntax", f"Not valid JSON: {getattr(e, 'msg', str(e))}.", hint, getattr(e, "colno", None))]


def check_sql(code: str) -> list[dict]:
    import duckdb
    out: list[dict] = []
    stmts = [s.strip() for s in re.split(r";\s*(?:\n|$)", code) if s.strip()]
    if not stmts:
        return [_f(1, "error", "empty", "There is no SQL here.")]
    con = duckdb.connect(":memory:")
    try:
        for s in stmts:
            try:
                r = json.loads(con.execute("SELECT json_serialize_sql(?)", [s]).fetchone()[0])
            except Exception as e:  # noqa: BLE001
                out.append(_f(_line_of(code, s), "error", "syntax", f"Can't parse: {str(e)[:120]}", "Check keywords, commas and quotes."))
                continue
            if r.get("error"):
                pos = r.get("position")
                ln = _line_of(code, s) + (s[:int(pos)].count("\n") if str(pos).isdigit() else 0)
                out.append(_f(ln, "error", "syntax", str(r.get("error_message", "Syntax error")).splitlines()[0][:160], "Check keywords, commas, quotes and brackets near here."))
    finally:
        con.close()
    for i, ln in enumerate(code.splitlines(), 1):
        low = re.sub(r"'[^']*'", "''", ln.lower())
        if re.match(r"\s*(update|delete)\b", low) and "where" not in " ".join(code.lower().split(";")[0:1]) and not _has_where(code, ln):
            out.append(_f(i, "warning", "no-where", "UPDATE/DELETE with no WHERE changes or removes EVERY row.", "Add a WHERE clause (and try it as a SELECT first)."))
        if re.search(r"\bselect\s+\*", low):
            out.append(_f(i, "info", "select-star", "SELECT * returns every column, including ones that may change or be sensitive.", "Name the columns you need."))
        if re.match(r"\s*(drop|truncate)\b", low):
            out.append(_f(i, "warning", "destructive", "DROP/TRUNCATE permanently removes data.", "Back up first, and double-check the table name."))
        if re.search(r"(\|\|\s*['\"]?\s*\w+\s*\|\||\+\s*@|%s|\{[a-z_]*\}|\$\{)", ln, re.I):
            out.append(_f(i, "warning", "string-built", "This looks like values pasted into the SQL as text, which invites SQL injection.", "Use parameters (? or $1) and pass the values separately."))
    if len(stmts) > 1:
        out.append(_f(1, "info", "multiple", f"{len(stmts)} statements. Most drivers run one at a time."))
    return out


def _line_of(code: str, stmt: str) -> int:
    i = code.find(stmt[:30])
    return code[:i].count("\n") + 1 if i >= 0 else 1


def _has_where(code: str, line: str) -> bool:
    i = code.find(line)
    chunk = code[i:].split(";")[0].lower() if i >= 0 else line.lower()
    return " where " in f" {chunk} " or "\nwhere" in chunk


# ---------------------------------------------------------------- entry points


def check(code: str, language: str = "auto") -> dict:
    code = code or ""
    if not code.strip():
        raise CodeError("Paste some code first.")
    if len(code) > MAX_CHARS:
        raise CodeError(f"That's over {MAX_CHARS:,} characters. Paste one file or function at a time.")
    lang = detect(code) if language in ("auto", "", None) else language
    if lang not in LANGS:
        raise CodeError("language must be one of: " + ", ".join(LANGS) + ".")
    found = {"python": check_python, "javascript": check_javascript, "html": check_html, "json": check_json, "sql": check_sql}[lang](code)
    order = {"error": 0, "warning": 1, "info": 2}
    found.sort(key=lambda f: (order[f["severity"]], f["line"] or 0))
    n = {s: sum(1 for f in found if f["severity"] == s) for s in order}
    node_note = "JavaScript was syntax-checked by bracket matching only (Node isn't installed)." if lang == "javascript" and not shutil.which("node") else ""
    return {"language": lang, "findings": found[:MAX_FINDINGS], "counts": n, "clean": n["error"] == 0 and n["warning"] == 0, "lines": code.count("\n") + 1,
            "says": ("No errors or warnings found." if not (n["error"] or n["warning"]) else f"{n['error']} error(s), {n['warning']} warning(s), {n['info']} note(s)."), "note": node_note,
            "caution": "A clean result means no common mistakes were found, not that the code is correct. Run it with test data."}


def safe_fixes(code: str, language: str = "auto") -> dict:
    """Fixes that cannot change what the code means. Python: == None, bare except, trailing spaces. Everything else: trailing spaces and blank-line tidying."""
    lang = detect(code) if language in ("auto", "", None) else language
    fixed = "\n".join(ln.rstrip() for ln in code.splitlines()) + ("\n" if code.endswith("\n") else "")
    changes = []
    if fixed != code:
        changes.append("Removed trailing spaces.")
    if lang == "python":
        new = re.sub(r"(\w|\)|\])\s*==\s*None\b", r"\1 is None", fixed)
        new = re.sub(r"(\w|\)|\])\s*!=\s*None\b", r"\1 is not None", new)
        if new != fixed:
            changes.append("Changed '== None' / '!= None' to 'is None' / 'is not None'.")
        fixed = new
        new = re.sub(r"(?m)^(\s*)except\s*:", r"\1except Exception:", fixed)
        if new != fixed:
            changes.append("Changed bare 'except:' to 'except Exception:'.")
        fixed = new
    return _review(code, fixed, lang, changes or ["Nothing safe to change automatically."])


def _review(before: str, after: str, lang: str, changes: list[str]) -> dict:
    diff = []
    for ln in difflib.unified_diff(before.splitlines(), after.splitlines(), "before", "after", lineterm="", n=2):
        if ln.startswith(("---", "+++")):
            continue
        diff.append({"kind": "hunk" if ln.startswith("@@") else "add" if ln.startswith("+") else "del" if ln.startswith("-") else "same", "text": ln[1:] if ln[:1] in "+- " else ln})
    b, a = check(before, lang), check(after, lang) if after.strip() else {"findings": [], "counts": {"error": 0, "warning": 0, "info": 0}}
    return {"language": lang, "fixed": after, "changed": before != after, "changes": changes, "diff": diff, "before": b["counts"], "after": a["counts"], "after_findings": a["findings"][:20],
            "says": (f"Errors {b['counts']['error']} to {a['counts']['error']}, warnings {b['counts']['warning']} to {a['counts']['warning']}." if before != after else "No change."), "applied": False,
            "note": "Nothing was changed on disk. Read the differences, then paste the fixed code yourself if you agree."}


def extract_code(reply: str) -> tuple[str, str]:
    """Pull the first fenced block out of an AI reply. Returns (code, the rest as the explanation)."""
    m = re.search(r"```[a-zA-Z0-9+#]*\n(.*?)```", reply, re.S)
    if not m:
        raise CodeError("The assistant didn't return a code block. Try again, or use the safe fixes.")
    return m.group(1).rstrip("\n") + "\n", (reply[:m.start()] + reply[m.end():]).strip()


def notebook(code: str, language: str = "auto", title: str = "Code from the Workbench") -> dict:
    """A ready-to-open Jupyter notebook (nbformat 4, built by hand) holding the code, with a first cell that says what it is."""
    code = code or ""
    if not code.strip():
        raise CodeError("Paste some code first.")
    lang = detect(code) if language in ("auto", "", None) else language
    esc = code.replace("\\", "\\\\").replace("'''", "\\'\\'\\'")
    intro = f"# {title[:80]}\n\nSent from the Code Workbench. Run the cell below with Shift+Enter. Language: **{lang}**."
    cells: list[dict] = []

    def md(s):
        return {"cell_type": "markdown", "metadata": {}, "source": s.splitlines(True)}

    def cd(s):
        return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.splitlines(True)}
    cells.append(md(intro))
    if lang == "python":
        cells.append(cd(code))
    elif lang == "sql":
        cells.append(md("The cell below opens your dashboard database **read-only**. Set `BI_DB` to the path of your `.duckdb` file first (it is the file the dashboard uses)."))
        cells.append(cd("import os, duckdb\ncon = duckdb.connect(os.environ.get('BI_DB', 'bi.duckdb'), read_only=True)\nsql = '''" + esc + "'''\ncon.sql(sql).df()"))
    elif lang == "json":
        cells.append(cd("import json\ndata = json.loads(r'''" + esc + "''')\ndata"))
    else:
        label = "HTML" if lang == "html" else "JavaScript"
        cells.append(md(f"{label} doesn't run in a Python kernel, so it is kept here as text. " + ("The next cell displays it." if lang == "html" else "Paste it into a browser console or a `.js` file.")))
        cells.append(cd("from IPython.display import HTML, display\ndisplay(HTML(r'''" + esc + "'''))") if lang == "html" else md("```javascript\n" + code + "\n```"))
    return {"cells": cells, "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}, "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}


def jupyter_status() -> dict:
    """Is a Jupyter server answering on this computer (default port 8888)? Only ever contacts localhost."""
    import urllib.request
    for port in (8888, 8889):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api", timeout=0.6) as r:         # noqa: S310  fixed local address
                if r.status == 200:
                    return {"running": True, "url": f"http://localhost:{port}/tree"}
        except Exception:  # noqa: BLE001
            continue
    return {"running": False, "url": "http://localhost:8888/tree", "how": "In a terminal on your computer run:  pip install notebook   then   jupyter notebook"}
