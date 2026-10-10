"""Makes bi_personal_bundle.zip from THIS computer: the app plus your data, backups, models and backend/.env (your AI keys).
For your own computers only. Never hand this zip to anyone else: it contains your data and keys.
Stop the app first (so the database files are complete), then run:  python installer/make_personal_bundle.py
"""
import sys
import zipfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"node_modules", ".venv", ".next", "__pycache__", ".pytest_cache", ".git"}
SKIP_SUFFIX = (".tsbuildinfo", ".pyc")
SKIP_NAMES = {"next-env.d.ts"}

if (ROOT / "backend" / "data").exists() and any(p.name.endswith(".wal") for p in (ROOT / "backend" / "data").glob("*.wal")):
    sys.exit("A .wal file exists in backend/data, which usually means the app is still running. Stop it, then try again.")

out = ROOT.parent / f"bi_personal_bundle_{datetime.now():%Y%m%d}.zip"
n = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in ROOT.rglob("*"):
        rel = p.relative_to(ROOT)
        if p.is_dir() or SKIP_DIRS & set(rel.parts) or p.suffix in SKIP_SUFFIX or p.name in SKIP_NAMES:
            continue
        z.write(p, Path(ROOT.name) / rel)
        n += 1
print(f"Wrote {out} ({n} files). It includes your data and backend/.env. Keep it private.")
