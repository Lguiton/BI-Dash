"""AI does the whole job: a complete piece of work for the Data Analyst, Data Scientist or BI role.

You press one button, the agent works through the same read-only tools you have (schema, SQL, the Analysis Lab statistics) and hands back a full
written deliverable with the numbers it relied on. Keep it next to your own work and compare: where you agree you can be more confident, where you
differ one of you has found something worth a second look. It changes nothing in your data. The same privacy mode and provider settings apply as for chat.
"""
from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from app.services import agents, ai_policy, llm_router, manuals, providers, state, study, workspaces
from app.services.agents import AgentError
from app.services.ai_agent import AiError

MAX_STEPS = 16
MAX_OUT_TOKENS = 4000
KEEP = 12

ROLES = {
    "analyst": {"agent": "analyst", "label": "Data Analyst",
                "sections": ["The question and the decision it supports", "Can the data be trusted (checks run, problems found, what you did about them)", "What the data is (grain, key columns, period covered)",
                             "KPIs (each with its value, the baseline it is compared to, and whether it is on track)", "Findings (the biggest driver, with numbers and the test or comparison you used)",
                             "Charts I would show (one per point, and what each should make the reader see)", "The story (takeaway, how things stood, what changed, the evidence, the ask)",
                             "Recommendation (specific action, who, by when)", "What the data cannot tell you"]},
    "scientist": {"agent": "scientist", "label": "Data Scientist",
                  "sections": ["The business question, in one sentence, and the decision it serves", "Data needed and whether this data is suitable (rows, groups, quality)",
                               "Hypothesis (null, alternative, the smallest difference that would matter)", "Describe first (distributions, relationships, outliers)",
                               "The test (method, effect size with its interval, p-value read properly)", "Several models or views: segments, drivers, forecast, and which patterns more than one method agrees on",
                               "Challenge the conclusion (confounders, what else could explain it, what an experiment would need)", "Approach if this became a predictive model (target, baseline, split, how success is measured)",
                               "The story for a non-technical reader", "Recommendation and next step", "Limits"]},
    "bi": {"agent": "analyst", "label": "BI Analyst",
           "sections": ["Executive summary (three sentences a manager can repeat)", "KPI scorecard (value, baseline, direction, status)", "Trends over time (what is moving, by how much)",
                        "Breakdowns and drivers (by entity, category, region or whatever the data has)", "Anomalies and things to look at", "Outlook (a simple forecast with its caveat)",
                        "The story (takeaway, before, what changed, evidence, ask)", "Recommended actions, in priority order", "Data notes and caveats"]},
}


# What kind of analysis to do. "complete" uses the role's own full outline; each other type narrows the work to that kind of question.
CLOSE = ["The story (takeaway, how things stood, what changed, the evidence, the ask)", "Recommendation (specific action, who, by when)", "What the data cannot tell you"]
TYPES = {
    "complete": {"label": "Complete analysis (the role's full outline)", "sections": None, "brief": ""},
    "descriptive": {"label": "Descriptive: what happened?", "brief": "Descriptive analytics only: summarise the current status and the past. Use describe, distribution, timeseries (trend) and business metrics; no cause claims.",
                    "sections": ["The question", "Data used and period covered", "Headline numbers (totals, averages, shares, with the baseline for each)", "Trends over time", "Breakdowns (by entity, category, region or whatever the data has)", "Outliers and unusual days or records"] + CLOSE},
    "diagnostic": {"label": "Diagnostic: why did it happen?", "brief": "Diagnostic analytics only: find out why a number moved or differs. Use diagnose, compare, correlation and drill-down SQL. State clearly that association is not cause.",
                   "sections": ["The question: what changed or differs", "Where it shows up (drill down by group and period)", "Candidate drivers and how strongly each relates (effect sizes, intervals)", "Tests run (method, result read properly)", "Alternative explanations and confounders"] + CLOSE},
    "predictive": {"label": "Predictive: what is likely to happen?", "brief": "Predictive analytics only: forecast or estimate what comes next. Use timeseries and arima forecasts and say how far ahead is credible; describe what a regression or ML model would need (target, baseline, time-based split). Do not claim you trained a model unless a tool did.",
                   "sections": ["The question and the horizon", "History available and whether it is enough", "Forecast (values, range, method, seasonality)", "How much to trust it (history length, volatility, baseline to beat)", "Inputs that would help a model (features, how to split, how to score it)"] + CLOSE},
    "prescriptive": {"label": "Prescriptive: what should we do?", "brief": "Prescriptive analytics only: turn evidence into a ranked set of actions. Use diagnose and compare to support each action with numbers, give expected impact as a range, and state what to test first. Past association is not a guaranteed effect.",
                     "sections": ["The goal and constraints", "Evidence for each option (numbers and where from)", "Ranked actions with expected impact as a range", "Risks and trade-offs", "How to test before committing, and what to measure after"] + CLOSE},
    "classification": {"label": "Classification: which group, or yes/no?", "brief": "Classification thinking: define the yes/no or category outcome, find what separates the groups with compare and correlation, and describe how a decision tree or classifier would be set up and judged (baseline, held-back rows, sensitivity and specificity, cost of a miss versus a false alarm). Do not claim a model was trained unless a tool did.",
                       "sections": ["The outcome to classify and how it is defined", "How common each class is (the baseline to beat)", "What separates the groups (numbers)", "Set-up for a decision tree or classifier (inputs, split, scoring, cost of a miss)", "Risks (leakage, imbalance)"] + CLOSE},
    "inference": {"label": "Statistical inference (sample to population)", "brief": "Statistical inference: treat the rows as a sample. Check the type and level of each variable (analyze kind=variables), describe with frequency and distribution, build confidence intervals, and run hypothesis tests with analyze (test_mean, compare, crosstab, correlation). State H0 and H1, the significance level, the test statistic, p-value, effect size, the risk of Type I and Type II errors, and what the result does and does not show about the population.",
                  "sections": ["The question and the population it is about", "The sample (size, how it was collected, whether it is representative) and the type of each variable", "Descriptive summary (centre, spread, shape; sample versus population formulas)", "Confidence intervals (level, margin of error)", "Hypothesis tests (H0, H1, alpha, statistic, p-value, decision, effect size, Type I and II risk)", "Association between variables (cross table, correlation) with the caveat that it is not cause"] + CLOSE},
    "segments": {"label": "Segmentation: what groups and outliers exist?", "brief": "Segmentation: find natural groups, archetypes and outliers using breakdown SQL, describe and distribution; compare groups on key measures; name each segment in business terms with one action each.",
                 "sections": ["The question", "How the groups were found (the measures used)", "The segments (name, size, defining numbers)", "Outliers and why they differ", "One action per segment"] + CLOSE},
    "quality": {"label": "Data quality and preparation", "brief": "Data preparation only: run analyze kind=inspect on the table and describe, then list every problem and the fix you would apply (placeholder codes, missing values, duplicates, rare categories, wrong types, outliers), new columns to add, and whether the table needs rolling up to one row per entity.",
                "sections": ["What the data is (rows, columns, grain)", "Health check results (score and every issue)", "Fix plan, in order, with the reason for each", "New columns worth adding (ratios, dates, groups, flags, outcome windows)", "Is it ready for modeling? What is still missing"] + ["What the data cannot tell you"]},
    "business": {"label": "Business health (KPIs, margin, burn)", "brief": "Business metrics: revenue, cost, profit, margin, monthly revenue and cost versus budget using business and SQL tools; say what is healthy, what is not, and the most valuable action.",
                 "sections": ["The question", "KPI scorecard (value, baseline, status)", "Margin and cost versus budget", "Monthly revenue and trend", "What deserves attention"] + CLOSE},
}


def _key() -> str:
    return f"aiwork:{workspaces.active()}"


def list_work(role: str | None = None) -> list[dict]:
    import json
    items = json.loads(state.kv_get(_key(), "[]") or "[]")
    return [i for i in items if not role or i["role"] == role]


def delete_work(work_id: str) -> None:
    import json
    items = [i for i in list_work() if i["id"] != work_id]
    state.kv_set(_key(), json.dumps(items))


def _save(entry: dict) -> None:
    import json
    items = [entry] + list_work()
    state.kv_set(_key(), json.dumps(items[:KEEP]))


def _system(role: str, source: str, kind: str = "complete") -> str:
    r = ROLES[role]
    t = TYPES[kind]
    a, man = agents.AGENTS[r["agent"]], manuals.MANUALS[r["agent"]]
    base = agents.SYSTEM.format(name=f"{r['label']} agent", focus=a["focus"], knows=a["knows"],
                                steps="\n".join(f"- {s['id']}: {s['title']}" for s in man["steps"]), current="")
    secs = "\n".join(f"## {i}. {x}" for i, x in enumerate(t["sections"] or r["sections"], 1))
    return (base + f"""

FULL-WORK MODE. You are doing the {'complete job' if kind == 'complete' else 'work'} of a {r['label']} yourself, so the user can compare your work with their own.
{('TYPE OF ANALYSIS: ' + t['label'] + '. ' + t['brief']) if kind != 'complete' else ''}
Overrides to the rules above: you may write as much as the deliverable needs, and you may call tools many times (up to {MAX_STEPS} rounds).
- Start with get_context and get_schema, then work through the manual's steps in order using run_sql and analyze (data source: {source!r}). Run analyze kind=inspect on an imported table before using it.
- Every number in the deliverable must come from a tool result in this session. If a tool failed or the data cannot answer something, say so in that section instead of guessing.
- Reply with ONLY the finished deliverable in Markdown, using exactly these headings in this order:
{secs}
## Numbers to check
A bulleted list (no tables) of the key figures you relied on, each as: figure, value, and the tool or SQL it came from, so the user can verify each one.
- Do not claim to have changed or saved anything. Association is not cause: say so where it matters.""")


def run(role: str, question: str = "", source: str = "operations", provider: str = "auto", effort: str = "complex", adapters: dict | None = None, kind: str = "complete") -> dict:
    if role not in ROLES:
        raise AgentError("Pick analyst, scientist or bi.", 404)
    if kind not in TYPES:
        raise AgentError("Pick a type of analysis from the list.", 400)
    pol = ai_policy.describe()
    if not pol["allowed"]:
        state.audit("ai_work", f"{role}: blocked, AI is off", ok=False)
        raise AgentError("AI is switched off for this workspace. Turn it on in Settings (choose 'summaries only' to keep row-level data private).", 403)
    question = (question or "").strip()[:600]
    task = question or ("Do a complete analysis of this data and tell me what matters to the business." if kind == "complete" else f"Do a {TYPES[kind]['label'].split(':')[0].lower()} analysis of this data and tell me what matters to the business.")
    task = f"{task}\n\nData source to analyse: {source}."
    st = llm_router.status()
    claude = next((r for r in st["providers"] if r["id"] == "anthropic"), None)
    if provider == "auto" and "anthropic" in st["ready"] and claude and claude["used_today"] < claude["daily_limit"]:
        provider = "anthropic"          # these are long, multi-step jobs: Claude is the default whenever its key is set
    pl = llm_router.plan(task, provider, effort)
    if not pl["order"] and provider == "anthropic":
        pl = llm_router.plan(task, "auto", effort)
    if not pl["order"]:
        why = "; ".join(f"{s['provider']}: {s['why']}" for s in pl["skipped"])
        raise AgentError(f"No AI provider is ready ({why}). Add a key to backend/.env and restart the backend.", 503)
    track = ROLES[role]["agent"]
    tools = [agents.TOOL_CONTEXT, agents.TOOL_STEP, agents.TOOL_SCHEMA, agents.TOOL_SQL, agents.TOOL_ANALYZE]
    system = _system(role, source, kind)
    last = None
    for p in pl["order"]:
        try:
            adapter = adapters[p] if adapters and p in adapters else providers.ADAPTERS[p](max_tokens=MAX_OUT_TOKENS)
        except ImportError:
            last = f"{providers.INFO[p]['label']} SDK isn't installed."
            continue
        llm_router._count(p)
        t0 = time.perf_counter()
        try:
            res = _loop(track, adapter, system, tools, task)
        except AiError as e:
            last = str(e)
            continue
        entry = {"id": uuid.uuid4().hex[:10], "role": role, "label": ROLES[role]["label"], "kind": kind, "kind_label": TYPES[kind]["label"], "question": question, "source": source,
                 "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "provider": p, "model": adapter.model,
                 "markdown": res.reply, "complete": not res.stopped_early,
                 "tools_used": res.tools_used, "tokens": {"in": res.input_tokens, "out": res.output_tokens}}
        _save(entry)
        state.audit("ai_work", f"[{pol['mode']}] {role}/{p}: {question[:120] or 'complete analysis'}")
        study.log_ai(f"[{role} full work] {question or 'complete analysis'}", p, adapter.model, "agent", res.input_tokens, res.output_tokens, True, False, pl["kind"], role, round(time.perf_counter() - t0, 2))
        return entry
    raise AgentError(last or "Every provider failed.", 502)


def _loop(track: str, adapter, system: str, tools: list, task: str) -> agents.ChatResult:
    adapter.start(system, tools, task)
    res = agents.ChatResult()
    for _ in range(MAX_STEPS):
        try:
            turn = adapter.next_turn()
        except providers.ProviderError as e:
            raise AiError(str(e), e.status) from None
        res.input_tokens += turn.input_tokens
        res.output_tokens += turn.output_tokens
        if not turn.calls:
            res.reply = turn.text or "(no answer)"
            if turn.cut_off:
                res.reply += "\n\n(Cut off by the length limit. Ask for the missing sections in chat.)"
            return res
        results = []
        for c in turn.calls:
            out, err = agents._tool(track, c.name, c.args, res)
            res.tools_used.append({"tool": c.name, "error": err, "what": agents._what(c.name, c.args), "chars": len(out or "")})
            results.append((c, out, err))
        adapter.add_results(turn, results)
    res.stopped_early = True
    res.reply = ("I used all my tool rounds before finishing. Here is where I stopped; ask a narrower question or a specific question for the rest.\n\n"
                 + "\n".join(f"- {t['tool']}: {t['what']}" for t in res.tools_used[-10:]))
    return res
