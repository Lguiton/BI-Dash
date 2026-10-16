"""The usual steps for a job in each field, so "Start as job" gives you a ready checklist instead of one empty step.

Plain lists you can edit on the job; nothing is sent anywhere. A field can have a few variants picked by words in the job title."""
from __future__ import annotations

import re

# field -> [(words that pick this variant, [steps])]; the last entry of each field (no words) is its default.
STEPS: dict[str, list[tuple[str, list[str]]]] = {
    "itsupport": [
        ("printer print scanner", ["Ask what changed and what the printer shows", "Check power, cables, paper and the queue", "Check the driver and the network address", "Print a test page and confirm with the user"]),
        ("slow tune-up cleanup virus malware", ["Back up what matters before touching anything", "Check startup items, disk space and updates", "Scan and clean", "Restart, time the boot, and confirm with the user"]),
        ("screen battery cracked repair hardware", ["Confirm the symptom and back up if the device boots", "Open a quote with the part cost and time", "Do the repair", "Test everything and show the user"]),
        ("", ["Get the symptoms and what changed", "Check the likely causes, easiest first", "Fix and test", "Confirm with the user and note what fixed it"]),
    ],
    "network": [
        ("wifi wi-fi wireless dropping coverage", ["Collect symptoms: where, when, which devices", "Check channel, signal and interference", "Apply the fix (channel, placement, firmware)", "Watch it for a day and confirm"]),
        ("guest vlan separate segment", ["Draw the current layout and what must be separated", "Set up the guest network or VLAN", "Test that guests cannot reach office devices", "Write the settings down for the client"]),
        ("", ["Map the network and what is wrong", "Check the likely causes, easiest first", "Fix and test", "Document and confirm"]),
    ],
    "security": [
        ("phishing email password scam", ["Contain: change the password and sign out other sessions", "Check what the account could reach and the sign-in history", "Turn on multi-factor sign-in", "Write up what happened and what to watch"]),
        ("", ["List accounts, devices and backups", "Check updates, passwords and multi-factor sign-in", "Fix the biggest gaps first", "Write the one-page findings"]),
    ],
    "analyst": [
        ("", ["Load the data and check gaps and duplicates", "Build the numbers and charts the client asked for", "Write the short plain-English summary", "List what could not be checked"]),
    ],
    "scientist": [("", ["State the question and the groups", "Run the analysis and check the assumptions", "Report the size of the effect and how sure you are", "State what it does not prove"])],
    "ml": [("", ["Check the target and the class balance", "Train a simple baseline and a better model on a time-based split", "Report the honest score on held-out data", "Write what it is and is not good for"])],
    "ai": [("", ["Define what it must and must not answer", "Build and test it on real questions", "Check cost and what gets logged", "Write the handover notes"])],
    "cpe": [("", ["List inputs, units and assumptions", "Calculate and sanity-check by rough estimate", "Test or measure to confirm", "Write assumptions and who must sign off"])],
    "engineering": [("", ["Map the sources and the target", "Build and test the pipeline", "Add checks and a backup", "Document how to run and fix it"])],
    "fullstack": [("", ["Reproduce the problem and read the error", "Find the cause and fix it", "Add a test that fails before and passes after", "Check other inputs and deploy notes"])],
    "pm": [("", ["Write the goal, scope and what is out of scope", "List tasks, owners and dates", "Name the top risks and what to do about each", "Share the plan and agree the next check-in"])],
    "sysanalyst": [("", ["Interview and list how it works today", "Mark the pain points from what was said", "Write the requirements as testable statements", "List open questions for the client"])],
}
_W = re.compile(r"[a-z0-9][a-z0-9-]*")


def for_job(title: str, field: str | None) -> list[str]:
    """The step titles for this job, or [] when the field has no template."""
    variants = STEPS.get(field or "")
    if not variants:
        return []
    words = set(_W.findall((title or "").lower()))
    best, hit = None, 0
    for key, steps in variants:
        n = len(words & set(key.split())) if key else 0
        if n > hit:
            best, hit = steps, n
    return list(best or variants[-1][1])
