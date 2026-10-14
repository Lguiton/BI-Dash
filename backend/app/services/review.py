"""Spaced review: the quiz questions you miss come back, the ones you know come back later.

A Leitner scheme over the track quizzes. A right answer moves a question up one box (it returns after 1, 3, 7, 14, 30, 60 days);
a wrong answer sends it back to box 0 (due today). A session is the questions that are due, then new ones from tracks you have
started, mixed across tracks. Weak spots are the manual steps where your answers keep going wrong.
Taking a full track quiz feeds the same cards, so there is one memory of what you know.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

from app.services import manuals, quizzes, state

INTERVALS = [0, 1, 3, 7, 14, 30, 60]
MAX_SESSION = 30
WEAK_BELOW = 0.8


class ReviewError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _today() -> date:
    return date.today()


def cid(track: str, q: dict) -> str:
    return hashlib.sha1(f"{track}|{q['q']}".encode()).hexdigest()[:10]


def _deck() -> dict[str, dict]:
    out = {}
    for t, qs in quizzes.QUIZZES.items():
        steps = {s["id"]: s["title"] for s in manuals.MANUALS[t]["steps"]}
        for q in qs:
            out[cid(t, q)] = {"id": cid(t, q), "track": t, "step": q["step"], "step_title": steps.get(q["step"], q["step"]), "q": q["q"], "options": q["options"], "answer": q["answer"], "why": q["why"]}
    return out


def _load(key: str, default):
    raw = state.kv_get(key)
    return json.loads(raw) if raw else default


def _cards() -> dict:
    return _load("review_cards", {})


def _started() -> set[str]:
    done = _load("manual_done", {})
    res = _load("quiz_results", {})
    return {t for t, v in done.items() if v} | set(res)


def record(card_id: str, ok: bool, cards: dict | None = None, persist: bool = True) -> dict:
    """Update one card. Returns the card."""
    allc = cards if cards is not None else _cards()
    c = allc.get(card_id, {"box": 0, "right": 0, "wrong": 0, "due": _today().isoformat()})
    if ok:
        c["right"] += 1
        c["box"] = min(c["box"] + 1, len(INTERVALS) - 1)
    else:
        c["wrong"] += 1
        c["box"] = 0
    c["due"] = (_today() + timedelta(days=INTERVALS[c["box"]])).isoformat()
    c["last"] = _today().isoformat()
    allc[card_id] = c
    if persist:
        state.kv_set("review_cards", json.dumps(allc))
    return c


def record_quiz(track: str, graded: list[dict]) -> None:
    """Called by quizzes.submit so a full quiz and the daily review share one memory."""
    qs = quizzes.QUIZZES.get(track, [])
    allc = _cards()
    for g in graded:
        if 0 <= g["id"] < len(qs):
            record(cid(track, qs[g["id"]]), g["ok"], allc, persist=False)
    state.kv_set("review_cards", json.dumps(allc))
    _mark_day()


def _mark_day() -> None:
    days = set(_load("review_days", []))
    days.add(_today().isoformat())
    state.kv_set("review_days", json.dumps(sorted(days)[-400:]))


def streak() -> dict:
    days = {date.fromisoformat(d) for d in _load("review_days", [])}
    t = _today()
    cur = t if t in days else t - timedelta(days=1)
    n = 0
    while cur in days:
        n += 1
        cur -= timedelta(days=1)
    return {"days": n, "today_done": t in days}


def _is_due(c: dict) -> bool:
    return date.fromisoformat(c["due"]) <= _today()


def session(n: int = 10, track: str | None = None) -> dict:
    if not isinstance(n, int) or not 1 <= n <= MAX_SESSION:
        raise ReviewError(f"Ask for between 1 and {MAX_SESSION} questions.")
    deck, cards = _deck(), _cards()
    if track and track not in quizzes.QUIZZES:
        raise ReviewError("No quiz for that discipline.", 404)
    ok = lambda d: not track or d["track"] == track  # noqa: E731
    due = sorted((d for i, d in deck.items() if i in cards and _is_due(cards[i]) and ok(d)), key=lambda d: (cards[d["id"]]["due"], d["id"]))
    picked = [dict(d, kind="due") for d in due[:n]]
    if len(picked) < n:
        started = _started()
        tracks = [t for t in quizzes.QUIZZES if (not track or t == track) and (t in started or not started or track)]
        new_by_track = {t: [d for i, d in deck.items() if d["track"] == t and i not in cards] for t in tracks}
        queues = [q for q in new_by_track.values() if q]
        k = 0
        while queues and len(picked) < n:
            q = queues[k % len(queues)]
            picked.append(dict(q.pop(0), kind="new"))
            queues = [x for x in queues if x]
            k += 1
    for p in picked:
        p.pop("answer"), p.pop("why")
    return {"cards": picked, "due_total": len(due), "n": len(picked)}


def answer(card_id: str, picked) -> dict:
    d = _deck().get(card_id)
    if not d:
        raise ReviewError("No such question.", 404)
    if not isinstance(picked, int) or isinstance(picked, bool) or not 0 <= picked < len(d["options"]):
        raise ReviewError("Pick one of the listed answers.")
    ok = picked == d["answer"]
    c = record(card_id, ok)
    _mark_day()
    days = INTERVALS[c["box"]]
    return {"ok": ok, "correct": d["answer"], "why": d["why"], "box": c["box"], "next_in_days": days,
            "next": "back later today" if days == 0 else f"back in {days} day{'s' if days != 1 else ''}"}


def weak_spots(limit: int = 12) -> list[dict]:
    deck, cards = _deck(), _cards()
    per: dict[tuple[str, str], dict] = {}
    for i, c in cards.items():
        d = deck.get(i)
        if not d:
            continue
        s = per.setdefault((d["track"], d["step"]), {"track": d["track"], "step": d["step"], "step_title": d["step_title"], "right": 0, "wrong": 0})
        s["right"] += c["right"]
        s["wrong"] += c["wrong"]
    quiz_missed = {(t, s) for t, r in _load("quiz_results", {}).items() for s in r.get("missed_steps", [])}
    out = []
    for (t, st), s in per.items():
        n = s["right"] + s["wrong"]
        acc = s["right"] / n if n else 1
        if (n >= 2 and acc < WEAK_BELOW) or (s["wrong"] and (t, st) in quiz_missed):
            out.append({**s, "attempts": n, "accuracy_pct": round(100 * acc), "href": f"/tracks/{t}"})
    out.sort(key=lambda x: (x["accuracy_pct"], -x["wrong"]))
    return out[:limit]


def summary() -> dict:
    deck, cards = _deck(), _cards()
    started = _started()
    rows = []
    for t in quizzes.QUIZZES:
        ids = [i for i, d in deck.items() if d["track"] == t]
        seen = [cards[i] for i in ids if i in cards]
        r, w = sum(c["right"] for c in seen), sum(c["wrong"] for c in seen)
        rows.append({"track": t, "questions": len(ids), "seen": len(seen), "due": sum(1 for c in seen if _is_due(c)), "mastered": sum(1 for c in seen if c["box"] >= 4),
                     "accuracy_pct": round(100 * r / (r + w)) if r + w else None, "started": t in started})
    due = sum(r["due"] for r in rows)
    new = sum(r["questions"] - r["seen"] for r in rows if r["started"] or not started)
    return {"due": due, "new_available": new, "streak": streak(), "tracks": rows, "weak": weak_spots(5),
            "daily": f"{due} due" + (f" and {min(new, 10 - min(due, 10))} new" if due < 10 and new else "") if (due or new) else "Nothing due. Come back tomorrow."}
