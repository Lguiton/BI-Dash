"""A one-page portfolio of what you have actually done, per track, plus case-study notes you write yourself.

Evidence is labelled by how it is known:
  * quiz passed          graded by the server (80% or better)
  * review accuracy      graded by the server, from the spaced-review cards
  * steps ticked         your own record; the app does not verify it
  * case studies         your own words
Nothing here is invented. If you have done nothing in a track, the page says so instead of listing skills.
"""
from __future__ import annotations

import json
import re
import uuid

from app.services import agents, manuals, quizzes, review, state

FIELDS = ("title", "problem", "actions", "result", "skills")
LIMITS = {"title": 120, "problem": 1500, "actions": 2000, "result": 1500, "skills": 300}
MAX_CASES = 60


class PortfolioError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _load(key, default):
    raw = state.kv_get(key)
    return json.loads(raw) if raw else default


def _cases() -> list[dict]:
    return _load("case_studies", [])


def _label(track: str) -> str:
    return manuals.MANUALS[track]["title"].split(":")[0].strip()


def prompts(track: str) -> list[str]:
    """Starter ideas for case studies, from the steps you ticked."""
    done = set(_load("manual_done", {}).get(track, []))
    out = []
    for s in manuals.MANUALS[track]["steps"]:
        if s["id"] in done:
            out.append(f"{s['title']}: what was the situation, what did you do, and what was the outcome? Use the tool and say what you checked.")
    return out[:6]


def _clean(b: dict) -> dict:
    if not isinstance(b, dict):
        raise PortfolioError("Send the case study as an object.")
    track = b.get("track")
    if track not in manuals.MANUALS:
        raise PortfolioError("Pick a discipline.")
    c = {"track": track}
    for f in FIELDS:
        v = str(b.get(f, "")).strip()
        if len(v) > LIMITS[f]:
            raise PortfolioError(f"{f.capitalize()} is limited to {LIMITS[f]} characters.")
        c[f] = v
    if not c["title"]:
        raise PortfolioError("Give the case study a title.")
    if not (c["problem"] or c["actions"] or c["result"]):
        raise PortfolioError("Write at least the problem, what you did, or the result.")
    return c


def cases(track: str | None = None) -> list[dict]:
    return [c for c in _cases() if not track or c["track"] == track]


def add_case(b: dict) -> dict:
    allc = _cases()
    if len(allc) >= MAX_CASES:
        raise PortfolioError(f"You can keep up to {MAX_CASES} case studies. Delete one first.")
    c = {"id": uuid.uuid4().hex[:8], **_clean(b), "at": state.now()}
    allc.append(c)
    state.kv_set("case_studies", json.dumps(allc))
    return c


def update_case(cid: str, b: dict) -> dict:
    allc = _cases()
    i = next((k for k, c in enumerate(allc) if c["id"] == cid), None)
    if i is None:
        raise PortfolioError("No such case study.", 404)
    allc[i] = {**allc[i], **_clean({**allc[i], **b}), "updated": state.now()}
    state.kv_set("case_studies", json.dumps(allc))
    return allc[i]


def delete_case(cid: str) -> dict:
    allc = _cases()
    keep = [c for c in allc if c["id"] != cid]
    if len(keep) == len(allc):
        raise PortfolioError("No such case study.", 404)
    state.kv_set("case_studies", json.dumps(keep))
    return {"deleted": cid}


def build() -> dict:
    done_all = _load("manual_done", {})
    qres = _load("quiz_results", {})
    rev = {r["track"]: r for r in review.summary()["tracks"]}
    cs = _cases()
    tracks = []
    for t, m in manuals.MANUALS.items():
        steps = m["steps"]
        done_ids = set(done_all.get(t, []))
        q = qres.get(t)
        r = rev.get(t, {})
        done_steps = [s["title"] for s in steps if s["id"] in done_ids]
        mine = [c for c in cs if c["track"] == t]
        active = bool(done_steps or q or r.get("seen") or mine)
        tracks.append({
            "track": t, "name": _label(t), "outcome": m["outcome"], "active": active,
            "steps_done": len(done_steps), "steps_total": len(steps), "steps": done_steps,
            "quiz": ({"best_pct": q["best_pct"], "attempts": q["attempts"], "passed": q["passed"], "pass_pct": quizzes.PASS_PCT} if q else None),
            "review": ({"seen": r["seen"], "mastered": r["mastered"], "accuracy_pct": r["accuracy_pct"]} if r.get("seen") else None),
            "cases": mine,
        })
    act = [t for t in tracks if t["active"]]
    return {"tracks": tracks, "active": len(act), "quizzes_passed": sum(1 for t in act if t["quiz"] and t["quiz"]["passed"]),
            "steps_done": sum(t["steps_done"] for t in tracks), "cases": len(cs), "streak": review.streak()["days"],
            "note": "Steps are ticked by you and not verified. Quiz and review results are graded by the app."}


def _md(s: str) -> str:
    return re.sub(r"([\\`*_{}\[\]<>#|])", r"\\\1", s)


def markdown(track: str | None = None) -> str:
    p = build()
    rows = [t for t in p["tracks"] if t["active"] and (not track or t["track"] == track)]
    if track and track not in manuals.MANUALS:
        raise PortfolioError("No such discipline.", 404)
    out = ["# Skills portfolio", "",
           f"{p['steps_done']} practice steps completed across {p['active']} discipline(s); {p['quizzes_passed']} quiz(zes) passed at {quizzes.PASS_PCT}% or better; {p['cases']} case stud{'y' if p['cases'] == 1 else 'ies'}.", "",
           "_Steps are my own record. Quiz and review scores were graded by the practice app. Case studies are in my own words._", ""]
    if not rows:
        out += ["No activity yet in " + (_label(track) if track else "any discipline") + ".", ""]
    for t in rows:
        out += [f"## {_md(t['name'])}", "", f"_{_md(t['outcome'])}_", ""]
        out.append(f"- Practice steps completed: {t['steps_done']} of {t['steps_total']}")
        if t["quiz"]:
            q = t["quiz"]
            out.append(f"- Knowledge check: best {q['best_pct']}% in {q['attempts']} attempt(s), " + ("passed" if q["passed"] else f"not yet at the {q['pass_pct']}% pass mark"))
        if t["review"]:
            r = t["review"]
            out.append(f"- Spaced review: {r['seen']} questions seen, {r['mastered']} mastered" + (f", {r['accuracy_pct']}% correct" if r["accuracy_pct"] is not None else ""))
        out.append("")
        if t["steps"]:
            out += ["**Practised**", ""] + [f"- {_md(x)}" for x in t["steps"]] + [""]
        for c in t["cases"]:
            out += [f"### {_md(c['title'])}", ""]
            for lab, key in (("Situation", "problem"), ("What I did", "actions"), ("Result", "result")):
                if c[key]:
                    out += [f"**{lab}.** {_md(c[key])}", ""]
            if c["skills"]:
                out += [f"**Skills:** {_md(c['skills'])}", ""]
    return "\n".join(out).rstrip() + "\n"
