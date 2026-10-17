"""Agent works the job: the field's agent drafts the work for every open step, one after another.

A DRAFT only. It never marks a step done, never sends anything, never touches equipment. The owner reads it, edits it and decides.
One agent call per open step (at most MAX_STEPS), so it costs far less than the three-AI work team."""
from __future__ import annotations

from app.services import agents, ai_policy, assistants, jobfield, prep, state, worklog

MAX_STEPS = 8
ADVICE_FIELDS = {"itsupport", "network", "security"}


class AutoError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _steps(jid: int) -> list[dict]:
    rows = [r for r in worklog.listing()["items"] if r.get("job_id") == jid and r["status"] != "done"]
    return sorted(rows, key=lambda r: r["id"])


def run(jid: int, instructions: str = "", adapters: dict | None = None) -> dict:
    from app.services import clients as cl
    if ai_policy.describe()["mode"] == "off":
        raise AutoError("AI is switched off for this workspace in Settings, so the agent can't work the job. The steps and how-to guides still work.", 403)
    try:
        j = cl.job_totals(int(jid))["job"]
    except cl.ClientError as e:
        raise AutoError(e.message, e.status) from None
    fkey = ((jobfield.of_job(j) or {}).get("key")) or jobfield.guess(j["title"]) or ""
    if fkey not in agents.AGENTS:
        raise AutoError("Pick a field for this job first (the Field box), so the right agent is used.")
    steps = _steps(int(jid))
    todo = steps[:MAX_STEPS] or [{"id": 0, "title": j["title"]}]
    ins = (instructions or "").strip()[:400]
    advice = fkey in ADVICE_FIELDS
    parts, failed, used = [], [], 0
    for n, s in enumerate(todo, 1):
        msg = (f'Work this step of the job "{j["title"][:120]}": "{s["title"][:200]}". Use the job details, the practice files if any, my tools and my past fixes. '
               + ("Give the checklist, likely causes in order and questions to ask; you cannot see the equipment, so never say anything was checked or fixed. " if advice else
                  "Do as much of the work as the information allows and show the result with the numbers. Say clearly what you could not check. ")
               + (f"Owner's instructions: {ins}. " if ins else "") + "Draft only.")
        try:
            r = agents.chat(fkey, msg[:1200], [], None, "auto", adapters, "auto", "default", None, None, int(jid))
            parts.append(f"STEP {n}: {s['title']}\n{r.reply.strip()}")
            used += 1
        except agents.AgentError as e:
            failed.append(f"Step {n}: {e.message}")
            if getattr(e, "status", 400) in (403, 429):
                break
        except Exception as e:  # noqa: BLE001 - a provider failure on one step must not lose the others
            failed.append(f"Step {n}: {str(e)[:120]}")
    if not parts:
        raise AutoError("The agent couldn't answer. " + (failed[0] if failed else "Check the AI keys in Settings."), 502)
    text = "\n\n".join(parts)[:6000]
    out = {"text": text, "kind": "team", "title": f"Agent work: {j['title']}", "status": "pending", "edited": False, "mode": "advice" if advice else "work",
           "judge_notes": "One agent worked each open step. It can be wrong and it checked nothing on real equipment. Verify before you use or send anything.",
           "judge": "", "drafts": [], "failed": failed, "field": fkey, "warnings": [], "model": agents.AGENTS[fkey]["name"], "at": state.now(), "steps": used}
    d = prep._drafts()
    d[f"auto:{jid}"] = out
    prep._save(d)
    assistants.record("draft", f"auto:{jid}", out["title"])
    state.audit("jobauto_run", f"job {jid} field={fkey} steps={used} failed={len(failed)}")
    return {"key": f"auto:{jid}", **out}
