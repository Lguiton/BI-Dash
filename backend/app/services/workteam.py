"""Work team: type a job, three AI drafters each do the work, a judge writes one final draft for you to check.

Works in the Practice and the Real workspace. It only ever produces a DRAFT in the approval queue: nothing is sent to a client and nothing is run.
IT repair, networking and security jobs get advice and checklists only, never a claim that something was fixed (the work happens on real gear).
Data jobs: facts (counts, ranges, blanks, duplicates) are computed here from the text, so the models are given the facts and not asked to count."""
from __future__ import annotations

import csv
import io
import statistics
from datetime import datetime, timezone

from app.services import ai_policy, assistants, experience, jobfield, llm_router, practice_kits, prep, providers, state, workspaces
from app.services.ai_agent import AiError

DEFAULTS = {"enabled": False, "daily_cap": 3}
HARD_MAX = 20
DRAFTERS = ("google", "openai", "anthropic")
JUDGES = ("anthropic", "openai", "google")
ADVICE_FIELDS = {"itsupport", "network", "security"}
MAX_MATERIAL = 6000
MAX_DRAFT = 4000
MAX_FINAL = 6000
SPLIT = "=== JUDGE NOTES ==="
LABELS = {"google": "Gemini", "openai": "OpenAI", "anthropic": "Claude"}


class TeamError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _ws() -> str:
    return workspaces.active()


def config() -> dict:
    return {**DEFAULTS, **(state.setting_get(_ws(), "workteam", {}) or {})}


def _ukey() -> str:
    return f"team_used:{_ws()}:{datetime.now(timezone.utc).date().isoformat()}"


def used_today() -> int:
    return int(state.kv_get(_ukey(), "0") or 0)


def status() -> dict:
    c = config()
    ready = {p: bool(providers.api_key(p)) for p in DRAFTERS}
    return {**c, "used_today": used_today(), "remaining": max(0, c["daily_cap"] - used_today()), "hard_max": HARD_MAX, "providers_ready": ready,
            "ai_mode": ai_policy.describe()["mode"], "workspace": _ws(),
            "note": "Each run asks up to three AIs to do the job and one to judge them, so it uses up to four calls. The result is a draft for you to check; nothing is sent or run."}


def update_config(body: dict) -> dict:
    cfg = config()
    if "daily_cap" in body:
        try:
            n = int(body["daily_cap"])
        except (TypeError, ValueError):
            raise TeamError("The daily cap must be a whole number.") from None
        if not 1 <= n <= HARD_MAX:
            raise TeamError(f"The daily cap must be from 1 to {HARD_MAX} runs.")
        cfg["daily_cap"] = n
    if "enabled" in body:
        cfg["enabled"] = bool(body["enabled"])
    state.setting_set(_ws(), "workteam", cfg)
    state.audit("workteam_config", f"enabled={cfg['enabled']} cap={cfg['daily_cap']}")
    return status()


# ------------------------------------------------------------ facts computed here, not by the models
def facts(text: str) -> str:
    """If the text is a CSV table, count things exactly. Returns '' when it is not a table."""
    try:
        rows = list(csv.reader(io.StringIO(text.strip())))
    except csv.Error:
        return ""
    if len(rows) < 3 or len(rows[0]) < 2 or any(len(r) != len(rows[0]) for r in rows[1:]):
        return ""
    head, body = rows[0], rows[1:]
    seen, dup = set(), 0
    for r in body:
        t = tuple(r)
        dup += t in seen
        seen.add(t)
    out = [f"Table: {len(body)} rows, {len(head)} columns. Exact duplicate rows: {dup}."]
    for i, h in enumerate(head):
        col = [r[i].strip() for r in body]
        blank = sum(1 for v in col if v == "")
        nums = []
        for v in col:
            try:
                nums.append(float(v))
            except ValueError:
                pass
        if nums and len(nums) >= len(col) - blank - 0:
            out.append(f"- {h}: number, min {min(nums):g}, max {max(nums):g}, mean {statistics.mean(nums):.4g}, blanks {blank}")
        else:
            out.append(f"- {h}: text, {len(set(col))} different values, blanks {blank}")
    return "\n".join(out)


def _material(jid: int, pasted: str, kit: dict | None) -> tuple[str, list[str]]:
    """What the team is allowed to see. Returns (text, warnings)."""
    warns: list[str] = []
    parts: list[str] = []
    real = not _sample()
    if kit and not real:
        for f in kit["files"]:
            txt = f["text"]
            ft = facts(txt) if f["kind"] == "csv" else ""
            parts.append(f"FILE {f['name']} (practice data):\n" + (ft + "\nFirst rows:\n" + "\n".join(txt.splitlines()[:25]) if ft else txt[:MAX_MATERIAL]))
    pasted = (pasted or "").strip()
    if pasted:
        ft = facts(pasted)
        if ft and real:
            parts.append("PASTED TABLE (real; only computed facts are shared, not the rows):\n" + ft)
            warns.append("Your pasted table was summarised locally: the models saw counts and ranges, not the rows.")
        else:
            parts.append("PASTED MATERIAL" + (" (real)" if real else "") + ":\n" + ((ft + "\n") if ft else "") + pasted[:MAX_MATERIAL])
            if real:
                warns.append("The pasted text was sent to the AI providers (client names and secrets removed first). Do not paste passwords, card numbers or anything the client has not agreed to share.")
    return experience.scrub("\n\n".join(parts)), warns


def _sample() -> bool:
    from app.services import clients
    return clients.sample()


# ------------------------------------------------------------ prompts
BASE = ("You are one of three assistants who each do the same job independently for a one-person freelance service in Henderson, Nevada. The owner will read, "
        "check and edit your work before anyone sees it. Use ONLY the job description and material given. Never invent numbers, file contents, model names, "
        "prices, laws or results. If something needed is missing, say so and say what you would need. Plain text, short headings, no markdown tables.")
WORK = (" Do the job: produce the finished work product as the owner would hand it over (analysis steps with the numbers from the facts given, a plan, requirements, "
        "a calculation with units, a fixed code snippet). End with two short sections: Assumptions, and What I could not check. Where you did arithmetic, show it. "
        "If code is involved, show the full corrected code and a test.")
ADVICE = (" This is an IT, network or security job and you cannot see or touch the equipment. Do NOT say anything was fixed or checked. Write a numbered "
          "checklist of what to check first (safest and easiest first), the likely causes in order, questions to ask the client, and how the owner will confirm it is fixed. "
          "No commands that delete data, change security settings or need administrator rights.")
JUDGE = ("You are the judge. Three assistants did the same job independently. Read the job, the material, and the three drafts. Write the best single final version: "
         "keep what is correct and well supported, fix mistakes you can see, drop anything not supported by the material, and where the drafts disagree on a fact or number "
         "say so plainly instead of picking silently. Do not add new facts. Then write the line  " + SPLIT + "  and under it, in under 120 words: which draft was strongest, "
         "where they disagreed, and the specific things the owner must verify before using it. Plain text.")


def _once(provider: str, system: str, prompt: str, adapters: dict | None) -> dict | None:
    if not (adapters and provider in adapters) and not providers.api_key(provider):
        return None
    try:
        return llm_router.complete(system, prompt, "medium", provider, adapters)
    except AiError:
        return None
    except Exception:  # noqa: BLE001 - one provider's SDK failure must not stop the other two
        return None


def run(jid: int, instructions: str = "", material: str = "", adapters: dict | None = None) -> dict:
    from app.services import clients as cl
    cfg = config()
    if not cfg["enabled"]:
        raise TeamError("The work team is switched off. Turn it on in the job bar first.", 403)
    if ai_policy.describe()["mode"] == "off":
        raise TeamError("AI is switched off for this workspace in Settings.", 403)
    if used_today() >= cfg["daily_cap"]:
        raise TeamError(f"The daily cap of {cfg['daily_cap']} team runs is used up. It resets tomorrow (UTC), or raise the cap.", 429)
    try:
        j = cl.job_totals(int(jid))["job"]
    except cl.ClientError as e:
        raise TeamError(e.message, e.status) from None
    fkey = ((jobfield.of_job(j) or {}).get("key")) or jobfield.guess(j["title"]) or ""
    advice = fkey in ADVICE_FIELDS
    kit = practice_kits.for_title(j["title"])
    mat, warns = _material(int(jid), material, kit)
    brief = (kit["brief"] if kit and not _real() else "")
    task = [f"Job: {experience.scrub(j['title'])}"]
    if brief:
        task.append(f"Brief: {brief}")
    ins = experience.scrub((instructions or "").strip())[:1500]
    if ins:
        task.append(f"Owner's instructions: {ins}")
    if not mat and not advice and not brief and not ins:
        raise TeamError("Tell the team what the job needs: add a line of instructions or paste the material to work from.")
    if not mat and not advice and _real():
        warns.append("No material was given, so the team can only write a plan and the questions it needs answered.")
    prompt = "\n".join(task) + ("\n\nMATERIAL:\n" + mat if mat else "")
    system = BASE + (ADVICE if advice else WORK) + assistants.role_prompt(fkey)
    state.kv_set(_ukey(), str(used_today() + 1))
    drafts, failed = [], []
    for p in DRAFTERS:
        r = _once(p, system, prompt, adapters)
        if r:
            drafts.append({"provider": p, "label": LABELS[p], "model": r.get("model", ""), "text": r["text"][:MAX_DRAFT]})
        else:
            failed.append(LABELS[p])
    if not drafts:
        raise TeamError("None of the three AIs could answer. Check the keys in backend/.env (python scripts/check_ai_keys.py) and try again.", 502)
    final, notes, judge = drafts[0]["text"], "", ""
    if len(drafts) > 1:
        jp = prompt + "\n\n" + "\n\n".join(f"DRAFT {chr(65 + i)} ({d['label']}):\n{d['text']}" for i, d in enumerate(drafts))
        for p in JUDGES:
            r = _once(p, JUDGE + (ADVICE if advice else ""), jp, adapters)
            if r:
                judge = LABELS[p]
                a, _, b = r["text"].partition(SPLIT)
                final, notes = a.strip()[:MAX_FINAL], b.strip()[:1200]
                break
        if not judge:
            notes = "The judge could not answer, so Draft A is shown unjudged. Compare the drafts below."
    else:
        notes = f"Only {drafts[0]['label']} answered, so there was nothing to compare and no judge. Treat it as a single first pass."
    out = {"text": final, "judge_notes": notes, "judge": judge, "drafts": drafts, "failed": failed, "mode": "advice" if advice else "work",
           "field": fkey, "warnings": warns, "workspace": "practice" if not _real() else "real", "kind": "team", "title": f"Team draft: {j['title']}",
           "status": "pending", "edited": False, "model": judge or drafts[0]["label"], "at": state.now()}
    d = prep._drafts()
    d[f"team:{jid}"] = out
    prep._save(d)
    assistants.record("draft", f"team:{jid}", out["title"])
    state.audit("workteam_run", f"job {jid} drafters={len(drafts)} judge={judge or 'none'}")
    return {"key": f"team:{jid}", **out, "used_today": used_today()}


def _real() -> bool:
    return not _sample()


def kit_for_job(jid: int) -> dict | None:
    """The practice kit for this job (Practice workspace only). The answer key is NOT included; ask for it separately."""
    from app.services import clients as cl
    if _real():
        return None
    try:
        j = cl.job_totals(int(jid))["job"]
    except cl.ClientError as e:
        raise TeamError(e.message, e.status) from None
    k = practice_kits.for_title(j["title"])
    if not k:
        return None
    return {k2: v for k2, v in k.items() if k2 != "answer"}


def kit_answer(jid: int) -> dict:
    from app.services import clients as cl
    if _real():
        raise TeamError("Answer keys exist only for practice jobs.", 404)
    try:
        j = cl.job_totals(int(jid))["job"]
    except cl.ClientError as e:
        raise TeamError(e.message, e.status) from None
    k = practice_kits.for_title(j["title"])
    if not k:
        raise TeamError("This job has no practice kit.", 404)
    return {"answer": k["answer"], "note": "Computed from the practice files. Try the job first, then compare. Your answer can be right and worded differently."}
