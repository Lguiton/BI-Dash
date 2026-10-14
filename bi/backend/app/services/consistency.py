"""Cross-checks between the pieces of the learning system that are written by hand and can drift apart.

Checks (each finding has a level: error = broken, warn = probably wrong, info = worth a look):
  * every quiz question points at a real manual step; every manual step has a question (info if not)
  * every manual step opens a tab that exists
  * the tool map uses known statuses, has no duplicate rows, and links only to local pages
  * nobody repeats, in a manual, quiz, tool map row or agent note, a claim that a source-mistake note calls wrong
  * hand-written rules for claims we know are wrong (FACT_RULES)
  * the same quiz question written twice
Run from the command line with scripts/check_consistency.py, or read it through /api/consistency.
"""
from __future__ import annotations

import re
from collections import Counter

from app.services import agents, known_errors, manuals, quizzes, toolmap

# (id, pattern, why it is wrong). Patterns are matched case-insensitively on the text of manuals, quizzes, tool map and agent notes.
FACT_RULES: list[tuple[str, str, str]] = [
    ("tacacs-1993", r"tacacs\+?[^.]{0,60}open standard[^.]{0,40}1993", "TACACS+ is Cisco-originated; RFC 8907 (2020) is informational. 1993 is older TACACS."),
    ("hash-never-collide", r"never (?:produce|give|return)s? the same (?:hash|output)", "Collisions must exist; a good hash makes finding one infeasible."),
    ("fde-integrity", r"full[- ]disk encryption[^.]{0,60}\bintegrity\b", "Full-disk encryption protects confidentiality, not integrity."),
    ("raid-backup", r"raid (?:is|as) (?:a )?backup", "RAID is availability, not a backup."),
    ("degauss-ssd", r"degauss(?:ing)? (?:works|is effective) (?:on|for) (?:ssd|flash)", "Degaussing does not work on SSDs or flash."),
    ("wep-secure", r"wep (?:is|remains) (?:secure|safe)", "WEP is broken."),
    ("lb-ddos", r"load balancers? (?:protects?|guards?|defends?)[^.]{0,30}ddos", "A load balancer is not a DDoS defence."),
    ("gpo-order", r"(?<!local, )(?<!local )site,? domain,? (?:and )?ou", "Local policy applies first; Enforced and Block Inheritance can reverse the order."),
]
# A sentence that says the claim is wrong is a correction, not an echo.
CORRECTION = re.compile(r"\b(?:not|isn't|doesn't|does not|do not|don't|no|wrong|mistake|myth|impossible|cannot|can't|only a|rather than|instead of|course says|poster|slips?|claims?|deprecated|true only|exists only|a convention|unsourced|vendor|dated)\b|\bnor\b", re.I)
STATUSES = {"built", "partial", "taught", "not_embedded"}


def _f(level, check, where, message):
    return {"level": level, "check": check, "where": where, "message": message}


def corpus() -> list[tuple[str, str]]:
    """(where, text) for every hand-written piece that states facts. Source-mistake notes and each step's list of beginner mistakes are left out: they state wrong things on purpose."""
    out: list[tuple[str, str]] = []
    for t, m in manuals.MANUALS.items():
        for s in m["steps"]:
            out.append((f"manual {t}/{s['id']}", " ".join([s["title"], s["what"], *s["how"], s["done_when"], s["ask"]])))
    for t, qs in quizzes.QUIZZES.items():
        for i, q in enumerate(qs):
            out.append((f"quiz {t}#{i}", " ".join([q["q"], *q["options"], q["why"]])))
    for g, rows in toolmap.MAP.items():
        for r in rows:
            out.append((f"toolmap {g}: {r['tool'][:40]}", f"{r['tool']} {r['note']}"))
    for t, a in agents.AGENTS.items():
        out.append((f"agent {t}", a["knows"]))
    return out


def _sentences(text: str) -> list[str]:
    return [x for x in re.split(r"(?<=[.!?;])\s+|\n+", text) if x.strip()]


def _quotes(text: str) -> list[str]:
    """Quoted phrases inside a source-mistake note: 'like this' or "like this" of 14+ characters."""
    found = re.findall(r"'([^']{14,160})'|\"([^\"]{14,160})\"", text)
    return [a or b for a, b in found]


def run() -> dict:
    out: list[dict] = []
    # 1. quiz <-> manual
    for t, qs in quizzes.QUIZZES.items():
        ids = {s["id"] for s in manuals.MANUALS[t]["steps"]}
        for i, q in enumerate(qs):
            if q["step"] not in ids:
                out.append(_f("error", "quiz-step", f"quiz {t}#{i}", f"Question points at step '{q['step']}', which is not in the {t} manual."))
        covered = {q["step"] for q in qs}
        for s in manuals.MANUALS[t]["steps"]:
            if s["id"] not in covered:
                out.append(_f("info", "quiz-coverage", f"manual {t}/{s['id']}", "No quiz question tests this step."))
    # 2. tabs
    for t, m in manuals.MANUALS.items():
        for s in m["steps"]:
            tab = (s["tool"] or {}).get("tab")
            if tab and tab not in manuals.VALID_TABS.get(t, set()):
                out.append(_f("error", "tab", f"manual {t}/{s['id']}", f"Opens tab '{tab}', which {t} does not have."))
    # 3. tool map
    seen = Counter()
    for g, rows in toolmap.MAP.items():
        for r in rows:
            seen[r["tool"]] += 1
            if r["status"] not in STATUSES:
                out.append(_f("error", "toolmap-status", f"toolmap {g}: {r['tool'][:40]}", f"Unknown status '{r['status']}'."))
            if r["href"] and not str(r["href"]).startswith("/"):
                out.append(_f("warn", "toolmap-href", f"toolmap {g}: {r['tool'][:40]}", f"Link '{r['href']}' is not a local page."))
    for name, n in seen.items():
        if n > 1:
            out.append(_f("warn", "toolmap-duplicate", f"toolmap: {name[:50]}", f"Listed {n} times."))
    # 4. facts and echoed mistakes
    docs = corpus()
    for rid, pat, why in FACT_RULES:
        rx = re.compile(pat, re.I | re.S)
        for where, text in docs:
            for sent in _sentences(text):
                if rx.search(sent) and not CORRECTION.search(sent):
                    out.append(_f("error", f"fact:{rid}", where, why))
                    break
    for it in known_errors.all_items():
        for qte in _quotes(it["text"]):
            needle = qte.lower()
            for where, text in docs:
                hit = next((x for x in _sentences(text) if needle in x.lower()), None)
                if hit and not CORRECTION.search(hit.lower().replace(needle, "")):
                    out.append(_f("warn", "echoed-mistake", where, f"Repeats a claim a source-mistake note calls wrong: “{qte[:80]}” ({it['id']})."))
    # 5. duplicate questions
    qs_seen: dict[str, str] = {}
    for t, qs in quizzes.QUIZZES.items():
        for i, q in enumerate(qs):
            key = re.sub(r"\W+", " ", q["q"].lower()).strip()
            if key in qs_seen:
                out.append(_f("info", "quiz-duplicate", f"quiz {t}#{i}", f"Same question as {qs_seen[key]}."))
            else:
                qs_seen[key] = f"quiz {t}#{i}"
    counts = Counter(x["level"] for x in out)
    return {"errors": counts["error"], "warnings": counts["warn"], "info": counts["info"], "findings": out,
            "checked": {"manual_steps": sum(len(m["steps"]) for m in manuals.MANUALS.values()), "quiz_questions": sum(len(q) for q in quizzes.QUIZZES.values()),
                        "toolmap_rows": sum(len(r) for r in toolmap.MAP.values()), "source_notes": len(known_errors.all_items()), "fact_rules": len(FACT_RULES)}}
