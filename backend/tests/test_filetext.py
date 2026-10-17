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


def test_unfinished_download_and_old_excel_get_clear_messages():
    r = c.post("/api/files/text", files={"file": ("Car_sales.csv.xlsx.crdownload", b"x")})
    assert r.status_code == 400 and "hasn't finished" in r.json()["detail"]
    r = c.post("/api/files/text", files={"file": ("old.xls", b"x")})
    assert r.status_code == 400 and ".xlsx" in r.json()["detail"]


def test_utf16_log_and_tsv_themes_are_read():
    log = "Oct 17 10:00:01 host sshd[1]: Failed password for root from 10.0.0.5 port 22 ssh2\n" * 3
    r = c.post("/api/security/logs/analyze-file", files={"file": ("auth.log", log.encode("utf-16"))})
    assert r.status_code == 200 and r.json()["info"]["kinds"] == {"auth_fail": 3}
    r = c.post("/api/stats/themes/upload", files={"file": ("c.tsv", b"The delivery was late again\nGreat support fast answer\nDelivery late again", "text/plain")})
    assert r.status_code == 200
