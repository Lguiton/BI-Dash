import importlib.util
import io
import json
import shutil
import sys
from pathlib import Path

import pytest

from app.services import content, manuals, quizzes

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture()
def cli(tmp_path, monkeypatch):
    d = tmp_path / "content"
    shutil.copytree(content.DIR, d)
    monkeypatch.setattr(content, "DIR", d)
    content.load_manuals.cache_clear()
    spec = importlib.util.spec_from_file_location("content_cli", ROOT / "scripts" / "content.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "D", d)

    def run(args, stdin=None):
        monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(stdin) if stdin is not None else ""))
        return m.main(args)
    yield run, d
    content.load_manuals.cache_clear()


def refused(run, args, data):
    """The command either exits with a message or returns a failure code; either way it must not succeed."""
    try:
        return run(args, data) != 0
    except SystemExit as e:
        return bool(e.code)


STEP = {"id": "new-step", "title": "A new step", "what": "Something.", "how": ["Do it."], "tool": {"label": "Ticket coach", "href": None, "tab": "coach"}, "done_when": "Done.", "mistakes": ["Rushing."], "ask": "Why?"}
QUESTION = {"step": "new-step", "q": "A question?", "options": ["a", "b", "c", "d"], "answer": 2, "why": "Because."}


def test_shipped_content_loads_and_matches_the_app():
    assert list(manuals.MANUALS) == content.tracks() == list(quizzes.QUIZZES)
    assert sum(len(m["steps"]) for m in manuals.MANUALS.values()) > 150
    assert all(content.knows(t) for t in ("itsupport", "network", "security", "analyst"))


def test_validate_command_passes_on_shipped_content(cli, capsys):
    run, _ = cli
    assert run(["validate"]) == 0 and "OK:" in capsys.readouterr().out


def test_add_step_then_question_then_validate(cli, capsys):
    run, d = cli
    assert run(["add-step", "itsupport", "--after", "tickets"], STEP) == 0
    ids = [s["id"] for s in json.loads((d / "manuals" / "itsupport.json").read_text())["steps"]]
    assert ids[ids.index("tickets") + 1] == "new-step"
    assert run(["add-question", "itsupport"], QUESTION) == 0
    assert run(["validate"]) == 0
    assert run(["stats"]) == 0


def test_cli_refuses_bad_input_and_writes_nothing(cli):
    run, d = cli
    before = (d / "manuals" / "itsupport.json").read_text()
    for bad in ({**STEP, "id": "tickets"}, {**STEP, "how": []}, {**STEP, "tool": {"label": "x", "href": None, "tab": "nope"}}):
        assert refused(run, ["add-step", "itsupport"], bad), bad
    assert (d / "manuals" / "itsupport.json").read_text() == before
    qbefore = (d / "quizzes" / "itsupport.json").read_text()
    for bad in ({**QUESTION, "step": "no-such"}, {**QUESTION, "answer": 4}, {**QUESTION, "options": ["a", "a", "b", "c"]}):
        assert refused(run, ["add-question", "itsupport"], bad), bad
    assert (d / "quizzes" / "itsupport.json").read_text() == qbefore


def test_add_note_and_tool(cli):
    run, d = cli
    assert run(["add-note"], {"tracks": ["network"], "text": "NEW TOPIC: a fact."}) == 0
    notes = json.loads((d / "agent_notes.json").read_text())
    assert notes[-1]["id"] == f"n{len(notes):03d}" and notes[-1]["topic"]
    assert run(["add-note"], {"tracks": ["nope"], "text": "x"}) == 1
    cat = next(iter(json.loads((d / "toolmap.json").read_text())))
    assert run(["add-tool", cat], {"tool": "T", "status": "built", "where": "w", "note": "n"}) == 0
    assert refused(run, ["add-tool", cat], {"tool": "T", "status": "weird", "where": "w", "note": "n"})


def test_loader_errors_name_the_file_and_item(tmp_path, monkeypatch):
    d = tmp_path / "c"
    shutil.copytree(content.DIR, d)
    monkeypatch.setattr(content, "DIR", d)
    content.load_manuals.cache_clear()
    p = d / "manuals" / "pm.json"
    m = json.loads(p.read_text())
    m["steps"][1]["how"] = "not a list"
    p.write_text(json.dumps(m))
    with pytest.raises(content.ContentError, match=r"manuals/pm.json step #2"):
        content.load_manuals()
    p.write_text("{ broken")
    content.load_manuals.cache_clear()
    with pytest.raises(content.ContentError, match="not valid JSON"):
        content.load_manuals()
    content.load_manuals.cache_clear()
