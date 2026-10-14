# Where the learning content lives, and how to change it

The manuals, quiz questions, agent notes and tool map are data, not code. They live in `backend/app/content/`:

| File | What it holds |
|---|---|
| `index.json` | The order of the eleven tracks |
| `manuals/<track>.json` | Title, intro, outcome and the ordered steps |
| `quizzes/<track>.json` | The checkpoint questions (each points at a step) |
| `agent_notes.json` | What each agent knows. One note can serve several tracks |
| `toolmap.json` | The tool map rows, grouped by category |

Everything is checked when the app starts. A typo (a missing field, a duplicate step id, an answer number that does not exist, a quiz question pointing at a step that is not there) stops the app with a message that names the file and the item.

## Adding to it

```
python scripts/content.py validate
python scripts/content.py stats                       # steps, questions, notes; steps with no question
python scripts/content.py add-step itsupport --after tickets < step.json
python scripts/content.py add-question itsupport < question.json
python scripts/content.py add-note < note.json        # {"topic": "...", "tracks": ["network", "security"], "text": "TOPIC: ..."}
python scripts/content.py add-tool "Cybersecurity" < row.json
```

A step opens a tab on its dashboard. A new tab must be added to `VALID_TABS` in `services/manuals.py` and to the panel first; the command refuses unknown tabs.

## Checking it

`python scripts/check_consistency.py` cross-checks the pieces that are written by hand and can drift apart:

- every quiz question points at a real step, and every step has a question
- every step opens a tab that exists; every tool-map row has a known status and a local link
- nothing repeats a claim that a source-mistake note calls wrong (the notes live next to the code they affect and are gathered by `services/known_errors.py`)
- a short list of claims known to be wrong (`FACT_RULES`) does not appear in a manual, quiz, tool map row or agent note

When you correct a mistake once (in a lab module's `SLIPS` list), the agents see it: each time you ask an agent something, it is given the few corrections that match your question.

## One command for "is it ready?"

`python scripts/update.py` runs the content check, the consistency check, the quick tests and the frontend type check and lint. `--full` adds the slow tests, `--zip 19` writes `../bi_update19.zip` and runs the bundle safety check on it.

## Tests

`pytest -m "not slow"` is the quick tier. Tests that need the imported sample year use the `load_clean` fixture, which copies a database built once per run instead of importing the CSV each time (that import took about 8 seconds and 35 tests needed it).
