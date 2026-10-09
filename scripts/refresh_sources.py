#!/usr/bin/env python3
"""Refresh saved data sources from the command line (cron, Task Scheduler, or a one-off).

    python scripts/refresh_sources.py                 # every due source in the remembered workspace
    python scripts/refresh_sources.py --all           # every enabled source, due or not
    python scripts/refresh_sources.py --workspace real --id 3

Stop the API first if it is running: DuckDB lets only one process open a database file for writing. If the API is
running, leave the built-in scheduler to it (BI_SCHEDULER=1, the default) or call POST /api/sources/<id>/run instead.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.services import db, sources, state, workspaces  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workspace", choices=workspaces.NAMES, help="practice or real (default: the one the app last used)")
    ap.add_argument("--id", type=int, help="refresh only this source")
    ap.add_argument("--all", action="store_true", help="ignore schedules and refresh every enabled source")
    a = ap.parse_args()
    try:
        workspaces.startup()
        if a.workspace:
            workspaces.activate(a.workspace)
        todo = [sources.get(a.id)] if a.id else [s for s in sources.list_sources() if s["enabled"]] if a.all else sources.due()
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        print(("Could not open the database. Is the API still running? " if "lock" in msg.lower() else "Error: ") + msg.splitlines()[0])
        return 2
    if not todo:
        print(f"Nothing to do in the {workspaces.active()} workspace.")
        return 0
    failed = 0
    for s in todo:
        try:
            r = sources.run_source(s["id"])
            print(f"ok    {s['name']}: {r['message']} ({r['seconds']}s)")
        except sources.SourceError as e:
            failed += 1
            print(f"FAIL  {s['name']}: {e.message}")
    db.close_connection()
    state.close_all()
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
