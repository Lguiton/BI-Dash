from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.services import auth, state

router = APIRouter(prefix="/api/auth", tags=["auth"])


class Pw(BaseModel):
    password: str = Field(max_length=200)


class Change(BaseModel):
    current: str = Field(max_length=200)
    new: str = Field(max_length=200)


def _set(resp: Response, tok: str):
    resp.set_cookie(auth.COOKIE, tok, max_age=auth.SESSION_SECONDS, httponly=True, samesite="lax", secure=auth.secure_cookie(), path="/")


def _w(fn, *a):
    try:
        return fn(*a)
    except auth.AuthError as e:
        raise HTTPException(e.status, e.message) from e


@router.get("/status")
def status(request: Request):
    return {"enabled": auth.enabled(), "authenticated": (not auth.enabled()) or auth.valid_token(request.cookies.get(auth.COOKIE))}


@router.post("/login")
def login(b: Pw, request: Request, response: Response):
    if not auth.enabled():
        return {"enabled": False, "authenticated": True}
    ip = request.client.host if request.client else "?"
    try:
        tok = auth.login(b.password, ip)
    except auth.AuthError as e:
        state.audit("login_failed", f"from {ip}: {e.message}", ok=False)
        raise HTTPException(e.status, e.message) from e
    state.audit("login", f"from {ip}")
    _set(response, tok)
    return {"enabled": True, "authenticated": True}


@router.post("/logout")
def logout(response: Response):
    state.audit("logout", "")
    response.delete_cookie(auth.COOKIE, path="/")
    return {"authenticated": False}


@router.post("/change-password")
def change(b: Change, response: Response):
    if not auth.enabled():
        raise HTTPException(400, "Login is not turned on.")
    _set(response, _w(auth.change_password, b.current, b.new))
    state.audit("password_changed", "")
    return {"changed": True}


@router.post("/sign-out-everywhere")
def everywhere(request: Request, response: Response):
    if auth.enabled() and not auth.valid_token(request.cookies.get(auth.COOKIE)):
        raise HTTPException(401, "Sign in first.")
    auth.sign_out_everywhere()
    response.delete_cookie(auth.COOKIE, path="/")
    return {"signed_out": True}
