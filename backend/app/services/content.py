"""Loads the hand-written learning content from JSON files in app/content/.

    content/index.json          the order of the tracks
    content/manuals/<track>.json   title, intro, outcome and the ordered steps
    content/quizzes/<track>.json   the checkpoint questions
    content/agent_notes.json    notes each agent knows; one note can serve several tracks
    content/toolmap.json        the tool map rows, grouped by category

Everything is checked when it is loaded, so a typo (a missing field, a duplicate step id, an answer number that does not
exist) stops the app with a message that names the file and the item, instead of showing up as a blank page later.
scripts/content.py adds steps, questions and notes from the command line and validates the lot.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

DIR = Path(__file__).resolve().parent.parent / "content"
STATUSES = {"built", "partial", "taught", "not_embedded"}


class ContentError(ValueError):
    pass


def _read(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise ContentError(f"Missing content file: {path.relative_to(DIR.parent)}") from e
    except json.JSONDecodeError as e:
        raise ContentError(f"{path.relative_to(DIR.parent)} is not valid JSON (line {e.lineno}, column {e.colno}): {e.msg}") from e


def _need(cond, where, msg):
    if not cond:
        raise ContentError(f"{where}: {msg}")


def _text(v) -> bool:
    return isinstance(v, str) and v.strip() != ""


def tracks() -> list[str]:
    idx = _read(DIR / "index.json")
    _need(isinstance(idx.get("tracks"), list) and idx["tracks"], "content/index.json", "needs a non-empty 'tracks' list")
    return idx["tracks"]


def check_step(step, where):
    _need(isinstance(step, dict), where, "a step must be an object")
    for k in ("id", "title", "what", "done_when", "ask"):
        _need(_text(step.get(k)), where, f"'{k}' must be non-empty text")
    for k in ("how", "mistakes"):
        _need(isinstance(step.get(k), list) and all(_text(x) for x in step[k]), where, f"'{k}' must be a list of non-empty text")
    _need(len(step["how"]) >= 1, where, "'how' needs at least one instruction")
    t = step.get("tool")
    _need(t is None or (isinstance(t, dict) and _text(t.get("label")) and "href" in t and "tab" in t), where, "'tool' must be null or {label, href, tab}")


def check_manual(track, m):
    where = f"content/manuals/{track}.json"
    _need(isinstance(m, dict), where, "must be an object")
    for k in ("title", "intro", "outcome"):
        _need(_text(m.get(k)), where, f"'{k}' must be non-empty text")
    _need(isinstance(m.get("steps"), list) and m["steps"], where, "needs a non-empty 'steps' list")
    seen = set()
    for i, s in enumerate(m["steps"]):
        check_step(s, f"{where} step #{i + 1} ({s.get('id') if isinstance(s, dict) else '?'})")
        _need(s["id"] not in seen, where, f"step id '{s['id']}' appears twice")
        seen.add(s["id"])


def check_question(q, where, step_ids=None):
    _need(isinstance(q, dict), where, "a question must be an object")
    _need(_text(q.get("q")) and _text(q.get("why")) and _text(q.get("step")), where, "'q', 'why' and 'step' must be non-empty text")
    o = q.get("options")
    _need(isinstance(o, list) and len(o) == 4 and all(_text(x) for x in o) and len(set(o)) == 4, where, "'options' must be four different non-empty texts")
    _need(isinstance(q.get("answer"), int) and not isinstance(q["answer"], bool) and 0 <= q["answer"] < 4, where, "'answer' must be 0, 1, 2 or 3")
    if step_ids is not None:
        _need(q["step"] in step_ids, where, f"step '{q['step']}' is not in that track's manual")


def check_note(n, where, valid_tracks):
    _need(isinstance(n, dict) and _text(n.get("id")) and _text(n.get("text")), where, "needs 'id' and 'text'")
    _need(isinstance(n.get("tracks"), list) and n["tracks"] and all(t in valid_tracks for t in n["tracks"]), where, f"'tracks' must list known tracks ({', '.join(valid_tracks)})")


def check_toolmap(tm):
    _need(isinstance(tm, dict) and tm, "content/toolmap.json", "must map category names to lists of rows")
    for cat, rows in tm.items():
        _need(isinstance(rows, list) and rows, f"content/toolmap.json [{cat}]", "needs a list of rows")
        for r in rows:
            w = f"content/toolmap.json [{cat}] {str(r.get('tool', '?'))[:40]}"
            _need(all(_text(r.get(k)) for k in ("tool", "status", "where", "note")), w, "needs tool, status, where and note")
            _need(r["status"] in STATUSES, w, f"status must be one of {sorted(STATUSES)}")
            _need(r.get("href") is None or str(r["href"]).startswith("/"), w, "href must be null or a local path starting with /")


@lru_cache(maxsize=1)
def load_manuals() -> dict[str, dict]:
    out = {}
    for t in tracks():
        m = _read(DIR / "manuals" / f"{t}.json")
        check_manual(t, m)
        out[t] = m
    return out


def load_quizzes() -> dict[str, list[dict]]:
    """Fresh copies each call: the quiz module reorders the options in place."""
    manuals = load_manuals()
    out = {}
    for t in tracks():
        qs = _read(DIR / "quizzes" / f"{t}.json")
        _need(isinstance(qs, list) and qs, f"content/quizzes/{t}.json", "needs a non-empty list of questions")
        ids = {s["id"] for s in manuals[t]["steps"]}
        for i, q in enumerate(qs):
            check_question(q, f"content/quizzes/{t}.json question #{i + 1}", ids)
        out[t] = qs
    return out


def load_notes() -> list[dict]:
    notes = _read(DIR / "agent_notes.json")
    valid = tracks()
    _need(isinstance(notes, list), "content/agent_notes.json", "must be a list")
    seen = set()
    for i, n in enumerate(notes):
        check_note(n, f"content/agent_notes.json note #{i + 1}", valid)
        _need(n["id"] not in seen, "content/agent_notes.json", f"note id '{n['id']}' appears twice")
        seen.add(n["id"])
    return notes


def knows(track: str) -> str:
    """The text an agent is given as its domain notes: every note that lists its track, in file order."""
    return " ".join(n["text"] for n in load_notes() if track in n["tracks"])


def load_toolmap() -> dict[str, list[dict]]:
    tm = _read(DIR / "toolmap.json")
    check_toolmap(tm)
    return tm
