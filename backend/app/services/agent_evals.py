"""Agent evals: a fixed set of questions per discipline you can re-run after changing a model, a prompt or a routing rule.

Two modes:
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
    "itsupport": [
        {"id": "first-ticket", "ask": "A user says the printer is broken. What do I check first?", "tier": "simple"},
        {"id": "raid-backup", "ask": "Is RAID a backup?", "tier": "simple"},
        {"id": "nav-tickets", "ask": "Take me to the helpdesk tab", "tier": "simple", "nav": True},
    ],
}
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
            "max_live_cases": MAX_LIVE_CASES,
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


def run(track: str, mode: str = "route", provider: str = "auto", confirm: bool = False, adapters: dict | None = None) -> dict:
    if track not in CASES:
        raise EvalError("No eval set for that discipline.", 404)
    if mode not in ("route", "live"):
        raise EvalError("Mode must be 'route' or 'live'.")
    cases = CASES[track]
    results, models = [], set()
    if mode == "live":
        if not confirm:
            raise EvalError(f"A live run asks the real model up to {min(len(cases), MAX_LIVE_CASES)} questions and counts against your daily caps. Confirm to go ahead.")
        if not agents.ai_policy.describe()["allowed"]:
            raise EvalError("AI is switched off for this workspace, so a live run can't happen. Turn it on in Settings, or use the free route check.", 403)
    for c in cases[:MAX_LIVE_CASES] if mode == "live" else cases:
        checks = [_route_check(c)]
        row = {"id": c["id"], "ask": c["ask"], "expected_tier": c["tier"], "reply": "", "provider": "", "model": "", "seconds": None}
        if mode == "live":
            t0 = time.perf_counter()
            try:
                r = agents.chat(track, c["ask"], [], None, provider, adapters, "auto")
                checks += _live_checks(c, r)
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
