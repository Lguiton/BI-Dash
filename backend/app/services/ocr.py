"""Scanned files and photos to text, using Tesseract installed on this computer. Nothing leaves the machine and nothing is stored.
OCR output is a draft: letters and digits get confused, so check the numbers before using them."""
from __future__ import annotations

import io
import os
import shutil
import subprocess
import tempfile

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp", ".gif")
MAX_PAGES = 20
TIMEOUT = 90

INSTALL = {
    "windows": ["Install Tesseract for Windows from the UB Mannheim build: search 'tesseract UB Mannheim' and run the installer (keep the English language option ticked).",
                "The default folder is C:\\Program Files\\Tesseract-OCR. The app looks there by itself, so there is no need to change PATH. If you installed it somewhere else, set TESSERACT_CMD in backend/.env to the full path of tesseract.exe. Then restart the backend.",
                "If the dashboard backend runs inside WSL, install it there instead: sudo apt update && sudo apt install -y tesseract-ocr"],
    "wsl_or_linux": ["sudo apt update && sudo apt install -y tesseract-ocr", "Other languages: sudo apt install tesseract-ocr-spa (Spanish), tesseract-ocr-fra, and so on."],
    "check": "Run  tesseract --version  in the same terminal that starts the backend. If it prints a version, restart the backend and reload this page.",
}


class OcrError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _is_windows() -> bool:
    return os.name == "nt"


def _windows_paths() -> list[str]:
    """Where the Windows installers put tesseract.exe, so it is found even when it was never added to PATH."""
    roots = [os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)"), os.environ.get("LOCALAPPDATA")]
    out = [os.path.join(r, "Tesseract-OCR", "tesseract.exe") for r in roots if r]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        out.append(os.path.join(local, "Programs", "Tesseract-OCR", "tesseract.exe"))
    return out + [r"C:\Program Files\Tesseract-OCR\tesseract.exe", r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]


def _cmd() -> str | None:
    c = os.environ.get("TESSERACT_CMD", "").strip().strip('"')
    if c:
        return c if (os.path.isfile(c) or shutil.which(c)) else None
    found = shutil.which("tesseract")
    if found:
        return found
    if _is_windows():
        for p in _windows_paths():
            if os.path.isfile(p):
                return p
    return None


def _run(args, **kw):
    """subprocess.run that does not flash a console window on Windows."""
    if _is_windows():
        kw.setdefault("creationflags", 0x08000000)       # CREATE_NO_WINDOW
    return subprocess.run(args, **kw)


def status() -> dict:
    cmd = _cmd()
    if not cmd:
        return {"available": False, "version": None, "languages": [], "install": INSTALL,
                "message": "Tesseract is not installed on the computer that runs the backend, so scanned files and photos can't be read yet."}
    try:
        v = _run([cmd, "--version"], capture_output=True, text=True, timeout=15)
        ver = (v.stdout or v.stderr).splitlines()[0] if (v.stdout or v.stderr) else "unknown"
        langs = _run([cmd, "--list-langs"], capture_output=True, text=True, timeout=15).stdout.splitlines()[1:]
    except (OSError, subprocess.TimeoutExpired):
        return {"available": False, "version": None, "languages": [], "install": INSTALL, "message": "Tesseract was found but would not start."}
    return {"available": True, "version": ver, "languages": [x.strip() for x in langs if x.strip() and x.strip() != "osd"], "install": INSTALL, "message": "Ready."}


def _lang(lang: str) -> str:
    lang = (lang or "eng").strip() or "eng"
    if not all(ch.isalnum() or ch in "_+" for ch in lang):
        raise OcrError("Language codes use letters only, like eng or spa.")
    return lang


def _ocr_png(cmd: str, png: bytes, lang: str) -> tuple[str, float | None]:
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "page.png")
        with open(src, "wb") as f:
            f.write(png)
        try:
            p = _run([cmd, src, "stdout", "-l", lang, "--psm", "3", "tsv"], capture_output=True, text=True, timeout=TIMEOUT)
        except subprocess.TimeoutExpired:
            raise OcrError("Reading that page took too long. Try a smaller or clearer image.") from None
        if p.returncode != 0:
            msg = (p.stderr or "").strip()
            if "Failed loading language" in msg or "Error opening data file" in msg:
                raise OcrError(f"The language '{lang}' is not installed for Tesseract. Install its language pack or use eng.")
            raise OcrError("Tesseract could not read that image.")
    words, confs, last_key, line = [], [], None, []
    out_lines = []
    for row in p.stdout.splitlines()[1:]:
        c = row.split("\t")
        if len(c) < 12:
            continue
        key = (c[2], c[3], c[4])
        if last_key is not None and key != last_key:
            out_lines.append(" ".join(line))
            line = []
        last_key = key
        txt = c[11].strip()
        if txt:
            line.append(txt)
            try:
                cf = float(c[10])
                if cf >= 0:
                    confs.append(cf)
            except ValueError:
                pass
    if line:
        out_lines.append(" ".join(line))
    return "\n".join(out_lines), (sum(confs) / len(confs) if confs else None)


def _prepare(img_bytes: bytes) -> bytes:
    """Grey, upscale small images and flatten transparency: the three things that help Tesseract most."""
    from PIL import Image, ImageOps
    try:
        im = Image.open(io.BytesIO(img_bytes))
        im.load()
    except Exception:
        raise OcrError("Couldn't open that image. Is it damaged?") from None
    if getattr(im, "n_frames", 1) > 1:
        im.seek(0)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
        im = Image.alpha_composite(bg, im)
    im = ImageOps.exif_transpose(im).convert("L")
    if max(im.size) < 1600:
        k = 1600 / max(im.size)
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    if max(im.size) > 6000:
        k = 6000 / max(im.size)
        im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
    im = ImageOps.autocontrast(im)
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def _pdf_pages(raw: bytes):
    try:
        import pypdfium2 as pdfium
    except ImportError:
        raise OcrError("PDF page rendering is not installed (pypdfium2).", 500) from None
    try:
        pdf = pdfium.PdfDocument(raw)
    except Exception:
        raise OcrError("Couldn't open that PDF. Is it damaged or password protected?") from None
    n = len(pdf)
    for i in range(min(n, MAX_PAGES)):
        img = pdf[i].render(scale=2.5).to_pil()
        buf = io.BytesIO()
        img.convert("L").save(buf, "PNG")
        yield i + 1, n, buf.getvalue()


def read(name: str, raw: bytes, lang: str = "eng") -> dict:
    cmd = _cmd()
    if not cmd:
        raise OcrError("Reading scanned files needs Tesseract, which isn't installed on the backend's computer yet. Open Settings > Scanned files for the install steps.", 503)
    lang = _lang(lang)
    low = (name or "").lower()
    pages, notes, confs = [], [], []
    if low.endswith(".pdf"):
        total = 0
        for num, total, png in _pdf_pages(raw):
            t, c = _ocr_png(cmd, png, lang)
            pages.append(f"--- page {num} ---\n{t}")
            if c is not None:
                confs.append(c)
        if total > MAX_PAGES:
            notes.append(f"Only the first {MAX_PAGES} of {total} pages were read.")
    elif low.endswith(IMAGE_EXT):
        t, c = _ocr_png(cmd, _prepare(raw), lang)
        pages.append(t)
        if c is not None:
            confs.append(c)
    else:
        raise OcrError("OCR reads images (png, jpg, tif, bmp, webp) and scanned PDFs.")
    text = "\n".join(pages).strip()
    conf = round(sum(confs) / len(confs), 1) if confs else None
    if not text.replace("-", "").replace("page", "").strip():
        raise OcrError("No text was found in that image. Try a sharper, straighter, better-lit picture.")
    if conf is not None and conf < 60:
        notes.append(f"Low confidence ({conf}%). Many characters are probably wrong: retake the picture or check every number.")
    notes.append("OCR is a draft. Letters and digits get swapped (O and 0, l and 1, S and 5), so check every figure before using it.")
    return {"name": name, "text": text, "chars": len(text), "pages": len(pages), "confidence_pct": conf, "language": lang, "notes": notes}
