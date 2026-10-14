"""Intake Workflow: upload one file and a Supervisor runs it past the right specialist at each stage, with a gate after every stage.

  1 Cybersecurity       safety scan (refuses programs, zip bombs, unsafe paths; flags spreadsheet-formula cells)
  2 Data Engineering    structure it: tables are read and typed; free text becomes rows with emails, dates and amounts pulled out; the raw copy is kept
  3 Data Analyst        inspect, clean a COPY with safe rules only, add quality rules, queue what needs a human
  4 Systems Analyst     data dictionary and fitness-for-use check
  5 Cybersecurity + AI Engineering   find personal data, hide it from the AI agents, keep it out of the model and the dashboard
  6 Data Scientist      correlations, trend, anomalies, text themes
  7 Machine Learning    a predictive model with a baseline, if you tell it what to predict
  8 BI                  a dashboard built from the cleaned copy, with a plain-language headline
  9 Supervisor          one report: who did what, what was skipped and why, what still needs you, and how to undo it

Test first: a preview run does stages 1 and 2 on the file without writing anything and shows the plan. Nothing is deleted or overwritten:
the raw table, the cleaned copy and the dashboard are new objects, and "Undo" removes exactly the objects a run created.
Honest limits: rules, not a language model, decide each step; the cleaning is deliberately conservative (it lists, but does not fix, missing values,
outliers and odd codes); PDFs and images are only read if they contain a table; personal-data detection is a detector, not a guarantee."""
from __future__ import annotations

import hashlib
import json
import re
import secrets
import time
from pathlib import Path

import pandas as pd

from app.config import MAX_UPLOAD_BYTES

MAX_RUNS = 20

AGENT_MAP = [
    {"key": "security_gate", "agent": "Cybersecurity agent", "does": "Safety scan before anything is read", "uses": "Upload rules, formula-cell check, file fingerprint"},
    {"key": "structure", "agent": "Data Engineering agent", "does": "Turns files and free text into a typed table; keeps the raw copy; catalogs it", "uses": "Data tab, Dataset hub, Pipeline monitor"},
    {"key": "clean", "agent": "Data Analyst agent", "does": "Cleans a copy with safe rules, adds quality rules, queues what needs a person", "uses": "Data quality, Wrangling log, Issue queue"},
    {"key": "dictionary", "agent": "Systems Analyst agent", "does": "Writes the data dictionary and checks the data fits the job", "uses": "Dataset hub catalog"},
    {"key": "privacy", "agent": "Cybersecurity + AI Engineering agents", "does": "Finds personal data; blocks it from AI agents; keeps it out of model and dashboard", "uses": "Governance, AI privacy limits"},
    {"key": "science", "agent": "Data Scientist agent", "does": "Correlations, trend, anomalies, text themes", "uses": "Analysis Lab, NLP & Deep Learning"},
    {"key": "model", "agent": "Machine Learning agent", "does": "Builds and honestly tests a model when you name a target", "uses": "Model Studio"},
    {"key": "bi", "agent": "BI / Analyst agent", "does": "Builds a dashboard from the cleaned copy and writes the headline", "uses": "Business dashboards"},
    {"key": "report", "agent": "Supervisor", "does": "Plans the run, enforces the gates, writes the report and the undo list", "uses": "Activity log"},
]
NOT_INCLUDED = [
    {"agent": "IT Specialist, Network Engineer, Computer Engineer", "why": "They work on devices and networks, not on the data itself."},
    {"agent": "Project & Product agent", "why": "Plans work rather than touching data. Open items from a run can be added to its board by hand."},
    {"agent": "Full Stack agent", "why": "Builds software around data; nothing in this workflow needs new code."},
]


class IntakeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    from app.services import workspaces
    return workspaces.active()


def _dir() -> Path:
    from app.config import db_path
    from app.services import db
    base = Path(db._path) if getattr(db, "_path", None) else db_path()
    d = base.parent / f"{base.stem}_intake"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _key(rid: str) -> str:
    return f"intake:{_ws()}:{rid}"


def _index() -> list[str]:
    from app.services import state
    try:
        return json.loads(state.kv_get(f"intake:{_ws()}:index") or "[]")
    except ValueError:
        return []


def _save(run: dict) -> None:
    from app.services import state
    state.kv_set(_key(run["id"]), json.dumps(run, default=str))
    idx = [i for i in _index() if i != run["id"]] + [run["id"]]
    for old in idx[:-MAX_RUNS]:
        (_dir() / f"{old}.bin").unlink(missing_ok=True)
    state.kv_set(f"intake:{_ws()}:index", json.dumps(idx[-MAX_RUNS:]))


def get(rid: str) -> dict:
    from app.services import state
    if not re.fullmatch(r"[a-f0-9]{10}", rid or ""):
        raise IntakeError("No such run.", 404)
    raw = state.kv_get(_key(rid))
    if not raw:
        raise IntakeError("No such run.", 404)
    return json.loads(raw)


def list_runs() -> list[dict]:
    out = []
    for rid in reversed(_index()):
        try:
            r = get(rid)
            out.append({k: r[k] for k in ("id", "file", "name", "created", "status", "mode")} | {"stages_done": sum(1 for s in r["stages"] if s["status"] != "pending"), "stages": len(r["stages"])})
        except IntakeError:
            continue
    return out


def agents() -> dict:
    return {"stages": AGENT_MAP, "not_included": NOT_INCLUDED}


# ---------------------------------------------------------------- start / advance


def start(raw: bytes, filename: str, name: str = "", target: str = "", preview: bool = True, protect_pii: bool = True) -> dict:
    from app.services import anyfile, datasets, state
    fn = (filename or "data.csv").strip()[:200]
    if not raw:
        raise IntakeError("The file is empty.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise IntakeError(f"That file is over the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
    if not fn.lower().endswith(anyfile.EXTS):
        raise IntakeError("That file type isn't supported. Use CSV, TSV, TXT, LOG, Excel (.xlsx), JSON, XML, PDF (with a table), Parquet or HTML.")
    label = (name or re.sub(r"\.[A-Za-z0-9]+$", "", fn)).strip()[:50] or "Intake"
    base = datasets.table_name_for(label)[:40]
    rid = secrets.token_hex(5)
    (_dir() / f"{rid}.bin").write_bytes(raw)
    keys = [a["key"] for a in AGENT_MAP]
    plan = ["security_gate", "structure", "preview_plan"] if preview else keys
    titles = {a["key"]: a for a in AGENT_MAP}
    stages = [{"key": k, "agent": titles.get(k, {"agent": "Supervisor"})["agent"], "title": titles.get(k, {"does": "What would happen next"})["does"], "status": "pending", "summary": "", "details": {}, "seconds": 0} for k in plan]
    run = {"id": rid, "file": fn, "name": label, "table_base": base, "created": time.strftime("%Y-%m-%d %H:%M"), "mode": "preview" if preview else "apply", "status": "running", "idx": 0, "stages": stages,
           "options": {"target": (target or "").strip()[:80], "protect_pii": bool(protect_pii)}, "ctx": {}, "created_objects": {"tables": [], "packs": [], "rules": []}, "supervisor": [
               f"Plan: {'test run (nothing is written)' if preview else 'full run'} for {fn}. Each stage must pass its gate before the next starts."], "bytes": len(raw)}
    state.audit("intake_start", f"{fn} ({'preview' if preview else 'apply'})")
    _save(run)
    return run


def apply(rid: str) -> dict:
    """Turn a finished test run into a full run on the same stored file."""
    from app.services import state
    old = get(rid)
    if old["mode"] != "preview" or old["status"] not in ("preview_done", "stopped"):
        raise IntakeError("Only a finished test run can be run for real.")
    if not (_dir() / f"{rid}.bin").exists():
        raise IntakeError("The uploaded file is gone; upload it again.", 404)
    raw = (_dir() / f"{rid}.bin").read_bytes()
    new = start(raw, old["file"], old["name"], old["options"].get("target", ""), False, old["options"].get("protect_pii", True))
    state.audit("intake_apply", old["file"])
    return new


def advance(rid: str) -> dict:
    run = get(rid)
    if run["status"] not in ("running",):
        return run
    st = run["stages"][run["idx"]]
    fn = STAGE_FUNCS[st["key"]]
    t0 = time.time()
    raw = (_dir() / f"{rid}.bin").read_bytes() if (_dir() / f"{rid}.bin").exists() else b""
    try:
        out = fn(run, raw)
    except IntakeError as e:
        out = {"status": "stopped", "summary": e.message, "details": {}}
    except Exception as e:  # noqa: BLE001  one stage failing must not lose the run
        out = {"status": "failed", "summary": f"{type(e).__name__}: {str(e)[:200]}", "details": {}}
    st.update(status=out["status"], summary=out["summary"], details=out.get("details", {}), seconds=round(time.time() - t0, 1))
    for note in out.get("supervisor", []):
        run["supervisor"].append(note)
    halt = out["status"] == "stopped" or (out["status"] == "failed" and st["key"] in HARD)
    if halt:
        run["status"] = "stopped"
        run["supervisor"].append(f"Stopped after '{st['key']}': {out['summary']} Later stages were not run.")
        for s in run["stages"][run["idx"] + 1:]:
            s["status"] = "not_run"
    else:
        run["idx"] += 1
        if run["idx"] >= len(run["stages"]):
            run["status"] = "preview_done" if run["mode"] == "preview" else "done"
    from app.services import state
    if run["status"] in ("done", "preview_done", "stopped"):
        state.audit("intake_finish", f"{run['file']}: {run['status']}")
    _save(run)
    return run


def run_all(rid: str) -> dict:
    """Run every remaining stage (used by tests and the scheduler; the page advances one stage per call to show progress)."""
    r = get(rid)
    while r["status"] == "running":
        r = advance(rid)
    return r


def undo(rid: str) -> dict:
    from app.services import biz_packs, datasets, expectations, state
    run = get(rid)
    gone = {"tables": [], "packs": [], "rules": []}
    for pid in run["created_objects"]["packs"]:
        try:
            biz_packs.delete_custom(pid)
            gone["packs"].append(pid)
        except Exception:  # noqa: BLE001
            pass
    for rule in run["created_objects"]["rules"]:
        try:
            expectations.delete_rule(int(rule))
            gone["rules"].append(rule)
        except Exception:  # noqa: BLE001
            pass
    for t in reversed(run["created_objects"]["tables"]):
        try:
            datasets.delete_table(t)
            gone["tables"].append(t)
        except Exception:  # noqa: BLE001
            pass
    run["created_objects"] = {"tables": [], "packs": [], "rules": []}
    run["status"] = "undone"
    run["supervisor"].append(f"Undone: removed {len(gone['tables'])} table(s), {len(gone['packs'])} dashboard(s) and {len(gone['rules'])} rule(s) this run created. Protections on personal-data columns were kept.")
    (_dir() / f"{rid}.bin").unlink(missing_ok=True)
    state.audit("intake_undo", run["file"])
    _save(run)
    return run


# ---------------------------------------------------------------- stage 1: security


def s_security(run: dict, raw: bytes) -> dict:
    from app.services import anyfile
    fn = run["file"]
    try:
        anyfile.check_safe(raw, fn)
    except anyfile.FileError as e:
        raise IntakeError(f"Refused: {e.message}") from e
    sha = hashlib.sha256(raw).hexdigest()
    run["ctx"]["sha256"] = sha
    formula = 0
    if fn.lower().endswith((".csv", ".tsv", ".txt", ".log", ".dat")):
        text = raw.decode("utf-8", "ignore")
        formula = len(re.findall(r"(?m)(?:^|[,\t;|])\s*[=+@][^,\t;|\n]*(?:\||cmd|powershell|hyperlink|dde)[^,\t;|\n]*", text, flags=re.I))
    d = {"bytes": len(raw), "sha256": sha[:16] + "…", "formula_cells": formula}
    if formula:
        return {"status": "warn", "summary": f"Safe to read, but {formula} cell(s) look like spreadsheet formulas that can run programs if opened in Excel. They are stored as plain text here; do not open the original file in Excel.", "details": d,
                "supervisor": ["Security passed with a warning, so later stages continue; formula-like cells are kept as inert text."]}
    return {"status": "ok", "summary": f"No programs, disguised archives or unsafe paths. {len(raw):,} bytes; fingerprint {sha[:12]}.", "details": d, "supervisor": ["Security gate passed."]}


# ---------------------------------------------------------------- stage 2: structure


def _delims(text: str) -> str | None:
    lines = [ln for ln in text.splitlines() if ln.strip()][:40]
    if len(lines) < 3:
        return None
    for d in (",", "\t", "|", ";"):
        counts = [ln.count(d) for ln in lines]
        if min(counts) >= 1 and sum(1 for c in counts if c == counts[0]) >= 0.8 * len(counts):
            return d
    return None


def _is_free_text(raw: bytes, fn: str) -> bool:
    if not fn.lower().endswith((".txt", ".log", ".dat")):
        return False
    return _delims(raw.decode("utf-8", "ignore")) is None


def _lines_table(raw: bytes, pages: list[int] | None = None, lines: list[str] | None = None) -> tuple[list[str], list[list[str | None]]]:
    """Free text to rows: one row per non-empty line, with the emails, phones, dates and amounts found in it. PDFs also get a page column."""
    from app.services import nlp_lab
    rows = []
    src = lines if lines is not None else [x.strip() for x in raw.decode("utf-8", "ignore").splitlines() if x.strip()][:20000]
    for i, ln in enumerate(src, 1):
        found = {"EMAIL": [], "DATE": [], "MONEY": [], "PHONE": []}
        try:
            for e in nlp_lab.entities(ln[:2900])["entities"]:
                if e["label"] in found:
                    found[e["label"]].append(e["text"])
        except nlp_lab.NlpError:
            pass
        found["PHONE"] += re.findall(r"\(?\b\d{3}\)?[-. ]\d{3}[-. ]\d{4}\b", ln)
        row = [str(i), ln, "; ".join(found["EMAIL"]) or None, "; ".join(found["PHONE"]) or None, "; ".join(found["DATE"]) or None, "; ".join(found["MONEY"]) or None]
        rows.append(([str(pages[i - 1])] + row) if pages else row)
    return (["page"] if pages else []) + ["line_no", "text", "emails", "phones", "dates", "amounts"], rows


def s_structure(run: dict, raw: bytes) -> dict:
    from app.services import datasets, governance
    fn = run["file"]
    free = _is_free_text(raw, fn)
    preview = run["mode"] == "preview"
    try:
        if free:
            header, rows = _lines_table(raw)
        else:
            header, rows, _info = datasets.read_table(raw, fn)
            if _info.get("text_only"):                      # a PDF with words but no table
                from app.services import fileformats
                pl = fileformats.pdf_lines(raw)
                header, rows = _lines_table(b"", [p for p, _ in pl], [t for _, t in pl])
                free = True
    except datasets.DataError as e:
        raise IntakeError(f"Couldn't structure this file: {e}") from e
    if not rows:
        raise IntakeError("The file has a header but no rows.")
    names = datasets.sanitize_columns(header)
    cols = datasets.infer_types(names, rows)
    d = {"unstructured": free, "rows": len(rows), "columns": [{"name": c["name"], "type": c["type"]} for c in cols][:40]}
    how = ("It was free text, so each line became a row and emails, phone numbers, dates and amounts were pulled into their own columns." if free else
           "It was already a table; columns were named and typed (numbers, dates, text).")
    if preview:
        return {"status": "ok", "summary": f"Would store {len(rows):,} rows x {len(cols)} columns. {how} Nothing was written.", "details": d, "supervisor": ["Test run: structure checked, not stored."]}
    raw_table = datasets.table_name_for(run["table_base"] + "_raw")
    res = datasets.import_rows(header, rows, raw_table, "replace", source=f"intake:{fn}"[:60])
    run["created_objects"]["tables"].append(res["table"])
    run["ctx"].update(raw_table=res["table"], work_table=res["table"], rows=res["rows"], free_text=free)
    try:
        governance.save_asset(res["table"], {"description": f"Raw copy ingested by Intake from {fn} on {run['created']}. Never edited.", "owner": "intake"})
    except Exception:  # noqa: BLE001
        pass
    prof = datasets.profile(res["table"])
    kinds = {c["name"]: c["kind"] for c in prof["columns"]}
    run["ctx"]["date_col"] = next((c for c, k in kinds.items() if k == "date"), None)
    run["ctx"]["num_cols"] = [c for c, k in kinds.items() if k == "number"]
    run["ctx"]["text_cols"] = [c for c, k in kinds.items() if k == "text"]
    d["table"] = res["table"]
    return {"status": "ok", "summary": f"Stored {res['rows']:,} rows x {len(cols)} columns as '{res['table']}' (the untouched raw copy). {how}", "details": d, "supervisor": ["Structure gate passed: raw copy stored and cataloged."]}


def s_preview_plan(run: dict, raw: bytes) -> dict:
    structure = next(s for s in run["stages"] if s["key"] == "structure")["details"]
    cols = structure.get("columns", [])
    nums = [c for c in cols if c["type"] in ("number", "BIGINT", "DOUBLE", "INTEGER", "int", "float")]
    has_date = any("date" in c["type"].lower() for c in cols)
    has_text = structure.get("unstructured") or any(c["type"].lower() in ("text", "varchar") for c in cols)
    plan = ["The Analyst will inspect it and clean a copy with safe rules only (spaces, capitalisation, numbers stored as text, duplicate rows).",
            "The Systems Analyst will write the data dictionary; Security + AI Engineering will scan for personal data and hide it from the AI agents.",
            "The Data Scientist will " + ("look for trends, correlations and unusual rows" if len(nums) >= 2 else "profile what it can") + (" and find themes in the text" if has_text else "") + ".",
            ("The Machine Learning agent will build a model for '" + run["options"]["target"] + "'.") if run["options"].get("target") else "The Machine Learning agent will skip modelling until you name a column to predict.",
            "BI will build a dashboard." if has_date and nums else "BI will skip the dashboard: it needs a date column and at least one number."]
    return {"status": "ok", "summary": "Test run complete. Nothing was written. Review the plan, then press Run for real.", "details": {"plan": plan}, "supervisor": ["Preview finished; waiting for you to approve the full run."]}


# ---------------------------------------------------------------- stage 3: analyst


def s_clean(run: dict, raw: bytes) -> dict:
    from app.services import cleaning, data_issues, datasets, expectations
    raw_t = run["ctx"]["raw_table"]
    rep = cleaning.inspect(raw_t)
    steps, notes, flagged = [], [], []
    text_cols = [c["name"] for c in rep["columns"] if c["kind"] == "text"]
    by_kind: dict[str, list[str]] = {}
    for i in rep["issues"]:
        by_kind.setdefault(i["kind"], []).append(i.get("column", ""))
    if by_kind.get("spaces") and text_cols:
        steps.append({"op": "trim"})
    for c in by_kind.get("case", []):
        steps.append({"op": "lower", "column": c})
    for c in by_kind.get("number_as_text", []):
        steps.append({"op": "convert", "column": c, "to": "number"})
    for c in by_kind.get("date_as_text", []):
        steps.append({"op": "convert", "column": c, "to": "date"})
    if by_kind.get("duplicates"):
        steps.append({"op": "dedupe"})
    steps = steps[:cleaning.MAX_STEPS]
    for kind in ("missing", "outliers", "placeholder", "many_levels"):
        for c in by_kind.get(kind, []):
            flagged.append((kind, c))
    work = raw_t
    d = {"health_before": rep["health"], "rows": rep["rows"], "steps": [s["op"] + (":" + s["column"] if s.get("column") else "") for s in steps], "left_for_a_human": [f"{k}: {c}" for k, c in flagged]}
    if steps:
        new_name = datasets.table_name_for(run["table_base"] + "_clean")
        res = cleaning.clean(raw_t, new_name, steps, f"Intake: safe automatic cleaning of {run['file']}")
        run["created_objects"]["tables"].append(res["table"])
        work = res["table"]
        d.update(health_after=res["health_after"], rows_after=res["rows_after"], log=[x["text"] for x in res["log"]])
        if res["rows_after"] < 0.5 * rep["rows"]:
            raise IntakeError(f"Cleaning would have removed {rep['rows'] - res['rows_after']:,} of {rep['rows']:,} rows, which is too many to do without asking. The raw copy is kept; look at the duplicate rows first.")
        notes.append(f"Cleaned a copy ({res['rows_before']:,} to {res['rows_after']:,} rows); health {res['health_before']} to {res['health_after']}.")
    else:
        notes.append("Nothing needed fixing automatically, so the raw copy is used as it is.")
    run["ctx"]["work_table"] = work
    prof = datasets.profile(work)
    kinds = {c["name"]: c["kind"] for c in prof["columns"]}
    run["ctx"].update(date_col=next((c for c, k in kinds.items() if k == "date"), None), num_cols=[c for c, k in kinds.items() if k == "number"], text_cols=[c for c, k in kinds.items() if k == "text"], rows=prof["rows"])
    added = []
    try:
        for s in expectations.suggest(work)["suggestions"]:
            if s["kind"] in ("not_null", "unique") and len(added) < 8:
                r = expectations.add_rule(work, s["kind"], s["params"])
                run["created_objects"]["rules"].append(r["id"])
                added.append(r["text"])
        res_dq = expectations.run(work, "intake")
        d["quality_rules"] = added
        d["rules_failing"] = res_dq["failed"]
    except Exception as e:  # noqa: BLE001
        d["quality_rules_note"] = f"Rules not added: {str(e)[:100]}"
    queued = 0
    for kind, c in flagged[:6]:
        try:
            data_issues.create({"role": "analyst", "severity": "medium", "table": work, "column": c, "summary": f"Intake found {kind} in {c} ({run['file']}). Not changed automatically; decide how to handle it.", "expected": ""})
            queued += 1
        except Exception:  # noqa: BLE001
            pass
    d["issues_queued"] = queued
    if flagged:
        notes.append(f"{len(flagged)} thing(s) need a person's judgement (missing values, outliers, odd codes); {queued} added to the Data Engineer's issue queue.")
    return {"status": "ok", "summary": " ".join(notes), "details": d, "supervisor": ["Analyst gate passed: the original is untouched and the working copy is '" + work + "'."]}


# ---------------------------------------------------------------- stage 4: dictionary


def _role(c: dict, rows: int) -> str:
    n = c["name"].lower()
    if c["kind"] == "date":
        return "date"
    if re.search(r"(^|_)(id|key|uuid)$", n) or (rows >= 20 and c["distinct_count"] == rows):
        return "identifier"
    if c["kind"] == "number":
        return "measure"
    if c["kind"] == "text" and c["distinct_count"] <= max(12, rows * 0.05):
        return "category"
    return "free text"


def s_dictionary(run: dict, raw: bytes) -> dict:
    from app.services import datasets, governance
    t = run["ctx"]["work_table"]
    prof = datasets.profile(t)
    rows = prof["rows"]
    dic = []
    for c in prof["columns"]:
        ex = ", ".join(str(x["value"]) for x in c.get("top", [])[:3]) if c["kind"] == "text" else (f"{c.get('min')} to {c.get('max')}" if c["kind"] in ("number", "date") else "")
        dic.append({"column": c["name"], "type": c["kind"], "role": _role(c, rows), "missing_pct": round(100 * c["nulls"] / rows, 1) if rows else 0, "example": ex[:60]})
    run["ctx"]["roles"] = {x["column"]: x["role"] for x in dic}
    checks = [("Enough rows to model or trend (50+)", rows >= 50), ("Has a date column (needed for trends and a dashboard)", bool(run["ctx"].get("date_col"))),
              ("Has at least one measure (a number to track)", bool(run["ctx"].get("num_cols"))), ("No column is mostly empty (under 40% missing)", all(x["missing_pct"] < 40 for x in dic))]
    try:
        governance.save_asset(t, {"description": "Columns: " + "; ".join(f"{x['column']} ({x['role']})" for x in dic)[:280], "owner": "intake"})
    except Exception:  # noqa: BLE001
        pass
    failed = [c for c, ok in checks if not ok]
    return {"status": "ok" if not failed else "warn", "summary": f"Described {len(dic)} columns. " + ("Fit for analysis." if not failed else "Limits: " + "; ".join(failed) + "."),
            "details": {"dictionary": dic, "fit": [{"check": c, "ok": ok} for c, ok in checks]}, "supervisor": ["Dictionary saved to the catalog." + (" Some downstream stages may be skipped for the limits listed." if failed else "")]}


# ---------------------------------------------------------------- stage 5: privacy


def s_privacy(run: dict, raw: bytes) -> dict:
    from app.services import governance
    t = run["ctx"]["work_table"]
    found = [f for f in governance.pii_scan()["findings"] if f["table"] in (t, run["ctx"].get("raw_table"))]
    cols = sorted({f["column"] for f in found})
    run["ctx"]["pii_cols"] = cols
    blocked = []
    if cols and run["options"].get("protect_pii", True):
        try:
            governance.protect(cols)
            blocked = cols
        except governance.GovError:
            pass
    try:
        governance.save_asset(t, {"classification": "restricted" if cols else "internal", "description": f"Working copy from {run['file']}.", "owner": "intake"})
    except Exception:  # noqa: BLE001
        pass
    d = {"findings": [{"column": f["column"], "category": f["category"], "confidence": f["confidence"]} for f in found], "blocked_from_ai": blocked}
    if not cols:
        return {"status": "ok", "summary": "No obvious personal data (names, emails, phones, IDs, card numbers) found. A clean result means nothing obvious, not nothing.", "details": d, "supervisor": ["Privacy gate passed."]}
    return {"status": "warn", "summary": f"Personal data likely in {', '.join(cols)}. " + ("Those columns are now hidden from the AI agents and excluded from the model and the dashboard." if blocked else "They are excluded from the model and the dashboard; turn on protection to hide them from AI agents."),
            "details": d, "supervisor": [f"Privacy: {len(cols)} column(s) kept out of downstream stages."]}


# ---------------------------------------------------------------- stage 6: science


def _frame(run: dict) -> pd.DataFrame:
    from app.services import biz_models
    df, _ = biz_models.load(run["ctx"]["work_table"])
    return df.drop(columns=[c for c in run["ctx"].get("pii_cols", []) if c in df.columns], errors="ignore")


def s_science(run: dict, raw: bytes) -> dict:
    from app.services import nlp_dl_studio as nd
    df = _frame(run)
    ctx = run["ctx"]
    findings, tables = [], []
    nums = [c for c in ctx.get("num_cols", []) if c in df.columns and not re.search(r"(^|_)(id|key)$", c.lower()) and df[c].nunique() > 3]
    if len(nums) >= 2 and len(df) >= 10:
        cm = df[nums[:12]].corr().abs()
        pairs = sorted(((cm.iloc[i, j], nums[i], nums[j]) for i in range(len(cm)) for j in range(i + 1, len(cm)) if cm.iloc[i, j] == cm.iloc[i, j]), reverse=True)[:3]
        pairs = [p for p in pairs if p[0] >= 0.3]
        if pairs:
            findings.append("Strongest relationships: " + "; ".join(f"{a} and {b} (r {r:.2f})" for r, a, b in pairs) + ". A relationship is not proof one causes the other.")
    dc = ctx.get("date_col")
    if dc and dc in df.columns and nums:
        s = df.assign(_d=pd.to_datetime(df[dc], errors="coerce")).dropna(subset=["_d"]).groupby("_d")[nums[0]].sum()
        if len(s) >= 12:
            q = max(2, len(s) // 4)
            a, b = s.iloc[:q].mean(), s.iloc[-q:].mean()
            if a:
                findings.append(f"Trend: {nums[0]} per day averages {b:,.1f} in the latest quarter of the period against {a:,.1f} in the first ({100 * (b - a) / abs(a):+.0f}%).")
    jobs = []
    if len(nums) >= 2 and len(df) >= 50:
        try:
            r = nd.dl_anomaly(df[nums[:20]])
            findings += r["findings"]
            tables += r["tables"][:1]
            jobs.append("anomalies")
        except nd.StudioError as e:
            findings.append(f"Anomaly check skipped: {e.message}")
    try:
        tcol = nd._text_col(df.drop(columns=[c for c in df.columns if ctx.get("roles", {}).get(c) in ("identifier", "category")], errors="ignore"), "")
        for fn, label in ((nd.nlp_topics, "themes"), (nd.nlp_keywords, "keywords")):
            try:
                r = fn(df, tcol)
                findings += r["findings"]
                tables += r["tables"][:1]
                jobs.append(label)
            except nd.StudioError:
                pass
    except nd.StudioError:
        pass
    if not findings:
        return {"status": "skipped", "summary": "Not enough numeric or text content for pattern finding.", "details": {}, "supervisor": ["Science skipped: nothing to analyse beyond profiling."]}
    return {"status": "ok", "summary": " ".join(findings[:4]), "details": {"findings": findings, "tables": [{"title": t["title"], "columns": t["columns"], "rows": t["rows"][:8]} for t in tables[:3]], "jobs": jobs},
            "supervisor": ["Science done (" + ", ".join(jobs or ["trend/relationships"]) + ")."]}


# ---------------------------------------------------------------- stage 7: model


def s_model(run: dict, raw: bytes) -> dict:
    from app.services import biz_models, ml_studio
    tg = run["options"].get("target", "")
    ctx = run["ctx"]
    if not tg:
        cands = [c for c in ctx.get("num_cols", []) if not re.search(r"(^|_)(id|key)$", c.lower())][:4]
        return {"status": "skipped", "summary": "No target named, so no model was built." + (f" Candidates: {', '.join(cands)}." if cands else ""), "details": {"candidates": cands},
                "supervisor": ["Model skipped: it needs a column to predict. Re-run with a target, or use Model Studio."]}
    df = _frame(run)
    if tg not in df.columns:
        raise IntakeError(f"'{tg}' isn't a column of the cleaned data (or it was kept out as personal data).") if tg not in ctx.get("pii_cols", []) else IntakeError(f"'{tg}' holds personal data, so it won't be modelled.")
    feats = [c for c in df.columns if c != tg and ctx.get("roles", {}).get(c) not in ("identifier", "free text")]
    try:
        r = ml_studio.build(ctx["work_table"], tg, feats[:40] or None, "auto", {"models": ["baseline", "ridge", "logistic", "forest", "boosting"], "seconds": 40})
    except biz_models.ModelError as e:
        return {"status": "warn", "summary": f"No model: {e.message}", "details": {}, "supervisor": ["Model not built: " + e.message]}
    run["ctx"]["model_id"] = r["id"]
    return {"status": "ok" if r["useful"] else "warn", "summary": r["verdict"], "details": {"model_id": r["id"], "best": r["best"], "useful": r["useful"], "important_inputs": [i["input"] for i in r["importance"]][:5], "split": r["split"]},
            "supervisor": ["Model " + ("is useful" if r["useful"] else "did NOT beat the baseline, so it is flagged unreliable") + ". Saved in Model Studio."]}


# ---------------------------------------------------------------- stage 8: BI


def s_bi(run: dict, raw: bytes) -> dict:
    from app.services import biz_packs
    ctx = run["ctx"]
    if not ctx.get("date_col") or not ctx.get("num_cols"):
        return {"status": "skipped", "summary": "No dashboard: it needs a date column and at least one number. Browse the table in the Data tab instead.", "details": {"table": ctx["work_table"]},
                "supervisor": ["BI skipped: the data has no date or no measure."]}
    df = _frame(run)
    for c in [c for c in df.columns if ctx.get("roles", {}).get(c) == "free text"]:
        df = df.drop(columns=[c])
    csv_text = df.head(biz_packs.MAX_ROWS).to_csv(index=False)
    try:
        res = biz_packs.create_custom(csv_text, run["name"][:50] if len(run["name"]) >= 2 else "Intake data", ctx["date_col"])
    except biz_packs.PackError as e:
        return {"status": "warn", "summary": f"Dashboard not built: {e}", "details": {}, "supervisor": ["BI could not build a dashboard: " + str(e)]}
    run["created_objects"]["packs"].append(res["id"])
    head = ""
    try:
        dash = biz_packs.dashboard(res["id"], 30)
        parts = [f"{k['label']} {k['value']}" + (f" ({k['change_pct']:+.0f}% vs the 30 days before)" if k.get("change_pct") is not None else "") for k in dash["kpis"][:3]]
        head = "Last 30 days: " + "; ".join(parts) + "."
    except Exception:  # noqa: BLE001
        pass
    return {"status": "ok", "summary": f"Dashboard '{run['name']}' built from {res['rows']:,} rows with {len(res['measures'])} measure(s) and {len(res['categories'])} categor(ies). {head}",
            "details": {"pack_id": res["id"], "measures": res["measures"], "categories": res["categories"], "notes": res["notes"]}, "supervisor": ["BI done: dashboard created."]}


# ---------------------------------------------------------------- stage 9: report


def s_report(run: dict, raw: bytes) -> dict:
    done = [s for s in run["stages"] if s["key"] != "report"]
    skipped = [s for s in done if s["status"] in ("skipped", "not_run")]
    warns = [s for s in done if s["status"] in ("warn", "failed")]
    needs = []
    a = next((s for s in done if s["key"] == "clean"), None)
    if a and a["details"].get("left_for_a_human"):
        needs.append("Decide how to handle: " + "; ".join(a["details"]["left_for_a_human"][:6]) + " (queued in Data Engineering > Issue queue).")
    m = next((s for s in done if s["key"] == "model"), None)
    if m and m["status"] == "skipped":
        needs.append("Tell it what to predict to run the model stage, or use Model Studio.")
    if m and m["status"] == "warn" and m["details"].get("model_id"):
        needs.append("The model did not beat guessing; do not rely on it. More or better inputs are needed.")
    p = next((s for s in done if s["key"] == "privacy"), None)
    if p and p["details"].get("findings"):
        needs.append("Review the personal-data columns found: " + ", ".join(sorted({f['column'] for f in p['details']['findings']})) + ".")
    links = []
    ct = run["created_objects"]
    if run["ctx"].get("work_table"):
        links.append({"label": "Browse the cleaned table", "href": "/data"})
    if ct["packs"]:
        links.append({"label": "Open the new dashboard", "href": f"/packs?pid={ct['packs'][0]}"})
    if run["ctx"].get("model_id"):
        links.append({"label": "Open the model in Model Studio", "href": "/studio"})
    links.append({"label": "See what was logged", "href": "/activity"})
    d = {"made": {"tables": ct["tables"], "dashboards": ct["packs"], "quality_rules": len(ct["rules"])}, "needs_you": needs, "skipped": [{"stage": s["key"], "why": s["summary"]} for s in skipped], "links": links}
    msg = f"Run finished: {len(done) - len(skipped) - len(warns)} stage(s) clean, {len(warns)} with warnings, {len(skipped)} skipped."
    return {"status": "ok", "summary": msg + (" Needs you: " + " ".join(needs[:2]) if needs else " Nothing needs you."), "details": d,
            "supervisor": ["Report written. Everything created is listed so Undo removes exactly that."]}


STAGE_FUNCS = {"security_gate": s_security, "structure": s_structure, "preview_plan": s_preview_plan, "clean": s_clean, "dictionary": s_dictionary, "privacy": s_privacy,
               "science": s_science, "model": s_model, "bi": s_bi, "report": s_report}
HARD = {"security_gate", "structure", "clean"}
