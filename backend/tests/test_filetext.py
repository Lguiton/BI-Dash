import io

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.main import app

c = TestClient(app)


def _xlsx():
    wb = Workbook()
    ws = wb.active
    ws.title = "Data"
    ws.append(["month", "bookings"])
    for i in range(36):
        ws.append([f"2023-{i:02d}", 50 + i])
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def test_xlsx_to_text_keeps_all_rows():
    r = c.post("/api/files/text", files={"file": ("b.xlsx", _xlsx())}).json()
    assert "## Sheet: Data" in r["text"] and r["text"].count("\n") >= 37 and "85" in r["text"]


def test_rejects_other_types_and_bad_files():
    assert c.post("/api/files/text", files={"file": ("a.exe", b"x")}).status_code == 400
    assert c.post("/api/files/text", files={"file": ("a.xlsx", b"not a workbook")}).status_code == 400
