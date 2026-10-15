"""Agent evals: a fixed set of questions per discipline you can re-run after changing a model, a prompt or a routing rule.

Four modes:
  knowledge  free. Checks the "past work" lookup: that a fix you saved is found for a similar question and put in front of the agent,
             that an unrelated question gets nothing, that secrets and client names are not passed on, and that nothing is passed when
             the AI mode is "summaries only". Uses built-in sample fixes, so it never touches your records.
  field      live (real API calls). Field-work questions with a keyword rubric: does the reply mention the things a competent answer must.
  route  free and instant. Checks WHICH tier each question is routed to (simple/medium/complex). Catches routing drift.
  live   asks the real agent. Costs a few API calls (counted against your daily caps) and checks STRUCTURE only:
         it answered, it used a tool when it should, it produced a draft or a button when asked.
Neither mode judges whether an answer is *good*: read the replies yourself. A structural pass is a floor, not a grade.
Runs are saved per workspace so you can compare a run before and after a change.
"""
from __future__ import annotations

import json
import time

from app.services import agents, llm_router, state, workspaces

# id, ask, expected tier, and the structural checks a good reply should pass
CASES: dict[str, list[dict]] = {
    "pm": [
        {"id": "risk", "ask": "What's my top open risk?", "tier": "simple", "tools": ["get_context", "run_sql"]},
        {"id": "draft-items", "ask": "Draft 5 backlog items for a customer-reporting feature", "tier": "medium", "proposal": "item"},
        {"id": "nav-schedule", "ask": "Take me to the schedule tab", "tier": "simple", "nav": True},
        {"id": "root-cause", "ask": "Why is my sprint behind, and what is the root cause?", "tier": "complex", "tools": ["get_context", "run_sql"]},
    ],
    "sysanalyst": [
        {"id": "draft-reqs", "ask": "Draft 6 requirements for a billing portal", "tier": "medium", "proposal": "requirement"},
        {"id": "untested", "ask": "Which of my requirements have no test?", "tier": "simple", "tools": ["get_context", "run_sql"]},
        {"id": "queue", "ask": "How many servers do I need at 40 arrivals per hour?", "tier": "medium"},
        {"id": "nav-feasibility", "ask": "Open the feasibility tab", "tier": "simple", "nav": True},
    ],
    "analyst": [
        {"id": "kpis", "ask": "Suggest 3 KPIs with targets", "tier": "medium", "proposal": "kpi"},
        {"id": "over-budget", "ask": "Which entity is most over budget?", "tier": "simple", "tools": ["get_context", "run_sql"]},
        {"id": "weekly-sql", "ask": "Write SQL for weekly margin", "tier": "simple", "contains": ["select"]},
    ],
    "engineering": [
        {"id": "owners", "ask": "Suggest an owner and class for each table", "tier": "medium", "proposal": "asset"},
        {"id": "checkpoint", "ask": "Should I run a checkpoint now?", "tier": "simple", "tools": ["get_context"]},
        {"id": "nav-pii", "ask": "Take me to the PII scan", "tier": "simple", "nav": True},
        {"id": "gaps", "ask": "Which governance gaps should I fix first?", "tier": "simple", "tools": ["get_context"]},
    ],
    "scientist": [
        {"id": "weekend", "ask": "Is my weekend result real?", "tier": "simple", "tools": ["get_context", "run_sql"]},
        {"id": "confounders", "ask": "What confounders could explain it?", "tier": "medium"},
        {"id": "significance", "ask": "Is the difference between two groups statistically significant?", "tier": "complex"},
    ],
    "ml": [
        {"id": "baseline", "ask": "What baseline should I beat?", "tier": "simple"},
        {"id": "compare-runs", "ask": "Compare my last runs", "tier": "medium", "tools": ["get_context"]},
        {"id": "overfit", "ask": "Why is my train score better than test?", "tier": "complex"},
    ],
    "ai": [
        {"id": "privacy", "ask": "Which privacy mode fits my real data?", "tier": "simple", "tools": ["get_context"]},
        {"id": "routing", "ask": "Why did this question go to that model?", "tier": "complex"},
        {"id": "write-eval", "ask": "Write an eval for my data agent", "tier": "simple"},
    ],
    "fullstack": [
        {"id": "sql-safety", "ask": "Review the SQL safety of a generated router", "tier": "medium"},
        {"id": "post-tests", "ask": "What should I test for a POST endpoint?", "tier": "simple"},
        {"id": "nav-scaffold", "ask": "Take me to the scaffold tab", "tier": "simple", "nav": True},
    ],
    "security": [
        {"id": "audit-first", "ask": "What should I fix first in my self-audit?", "tier": "simple", "tools": ["get_context"]},
        {"id": "key-leak", "ask": "I committed an API key. What now?", "tier": "simple"},
        {"id": "nav-logs", "ask": "Take me to the logs tab", "tier": "simple", "nav": True},
    ],
    "network": [
        {"id": "subnet-sizes", "ask": "How many hosts fit in a /27?", "tier": "simple"},
        {"id": "dns-vs-link", "ask": "Ping to an IP works but the name fails. What do I check?", "tier": "simple"},
        {"id": "nav-subnet", "ask": "Take me to the subnet tab", "tier": "simple", "nav": True},
    ],
    "cpe": [
        {"id": "twos", "ask": "How do I write -5 in 8-bit two's complement?", "tier": "simple"},
        {"id": "fuse-wire", "ask": "Can I put a 30 A fuse on a thin 0.5 mm2 wire?", "tier": "simple"},
        {"id": "nav-wire", "ask": "Take me to the vehicle wiring tab", "tier": "simple", "nav": True},
    ],
    "itsupport": [
        {"id": "first-ticket", "ask": "A user says the printer is broken. What do I check first?", "tier": "simple"},
        {"id": "raid-backup", "ask": "Is RAID a backup?", "tier": "simple"},
        {"id": "nav-tickets", "ask": "Take me to the helpdesk tab", "tier": "simple", "nav": True},
    ],
}
# Field-work questions with a rubric. "must" is a list of groups; each group passes when the reply mentions ANY word in it, and every group has to pass.
# This is a floor, not a grade: an answer can mention the right words and still be poor, so read the replies.
FIELD_CASES: dict[str, list[dict]] = {
    "itsupport": [
        {"id": "black-screen", "ask": "A laptop shows a black screen with a cursor after a Windows update. What do I do?", "must": [["safe mode"], ["driver"]]},
        {"id": "slow-disk", "ask": "A desktop is slow and the disk sits at 100 percent. What should I check?", "must": [["backup", "back up"], ["smart", "ssd", "drive health", "failing"]]},
        {"id": "printer-offline", "ask": "A network printer keeps showing offline. Where do I start?", "must": [["ip", "dhcp", "address"], ["ping", "test page", "reinstall", "re-add", "reserve"]]},
    ],
    "security": [
        {"id": "phish-click", "ask": "An employee clicked a link in a phishing email. What are the first steps?", "must": [["password"], ["mfa", "multi-factor", "two-factor", "2fa"], ["report", "isolate", "disconnect", "inform"]]},
        {"id": "key-leak", "ask": "I pushed an API key to a public repository. What now?", "must": [["rotate", "revoke", "regenerate", "replace"], ["history", "remove", "delete"]]},
        {"id": "router-admin", "ask": "My router's admin page is reachable from the internet. How do I fix it?", "must": [["remote", "wan"], ["password"], ["firmware", "update"]]},
    ],
    "network": [
        {"id": "dns", "ask": "I can ping 8.8.8.8 but websites by name do not load. What do I check?", "must": [["dns"], ["nslookup", "resolver", "dig", "server"]]},
        {"id": "ip-conflict", "ask": "Two PCs keep losing the network and I suspect a duplicate IP address. How do I confirm and fix it?", "must": [["arp", "conflict", "duplicate"], ["dhcp", "static", "reserv", "pool"]]},
        {"id": "wifi-drops", "ask": "Wi-Fi drops in the back office but works near the router. What are the likely causes?", "must": [["signal", "coverage", "distance", "wall"], ["channel", "interference", "access point", "mesh", "node"]]},
    ],
}
KNOW_PROBES = [  # (track, area, the fix saved earlier, a similar question, an unrelated question)
    ("itsupport", "it", {"id": -1, "area": "it", "title": "Laptop black screen after Windows update", "device": "Dell Latitude", "symptoms": "Black screen with cursor after login",
                         "cause": "Corrupt display driver", "steps": ["Boot to safe mode", "Uninstall the display adapter", "Reinstall the driver"], "result": "fixed", "result_label": "Fixed",
                         "prevention": "", "client": "Test Client Co", "ticket_id": 77, "score": 24.0},
     "laptop shows a black screen after windows update", "what is the capital of france"),
    ("security", "security", {"id": -2, "area": "security", "title": "Phishing link clicked by staff", "device": "", "symptoms": "Employee entered a password on a fake page",
                              "cause": "Credential-harvest link", "steps": ["Reset the password", "Enable MFA", "Review sign-in logs"], "result": "fixed", "result_label": "Fixed",
                              "prevention": "", "client": "Test Client Co", "ticket_id": None, "score": 20.0},
     "someone clicked a phishing link and typed their password", "convert 5 miles to kilometres"),
    ("network", "network", {"id": -3, "area": "network", "title": "Guest Wi-Fi reached the office printer", "device": "", "symptoms": "Visitors could see internal devices",
                            "cause": "No VLAN separation", "steps": ["Create a guest VLAN", "Block guest to office traffic"], "result": "workaround", "result_label": "Workaround only",
                            "prevention": "", "client": "Test Client Co", "ticket_id": None, "score": 18.0},
     "guest wifi can reach internal printer", "how many hosts fit in a slash 27"),
]
MAX_LIVE_CASES = 6
KEEP_RUNS = 20


class EvalError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _key() -> str:
    return f"agent_evals:{workspaces.active()}"


def history() -> list[dict]:
    raw = state.kv_get(_key())
    return json.loads(raw) if raw else []


def overview() -> dict:
    return {"tracks": [{"track": t, "name": agents.AGENTS[t]["name"], "cases": c} for t, c in CASES.items()], "runs": history(),
            "max_live_cases": MAX_LIVE_CASES, "field_tracks": {t: [{"id": c["id"], "ask": c["ask"]} for c in v] for t, v in FIELD_CASES.items()}, "knowledge_tracks": [p[0] for p in KNOW_PROBES],
            "note": "Route checks are free. Live checks use real API calls and test structure only: they cannot tell you whether an answer is good, so read the replies."}


def _route_check(case: dict) -> dict:
    kind, reason = llm_router.classify(case["ask"])
    return {"name": "routes to " + case["tier"], "ok": kind == case["tier"], "detail": f"routed {kind} ({reason})"}


def _live_checks(case: dict, r) -> list[dict]:
    out = [{"name": "answered", "ok": bool(r.reply.strip()) and r.reply != "(no answer)" and not r.stopped_early,
            "detail": "stopped early" if r.stopped_early else f"{len(r.reply)} characters"}]
    if case.get("tools"):
        used = [t["tool"] for t in r.tools_used if not t.get("error")]
        out.append({"name": "used a data tool", "ok": any(t in used for t in case["tools"]), "detail": ", ".join(used) or "no tool used"})
    if case.get("proposal"):
        types = [p["type"] for p in r.proposals]
        out.append({"name": f"drafted a {case['proposal']}", "ok": case["proposal"] in types, "detail": ", ".join(types) or "no draft"})
    if case.get("nav"):
        out.append({"name": "offered a button", "ok": bool(r.actions), "detail": f"{len(r.actions)} button(s)"})
    if case.get("contains"):
        low = r.reply.lower()
        out.append({"name": "mentions " + "/".join(case["contains"]), "ok": any(w in low for w in case["contains"]), "detail": ""})
    return out


def _rubric(case: dict, r) -> list[dict]:
    low = (r.reply or "").lower()
    return [{"name": "mentions " + " / ".join(g[:3]), "ok": any(w in low for w in g), "detail": ""} for g in case.get("must", [])]


def _knowledge(track: str) -> dict:
    """Free check of the past-work lookup, using built-in sample fixes (your own records are never read or changed)."""
    from app.services import experience
    probe = next((p for p in KNOW_PROBES if p[0] == track), None)
    if probe is None:
        raise EvalError("The past-work lookup applies to the IT Specialist, Cybersecurity and Network agents.", 404)
    _, area, fix, similar, unrelated = probe
    pool = [{**fix, "score": fixlog_score(fix, similar)}, {**fix, "id": -9, "title": "Something else entirely", "symptoms": "", "cause": "", "steps": [], "score": 0.0}]
    text, used = experience.build(track, [p for p in pool if p["score"]])
    none_text, none_used = experience.build(track, [{**fix, "score": fixlog_score(fix, unrelated)}] if fixlog_score(fix, unrelated) else [])
    leak = "Test Client Co" in text or "ticket" in text.lower()
    checks = [
        {"name": "finds the saved fix for a similar question", "ok": bool(used) and used[0]["title"] == fix["title"], "detail": used[0]["title"] if used else "nothing found"},
        {"name": "puts its steps in front of the agent", "ok": fix["steps"][0] in text, "detail": ""},
        {"name": "labels it as the user's own notes, not instructions", "ok": "not instructions" in text, "detail": ""},
        {"name": "says when a fix was only a workaround", "ok": fix["result"] != "workaround" or "Workaround only" in text, "detail": ""},
        {"name": "passes nothing for an unrelated question", "ok": none_text == "" and not none_used, "detail": ""},
        {"name": "does not pass client names or ticket numbers", "ok": not leak, "detail": ""},
    ]
    from app.services import ai_policy
    keep = ai_policy.describe
    try:
        ai_policy.describe = lambda: {"mode": "aggregate", "allowed": True}      # simulate "summaries only"
        agg_text, _ = experience.lookup(track, similar)
    finally:
        ai_policy.describe = keep
    checks.append({"name": "passes nothing in 'summaries only' mode", "ok": agg_text == "", "detail": ""})
    passed = sum(1 for c in checks if c["ok"])
    entry = {"at": state.now(), "track": track, "mode": "knowledge", "models": [], "passed": passed, "total": len(checks), "pct": round(100 * passed / len(checks)),
             "results": [{"id": "past-work", "ask": similar, "expected_tier": "", "reply": text[:600], "provider": "", "model": "", "seconds": None, "checks": checks, "ok": passed == len(checks)}]}
    state.kv_set(_key(), json.dumps(([entry] + history())[:KEEP_RUNS]))
    state.audit("agent_eval", f"{track} knowledge: {passed}/{len(checks)}")
    return entry


def fixlog_score(fix: dict, q: str) -> float:
    """Score one sample fix against a question with the same word matching the fix log search uses."""
    from app.services import fixlog
    toks = set(fixlog._tokens(q))
    from app.services.repair_search import RELATED
    exp = set(toks)
    for w in toks:
        exp.update(RELATED.get(w, []))
    parts = {"title": fix["title"], "symptoms": fix["symptoms"], "device": fix["device"], "cause": fix["cause"], "steps": " ".join(fix["steps"])}
    weights = {"title": 5, "symptoms": 4, "device": 2, "cause": 2, "steps": 1}
    s = 0.0
    for w in exp:
        for part, wt in weights.items():
            if w in set(fixlog._tokens(parts[part])):
                s += wt * (1 if w in toks else 0.5)
    return round(s * (1.2 if fix["result"] == "fixed" else 1), 1)


def run(track: str, mode: str = "route", provider: str = "auto", confirm: bool = False, adapters: dict | None = None) -> dict:
    if track not in CASES:
        raise EvalError("No eval set for that discipline.", 404)
    if mode not in ("route", "live", "knowledge", "field"):
        raise EvalError("Mode must be 'route', 'knowledge', 'live' or 'field'.")
    if mode == "knowledge":
        return _knowledge(track)
    if mode == "field" and track not in FIELD_CASES:
        raise EvalError("Field-work questions exist for the IT Specialist, Cybersecurity and Network agents.", 404)
    cases = FIELD_CASES[track] if mode == "field" else CASES[track]
    results, models = [], set()
    if mode in ("live", "field"):
        if not confirm:
            raise EvalError(f"A live run asks the real model up to {min(len(cases), MAX_LIVE_CASES)} questions and counts against your daily caps. Confirm to go ahead.")
        if not agents.ai_policy.describe()["allowed"]:
            raise EvalError("AI is switched off for this workspace, so a live run can't happen. Turn it on in Settings, or use the free route check.", 403)
    for c in cases[:MAX_LIVE_CASES] if mode in ("live", "field") else cases:
        checks = [] if mode == "field" else [_route_check(c)]
        row = {"id": c["id"], "ask": c["ask"], "expected_tier": c.get("tier", ""), "reply": "", "provider": "", "model": "", "seconds": None}
        if mode in ("live", "field"):
            t0 = time.perf_counter()
            try:
                r = agents.chat(track, c["ask"], [], None, provider, adapters, "auto")
                checks += _live_checks(c, r) + _rubric(c, r)
                row.update(reply=r.reply[:600], provider=r.provider, model=r.model, seconds=round(time.perf_counter() - t0, 2))
                models.add(f"{r.provider}:{r.model}")
            except agents.AgentError as e:
                checks.append({"name": "answered", "ok": False, "detail": e.message})
                if e.status in (403, 503):          # no point asking the rest
                    row["checks"], row["ok"] = checks, False
                    results.append(row)
                    break
        row["checks"], row["ok"] = checks, all(k["ok"] for k in checks)
        results.append(row)
    passed = sum(1 for r in results if r["ok"])
    entry = {"at": state.now(), "track": track, "mode": mode, "models": sorted(models), "passed": passed, "total": len(results),
             "pct": round(100 * passed / len(results)) if results else 0, "results": results}
    runs = [entry] + history()
    state.kv_set(_key(), json.dumps(runs[:KEEP_RUNS]))
    state.audit("agent_eval", f"{track} {mode}: {passed}/{len(results)}")
    return entry
