"""Five leadership disciplines: a self-review that finds the weakest one and what to do about it.

From an infographic titled "The 5 Disciplines of Strategic Leadership", credited to The Modern Monkey and shown with a Harvard Business
School logo, but described as only "inspired by" HBS research. It is not an official HBS framework. The rating scale and thresholds here
are my own; the infographic gives none.
"""
from __future__ import annotations


class LeaderError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


DISCIPLINES = [
    ("focus", "Sustain a focus on the big picture", "Clarify where to play and how to win.",
     ["Articulate a compelling vision", "Make strategic trade-offs", "Align the organization"], ["Clear direction", "Better decisions", "Stronger alignment"],
     "Write one page: what we will do, what we will stop, and who must agree. Count the things you said no to this quarter."),
    ("team", "Build and engage the right team", "Results come from the right mix of talent, trust and diversity.",
     ["Hire for potential and values", "Build trust and psychological safety", "Develop people relentlessly"], ["Higher performance", "Greater retention", "Stronger bench strength"],
     "Ask each person one question in a 1:1: what did you hold back this month, and why? Name a successor for each key role."),
    ("challenge", "Challenge the status quo", "Breakthroughs need curiosity, courage and constructive dissent.",
     ["Encourage diverse perspectives", "Ask better questions", "Promote intelligent risk-taking"], ["More innovation", "Better problem solving", "Adaptive organization"],
     "Before the next decision, ask someone to argue the opposite. Record what was risked and what was learned from the last failure."),
    ("execute", "Drive execution with discipline", "Strategy without execution is just an idea.",
     ["Set clear priorities", "Establish cadence and accountability", "Track, learn and adapt"], ["Consistent progress", "Operational excellence", "Strong accountability"],
     "Cut your priorities to three. Fix a weekly review with named owners and dates, and publish what slipped."),
    ("value", "Create long-term value", "Sustainable value is built for all stakeholders.",
     ["Invest for the long term", "Manage risk and reputation", "Balance people, planet, profit"], ["Stronger stakeholder trust", "Resilient performance", "Enduring legacy"],
     "List one decision this year where short-term gain was given up. Name the top risk to reputation and who owns it."),
]


def framework() -> list[dict]:
    return [{"id": i, "name": n, "summary": s, "behaviours": b, "claimed_impact": im, "practice": p} for i, n, s, b, im, p in DISCIPLINES]


def review(ratings: dict) -> dict:
    """ratings: discipline id -> list of three scores 1 to 5, one per behaviour."""
    if not isinstance(ratings, dict):
        raise LeaderError("Send ratings as an object of discipline id to three scores.")
    ids = [d[0] for d in DISCIPLINES]
    bad = [k for k in ratings if k not in ids]
    if bad:
        raise LeaderError(f"Unknown discipline '{bad[0]}'.")
    out = []
    for i, n, _s, beh, _im, practice in DISCIPLINES:
        r = ratings.get(i)
        if r is None:
            continue
        if not isinstance(r, list) or len(r) != 3 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not 1 <= x <= 5 for x in r):
            raise LeaderError(f"'{i}' needs three scores from 1 to 5.")
        low = min(range(3), key=lambda k: r[k])
        out.append({"id": i, "name": n, "average": round(sum(r) / 3, 2), "weakest_behaviour": beh[low], "practice": practice})
    if not out:
        raise LeaderError("Rate at least one discipline.")
    out.sort(key=lambda d: d["average"])
    gap = round(out[-1]["average"] - out[0]["average"], 2)
    return {"ranked_weakest_first": out, "focus_first": out[0],
            "note": "Rate yourself against evidence (a decision, a date, a person), then ask two others to rate you. Self-ratings run high." + (" The spread is small: one practice at a time beats fixing all five." if gap < 1 else ""),
            "lesson": "Fix the weakest behaviour with one practice and a date, not five resolutions."}


SLIPS = [
    "5 Disciplines infographic: it carries a Harvard Business School logo and a quote labelled 'HBS Leadership Principle', yet the text says only 'inspired by research and teaching at HBS' and credits a third party (The Modern Monkey). It is not an HBS publication, and the quote cannot be traced to one. Treat it as a summary of common advice.",
    "5 Disciplines infographic: the 'Leadership Impact' column (better decisions, higher retention, more innovation) is stated as a result with no study, size of effect or source. Each is a hope, not a finding.",
    "5 Disciplines infographic: 'Great organizations compound the impact' is a claim, not a measure. The graphic gives nothing to measure any of the five disciplines, so you cannot tell whether you are improving.",
    "5 Disciplines infographic: the disciplines overlap (long-term value includes managing risk, which also sits in execution) and 'balance people, planet, profit' has no way to settle a trade-off. Decide what wins when they conflict.",
]
NOT_BUILT = ["Leading people. This only organises a self-review; behaviour change needs practice and feedback from other people."]


def reference() -> dict:
    return {"framework": framework(), "slips": SLIPS, "not_built": NOT_BUILT}
