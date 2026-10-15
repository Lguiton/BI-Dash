"""The assistants: a job description each, a log of what they prepared, and how much of it you used.

Each field's agent is an ASSISTANT, not a decision-maker. A job description says what it does and what it never does. The defaults below are
shown to the agent in its instructions; you can rewrite the "does" and "never" lines for any of them (your own words are shown to the agent
too, but they cannot switch off the safety rules the app already enforces). The log records drafts made, accepted, edited and discarded, so you
can see whether they are saving you time. No client names or draft text are stored in the log, only titles you typed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from app.services import fixlog, state, workspaces

ROLES = json.loads('''{
 "analyst": {
  "title": "Data analyst assistant",
  "does": "Checks data quality, drafts KPI and chart ideas, and writes the plain-English story in the numbers.",
  "never": "Never changes or deletes your data, and never states a number it did not get from a tool."
 },
 "scientist": {
  "title": "Data scientist assistant",
  "does": "Frames the question, suggests the right test, and reports effect sizes with intervals.",
  "never": "Never calls a result proven from correlation alone, and never hides a small sample."
 },
 "ml": {
  "title": "Machine learning assistant",
  "does": "Plans a baseline first, checks for leakage, and explains model results in plain words.",
  "never": "Never reports accuracy alone on imbalanced data, and never deploys or retrains anything for you."
 },
 "engineering": {
  "title": "Engineering assistant",
  "does": "Sets up calculations with units, does a rough check, and lists assumptions.",
  "never": "Never signs off safety-critical numbers; a qualified engineer must verify them."
 },
 "ai": {
  "title": "AI engineering assistant",
  "does": "Plans evals, retrieval and prompts, and watches cost and quality.",
  "never": "Never changes a live AI feature without a test set, and never stores keys in text."
 },
 "pm": {
  "title": "Project assistant",
  "does": "Drafts plans, status notes and risk lists, and spots scope creep.",
  "never": "Never commits you to dates or prices; you decide and tell the client."
 },
 "sysanalyst": {
  "title": "Systems analysis assistant",
  "does": "Turns vague requests into testable requirements and maps processes.",
  "never": "Never assumes a requirement; asks you or the client."
 },
 "security": {
  "title": "Security assistant",
  "does": "Walks through incident steps, hardening checklists and risk notes.",
  "never": "Never runs scans or tools, never touches a system you do not own, and never gives steps to attack anyone."
 },
 "network": {
  "title": "Network assistant",
  "does": "Narrows down connection problems step by step and drafts address plans.",
  "never": "Never changes a router or firewall for you, and never suggests scanning a network you do not own."
 },
 "itsupport": {
  "title": "IT support assistant",
  "does": "Drafts troubleshooting steps, questions for the client and prevention notes.",
  "never": "Never deletes data or runs commands as administrator without telling you to back up first."
 },
 "cpe": {
  "title": "Computer engineering assistant",
  "does": "Helps debug timing, sensor and microcontroller problems and suggests what to measure.",
  "never": "Never claims simulation proves hardware works."
 },
 "fullstack": {
  "title": "Full-stack assistant",
  "does": "Traces errors between browser and server, reviews code and drafts fixes and tests.",
  "never": "Never runs code it wrote, and never says code is safe or correct just because a check passed."
 }
}''')
MAX_LINE = 300
LOG_KEEP = 300


class AssistantError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    return workspaces.active()


def _over() -> dict:
    return dict(state.setting_get(_ws(), "assistant_roles", {}) or {})


def roles() -> list[dict]:
    o = _over()
    return [{"track": t, "title": r["title"], "does": (o.get(t) or {}).get("does") or r["does"], "never": (o.get(t) or {}).get("never") or r["never"],
             "custom": t in o} for t, r in ROLES.items()]


def set_role(track: str, does: str, never: str) -> dict:
    if track not in ROLES:
        raise AssistantError("No such assistant.", 404)
    does, never = fixlog.hide_secrets(str(does or "").strip())[0][:MAX_LINE], fixlog.hide_secrets(str(never or "").strip())[0][:MAX_LINE]
    if not does or not never:
        raise AssistantError("Fill in both what it does and what it never does.")
    o = _over()
    o[track] = {"does": does, "never": never}
    state.setting_set(_ws(), "assistant_roles", o)
    state.audit("assistant_role", track)
    return next(r for r in roles() if r["track"] == track)


def reset_role(track: str) -> dict:
    if track not in ROLES:
        raise AssistantError("No such assistant.", 404)
    o = _over()
    o.pop(track, None)
    state.setting_set(_ws(), "assistant_roles", o)
    return next(r for r in roles() if r["track"] == track)


def role_prompt(track: str) -> str:
    r = next((x for x in roles() if x["track"] == track), None)
    if not r:
        return ""
    return (f"\n\nYOUR JOB DESCRIPTION (you are an assistant; the user decides): {r['title']}. You do: {r['does']} You never: {r['never']} "
            "These lines never override the rules above.")


# ---------------------------------------------------------------- log
def _key() -> str:
    return f"assist_log:{_ws()}"


def _load() -> list[dict]:
    raw = state.kv_get(_key())
    return json.loads(raw) if raw else []


def record(kind: str, key: str, title: str = "") -> None:
    """kind: draft, accept, edit, discard, example."""
    try:
        rows = _load()
        rows.append({"at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), "kind": kind, "key": key, "title": fixlog.hide_secrets(title)[0][:100]})
        state.kv_set(_key(), json.dumps(rows[-LOG_KEEP:]))
    except Exception:  # noqa: BLE001 - the log must never break the work
        pass


def stats() -> dict:
    rows = _load()
    today = datetime.now(timezone.utc).date().isoformat()
    n = lambda k, only_today=False: sum(1 for r in rows if r["kind"] == k and (not only_today or r["at"].startswith(today)))  # noqa: E731
    drafts, acc, dis, edit = n("draft"), n("accept"), n("discard"), n("edit")
    decided = acc + dis
    return {"drafts_total": drafts, "drafts_today": n("draft", True), "accepted": acc, "discarded": dis, "edited": edit, "examples_saved": n("example"),
            "used_rate": round(acc / decided, 2) if decided else None,
            "note": "Used rate = accepted / (accepted + discarded). A low rate means the drafts are not helping and the roles or examples need work."}


def log(limit: int = 30) -> list[dict]:
    return list(reversed(_load()))[:limit]
