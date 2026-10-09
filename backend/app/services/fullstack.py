"""Full-stack developer tools that work on this very project.

* api_map: every endpoint the running API exposes, read from its own OpenAPI schema.
* request_test: call one of those endpoints in-process (like Postman, but inside the app). Writes are allowed in Practice only.
* scaffold: turn any table into starter code for every layer (SQL, Pydantic, FastAPI CRUD, TypeScript, React, pytest).
  It returns text for you to read and paste. It never writes files for you.
* codebase: lines, files and tests per language, read from the project folder.
* stack: versions and configuration facts. Only things the app can actually see; no scores, no pretend audits.
"""
from __future__ import annotations

import importlib.metadata as md
import os
import platform
import re
import shutil
import time
from pathlib import Path

from app.config import BASE_DIR, cors_origins
from app.services import state, workspaces
from app.services.db import fetch_all, get_cursor

ROOT = BASE_DIR.parent
METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE")
MAX_BODY_SHOWN = 20_000
# Switching workspace from a tester would silently change what every other page shows.
BLOCKED_PATHS = ("/api/workspaces/active", "/api/fullstack/request")


class FsError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# ------------------------------------------------------------------ API map
def api_map(app) -> dict:
    spec = app.openapi()
    comps = spec.get("components", {}).get("schemas", {})
    out = []
    for path, ops in spec.get("paths", {}).items():
        for method, op in ops.items():
            if method.upper() not in METHODS:
                continue
            params = [{"name": p["name"], "in": p["in"], "required": bool(p.get("required")), "type": (p.get("schema") or {}).get("type", "string")}
                      for p in op.get("parameters", [])]
            body = (op.get("requestBody") or {}).get("content", {})
            sample = None
            if "application/json" in body:
                ref = (body["application/json"].get("schema") or {}).get("$ref", "")
                props = comps.get(ref.split("/")[-1], {}).get("properties")
                sample = {k: None for k in props} if props else {}
            out.append({"method": method.upper(), "path": path, "group": (path.split("/")[2] if path.count("/") >= 2 else "root"),
                        "summary": op.get("summary", ""), "params": params, "json_body": sample is not None, "sample_body": sample,
                        "multipart": "multipart/form-data" in body})
    out.sort(key=lambda e: (e["group"], e["path"], METHODS.index(e["method"])))
    groups: dict[str, int] = {}
    for e in out:
        groups[e["group"]] = groups.get(e["group"], 0) + 1
    by_method = {m: sum(1 for e in out if e["method"] == m) for m in METHODS}
    return {"title": spec.get("info", {}).get("title"), "version": spec.get("info", {}).get("version"), "total": len(out),
            "by_method": by_method, "groups": [{"group": g, "endpoints": n} for g, n in sorted(groups.items())], "endpoints": out}


def request_test(app, method: str, path: str, body=None) -> dict:
    method = (method or "").upper()
    if method not in METHODS:
        raise FsError(f"method must be one of {', '.join(METHODS)}.")
    if not isinstance(path, str) or not path.startswith("/api/") or "//" in path or ".." in path or "\\" in path or "#" in path:
        raise FsError("Only paths on this app's own API are allowed, and they must start with /api/.")
    if path.split("?")[0] in BLOCKED_PATHS:
        raise FsError("That endpoint is blocked in the tester: switch workspaces with the Practice/Real switch instead.")
    if method != "GET" and workspaces.active() != "practice":
        raise FsError("The tester only sends GET requests while the Real workspace is active, so a test can't change real data. Switch to Practice to try writes.", 409)
    from fastapi.testclient import TestClient
    client = TestClient(app, raise_server_exceptions=False)
    kwargs = {}
    if body not in (None, ""):
        kwargs["json"] = body
    t0 = time.perf_counter()
    try:
        r = client.request(method, path, **kwargs)
    except Exception as e:  # noqa: BLE001
        raise FsError(f"The request couldn't be made: {e}") from None
    ms = (time.perf_counter() - t0) * 1000
    ctype = r.headers.get("content-type", "")
    text = r.text if ("json" in ctype or ctype.startswith("text/")) else f"<{len(r.content):,} bytes of {ctype or 'binary data'}>"
    shown = text[:MAX_BODY_SHOWN]
    state.audit("fullstack_request", f"{method} {path} -> {r.status_code}", ok=r.status_code < 400)
    return {"method": method, "path": path, "status": r.status_code, "ms": round(ms, 1), "content_type": ctype, "truncated": len(text) > MAX_BODY_SHOWN,
            "body": shown, "reading": _reading(r.status_code)}


def _reading(code: int) -> str:
    return ("Success." if code < 300 else "Redirect." if code < 400 else
            "The request was wrong: read the message, then check the path, parameters and body (422 means the body didn't match the schema)."
            if code < 500 else "The server failed on a valid-looking request: that's a bug to find in the logs and fix.")


# ------------------------------------------------------------------ scaffold
PY = {"BIGINT": "int", "INTEGER": "int", "SMALLINT": "int", "TINYINT": "int", "HUGEINT": "int", "UBIGINT": "int", "UINTEGER": "int",
      "DOUBLE": "float", "FLOAT": "float", "REAL": "float", "BOOLEAN": "bool", "DATE": "date", "TIMESTAMP": "datetime", "VARCHAR": "str"}
TS = {"int": "number", "float": "number", "bool": "boolean", "date": "string", "datetime": "string", "str": "string"}
HTML = {"int": "number", "float": "number", "bool": "checkbox", "date": "date", "datetime": "datetime-local", "str": "text"}


def _py_type(t: str) -> str:
    t = t.upper().split("(")[0].strip()
    return "float" if t.startswith("DECIMAL") else PY.get(t, "str")


def _ident(s: str) -> str:
    s = re.sub(r"\W+", "_", s).strip("_") or "col"
    return ("c_" + s) if s[0].isdigit() else s


def _camel(s: str) -> str:
    return "".join(p.capitalize() for p in _ident(s).split("_")) or "Item"


def scaffold_tables() -> list[str]:
    from app.services import governance
    with get_cursor() as cur:
        return sorted(n for n, o in governance._objects(cur).items() if o["kind"] == "table" and n not in governance.SYSTEM_TABLES)


def scaffold(table: str, with_ui: bool = True) -> dict:
    if table not in scaffold_tables():
        raise FsError("Pick one of your tables (system tables aren't scaffolded).", 404)
    with get_cursor() as cur:
        cols = fetch_all(cur, "SELECT column_name AS name, data_type AS type, is_nullable = 'YES' AS nullable FROM information_schema.columns WHERE table_name = ? ORDER BY ordinal_position", [table])
        pk = [r[0] for r in cur.execute("SELECT unnest(constraint_column_names) FROM duckdb_constraints() WHERE table_name = ? AND constraint_type = 'PRIMARY KEY'", [table]).fetchall()]
    if not cols:
        raise FsError("That table has no columns.", 404)
    pk_col = pk[0] if len(pk) == 1 else None
    cls, route = _camel(table), "/api/" + table.replace("_", "-")
    fields = [{**c, "py": _py_type(c["type"]), "id": _ident(c["name"])} for c in cols]
    q = lambda n: '"' + n.replace('"', '""') + '"'  # noqa: E731

    ddl = f"CREATE TABLE IF NOT EXISTS {q(table)} (\n" + ",\n".join(
        f"  {q(f['name'])} {f['type']}{'' if f['nullable'] else ' NOT NULL'}{' PRIMARY KEY' if f['name'] == pk_col else ''}" for f in fields) + "\n);"

    py_models = (
        "from datetime import date, datetime\nfrom pydantic import BaseModel\n\n\n"
        f"class {cls}In(BaseModel):\n    \"\"\"What a client may send. The primary key is chosen by the database or the caller, as you decide.\"\"\"\n" +
        "\n".join(f"    {f['id']}: {f['py']}{' | None = None' if f['nullable'] and f['name'] != pk_col else ''}" for f in fields if f["name"] != pk_col or True) +
        f"\n\n\nclass {cls}Out({cls}In):\n    pass\n")

    names = [q(f["name"]) for f in fields]
    non_pk = [f for f in fields if f["name"] != pk_col]
    if pk_col:
        router = f'''from fastapi import APIRouter, HTTPException

from app.services.db import fetch_all, get_cursor

router = APIRouter(prefix="{route}", tags=["{table}"])
COLS = [{", ".join(repr(f["name"]) for f in fields)}]


@router.get("")
def list_rows(limit: int = 100, offset: int = 0):
    with get_cursor() as cur:
        return fetch_all(cur, 'SELECT * FROM {q(table)} ORDER BY {q(pk_col)} LIMIT ? OFFSET ?', [min(limit, 1000), offset])


@router.get("/{{key}}")
def get_row(key: str):
    with get_cursor() as cur:
        rows = fetch_all(cur, 'SELECT * FROM {q(table)} WHERE {q(pk_col)} = ?', [key])
    if not rows:
        raise HTTPException(404, "Not found")
    return rows[0]


@router.post("", status_code=201)
def create_row(body: dict):
    data = {{k: v for k, v in body.items() if k in COLS}}
    if not data:
        raise HTTPException(422, "Send at least one known column.")
    cols = ", ".join('"' + c + '"' for c in data)
    marks = ", ".join("?" * len(data))
    with get_cursor() as cur:
        cur.execute(f'INSERT INTO {q(table)} ({{cols}}) VALUES ({{marks}})', list(data.values()))
    return data


@router.put("/{{key}}")
def update_row(key: str, body: dict):
    data = {{k: v for k, v in body.items() if k in COLS and k != {pk_col!r}}}
    if not data:
        raise HTTPException(422, "Nothing to update.")
    sets = ", ".join('"' + c + '" = ?' for c in data)
    with get_cursor() as cur:
        cur.execute(f'UPDATE {q(table)} SET {{sets}} WHERE {q(pk_col)} = ?', [*data.values(), key])
    return get_row(key)


@router.delete("/{{key}}")
def delete_row(key: str):
    with get_cursor() as cur:
        cur.execute('DELETE FROM {q(table)} WHERE {q(pk_col)} = ?', [key])
    return {{"deleted": key}}
'''
    else:
        router = (f"# {table} has no single-column primary key, so row-level GET/PUT/DELETE by id would be ambiguous.\n"
                  "# Add a primary key first (ALTER TABLE ... or recreate with the DDL above), then regenerate.\n"
                  f"from fastapi import APIRouter\n\nfrom app.services.db import fetch_all, get_cursor\n\nrouter = APIRouter(prefix=\"{route}\", tags=[\"{table}\"])\n\n\n"
                  f"@router.get(\"\")\ndef list_rows(limit: int = 100, offset: int = 0):\n    with get_cursor() as cur:\n"
                  f"        return fetch_all(cur, 'SELECT * FROM {q(table)} LIMIT ? OFFSET ?', [min(limit, 1000), offset])\n")

    ts = f"export interface {cls} {{\n" + "\n".join(f"  {f['id']}{'?' if f['nullable'] else ''}: {TS[f['py']]}{' | null' if f['nullable'] else ''};" for f in fields) + "\n}\n"

    ui = ""
    if with_ui:
        inputs = "\n".join(
            f'      <label className="flex flex-col gap-1 text-xs text-muted">{f["name"]}\n'
            f'        <input className="field" type="{HTML[f["py"]]}" value={{String(form.{f["id"]} ?? "")}} onChange={{(e) => setForm({{ ...form, {f["id"]}: e.target.value }})}} />\n      </label>'
            for f in non_pk[:8] if f["py"] != "bool")
        ui = f'''"use client";
import {{ useEffect, useState }} from "react";
import {{ getJson, postJson }} from "@/lib/api";
import type {{ {cls} }} from "@/lib/types";

export function {cls}Panel() {{
  const [rows, setRows] = useState<{cls}[]>([]);
  const [form, setForm] = useState<Partial<Record<keyof {cls}, string>>>({{}});
  const [version, setVersion] = useState(0);
  useEffect(() => {{
    const ctl = new AbortController();
    getJson<{cls}[]>("{route}", ctl.signal).then(setRows).catch(() => {{}});
    return () => ctl.abort();
  }}, [version]);
  return (
    <section className="card p-4 space-y-3">
      <h3 className="text-sm font-semibold">{table}</h3>
{inputs}
      <button className="btn btn-primary" onClick={{async () => {{ await postJson("{route}", form); setForm({{}}); setVersion((v) => v + 1); }}}}>Add</button>
      <pre className="text-xs overflow-auto">{{JSON.stringify(rows, null, 2)}}</pre>
    </section>
  );
}}
'''
    sample = {f["name"]: ("2026-01-01" if f["py"] == "date" else 1 if f["py"] in ("int", "float") else True if f["py"] == "bool" else "sample") for f in non_pk}
    test = f'''def test_{_ident(table)}_list_and_create(client):
    r = client.get("{route}")
    assert r.status_code == 200 and isinstance(r.json(), list)
    # Change the sample values so they satisfy this table's real constraints, then assert the row comes back.
    r = client.post("{route}", json={sample!r})
    assert r.status_code in (201, 422)
'''
    files = [{"name": f"{table}.sql", "language": "sql", "content": ddl + "\n"},
             {"name": f"backend/app/routers/{_ident(table)}.py", "language": "python", "content": py_models + "\n\n" + router},
             {"name": "frontend/src/lib/types.ts (add)", "language": "typescript", "content": ts},
             {"name": f"backend/tests/test_{_ident(table)}.py", "language": "python", "content": test}]
    if ui:
        files.insert(3, {"name": f"frontend/src/components/{cls}Panel.tsx", "language": "typescript", "content": ui})
    return {"table": table, "primary_key": pk_col, "columns": len(fields), "route": route, "files": files,
            "next_steps": [f"Read the generated router: every value is a bound `?` parameter, never pasted into the SQL.",
                           "Register it in app/main.py with app.include_router(...), then restart the backend.",
                           "Open the API map tab and send a request to it with the tester.",
                           "Add validation and real tests: scaffolds are a starting point, not a finished feature."],
            "caveat": "Generated from the table's columns only. It doesn't know your business rules, permissions or relationships."}


# ------------------------------------------------------------------ codebase
LANG = {".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript (React)", ".css": "CSS", ".md": "Markdown", ".sql": "SQL", ".ipynb": "Notebook", ".yml": "YAML", ".yaml": "YAML", ".json": "JSON", ".mjs": "JavaScript"}
SKIP_DIRS = {"node_modules", ".next", ".venv", "venv", "__pycache__", ".git", "lake", "_out", "landing", "_work", ".pytest_cache", "backups", "public"}


def codebase() -> dict:
    stats: dict[str, dict] = {}
    big: list[tuple[int, str]] = []
    tests = routes = 0
    n_files = 0
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            ext = Path(f).suffix.lower()
            if ext not in LANG or f.endswith((".duckdb", ".lock")) or f in ("package-lock.json",):
                continue
            p = Path(dirpath) / f
            try:
                if p.stat().st_size > 2_000_000:
                    continue
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            n_files += 1
            if n_files > 20_000:
                break
            lines = sum(1 for ln in text.splitlines() if ln.strip())
            s = stats.setdefault(LANG[ext], {"language": LANG[ext], "files": 0, "lines": 0})
            s["files"] += 1
            s["lines"] += lines
            rel = str(p.relative_to(ROOT))
            if ext in (".py", ".ts", ".tsx"):
                big.append((lines, rel))
            if ext == ".py" and "/tests/" in "/" + rel.replace("\\", "/"):
                tests += len(re.findall(r"^\s*(?:async\s+)?def test_", text, flags=re.M))
            if ext == ".py" and "routers" in rel:
                routes += len(re.findall(r"@router\.(?:get|post|put|patch|delete)\(", text))
    langs = sorted(stats.values(), key=lambda s: -s["lines"])
    py = stats.get("Python", {"lines": 0})["lines"]
    test_lines = 0
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if Path(dirpath).name == "tests":
            for f in files:
                if f.endswith(".py"):
                    try:
                        test_lines += sum(1 for ln in (Path(dirpath) / f).read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip())
                    except OSError:
                        pass
    big.sort(reverse=True)
    return {"languages": langs, "files": n_files, "tests": tests, "route_functions": routes,
            "test_to_python_ratio": round(test_lines / py, 2) if py else None,
            "largest": [{"file": f, "lines": n} for n, f in big[:8]],
            "reading": "Lines are non-blank lines. A very large file is a hint it does too many jobs; the test ratio is a rough signal, not a quality score."}


# ------------------------------------------------------------------ stack and configuration facts
def _ver(pkg: str) -> str | None:
    try:
        return md.version(pkg)
    except md.PackageNotFoundError:
        return None


def stack() -> dict:
    ws = workspaces.active()
    origins = cors_origins()
    gitignore = (ROOT / ".gitignore")
    ignored = gitignore.read_text(errors="ignore").splitlines() if gitignore.exists() else []
    env_names = ["GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"]
    with get_cursor() as cur:
        ext = cur.execute("SELECT current_setting('enable_external_access')").fetchone()[0]
    facts = [
        {"area": "Authentication", "value": "none (single-user app)", "note": "Deliberate for personal use. Before exposing it beyond localhost, put it behind a login or a private network (see docs/REAL_USE.md)."},
        {"area": "CORS allowed origins", "value": ", ".join(origins), "note": "Wildcard * is " + ("PRESENT: tighten it." if "*" in origins else "not used. Good.")},
        {"area": "Database external access", "value": str(ext), "note": "DuckDB can't read arbitrary files or URLs from SQL." if str(ext).lower() in ("false", "0") else "SQL could read files from disk: review."},
        {"area": ".env ignored by git", "value": "yes" if any(x.strip() in (".env", "*.env", "backend/.env") for x in ignored) else "NOT FOUND", "note": "API keys must never be committed."},
        {"area": "AI keys present (names only)", "value": ", ".join(n for n in env_names if os.environ.get(n)) or "none", "note": "Values are never shown."},
        {"area": "Active workspace", "value": ws, "note": "Practice and Real are separate database files."},
    ]
    tools = {t: bool(shutil.which(t)) for t in ("node", "npm", "git", "docker", "psql")}
    return {"python": platform.python_version(), "platform": platform.platform(),
            "packages": {p: _ver(p) for p in ("fastapi", "starlette", "uvicorn", "pydantic", "duckdb", "pandas", "scikit-learn", "psycopg")},
            "tools_on_path": tools, "facts": facts,
            "reading": "These are facts the running app can see, not a security audit. Anything not listed here has not been checked."}
