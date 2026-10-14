"""Data toolbox API: Analyst, BI, Data Science and Data Engineering tools plus the how-to/fix guides."""
from fastapi import APIRouter, Body, HTTPException, Response
from fastapi.responses import HTMLResponse

from app.services import analyst_tools as at, bi_tools as bt, data_howto as hw, de_tools as de, ds_tools as ds, script_gen as sg

router = APIRouter(prefix="/api/toolbox", tags=["toolbox"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (at.ToolError, bt.BiError, ds.DsError, de.DeError, sg.ScriptError) as e:
        raise HTTPException(getattr(e, "status", 400), e.message) from None


def _b(body: dict, *names):
    return {n: body[n] for n in names if n in body}


# ---------------------------------------------------------------- how-to
@router.get("/howto")
def howto_areas():
    return {"areas": hw.areas()}


@router.get("/howto/search")
def howto_search(q: str = ""):
    return {"results": hw.search(q, 8)}


@router.get("/howto/{gid}")
def howto_get(gid: str):
    g = hw.get(gid)
    if not g:
        raise HTTPException(404, "No guide with that id.")
    return g


@router.get("/howto-ref/{ref}")
def howto_ref(ref: str, title: str = ""):
    return {"id": hw.for_ref(ref, title)}


# ---------------------------------------------------------------- analyst
@router.get("/analyst/columns")
def a_columns(source: str):
    return {"columns": _g(at.columns, source)}


@router.post("/analyst/query")
def a_query(body: dict = Body(...)):
    return _g(at.run_query, body.get("source"), body.get("metric"), **_b(body, "column", "denominator", "group_by", "grain", "filters", "order", "limit"))


@router.post("/analyst/pivot")
def a_pivot(body: dict = Body(...)):
    return _g(at.pivot, body.get("source"), body.get("rows"), body.get("cols"), body.get("value"), body.get("agg") or "sum", int(body.get("max_cols") or 12))


@router.post("/analyst/ab")
def a_ab(body: dict = Body(...)):
    return _g(at.ab_proportions, int(body.get("a_success", 0)), int(body.get("a_n", 0)), int(body.get("b_success", 0)), int(body.get("b_n", 0)))


@router.post("/analyst/means")
def a_means(body: dict = Body(...)):
    return _g(at.ab_means, [float(x) for x in body.get("a", [])], [float(x) for x in body.get("b", [])])


@router.post("/analyst/samplesize")
def a_size(body: dict = Body(...)):
    return _g(at.sample_size, float(body.get("base_rate", 0)), float(body.get("min_effect", 0)))


@router.post("/analyst/survey")
def a_survey(body: dict = Body(...)):
    return _g(at.survey, body.get("source"), body.get("column"), body.get("group"))


@router.get("/analyst/notebook")
def nb_list():
    return {"entries": at.nb_list()}


@router.post("/analyst/notebook")
def nb_save(body: dict = Body(...)):
    return _g(at.nb_save, body)


@router.delete("/analyst/notebook/{i}")
def nb_del(i: int):
    return _g(at.nb_delete, i)


@router.get("/analyst/notebook/{i}/html", response_class=HTMLResponse)
def nb_html(i: int):
    return HTMLResponse(_g(at.nb_html, i))


# ---------------------------------------------------------------- BI
@router.post("/bi/design", response_class=HTMLResponse)
def bi_design(body: dict = Body(...)):
    return HTMLResponse(_g(bt.design, body.get("pack"), int(body.get("days") or 30), body.get("kpis"), bool(body.get("show_trend", True)), int(body.get("breakdowns", 2)), str(body.get("title") or ""), str(body.get("client") or "")))


@router.post("/bi/story", response_class=HTMLResponse)
def bi_story(body: dict = Body(...)):
    return HTMLResponse(_g(bt.story, body.get("pack"), int(body.get("days") or 30), str(body.get("headline") or ""), str(body.get("recommendation") or ""), str(body.get("client") or "")))


@router.get("/bi/schedules")
def bi_sched():
    return {"items": bt.sched_list()}


@router.post("/bi/schedules")
def bi_sched_add(body: dict = Body(...)):
    return _g(bt.sched_add, body.get("pack"), int(body.get("days") or 30), int(body.get("every_days") or 30), str(body.get("client") or ""), str(body.get("prepared_by") or ""))


@router.delete("/bi/schedules/{sid}")
def bi_sched_del(sid: int):
    return _g(bt.sched_remove, sid)


@router.post("/bi/schedules/{sid}/run")
def bi_sched_run(sid: int):
    return _g(bt.run_due, None, sid)


@router.get("/bi/schedules/{sid}/output/{day}", response_class=HTMLResponse)
def bi_sched_out(sid: int, day: str):
    return HTMLResponse(_g(bt.sched_output, sid, day))


@router.get("/bi/alerts")
def bi_alerts():
    return {**_g(bt.alert_check), "rules": bt.alert_list()}


@router.post("/bi/alerts")
def bi_alert_add(body: dict = Body(...)):
    return _g(bt.alert_add, body.get("pack"), body.get("kpi"), body.get("op"), body.get("value"), int(body.get("days") or 30))


@router.delete("/bi/alerts/{aid}")
def bi_alert_del(aid: int):
    return _g(bt.alert_remove, aid)


@router.get("/bi/dictionary")
def bi_dict(fmt: str = "json", dashboards: str = ""):
    if fmt == "json":
        return {"items": bt.kpi_dictionary()}
    body, mime = _g(bt.kpi_dictionary_export, fmt, [d for d in dashboards.split(",") if d] or None)
    return Response(body, media_type=mime, headers={"Content-Disposition": f'attachment; filename="kpi-dictionary.{fmt}"'} if fmt == "csv" else {})


# ---------------------------------------------------------------- data science
@router.post("/ds/forecast")
def ds_forecast(body: dict = Body(...)):
    return _g(ds.forecast, body.get("source"), body.get("date_col"), body.get("value_col"), body.get("agg") or "sum", body.get("freq") or "day", int(body.get("horizon") or 14), int(body.get("folds") or 3))


@router.get("/ds/modelcard/{mid}", response_class=HTMLResponse)
def ds_card(mid: str, owner: str = "", purpose: str = ""):
    return HTMLResponse(_g(ds.model_card, mid, owner, purpose))


@router.post("/ds/drift")
def ds_drift(body: dict = Body(...)):
    return _g(ds.drift, body.get("model"), int(body.get("recent_days") or 30), body.get("new_source") or None)


@router.post("/ds/segments")
def ds_seg(body: dict = Body(...)):
    return _g(ds.segments, body.get("source"), body.get("features") or [], body.get("k"))


# ---------------------------------------------------------------- data engineering
@router.post("/de/snapshot")
def de_snap(body: dict = Body(...)):
    return _g(de.snapshot, body.get("source"))


@router.post("/de/schema-check")
def de_check(body: dict = Body(...)):
    return _g(de.schema_check, body.get("source"), bool(body.get("accept")))


@router.get("/de/snapshots")
def de_snaps():
    return {"items": de.snapshots()}


@router.post("/de/dedupe/preview")
def de_dd_prev(body: dict = Body(...)):
    return _g(de.dedupe_preview, body.get("source"), body.get("keys") or [], body.get("keep") or "first", body.get("order_col"))


@router.post("/de/dedupe/apply")
def de_dd(body: dict = Body(...)):
    return _g(de.dedupe_apply, body.get("source"), body.get("keys") or [], body.get("new_table"), body.get("keep") or "first", body.get("order_col"))


@router.post("/de/merge/preview")
def de_mg_prev(body: dict = Body(...)):
    return _g(de.merge_preview, body.get("left"), body.get("right"), body.get("left_key"), body.get("right_key"), body.get("how") or "left")


@router.post("/de/merge/apply")
def de_mg(body: dict = Body(...)):
    return _g(de.merge_apply, body.get("left"), body.get("right"), body.get("left_key"), body.get("right_key"), body.get("new_table"), body.get("how") or "left", bool(body.get("allow_multiply")))


@router.get("/de/made")
def de_made():
    return {"items": de.made_tables()}


@router.post("/de/undo")
def de_undo(body: dict = Body(...)):
    return _g(de.undo, body.get("table"))


@router.get("/de/contracts")
def de_contracts():
    return {"items": de.contract_list()}


@router.get("/de/contract")
def de_contract(source: str):
    return {"contract": _g(de.contract_get, source)}


@router.get("/de/contract/propose")
def de_propose(source: str):
    return _g(de.contract_propose, source)


@router.post("/de/contract")
def de_csave(body: dict = Body(...)):
    return _g(de.contract_save, body.get("source"), body.get("columns") or [], str(body.get("owner") or ""))


@router.delete("/de/contract")
def de_cdel(source: str):
    return _g(de.contract_delete, source)


@router.post("/de/contract/check")
def de_ccheck(body: dict = Body(...)):
    return _g(de.contract_check, body.get("source"))


@router.get("/de/contract/markdown")
def de_cmd(source: str):
    return Response(_g(de.contract_markdown, source), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="data-contract.md"'})


@router.post("/de/estimate")
def de_est(body: dict = Body(...)):
    return _g(de.estimate, body.get("rows_per_day"), body.get("columns", 20), body.get("avg_value_bytes", 12), body.get("retention_months", 12), body.get("loads_per_day", 1), body.get("ram_gb", 16), body.get("history_rows", 0))


# ---------------------------------------------------------------- scripts to paste (text only, never run)
@router.get("/scripts/kinds")
def sc_kinds():
    return {"kinds": sg.KINDS, "dialects": list(sg.DIALECTS), "types": list(sg.TYPES)}


@router.post("/scripts")
def sc_make(body: dict = Body(...)):
    return _g(sg.generate, body.get("kind"), body.get("params") or {})


@router.post("/scripts/check")
def sc_check(body: dict = Body(...)):
    return {"safety": sg.scan(str(body.get("text") or "")[:20000])}
