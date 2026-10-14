"""Readers for XML, PDF tables and JSON-lines, plus the guide to common file formats.

Safety: XML that declares a DOCTYPE or entities is refused (entity tricks can blow up memory), PDFs are capped by pages,
and nothing is ever executed. Everything comes back as the same (header, rows) shape the CSV importer uses.
"""
from __future__ import annotations

import io
import json
import xml.etree.ElementTree as ET
from collections import Counter

MAX_PDF_PAGES = 200
MAX_COLS = 300
MAX_DEPTH = 3


def _err(msg: str, status: int = 400):
    from app.services.datasets import DataError
    return DataError(msg, status)


def _cell(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    s = str(v).strip()
    return s if s != "" else None


# ------------------------------------------------------------------ JSON (flatten nested objects) and JSON lines
def flatten(obj: dict, prefix: str = "", depth: int = 0, out: dict | None = None) -> dict:
    """{"customer": {"name": "A"}} -> {"customer_name": "A"}. Lists stay as JSON text (one cell)."""
    out = {} if out is None else out
    for k, v in obj.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and depth < MAX_DEPTH and v:
            flatten(v, f"{key}_", depth + 1, out)
        else:
            out[key] = v
    return out


def table_from_objects(objs: list[dict]) -> list[list[str | None]]:
    flat = [flatten(o) for o in objs]
    cols: list[str] = []
    seen = set()
    for o in flat[:5000]:
        for k in o:
            if k not in seen:
                seen.add(k)
                cols.append(k)
    if len(cols) > MAX_COLS:
        raise _err(f"{len(cols)} columns is over the {MAX_COLS}-column limit.")
    return [cols] + [[_cell(o.get(c)) for c in cols] for o in flat]


def read_jsonl(text: str) -> list[list[str | None]]:
    objs = []
    for i, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            v = json.loads(line)
        except ValueError as e:
            raise _err(f"Line {i} is not valid JSON, so this isn't a JSON-lines file.") from e
        if not isinstance(v, dict):
            raise _err(f"Line {i} is not a JSON object. JSON lines needs one {{...}} per line.")
        objs.append(v)
    if not objs:
        raise _err("The file has no JSON lines.")
    return table_from_objects(objs)


# ------------------------------------------------------------------ XML
def _tag(e: ET.Element) -> str:
    return e.tag.rsplit("}", 1)[-1] if isinstance(e.tag, str) else ""


def _elem_fields(e: ET.Element, prefix: str, depth: int, acc: dict[str, list[str]]) -> None:
    for k, v in e.attrib.items():
        acc.setdefault(f"{prefix}{k.rsplit('}', 1)[-1]}" if prefix else k.rsplit("}", 1)[-1], []).append(v.strip())
    kids = [c for c in e if isinstance(c.tag, str)]
    for c in kids:
        name = f"{prefix}{_tag(c)}"
        sub = [x for x in c if isinstance(x.tag, str)]
        if (sub or c.attrib) and depth < MAX_DEPTH:
            text = (c.text or "").strip()
            if text:
                acc.setdefault(name, []).append(text)
            _elem_fields(c, f"{name}_", depth + 1, acc)
        else:
            t = (c.text or "").strip()
            if t:
                acc.setdefault(name, []).append(t)


def read_xml(raw: bytes) -> list[list[str | None]]:
    low = raw.lower()
    if b"<!doctype" in low or b"<!entity" in low:
        raise _err("This XML declares a DOCTYPE or entities, which the importer refuses for safety. Remove that part and try again.")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise _err(f"That file is not valid XML ({e}).") from e
    # the records are the repeating children of the first element that has any
    records: list[ET.Element] = []
    queue = [root]
    while queue and not records:
        node = queue.pop(0)
        kids = [c for c in node if isinstance(c.tag, str)]
        counts = Counter(_tag(c) for c in kids)
        rep = [t for t, n in counts.items() if n >= 2]
        if rep:
            best = max(rep, key=lambda t: counts[t])
            records = [c for c in kids if _tag(c) == best]
        else:
            queue.extend(kids)
    if not records:
        records = [root]
    rows: list[dict[str, str]] = []
    cols: list[str] = []
    seen = set()
    for r in records:
        acc: dict[str, list[str]] = {}
        text = (r.text or "").strip()
        if text and not [c for c in r if isinstance(c.tag, str)]:
            acc[_tag(r)] = [text]
        _elem_fields(r, "", 0, acc)
        row = {k: "; ".join(v) for k, v in acc.items() if v}
        for k in row:
            if k not in seen:
                seen.add(k)
                cols.append(k)
        rows.append(row)
    if not cols:
        raise _err("No data found in this XML (no elements or attributes with values).")
    if len(cols) > MAX_COLS:
        raise _err(f"{len(cols)} columns is over the {MAX_COLS}-column limit.")
    return [cols] + [[row.get(c) for c in cols] for row in rows]


# ------------------------------------------------------------------ PDF
def _pdfplumber():
    try:
        import pdfplumber
    except ImportError as e:
        raise _err("Reading PDFs needs the 'pdfplumber' package. Run: pip install -r backend/requirements.txt, then restart the backend.", 501) from e
    return pdfplumber


def read_pdf_table(raw: bytes) -> tuple[list[list[str | None]], dict]:
    pdfplumber = _pdfplumber()
    tables: list[tuple[int, list[list]]] = []
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise _err(f"This PDF has {len(pdf.pages)} pages; the limit is {MAX_PDF_PAGES}.")
            pages = len(pdf.pages)
            for i, page in enumerate(pdf.pages, 1):
                for t in page.extract_tables():
                    if t and len(t) >= 2 and max(len(r) for r in t) >= 2:
                        tables.append((i, t))
    except Exception as e:  # pdfminer raises many different errors on damaged files
        if e.__class__.__name__ == "DataError":
            raise
        raise _err("That PDF could not be opened (damaged or password-protected).") from e
    if not tables:
        raise _err("No table with ruled lines was found in this PDF. Scanned/image PDFs and plain-text reports can't be turned into rows. "
                   "For the text itself, use Analysis Lab > Qualitative > Theme finder.")
    header = [(" ".join(str(c).split()) if c else f"column_{i + 1}") for i, c in enumerate(tables[0][1][0])]
    width = len(header)
    rows, skipped = [], 0
    for _, t in tables:
        for r in t:
            if len(r) != width:
                skipped += 1
                continue
            cells = [None if c is None else " ".join(str(c).split()) or None for c in r]
            if [c or "" for c in cells] == [h for h in header]:
                continue  # header repeated on the next page
            if not any(cells):
                continue
            rows.append(cells)
    if not rows:
        raise _err("The PDF has a table, but no rows matched its header width.")
    return [header] + rows, {"pages": pages, "tables": len(tables), "skipped_rows": skipped}


def pdf_text(raw: bytes) -> str:
    pdfplumber = _pdfplumber()
    out = []
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            if len(pdf.pages) > MAX_PDF_PAGES:
                raise _err(f"This PDF has {len(pdf.pages)} pages; the limit is {MAX_PDF_PAGES}.")
            for page in pdf.pages:
                out.append(page.extract_text() or "")
    except Exception as e:
        if e.__class__.__name__ == "DataError":
            raise
        raise _err("That PDF could not be opened (damaged or password-protected).") from e
    text = "\n\n".join(out).strip()
    if not text:
        raise _err("No text found. This PDF may be a scan (an image); it needs OCR first, which this app doesn't do.")
    return text


# ------------------------------------------------------------------ the guide
FORMATS = [
    {"id": "delimited", "name": "Delimited text (CSV, TSV, pipe)", "ext": ".csv .tsv .txt", "family": "Structured",
     "structure": "Plain text, one record per line, fields split by a delimiter (comma, tab, pipe, semicolon). The first line is usually the header.",
     "benefits": "Opens anywhere, tiny, easy to stream and append, every tool reads it.",
     "limits": "No types (everything is text), no schema, quoting and delimiter clashes, no multiple tables or formatting.",
     "in_app": "Yes. My data detects the delimiter, text encoding and column types."},
    {"id": "xlsx", "name": "Microsoft Excel (XLSX)", "ext": ".xlsx .xlsm", "family": "Structured",
     "structure": "A zipped bundle of XML files: workbook, sheets, styles. Cells hold typed values and formulas.",
     "benefits": "Multiple sheets, formulas, formatting and charts in one file; familiar to business users.",
     "limits": "About 1 million rows per sheet, messy layouts (merged cells, notes above the header), macros are a risk, slow for big data.",
     "in_app": "Yes (.xlsx/.xlsm; pick the sheet). Old .xls must be re-saved."},
    {"id": "json", "name": "JSON and JSON lines", "ext": ".json .jsonl .ndjson", "family": "Semi-structured",
     "structure": "Nested key-value objects and lists. JSON lines is one object per line, so files can be streamed.",
     "benefits": "Flexible: records can differ and nest; the default format of web APIs; JSON lines suits logs and events.",
     "limits": "Verbose, no enforced schema, nesting must be flattened for tables, a plain JSON file must be read whole.",
     "in_app": "Yes. Nested objects become columns (customer.name -> customer_name); lists stay as JSON text."},
    {"id": "xml", "name": "XML", "ext": ".xml", "family": "Semi-structured",
     "structure": "Tagged elements with attributes, nested like a tree. Can carry a schema (XSD) and namespaces.",
     "benefits": "Self-describing, validated against a schema, long-standing in finance, healthcare and government exchange.",
     "limits": "Very verbose, slow to parse, awkward for tables, and entity tricks can be a security risk.",
     "in_app": "Yes. The repeating element becomes the rows; attributes and child tags become columns. Files with a DOCTYPE are refused."},
    {"id": "pdf", "name": "PDF", "ext": ".pdf", "family": "Unstructured (layout)",
     "structure": "A page description: where to draw each piece of text and line. It stores looks, not data.",
     "benefits": "Looks identical everywhere, good for reports, invoices and forms you share.",
     "limits": "Tables are only drawn, not stored, so extraction is a best guess; scans are images (need OCR).",
     "in_app": "Tables with ruled lines load into My data. Text feeds Analysis Lab > Qualitative > Theme finder. Scans (images) are not supported."},
    {"id": "parquet", "name": "Parquet (columnar)", "ext": ".parquet", "family": "Structured (binary)",
     "structure": "Data stored column by column, compressed, with the schema inside.",
     "benefits": "Small files and fast analytics: a query reads only the columns it needs. Standard in big-data tools.",
     "limits": "Not human-readable, written in batches (not for editing single rows).",
     "in_app": "Written and read in Analysis Lab > Big data (practice). The warehouse also exports Parquet."},
    {"id": "sqlite", "name": "SQLite / database files", "ext": ".sqlite .db", "family": "Structured (binary)",
     "structure": "A whole relational database in one file: tables, keys and indexes.",
     "benefits": "Real SQL, keys and types in a single portable file.",
     "limits": "One writer at a time; the file is opaque without a database tool.",
     "in_app": "Yes, as a Source (read-only)."},
    {"id": "text", "name": "Plain text, logs and notes", "ext": ".txt .log .md", "family": "Unstructured",
     "structure": "Free text with no fixed fields. Logs have a loose pattern; notes have none.",
     "benefits": "Captures what tables can't: reasons, complaints, context.",
     "limits": "Needs parsing or text analysis to count anything; meaning depends on context.",
     "in_app": "Yes: Theme finder (Analysis Lab > Qualitative), Knowledge search, and the Event log reader."},
]
