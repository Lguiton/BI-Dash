#!/usr/bin/env python3
"""One command for "is this ready?" and "make the zip".

    python scripts/update.py                  content check, consistency check, quick tests, frontend type check and lint
    python scripts/update.py --full           the same, with every backend test (includes the slow ones)
    python scripts/update.py --zip 19         after the checks pass, write ../bi_update19.zip and check it
    python scripts/update.py --no-frontend    skip the frontend steps (no node_modules, or backend-only change)
    python scripts/update.py --only content   run one step: content | consistency | tests | frontend

It stops at the first failing step and says which. The zip leaves out secrets, databases, caches, node_modules and build
output, then runs scripts/check_bundle.py on the result. Run it from anywhere; it works from the project folder.
"""
import fnmatch
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PY = sys.executable
EXCLUDE = ["frontend/node_modules/*", "frontend/.next/*", "frontend/tsconfig.tsbuildinfo", "*/__pycache__/*", "*.pyc", ".git/*", "*/.env", ".env", "backend/data/*.duckdb*",
           "backend/data/*.sqlite*", "backend/data/backups/*", "backend/data/models/*", "*/.pytest_cache/*", "data_engineering/lake/*", "python_practice/_out/*", ".venv/*", "*.zip"]


def run(label, cmd, cwd=ROOT) -> bool:
    t = time.time()
    print(f"\n== {label}", flush=True)
    r = subprocess.run(cmd, cwd=cwd)
    ok = r.returncode == 0
    print(f"-- {label}: {'ok' if ok else 'FAILED'} ({time.time() - t:.0f}s)", flush=True)
    return ok


def node_bin(name):
    p = ROOT / "frontend" / "node_modules" / ".bin" / name
    return str(p) if p.exists() else None


def steps(args):
    out = []
    out.append(("content", lambda: run("Content files", [PY, "scripts/content.py", "validate"])))
    out.append(("consistency", lambda: run("Consistency of manuals, quizzes, tool map and agent notes", [PY, "scripts/check_consistency.py"])))
    test_cmd = [PY, "-m", "pytest", "-q", "-p", "no:cacheprovider"] + ([] if "--full" in args else ["-m", "not slow"])
    out.append(("tests", lambda: run("Backend tests" + ("" if "--full" in args else " (quick tier; --full adds the slow ones)"), test_cmd, cwd=ROOT / "backend")))
    if "--no-frontend" not in args:
        def frontend():
            tsc, es = node_bin("tsc"), node_bin("eslint")
            if not tsc:
                print("\n== Frontend: skipped (run 'npm install' in frontend/ to enable the type check and lint)")
                return True
            ok = run("Frontend type check", [tsc, "--noEmit"], cwd=ROOT / "frontend")
            return ok and (not es or run("Frontend lint", [es, "src"], cwd=ROOT / "frontend"))
        out.append(("frontend", frontend))
    return out


def make_zip(n: str) -> Path:
    name = ROOT.name
    dest = ROOT.parent / f"bi_update{n}.zip"
    count = 0
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(ROOT.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            if any(fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch("x/" + rel, pat) for pat in EXCLUDE):
                continue
            z.write(p, f"{name}/{rel}")
            count += 1
    print(f"\nWrote {dest} ({count} files, {dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def main(argv) -> int:
    if "-h" in argv or "--help" in argv:
        print(__doc__)
        return 0
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    zip_n = argv[argv.index("--zip") + 1] if "--zip" in argv else None
    if zip_n is not None and (not zip_n.isdigit() or only):
        print("--zip needs a number (for example --zip 19) and cannot be combined with --only.")
        return 2
    for name, fn in steps(argv):
        if only and name != only:
            continue
        if not fn():
            print(f"\nStopped: the '{name}' step failed.")
            return 1
    if zip_n is not None:
        dest = make_zip(zip_n)
        if not run("Bundle safety check", [PY, "scripts/check_bundle.py", str(dest)]):
            print(f"\n{dest.name} was written but the safety check found something. Do not share it until that is fixed.")
            return 1
    print("\nAll steps passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
