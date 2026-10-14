"""Data Engineering tools: schema change detector, dedupe and merge with Undo, data contracts, and a volume cost/speed estimator.

Rules these follow: the original table is never changed (every dedupe or merge makes a NEW table you can drop with Undo), every change is previewed first with
counts, and every estimate is a range with its assumptions written out."""
from __future__ import annotations

import difflib
import json
import math
import re
import time

from app.services import biz_models, datasets, state, workspaces
from app.services.db import fetch_all, get_cursor

q = datasets.q


class DeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _table(source: str) -> str:
    try:
        return biz_models._table_for(source)[0]
    except biz_models.ModelError as e:
        raise DeError(str(e), getattr(e, "status", 400)) from None


def _cols(t: str) -> list[dict]:
    with get_cursor() as cur:
        return fetch_all(cur, "SELECT column_name AS name, data_type AS type FROM information_schema.columns WHERE table_schema='main' AND table_name = ? ORDER BY ordinal_position", [t])


def _kv(name: str) -> dict:
    raw = state.kv_get(f"detools:{name}:{workspaces.active()}")
    return json.loads(raw) if raw else {}


def _kv_set(name: str, d: dict) -> None:
    state.kv_set(f"detools:{name}:{workspaces.active()}", json.dumps(d))


def _kind(t: str) -> str:
    return datasets.kind_of(t)


# ------------------------------------------------------------------ 1. schema change detector

def snapshot(source: str) -> dict:
    t = _table(source)
    cs = _cols(t)
    with get_cursor() as cur:
        n = cur.execute(f"SELECT COUNT(*) FROM {q(t)}").fetchone()[0]
    d = _kv("snap")
    h = d.setdefault(t, [])
    h.append({"at": time.strftime("%Y-%m-%d %H:%M"), "columns": cs, "rows": n})
    d[t] = h[-10:]
    _kv_set("snap", d)
    return {"table": t, "columns": len(cs), "rows": n, "saved": h[-1]["at"]}


def schema_check(source: str, accept: bool = False) -> dict:
    t = _table(source)
    live = _cols(t)
    d = _kv("snap")
    h = d.get(t)
    if not h:
        return {"table": t, "status": "no_baseline", "says": "No saved shape for this table yet. Save one now while the data is known to be good, then check again after the next load.", "changes": []}
    base = h[-1]["columns"]
    bn, ln = {c["name"]: c["type"] for c in base}, {c["name"]: c["type"] for c in live}
    missing, new = [n for n in bn if n not in ln], [n for n in ln if n not in bn]
    changes, used_new = [], set()
    for m in missing:
        # a missing column plus a new one of the same type with a similar name is probably a rename
        best = max(((max(difflib.SequenceMatcher(None, m.lower(), n.lower()).ratio(), 0.8 if min(len(m), len(n)) >= 3 and (m.lower() in n.lower() or n.lower() in m.lower()) else 0), n) for n in new if n not in used_new and _kind(ln[n]) == _kind(bn[m])), default=(0, None))
        if best[1] and best[0] >= 0.6:
            used_new.add(best[1])
            changes.append({"kind": "renamed", "column": m, "to": best[1], "severity": "high", "says": f"'{m}' looks renamed to '{best[1]}'. Anything that reads '{m}' will break or go blank."})
        else:
            changes.append({"kind": "missing", "column": m, "severity": "high", "says": f"'{m}' is gone. Reports and rules that use it will fail."})
    for n in new:
        if n not in used_new:
            changes.append({"kind": "new", "column": n, "severity": "low", "says": f"'{n}' is new. Nothing breaks, but decide whether you want it."})
    for n in bn:
        if n in ln and bn[n] != ln[n]:
            sev = "high" if _kind(bn[n]) != _kind(ln[n]) else "medium"
            changes.append({"kind": "type_changed", "column": n, "was": bn[n], "now": ln[n], "severity": sev, "says": f"'{n}' changed from {bn[n]} to {ln[n]}." + (" Math or date logic on it may now be wrong." if sev == "high" else "")})
    order_moved = [n for n in bn if n in ln] != [n for n in ln if n in bn]
    if order_moved and not changes:
        changes.append({"kind": "reordered", "column": "", "severity": "low", "says": "Columns are in a different order. Fine if everything reads columns by name; a problem if anything reads by position."})
    status = "ok" if not changes else ("breaking" if any(c["severity"] == "high" for c in changes) else "changed")
    says = {"ok": "Same shape as the saved baseline.", "changed": "Small changes. Nothing is broken, but look them over.", "breaking": "Breaking changes found. Fix the source or the reports before the next refresh."}[status]
    out = {"table": t, "status": status, "says": says, "changes": changes, "baseline_at": h[-1]["at"], "columns_now": len(live)}
    if accept:
        out["accepted"] = snapshot(t)
    return out


def snapshots() -> list[dict]:
    return [{"table": t, "saved": h[-1]["at"], "columns": len(h[-1]["columns"]), "versions": len(h)} for t, h in _kv("snap").items()]


# ------------------------------------------------------------------ 2. dedupe and merge (new table, with Undo)

MARK = ("deduped from ", "merged from ")


def _norm_expr(c: str, kind: str) -> str:
    return f"lower(trim(CAST({q(c)} AS VARCHAR)))" if kind == "text" else f"CAST({q(c)} AS VARCHAR)"


def _check_keys(t: str, keys: list[str]) -> dict[str, str]:
    cs = {c["name"]: _kind(c["type"]) for c in _cols(t)}
    if not keys:
        raise DeError("Choose at least one column that identifies a duplicate (like email, or customer plus date).")
    bad = [k for k in keys if k not in cs]
    if bad:
        raise DeError("Not in the table: " + ", ".join(bad) + ".")
    return cs


def dedupe_preview(source: str, keys: list[str], keep: str = "first", order_col: str | None = None) -> dict:
    t = _table(source)
    cs = _check_keys(t, keys)
    k = ", ".join(_norm_expr(c, cs[c]) for c in keys)
    with get_cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) FROM {q(t)}").fetchone()[0]
        grp = cur.execute(f"SELECT COUNT(*), COALESCE(SUM(n - 1), 0) FROM (SELECT COUNT(*) n FROM {q(t)} GROUP BY {k} HAVING COUNT(*) > 1)").fetchone()
        blank = cur.execute(f"SELECT COUNT(*) FROM {q(t)} WHERE " + " OR ".join(f"{q(c)} IS NULL" for c in keys)).fetchone()[0]
        sample = fetch_all(cur, f"SELECT {', '.join(q(c) for c in keys)}, COUNT(*) AS copies FROM {q(t)} GROUP BY {', '.join(q(c) for c in keys)} HAVING COUNT(*) > 1 ORDER BY copies DESC LIMIT 10")
    warn = []
    if blank:
        warn.append(f"{blank} row(s) have a blank in a key column. Blanks are treated as equal to each other, so they would collapse into one row.")
    if keep in ("newest", "oldest") and not order_col:
        warn.append("Choose a date column to say which copy is newest.")
    return {"table": t, "rows": total, "duplicate_groups": grp[0], "rows_to_remove": int(grp[1]), "rows_after": total - int(grp[1]), "examples": sample, "warnings": warn,
            "says": (f"{grp[0]} group(s) repeat; {int(grp[1])} extra row(s) would be removed, leaving {total - int(grp[1])}." if grp[0] else "No duplicates on those columns."),
            "note": "Text is compared ignoring capital letters and extra spaces. The original table is not touched."}


def _new_name(new_table: str, src: str) -> str:
    if not (new_table or "").strip():
        raise DeError("Name the new table.")
    target = datasets.table_name_for(new_table)
    if target == src:
        raise DeError("The new table needs a different name: the original is never changed.")
    datasets.ensure_registry()
    with get_cursor() as cur:
        exists = cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name = ?", [target]).fetchone()
        reg = cur.execute("SELECT source FROM user_tables WHERE table_name = ?", [target]).fetchone()
    if exists and not (reg and str(reg[0]).startswith(MARK)):
        raise DeError(f"'{target}' already exists and wasn't made by this tool. Pick another name.")
    return target


def _register(cur, target: str, label: str, source: str) -> int:
    meta = fetch_all(cur, "SELECT column_name AS name, data_type AS type FROM information_schema.columns WHERE table_schema='main' AND table_name = ? ORDER BY ordinal_position", [target])
    n = cur.execute(f"SELECT COUNT(*) FROM {q(target)}").fetchone()[0]
    cur.execute("DELETE FROM user_tables WHERE table_name = ?", [target])
    cur.execute("INSERT INTO user_tables VALUES (?, ?, ?, ?, ?, now(), now())", [target, label[:80], source, n, json.dumps(meta)])
    return n


def dedupe_apply(source: str, keys: list[str], new_table: str, keep: str = "first", order_col: str | None = None) -> dict:
    t = _table(source)
    cs = _check_keys(t, keys)
    if keep not in ("first", "last", "newest", "oldest"):
        raise DeError("keep must be first, last, newest or oldest.")
    if keep in ("newest", "oldest"):
        if not order_col or order_col not in cs:
            raise DeError("Choose a date or number column to decide which copy is newest.")
        order = f"{q(order_col)} {'DESC' if keep == 'newest' else 'ASC'} NULLS LAST"
    else:
        order = f"rowid {'ASC' if keep == 'first' else 'DESC'}"
    target = _new_name(new_table, t)
    k = ", ".join(_norm_expr(c, cs[c]) for c in keys)
    with get_cursor() as cur:
        before = cur.execute(f"SELECT COUNT(*) FROM {q(t)}").fetchone()[0]
        cur.execute("BEGIN")
        try:
            cur.execute(f"CREATE OR REPLACE TABLE {q(target)} AS SELECT * EXCLUDE (_rn) FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY {k} ORDER BY {order}) AS _rn FROM {q(t)}) WHERE _rn = 1")
            n = _register(cur, target, new_table.strip(), MARK[0] + t)
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
    return {"table": target, "rows_before": before, "rows_after": n, "removed": before - n, "undo": target,
            "message": f"Created {target} with {n:,} rows ({before - n:,} duplicates removed). {t} is untouched. Undo drops {target} only."}


def merge_preview(left: str, right: str, left_key: str, right_key: str, how: str = "left") -> dict:
    lt, rt = _table(left), _table(right)
    lc, rc = {c["name"]: c for c in _cols(lt)}, {c["name"]: c for c in _cols(rt)}
    if left_key not in lc or right_key not in rc:
        raise DeError("Pick a key column from each table.")
    if how not in ("left", "inner", "full"):
        raise DeError("how must be left, inner or full.")
    lk = _norm_expr(left_key, _kind(lc[left_key]["type"]))
    rk = _norm_expr(right_key, _kind(rc[right_key]["type"]))
    with get_cursor() as cur:
        ln = cur.execute(f"SELECT COUNT(*) FROM {q(lt)}").fetchone()[0]
        rn = cur.execute(f"SELECT COUNT(*) FROM {q(rt)}").fetchone()[0]
        rdup = cur.execute(f"SELECT COUNT(*) FROM (SELECT {rk} FROM {q(rt)} GROUP BY 1 HAVING COUNT(*) > 1)").fetchone()[0]
        ldup = cur.execute(f"SELECT COUNT(*) FROM (SELECT {lk} FROM {q(lt)} GROUP BY 1 HAVING COUNT(*) > 1)").fetchone()[0]
        res = cur.execute(f"SELECT COUNT(*), COUNT(*) FILTER (WHERE l.k IS NOT NULL AND r.k IS NOT NULL) FROM (SELECT {lk} k FROM {q(lt)}) l {'FULL' if how == 'full' else 'LEFT' if how == 'left' else 'INNER'} JOIN (SELECT {rk} k FROM {q(rt)}) r ON l.k = r.k").fetchone()
        l_only = cur.execute(f"SELECT COUNT(*) FROM {q(lt)} WHERE {lk} NOT IN (SELECT {rk} FROM {q(rt)} WHERE {rk} IS NOT NULL)").fetchone()[0]
    out_rows, matched = int(res[0]), int(res[1])
    warn = []
    if rdup or ldup:
        warn.append(f"Join explosion risk: {'the right table repeats ' + str(rdup) + ' key value(s)' if rdup else ''}{' and ' if rdup and ldup else ''}{'the left table repeats ' + str(ldup) if ldup else ''}. "
                    "Each repeat multiplies rows, so totals can double count.")
    if how == "left" and out_rows > ln:
        warn.append(f"A left join should keep {ln} rows but would produce {out_rows}.")
    if matched == 0:
        warn.append("No keys match at all. Check that both columns hold the same kind of ID (spaces, leading zeros, capital letters).")
    return {"left": lt, "right": rt, "how": how, "left_rows": ln, "right_rows": rn, "result_rows": out_rows, "matched": matched, "left_without_match": int(l_only),
            "explosion": bool(warn and (rdup or ldup)), "warnings": warn,
            "says": f"Result would have {out_rows:,} rows. {matched:,} matched; {int(l_only):,} left rows have no partner."}


def merge_apply(left: str, right: str, left_key: str, right_key: str, new_table: str, how: str = "left", allow_multiply: bool = False) -> dict:
    p = merge_preview(left, right, left_key, right_key, how)
    if p["explosion"] and not allow_multiply:
        raise DeError("This join would repeat rows (duplicate keys). Dedupe the repeating table first, or confirm that multiplying is what you want. " + " ".join(p["warnings"]))
    lt, rt = p["left"], p["right"]
    target = _new_name(new_table, lt)
    if target == rt:
        raise DeError("The new table needs a different name from both inputs.")
    lcols, rcols = [c["name"] for c in _cols(lt)], [c["name"] for c in _cols(rt)]
    lc = {c["name"]: c for c in _cols(lt)}
    rc = {c["name"]: c for c in _cols(rt)}
    sel = [f"l.{q(c)}" for c in lcols]
    for c in rcols:
        if c == right_key and right_key == left_key:
            continue
        sel.append(f"r.{q(c)} AS {q(c + '_right' if c in lcols else c)}")
    lk = _norm_expr(left_key, _kind(lc[left_key]["type"]))
    rk = _norm_expr(right_key, _kind(rc[right_key]["type"]))
    j = {"left": "LEFT", "inner": "INNER", "full": "FULL"}[how]
    with get_cursor() as cur:
        cur.execute("BEGIN")
        try:
            cur.execute(f"CREATE OR REPLACE TABLE {q(target)} AS SELECT {', '.join(sel)} FROM (SELECT *, {lk} AS _k FROM {q(lt)}) l {j} JOIN (SELECT *, {rk} AS _k FROM {q(rt)}) r ON l._k = r._k")
            n = _register(cur, target, new_table.strip(), f"{MARK[1]}{lt} + {rt}")
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
    return {"table": target, "rows": n, "undo": target, "message": f"Created {target} with {n:,} rows. {lt} and {rt} are untouched. Undo drops {target} only."}


def undo(table: str) -> dict:
    datasets.ensure_registry()
    with get_cursor() as cur:
        r = cur.execute("SELECT source FROM user_tables WHERE table_name = ?", [table]).fetchone()
    if not r or not str(r[0]).startswith(MARK):
        raise DeError("Undo only removes tables made by Dedupe or Merge here.", 404)
    datasets.delete_table(table)
    return {"dropped": table, "message": f"Dropped {table}. The original tables were never changed."}


def made_tables() -> list[dict]:
    return [{"table": t["table_name"], "label": t["label"], "source": t["source"], "rows": t["rows_count"], "created": t["created_at"]} for t in datasets.list_tables() if str(t["source"]).startswith(MARK)]


# ------------------------------------------------------------------ 3. data contracts

def contract_propose(source: str) -> dict:
    t = _table(source)
    out = []
    with get_cursor() as cur:
        n = cur.execute(f"SELECT COUNT(*) FROM {q(t)}").fetchone()[0]
        for c in _cols(t):
            col, k = q(c["name"]), _kind(c["type"])
            nulls = cur.execute(f"SELECT COUNT(*) FROM {q(t)} WHERE {col} IS NULL").fetchone()[0]
            e = {"name": c["name"], "kind": k, "nullable": nulls > 0}
            if n and cur.execute(f"SELECT COUNT(DISTINCT {col}) FROM {q(t)}").fetchone()[0] == n - nulls and n - nulls > 1 and k != "bool":
                e["unique"] = True
            if k == "number":
                lo, hi = cur.execute(f"SELECT MIN({col}), MAX({col}) FROM {q(t)}").fetchone()
                if lo is not None:
                    e["min"], e["max"] = float(lo), float(hi)
            elif k == "text":
                vals = [r[0] for r in cur.execute(f"SELECT DISTINCT {col} FROM {q(t)} WHERE {col} IS NOT NULL LIMIT 9").fetchall()]
                if 0 < len(vals) <= 8 and n >= 20:
                    e["allowed"] = sorted(str(v) for v in vals)
            out.append(e)
    return {"table": t, "columns": out, "note": "This is a starting point built from the data as it is now. Loosen ranges and allowed values before you save: today's min and max are not rules."}


def _clean_contract(cols: list[dict]) -> list[dict]:
    if not isinstance(cols, list) or not cols:
        raise DeError("A contract needs at least one column.")
    out = []
    for c in cols[:200]:
        nm = str(c.get("name") or "").strip()
        if not nm:
            raise DeError("Every column needs a name.")
        e = {"name": nm, "kind": c.get("kind") if c.get("kind") in ("text", "number", "date", "bool") else "text", "nullable": bool(c.get("nullable", True)), "unique": bool(c.get("unique", False))}
        for k in ("min", "max"):
            if c.get(k) not in (None, ""):
                try:
                    e[k] = float(c[k])
                except (TypeError, ValueError):
                    raise DeError(f"{k} for '{nm}' must be a number.") from None
        if isinstance(c.get("allowed"), list) and c["allowed"]:
            e["allowed"] = [str(a)[:80] for a in c["allowed"][:50]]
        out.append(e)
    return out


def contract_save(source: str, columns: list[dict], owner: str = "") -> dict:
    t = _table(source)
    d = _kv("contracts")
    d[t] = {"columns": _clean_contract(columns), "owner": owner[:80], "saved": time.strftime("%Y-%m-%d %H:%M")}
    _kv_set("contracts", d)
    return {"table": t, "columns": len(d[t]["columns"]), "saved": d[t]["saved"]}


def contract_get(source: str) -> dict | None:
    return _kv("contracts").get(_table(source))


def contract_delete(source: str) -> dict:
    t = _table(source)
    d = _kv("contracts")
    d.pop(t, None)
    _kv_set("contracts", d)
    return {"deleted": t}


def contract_list() -> list[dict]:
    return [{"table": t, "columns": len(c["columns"]), "owner": c.get("owner", ""), "saved": c["saved"], "last": (c.get("last") or {}).get("status")} for t, c in _kv("contracts").items()]


def contract_check(source: str) -> dict:
    t = _table(source)
    d = _kv("contracts")
    c = d.get(t)
    if not c:
        raise DeError("No contract saved for this table yet.", 404)
    live = {x["name"]: x for x in _cols(t)}
    issues = []

    def add(col, rule, msg, n=None, ex=None):
        issues.append({"column": col, "rule": rule, "says": msg, "rows": n, "examples": ex or []})

    with get_cursor() as cur:
        for e in c["columns"]:
            nm = e["name"]
            if nm not in live:
                add(nm, "present", f"Column '{nm}' is missing.")
                continue
            k, col = _kind(live[nm]["type"]), q(nm)
            if k != e["kind"] and not (e["kind"] == "number" and k == "number"):
                add(nm, "type", f"Expected {e['kind']} but the column is {live[nm]['type']}.")
                continue
            if not e["nullable"]:
                n = cur.execute(f"SELECT COUNT(*) FROM {q(t)} WHERE {col} IS NULL").fetchone()[0]
                if n:
                    add(nm, "not_blank", f"{n} blank value(s) where blanks are not allowed.", n)
            if e["unique"]:
                n = cur.execute(f"SELECT COALESCE(SUM(c - 1), 0) FROM (SELECT COUNT(*) c FROM {q(t)} WHERE {col} IS NOT NULL GROUP BY {col} HAVING COUNT(*) > 1)").fetchone()[0]
                if n:
                    ex = [str(r[0]) for r in cur.execute(f"SELECT {col} FROM {q(t)} GROUP BY {col} HAVING COUNT(*) > 1 LIMIT 3").fetchall()]
                    add(nm, "unique", f"{int(n)} repeated value(s) in a column that must be unique.", int(n), ex)
            if k == "number" and ("min" in e or "max" in e):
                conds = []
                if "min" in e:
                    conds.append(f"{col} < {float(e['min'])!r}")
                if "max" in e:
                    conds.append(f"{col} > {float(e['max'])!r}")
                where = " OR ".join(conds)
                n = cur.execute(f"SELECT COUNT(*) FROM {q(t)} WHERE {where}").fetchone()[0]
                if n:
                    ex = [str(r[0]) for r in cur.execute(f"SELECT {col} FROM {q(t)} WHERE {where} LIMIT 3").fetchall()]
                    add(nm, "range", f"{n} value(s) outside {e.get('min', '-inf'):g} to {e.get('max', 'inf'):g}." if "min" in e and "max" in e else f"{n} value(s) outside the allowed range.", n, ex)
            if k == "text" and e.get("allowed"):
                ph = ", ".join("?" for _ in e["allowed"])
                n = cur.execute(f"SELECT COUNT(*) FROM {q(t)} WHERE {col} IS NOT NULL AND CAST({col} AS VARCHAR) NOT IN ({ph})", e["allowed"]).fetchone()[0]
                if n:
                    ex = [str(r[0]) for r in cur.execute(f"SELECT DISTINCT {col} FROM {q(t)} WHERE {col} IS NOT NULL AND CAST({col} AS VARCHAR) NOT IN ({ph}) LIMIT 3", e["allowed"]).fetchall()]
                    add(nm, "allowed", f"{n} value(s) not in the allowed list.", n, ex)
    extra = [n for n in live if n not in {e["name"] for e in c["columns"]}]
    status = "fail" if issues else "pass"
    res = {"table": t, "status": status, "checked": len(c["columns"]), "issues": issues, "extra_columns": extra, "at": time.strftime("%Y-%m-%d %H:%M"),
           "says": "Data meets the contract." if status == "pass" else f"{len(issues)} rule(s) broken. Fix the source or change the contract on purpose."}
    c["last"] = {"status": status, "at": res["at"], "issues": len(issues)}
    _kv_set("contracts", d)
    return res


def contract_check_all() -> list[dict]:
    out = []
    for t in list(_kv("contracts")):
        try:
            r = contract_check(t)
            out.append({"table": t, "status": r["status"], "issues": len(r["issues"])})
        except Exception as e:   # a dropped table must not stop the others
            out.append({"table": t, "status": "error", "issues": 0, "why": str(e)[:120]})
    return out


_last_all = [0.0]


def contract_check_due(every_s: int = 900) -> list[dict]:
    """Called by the scheduler tick: re-check all contracts at most every 15 minutes."""
    if time.time() - _last_all[0] < every_s:
        return []
    _last_all[0] = time.time()
    return contract_check_all()


def contract_markdown(source: str) -> str:
    c = contract_get(source)
    if not c:
        raise DeError("No contract saved for this table yet.", 404)
    t = _table(source)
    rows = []
    for e in c["columns"]:
        rule = [e["kind"], "required" if not e["nullable"] else "may be blank"]
        if e["unique"]:
            rule.append("unique")
        if "min" in e or "max" in e:
            rule.append(f"{e.get('min', '')}..{e.get('max', '')}")
        if e.get("allowed"):
            rule.append("one of " + ", ".join(e["allowed"]))
        rows.append(f"| {e['name']} | " + "; ".join(rule) + " |")
    return f"# Data contract: {t}\n\nOwner: {c.get('owner') or 'not set'} · saved {c['saved']}\n\n| Column | Rule |\n|---|---|\n" + "\n".join(rows) + "\n"


# ------------------------------------------------------------------ 4. volume cost and speed estimator

def estimate(rows_per_day: float, columns: int = 20, avg_value_bytes: int = 12, retention_months: int = 12, loads_per_day: int = 1, ram_gb: float = 16, history_rows: float = 0) -> dict:
    try:
        rpd, cols, ab, ret, lpd, ram = float(rows_per_day), int(columns), int(avg_value_bytes), int(retention_months), int(loads_per_day), float(ram_gb)
    except (TypeError, ValueError):
        raise DeError("All inputs must be numbers.") from None
    if rpd <= 0 or not 1 <= cols <= 2000 or not 1 <= ret <= 240 or not 1 <= lpd <= 1440 or ram <= 0:
        raise DeError("Check the inputs: rows per day above 0, columns 1-2000, months 1-240, loads per day 1-1440.")
    total = float(history_rows) + rpd * 30.4 * ret
    raw_gb = total * cols * ab / 1e9
    db_gb = raw_gb * 0.3                        # columnar compression, typical 3-5x for business data
    mem_gb = total * cols * 8 * 3 / 1e9          # a dataframe copy plus working copies
    per_load = rpd / lpd
    # speed: loading and a typical group-by, as ranges because hardware varies
    load_s = (per_load / 200_000, per_load / 50_000)
    scan_s = (total / 50_000_000, total / 5_000_000)
    notes, tier = [], "laptop"
    if total > 1_048_576:
        notes.append("Past 1,048,576 rows Excel cannot open it. Use the dashboard, DuckDB or a database.")
    if mem_gb > ram * 0.5:
        notes.append(f"Loading everything at once into pandas needs about {mem_gb:.1f} GB, more than half of {ram:g} GB of RAM. Query in the database and pull only summaries.")
        tier = "database"
    if total > 2e9 or db_gb > 400:
        tier = "warehouse"
        notes.append("This is beyond what one laptop disk handles comfortably. A hosted warehouse or a partitioned file layout is the sensible next step.")
    elif total > 5e7 and tier == "laptop":
        tier = "database"
    rec = {"laptop": "A single DuckDB file on a laptop is fine at this size.", "database": "Keep it in DuckDB or Postgres on a computer with good disk and RAM, and avoid loading full tables into memory.",
           "warehouse": "Plan a warehouse or partitioned Parquet storage."}[tier]
    return {"total_rows": int(total), "storage_raw_gb": round(raw_gb, 3), "storage_db_gb": round(db_gb, 3), "memory_if_loaded_gb": round(mem_gb, 2), "rows_per_load": int(per_load),
            "load_seconds_range": [round(load_s[0], 2), round(load_s[1], 2)], "full_scan_seconds_range": [round(scan_s[0], 2), round(scan_s[1], 2)], "tier": tier, "recommendation": rec, "notes": notes,
            "assumptions": [f"{ab} bytes per value on average", "database file is about 30% of raw size (compression)", "a loaded dataframe is about 3 copies of 8-byte values", "speeds are ranges for a typical laptop: loading 50k-200k rows/s, scanning 5M-50M rows/s"],
            "caution": "Treat every number as within about 3x either way. Test with a real sample of your data before promising speed or cost to a client."}
