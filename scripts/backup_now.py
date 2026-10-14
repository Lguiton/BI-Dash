#!/usr/bin/env python3
"""Make a backup of your Real data right now. If the app is running it asks the app (safe, the database stays open);
if the app is stopped it copies the database files directly. Prints where the backup went."""
import json
import shutil
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "backend" / "data"


def via_app() -> bool:
    try:
        req = urllib.request.Request("http://127.0.0.1:8020/api/backups?workspace=real", data=b"{}", method="POST", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            print("Backup made by the running app:", json.loads(r.read()).get("name", "ok"))
        return True
    except Exception:  # noqa: BLE001 - app not running or refused
        return False


def direct() -> bool:
    src = DATA / "bi_warehouse_real.duckdb"
    if not src.exists():
        print("There is no Real data yet, so there is nothing to back up.")
        return True
    dest_dir = DATA / "backups" / "real"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = datetime.utcnow().strftime("%Y%m%d-%H%M%S") + "_manual.duckdb"
    shutil.copy2(src, dest_dir / name)
    wal = src.with_name(src.name + ".wal")
    if wal.exists():
        shutil.copy2(wal, dest_dir / (name + ".wal"))
    print("Backup copied while the app was stopped:", dest_dir / name)
    return True


if __name__ == "__main__":
    sys.exit(0 if via_app() or direct() else 1)
