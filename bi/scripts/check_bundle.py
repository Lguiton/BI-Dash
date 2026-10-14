"""Check a zip (or a folder) before you share it or copy it to another computer.

    python scripts/check_bundle.py ../bi_update17.zip            # shareable: no keys, no data, no computer control
    python scripts/check_bundle.py ../bi_personal_bundle.zip --personal   # your own other computer: keys and data are allowed

Exit code 0 means nothing risky was found, 1 means something was. A clean result means these checks passed,
not that the zip is safe in every way: read the list of what was checked.
"""
from __future__ import annotations

import re
import sys
import zipfile
from pathlib import Path

DATA_SUFFIX = (".duckdb", ".wal", ".sqlite", ".sqlite3", ".db")
SECRET_PATTERNS = [
    ("Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,}")),
    ("OpenAI-style API key", re.compile(r"\bsk-[A-Za-z0-9]{32,}")),
    ("Google API key", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}")),
    ("Slack token", re.compile(r"\bxox[abprs]-[A-Za-z0-9\-]{10,}")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
]
KEY_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]*(?:API_KEY|SECRET|TOKEN|PASSWORD))\s*=\s*(\S+)", re.M)
PLACEHOLDER = re.compile(r"^(?:|\"\"|''|your[-_ ]?.*|xxx+|changeme|<.*>|\.\.\.)$", re.I)
TEXT_LIMIT = 2_000_000
CHECKED = ["no .env file (except .env.example)", "no computer_control.enabled flag", "no database, WAL or sqlite files",
           "no folders of backups, the lake, or landing files", "no API keys, tokens or private keys in text files"]


def _entries(path: Path):
    """Yield (relative name, reader) for every file in a zip or folder."""
    if path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file() and not {"node_modules", ".git", ".venv", ".next"} & set(p.relative_to(path).parts):
                yield p.relative_to(path).as_posix(), (lambda p=p: p.read_bytes()[:TEXT_LIMIT])
    else:
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                if not info.is_dir():
                    yield info.filename, (lambda n=info.filename: z.read(n)[:TEXT_LIMIT])
            # a generator holding the zip open must finish inside this block, so callers consume it fully


def check(path: str | Path, personal: bool = False) -> dict:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)
    findings: list[str] = []
    n = 0
    items = []
    if path.is_dir():
        items = list(_entries(path))
    else:
        with zipfile.ZipFile(path) as z:
            items = [(i.filename, (lambda z=z, f=i.filename: z.read(f)[:TEXT_LIMIT])) for i in z.infolist() if not i.is_dir()]
            findings, n = _scan(items, personal)
            return {"ok": not findings, "files": n, "findings": findings, "mode": "personal" if personal else "shareable", "checked": _checked(personal)}
    findings, n = _scan(items, personal)
    return {"ok": not findings, "files": n, "findings": findings, "mode": "personal" if personal else "shareable", "checked": _checked(personal)}


def _checked(personal: bool) -> list[str]:
    return [c for c in CHECKED if not (personal and any(w in c for w in (".env", "database", "backups", "API keys")))]


def _scan(items, personal: bool) -> tuple[list[str], int]:
    out: list[str] = []
    for name, read in items:
        low = name.lower()
        base = low.rsplit("/", 1)[-1]
        if base == "computer_control.enabled":
            out.append(f"{name}: computer control would be switched on")
        if personal:
            continue
        if base == ".env" or (base.startswith(".env.") and base != ".env.example"):
            out.append(f"{name}: environment file (holds keys)")
        if low.endswith(DATA_SUFFIX):
            out.append(f"{name}: database file")
        if any(f"/{d}/" in f"/{low}" for d in ("backups", "lake", "landing", "_work")) and not low.endswith((".md", ".txt", ".py", ".sh", ".bat")):
            out.append(f"{name}: data from a run (backups, lake, landing)")
        if low.endswith((".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2", ".zip", ".pdf", ".parquet")):
            continue
        try:
            text = read().decode("utf-8")
        except UnicodeDecodeError:
            continue
        for label, pat in SECRET_PATTERNS:
            if pat.search(text):
                out.append(f"{name}: looks like a {label}")
        for m in KEY_LINE.finditer(text):
            val = m.group(2).strip("\"'")
            if not PLACEHOLDER.match(val) and not val.startswith(("$", "${", "os.environ", "process.env")) and len(val) >= 12 and not low.endswith((".md", ".example")):
                out.append(f"{name}: {m.group(1)} has a value")
    return out, len(items)


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    r = check(args[0], personal="--personal" in argv)
    print(f"Checked {r['files']} files in {r['mode']} mode.")
    for c in r["checked"]:
        print(f"  checked: {c}")
    if r["ok"]:
        print("Nothing risky found.")
        return 0
    print("Found:")
    for f in r["findings"]:
        print(f"  - {f}")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
