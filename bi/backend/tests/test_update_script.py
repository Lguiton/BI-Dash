import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location("update_script", ROOT / "scripts" / "update.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_zip_leaves_out_secrets_data_and_build_output(tmp_path, monkeypatch):
    m = _load()
    proj = tmp_path / "bi"
    keep = ["backend/app/main.py", "frontend/src/app/page.tsx", "backend/.env.example", "docs/A.md", "backend/app/content/index.json"]
    drop = ["backend/.env", ".env", "backend/data/x.duckdb", "backend/data/x.duckdb.wal", "backend/data/s.sqlite", "backend/data/backups/b.zip", "backend/data/models/m.pkl",
            "frontend/node_modules/a/b.js", "frontend/.next/x.js", "backend/app/__pycache__/m.pyc", "backend/.pytest_cache/v", ".git/config", "data_engineering/lake/f.parquet", "old.zip"]
    for f in keep + drop:
        p = proj / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")
    monkeypatch.setattr(m, "ROOT", proj)
    dest = m.make_zip("7")
    names = {n.split("/", 1)[1] for n in zipfile.ZipFile(dest).namelist()}
    assert names == set(keep)
    assert dest.name == "bi_update7.zip"


def test_bad_arguments_are_refused(capsys):
    m = _load()
    assert m.main(["--zip", "abc"]) == 2
    assert m.main(["--zip", "5", "--only", "content"]) == 2
    assert m.main(["--help"]) == 0
