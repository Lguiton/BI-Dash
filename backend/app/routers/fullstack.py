from fastapi import APIRouter, Body, HTTPException, Query, Request

from app.services import fullstack as fs

router = APIRouter(prefix="/api/fullstack", tags=["fullstack"])


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except fs.FsError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/api-map")
def api_map(request: Request):
    return fs.api_map(request.app)


@router.post("/request")
def request_test(request: Request, body: dict = Body(...)):
    return _g(fs.request_test, request.app, body.get("method"), body.get("path"), body.get("body"))


@router.get("/scaffold/tables")
def scaffold_tables():
    return {"tables": fs.scaffold_tables()}


@router.get("/scaffold")
def scaffold(table: str = Query(...), ui: bool = Query(True)):
    return _g(fs.scaffold, table, ui)


@router.get("/codebase")
def codebase():
    return fs.codebase()


@router.get("/stack")
def stack():
    return fs.stack()
