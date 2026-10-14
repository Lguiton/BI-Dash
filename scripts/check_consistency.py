#!/usr/bin/env python3
"""Cross-check the hand-written learning content (manuals, quizzes, tool map, agent notes, source-mistake notes).

    python scripts/check_consistency.py            # errors and warnings only
    python scripts/check_consistency.py --all      # include info (steps with no quiz question)

Exits 1 if there is an error or a warning, so it can sit in a pre-commit step or in scripts/update.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.services import consistency  # noqa: E402


def main() -> int:
    r = consistency.run()
    show_all = "--all" in sys.argv
    for f in r["findings"]:
        if f["level"] == "info" and not show_all:
            continue
        print(f"[{f['level']:5}] {f['check']:<18} {f['where']}: {f['message']}")
    c = r["checked"]
    print(f"\nChecked {c['manual_steps']} manual steps, {c['quiz_questions']} quiz questions, {c['toolmap_rows']} tool-map rows, "
          f"{c['source_notes']} source-mistake notes, {c['fact_rules']} fact rules.")
    print(f"{r['errors']} errors, {r['warnings']} warnings, {r['info']} info" + ("" if show_all else " (use --all to list info)"))
    return 1 if r["errors"] or r["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
