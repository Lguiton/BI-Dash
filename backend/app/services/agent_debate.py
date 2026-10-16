"""Debate: the field's agent is asked the same question twice, once on Gemini and once on OpenAI, each using the dashboard tools and
reading the pinned job. Claude only judges (another AI steps in if Claude fails) and writes one final report: what they agree on, where they differ and which side the tool
results back, and what to verify. Report only: it never changes anything. Off by default, with its own daily cap, because one debate is two agent runs plus a judge."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services import agents, ai_policy, assistants, prep, providers, state, workspaces
from app.services.agents import AgentError
from app.services.workteam import JUDGES, LABELS, _once

DEBATERS = ("google", "openai")          # Gemini and OpenAI debate; Claude only judges (it is the strongest, so it is kept for the ruling)

DEFAULTS = {"enabled": False, "daily_cap": 3}
HARD_MAX = 20
MAX_ANSWER = 2500
MAX_REPORT = 3500


class DebateError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    return workspaces.active()


def config() -> dict:
    return {**DEFAULTS, **(state.setting_get(_ws(), "debate", {}) or {})}


def _ukey() -> str:
    return f"debate_used:{_ws()}:{datetime.now(timezone.utc).date().isoformat()}"


def used_today() -> int:
    return int(state.kv_get(_ukey(), "0") or 0)


def status() -> dict:
    c = config()
    return {**c, "used_today": used_today(), "remaining": max(0, c["daily_cap"] - used_today()), "hard_max": HARD_MAX, "ai_mode": ai_policy.describe()["mode"],
            "providers_ready": {p: bool(providers.api_key(p)) for p in (*DEBATERS, "anthropic")}, "debaters": [LABELS[p] for p in DEBATERS], "judge": LABELS["anthropic"],
            "note": "A debate asks the field's agent on all three AIs, each using the tools, then a judge writes one report. Up to four AI calls plus their tool use, so it is off until you turn it on."}


def update_config(body: dict) -> dict:
    cfg = config()
    if "daily_cap" in body:
        try:
            n = int(body["daily_cap"])
        except (TypeError, ValueError):
            raise DebateError("The daily cap must be a whole number.") from None
        if not 1 <= n <= HARD_MAX:
            raise DebateError(f"The daily cap must be from 1 to {HARD_MAX} debates.")
        cfg["daily_cap"] = n
    if "enabled" in body:
        cfg["enabled"] = bool(body["enabled"])
    state.setting_set(_ws(), "debate", cfg)
    state.audit("debate_config", f"enabled={cfg['enabled']} cap={cfg['daily_cap']}")
    return status()


JUDGE = ("You are the judge of a debate. Two AI assistants answered the same question from one dashboard, each able to use the dashboard's calculators and read the "
         "open job. Write ONE final report for the owner, plain text, under 250 words, in these parts: Answer (the best supported answer, first); Agreed (what all or most said); "
         "Disagreed (where they differ, and which side is better supported, saying why: a claim backed by a tool result beats a claim without one); Verify (the specific things "
         "the owner must check before relying on it). Use only what the answers and tool lists show. Never add facts, numbers or steps of your own. If only one answered, say it was not a debate.")


def run(track: str, message: str, history: list[dict] | None = None, job_id: int | None = None, adapters: dict | None = None) -> dict:
    cfg = config()
    if not cfg["enabled"]:
        raise DebateError("The debate is switched off. Turn it on first.", 403)
    if ai_policy.describe()["mode"] == "off":
        raise DebateError("AI is switched off for this workspace in Settings.", 403)
    if used_today() >= cfg["daily_cap"]:
        raise DebateError(f"The daily cap of {cfg['daily_cap']} debates is used up. It resets tomorrow (UTC), or raise the cap.", 429)
    if track not in agents.AGENTS:
        raise DebateError("No agent for that discipline.", 404)
    message = (message or "").strip()
    if len(message) < 2:
        raise DebateError("Type a question first.")
    state.kv_set(_ukey(), str(used_today() + 1))
    answers, failed = [], []
    for p in DEBATERS:
        if not (adapters and p in adapters) and not providers.api_key(p):
            failed.append(f"{LABELS[p]} (no key)")
            continue
        try:
            r = agents.chat(track, message, history or [], None, p, adapters, "auto", "default", None, None, job_id)
        except AgentError as e:
            failed.append(f"{LABELS[p]} ({e.message[:80]})")
            continue
        except Exception:  # noqa: BLE001 - one provider failing must not stop the other two
            failed.append(LABELS[p])
            continue
        answers.append({"provider": p, "label": LABELS[p], "model": r.model, "text": r.reply[:MAX_ANSWER], "tools": [t["what"] or t["tool"] for t in r.tools_used if not t["error"]],
                        "tool_errors": [t["what"] or t["tool"] for t in r.tools_used if t["error"]], "tokens": r.input_tokens + r.output_tokens})
    if not answers:
        raise DebateError("Neither Gemini nor OpenAI could answer. Check the keys (python scripts/check_ai_keys.py), the privacy mode in Settings and try again.", 502)
    judge, report, jtok = "", answers[0]["text"], 0
    if len(answers) > 1:
        prompt = f"QUESTION: {message}\n\n" + "\n\n".join(
            f"ANSWER {chr(65 + i)} ({a['label']}). Tools it ran: {', '.join(a['tools']) or 'none'}" + (f". Tool calls that failed: {', '.join(a['tool_errors'])}" if a["tool_errors"] else "") + f"\n{a['text']}"
            for i, a in enumerate(answers))
        for p in JUDGES:
            r = _once(p, JUDGE, prompt, adapters)
            if r:
                judge, report = LABELS[p], r["text"].strip()[:MAX_REPORT]
                jtok = int(r.get("input_tokens") or 0) + int(r.get("output_tokens") or 0)
                break
        if not judge:
            report = "The judge could not answer, so the first answer is shown unjudged. Compare the answers below.\n\n" + answers[0]["text"]
    else:
        report = f"Only {answers[0]['label']} answered, so this was not a debate.\n\n" + answers[0]["text"]
    out = {"report": report, "judge": judge, "answers": answers, "failed": failed, "agent_tokens": sum(a["tokens"] for a in answers), "judge_tokens": jtok, "tokens": sum(a["tokens"] for a in answers) + jtok, "track": track}
    d = prep._drafts()
    key = f"debate:{track}:{job_id or 0}"
    d[key] = {"text": report, "kind": "team", "title": f"Debate report: {message[:70]}", "status": "pending", "edited": False, "at": state.now(), "model": judge or answers[0]["label"]}
    prep._save(d)
    assistants.record("draft", key, d[key]["title"])
    state.audit("debate_run", f"{track} answers={len(answers)} judge={judge or 'none'}")
    return {**out, "key": key, "used_today": used_today()}
