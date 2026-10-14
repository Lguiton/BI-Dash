"""A short checkpoint quiz at the end of each discipline's manual.

The questions test the ideas behind the steps, not button-clicking. The answers stay on the server: the page only gets the
questions, and grading happens here, with an explanation for every question (right or wrong). 80% passes.
Your best score per discipline is saved with your study progress.
"""
from __future__ import annotations

import json

from app.services import content, manuals, state

PASS_PCT = 80


def Q(step, q, options, answer, why):
    return {"step": step, "q": q, "options": options, "answer": answer, "why": why}


QUIZZES: dict[str, list[dict]] = content.load_quizzes()   # content/quizzes/<track>.json, checked when loaded


def _spread() -> None:
    """Rotate each question's options by a fixed, per-question amount so the right answer is not always in the same slot."""
    for t, qs in QUIZZES.items():
        for i, q in enumerate(qs):
            k = (i * 3 + len(t)) % 4
            if k:
                q["options"] = q["options"][k:] + q["options"][:k]
                q["answer"] = (q["answer"] - k) % 4


_spread()


class QuizError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _results() -> dict:
    raw = state.kv_get("quiz_results")
    return json.loads(raw) if raw else {}


def get(track: str) -> dict:
    qs = QUIZZES.get(track)
    if not qs:
        raise QuizError("No quiz for that discipline.", 404)
    steps = {s["id"]: s["title"] for s in manuals.MANUALS[track]["steps"]}
    res = _results().get(track)
    return {"track": track, "pass_pct": PASS_PCT, "result": res,
            "questions": [{"id": i, "step": q["step"], "step_title": steps.get(q["step"], ""), "q": q["q"], "options": q["options"]} for i, q in enumerate(qs)]}


def submit(track: str, answers) -> dict:
    qs = QUIZZES.get(track)
    if not qs:
        raise QuizError("No quiz for that discipline.", 404)
    if not isinstance(answers, list) or len(answers) != len(qs):
        raise QuizError(f"Answer all {len(qs)} questions.")
    graded, right = [], 0
    for i, (q, a) in enumerate(zip(qs, answers)):
        if not isinstance(a, int) or isinstance(a, bool) or not 0 <= a < len(q["options"]):
            raise QuizError(f"Question {i + 1} needs one of the listed answers.")
        ok = a == q["answer"]
        right += ok
        graded.append({"id": i, "ok": ok, "picked": a, "correct": q["answer"], "why": q["why"], "step": q["step"]})
    pct = round(100 * right / len(qs))
    allr = _results()
    prev = allr.get(track, {})
    cur = {"best_pct": max(pct, prev.get("best_pct", 0)), "last_pct": pct, "attempts": prev.get("attempts", 0) + 1, "passed": pct >= PASS_PCT or prev.get("passed", False),
           "last_at": state.now(), "missed_steps": sorted({g["step"] for g in graded if not g["ok"]})}
    allr[track] = cur
    state.kv_set("quiz_results", json.dumps(allr))
    state.audit("quiz", f"{track}: {right}/{len(qs)}")
    from app.services import review
    review.record_quiz(track, graded)
    return {"track": track, "score": right, "total": len(qs), "pct": pct, "passed_now": pct >= PASS_PCT, "result": cur, "graded": graded,
            "review": [g["step"] for g in graded if not g["ok"]]}
