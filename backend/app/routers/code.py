from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import JSONResponse

from app.routers import ai as ai_router
from app.services import agents, code_check as cc

router = APIRouter(prefix="/api/code", tags=["code"])
AI_MAX = 8000


def _g(fn, *a, **k):
    try:
        return fn(*a, **k)
    except cc.CodeError as e:
        raise HTTPException(e.status, e.message) from None


@router.post("/check")
def check(body: dict = Body(...)):
    return _g(cc.check, body.get("code"), body.get("language", "auto"))


@router.post("/fix")
def fix(body: dict = Body(...)):
    code, lang, mode = body.get("code") or "", body.get("language", "auto"), body.get("mode", "safe")
    if not code.strip():
        raise HTTPException(400, "Paste some code first.")
    if mode == "safe":
        return _g(cc.safe_fixes, code, lang)
    if len(code) > AI_MAX:
        raise HTTPException(400, f"For an AI fix, paste {AI_MAX:,} characters or fewer (one function or file).")
    chk = _g(cc.check, code, lang)
    lang = chk["language"]
    problems = "\n".join(f"- line {f['line']}: {f['message']}" for f in chk["findings"][:15]) or "- (no automatic findings; look for logic and security problems)"
    prompt = (f"Review and correct this {lang} code. Known findings:\n{problems}\n\nReturn ONE fenced code block with the full corrected code, then a short bullet list of what you changed and why. "
              f"Keep behaviour the same except for the fixes.\n\n```{lang}\n{code}\n```")
    try:
        if agents.ai_policy.describe()["allowed"]:
            ai_router._check_rate()
        r = agents.chat("fullstack", prompt, [], None, body.get("provider", "auto"), None, None)
    except agents.AgentError as e:
        return JSONResponse({"detail": e.message, "needs_ai": True}, status_code=e.status)
    fixed, why = _g(cc.extract_code, r.reply)
    out = cc._review(code, fixed, lang, [why] if why else ["See the assistant's notes."])
    out["mode"], out["provider"] = "ai", r.provider
    out["note"] = "Suggested by the assistant, then re-checked offline. Nothing was applied. Read the differences first."
    return out


@router.post("/notebook")
def notebook(body: dict = Body(...)):
    return _g(cc.notebook, body.get("code"), body.get("language", "auto"), body.get("title") or "Code from the Workbench")


@router.get("/jupyter")
def jupyter():
    return cc.jupyter_status()
