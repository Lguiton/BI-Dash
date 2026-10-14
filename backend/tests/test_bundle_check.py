import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_bundle", ROOT / "scripts" / "check_bundle.py")
cb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cb)


def _zip(tmp_path, files):
    p = tmp_path / "t.zip"
    with zipfile.ZipFile(p, "w") as z:
        for n, c in files.items():
            z.writestr(n, c)
    return p


def test_clean_bundle_passes(tmp_path):
    p = _zip(tmp_path, {"bi/README.md": "hello", "bi/backend/.env.example": "ANTHROPIC_API_KEY=your-key-here\n", "bi/app.py": "key = os.environ['ANTHROPIC_API_KEY']"})
    r = cb.check(p)
    assert r["ok"] and r["files"] == 3


def test_flags_env_keys_data_and_computer_control(tmp_path):
    p = _zip(tmp_path, {"bi/backend/.env": "ANTHROPIC_API_KEY=abc\n", "bi/notes.txt": "key sk-ant-api03-" + "a" * 40,
                        "bi/backend/data/real.duckdb": "x", "bi/computer_control.enabled": "", "bi/cfg.ini": "OPENAI_API_KEY=realvalue123456789",
                        "bi/backups/x.duckdb": "x"})
    f = " | ".join(cb.check(p)["findings"])
    for want in (".env: environment file", "Anthropic API key", "real.duckdb: database file", "computer control would be switched on", "OPENAI_API_KEY has a value", "backups"):
        assert want in f, want


def test_personal_mode_allows_keys_but_never_computer_control(tmp_path):
    ok = _zip(tmp_path, {"bi/backend/.env": "ANTHROPIC_API_KEY=sk-ant-api03-" + "a" * 40, "bi/data/real.duckdb": "x"})
    assert cb.check(ok, personal=True)["ok"]
    bad = tmp_path / "b.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("bi/computer_control.enabled", "")
    assert not cb.check(bad, personal=True)["ok"]


def test_folder_scan_and_cli_exit_codes(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / ".env").write_text("X=1")
    assert not cb.check(tmp_path)["ok"]
    assert cb.main([str(tmp_path)]) == 1
    (tmp_path / "a" / ".env").unlink()
    assert cb.main([str(tmp_path)]) == 0 and cb.main([]) == 2


def test_the_real_project_tree_is_clean_when_zipped_like_a_release():
    # the project's tracked source (not data, not .env) must hold no secrets
    import subprocess
    files = [f for f in subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True).stdout.split("\n") if f] if (ROOT / ".git").exists() else []
    if not files:
        return
    r = cb._scan([(f, (lambda f=f: (ROOT / f).read_bytes()[:cb.TEXT_LIMIT])) for f in files if (ROOT / f).is_file()], False)[0]
    assert r == [], r
