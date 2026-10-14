"""AI governance lab: an AI asset registry with risk checks, a use-case risk tier, a runtime policy simulator and spend attribution.

Everything here is paperwork and arithmetic over what you enter. It does not call a model, a gateway or a provider, and it
enforces nothing: a real gateway or identity system does the enforcing. The point is to practise the thinking.
"""
from __future__ import annotations

import csv
import io
import json
import re
import statistics
import uuid
from datetime import date, datetime

from app.services import state


class GovError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


KINDS = ["model", "agent", "mcp_server", "tool", "coding_agent", "dataset", "prompt"]
CLASSES = ["public", "internal", "confidential", "restricted"]
ACTIONS = ["read", "write", "deploy", "spend", "send_message", "external_call", "delete"]
AUTONOMY = ["suggest", "act_with_approval", "autonomous"]
MAX_ASSETS = 200
_RISKY_ACTIONS = {"write", "deploy", "send_message", "external_call", "delete", "spend"}


def _load() -> list[dict]:
    raw = state.kv_get("ai_assets")
    return json.loads(raw) if raw else []


def _save(items: list[dict]) -> None:
    state.kv_set("ai_assets", json.dumps(items))


def _today() -> date:
    return date.today()


def _days_since(iso: str) -> int | None:
    try:
        return (_today() - datetime.strptime(iso, "%Y-%m-%d").date()).days
    except (TypeError, ValueError):
        return None


def assess(a: dict) -> dict:
    """Risk tier (low/medium/high) and a list of issues for one registered asset."""
    score, issues = 0, []
    cls = CLASSES.index(a["data_class"])
    acts = set(a["actions"])
    risky = acts & _RISKY_ACTIONS
    score += cls  # 0..3
    if risky:
        score += 1 + (len(risky) > 2)
    if a["autonomy"] == "autonomous":
        score += 2
    elif a["autonomy"] == "act_with_approval":
        score += 1
    if a["pii"]:
        score += 1
    if not a["owner"]:
        issues.append("No owner. Someone must be accountable for it.")
    if not a["approved"]:
        issues.append("Not approved. If it is in use, this is shadow AI.")
    if a["autonomy"] == "autonomous" and risky and not a["human_oversight"]:
        issues.append("Acts on its own with side effects and no human oversight. Add approval for the risky actions.")
    if cls >= 2 and a["provider"] == "external":
        issues.append("Confidential or restricted data goes to an external provider. Check the contract, data residency and retention.")
    if a["pii"] and "read" in acts and not a["human_oversight"] and a["autonomy"] != "suggest":
        issues.append("Handles personal data without oversight. Add masking and a review route.")
    age = _days_since(a.get("last_review", ""))
    if age is None:
        issues.append("Never reviewed.")
    elif age > 365:
        issues.append(f"Last review {age} days ago. Review at least yearly.")
    if a["kind"] in ("agent", "coding_agent", "mcp_server", "tool") and not a["traced"]:
        issues.append("Its actions are not traced. You cannot investigate what you cannot see.")
    tier = "high" if score >= 6 else "medium" if score >= 3 else "low"
    return {"score": score, "tier": tier, "issues": issues}


def _clean(b: dict) -> dict:
    if not isinstance(b, dict):
        raise GovError("Send the asset as an object.")
    name = str(b.get("name", "")).strip()[:80]
    if not name:
        raise GovError("Give the asset a name.")
    kind = b.get("kind")
    if kind not in KINDS:
        raise GovError(f"Kind must be one of {', '.join(KINDS)}.")
    cls = b.get("data_class", "internal")
    if cls not in CLASSES:
        raise GovError(f"Data class must be one of {', '.join(CLASSES)}.")
    autonomy = b.get("autonomy", "suggest")
    if autonomy not in AUTONOMY:
        raise GovError(f"Autonomy must be one of {', '.join(AUTONOMY)}.")
    acts = b.get("actions", [])
    if not isinstance(acts, list) or any(x not in ACTIONS for x in acts):
        raise GovError(f"Actions must be a list from {', '.join(ACTIONS)}.")
    provider = b.get("provider", "internal")
    if provider not in ("internal", "external"):
        raise GovError("Provider must be internal or external.")
    review = str(b.get("last_review", "") or "").strip()
    if review and _days_since(review) is None:
        raise GovError("Last review must be a date like 2026-06-30.")
    return {"name": name, "kind": kind, "owner": str(b.get("owner", "")).strip()[:80], "purpose": str(b.get("purpose", "")).strip()[:300],
            "provider": provider, "data_class": cls, "pii": bool(b.get("pii", False)), "actions": sorted(set(acts)), "autonomy": autonomy,
            "human_oversight": bool(b.get("human_oversight", False)), "approved": bool(b.get("approved", False)), "traced": bool(b.get("traced", False)),
            "last_review": review}


def _view(a: dict) -> dict:
    return {**a, **assess(a)}


def assets() -> dict:
    items = [_view(a) for a in _load()]
    tiers = {t: sum(1 for a in items if a["tier"] == t) for t in ("high", "medium", "low")}
    return {"assets": items, "count": len(items), "tiers": tiers, "with_issues": sum(1 for a in items if a["issues"])}


def register(b: dict) -> dict:
    c = _clean(b)
    items = _load()
    if any(x["name"].lower() == c["name"].lower() for x in items):
        raise GovError(f"'{c['name']}' is already registered.", 409)
    if len(items) >= MAX_ASSETS:
        raise GovError(f"The registry holds {MAX_ASSETS} assets.")
    c["id"] = uuid.uuid4().hex[:8]
    items.append(c)
    _save(items)
    state.audit("ai_asset_register", c["name"])
    return _view(c)


def update(aid: str, b: dict) -> dict:
    items = _load()
    i = next((k for k, x in enumerate(items) if x["id"] == aid), None)
    if i is None:
        raise GovError("No such asset.", 404)
    c = _clean(b)
    if any(x["name"].lower() == c["name"].lower() and x["id"] != aid for x in items):
        raise GovError(f"'{c['name']}' is already registered.", 409)
    c["id"] = aid
    items[i] = c
    _save(items)
    state.audit("ai_asset_update", c["name"])
    return _view(c)


def remove(aid: str) -> dict:
    items = _load()
    gone = next((x for x in items if x["id"] == aid), None)
    if gone is None:
        raise GovError("No such asset.", 404)
    _save([x for x in items if x["id"] != aid])
    state.audit("ai_asset_delete", gone["name"])
    return {"deleted": aid}


def shadow_check(observed: list[str]) -> dict:
    """Compare what you actually see in use (API keys in logs, tool names in traces) with the registry."""
    names = [str(x).strip() for x in observed if str(x).strip()]
    if not names:
        raise GovError("List at least one asset you have seen in use, one per line.")
    if len(names) > 500:
        raise GovError("Keep it to 500 names.")
    reg = {a["name"].lower(): a for a in _load()}
    seen = {n.lower() for n in names}
    shadow = sorted({n for n in names if n.lower() not in reg})
    unapproved = sorted(reg[n]["name"] for n in seen if n in reg and not reg[n]["approved"])
    unused = sorted(a["name"] for k, a in reg.items() if k not in seen)
    return {"shadow_ai": shadow, "registered_but_unapproved": unapproved, "registered_not_seen": unused,
            "verdict": f"{len(shadow)} unregistered, {len(unapproved)} in use but unapproved, {len(unused)} registered but not seen.",
            "next": "Register or retire each unregistered one; approve or stop the unapproved ones; confirm the unseen ones are still needed."}


# ------------------------------------------------------------------ risk tier
PROHIBITED = {"social_scoring": "Scoring people on social behaviour so that they are treated worse elsewhere",
              "manipulation": "Manipulating people's behaviour in ways that harm them, or exploiting vulnerable groups",
              "biometric_id": "Real-time remote biometric identification in public spaces"}
HIGH = {"employment": "Hiring, promotion, firing or task allocation", "credit": "Credit scoring or insurance pricing for people",
        "education": "Admission, grading or exam proctoring", "essential_services": "Access to benefits, housing or emergency services",
        "law_enforcement": "Policing, evidence assessment or risk profiling", "migration": "Border, visa or asylum decisions",
        "justice": "Assisting judicial or legal decisions", "health_safety": "A safety component of a medical device or vehicle, or a clinical decision",
        "critical_infrastructure": "Operating power, water, traffic or similar systems", "biometrics": "Identifying people or inferring emotions from biometrics"}
TRANSPARENCY = {"talks_to_people": "People talk to it and might think it is a person", "generates_content": "It generates or alters text, images, audio or video people may take as real"}
CONTROLS = {
    "prohibited": ["Do not build or deploy. Get legal advice; some of these practices are banned in the EU and other places."],
    "high": ["Documented risk management and a named owner", "Data quality and bias testing on the groups affected", "Logging and traceability of decisions",
             "Meaningful human oversight with the power to override", "Accuracy, robustness and security testing, repeated after changes", "Instructions and limits for the people who use it",
             "A way for affected people to ask about and contest a decision", "Check which legal duties apply where you operate (for example the EU AI Act)"],
    "limited": ["Tell people they are dealing with AI", "Label or watermark generated content where the rules require it", "Keep a record of the use case and its owner"],
    "minimal": ["Register it, name an owner, and apply ordinary security and privacy controls", "Re-assess if its purpose or data changes"],
}
NIST = {"high": "Govern (policy, accountability), Map (context and impacts), Measure (test, bias, accuracy), Manage (monitor, respond)",
        "limited": "Govern and Map first, then Measure the transparency controls", "minimal": "Govern: register and review; Map if the purpose changes",
        "prohibited": "Govern: stop and escalate"}


def risk_tier(answers: dict) -> dict:
    if not isinstance(answers, dict):
        raise GovError("Send the answers as an object.")
    bad = [k for k in answers if k not in {*PROHIBITED, *HIGH, *TRANSPARENCY}]
    if bad:
        raise GovError(f"Unknown question '{bad[0]}'.")
    pro = [PROHIBITED[k] for k in PROHIBITED if answers.get(k)]
    hi = [HIGH[k] for k in HIGH if answers.get(k)]
    tr = [TRANSPARENCY[k] for k in TRANSPARENCY if answers.get(k)]
    tier = "prohibited" if pro else "high" if hi else "limited" if tr else "minimal"
    return {"tier": tier, "because": pro or hi or tr or ["None of the listed triggers apply."], "controls": CONTROLS[tier], "nist_ai_rmf": NIST[tier],
            "limit": "A learning aid modelled on the EU AI Act's four levels, not legal advice. The law, its dates and its exceptions change and differ by country. Ask a lawyer before relying on it."}


# ------------------------------------------------------------------ policy simulator
EFFECTS = ["allow", "deny", "approve"]
_FIELDS = ["role", "action", "data_class", "kind"]


def _rules(rules: list) -> list[dict]:
    if not isinstance(rules, list) or not rules:
        raise GovError("Give at least one rule.")
    if len(rules) > 100:
        raise GovError("Keep it to 100 rules.")
    out = []
    for i, r in enumerate(rules):
        if not isinstance(r, dict) or r.get("effect") not in EFFECTS:
            raise GovError(f"Rule {i + 1}: effect must be allow, deny or approve.")
        out.append({"id": i + 1, "effect": r["effect"], **{f: (str(r.get(f) or "*").strip().lower() or "*") for f in _FIELDS}})
    return out


def _match(rule: dict, req: dict) -> bool:
    return all(rule[f] in ("*", str(req.get(f, "")).lower()) for f in _FIELDS)


def simulate(rules: list, requests: list, default: str = "deny") -> dict:
    """Deny beats approve beats allow. If nothing matches, the default applies. Shows which rule decided."""
    rs = _rules(rules)
    if default not in EFFECTS:
        raise GovError("Default must be allow, deny or approve.")
    if not isinstance(requests, list) or not requests or len(requests) > 200:
        raise GovError("Give between 1 and 200 requests.")
    order = {"deny": 0, "approve": 1, "allow": 2}
    results, used = [], set()
    for i, q in enumerate(requests):
        if not isinstance(q, dict):
            raise GovError(f"Request {i + 1} must be an object.")
        hits = sorted((r for r in rs if _match(r, q)), key=lambda r: (order[r["effect"]], -sum(r[f] != "*" for f in _FIELDS)))
        if hits:
            used.add(hits[0]["id"])
            results.append({"request": {f: q.get(f, "") for f in _FIELDS}, "decision": hits[0]["effect"], "rule": hits[0]["id"], "matched": len(hits)})
        else:
            results.append({"request": {f: q.get(f, "") for f in _FIELDS}, "decision": default, "rule": 0, "matched": 0})
    warn = []
    for r in rs:
        if r["effect"] == "allow" and all(r[f] == "*" for f in _FIELDS):
            warn.append(f"Rule {r['id']} allows everything. A blanket allow makes the other allow rules pointless.")
        if r["id"] not in used:
            warn.append(f"Rule {r['id']} never decided any request in this test.")
    if default == "allow":
        warn.append("The default is allow: anything you forgot to write a rule for goes through. Prefer default deny.")
    tally = {e: sum(1 for x in results if x["decision"] == e) for e in EFFECTS}
    return {"results": results, "tally": tally, "warnings": warn,
            "lesson": "Governing actions, not just access: the same agent is allowed to read but must ask before it pushes code.",
            "limit": "This models the idea. A real gateway enforces it, with identity from your login system."}


# ------------------------------------------------------------------ spend
def _parse_usage(text: str) -> list[dict]:
    rows = list(csv.DictReader(io.StringIO(text.strip())))
    need = {"user", "team", "app", "model", "input_tokens", "output_tokens"}
    if not rows or not need <= set(rows[0]):
        raise GovError("Usage needs a header row with: user, team, app, model, input_tokens, output_tokens (and optionally task).")
    if len(rows) > 50_000:
        raise GovError("Keep it to 50,000 rows.")
    out = []
    for i, r in enumerate(rows):
        try:
            tin, tout = int(r["input_tokens"]), int(r["output_tokens"])
        except (TypeError, ValueError):
            raise GovError(f"Row {i + 2}: token counts must be whole numbers.") from None
        if tin < 0 or tout < 0:
            raise GovError(f"Row {i + 2}: token counts cannot be negative.")
        out.append({"user": r["user"].strip(), "team": r["team"].strip(), "app": r["app"].strip(), "model": r["model"].strip(),
                    "in": tin, "out": tout, "task": (r.get("task") or "").strip().lower()})
    return out


def spend(usage_csv: str, prices: dict, budgets: dict | None = None, cheap_model: str = "", rate_limit_tpm: int = 0) -> dict:
    rows = _parse_usage(usage_csv or "")
    if not isinstance(prices, dict) or not prices:
        raise GovError("Give a price per million tokens for each model: {model: {input, output}}.")
    pr = {}
    for m, p in prices.items():
        try:
            pr[m] = (float(p["input"]), float(p["output"]))
        except (KeyError, TypeError, ValueError):
            raise GovError(f"Price for '{m}' needs numeric input and output values.") from None
        if min(pr[m]) < 0:
            raise GovError(f"Price for '{m}' cannot be negative.")
    unknown = sorted({r["model"] for r in rows} - set(pr))
    if unknown:
        raise GovError(f"No price for model '{unknown[0]}'.")
    if cheap_model and cheap_model not in pr:
        raise GovError(f"No price for the cheaper model '{cheap_model}'.")

    def cost(r, model=None):
        pi, po = pr[model or r["model"]]
        return (r["in"] * pi + r["out"] * po) / 1_000_000
    total = sum(cost(r) for r in rows)

    def by(key):
        agg: dict[str, dict] = {}
        for r in rows:
            a = agg.setdefault(r[key] or "(blank)", {"cost": 0.0, "tokens": 0, "calls": 0})
            a["cost"] += cost(r)
            a["tokens"] += r["in"] + r["out"]
            a["calls"] += 1
        return [{key: k, "cost": round(v["cost"], 4), "share_pct": round(100 * v["cost"] / total, 1) if total else 0, "tokens": v["tokens"], "calls": v["calls"]}
                for k, v in sorted(agg.items(), key=lambda kv: -kv[1]["cost"])]
    users = by("user")
    med = statistics.median([u["cost"] for u in users]) if users else 0
    outliers = [u for u in users if med > 0 and u["cost"] > 3 * med and len(users) >= 4]
    status = []
    for team, limit in (budgets or {}).items():
        try:
            lim = float(limit)
        except (TypeError, ValueError):
            raise GovError(f"Budget for '{team}' must be a number.") from None
        spent = sum(cost(r) for r in rows if r["team"] == team)
        pct = 100 * spent / lim if lim > 0 else 0
        status.append({"team": team, "spent": round(spent, 4), "budget": lim, "used_pct": round(pct, 1), "status": "blocked" if pct >= 100 else "alert" if pct >= 80 else "ok"})
    out = {"total_cost": round(total, 4), "calls": len(rows), "tokens": sum(r["in"] + r["out"] for r in rows),
           "by_team": by("team"), "by_user": users, "by_app": by("app"), "by_model": by("model"), "budgets": status,
           "outliers": [{"user": u["user"], "cost": u["cost"], "times_median": round(u["cost"] / med, 1)} for u in outliers]}
    if cheap_model:
        simple = [r for r in rows if r["task"] == "simple" and r["model"] != cheap_model]
        saved = sum(cost(r) - cost(r, cheap_model) for r in simple)
        out["routing_what_if"] = {"simple_calls_moved": len(simple), "estimated_saving": round(saved, 4), "saving_pct": round(100 * saved / total, 1) if total else 0,
                                  "caveat": "Assumes the cheaper model is as good on those tasks. That is the claim to test with your own evaluation set before moving traffic."}
    if rate_limit_tpm > 0:
        out["rate_limit_note"] = f"A limit of {rate_limit_tpm:,} tokens per minute caps one user's burst; this usage has no timestamps, so it cannot be replayed against the limit."
    return out


SAMPLE_USAGE = """user,team,app,model,input_tokens,output_tokens,task
ana,platform,code-agent,big-model,420000,90000,complex
ben,platform,code-agent,big-model,380000,80000,complex
cy,platform,code-agent,big-model,40000,9000,simple
dee,support,helpdesk-bot,big-model,150000,40000,simple
dee,support,helpdesk-bot,big-model,160000,42000,simple
eli,support,helpdesk-bot,small-model,90000,20000,simple
fay,data,sql-assistant,big-model,60000,15000,complex
gus,data,sql-assistant,big-model,2500000,600000,complex
"""
SAMPLE_PRICES = {"big-model": {"input": 3.0, "output": 15.0}, "small-model": {"input": 0.25, "output": 1.25}}


# ------------------------------------------------------------------ reference
CROSSWALK = [
    ("Know what AI exists (unified asset registry)", "Govern / Map", "Registry tab; shadow-AI check", "A spreadsheet is a start; a gateway or catalog keeps it current"),
    ("Identity-aware access and on-behalf-of-user", "Govern / Manage", "Policy simulator (role, action, data class)", "Needs real identity propagation in your systems"),
    ("Govern actions, not only access", "Manage", "Policy simulator: allow, deny, approve", "Enforcement needs a gateway or your own middleware"),
    ("Guardrails: PII masking, prompt injection, unsafe content", "Manage / Measure", "AI engineering > AI tools > PII and injection scan", "Guardrails are filters that miss things; layer them"),
    ("Trace every interaction end to end", "Measure / Manage", "AI engineering > AI tools > Agent trace", "Treat traces as sensitive data: they hold prompts and responses"),
    ("Spend visibility, attribution, budgets", "Govern / Manage", "Spend tab", "Real usage comes from provider logs or a gateway"),
    ("Route tasks to cheaper models", "Manage", "Spend tab routing what-if", "Prove quality with evals before moving traffic"),
    ("Model choice without lock-in (substitution, fallbacks, traffic splitting)", "Manage", "AI engineering > Reliability and MLOps lab (canary, shadow)", "Architect so a model swap is configuration"),
    ("Risk classification of use cases", "Map", "Risk tier tab", "Not in the book; added here (EU AI Act levels, NIST AI RMF)"),
]
GAPS = ["Regulation and standards: the EU AI Act, the NIST AI Risk Management Framework (Govern, Map, Measure, Manage) and ISO/IEC 42001 are not covered.",
        "Risk classification of use cases and when a human must be in the loop.",
        "Fairness, bias testing and explainability get one passing mention.",
        "Model and data documentation (model cards, data sheets), red-teaming and incident reporting.",
        "Evidence: every figure comes from the vendor or its customers, with no independent audit."]
SLIPS = [
    "AI governance book (Databricks): it is vendor material. 'The industry's only unified governance solution', '14,000 organizations', 'match frontier quality at up to 30% lower cost', 'typically 50% or more in total savings' and the customer savings figures are marketing claims with no method shown. Treat them as hypotheses to test, not benchmarks.",
    "AI governance book: 'a new frontier model every five days' and the Gartner forecast of '150,000 agents per Fortune 500 company by 2028' are given without a source you can check. Do not repeat them as facts.",
    "AI governance book: it says governance rests on five principles (data and context, security and policy, transparency, operational oversight, cost optimisation), then organises the whole book around three (cost, choice, control). Choice is not one of the five, and fairness and compliance get little room. A framework should not change shape between pages.",
    "AI governance book: guardrails are presented as protection against prompt injection and jailbreaks. They reduce risk; they do not remove it. Injection has no complete filter, so limit what a tricked agent can do (least privilege, approval for risky actions).",
    "AI governance book: 'Smart Routing' and similar features name products and versions that may have changed since writing. Check the vendor's current documentation before planning around a feature.",
    "AI governance book: it treats 'govern the data' and 'govern the AI' as one platform problem. The harder questions it skips are who is accountable when an agent errs, what law applies, and how affected people contest a decision.",
]
NOT_BUILT = [
    "Unity Catalog, Unity Gateway, MLflow Tracing on Databricks, Genie and Lakewatch: commercial platform features that need Databricks. Open alternatives to learn the same ideas: OpenTelemetry for traces, MLflow (open source) for tracking, LiteLLM or Portkey for a model gateway, Open Policy Agent for policy. Docs: https://opentelemetry.io, https://mlflow.org, https://www.openpolicyagent.org, https://docs.litellm.ai",
    "Live enforcement of budgets, guardrails and approvals, and real on-behalf-of-user identity: these need a gateway in front of real model traffic.",
    "Standards documents: NIST AI RMF (https://www.nist.gov/itl/ai-risk-management-framework), EU AI Act (https://artificialintelligenceact.eu) and ISO/IEC 42001 (paid standard).",
]


def reference() -> dict:
    return {"principles": ["Trustworthy data and context", "Security and policy enforcement", "Transparency and accountability", "Operational oversight", "Cost optimisation"],
            "themes": {"Cost": "see it, attribute it, budget it, route to cheaper models", "Choice": "centralise access, architect for substitution, fallbacks and traffic splitting",
                       "Control": "register every AI asset, govern actions at runtime, trace everything, treat traces as sensitive"},
            "crosswalk": [{"idea": a, "nist_ai_rmf": b, "in_this_app": c, "limit": d} for a, b, c, d in CROSSWALK],
            "gaps_in_the_book": GAPS, "slips": SLIPS, "not_built": NOT_BUILT,
            "kinds": KINDS, "data_classes": CLASSES, "actions": ACTIONS, "autonomy": AUTONOMY,
            "high_risk_triggers": HIGH, "prohibited_triggers": PROHIBITED, "transparency_triggers": TRANSPARENCY}


def sample() -> dict:
    return {"usage": SAMPLE_USAGE, "prices": json.dumps(SAMPLE_PRICES, indent=1),
            "rules": "deny, *, send_message, restricted, agent\napprove, agent, deploy, *, *\nallow, analyst, read, internal, *\nallow, agent, read, internal, *",
            "requests": "analyst, read, internal, model\nagent, deploy, internal, agent\nagent, send_message, restricted, agent\nintern, delete, internal, tool",
            "observed": "support-bot\nsql-assistant\nnotes-summariser-v2\ncode-agent"}


def _lines(t: str):
    return [[p.strip() for p in l.split(",")] for l in (t or "").splitlines() if l.strip()]


def simulate_text(rules_text: str, requests_text: str, default: str = "deny") -> dict:
    rules = [{"effect": (p + [""] * 5)[0], "role": (p + [""] * 5)[1], "action": (p + [""] * 5)[2], "data_class": (p + [""] * 5)[3], "kind": (p + [""] * 5)[4]} for p in _lines(rules_text)]
    reqs = [{"role": (p + [""] * 4)[0], "action": (p + [""] * 4)[1], "data_class": (p + [""] * 4)[2], "kind": (p + [""] * 4)[3]} for p in _lines(requests_text)]
    return simulate(rules, reqs, default)
