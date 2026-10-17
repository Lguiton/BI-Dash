import io
import shutil

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app
from app.services import ocr

client = TestClient(app)
needs = pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract not installed here")


def picture(lines=("INVOICE 1042", "Total due 250.00"), fmt="PNG"):
    im = Image.new("RGB", (900, 260), "white")
    d = ImageDraw.Draw(im)
    f = ImageFont.load_default(size=48)
    for i, t in enumerate(lines):
        d.text((30, 30 + i * 80), t, fill="black", font=f)
    b = io.BytesIO()
    im.save(b, fmt)
    return b.getvalue()


def test_status_shape():
    s = client.get("/api/ocr/status").json()
    assert "available" in s and s["install"]["wsl_or_linux"] and s["install"]["windows"]


def test_missing_tesseract_is_a_clear_message(monkeypatch):
    monkeypatch.setenv("TESSERACT_CMD", "/nonexistent/tesseract")
    assert ocr.status()["available"] is False
    r = client.post("/api/ocr/read", files={"file": ("a.png", picture(), "image/png")})
    assert r.status_code == 503 and "Tesseract" in r.json()["detail"]
    r2 = client.post("/api/files/text", files={"file": ("a.png", picture(), "image/png")})
    assert r2.status_code == 503


@needs
def test_reads_an_image():
    r = client.post("/api/ocr/read", files={"file": ("inv.png", picture(), "image/png")})
    assert r.status_code == 200
    j = r.json()
    assert "INVOICE" in j["text"] and "1042" in j["text"] and "250.00" in j["text"]
    assert j["confidence_pct"] and j["notes"]


@needs
def test_reads_a_scanned_pdf_through_the_universal_reader():
    im = Image.open(io.BytesIO(picture()))
    b = io.BytesIO()
    im.save(b, "PDF")
    r = client.post("/api/files/text", files={"file": ("scan.pdf", b.getvalue(), "application/pdf")})
    assert r.status_code == 200 and "1042" in r.json()["text"] and "page 1" in r.json()["text"]


@needs
def test_blank_and_bad_inputs():
    blank = io.BytesIO()
    Image.new("RGB", (400, 200), "white").save(blank, "PNG")
    assert client.post("/api/ocr/read", files={"file": ("b.png", blank.getvalue(), "image/png")}).status_code == 400
    assert client.post("/api/ocr/read", files={"file": ("x.png", b"not an image", "image/png")}).status_code == 400
    assert client.post("/api/ocr/read", files={"file": ("x.txt", b"hello", "text/plain")}).status_code == 400
    assert client.post("/api/ocr/read", files={"file": ("a.png", picture(), "image/png")}, data={"lang": "../etc"}).status_code == 400
