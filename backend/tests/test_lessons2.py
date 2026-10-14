import pytest

from app.services import courses as co, known_errors, leadership as le, survey_stats as ss


def test_proportion_and_small_group_note():
    r = ss.proportion(57, 150)
    assert r["low"] < 57 < r["high"] and abs(r["worst_case_plus_minus_points"] - 8.0) < 0.1
    assert ss.proportion(50, 30)["notes"]
    for bad in ((101, 10), (50, 1), (-1, 10)):
        with pytest.raises(ss.SurveyError):
            ss.proportion(*bad)
    with pytest.raises(ss.SurveyError):
        ss.proportion(50, 100, 80)


def test_compare_and_sample_size():
    assert ss.compare(57, 150, 44, 150)["likely_real"]
    assert not ss.compare(52, 40, 44, 40)["likely_real"]
    assert any("small" in n for n in ss.compare(44, 40, 16, 40)["notes"])
    assert ss.sample_size(8)["needed"] == 151
    assert ss.sample_size(4)["needed"] > 3.9 * ss.sample_size(8)["needed"]
    with pytest.raises(ss.SurveyError):
        ss.sample_size(0)


def test_multi_select_and_joint():
    assert "more than one" in ss.multi_select(ss.SAMPLE["multi"])["verdict"]
    assert "one choice" in ss.multi_select("a | 60\nb | 40")["verdict"]
    j = ss.joint(ss.SAMPLE["joint"])
    assert j["marginal_x"] == {"0": 0.3, "1": 0.7} and not j["independent"]
    assert ss.joint("0|0|0.25\n0|1|0.25\n1|0|0.25\n1|1|0.25")["independent"]
    for bad in ("0|0|0.5\n0|1|0.5", "a|b|0.5\na|c|0.2\nd|b|0.2\nd|c|0.2", "0|0|0.1\n0|0|0.1\n1|0|0.4\n1|1|0.4", "x"):
        with pytest.raises(ss.SurveyError):
            ss.joint(bad)


def test_courses_list_duplicates_and_progress(client):
    assert len(co.COURSES) == 60 and co.duplicates()[0]["ids"] == [32, 54]
    assert sum(1 for c in co.COURSES if c["provider"] in ("Udacity", "Udemy")) == 30
    assert client.put("/api/courses/5", json={"done": True}).json()["done"] == [5]
    assert client.get("/api/courses").json()["done_count"] == 1
    assert client.put("/api/courses/99", json={"done": True}).status_code == 404
    assert client.get("/api/courses/path/genai-builder").json()["steps"][0]["order"] == 1
    assert client.get("/api/courses/path/nope").status_code == 404
    assert client.get("/api/courses?q=kaggle").json()["count"] == 8


def test_leadership_review():
    r = le.review({"focus": [5, 5, 5], "team": [2, 3, 3], "execute": [3, 3, 3]})
    assert r["focus_first"]["id"] == "team" and r["focus_first"]["weakest_behaviour"] == "Hire for potential and values"
    for bad in ({}, {"zz": [1, 1, 1]}, {"focus": [1, 2]}, {"focus": [0, 3, 3]}):
        with pytest.raises(le.LeaderError):
            le.review(bad)


def test_endpoints_and_slips(client):
    assert client.post("/api/surveystats/compare", json={"percent1": 57, "n1": 150, "percent2": 44, "n2": 150}).status_code == 200
    assert client.post("/api/surveystats/joint", json={"text": "bad"}).status_code == 400
    assert client.post("/api/leadership/review", json={"ratings": {"focus": [3, 3, 3]}}).status_code == 200
    for m in ("survey_stats", "courses", "leadership"):
        assert m in known_errors.SOURCES
