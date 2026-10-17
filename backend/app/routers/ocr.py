"""Scanned files and photos to text on this computer (Tesseract)."""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.services import ocr

router = APIRouter(prefix="/api/ocr", tags=["ocr"])
MAX = 25 * 1024 * 1024


@router.get("/status")
def status():
    return ocr.status()


@router.post("/read")
async def read(file: UploadFile = File(...), lang: str = Form("eng")):
    raw = await file.read(MAX + 1)
    if len(raw) > MAX:
        raise HTTPException(400, "That file is over 25 MB. Use a smaller scan.")
    if not raw:
        raise HTTPException(400, "That file is empty.")
    try:
        return ocr.read(file.filename or "", raw, lang)
    except ocr.OcrError as e:
        raise HTTPException(e.status, e.message) from None
