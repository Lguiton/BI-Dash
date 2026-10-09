from fastapi import APIRouter, Body, HTTPException

from app.services import company

router = APIRouter(prefix="/api/company", tags=["company"])


def _g(fn, *a):
    try:
        return fn(*a)
    except company.CoError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("")
def overview():
    return company.overview()


@router.put("/brief")
def brief(body: dict = Body(...)):
    return company.brief_save(body)


@router.put("/deliverables/{did}")
def deliverable(did: str, body: dict = Body(...)):
    return _g(company.set_done, did, bool(body.get("done")))


@router.put("/deliverables/{did}/meta")
def deliverable_meta(did: str, body: dict = Body(...)):
    return _g(company.set_meta, did, body.get("note"), body.get("due"))


@router.get("/snapshots")
def snapshots():
    return {"snapshots": company.snapshots(12), "weekly_due": company.weekly_due()}


@router.post("/snapshots")
def take_snapshot():
    return company.snapshot("manual")


@router.post("/snapshots/ai-brief")
def ai_brief():
    return _g(company.ai_brief)


@router.get("/export")
def export(format: str = "xlsx"):
    from fastapi.responses import Response
    from app.services import company_export
    if format not in ("xlsx", "pdf"):
        raise HTTPException(400, "Format must be xlsx or pdf.")
    try:
        data = company_export.xlsx() if format == "xlsx" else company_export.pdf()
    except ImportError as e:
        raise HTTPException(501, f"Export needs an extra package: pip install openpyxl reportlab ({e.name})")
    mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if format == "xlsx" else "application/pdf"
    return Response(data, media_type=mime, headers={"Content-Disposition": f'attachment; filename="company_plan.{format}"'})
