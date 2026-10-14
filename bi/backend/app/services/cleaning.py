"""Data cleaning for imported tables: inspect, clean into a NEW table, verify, and keep a log.

The original table is never changed. Each step is one of a small set of whitelisted operations, built as SQL with bound values.
Cleaning is a subset of wrangling: it fixes missing values, duplicates, wrong types, inconsistent text and outliers, and the
reasons are written down (a Wrangling note is saved automatically).
"""
from __future__ import annotations

import json

from app.services import datasets, qual
from app.services.datasets import DataError, q
from app.services.db import fetch_all, get_cursor

MAX_STEPS = 15
OPS = ("add_feature", "set_missing", "group_rare", "dedupe", "trim", "lower", "upper", "drop_missing", "fill_missing", "convert", "drop_column", "remove_outliers", "standardize", "strip_chars", "split_text", "replace_text")


def _cols(table: str) -> dict[str, str]:
    return {c["name"]: datasets.kind_of(c["type"]) for c in datasets.table_columns(table)}


def inspect(table: str) -> dict:
    cols = _cols(table)
    t = q(table)
    out, issues = [], []
    with get_cursor() as cur:
        total = cur.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        distinct_rows = cur.execute(f"SELECT COUNT(*) FROM (SELECT DISTINCT * FROM {t})").fetchone()[0] if total else 0
        dups = total - distinct_rows
        for name, kind in cols.items():
            c = q(name)
            nulls = cur.execute(f"SELECT COUNT(*) - COUNT({c}) FROM {t}").fetchone()[0]
            item = {"name": name, "kind": kind, "missing": nulls, "missing_pct": round(nulls / total * 100, 1) if total else 0, "problems": []}
            if kind == "text":
                spaces = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {c} IS NOT NULL AND CAST({c} AS VARCHAR) <> trim(CAST({c} AS VARCHAR))").fetchone()[0]
                d_raw, d_norm = cur.execute(f"SELECT COUNT(DISTINCT {c}), COUNT(DISTINCT lower(trim(CAST({c} AS VARCHAR)))) FROM {t}").fetchone()
                nn = total - nulls
                as_num = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {c} IS NOT NULL AND TRY_CAST(trim({c}) AS DOUBLE) IS NOT NULL").fetchone()[0]
                as_date = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {c} IS NOT NULL AND TRY_CAST(trim({c}) AS DATE) IS NOT NULL").fetchone()[0]
                if 15 < d_raw <= nn * 0.5 and nn >= 30:
                    item["problems"].append({"kind": "many_levels", "count": d_raw, "detail": f"{d_raw:,} different values: too many to be informative as they are. Group the rare ones into 'Other'."})
                if spaces:
                    item["problems"].append({"kind": "spaces", "count": spaces, "detail": f"{spaces:,} value(s) have extra spaces at the start or end."})
                if d_raw > d_norm:
                    item["problems"].append({"kind": "case", "count": d_raw - d_norm, "detail": f"{d_raw - d_norm} value(s) differ only by capital letters or spaces (e.g. 'ny' and 'NY')."})
                if nn and as_num == nn:
                    item["problems"].append({"kind": "number_as_text", "count": nn, "detail": "Every value looks like a number but is stored as text."})
                elif nn and as_date == nn:
                    item["problems"].append({"kind": "date_as_text", "count": nn, "detail": "Every value looks like a date but is stored as text."})
            elif kind == "number" and total - nulls >= 8:
                mx, mn = cur.execute(f"SELECT MAX({c}), MIN({c}) FROM {t}").fetchone()
                for sv, edge in ((mx, "high"), (mn, "low")):
                    if sv in (99, 999, 9999, 99999, -1, -99, -999, -9999):
                        k2 = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {c} = ?", [sv]).fetchone()[0]
                        nxt = cur.execute(f"SELECT {'MAX' if edge == 'high' else 'MIN'}({c}) FROM {t} WHERE {c} <> ?", [sv]).fetchone()[0]
                        if k2 and nxt is not None and abs(sv) > 2 * abs(nxt if nxt else 1) and k2 / max(1, total - nulls) < 0.5:
                            item["problems"].append({"kind": "placeholder", "count": k2, "value": sv, "detail": f"{k2:,} row(s) hold {sv:g}, far from the rest ({nxt:g} is the next {edge}est). That is often a code for 'missing', not a real value."})
                q1, q3 = cur.execute(f"SELECT quantile_cont({c}, 0.25), quantile_cont({c}, 0.75) FROM {t}").fetchone()
                if q1 is not None and q3 is not None and q3 > q1:
                    lo, hi = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
                    n_out = cur.execute(f"SELECT COUNT(*) FROM {t} WHERE {c} < ? OR {c} > ?", [lo, hi]).fetchone()[0]
                    if n_out:
                        item["problems"].append({"kind": "outliers", "count": n_out, "detail": f"{n_out:,} value(s) outside {lo:,.4g} to {hi:,.4g} (the usual 1.5 x IQR fence). Outliers may be real: look before removing."})
            if nulls:
                item["problems"].append({"kind": "missing", "count": nulls, "detail": f"{nulls:,} missing ({item['missing_pct']}%)."})
            out.append(item)
    if dups:
        issues.append({"kind": "duplicates", "detail": f"{dups:,} exact duplicate row(s)."})
    for it in out:
        for p in it["problems"]:
            issues.append({"kind": p["kind"], "column": it["name"], "detail": p["detail"], **({"value": p["value"]} if "value" in p else {})})
    score = max(0, 100 - min(100, (dups / total * 100 if total else 0) + sum(i["missing_pct"] for i in out) / max(1, len(out)) + 5 * sum(1 for i in issues if i["kind"] in ("spaces", "case", "number_as_text", "date_as_text"))))
    return {"table": table, "rows": total, "duplicate_rows": dups, "columns": out, "issues": issues, "health": round(score), "clean": not issues,
            "lesson": ("Inspect first, then clean, then verify. Fix what the problem needs: filter out missing rows, source the data, or impute (fill with a statistic). "
                       "Whatever you choose, write down what you changed and why, and re-inspect afterwards so the rules still hold.")}


def _need(cols: dict[str, str], name, kinds: tuple[str, ...] | None = None) -> str:
    if not isinstance(name, str) or name not in cols:
        raise DataError(f"'{name}' isn't a column of this table.")
    if kinds and cols[name] not in kinds:
        raise DataError(f"'{name}' is {cols[name]}; this step needs {' or '.join(kinds)}.")
    return name


def _step_sql(cols: dict[str, str], prev: str, s: dict, idx: int) -> tuple[str, list, str, dict[str, str]]:
    """Return (select sql from prev, params, human text, new column kinds)."""
    op = s.get("op")
    if op not in OPS:
        raise DataError(f"Step {idx}: unknown operation.")
    allc = ", ".join(q(c) for c in cols)
    new = dict(cols)
    if op == "add_feature":
        # feature engineering: a new column built from existing ones, using what you know about the business
        how = s.get("how")
        name = str(s.get("name") or "").strip()[:60]
        if not name or name in cols:
            raise DataError(f"Step {idx}: give the new column a name that isn't already used.")
        if how in ("ratio", "difference", "product"):
            a, b = _need(cols, s.get("a"), ("number",)), _need(cols, s.get("b"), ("number",))
            expr = {"ratio": f"{q(a)} / NULLIF({q(b)}, 0)", "difference": f"{q(a)} - {q(b)}", "product": f"{q(a)} * {q(b)}"}[how]
            text, kind = f"Added {name} = {a} {'/' if how == 'ratio' else '-' if how == 'difference' else '*'} {b}.", "number"
        elif how == "date_part":
            a, part = _need(cols, s.get("a"), ("date",)), s.get("part")
            if part not in ("year", "month", "quarter", "dayofweek", "week"):
                raise DataError(f"Step {idx}: part must be year, month, quarter, dayofweek or week.")
            expr, text, kind = f"CAST(date_part('{part}', {q(a)}) AS INTEGER)", f"Added {name} = the {part} of {a}.", "number"
        elif how == "repeat_within":
            # an outcome to predict: does the SAME entity come back within N days of this record? (readmission, repeat purchase, re-contact)
            ent_c, a = _need(cols, s.get("entity")), _need(cols, s.get("a"), ("date",))
            try:
                days = int(s.get("days", 30))
            except (TypeError, ValueError) as e:
                raise DataError(f"Step {idx}: days must be a whole number.") from e
            if not 1 <= days <= 3650:
                raise DataError(f"Step {idx}: days must be between 1 and 3650.")
            nxt = f"LEAD({q(a)}) OVER (PARTITION BY {q(ent_c)} ORDER BY {q(a)})"
            expr = f"CASE WHEN {nxt} IS NULL THEN 0 WHEN date_diff('day', CAST({q(a)} AS DATE), CAST({nxt} AS DATE)) <= {days} THEN 1 ELSE 0 END"
            text, kind = f"Added {name} = 1 when the same {ent_c} has another record within {days} days after this one, else 0 (a yes/no outcome to predict).", "number"
        elif how == "before_after":
            # impact without a control group: label every record 'before' or 'after' a launch date, then compare the two periods
            a = _need(cols, s.get("a"), ("date",))
            cut = str(s.get("cutoff") or "")
            from datetime import date as _d
            try:
                _d.fromisoformat(cut)
            except ValueError as e:
                raise DataError(f"Step {idx}: give the launch date as YYYY-MM-DD.") from e
            expr, text, kind = f"CASE WHEN {q(a)} IS NULL THEN NULL WHEN CAST({q(a)} AS DATE) < DATE '{cut}' THEN 'before' ELSE 'after' END", f"Added {name} = 'before' or 'after' {cut} (compare the two with Compare groups).", "text"
        elif how == "zscore":
            a = _need(cols, s.get("a"), ("number",))
            expr, text, kind = f"({q(a)} - AVG({q(a)}) OVER ()) / NULLIF(STDDEV_SAMP({q(a)}) OVER (), 0)", f"Added {name} = the z-score of {a}: how many standard deviations each value is from the average (mean 0, standard deviation 1).", "number"
        elif how == "log":
            a = _need(cols, s.get("a"), ("number",))
            expr, text, kind = f"CASE WHEN {q(a)} > 0 THEN ln({q(a)}) END", f"Added {name} = natural log of {a} (positive values only; tames a long right tail).", "number"
        elif how == "bucket":
            a = _need(cols, s.get("a"), ("number",))
            try:
                n = int(s.get("bins", 4))
            except (TypeError, ValueError) as e:
                raise DataError(f"Step {idx}: bins must be a whole number.") from e
            if not 2 <= n <= 10:
                raise DataError(f"Step {idx}: use 2 to 10 groups.")
            expr, text, kind = f"CASE WHEN {q(a)} IS NULL THEN NULL ELSE 'G' || CAST(ntile({n}) OVER (ORDER BY {q(a)}) AS VARCHAR) END", f"Added {name} = {a} sorted into {n} equal-size groups (G1 lowest).", "text"
        elif how == "flag":
            a, o = _need(cols, s.get("a"), ("number",)), s.get("op2")
            if o not in ("gt", "gte", "lt", "lte", "eq"):
                raise DataError(f"Step {idx}: condition must be gt, gte, lt, lte or eq.")
            try:
                v = float(s.get("value"))
            except (TypeError, ValueError) as e:
                raise DataError(f"Step {idx}: give a number to compare against.") from e
            sym = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "eq": "="}[o]
            expr, text, kind = f"CASE WHEN {q(a)} IS NULL THEN NULL WHEN {q(a)} {sym} {v!r} THEN 1 ELSE 0 END", f"Added {name} = 1 when {a} {sym} {v:g}, else 0.", "number"
        else:
            raise DataError(f"Step {idx}: how must be ratio, difference, product, date_part, log, bucket, flag, zscore, repeat_within or before_after.")
        new[name] = kind
        return f"SELECT *, {expr} AS {q(name)} FROM {prev}", [], text, new
    if op == "set_missing":
        c = _need(cols, s.get("column"), ("number", "text"))
        try:
            v = float(s.get("value")) if cols[c] == "number" else str(s.get("value"))
        except (TypeError, ValueError) as e:
            raise DataError(f"Step {idx}: give the placeholder value to treat as missing.") from e
        sel = ", ".join(f"NULLIF({q(c)}, ?) AS {q(c)}" if x == c else q(x) for x in cols)
        return f"SELECT {sel} FROM {prev}", [v], f"Treated {v:g} in {c} as missing (it was a placeholder)." if cols[c] == "number" else f"Treated '{v}' in {c} as missing.", new
    if op == "group_rare":
        c = _need(cols, s.get("column"), ("text",))
        try:
            share = float(s.get("min_share", 0.02))
        except (TypeError, ValueError) as e:
            raise DataError(f"Step {idx}: min_share must be a number.") from e
        if not 0 < share < 0.5:
            raise DataError(f"Step {idx}: min_share must be between 0 and 0.5.")
        col = q(c)
        keep = f"(SELECT {col} FROM {prev} WHERE {col} IS NOT NULL GROUP BY {col} HAVING COUNT(*) >= {share} * (SELECT COUNT({col}) FROM {prev}))"
        sel = ", ".join(f"CASE WHEN {col} IS NULL OR {col} IN {keep} THEN {col} ELSE 'Other' END AS {col}" if x == c else q(x) for x in cols)
        return f"SELECT {sel} FROM {prev}", [], f"Grouped values of {c} that are under {share:.0%} of rows into 'Other'.", new
    if op == "dedupe":
        return f"SELECT DISTINCT * FROM {prev}", [], "Removed exact duplicate rows.", new
    if op in ("trim", "lower", "upper"):
        targets = [c for c, k in cols.items() if k == "text"] if not s.get("column") else [_need(cols, s["column"], ("text",))]
        if not targets:
            raise DataError(f"Step {idx}: there are no text columns.")
        fn = {"trim": "trim", "lower": "lower", "upper": "upper"}[op]
        sel = ", ".join(f"{fn}(CAST({q(c)} AS VARCHAR)) AS {q(c)}" if c in targets else q(c) for c in cols)
        word = {"trim": "Trimmed spaces in", "lower": "Made lower case:", "upper": "Made upper case:"}[op]
        return f"SELECT {sel} FROM {prev}", [], f"{word} {', '.join(targets)}.", new
    if op == "drop_missing":
        cs = s.get("columns") or []
        if not isinstance(cs, list) or not cs:
            raise DataError(f"Step {idx}: pick at least one column.")
        for c in cs:
            _need(cols, c)
        cond = " AND ".join(f"{q(c)} IS NOT NULL" for c in cs)
        return f"SELECT * FROM {prev} WHERE {cond}", [], f"Removed rows with a missing value in {', '.join(cs)}.", new
    if op == "fill_missing":
        c = _need(cols, s.get("column"))
        m = s.get("method")
        col = q(c)
        if m in ("mean", "median"):
            _need(cols, c, ("number",))
            stat = "AVG" if m == "mean" else "MEDIAN"
            fill, params = f"(SELECT {stat}({col}) FROM {prev})", []
            what = f"the {m}"
        elif m == "mode":
            fill, params = f"(SELECT {col} FROM {prev} WHERE {col} IS NOT NULL GROUP BY {col} ORDER BY COUNT(*) DESC, {col} LIMIT 1)", []
            what = "the most common value"
        elif m == "value":
            v = s.get("value")
            if v is None or str(v).strip() == "":
                raise DataError(f"Step {idx}: give the value to fill with.")
            if cols[c] == "number":
                try:
                    v = float(v)
                except (TypeError, ValueError) as e:
                    raise DataError(f"Step {idx}: '{c}' is a number column; the fill value must be a number.") from e
                fill, params = "?", [v]
            elif cols[c] == "text":
                fill, params = "?", [str(v)[:200]]
            else:
                raise DataError(f"Step {idx}: filling with a fixed value works on number and text columns.")
            what = f"'{v}'"
        else:
            raise DataError(f"Step {idx}: method must be mean, median, mode or value.")
        sel = ", ".join(f"COALESCE({col}, {fill}) AS {col}" if x == c else q(x) for x in cols)
        return f"SELECT {sel} FROM {prev}", params, f"Filled missing {c} with {what} (imputation).", new
    if op == "convert":
        c = _need(cols, s.get("column"))
        to = s.get("to")
        if to not in ("number", "date", "text"):
            raise DataError(f"Step {idx}: convert to number, date or text.")
        ty = {"number": "DOUBLE", "date": "DATE", "text": "VARCHAR"}[to]
        expr = f"TRY_CAST(trim(CAST({q(c)} AS VARCHAR)) AS {ty})" if to != "text" else f"CAST({q(c)} AS VARCHAR)"
        sel = ", ".join(f"{expr} AS {q(c)}" if x == c else q(x) for x in cols)
        new[c] = to
        return f"SELECT {sel} FROM {prev}", [], f"Converted {c} to {to}; values that can't convert become missing.", new
    if op == "drop_column":
        c = _need(cols, s.get("column"))
        if len(cols) == 1:
            raise DataError(f"Step {idx}: can't drop the only column.")
        new.pop(c)
        return f"SELECT {', '.join(q(x) for x in new)} FROM {prev}", [], f"Dropped column {c} (not relevant to the use case).", new
    if op == "remove_outliers":
        c = _need(cols, s.get("column"), ("number",))
        col = q(c)
        sql = (f"SELECT * FROM {prev}, (SELECT quantile_cont({col}, 0.25) AS _q1, quantile_cont({col}, 0.75) AS _q3 FROM {prev}) _b "
               f"WHERE {col} IS NULL OR _q3 = _q1 OR ({col} >= _q1 - 1.5 * (_q3 - _q1) AND {col} <= _q3 + 1.5 * (_q3 - _q1))")
        return f"SELECT {allc} FROM ({sql})", [], f"Removed outliers in {c} (outside 1.5 x IQR).", new
    if op == "strip_chars":
        c = _need(cols, s.get("column"), ("text",))
        keep = s.get("keep")
        pat = {"digits": "[^0-9]", "letters_digits": "[^a-zA-Z0-9]", "letters_digits_spaces": "[^a-zA-Z0-9 ]"}.get(keep)
        if not pat:
            raise DataError(f"Step {idx}: keep must be digits, letters_digits or letters_digits_spaces.")
        # 'g' is needed in DuckDB: without it only the FIRST match is replaced (a common trap when copying MySQL recipes)
        expr = f"regexp_replace(CAST({q(c)} AS VARCHAR), '{pat}', '', 'g')"
        sel = ", ".join(f"{expr} AS {q(c)}" if x == c else q(x) for x in cols)
        what = {"digits": "digits only", "letters_digits": "letters and digits only", "letters_digits_spaces": "letters, digits and spaces only"}[keep]
        return f"SELECT {sel} FROM {prev}", [], f"Stripped {c} down to {what}.", new
    if op == "split_text":
        c = _need(cols, s.get("column"), ("text",))
        ch = {"space": " ", "comma": ",", "semicolon": ";", "pipe": "|", "dash": "-", "slash": "/", "underscore": "_", "at": "@"}.get(s.get("delimiter", "space"))
        if ch is None:
            raise DataError(f"Step {idx}: pick a delimiter from the list.")
        a, b = (str(x).strip()[:60] for x in (s.get("names") or ["", ""])[:2])
        if not a or not b or a == b or a in cols or b in cols:
            raise DataError(f"Step {idx}: give two different names for the new columns that aren't already used.")
        col = f"CAST({q(c)} AS VARCHAR)"
        new[a] = new[b] = "text"
        extra = (f"trim(split_part({col}, '{ch}', 1)) AS {q(a)}, "
                 f"CASE WHEN strpos({col}, '{ch}') = 0 THEN NULL ELSE trim(substr({col}, strpos({col}, '{ch}') + 1)) END AS {q(b)}")
        return f"SELECT {allc}, {extra} FROM {prev}", [], f"Split {c} at the first {s.get('delimiter', 'space')} into {a} and {b} (everything after the first {s.get('delimiter', 'space')} goes in {b}).", new
    if op == "replace_text":
        c = _need(cols, s.get("column"), ("text",))
        find, rep = str(s.get("find") or ""), str(s.get("with") if s.get("with") is not None else "")
        if not find:
            raise DataError(f"Step {idx}: say what text to find.")
        expr = f"replace(CAST({q(c)} AS VARCHAR), ?, ?)"
        sel = ", ".join(f"{expr} AS {q(c)}" if x == c else q(x) for x in cols)
        return f"SELECT {sel} FROM {prev}", [find[:200], rep[:200]], f"Replaced '{find[:40]}' with '{rep[:40]}' in {c}.", new
    # standardize
    c = _need(cols, s.get("column"), ("text",))
    mp = s.get("mapping")
    if not isinstance(mp, dict) or not mp or len(mp) > 50:
        raise DataError(f"Step {idx}: give a mapping of old to new values (up to 50).")
    whens, params = [], []
    for old, nw in mp.items():
        whens.append("WHEN lower(trim(CAST({c} AS VARCHAR))) = lower(trim(?)) THEN ?".format(c=q(c)))
        params += [str(old)[:200], str(nw)[:200]]
    expr = f"CASE {' '.join(whens)} ELSE {q(c)} END"
    sel = ", ".join(f"{expr} AS {q(c)}" if x == c else q(x) for x in cols)
    return f"SELECT {sel} FROM {prev}", params, f"Standardized values in {c} ({len(mp)} mapping(s)).", new


def clean(table: str, new_table: str, steps: list[dict], note: str = "") -> dict:
    cols = _cols(table)
    if not isinstance(steps, list) or not steps:
        raise DataError("Add at least one cleaning step.")
    if len(steps) > MAX_STEPS:
        raise DataError(f"At most {MAX_STEPS} steps at a time.")
    target = datasets.table_name_for(new_table or "")
    if not (new_table or "").strip():
        raise DataError("Name the cleaned table.")
    if target == table:
        raise DataError("The cleaned copy needs a different name: the original is never changed.")
    prev, log, temps = q(table), [], []
    with get_cursor() as cur:
        before = cur.execute(f"SELECT COUNT(*) FROM {q(table)}").fetchone()[0]
        last = before
        try:
            for i, s in enumerate(steps, 1):
                sql, p, text, cols = _step_sql(cols, prev, s, i)
                tmp = f"_clean_step_{i}"
                cur.execute(f"CREATE OR REPLACE TEMP TABLE {tmp} AS {sql}", p)   # each step is materialized, so bound values stay in order
                temps.append(tmp)
                prev = tmp
                n = cur.execute(f"SELECT COUNT(*) FROM {tmp}").fetchone()[0]
                log.append({"step": i, "op": s["op"], "text": text, "rows_after": n, "rows_removed": last - n})
                last = n
            if last == 0:
                raise DataError("These steps would remove every row. Nothing was created.")
            datasets.ensure_registry()
            registered = cur.execute("SELECT 1 FROM user_tables WHERE table_name = ?", [target]).fetchone()
            exists = cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name = ?", [target]).fetchone()
            if exists and not registered:
                raise DataError(f"'{target}' is a built-in table. Pick another name.")
            cur.execute("BEGIN")
            try:
                cur.execute(f"CREATE OR REPLACE TABLE {q(target)} AS SELECT * FROM {prev}")
                meta = fetch_all(cur, "SELECT column_name AS name, data_type AS type FROM information_schema.columns WHERE table_schema='main' AND table_name = ? ORDER BY ordinal_position", [target])
                cur.execute("DELETE FROM user_tables WHERE table_name = ?", [target])
                cur.execute("INSERT INTO user_tables VALUES (?, ?, ?, ?, ?, now(), now())", [target, new_table.strip()[:80], f"cleaned from {table}", last, json.dumps(meta)])
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise
        finally:
            for t in temps:
                cur.execute(f"DROP TABLE IF EXISTS {t}")
    after = inspect(target)
    before_health = inspect(table)["health"]
    entry = qual.create("wrangle", f"Cleaned {table} into {target}", {
        "purpose": (note or "Cleaning for analysis")[:200], "raw_sources": [table],
        "cleaning": [f"{x['text']} ({x['rows_removed']:,} row(s) removed; {x['rows_after']:,} left)" if x["rows_removed"] else x["text"] for x in log],
        "validation": [f"Re-inspected: health {before_health} before, {after['health']} after; {len(after['issues'])} issue(s) left."],
        "published_as": target})
    return {"table": target, "rows_before": before, "rows_after": last, "log": log, "verification": after, "health_before": before_health,
            "health_after": after["health"], "note_id": entry["id"],
            "message": f"Created {target} ({last:,} rows) and saved the steps in your Wrangling log. {table} is untouched."}


# ------------------------------------------------------------------ roll up to one row per entity
MAX_ROLLUP_COLS = 30


def rollup(table: str, entity_col: str, new_table: str, cohort: list[dict] | None = None, mode: str = "and", note: str = "") -> dict:
    """Turn many records per entity (orders per customer, visits per patient) into ONE row per entity with summary columns.

    Many models (decision trees, clustering, regression) need one record per entity. An optional cohort filter keeps only the
    records you want first (the inclusion criteria). Creates a NEW table; the source is untouched.
    """
    from app.services import stats_lab as sl
    cols = _cols(table)
    ent = _need(cols, entity_col)
    target = datasets.table_name_for(new_table or "")
    if not (new_table or "").strip():
        raise DataError("Name the new table.")
    if target == table:
        raise DataError("The new table needs a different name: the original is never changed.")
    where, params, words = sl.where_clause(cols, cohort, mode)
    aggs, made = ["COUNT(*) AS records"], ["records (how many rows the entity had)"]
    used = [c for c in cols if c != ent][:MAX_ROLLUP_COLS]
    for c in used:
        k = cols[c]
        qc = q(c)
        if k == "number":
            aggs += [f"SUM({qc}) AS {q(c + '_sum')}", f"AVG({qc}) AS {q(c + '_avg')}", f"MIN({qc}) AS {q(c + '_min')}", f"MAX({qc}) AS {q(c + '_max')}"]
            made.append(f"{c}: sum, average, min, max")
        elif k == "date":
            aggs += [f"MIN({qc}) AS {q(c + '_first')}", f"MAX({qc}) AS {q(c + '_last')}"]
            made.append(f"{c}: first and last")
        elif k == "bool":
            aggs += [f"SUM(CASE WHEN {qc} THEN 1 ELSE 0 END) AS {q(c + '_true')}"]
            made.append(f"{c}: count of true")
        else:
            aggs += [f"COUNT(DISTINCT {qc}) AS {q(c + '_distinct')}"]
            made.append(f"{c}: number of different values")
    sql = f"SELECT {q(ent)}, {', '.join(aggs)} FROM {q(table)}{where} GROUP BY {q(ent)} HAVING {q(ent)} IS NOT NULL"
    with get_cursor() as cur:
        before = cur.execute(f"SELECT COUNT(*) FROM {q(table)}{where}", params).fetchone()[0]
        if before == 0:
            raise DataError("No records match the cohort filter. Nothing was created.")
        datasets.ensure_registry()
        registered = cur.execute("SELECT 1 FROM user_tables WHERE table_name = ?", [target]).fetchone()
        exists = cur.execute("SELECT 1 FROM information_schema.tables WHERE table_schema='main' AND table_name = ?", [target]).fetchone()
        if exists and not registered:
            raise DataError(f"'{target}' is a built-in table. Pick another name.")
        cur.execute("BEGIN")
        try:
            cur.execute(f"CREATE OR REPLACE TABLE {q(target)} AS {sql}", params)
            n = cur.execute(f"SELECT COUNT(*) FROM {q(target)}").fetchone()[0]
            meta = fetch_all(cur, "SELECT column_name AS name, data_type AS type FROM information_schema.columns WHERE table_schema='main' AND table_name = ? ORDER BY ordinal_position", [target])
            cur.execute("DELETE FROM user_tables WHERE table_name = ?", [target])
            cur.execute("INSERT INTO user_tables VALUES (?, ?, ?, ?, ?, now(), now())", [target, new_table.strip()[:80], f"one row per {entity_col} from {table}", n, json.dumps(meta)])
            cur.execute("COMMIT")
        except Exception:
            cur.execute("ROLLBACK")
            raise
    entry = qual.create("wrangle", f"Rolled {table} up to one row per {entity_col} ({target})", {
        "purpose": (note or f"One record per {entity_col} for modeling")[:200], "raw_sources": [table],
        "cleaning": ([f"Cohort: {'; '.join(words)} ({before:,} record(s) kept)"] if words else []) + [f"Grouped by {entity_col}: " + "; ".join(made[:12])],
        "validation": [f"{before:,} record(s) became {n:,} row(s), one per {entity_col}."], "published_as": target})
    return {"table": target, "records_used": before, "entities": n, "columns": len(meta), "created": made, "cohort": words, "note_id": entry["id"],
            "message": f"Created {target}: {before:,} record(s) became {n:,} row(s), one per {entity_col}. {table} is untouched."}
