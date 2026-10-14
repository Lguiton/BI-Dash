"""Update 14 endpoints: first-run checklist, notebook export, saved views, lineage, weekly report, palette actions,
sample packs and export-everything."""
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.services import actions, export_all, lineage, nbexport, packs, setup_check, views, weekly

router = APIRouter(prefix="/api", tags=["more"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (nbexport.NbError, views.ViewError, lineage.LineageError, weekly.WeeklyError, actions.ActionError, packs.PackError) as e:
        raise HTTPException(e.status, e.message) from e
    except Exception as e:  # noqa: BLE001
        if type(e).__name__ == "MailError":
            raise HTTPException(getattr(e, "status", 502), getattr(e, "message", str(e))) from e
        if type(e).__name__ in ("SqlLabError", "DataError"):
            raise HTTPException(getattr(e, "status", 400), getattr(e, "message", str(e))) from e
        raise


@router.get("/setup")
def setup():
    return setup_check.status()


class NbIn(BaseModel):
    kind: str
    sql: str | None = Field(None, max_length=20000)
    steps: list[dict] | None = Field(None, max_length=30)
    config: dict | None = None
    title: str | None = Field(None, max_length=80)


@router.post("/notebook/export")
def notebook_export(body: NbIn):
    out = _g(nbexport.build, body.kind, body.model_dump(exclude_none=True))
    import json
    return Response(json.dumps(out["notebook"], indent=1), media_type="application/x-ipynb+json",
                    headers={"Content-Disposition": f'attachment; filename="{out["filename"]}"'})


class ViewIn(BaseModel):
    name: str = Field(max_length=60)
    filters: dict | None = None
    hidden: list[str] | None = None
    order: list[str] | None = None
    id: str | None = Field(None, max_length=40)


@router.get("/views")
def views_list():
    return {"views": views.list_views()}


@router.post("/views")
def views_save(body: ViewIn):
    return _g(views.save, body.name, body.filters, body.hidden, body.order, body.id)


@router.delete("/views/{vid}")
def views_delete(vid: str):
    _g(views.delete, vid)
    return {"deleted": vid}


@router.get("/lineage/kpi/{kid}")
def lineage_kpi(kid: str):
    return _g(lineage.kpi, kid)


class WeeklyIn(BaseModel):
    enabled: bool | None = None
    weekday: int | None = None


@router.get("/weekly")
def weekly_get():
    return {"config": weekly.config(), "days": weekly.DAYS, "email_ready": weekly.mailer.configured(), **_g(_safe_changes)}


def _safe_changes():
    try:
        return {"report": weekly.what_changed(), "error": None}
    except weekly.WeeklyError as e:
        return {"report": None, "error": e.message}


@router.put("/weekly")
def weekly_put(body: WeeklyIn):
    return _g(weekly.save_config, body.model_dump(exclude_none=True))


@router.post("/weekly/send")
def weekly_send():
    return _g(weekly.send_now)


@router.get("/actions")
def actions_list():
    return {"actions": actions.catalog()}


class ActIn(BaseModel):
    confirm: bool = False


@router.post("/actions/{aid}/run")
def actions_run(aid: str, body: ActIn):
    return _g(actions.run, aid, body.confirm)


@router.get("/packs")
def packs_list():
    return {"packs": packs.catalog()}


@router.post("/packs/{pid}/load")
def packs_load(pid: str):
    return _g(packs.load, pid)


@router.get("/export-all")
def export_everything():
    data = export_all.build()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="bi_export_{stamp}.zip"'})
