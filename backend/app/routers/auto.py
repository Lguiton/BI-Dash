"""Today list, recurring jobs and capped AI prep drafts."""
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import PlainTextResponse

from app.services import assistants, automation, eivanta_notes, experience, prep, project_links

router = APIRouter(prefix="/api/auto", tags=["automation"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except (automation.AutoError, prep.PrepError, assistants.AssistantError, eivanta_notes.NoteError, project_links.LinkError) as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/today")
def today():
    return automation.today()


@router.get("/recurring")
def recurring():
    return {"recurring": automation.recurring_list(), "note": "Created when the app runs on or after the day, once per week or month."}


@router.post("/recurring")
def recurring_add(body: dict = Body(...)):
    return _g(automation.recurring_add, body)


@router.put("/recurring/{rid}")
def recurring_update(rid: int, body: dict = Body(...)):
    return _g(automation.recurring_update, rid, body)


@router.delete("/recurring/{rid}")
def recurring_delete(rid: int):
    return _g(automation.recurring_delete, rid)


@router.post("/recurring/run")
def recurring_run():
    return {"created": automation.run_recurring()}


@router.get("/prep")
def prep_status():
    return prep.status()


@router.put("/prep")
def prep_config(body: dict = Body(...)):
    return _g(prep.update_config, body)


@router.get("/prep/drafts")
def prep_drafts():
    return prep.drafts()


@router.post("/prep/item/{wid}")
def prep_item(wid: int):
    return _g(prep.draft_item, wid)


@router.post("/prep/table")
def prep_table(body: dict = Body(...)):
    return _g(prep.draft_table, str(body.get("table") or ""))


@router.delete("/prep/drafts/{key:path}")
def prep_delete(key: str):
    return _g(prep.delete_draft, key)


@router.get("/queue")
def queue():
    return prep.queue()


@router.put("/prep/drafts/{key:path}")
def prep_update(key: str, body: dict = Body(...)):
    return _g(prep.update_draft, key, body)


@router.post("/prep/job/{jid}")
def prep_job(jid: int):
    return _g(prep.draft_job, jid)


@router.get("/assistants")
def assistants_desk():
    return {"roles": assistants.roles(), "stats": assistants.stats(), "log": assistants.log(30), "mine": experience.mine_list(),
            "note": "Assistants prepare; you decide. Roles are shown to the agents as their job description."}


@router.put("/assistants/roles/{track}")
def role_set(track: str, body: dict = Body(...)):
    return _g(assistants.set_role, track, body.get("does"), body.get("never"))


@router.delete("/assistants/roles/{track}")
def role_reset(track: str):
    return _g(assistants.reset_role, track)


@router.delete("/examples/mine/{eid}")
def mine_delete(eid: int):
    if not experience.delete_mine(eid):
        raise HTTPException(404, "No such example.")
    return {"deleted": eid}


@router.get("/eivanta-notes")
def notes_list(job_id: int | None = None):
    return eivanta_notes.listing(job_id)


@router.post("/eivanta-notes")
def notes_add(body: dict = Body(...)):
    return _g(eivanta_notes.add, body)


@router.delete("/eivanta-notes/{nid}")
def notes_delete(nid: int):
    return _g(eivanta_notes.delete, nid)


@router.get("/eivanta-notes/export")
def notes_export():
    return PlainTextResponse(eivanta_notes.markdown(), media_type="text/markdown", headers={"Content-Disposition": 'attachment; filename="learned-for-eivanta.md"'})


@router.get("/links")
def links_list():
    return project_links.listing()


@router.put("/links")
def links_save(body: dict = Body(...)):
    return _g(project_links.save, body.get("links"))


@router.get("/links/status")
def links_status():
    return project_links.status()
