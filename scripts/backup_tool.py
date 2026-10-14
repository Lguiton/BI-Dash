#!/usr/bin/env python3
"""Incremental backup with a restore drill. Standard library only. Runs on folders you choose, on your own computer.

    python scripts/backup_tool.py backup  <folder to protect> <backup folder> [--label text]
    python scripts/backup_tool.py list    <backup folder>
    python scripts/backup_tool.py verify  <backup folder>
    python scripts/backup_tool.py restore <backup folder> <snapshot id> <empty destination folder>
    python scripts/backup_tool.py drill   <backup folder> <snapshot id> <folder that was protected>
    python scripts/backup_tool.py prune   <backup folder> --keep 5

Keep the backup folder on a different disk from the originals, and copy it off-site too (the 3-2-1 rule).
This engine teaches the idea and suits small folders; for important data also consider restic, Borg or Veeam."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.services import backup_lab as bl  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup"); b.add_argument("source"); b.add_argument("repo"); b.add_argument("--label", default="")
    sub.add_parser("list").add_argument("repo")
    sub.add_parser("verify").add_argument("repo")
    r = sub.add_parser("restore"); r.add_argument("repo"); r.add_argument("id"); r.add_argument("dest")
    d = sub.add_parser("drill"); d.add_argument("repo"); d.add_argument("id"); d.add_argument("source")
    p = sub.add_parser("prune"); p.add_argument("repo"); p.add_argument("--keep", type=int, default=5)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "backup":
            out = bl.snapshot(Path(a.source), Path(a.repo), a.label)
        elif a.cmd == "list":
            out = bl.summary(Path(a.repo))
        elif a.cmd == "verify":
            out = bl.verify(Path(a.repo))
        elif a.cmd == "restore":
            out = bl.restore(Path(a.repo), a.id, Path(a.dest))
        elif a.cmd == "drill":
            out = bl.drill(Path(a.repo), a.id, Path(a.source))
        else:
            out = bl.prune(Path(a.repo), a.keep)
    except bl.BackupError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        return 1
    print(json.dumps(out, indent=2))
    return 0 if (out.get("ok", True) if isinstance(out, dict) else True) else 2


if __name__ == "__main__":
    sys.exit(main())
