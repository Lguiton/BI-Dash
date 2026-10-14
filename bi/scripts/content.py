#!/usr/bin/env python3
"""Add and check the learning content that lives in backend/app/content/*.json.

    python scripts/content.py validate                 check every file (also run by scripts/update.py)
    python scripts/content.py stats                    steps, questions and notes per track; steps with no question
    python scripts/content.py add-step <track> [--after <step-id>] < step.json
    python scripts/content.py add-question <track> < question-or-list.json
    python scripts/content.py add-note < note.json     {"topic": "...", "tracks": ["itsupport"], "text": "TOPIC: ..."}
    python scripts/content.py add-tool "<category>" < row-or-list.json

A step is {id, title, what, how[], tool: {label, href, tab} | null, done_when, mistakes[], ask}.
A question is {step, q, options[4], answer (0-3), why}. Nothing is written unless the whole result still validates.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
from app.services import content  # noqa: E402

D = content.DIR


def save(path: Path, obj) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_stdin():
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Standard input is not valid JSON (line {e.lineno}): {e.msg}")


def valid_tabs(track):
    from app.services import manuals  # imported late: it loads the content itself
    return manuals.VALID_TABS.get(track)


def validate() -> int:
    content.load_manuals.cache_clear()
    try:
        man, quiz, notes, tm = content.load_manuals(), content.load_quizzes(), content.load_notes(), content.load_toolmap()
        for t, m in man.items():
            tabs = valid_tabs(t)
            for s in m["steps"]:
                tab = (s["tool"] or {}).get("tab")
                if tab and (tabs is None or tab not in tabs):
                    raise content.ContentError(f"manual {t}/{s['id']}: opens tab '{tab}', which {t} does not have (see VALID_TABS in services/manuals.py)")
    except content.ContentError as e:
        print("INVALID:", e)
        return 1
    print(f"OK: {len(man)} manuals ({sum(len(m['steps']) for m in man.values())} steps), {sum(len(q) for q in quiz.values())} questions, "
          f"{len(notes)} agent notes, {sum(len(r) for r in tm.values())} tool-map rows.")
    return 0


def stats() -> int:
    man, quiz, notes = content.load_manuals(), content.load_quizzes(), content.load_notes()
    print(f"{'track':<12}{'steps':>6}{'questions':>11}{'notes':>7}  steps without a question")
    for t in content.tracks():
        covered = {q["step"] for q in quiz[t]}
        gap = [s["id"] for s in man[t]["steps"] if s["id"] not in covered]
        print(f"{t:<12}{len(man[t]['steps']):>6}{len(quiz[t]):>11}{sum(t in n['tracks'] for n in notes):>7}  {len(gap)}" + (f" ({', '.join(gap[:4])}{'...' if len(gap) > 4 else ''})" if gap else ""))
    return 0


def add_step(track, after=None) -> int:
    if track not in content.tracks():
        raise SystemExit(f"Unknown track '{track}'. Tracks: {', '.join(content.tracks())}")
    step = read_stdin()
    p = D / "manuals" / f"{track}.json"
    m = json.loads(p.read_text(encoding="utf-8"))
    ids = [s["id"] for s in m["steps"]]
    if isinstance(step, dict) and step.get("id") in ids:
        raise SystemExit(f"Step id '{step['id']}' already exists in {track}.")
    pos = len(ids) if after is None else (ids.index(after) + 1 if after in ids else None)
    if pos is None:
        raise SystemExit(f"--after: no step '{after}' in {track}.")
    m["steps"].insert(pos, step)
    content.check_manual(track, m)
    tab = ((step.get("tool") or {}).get("tab"))
    if tab and tab not in (valid_tabs(track) or set()):
        raise SystemExit(f"Tab '{tab}' is not a tab of {track}. Add it to VALID_TABS in services/manuals.py and to the panel first.")
    save(p, m)
    print(f"Added step '{step['id']}' to {track} at position {pos + 1}. Next: add a question for it (add-question).")
    return 0


def add_question(track) -> int:
    if track not in content.tracks():
        raise SystemExit(f"Unknown track '{track}'.")
    new = read_stdin()
    new = new if isinstance(new, list) else [new]
    ids = {s["id"] for s in json.loads((D / "manuals" / f"{track}.json").read_text(encoding="utf-8"))["steps"]}
    p = D / "quizzes" / f"{track}.json"
    qs = json.loads(p.read_text(encoding="utf-8"))
    have = {q["q"].strip().lower() for q in qs}
    for i, q in enumerate(new):
        content.check_question(q, f"new question #{i + 1}", ids)
        if q["q"].strip().lower() in have:
            raise SystemExit(f"New question #{i + 1} is already in the {track} quiz.")
    qs.extend(new)
    save(p, qs)
    print(f"Added {len(new)} question(s) to {track}; it now has {len(qs)}.")
    return 0


def add_note() -> int:
    note = read_stdin()
    notes = json.loads((D / "agent_notes.json").read_text(encoding="utf-8"))
    nums = [int(n["id"][1:]) for n in notes if n["id"][:1] == "n" and n["id"][1:].isdigit()]
    note["id"] = f"n{max(nums, default=0) + 1:03d}"
    note.setdefault("topic", str(note.get("text", ""))[:40])
    content.check_note(note, "new note", content.tracks())
    notes.append(note)
    save(D / "agent_notes.json", notes)
    print(f"Added note {note['id']} for {', '.join(note['tracks'])}.")
    return 0


def add_tool(category) -> int:
    rows = read_stdin()
    rows = rows if isinstance(rows, list) else [rows]
    p = D / "toolmap.json"
    tm = json.loads(p.read_text(encoding="utf-8"))
    if category not in tm:
        raise SystemExit(f"Unknown category. Categories: {'; '.join(tm)}")
    for r in rows:
        r.setdefault("href", None)
    tm[category].extend(rows)
    content.check_toolmap(tm)
    save(p, tm)
    print(f"Added {len(rows)} row(s) to '{category}'.")
    return 0


def main(argv) -> int:
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, args = argv[0], argv[1:]
    try:
        if cmd == "validate":
            return validate()
        if cmd == "stats":
            return stats()
        if cmd == "add-step" and args:
            return add_step(args[0], args[args.index("--after") + 1] if "--after" in args else None)
        if cmd == "add-question" and args:
            return add_question(args[0])
        if cmd == "add-note":
            return add_note()
        if cmd == "add-tool" and args:
            return add_tool(args[0])
    except content.ContentError as e:
        print("INVALID:", e)
        return 1
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
