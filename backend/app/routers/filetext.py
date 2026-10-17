"""Turn an Excel, PDF or Word file into plain text so the Upload button and the agents can read it. Nothing is stored."""
from __future__ import annotations

import csv
import io
import re
import zipfile

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services import fileformats, ocr
from app.services.datasets import DataError

router = APIRouter(prefix="/api/files", tags=["files"])
MAX = 25 * 1024 * 1024


def _xlsx(raw: bytes) -> tuple[str, str]:
    from openpyxl import load_workbook
    try:
        wb = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(400, "Couldn't open that Excel file. Is it damaged or password protected?") from None
    out, note = [], ""
    for i, ws in enumerate(wb.worksheets):
        if i >= 6:
            note = "Only the first 6 sheets were read. "
            break
        buf = io.StringIO()
        w = csv.writer(buf)
        n = 0
        for row in ws.iter_rows(values_only=True):
            if n >= 2000:
                note += f"Sheet '{ws.title}' was cut at 2,000 rows. "
                break
            if any(c is not None for c in row):
                w.writerow(["" if c is None else (round(c, 4) if isinstance(c, float) else c) for c in row])
                n += 1
        out.append(f"## Sheet: {ws.title}\n{buf.getvalue()}")
    return "\n".join(out), note


def _docx(raw: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception:
        raise HTTPException(400, "Couldn't open that Word file.") from None
    xml = re.sub(r"</w:p>", "\n", xml)
    return re.sub(r"<[^>]+>", "", xml).replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")


def _scan(name: str, raw: bytes) -> tuple[str, str]:
    try:
        r = ocr.read(name, raw)
    except ocr.OcrError as e:
        raise HTTPException(e.status, e.message) from None
    return r["text"], " ".join(r["notes"]) + " "


@router.post("/text")
async def to_text(file: UploadFile = File(...)):
    name = (file.filename or "").lower()
    if re.search(r"\.(crdownload|part|partial|download|opdownload|tmp|temp)$", name):
        raise HTTPException(400, "That is a download that hasn't finished. Wait for it to complete, then pick the finished file.")
    if name.endswith(".xls"):
        raise HTTPException(400, "This is an old Excel (.xls) file. Open it in Excel and Save As .xlsx or CSV.")
    raw = await file.read(MAX + 1)
    if len(raw) > MAX:
        raise HTTPException(400, "That file is over 25 MB. Export a smaller slice.")
    note = ""
    if name.endswith((".xlsx", ".xlsm")):
        text, note = _xlsx(raw)
    elif name.endswith(".pdf"):
        try:
            text = fileformats.pdf_text(raw)
        except DataError as e:
            if "No text found" not in str(e):
                raise
            text, note = _scan(file.filename or name, raw)      # a scanned PDF: read the page pictures instead
    elif name.endswith(ocr.IMAGE_EXT):
        text, note = _scan(file.filename or name, raw)
    elif name.endswith(".docx"):
        text = _docx(raw)
    else:
        raise HTTPException(400, "This reader handles .xlsx, .xlsm, .pdf, .docx and picture files (png, jpg, tif, bmp, webp).")
    if not text.strip():
        raise HTTPException(400, "No readable text found (for a scan, install Tesseract so the app can read it).")
    return {"name": file.filename, "chars": len(text), "text": text[:60000], "note": (note + ("Text was cut at 60,000 characters." if len(text) > 60000 else "")).strip()}
