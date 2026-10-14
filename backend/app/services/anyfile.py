"""Turn an uploaded file of almost any common type into CSV text so every importer can use it.

Supported: .csv .tsv .txt .log .dat (delimiter sniffed), .xlsx .xlsm, .json .jsonl .ndjson, .xml, .pdf (tables), .parquet, .html/.htm (first table).
Nothing in a file is ever run. Header names are tidied to snake_case ("Record Date" becomes record_date)."""
from __future__ import annotations

import csv
import io

from app.config import MAX_UPLOAD_BYTES
from app.services import datasets

ACCEPT = ".csv,.tsv,.txt,.log,.dat,.xlsx,.xlsm,.json,.jsonl,.ndjson,.xml,.pdf,.parquet,.html,.htm"
EXTS = tuple(ACCEPT.split(","))


class FileError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


MAX_ENTRIES, MAX_EXPANDED, MAX_RATIO = 1000, 100 * 1024 * 1024, 100
_BAD_MAGIC = (b"MZ", b"\x7fELF", b"#!", b"PK\x03\x04")


def check_safe(raw: bytes, name: str) -> None:
    """VibeGrid-style upload rules: nothing is executed, programs are refused, and zip-based files (xlsx) must not be bombs or carry unsafe paths."""
    low = name.lower()
    zipped = low.endswith((".xlsx", ".xlsm"))
    if raw[:2] == b"MZ" or raw[:4] == b"\x7fELF" or raw[:2] == b"#!":
        raise FileError("That looks like a program, not a data file, so it was refused.")
    if raw[:4] == b"PK\x03\x04" and not zipped:
        raise FileError("Zip archives are not accepted here. Upload the data file itself.")
    if zipped:
        import zipfile
        try:
            zf = zipfile.ZipFile(io.BytesIO(raw))
        except zipfile.BadZipFile as e:
            raise FileError("That Excel file is damaged or not a real .xlsx.") from e
        infos = zf.infolist()
        if len(infos) > MAX_ENTRIES:
            raise FileError("That Excel file has too many parts and was refused.")
        total = 0
        for i in infos:
            n = i.filename
            if n.startswith(("/", "\\")) or ".." in n.replace("\\", "/").split("/") or i.flag_bits & 0x1:
                raise FileError("That Excel file has an unsafe or encrypted part and was refused.")
            total += i.file_size
            if i.compress_size and i.file_size / i.compress_size > MAX_RATIO and i.file_size > 1024 * 1024:
                raise FileError("That file is compressed suspiciously hard (possible zip bomb) and was refused.")
        if total > MAX_EXPANDED:
            raise FileError("That Excel file expands to more than 100 MB and was refused.")


def to_csv(raw: bytes, filename: str, sheet: str | None = None) -> tuple[str, dict]:
    name = (filename or "data.csv").strip()[:200]
    if not name.lower().endswith(EXTS):
        raise FileError("That file type isn't supported. Use CSV, TSV, TXT, Excel (.xlsx), JSON, XML, PDF (with a table), Parquet or HTML.")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise FileError(f"That file is over the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
    check_safe(raw, name)
    try:
        header, rows, info = datasets.read_table(raw, name, sheet)
    except datasets.DataError as e:
        raise FileError(str(e)) from e
    seen: dict[str, int] = {}
    cols = []
    for i, h in enumerate(header):
        s = datasets.slug(h or "", f"column_{i + 1}")
        seen[s] = seen.get(s, 0) + 1
        cols.append(s if seen[s] == 1 else f"{s}_{seen[s]}")
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(cols)
    w.writerows([["" if c is None else c for c in r] for r in rows])
    return out.getvalue(), {**info, "rows": len(rows), "columns": cols}
