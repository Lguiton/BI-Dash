from datetime import date, timedelta

import pytest

from app.services import quizzes, review


@pytest.fixture()
def day(monkeypatch):
    box = {"d": date(2026, 10, 12)}
    monkeypatch.setattr(review, "_today", lambda: box["d"])
    return box


def _answer(card, right=True):
    d = review._deck()[card["id"]]
    pick = d["answer"] if right else (d["answer"] + 1) % len(d["options"])
    return review.answer(card["id"], pick)


def test_new_cards_are_mixed_across_tracks_and_hide_answers(client, day):
    s = review.session(8)
    assert s["n"] == 8 and len({c["track"] for c in s["cards"]}) > 3
    assert all(c["kind"] == "new" and "answer" not in c and "why" not in c for c in s["cards"])


def test_right_answer_moves_up_boxes_and_returns_later(client, day):
    c = review.session(1)["cards"][0]
    r = _answer(c)
    assert r["ok"] and r["box"] == 1 and r["next_in_days"] == 1
    assert c["id"] not in [x["id"] for x in review.session(30)["cards"] if x["kind"] == "due"]
    day["d"] += timedelta(days=1)
    due = [x for x in review.session(30)["cards"] if x["kind"] == "due"]
    assert [x["id"] for x in due] == [c["id"]]
    assert _answer(c)["next_in_days"] == 3


def test_wrong_answer_resets_to_due_today(client, day):
    c = review.session(1)["cards"][0]
    _answer(c)
    day["d"] += timedelta(days=1)
    r = _answer(c, right=False)
    assert not r["ok"] and r["box"] == 0 and r["next"] == "back later today"
    assert c["id"] in [x["id"] for x in review.session(5)["cards"] if x["kind"] == "due"]


def test_validation(client, day):
    with pytest.raises(review.ReviewError):
        review.session(0)
    with pytest.raises(review.ReviewError):
        review.session(5, "nope")
    c = review.session(1)["cards"][0]
    for bad in (9, -1, True, "1"):
        with pytest.raises(review.ReviewError):
            review.answer(c["id"], bad)
    with pytest.raises(review.ReviewError):
        review.answer("zzzz", 0)


def test_streak_counts_consecutive_days_and_breaks(client, day):
    c = review.session(1)["cards"][0]
    for _ in range(3):
        _answer(c)
        day["d"] += timedelta(days=1)
    assert review.streak() == {"days": 3, "today_done": False}
    day["d"] += timedelta(days=1)
    assert review.streak()["days"] == 0


def test_full_quiz_feeds_cards_and_weak_spots(client, day):
    qs = quizzes.QUIZZES["itsupport"]
    wrong = [(q["answer"] + 1) % 4 for q in qs]
    client.post("/api/quizzes/itsupport", json={"answers": wrong})
    s = review.summary()
    row = next(t for t in s["tracks"] if t["track"] == "itsupport")
    assert row["seen"] == len(qs) and row["due"] == len(qs) and row["accuracy_pct"] == 0
    assert s["weak"] and s["weak"][0]["accuracy_pct"] == 0
    # a session restricted to that track returns its due cards first
    sess = review.session(5, "itsupport")
    assert all(c["kind"] == "due" for c in sess["cards"])


def test_started_tracks_are_preferred_for_new_cards(client, day):
    client.put("/api/manuals/pm/steps/okr", json={"done": True})
    s = review.session(6)
    assert {c["track"] for c in s["cards"]} == {"pm"}


def test_endpoints(client, day):
    assert client.get("/api/review/summary").status_code == 200
    cards = client.get("/api/review/session?n=3").json()["cards"]
    assert len(cards) == 3
    r = client.post("/api/review/answer", json={"id": cards[0]["id"], "picked": 0})
    assert r.status_code == 200 and "why" in r.json()
    assert client.post("/api/review/answer", json={"id": "nope", "picked": 0}).status_code == 404
    assert client.get("/api/review/session?n=99").status_code == 400
    assert client.get("/api/review/weak").status_code == 200
