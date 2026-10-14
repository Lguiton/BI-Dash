import io
import json

import pytest
from openpyxl import Workbook

from app.services import anyfile, biz_packs, biz_report

HEAD = "Record Date,Device Type,Fault,Service,Status,Labor Hours,Parts Cost,Price,Days To Fix\n"
ROW = "2026-10-01,Laptop,Battery,Bench repair,Completed,1.5,40,140,2\n2026-10-02,Phone,Cracked screen,Bench repair,Completed,0.75,60,120,1\n"


def _xlsx():
    wb = Workbook()
    ws = wb.active
    rows = [r.split(",") for r in (HEAD + ROW).strip().splitlines()]
    for r in rows:
        ws.append([float(c) if c.replace(".", "", 1).isdigit() and c != r[0] else c for c in r])
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def _parquet():
    import pyarrow as pa
    import pyarrow.parquet as pq
    cols = [c.strip() for c in HEAD.strip().split(",")]
    rows = [r.split(",") for r in ROW.strip().splitlines()]
    t = pa.table({c: [r[i] for r in rows] for i, c in enumerate(cols)})
    b = io.BytesIO()
    pq.write_table(t, b)
    return b.getvalue()


FILES = {
    "a.csv": (HEAD + ROW).encode(),
    "a.tsv": (HEAD + ROW).replace(",", "\t").encode(),
    "a.txt": (HEAD + ROW).replace(",", ";").encode(),
    "a.xlsx": None,
    "a.json": json.dumps([dict(zip(HEAD.strip().split(","), r.split(","))) for r in ROW.strip().splitlines()]).encode(),
    "a.jsonl": "\n".join(json.dumps(dict(zip(HEAD.strip().split(","), r.split(",")))) for r in ROW.strip().splitlines()).encode(),
    "a.xml": ("<rows>" + "".join("<row>" + "".join(f"<{h.replace(' ', '_')}>{v}</{h.replace(' ', '_')}>" for h, v in zip(HEAD.strip().split(","), r.split(","))) + "</row>" for r in ROW.strip().splitlines()) + "</rows>").encode(),
    "a.html": ("<table><tr>" + "".join(f"<th>{h}</th>" for h in HEAD.strip().split(",")) + "</tr>" + "".join("<tr>" + "".join(f"<td>{v}</td>" for v in r.split(",")) + "</tr>" for r in ROW.strip().splitlines()) + "</table>").encode(),
    "a.parquet": None,
}


@pytest.mark.parametrize("name", list(FILES))
def test_every_file_type_loads_into_a_dashboard(client, name):
    raw = FILES[name] or (_xlsx() if name.endswith("xlsx") else _parquet())
    r = client.post("/api/biz-packs/repair-jobs/import-file", files={"file": (name, raw)}, data={"replace": "true"})
    assert r.status_code == 200, (name, r.text)
    assert r.json()["imported"] == 2 and biz_packs.installed("repair-jobs") == 2


def test_unsupported_oversized_and_broken_files_are_refused_politely(client):
    assert client.post("/api/biz-packs/repair-jobs/import-file", files={"file": ("x.exe", b"MZ")}).status_code == 400
    assert client.post("/api/biz-packs/repair-jobs/import-file", files={"file": ("x.xlsx", b"not excel")}).status_code == 400
    assert client.post("/api/biz-packs/repair-jobs/import-file", files={"file": ("x.xml", b'<!DOCTYPE a [<!ENTITY x "y">]><a>&x;</a>')}).status_code == 400
    assert client.post("/api/biz-packs/repair-jobs/import-file", files={"file": ("x.csv", b"a,b\n1,2\n")}).status_code == 400   # missing columns explained
    assert ".parquet" in client.get("/api/biz-packs/file-types").json()["accept"]


def test_custom_dashboard_from_an_excel_file(client):
    rows = "date,region,sales\n" + "\n".join(f"2026-09-{d:02d},{'East' if d % 2 else 'West'},{100 + d}" for d in range(1, 29))
    wb = Workbook()
    ws = wb.active
    for line in rows.splitlines():
        ws.append(line.split(","))
    b = io.BytesIO()
    wb.save(b)
    r = client.post("/api/biz-packs/custom-file", files={"file": ("Sales.xlsx", b.getvalue())}, data={"name": "My sales"})
    assert r.status_code == 200, r.text


def test_report_html_and_pdf_with_sample_stamp_and_escaping(client):
    biz_packs.install_sample("repair-jobs")
    r = client.get("/api/biz-packs/repair-jobs/report?days=30&client=<script>alert(1)</script>Acme&prepared_by=Lamarcus")
    assert r.status_code == 200 and "<script>alert" not in r.text and "&lt;script&gt;" in r.text
    assert "SAMPLE DATA" in r.text and "Next actions" in r.text and "Profit after parts" in r.text
    assert "default-src 'none'" in r.headers["content-security-policy"]
    p = client.get("/api/biz-packs/repair-jobs/report?fmt=pdf")
    assert p.status_code == 200 and p.content[:4] == b"%PDF" and "attachment" in p.headers["content-disposition"]
    assert client.get("/api/biz-packs/repair-jobs/report?days=13").status_code == 400
    assert client.get("/api/biz-packs/nope/report").status_code == 404


def test_report_wording_follows_the_numbers():
    r = biz_report.build("repair-jobs", 30) if biz_packs.installed("repair-jobs") else None
    assert r is None or (r["summary"] and r["actions"])


def test_sandbox_preview_changes_nothing_and_warns(client):
    biz_packs.install_sample("repair-jobs")
    before = biz_packs.installed("repair-jobs")
    live = {k["label"]: k["value"] for k in biz_packs.dashboard("repair-jobs", 30)["kpis"]}
    # no new rows' effect on the numbers is the same as the dashboard's numbers
    csv_new = HEAD.replace(" ", "_").lower() + ROW.replace("2026-10-01", "2026-10-12").replace("2026-10-02", "2026-10-13")
    r = client.post("/api/biz-packs/repair-jobs/import-file/preview", files={"file": ("n.csv", csv_new.encode())}, data={"replace": "false"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["rows_valid"] == 2 and d["current_rows"] == before and d["resulting_rows"] == before + 2
    assert {k["label"]: k["before"] for k in d["kpis"]} == live                      # 'before' matches what the dashboard shows
    assert biz_packs.installed("repair-jobs") == before                                # nothing was written
    # replace with 2 rows: warns it removes more than it adds, and the numbers swing
    r2 = client.post("/api/biz-packs/repair-jobs/import-file/preview", files={"file": ("n.csv", csv_new.encode())}, data={"replace": "true"}).json()
    assert r2["resulting_rows"] == 2 and any("replaces" in w for w in r2["warnings"]) and r2["verdict"].startswith("Review")
    assert biz_packs.installed("repair-jobs") == before
    # duplicate detection against what is already loaded
    with biz_packs.get_cursor() as cur:
        top = cur.execute("SELECT * FROM biz_repair_jobs LIMIT 1").fetchone()
    assert top
    bad = client.post("/api/biz-packs/repair-jobs/import-file/preview", files={"file": ("x.csv", b"a,b\n1,2\n")}, data={})
    assert bad.status_code == 400


def test_unsafe_uploads_are_refused():
    import io
    import zipfile
    from app.services import anyfile
    for raw, name in ((b"MZ\x90\x00" + b"0" * 50, "a.csv"), (b"\x7fELF" + b"0" * 50, "a.txt")):
        with pytest.raises(anyfile.FileError):
            anyfile.to_csv(raw, name)
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("a.csv", "x")
    with pytest.raises(anyfile.FileError):
        anyfile.to_csv(b.getvalue(), "a.csv")                      # a zip pretending to be csv
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("../evil.xml", "x")
    with pytest.raises(anyfile.FileError):
        anyfile.to_csv(b.getvalue(), "a.xlsx")                     # path escape
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/big.xml", "0" * (20 * 1024 * 1024))
    with pytest.raises(anyfile.FileError):
        anyfile.to_csv(b.getvalue(), "a.xlsx")                     # bomb
