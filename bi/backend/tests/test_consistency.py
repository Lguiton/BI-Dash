from app.services import agents, consistency as c, known_errors as ke


def test_content_is_consistent_now():
    r = c.run()
    bad = [f for f in r["findings"] if f["level"] != "info"]
    assert not bad, bad[:5]


def test_fact_rules_catch_real_wrong_claims():
    import re
    wrong = {"tacacs-1993": "TACACS+ is an open standard released in 1993.", "hash-never-collide": "A good hash never produces the same output twice.",
             "fde-integrity": "Full-disk encryption gives confidentiality and integrity.", "raid-backup": "RAID is a backup.",
             "degauss-ssd": "Degaussing works on SSDs.", "wep-secure": "WEP is secure.", "lb-ddos": "A load balancer protects against DDoS.",
             "gpo-order": "Precedence is site, domain, OU."}
    for rid, pat, _ in c.FACT_RULES:
        assert re.search(pat, wrong[rid], re.I | re.S), rid
        assert not c.CORRECTION.search(wrong[rid]), rid


def test_corrections_are_not_flagged():
    assert c.CORRECTION.search("RAID is not a backup.")
    assert c.CORRECTION.search("The course says WEP is secure.")


def test_a_broken_quiz_step_is_reported(monkeypatch):
    from app.services import quizzes
    monkeypatch.setitem(quizzes.QUIZZES, "pm", quizzes.QUIZZES["pm"] + [quizzes.Q("no-such-step", "Q?", ["a", "b", "c", "d"], 0, "x")])
    assert any(f["check"] == "quiz-step" and "no-such-step" in f["message"] for f in c.run()["findings"])


def test_registry_collects_notes_and_matches_by_topic():
    assert len(ke.all_items()) > 80
    t = ke.prompt_text("itsupport", "Is TACACS+ an open standard from 1993?")
    assert "RFC 8907" in t
    assert ke.prompt_text("itsupport", "what is the capital of France") == ""
    assert all(it["tracks"] for it in ke.public())


def test_agent_prompt_gets_only_matching_corrections(client):
    from tests.test_manuals_agents import Turn, run
    _, f = run("itsupport", [Turn("ok")], "Is TACACS+ an open standard from 1993?")
    assert "KNOWN SOURCE MISTAKES" in f.system and "RFC 8907" in f.system
    _, g = run("itsupport", [Turn("ok")], "How do I reset a user password?")
    assert "KNOWN SOURCE MISTAKES" not in g.system


def test_endpoints(client):
    assert client.get("/api/consistency").json()["errors"] == 0
    assert client.get("/api/known-errors?track=network").json()["count"] > 10


def test_every_manual_step_has_a_quiz_question():
    gaps = [f["where"] for f in c.run()["findings"] if f["check"] == "quiz-coverage"]
    assert not gaps, gaps[:5]
