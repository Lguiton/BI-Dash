"""Ticket-writing coach: does this ticket give the next person what they need to act on it?

Two checks:
  * report      a new ticket (what is wrong) - nine things a technician asks about first
  * resolution  the closing note (what fixed it) - so the next person with the same problem can find the answer
Plus a priority suggestion from impact and urgency.

It looks for the presence of each kind of information with word patterns. It cannot judge whether the information is true or
well chosen; treat the score as a prompt for what to ask, not a grade of the person.
"""
from __future__ import annotations

import re

VAGUE_TITLES = {"help", "broken", "issue", "problem", "urgent", "not working", "doesn't work", "does not work", "please fix", "fix", "error", "it's down", "its down", "down", "bug", "question", "request", "asap", "pc", "computer", "email", "internet", "printer"}


class CoachError(ValueError):
    pass


def _has(rx: str, text: str) -> bool:
    return re.search(rx, text, re.I) is not None


REPORT_CHECKS = [
    ("who", "Who is affected", 12, r"\b(everyone|everybody|all (?:of )?(?:us|users|staff)|only me|just me|only (?:one|a few|some)|some (?:users|people)|my (?:team|department|manager|laptop|pc|computer)|the (?:team|department|office|floor|sales|finance|hr)|users?\b|customers?|[2-9]\d* (?:people|users|staff))",
     "Who is affected: just you, a team, or everyone? Which user name and which machine?"),
    ("what", "What is wrong, specifically", 14, r"\b(cannot|can't|can not|won't|will not|unable|fails?|failed|crash(?:es|ed)?|freez(?:es|ing)|frozen|slow|error|blank|stuck|locked|missing|disconnect(?:s|ed)?|timeout|timed out|no (?:sound|signal|connection|access)|keeps?\b)",
     "What exactly happens, in words someone else can picture? Say what you expected and what you got instead."),
    ("when", "When it started", 10, r"\b(since|started|began|yesterday|today|this (?:morning|afternoon|week)|last (?:night|week|monday|tuesday|wednesday|thursday|friday)|at \d{1,2}(?::\d{2})?\s?(?:am|pm)?|\d{1,2}:\d{2}|ago|first time|always|suddenly|intermittent|every (?:day|time|hour))",
     "When did it start, and is it constant or does it come and go?"),
    ("change", "What changed", 10, r"\b(after (?:an? |the |my |our )?(?:\w+ ){0,2}?(?:update|upgrade|install|reboot|restart|move|password|patch|reset|change)|(?:updated|installed|moved|changed|reset|upgraded|new (?:laptop|pc|phone|password|printer|software))|nothing (?:has )?changed|no changes)",
     "Did anything change just before it began: an update, a new device, a password change, a move?"),
    ("error", "The exact error or message", 14, r"(\"[^\"]{4,}\"|'[^']{6,}'|error (?:code|message)?\s*[:#]?\s*\S+|0x[0-9a-f]{3,}|\bcode\s*[:#]?\s*\d+|\b(?:says|shows|displays|reads|message)\b|\b[45]\d\d\b)",
     "What does the message say, word for word? A screenshot or the exact error code saves a round of questions."),
    ("steps", "How to make it happen", 10, r"\b(when i|whenever i|if i|every time i|after i|(?:i )?(?:click|open|try|press|log ?in|sign ?in|print|send|save|connect|launch|start)\w*|steps?\b)",
     "What are you doing when it happens? Give the steps in order so someone can repeat them."),
    ("tried", "What you already tried", 10, r"\b(tried|restart(?:ed)?|reboot(?:ed)?|re-?install(?:ed)?|re-?start(?:ed)?|checked|ran|cleared|reset|power[- ]?cycled|turned (?:it )?off and on|swapped|different (?:cable|port|browser|pc|network)|rebooting didn't|didn't help|did not help)",
     "What have you already tried (restart, another cable, another browser), and what happened?"),
    ("impact", "How much it matters", 10, r"\b(cannot work|can't work|unable to work|blocked|deadline|due (?:today|tomorrow|at)|customers?|payroll|invoice|meeting|presentation|workaround|in the meantime|urgent because|not urgent|low priority|not blocking|(?:no|have a) workaround|stopp?ed (?:work|us)|losing)",
     "How much does it stop you working, is there a workaround, and is there a deadline?"),
    ("where", "Device, software and place", 10, r"\b(windows(?: \d+)?|win ?(?:10|11)|mac(?:book|os)?|linux|ubuntu|ios|android|iphone|laptop|desktop|printer|vpn|wi-?fi|ethernet|outlook|teams|excel|word|chrome|edge|firefox|zoom|office|floor|room|desk|building|remote|home|version \S+|v?\d+\.\d+(?:\.\d+)?)\b",
     "Which device and software (and version), and where are you: office, room, home?"),
]
BAD_TITLE_MARKS = re.compile(r"[!]{2,}|\b(please|pls|plz)\b|^[A-Z0-9 \W]{12,}$")


def _title_review(title: str) -> dict:
    t = title.strip()
    notes, score = [], 100
    if not t:
        return {"score": 0, "notes": ["Add a title: it is the first thing everyone reads."], "good": False}
    words = t.split()
    if t.lower().strip(" .!?") in VAGUE_TITLES or len(words) < 3:
        notes.append("Too vague. A good title names the thing and the symptom, e.g. “Outlook crashes when opening attachments (Windows 11)”.")
        score -= 55
    if len(t) > 90:
        notes.append("Too long for a title. Keep it to one line and move detail into the description.")
        score -= 20
    if BAD_TITLE_MARKS.search(t):
        notes.append("Skip shouting, repeated exclamation marks and “please”. Urgency belongs in the impact line, not the title.")
        score -= 15
    if not _has(r"\b(cannot|can't|won't|unable|fails?|failed|crash\w*|slow|error|freez\w*|missing|locked|no |not |offline|down|stuck|blank|request|new|install|access|reset)\b", t) and len(words) >= 3:
        notes.append("Say what is wrong or what you need (cannot, crashes, slow, request, install).")
        score -= 15
    return {"score": max(score, 0), "notes": notes or ["Clear title."], "good": score >= 80}


def priority(users_affected: int | str, workaround: bool, deadline: bool = False, security: bool = False, business_critical: bool = False) -> dict:
    """Impact (how many, how important) by urgency (can they work around it, is there a deadline). P1 is highest."""
    try:
        n = int(users_affected)
    except (TypeError, ValueError):
        raise CoachError("Number of people affected must be a whole number.") from None
    if n < 1 or n > 100000:
        raise CoachError("Number of people affected should be between 1 and 100000.")
    impact = 3 if (n >= 25 or business_critical or security) else 2 if n >= 5 else 1
    urgency = 3 if (not workaround and (deadline or security or business_critical)) else 2 if (not workaround or deadline) else 1
    score = impact + urgency
    p, label = ("P1", "Critical: start now and keep the requester updated") if score >= 6 or (security and not workaround) else ("P2", "High: same day") if score == 5 else ("P3", "Normal: within the agreed time") if score >= 3 else ("P4", "Low: when time allows")
    why = [f"Impact {impact}/3 ({n} {'person' if n == 1 else 'people'}{', business critical' if business_critical else ''}{', security' if security else ''})",
           f"Urgency {urgency}/3 ({'no workaround' if not workaround else 'there is a workaround'}{', deadline' if deadline else ''})"]
    return {"priority": p, "label": label, "impact": impact, "urgency": urgency, "why": why,
            "limit": "A starting point. Your own service targets (SLA) decide the real response times, and a security incident should follow your incident procedure."}


def review_report(title: str, body: str) -> dict:
    if not isinstance(title, str) or not isinstance(body, str):
        raise CoachError("Send the title and the description as text.")
    if len(title) > 300 or len(body) > 8000:
        raise CoachError("Keep the title under 300 and the description under 8,000 characters.")
    if len(body.strip()) < 15:
        raise CoachError("Write the description first (at least a sentence), then check it.")
    tr = _title_review(title)
    text = f"{title}\n{body}"
    found, missing, got = [], [], 0
    total = sum(c[2] for c in REPORT_CHECKS)
    for cid, label, w, rx, ask in REPORT_CHECKS:
        if _has(rx, text):
            found.append({"id": cid, "label": label})
            got += w
        else:
            missing.append({"id": cid, "label": label, "ask": ask})
    score = round(0.8 * 100 * got / total + 0.2 * tr["score"])
    words = len(body.split())
    notes = []
    if words < 20:
        notes.append("Very short. One more sentence per missing item below will save a phone call.")
    if words > 350:
        notes.append("Long. Lead with a two-line summary, then the detail, so the key facts are not buried.")
    if _has(r"\b(it|this|that|the thing) (?:is|isn't|doesn't|won't|stopped)\b", body) and not _has(r"\b(outlook|teams|vpn|printer|laptop|windows|wifi|wi-fi|excel|word|login|password|email|account|monitor|keyboard)\b", text):
        notes.append("Pronouns like “it” appear without naming the thing. Name the program or device.")
    if _has(r"\b(again|as usual|like last time|same as before|happened before|keeps happening|recurring)\b", text) and not _has(r"#\d+|ticket|INC\d+|ref", text):
        notes.append("If this happened before, quote the old ticket number.")
    if _has(r"\b(password|passcode|pin)\s*(?:is|:|=)\s*\S+", text):
        notes.append("Do not put a password in a ticket. Tickets are read by many people. Say you can supply it by phone if needed.")
        score = max(score - 10, 0)
    band = "Ready to work" if score >= 80 else "Nearly there" if score >= 60 else "Needs more detail"
    return {"score": score, "band": band, "title": tr, "found": found, "missing": missing, "notes": notes,
            "questions_a_technician_would_ask": [m["ask"] for m in missing][:6],
            "template": ("Title: <thing> + <symptom> (<device or OS>)\nWho: <you / team>, <machine name>\nWhat happens: <expected vs actual>\nError message: \"<exact text>\"\nStarted: <when>, after <change?>\n"
                         "Steps: 1) ... 2) ... 3) ...\nTried: <what you did, and the result>\nImpact: <blocked / workaround / deadline>\nEnvironment: <device, software and version, location>"),
            "limit": "This looks for the kind of information, using word patterns. It cannot tell if the details are correct, and a short clear ticket can score lower than it deserves."}


RES_CHECKS = [
    ("cause", "Cause found", 25, r"\b(cause[ds]?|because|due to|root cause|the problem was|turned out|was (?:a |an )?(?:corrupt|full|expired|misconfigured|blocked|outdated|missing|disabled|locked|wrong)|expired|corrupt\w*|misconfig\w*|disk (?:was )?full|full disk|outdated|stale|conflict)",
     "What was the cause? “Restarted and it worked” teaches nobody anything."),
    ("action", "What was done", 25, r"\b(replaced|re-?installed|updated|cleared|deleted|removed|reset|re-?created|restored|enabled|disabled|changed|set|added|configured|ran|renewed|unlocked|cleaned|rolled back|reimaged|re-?joined|fixed by)\b",
     "What did you do, in enough detail to repeat it (the setting, the command, the part)?"),
    ("verify", "Confirmed it works", 25, r"\b(confirmed|verified|tested|checked (?:with|that)|user (?:confirmed|says|reports)|working (?:again|now)|resolved for|retested|test (?:page|print|login|email)|signed in|can now)\b",
     "How do you know it works? Say who confirmed it, or what test you ran."),
    ("prevent", "Prevention or follow-up", 15, r"\b(to prevent|prevent\w*|going forward|follow[- ]?up|monitor\w*|added (?:an )?alert|documented|knowledge ?base|kb\b|scheduled|recurr\w*|root cause ticket|problem ticket|reminder|will (?:check|review)|so that it (?:doesn't|does not))",
     "Will it happen again? Note a prevention step, a monitor, or a follow-up ticket."),
    ("time", "Effort or time", 10, r"\b(\d+\s?(?:min|mins|minutes|hours?|hrs?|h)\b|took|spent|total time)",
     "Add the time spent, so effort and trends can be measured."),
]
WEAK_RES = re.compile(r"^\s*(fixed|done|resolved|ok|working|solved|rebooted|restarted|closed|n/?a|completed)\W*$", re.I)


def review_resolution(note: str, root_cause_known: bool | None = None) -> dict:
    if not isinstance(note, str) or len(note.strip()) < 3:
        raise CoachError("Write the resolution note first.")
    if len(note) > 8000:
        raise CoachError("Keep the resolution note under 8,000 characters.")
    notes = []
    if WEAK_RES.match(note):
        return {"score": 0, "band": "Not useful to the next person", "found": [], "missing": [{"id": c[0], "label": c[1], "ask": c[4]} for c in RES_CHECKS], "notes": ["One word tells the next technician nothing. Say what was wrong, what you did and how you checked."],
                "template": RES_TEMPLATE, "limit": RES_LIMIT}
    found, missing, got = [], [], 0
    for cid, label, w, rx, ask in RES_CHECKS:
        if _has(rx, note):
            found.append({"id": cid, "label": label})
            got += w
        else:
            missing.append({"id": cid, "label": label, "ask": ask})
    if _has(r"\b(reboot(?:ed)?|restart(?:ed)?|power[- ]?cycl\w+)\b", note) and not _has(CAUSE_RX, note):
        notes.append("A restart fixed it, but the cause is unknown. If it returns, say so in a problem ticket rather than closing it as solved.")
    if _has(r"\b(password|passcode)\s*(?:is|:|=)\s*\S+", note):
        notes.append("Remove the password from the note.")
        got = max(got - 20, 0)
    if len(note.split()) < 8:
        notes.append("Very short. Add a sentence on the cause and the check.")
    band = "Useful to the next person" if got >= 75 else "Partly useful" if got >= 50 else "Thin"
    return {"score": got, "band": band, "found": found, "missing": missing, "notes": notes, "template": RES_TEMPLATE, "limit": RES_LIMIT}


CAUSE_RX = RES_CHECKS[0][3]
RES_TEMPLATE = "Cause: <what was actually wrong>\nFix: <what you did, with the setting, command or part>\nChecked: <how you know it works, and who confirmed>\nPrevent: <what stops a repeat, or the follow-up ticket>\nTime: <minutes spent>"
RES_LIMIT = "Looks for the kind of information with word patterns. It cannot tell whether the note is true."

SAMPLE_REPORT = {"title": "help", "body": "my computer is broken and it won't work. please fix asap"}
SAMPLE_GOOD = {"title": "Outlook crashes when opening PDF attachments (Windows 11)", "body": "Only me (Sales, laptop SAL-014). Since this morning, after the Windows update, Outlook closes when I double-click a PDF attachment. The message says \"Microsoft Outlook has stopped working\". I tried restarting Outlook and the laptop; same result. I can still read email on my phone, so there is a workaround, but I have a client proposal due at 3 pm. Office 365 version 2408, in the Las Vegas office."}
SAMPLE_RESOLUTION = {"note": "Cause: the PDF preview handler was corrupted by the update. Reinstalled the Adobe Reader and re-registered the preview handler. Tested by opening three attachments; user confirmed it works. Added the fix to the knowledge base. Took 25 minutes."}
