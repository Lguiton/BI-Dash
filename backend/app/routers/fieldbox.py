"""Field toolbox API: Computer engineering, AI engineering, ML/NLP, Project management and Full stack tools, plus per-field how-to/fix search."""
from fastapi import APIRouter, Body, HTTPException, Response
from fastapi.responses import HTMLResponse

from app.services import aieng_tools as ai, cpe_tools as cpe, field_howto as fh, fs_tools as fs, pm_tools as pm, text_tools as tx

router = APIRouter(prefix="/api/fieldbox", tags=["fieldbox"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (cpe.CpeError, ai.AiError, tx.TextError, pm.PmToolError, fs.FsError) as e:
        raise HTTPException(getattr(e, "status", 400), e.message) from None


def _md(text: str, name: str):
    return Response(text, media_type="text/markdown", headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ------------------------------------------------------------ how-to / fix
@router.get("/howto")
def howto_areas():
    return {"areas": fh.areas()}


@router.get("/howto/search")
def howto_search(q: str = "", area: str = ""):
    return {"results": fh.search(q, area if area in fh.AREAS else None, 8)}


@router.get("/howto/{gid}")
def howto_get(gid: str):
    g = fh.get(gid)
    if not g:
        raise HTTPException(404, "No guide with that id.")
    return g


@router.get("/howto-ref/{ref}")
def howto_ref(ref: str):
    return {"id": fh.for_ref(ref)}


# ------------------------------------------------------------ computer engineering
@router.get("/cpe/boards")
def cpe_boards():
    return {"boards": cpe.BOARDS}


@router.post("/cpe/parts")
def cpe_parts(body: dict = Body(...)):
    return _g(cpe.parts_check, str(body.get("board") or ""), body.get("parts") or [], body.get("supply_ma"), float(body.get("supply_v") or 5))


@router.post("/cpe/runtime")
def cpe_runtime(body: dict = Body(...)):
    return _g(cpe.runtime, body.get("battery_mah"), body.get("active_ma"), body.get("sleep_ma"), body.get("active_s"), body.get("period_s"))


@router.post("/cpe/sketch")
def cpe_sketch(body: dict = Body(...)):
    return _g(cpe.sketch, str(body.get("platform") or "arduino"), str(body.get("sensor") or ""), int(body.get("pin") or 0), int(body.get("interval_s") or 10), str(body.get("output") or "serial"), str(body.get("url") or ""))


@router.post("/cpe/testplan", response_class=HTMLResponse)
def cpe_plan(body: dict = Body(...)):
    return HTMLResponse(_g(cpe.test_plan, str(body.get("project") or ""), body.get("parts") or [], float(body.get("expected_ma") or 0), float(body.get("supply_v") or 5)))


# ------------------------------------------------------------ AI engineering
@router.get("/ai/evals")
def ai_evals():
    return {"suites": _g(ai.eval_list)}


@router.post("/ai/evals")
def ai_eval_save(body: dict = Body(...)):
    return _g(ai.eval_save, str(body.get("name") or ""), body.get("cases") or [], str(body.get("system_prompt") or ""), body.get("id"))


@router.get("/ai/evals/{sid}")
def ai_eval_get(sid: str):
    return _g(ai.eval_get, sid)


@router.delete("/ai/evals/{sid}")
def ai_eval_del(sid: str):
    return _g(ai.eval_delete, sid)


@router.post("/ai/evals/{sid}/score")
def ai_eval_score(sid: str, body: dict = Body(...)):
    return _g(ai.eval_score, sid, body.get("outputs") or {}, str(body.get("label") or ""))


@router.post("/ai/evals/{sid}/run")
def ai_eval_run(sid: str, body: dict = Body(default={})):
    return _g(ai.eval_run_live, sid, str(body.get("label") or ""), str(body.get("provider") or "auto"))


@router.get("/ai/prompts")
def ai_prompts():
    return {"prompts": _g(ai.prompt_list)}


@router.post("/ai/prompts")
def ai_prompt_save(body: dict = Body(...)):
    return _g(ai.prompt_save, str(body.get("name") or ""), str(body.get("text") or ""), str(body.get("note") or ""))


@router.get("/ai/prompts/{name}")
def ai_prompt_get(name: str):
    return {"versions": _g(ai.prompt_get, name)}


@router.get("/ai/prompts/{name}/diff")
def ai_prompt_diff(name: str, v1: int, v2: int):
    return _g(ai.prompt_diff, name, v1, v2)


@router.delete("/ai/prompts/{name}")
def ai_prompt_del(name: str):
    return _g(ai.prompt_delete, name)


@router.post("/ai/cost")
def ai_cost(body: dict = Body(...)):
    return _g(ai.cost, body.get("requests_per_day"), body.get("in_tokens"), body.get("out_tokens"), str(body.get("tier") or "medium"), body.get("price_in"), body.get("price_out"), float(body.get("retry_pct", 5)), int(body.get("days") or 30), float(body.get("extra_context_tokens") or 0))


@router.post("/ai/risks", response_class=HTMLResponse)
def ai_risks(body: dict = Body(...)):
    return HTMLResponse(_g(ai.risk_register, str(body.get("system") or ""), body.get("risks"), str(body.get("owner") or "")))


@router.post("/ai/handoff", response_class=HTMLResponse)
def ai_handoff(body: dict = Body(...)):
    return HTMLResponse(_g(ai.handoff, body))


# ------------------------------------------------------------ ML / NLP
@router.get("/text/sets")
def text_sets():
    return {"sets": _g(tx.set_list)}


@router.post("/text/sets")
def text_set_create(body: dict = Body(...)):
    return _g(tx.set_create, str(body.get("name") or ""), body.get("labels") or [])


@router.get("/text/sets/{name}")
def text_set_get(name: str, limit: int = 200):
    return _g(tx.set_get, name, limit)


@router.delete("/text/sets/{name}")
def text_set_del(name: str):
    return _g(tx.set_delete, name)


@router.post("/text/sets/{name}/examples")
def text_add(name: str, body: dict = Body(...)):
    if body.get("text"):
        return _g(tx.add_from_text, name, str(body["text"]))
    if body.get("source"):
        return _g(tx.add_from_table, name, str(body["source"]), str(body.get("text_col") or ""), str(body.get("label_col") or ""), int(body.get("limit") or 1000))
    return _g(tx.add_examples, name, body.get("rows") or [])


@router.delete("/text/sets/{name}/examples/{eid}")
def text_del_example(name: str, eid: int):
    return _g(tx.delete_example, name, eid)


@router.post("/text/sets/{name}/train")
def text_train(name: str):
    return _g(tx.train_report, name)


@router.post("/text/sets/{name}/classify")
def text_classify(name: str, body: dict = Body(...)):
    return _g(tx.classify, name, body.get("texts") or [], float(body.get("min_confidence") or 0.6))


@router.post("/text/extract")
def text_extract(body: dict = Body(...)):
    return _g(tx.extract_test, body.get("rules") or [], body.get("docs") or [])


@router.get("/experiments")
def exp_list(sort_by: str = "", higher_is_better: bool = True):
    return {"runs": _g(tx.exp_list, sort_by, higher_is_better)}


@router.post("/experiments")
def exp_add(body: dict = Body(...)):
    return _g(tx.exp_log, str(body.get("name") or ""), body.get("params") or {}, body.get("metrics") or {}, str(body.get("notes") or ""), str(body.get("dataset") or ""))


@router.delete("/experiments/{eid}")
def exp_del(eid: str):
    return _g(tx.exp_delete, eid)


@router.get("/experiments.csv")
def exp_csv():
    return Response(_g(tx.exp_csv), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="experiments.csv"'})


# ------------------------------------------------------------ project management
@router.post("/pm/sow", response_class=HTMLResponse)
def pm_sow(body: dict = Body(...)):
    return HTMLResponse(_g(pm.sow, body))


@router.post("/pm/status", response_class=HTMLResponse)
def pm_status(body: dict = Body(default={})):
    return HTMLResponse(_g(pm.status_report, str(body.get("project") or ""), str(body.get("client") or "")))


@router.post("/pm/estimate")
def pm_estimate(body: dict = Body(...)):
    return _g(pm.estimate, body.get("tasks") or [])


@router.post("/pm/stories")
def pm_stories(body: dict = Body(...)):
    return _g(pm.stories, body.get("items") or [])


@router.get("/pm/roadmap")
def pm_roadmap():
    return {"items": _g(pm.roadmap_list)}


@router.post("/pm/roadmap")
def pm_roadmap_add(body: dict = Body(...)):
    return _g(pm.roadmap_add, str(body.get("title") or ""), str(body.get("lane") or "next"), str(body.get("why") or ""), str(body.get("owner") or ""))


@router.post("/pm/roadmap/{rid}/move")
def pm_roadmap_move(rid: str, body: dict = Body(...)):
    return _g(pm.roadmap_move, rid, str(body.get("lane") or ""))


@router.delete("/pm/roadmap/{rid}")
def pm_roadmap_del(rid: str):
    return _g(pm.roadmap_delete, rid)


@router.get("/pm/roadmap.html", response_class=HTMLResponse)
def pm_roadmap_html(title: str = "Product roadmap"):
    return HTMLResponse(_g(pm.roadmap_html, title))


@router.get("/pm/log")
def pm_log():
    return {"entries": _g(pm.log_list)}


@router.post("/pm/log")
def pm_log_add(body: dict = Body(...)):
    return _g(pm.log_add, str(body.get("kind") or "decision"), body)


@router.delete("/pm/log/{lid}")
def pm_log_del(lid: str):
    return _g(pm.log_delete, lid)


@router.get("/pm/log.md")
def pm_log_md():
    return _md(_g(pm.log_markdown), "decision-log.md")


# ------------------------------------------------------------ full stack
@router.post("/fs/scaffold")
def fs_scaffold(body: dict = Body(...)):
    return _g(fs.scaffold, str(body.get("table") or ""), body.get("fields") or [], str(body.get("dialect") or "sqlite"))


@router.post("/fs/contract")
def fs_contract(body: dict = Body(...)):
    return _g(fs.api_contract, str(body.get("title") or ""), body.get("endpoints") or [])


@router.post("/fs/review", response_class=HTMLResponse)
def fs_review(body: dict = Body(...)):
    return HTMLResponse(_g(fs.review_report, str(body.get("code") or ""), str(body.get("language") or "auto"), str(body.get("project") or "")))


@router.post("/fs/runbook")
def fs_runbook(body: dict = Body(default={})):
    return _g(fs.runbook, str(body.get("kind") or "web_app"), str(body.get("host") or "vps"), str(body.get("domain") or ""))


@router.post("/fs/quote")
def fs_quote(body: dict = Body(...)):
    return _g(fs.quote, body.get("features") or [], float(body.get("rate") or 0), float(body.get("buffer_pct", 20)), float(body.get("discount_pct", 0)), float(body.get("deposit_pct", 40)))
