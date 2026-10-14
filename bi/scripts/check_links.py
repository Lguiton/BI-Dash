"""Check every outside link in the ML and AI learning paths. Needs internet, so run it on your own computer:

    python scripts/check_links.py

Prints OK / FAIL per link and exits 1 if any fail. A FAIL can also mean the site blocks scripts: open it in a browser
before deciding it has moved. Uses only the standard library.
"""
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.services import learn_path as lp  # noqa: E402


def check(url: str) -> str:
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": "Mozilla/5.0 (link check)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return f"OK {r.status}"
        except Exception as e:  # noqa: BLE001
            last = str(e)[:60]
    return f"FAIL {last}"


def main() -> int:
    bad = 0
    for key, (label, url) in lp.L.items():
        res = check(url)
        bad += res.startswith("FAIL")
        print(f"{res:<28} {label} -> {url}")
    print(f"\n{len(lp.L) - bad} ok, {bad} failed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
