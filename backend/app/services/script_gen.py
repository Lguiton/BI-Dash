"""Scripts to paste: SQL and shell text for database and data-engineering jobs.

Nothing here runs anything. Every result is text with a plain-English explanation, what to do first, how to check it worked, and a safety scan that flags
destructive statements. Names are validated, and values placed in shell scripts are quoted, so a odd table name cannot smuggle in a command."""
from __future__ import annotations

import json
import re
import shlex

DIALECTS = ("duckdb", "postgres", "mysql", "sqlite")
KINDS = {
    "create_table": "CREATE TABLE with keys, constraints and indexes",
    "upsert": "Insert-or-update (upsert) on a key",
    "dedupe": "Remove duplicates into a new table",
    "load_csv": "Load a CSV file into a table",
    "migration": "Change a table (add, rename or drop a column, add an index) with the way back",
    "backup": "Backup script (bash or PowerShell) with old-copy cleanup",
    "schedule": "Schedule a script (cron line or Windows Task Scheduler command)",
}
TYPES = {"text": {"duckdb": "VARCHAR", "postgres": "TEXT", "mysql": "VARCHAR(255)", "sqlite": "TEXT"},
         "integer": {"duckdb": "BIGINT", "postgres": "BIGINT", "mysql": "BIGINT", "sqlite": "INTEGER"},
         "number": {"duckdb": "DOUBLE", "postgres": "DOUBLE PRECISION", "mysql": "DOUBLE", "sqlite": "REAL"},
         "decimal": {"duckdb": "DECIMAL(18,2)", "postgres": "NUMERIC(18,2)", "mysql": "DECIMAL(18,2)", "sqlite": "NUMERIC"},
         "date": {"duckdb": "DATE", "postgres": "DATE", "mysql": "DATE", "sqlite": "TEXT"},
         "timestamp": {"duckdb": "TIMESTAMP", "postgres": "TIMESTAMP", "mysql": "DATETIME", "sqlite": "TEXT"},
         "bool": {"duckdb": "BOOLEAN", "postgres": "BOOLEAN", "mysql": "TINYINT(1)", "sqlite": "INTEGER"}}
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")


class ScriptError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _d(dialect: str) -> str:
    if dialect not in DIALECTS:
        raise ScriptError("dialect must be one of: " + ", ".join(DIALECTS) + ".")
    return dialect


def _n(name, what="name") -> str:
    if not isinstance(name, str) or not NAME.match(name):
        raise ScriptError(f"The {what} '{name}' must be letters, numbers and underscores only, starting with a letter or underscore.")
    return name


def _q(d: str, name: str) -> str:
    return f"`{name}`" if d == "mysql" else f'"{name}"'


def _ph(d: str, i: int) -> str:
    return f"${i}" if d == "postgres" else "%s" if d == "mysql" else "?"


def _cols(cols) -> list[dict]:
    if not isinstance(cols, list) or not cols:
        raise ScriptError("Give at least one column.")
    out = []
    for c in cols[:100]:
        t = c.get("type", "text")
        if t not in TYPES:
            raise ScriptError(f"Column type must be one of: {', '.join(TYPES)}.")
        out.append({"name": _n(c.get("name"), "column name"), "type": t, "nullable": bool(c.get("nullable", True)), "primary": bool(c.get("primary")), "unique": bool(c.get("unique")), "default": c.get("default")})
    return out


def _lit(v) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''")[:100] + "'"


# ------------------------------------------------------------------ safety scan
RISKY = [
    (r"\bdrop\s+(table|database|schema|view)\b", "high", "DROP removes a whole object and everything in it."),
    (r"\btruncate\b", "high", "TRUNCATE empties a table at once and usually can't be rolled back."),
    (r"\bdelete\s+from\s+\w+\s*;", "high", "DELETE without a WHERE removes every row."),
    (r"\bupdate\s+\w+\s+set\b(?![^;]*\bwhere\b)[^;]*;", "high", "UPDATE without a WHERE changes every row."),
    (r"\balter\s+table\b[^;]*\bdrop\b", "medium", "Dropping a column deletes its data."),
    (r"rm\s+-[a-z]*r[a-z]*f|rm\s+-[a-z]*f[a-z]*r", "high", "rm -rf deletes files without asking."),
    (r"remove-item[^\n]*-recurse", "high", "Remove-Item -Recurse deletes a folder tree."),
    (r"\bfind\b[^\n]*-delete|\bfind\b[^\n]*-exec\s+rm", "medium", "This deletes the files it finds. Run the find part without the delete first."),
    (r"chmod\s+(-R\s+)?777", "medium", "777 lets anyone read and change the files."),
    (r"(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba)?sh", "high", "Downloading and running code in one step is unsafe."),
    (r"\bdd\s+if=|\bmkfs\b|\bformat\s+[a-z]:", "high", "This can overwrite a whole disk."),
    (r"(password|passwd|secret|api[_-]?key)\s*=\s*['\"][^'\"$]{3,}", "high", "A password or key is written into the script. Use an environment variable instead."),
]


def scan(text: str) -> list[dict]:
    out = []
    for pat, sev, why in RISKY:
        if re.search(pat, text or "", re.I):
            out.append({"severity": sev, "says": why})
    return out


def _wrap(title, language, code, explain, run_first, verify, caution="") -> dict:
    return {"title": title, "language": language, "code": code.strip() + "\n", "explain": explain, "run_first": run_first, "verify": verify, "safety": scan(code),
            "caution": caution or "Text only: nothing was run. Try it on a copy of the database first.", "ran": False}


# ------------------------------------------------------------------ SQL
def create_table(dialect: str, table: str, columns: list[dict], indexes: list[list[str]] | None = None) -> dict:
    d, t, cs = _d(dialect), _n(table, "table name"), _cols(columns)
    prim = [c["name"] for c in cs if c["primary"]]
    lines = []
    for c in cs:
        ty = TYPES[c["type"]][d]
        one_pk = len(prim) == 1 and c["primary"]
        if one_pk and c["type"] == "integer" and d != "duckdb":
            ty = {"postgres": "BIGSERIAL", "mysql": "BIGINT AUTO_INCREMENT", "sqlite": "INTEGER"}[d]
        ln = f"  {_q(d, c['name'])} {ty}"
        if one_pk and d == "sqlite":
            ln += " PRIMARY KEY" if c["type"] == "integer" else ""
        if not c["nullable"] or c["primary"]:
            ln += " NOT NULL"
        if c["default"] not in (None, ""):
            ln += f" DEFAULT {_lit(c['default'])}"
        if c["unique"] and not c["primary"]:
            ln += " UNIQUE"
        lines.append(ln)
    sqlite_inline = d == "sqlite" and len(prim) == 1 and next(c for c in cs if c["name"] == prim[0])["type"] == "integer"
    if prim and not sqlite_inline:
        lines.append(f"  PRIMARY KEY ({', '.join(_q(d, p) for p in prim)})")
    code = f"CREATE TABLE IF NOT EXISTS {_q(d, t)} (\n" + ",\n".join(lines) + "\n);\n"
    for ix in indexes or []:
        names = [_n(x, "index column") for x in ix]
        code += f"CREATE INDEX IF NOT EXISTS {_q(d, 'ix_' + t + '_' + '_'.join(names))} ON {_q(d, t)} ({', '.join(_q(d, x) for x in names)});\n"
    if d == "mysql":
        code = code.replace("CREATE INDEX IF NOT EXISTS", "CREATE INDEX")
    ex = [f"Creates the table {t} if it does not exist yet, so running it twice does no harm.", "NOT NULL means the column must always have a value; PRIMARY KEY makes each row findable and unique."]
    if indexes:
        ex.append("An index makes searches on those columns faster but makes loading slightly slower. Add one only for columns you filter or join on a lot.")
    return _wrap(f"Create table {t} ({d})", "sql", code, ex, ["Run on a copy or an empty test database first.", "Check the column types match your data."], f"Run: SELECT COUNT(*) FROM {_q(d, t)}; it should return 0 on a new table.")


def upsert(dialect: str, table: str, columns: list[dict], key: list[str]) -> dict:
    d, t, cs = _d(dialect), _n(table, "table name"), _cols(columns)
    names = [c["name"] for c in cs]
    key = [_n(k, "key column") for k in (key or [])]
    if not key or any(k not in names for k in key):
        raise ScriptError("Choose key column(s) that are among the columns.")
    ins = f"INSERT INTO {_q(d, t)} ({', '.join(_q(d, n) for n in names)})\nVALUES ({', '.join(_ph(d, i + 1) for i in range(len(names)))})\n"
    upd = [n for n in names if n not in key]
    if d == "mysql":
        tail = "ON DUPLICATE KEY UPDATE " + (", ".join(f"{_q(d, n)} = VALUES({_q(d, n)})" for n in upd) if upd else f"{_q(d, key[0])} = {_q(d, key[0])}") + ";"
    else:
        tail = f"ON CONFLICT ({', '.join(_q(d, k) for k in key)}) " + ("DO UPDATE SET " + ", ".join(f"{_q(d, n)} = EXCLUDED.{_q(d, n)}" for n in upd) if upd else "DO NOTHING") + ";"
    ex = ["Inserts a row; if a row with the same key already exists it updates that row instead of creating a duplicate.", "The ? or $1 or %s marks are slots your program fills in with real values. Never paste values into the text yourself."]
    return _wrap(f"Upsert into {t} ({d})", "sql", ins + tail, ex, [f"The key columns ({', '.join(key)}) must be a PRIMARY KEY or UNIQUE in the table, or the database will refuse this."], "Run it twice with the same key: the row count must not grow.")


def dedupe(dialect: str, table: str, keys: list[str], new_table: str, order_col: str | None = None, keep: str = "first") -> dict:
    d, t, nt = _d(dialect), _n(table, "table name"), _n(new_table, "new table name")
    if nt == t:
        raise ScriptError("The new table needs a different name; the original is never changed.")
    keys = [_n(k, "key column") for k in (keys or [])]
    if not keys:
        raise ScriptError("Choose the columns that identify a duplicate.")
    if keep not in ("first", "newest"):
        raise ScriptError("keep must be first or newest.")
    if keep == "newest":
        _n(order_col, "date column")
        order = f"{_q(d, order_col)} DESC"
    else:
        order = "1"
    code = (f"CREATE TABLE {_q(d, nt)} AS\nSELECT * FROM (\n  SELECT *, ROW_NUMBER() OVER (PARTITION BY {', '.join(_q(d, k) for k in keys)} ORDER BY {order}) AS rn\n  FROM {_q(d, t)}\n) x\nWHERE rn = 1;\n"
            f"-- Then drop the helper column if you want it gone:\nALTER TABLE {_q(d, nt)} DROP COLUMN rn;\n")
    ex = [f"Copies one row per {', '.join(keys)} into a NEW table {nt}. {t} is not touched.", "ROW_NUMBER numbers the copies in each group; keeping number 1 keeps one copy."]
    if keep == "first":
        ex.append("'First' here is whichever copy the database finds first, which is not guaranteed. Use 'newest' with a date column when the choice matters.")
    return _wrap(f"Dedupe {t} into {nt} ({d})", "sql", code, ex, [f"Count first: SELECT COUNT(*) - COUNT(DISTINCT {', '.join(_q(d, k) for k in keys)}) FROM {_q(d, t)}; (works for one key column) to know how many rows will go."],
                 f"Compare SELECT COUNT(*) on both tables: the difference should equal the duplicates counted before.", "The ALTER ... DROP COLUMN line removes a column from the new table only. Skip it if unsure.")


def load_csv(dialect: str, table: str, path: str, header: bool = True, delimiter: str = ",") -> dict:
    d, t = _d(dialect), _n(table, "table name")
    if not path or re.search(r"[\x00-\x1f'\"`;]", path):
        raise ScriptError("Give a plain file path (no quotes or semicolons).")
    if delimiter not in (",", ";", "\t", "|"):
        raise ScriptError("delimiter must be a comma, semicolon, tab or pipe.")
    dl = "\\t" if delimiter == "\t" else delimiter
    h = "TRUE" if header else "FALSE"
    if d == "duckdb":
        code = f"INSERT INTO {_q(d, t)}\nSELECT * FROM read_csv('{path}', header = {h}, delim = '{dl}');\n"
    elif d == "postgres":
        code = f"-- In psql (loads from your computer):\n\\copy {_q(d, t)} FROM '{path}' WITH (FORMAT csv, HEADER {h}, DELIMITER '{dl}')\n"
    elif d == "mysql":
        code = f"LOAD DATA LOCAL INFILE '{path}'\nINTO TABLE {_q(d, t)}\nFIELDS TERMINATED BY '{dl}' OPTIONALLY ENCLOSED BY '\"'\nLINES TERMINATED BY '\\n'\n{'IGNORE 1 LINES' if header else ''};\n"
    else:
        code = f".mode csv\n.separator '{dl}'\n.import {'--skip 1 ' if header else ''}'{path}' {t}\n"
    ex = [f"Reads the file and adds its rows to {t}. Columns are matched by position, so the file's columns must be in the same order as the table.", "Loading twice adds the rows twice; load into an empty table or a staging table, then upsert."]
    return _wrap(f"Load CSV into {t} ({d})", "sql", code, ex, ["Open the CSV and check the first row is a header (or not) as you set it.", "Load into a copy of the table first."], f"SELECT COUNT(*) FROM {_q(d, t)}; should equal the file's line count (minus the header).")


def migration(dialect: str, table: str, action: str, column: str = "", new_name: str = "", col_type: str = "text", index_cols: list[str] | None = None) -> dict:
    d, t = _d(dialect), _n(table, "table name")
    Q = lambda x: _q(d, x)  # noqa: E731
    if action == "add_column":
        c = _n(column, "column name")
        if col_type not in TYPES:
            raise ScriptError(f"Column type must be one of: {', '.join(TYPES)}.")
        up = f"ALTER TABLE {Q(t)} ADD COLUMN {Q(c)} {TYPES[col_type][d]};"
        down = f"ALTER TABLE {Q(t)} DROP COLUMN {Q(c)};"
        ex = ["Adds an empty column. Existing rows get a blank (NULL) value in it."]
    elif action == "rename_column":
        c, n2 = _n(column, "column name"), _n(new_name, "new column name")
        up, down = f"ALTER TABLE {Q(t)} RENAME COLUMN {Q(c)} TO {Q(n2)};", f"ALTER TABLE {Q(t)} RENAME COLUMN {Q(n2)} TO {Q(c)};"
        ex = ["Renames the column. Every report, rule and query that used the old name will break: update them in the same change."]
    elif action == "drop_column":
        c = _n(column, "column name")
        up = f"ALTER TABLE {Q(t)} DROP COLUMN {Q(c)};"
        down = "-- Not reversible: the data in the column is gone. Restore from your backup.\n"
        ex = ["Removes the column and ALL its data. Back up first."]
    elif action == "add_index":
        cols = [_n(x, "index column") for x in (index_cols or [])]
        if not cols:
            raise ScriptError("Choose the column(s) to index.")
        nm = "ix_" + t + "_" + "_".join(cols)
        up = f"CREATE INDEX {Q(nm)} ON {Q(t)} ({', '.join(Q(x) for x in cols)});"
        down = f"DROP INDEX {Q(nm)}" + (f" ON {Q(t)}" if d == "mysql" else "") + ";"
        ex = ["Makes lookups on those columns faster, and loads slightly slower."]
    else:
        raise ScriptError("action must be add_column, rename_column, drop_column or add_index.")
    code = f"-- UP: apply the change\n{up}\n\n-- DOWN: undo it\n{down}\n"
    out = _wrap(f"Migration: {action.replace('_', ' ')} on {t} ({d})", "sql", code, ex + ["Run the UP part only. Keep the DOWN part for the day you need to go back."], ["Back up the database.", "Test on a copy."], f"Describe the table afterwards and confirm the change; then run your reports.",
                "The DOWN part is intentionally in the same text. Do not run both.")
    out["safety"] = scan(up)
    return out


# ------------------------------------------------------------------ shell
def _bash_q(v: str) -> str:
    if re.search(r"[\x00-\x1f]", v):
        raise ScriptError("Paths and names cannot contain line breaks.")
    return shlex.quote(v)


def _ps_q(v: str) -> str:
    if re.search(r"[\x00-\x1f]", v):
        raise ScriptError("Paths and names cannot contain line breaks.")
    return "'" + v.replace("'", "''") + "'"


def backup(shell: str, engine: str, source: str, dest_dir: str, keep_days: int = 14) -> dict:
    if shell not in ("bash", "powershell"):
        raise ScriptError("shell must be bash or powershell.")
    if engine not in DIALECTS:
        raise ScriptError("engine must be one of: " + ", ".join(DIALECTS) + ".")
    keep_days = int(keep_days)
    if not 1 <= keep_days <= 3650:
        raise ScriptError("keep_days must be between 1 and 3650.")
    if not source or not dest_dir:
        raise ScriptError("Give the database (file path or name) and the backup folder.")
    ext = {"duckdb": "duckdb", "sqlite": "db", "postgres": "sql", "mysql": "sql"}[engine]
    if shell == "bash":
        s, dd = _bash_q(source), _bash_q(dest_dir)
        cmd = {"duckdb": 'cp "$SRC" "$OUT"', "sqlite": 'sqlite3 "$SRC" ".backup \'$OUT\'"', "postgres": 'pg_dump "$SRC" > "$OUT"', "mysql": 'mysqldump "$SRC" > "$OUT"'}[engine]
        note = {"postgres": "SRC is the database name or a connection string. Put the password in ~/.pgpass, not in this script.", "mysql": "SRC is the database name. Put the login in ~/.my.cnf (chmod 600), not in this script.",
                "duckdb": "Close the app or stop writes first, or the copy may be mid-write.", "sqlite": "The .backup command is safe while the database is in use."}[engine]
        code = (f"#!/usr/bin/env bash\nset -euo pipefail\nSRC={s}\nDEST={dd}\nKEEP_DAYS={keep_days}\nmkdir -p \"$DEST\"\nSTAMP=$(date +%Y%m%d-%H%M%S)\nOUT=\"$DEST/backup-$STAMP.{ext}\"\n{cmd}\n"
                f"gzip \"$OUT\"\n# remove copies older than KEEP_DAYS (only files this script made)\nfind \"$DEST\" -name 'backup-*.{ext}.gz' -mtime +\"$KEEP_DAYS\" -delete\necho \"Backup written: $OUT.gz\"\n")
        lang = "bash"
    else:
        s, dd = _ps_q(source), _ps_q(dest_dir)
        cmd = {"duckdb": "Copy-Item -LiteralPath $Src -Destination $Out", "sqlite": 'sqlite3 $Src ".backup $Out"', "postgres": "pg_dump $Src | Out-File -Encoding utf8 -FilePath $Out", "mysql": "mysqldump $Src | Out-File -Encoding utf8 -FilePath $Out"}[engine]
        note = {"postgres": "Src is the database name or connection string. Put the password in the PGPASSWORD environment variable or pgpass.conf, not in this script.", "mysql": "Put the login in an option file, not in this script.",
                "duckdb": "Close the app or stop writes first, or the copy may be mid-write.", "sqlite": "Needs the sqlite3 command on your PATH."}[engine]
        code = (f"$ErrorActionPreference = 'Stop'\n$Src = {s}\n$Dest = {dd}\n$KeepDays = {keep_days}\nNew-Item -ItemType Directory -Force -Path $Dest | Out-Null\n$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'\n$Out = Join-Path $Dest \"backup-$Stamp.{ext}\"\n{cmd}\n"
                f"Compress-Archive -LiteralPath $Out -DestinationPath \"$Out.zip\"\nRemove-Item -LiteralPath $Out\n# remove zips older than KeepDays (only files this script made)\nGet-ChildItem -Path $Dest -Filter 'backup-*.{ext}.zip' | Where-Object {{ $_.LastWriteTime -lt (Get-Date).AddDays(-$KeepDays) }} | Remove-Item\nWrite-Output \"Backup written: $Out.zip\"\n")
        lang = "powershell"
    return _wrap(f"{engine} backup script ({shell})", lang, code, [f"Makes a dated, compressed copy of the database in the backup folder and deletes copies older than {keep_days} days (only the ones this script named).", note],
                 ["Run it once by hand and look in the backup folder.", "Back up to a second drive or a cloud-synced folder, not the same disk."], "Restore the backup into a test database once. A backup you never restored is a hope, not a backup.",
                 "The cleanup line deletes old backups. Check the folder path twice before scheduling it.")


def schedule(shell: str, script_path: str, when: str = "02:30", days: str = "daily") -> dict:
    if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", when or ""):
        raise ScriptError("when must be a 24-hour time like 02:30.")
    if days not in ("daily", "weekdays", "weekly"):
        raise ScriptError("days must be daily, weekdays or weekly.")
    h, m = when.split(":")
    if shell == "bash":
        dow = {"daily": "*", "weekdays": "1-5", "weekly": "0"}[days]
        code = f"# Add with: crontab -e\n{int(m)} {int(h)} * * {dow} {_bash_q(script_path)} >> \"$HOME/backup.log\" 2>&1\n"
        lang, ex = "bash", ["Cron runs the script at that time and appends its output to a log file you can read if something fails.", "Cron only runs while the computer is on."]
    elif shell == "powershell":
        sched = {"daily": "/SC DAILY", "weekdays": "/SC WEEKLY /D MON,TUE,WED,THU,FRI", "weekly": "/SC WEEKLY /D SUN"}[days]
        code = f"schtasks /Create /TN \"DataJob\" {sched} /ST {when} /TR \"powershell -NoProfile -ExecutionPolicy Bypass -File {script_path}\"\n"
        if re.search(r"[\"\x00-\x1f]", script_path):
            raise ScriptError("The script path cannot contain double quotes or line breaks.")
        lang, ex = "powershell", ["Windows Task Scheduler runs the script at that time.", "If the computer is off then, the job is skipped unless you tick 'run as soon as possible after a missed start' in the task's settings."]
    else:
        raise ScriptError("shell must be bash or powershell.")
    return _wrap(f"Schedule {days} at {when} ({shell})", lang, code, ex, ["Run the script by hand first and confirm it works."], "List the schedule (crontab -l or schtasks /Query /TN DataJob) and check it again after the first run time.")


GENERATORS = {"create_table": create_table, "upsert": upsert, "dedupe": dedupe, "load_csv": load_csv, "migration": migration, "backup": backup, "schedule": schedule}


def generate(kind: str, params: dict) -> dict:
    fn = GENERATORS.get(kind)
    if not fn:
        raise ScriptError("kind must be one of: " + ", ".join(GENERATORS) + ".")
    p = dict(params or {})
    try:
        return fn(**p)
    except TypeError as e:
        raise ScriptError(f"Missing or unknown options for {kind}: {e}") from None


TOOL_MAKE_SCRIPT = {"name": "make_script", "description": "Write a SQL or shell script as TEXT for the user to paste (nothing is run). kind: create_table(dialect, table, columns[{name,type,nullable,primary,unique,default}], indexes), upsert(dialect, table, columns, key), "
                    "dedupe(dialect, table, keys, new_table, order_col, keep), load_csv(dialect, table, path, header, delimiter), migration(dialect, table, action, column, new_name, col_type, index_cols), backup(shell, engine, source, dest_dir, keep_days), schedule(shell, script_path, when, days). "
                    "dialect/engine: duckdb|postgres|mysql|sqlite; shell: bash|powershell; types: text,integer,number,decimal,date,timestamp,bool. Show the code in a code block, then read out the run_first steps, the verify step and any safety warnings. Say it has not been run.",
                    "input_schema": {"type": "object", "properties": {"kind": {"type": "string", "enum": list(GENERATORS)}, "params": {"type": "object"}}, "required": ["kind", "params"]}}


def tool_result(args: dict) -> str:
    try:
        return json.dumps(generate(str((args or {}).get("kind") or ""), (args or {}).get("params") or {}))
    except ScriptError as e:
        return json.dumps({"error": e.message})
