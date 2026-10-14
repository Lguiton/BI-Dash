"""Industry x department dashboard packs (see services/packs.py)."""
from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import PlainTextResponse, Response
from typing import Literal

from pydantic import BaseModel, Field

from app.services import agents as agents_svc, anyfile, biz_agents, biz_models, biz_packs as packs, biz_report

router = APIRouter(prefix="/api/biz-packs", tags=["biz-packs"])


class ImportBody(BaseModel):
    csv: str = Field(max_length=packs.MAX_CSV_BYTES)
    replace: bool = False


def _run(fn, *a):
    try:
        return fn(*a)
    except packs.PackError as e:
        raise HTTPException(404 if str(e).startswith("No pack") else 400, str(e)) from e


@router.get("")
def list_packs():
    return {"packs": packs.catalog()}


@router.get("/overview")
def overview(days: int = Query(30, ge=0, le=3650)):
    return packs.overview(days)


class RowIn(BaseModel):
    values: dict


class CustomIn(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    csv: str = Field(max_length=packs.MAX_CSV_BYTES)
    date_column: str | None = Field(default=None, max_length=80)
    lower_is_better: list[str] = Field(default_factory=list, max_length=20)


@router.post("/custom")
def create_custom(body: CustomIn):
    return _run(packs.create_custom, body.csv, body.name, body.date_column, body.lower_is_better)


@router.delete("/{pid}/custom")
def delete_custom(pid: str):
    return _run(packs.delete_custom, pid)


@router.get("/{pid}/form")
def form(pid: str):
    return _run(packs.form_spec, pid)


@router.post("/{pid}/rows")
def add_row(pid: str, body: RowIn):
    return _run(packs.add_row, pid, body.values)


async def _file_csv(file: UploadFile, sheet: str | None = None):
    raw = await file.read(anyfile.MAX_UPLOAD_BYTES + 1)
    try:
        return anyfile.to_csv(raw, file.filename or "data.csv", sheet)
    except anyfile.FileError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/file-types")
def file_types():
    return {"accept": anyfile.ACCEPT}


@router.post("/{pid}/import-file")
async def import_file(pid: str, file: UploadFile = File(...), replace: bool = Form(False), sheet: str | None = Form(None)):
    """Import any supported file type (CSV, Excel, JSON, XML, PDF table, Parquet, HTML table) into this dashboard."""
    text, info = await _file_csv(file, sheet)
    r = _run(packs.import_csv, pid, text, replace)
    return {**r, "source": {k: info[k] for k in ("filename", "rows") if k in info}}


@router.post("/{pid}/import-file/preview")
async def import_file_preview(pid: str, file: UploadFile = File(...), replace: bool = Form(False), sheet: str | None = Form(None), days: int = Form(30)):
    """Sandbox: test an import first. Nothing is written; you get the warnings and the before/after KPIs."""
    text, info = await _file_csv(file, sheet)
    r = _run(packs.preview_import, pid, text, replace, days if days in (7, 14, 30, 60, 90, 180, 365) else 30)
    return {**r, "source": {k: info[k] for k in ("filename", "rows") if k in info}}


@router.post("/custom-file")
async def custom_from_file(file: UploadFile = File(...), name: str = Form(...), date_column: str | None = Form(None), lower_is_better: str = Form(""), sheet: str | None = Form(None)):
    """Build a new dashboard from any supported file type."""
    text, _ = await _file_csv(file, sheet)
    lib = [c.strip() for c in lower_is_better.split(",") if c.strip()]
    return _run(packs.create_custom, text, name, date_column or None, lib)


@router.get("/{pid}/report")
def report(pid: str, days: int = Query(30), fmt: Literal["html", "pdf"] = "html", client: str = Query("", max_length=80), prepared_by: str = Query("", max_length=80), download: bool = False):
    r = _run(biz_report.build, pid, days, client, prepared_by)
    stem = f"{pid}-report-{r['generated']}"
    if fmt == "pdf":
        body, mt = biz_report.to_pdf(r), "application/pdf"
    else:
        body, mt = biz_report.to_html(r).encode("utf-8"), "text/html; charset=utf-8"
    disp = f'{"attachment" if download or fmt == "pdf" else "inline"}; filename="{stem}.{fmt}"'
    return Response(body, media_type=mt, headers={"Content-Disposition": disp, "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; img-src data:"})


@router.get("/{pid}/browse")
def browse(pid: str, q: str = "", sort: str = "record_date", dir: str = "desc", limit: int = 50, offset: int = 0):
    return _run(packs.browse, pid, q, sort, dir, limit, offset)


@router.delete("/{pid}/rows/{row_id}")
def delete_row(pid: str, row_id: int):
    return _run(packs.delete_row, pid, row_id)


@router.post("/samples")
def all_samples():
    return _run(packs.install_all_samples)


@router.get("/{pid}/explain")
def explain(pid: str, kpi: str, days: int = 30):
    """Explain one number on a dashboard: meaning, formula, change, what moved it."""
    return _run(packs.explain, pid, kpi[:80], days if days in (0, 7, 14, 30, 60, 90, 180, 365) else 30)


@router.get("/{pid}/dashboard")
def dashboard(pid: str, days: int = Query(30, ge=0, le=3650)):
    return _run(packs.dashboard, pid, days)


@router.post("/{pid}/sample")
def sample(pid: str):
    return _run(packs.install_sample, pid)


@router.post("/{pid}/import")
def import_csv(pid: str, body: ImportBody):
    return _run(packs.import_csv, pid, body.csv, body.replace)


@router.get("/{pid}/template.csv", response_class=PlainTextResponse)
def template(pid: str):
    return PlainTextResponse(_run(packs.template_csv, pid), headers={"Content-Disposition": f'attachment; filename="{pid}.csv"'})


@router.delete("/{pid}/data")
def clear(pid: str):
    return _run(packs.clear, pid)


# ---------------------------------------------------------------- assistants and models
class ChatIn(BaseModel):
    message: str = Field(min_length=2, max_length=1200)
    history: list[dict] = Field(default_factory=list, max_length=20)
    provider: Literal["auto", "google", "openai", "anthropic", "ollama"] = "auto"
    effort: Literal["auto", "simple", "medium", "complex"] = "auto"
    persona: Literal["analyst", "cfo", "math"] = "analyst"


class ModelIn(BaseModel):
    target: str = Field(min_length=1, max_length=60)
    features: list[str] | None = Field(default=None, max_length=40)
    task: Literal["auto", "regression", "classification"] = "auto"


class PredictIn(BaseModel):
    rows: list[dict] = Field(min_length=1, max_length=biz_models.MAX_PREDICT_ROWS)


def _model(fn, *a):
    try:
        return fn(*a)
    except (biz_models.ModelError, packs.PackError) as e:
        raise HTTPException(getattr(e, "status", 400), getattr(e, "message", None) or str(e)) from e


@router.get("/{pid}/assistant")
def assistant_info(pid: str):
    return _run(biz_agents.info, pid)


@router.post("/{pid}/assistant/chat")
def assistant_chat(pid: str, body: ChatIn):
    _run(packs._get, pid)
    from app.routers import ai as ai_router
    if agents_svc.ai_policy.describe()["allowed"]:
        ai_router._check_rate()
    try:
        r = biz_agents.chat(pid, body.message, body.history, body.provider, None, body.effort, body.persona)
    except agents_svc.AgentError as e:
        raise HTTPException(e.status, e.message) from None
    return {"reply": r.reply, "provider": r.provider, "model": r.model, "route": r.route, "actions": r.actions,
            "tools_used": r.tools_used, "stopped_early": r.stopped_early, "usage": {"input_tokens": r.input_tokens, "output_tokens": r.output_tokens}}


@router.post("/{pid}/model")
def build_model(pid: str, body: ModelIn):
    """Build a model without any AI: pick a column to predict."""
    _run(packs._get, pid)
    return _model(biz_models.build, pid, body.target, body.features, body.task)


models_router = APIRouter(prefix="/api/biz-models", tags=["biz-models"])


@models_router.get("")
def models_list():
    return {"models": biz_models.list_models()}


@models_router.get("/{mid}")
def model_get(mid: str):
    return _model(biz_models.get, mid)


@models_router.delete("/{mid}")
def model_delete(mid: str):
    return _model(biz_models.delete, mid)


@models_router.post("/{mid}/predict")
def model_predict(mid: str, body: PredictIn):
    return _model(biz_models.predict, mid, body.rows)
