import io
import json

import pytest

from app.services import fileformats
from app.services.datasets import DataError, read_table
from tests.conftest import csv_file

XML = b"""<?xml version="1.0"?>
<orders>
  <order id="O1"><customer>C01</customer><date>2026-01-01</date><line product="Widget" qty="2">19.99</line></order>
  <order id="O2"><customer>C02</customer><date>2026-01-02</date><line product="Gadget" qty="1">5.00</line><note>rush</note></order>
  <order id="O3"><customer>C01</customer><date>2026-01-03</date><line product="Widget" qty="4">39.98</line></order>
</orders>
"""


def test_xml_records_attributes_and_children():
    header, rows, info = read_table(XML, "orders.xml")
    assert header == ["id", "customer", "date", "line", "line_product", "line_qty", "note"]
    assert len(rows) == 3 and rows[0][:3] == ["O1", "C01", "2026-01-01"] and rows[0][4] == "Widget" and rows[0][3] == "19.99"
    assert rows[1][6] == "rush" and rows[0][6] is None


def test_xml_namespaces_nesting_and_repeats():
    x = b"""<root xmlns="urn:x"><item><name>A</name><tags><t>x</t><t>y</t></tags><geo><lat>1</lat><lon>2</lon></geo></item>
            <item><name>B</name><tags><t>z</t></tags><geo><lat>3</lat><lon>4</lon></geo></item></root>"""
    header, rows, _ = read_table(x, "n.xml")
    assert "name" in header and "geo_lat" in header and "tags_t" in header
    assert rows[0][header.index("tags_t")] == "x; y" and rows[1][header.index("geo_lon")] == "4"


def test_xml_refuses_entities_and_garbage():
    bomb = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaa">]><l><i>&a;</i><i>&a;</i></l>'
    with pytest.raises(DataError, match="DOCTYPE"):
        read_table(bomb, "bomb.xml")
    with pytest.raises(DataError, match="not valid XML"):
        read_table(b"<a><b></a>", "bad.xml")


def test_json_nested_flatten_and_jsonl():
    data = [{"id": 1, "customer": {"name": "A", "geo": {"city": "LV"}}, "items": [1, 2]}, {"id": 2, "customer": {"name": "B", "geo": {"city": "NY"}}, "coupon": "X"}]
    header, rows, _ = read_table(json.dumps(data).encode(), "o.json")
    assert header == ["id", "customer_name", "customer_geo_city", "items", "coupon"]
    assert rows[0][2] == "LV" and rows[0][3] == "[1, 2]" and rows[1][4] == "X" and rows[1][3] is None
    lines = b'{"a": 1, "b": {"c": 2}}\n{"a": 3, "b": {"c": 4}}\n'
    header, rows, _ = read_table(lines, "e.jsonl")
    assert header == ["a", "b_c"] and rows == [["1", "2"], ["3", "4"]]
    header, rows, _ = read_table(lines, "e.json")  # JSON lines saved with a .json name still works
    assert len(rows) == 2
    with pytest.raises(DataError):
        read_table(b'{"a": 1}\nnot json\n', "bad.jsonl")


def _pdf_with_table(rows, title="Sales"):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    buf = io.BytesIO()
    t = Table(rows)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.5, colors.black)]))
    SimpleDocTemplate(buf, pagesize=letter).build([Paragraph(title, getSampleStyleSheet()["Title"]), t])
    return buf.getvalue()


def test_pdf_table_and_text_and_failures():
    pytest.importorskip("pdfplumber")
    raw = _pdf_with_table([["region", "units", "revenue"], ["West", "10", "100.50"], ["East", "7", "70.25"], ["North", "3", "31.00"]])
    header, rows, info = read_table(raw, "sales.pdf")
    assert header == ["region", "units", "revenue"] and len(rows) == 3 and rows[0] == ["West", "10", "100.50"]
    assert info["tables"] == 1 and info["pages"] == 1
    assert "Sales" in fileformats.pdf_text(raw)
    with pytest.raises(DataError, match="damaged"):
        read_table(b"%PDF-1.4 not really", "x.pdf")
    from reportlab.pdfgen import canvas
    b = io.BytesIO()
    c = canvas.Canvas(b)
    c.drawString(72, 700, "Just a paragraph of text, no table.")
    c.save()
    with pytest.raises(DataError, match="No table"):
        read_table(b.getvalue(), "text.pdf")


def test_import_endpoints_accept_new_formats_and_guide(client):
    r = client.post("/api/data/import", files={"file": ("orders.xml", XML, "application/xml")}, data={"mode": "replace"})
    assert r.status_code == 200, r.text
    assert r.json()["table"] == "orders" and r.json()["rows"] == 3
    r = client.post("/api/data/import", files={"file": ("ev.jsonl", b'{"u":1,"p":{"k":"a"}}\n{"u":2,"p":{"k":"b"}}\n', "application/json")}, data={"mode": "replace"})
    assert r.status_code == 200 and {c["name"] for c in r.json()["columns"]} == {"u", "p_k"}
    g = client.get("/api/data/formats").json()["formats"]
    assert {"delimited", "xlsx", "json", "xml", "pdf", "parquet", "text"} <= {f["id"] for f in g}
    assert all(f["structure"] and f["benefits"] and f["limits"] and f["in_app"] for f in g)
    bad = client.post("/api/data/import", files={"file": ("bomb.xml", b"<!DOCTYPE a [<!ENTITY x 'y'>]><a><i>&x;</i><i>1</i></a>", "application/xml")})
    assert bad.status_code == 400
