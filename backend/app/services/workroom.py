"""Work Room: paste a client's issue (or say "build X" / "fix Y") and the agents do the whole job inside the dashboard.

Two screens read from here: the owner's CHECKLIST (the job's ordered steps, which only the owner ticks) and the AGENTS' WORK
(what the agents already produced for each step). The agents never tick a step, never send anything and never touch equipment or
the owner's tables. Everything is a draft to verify with outside tools. Runs go on in the background and the page polls status."""
from __future__ import annotations

import json
import threading
from datetime import datetime

from app.services import agents, ai_policy, autopilot, codecheck, clients as cl, job_intake, jobfield, jobpage, prep, state, worklog

MAX_STEPS = 14
ADVICE_FIELDS = {"itsupport", "network", "security"}
_lock = threading.Lock()
_RUNS: dict[int, dict] = {}


class RoomError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _key(jid: int) -> str:
    return f"wr:{jid}"


def _load(jid: int) -> dict:
    return prep._drafts().get(_key(jid)) or {"request": "", "results": {}, "autopilot": None, "reply": None, "instructions": ""}


def _store(jid: int, data: dict) -> None:
    with _lock:
        d = prep._drafts()
        d[_key(jid)] = data
        prep._save(d)


def _job(jid: int) -> tuple[dict, str]:
    try:
        j = cl.job_totals(int(jid))["job"]
    except cl.ClientError as e:
        raise RoomError(e.message, e.status) from None
    fkey = ((jobfield.of_job(j) or {}).get("key")) or jobfield.guess(j["title"]) or ""
    return j, fkey


def _steps(jid: int, include_done: bool = True) -> list[dict]:
    rows = [r for r in worklog.listing(include_done=True)["items"] if r.get("job_id") == jid]
    return sorted(rows, key=lambda r: r["id"])


def begin(request: str, client: str = "", field: str | None = None) -> dict:
    """Turn pasted text (a client message, 'build X', 'fix Y') into an active job with the field's usual steps. Nothing is sent."""
    request = (request or "").strip()
    if len(request) < 5:
        raise RoomError("Paste the client's message, or describe what to build or fix.")
    try:
        sug = job_intake.read(request)
    except ValueError as e:
        raise RoomError(str(e)) from None
    title = (sug.get("title") or request.splitlines()[0])[:110] or "New job"
    fkey = field or (sug.get("field") or {}).get("key") or jobfield.guess(title + " " + request[:600])
    name = (client or sug.get("client") or "").strip() or "New client (rename me)"
    try:
        r = jobpage.quick_start(title, name, None, fkey, True, sug.get("due"), ((sug.get("quote") or {}).get("suggested")))
    except cl.ClientError as e:
        raise RoomError(e.message, e.status) from None
    jid = r["job"]["id"]
    data = _load(jid)
    data["request"] = request[:6000]
    _store(jid, data)
    state.audit("workroom_begin", f"job {jid} field={fkey}")
    return {"job_id": jid, "title": title, "field": jobfield.info(fkey), "client": name, "steps": [x["title"] for x in r["work_items"]]}


def view(jid: int) -> dict:
    j, fkey = _job(jid)
    run = dict(_RUNS.get(jid) or {"state": "idle", "done": 0, "total": 0, "current": ""})   # read the run state BEFORE the saved results, so "done" never shows with stale results
    data = _load(jid)
    steps = []
    for s in _steps(jid):
        res = data["results"].get(str(s["id"]))
        steps.append({"id": s["id"], "title": s["title"], "done": s["status"] == "done", "status": s["status"], "agent": res})
    return {"job": {"id": j["id"], "title": j["title"], "status": j["status"], "field": jobfield.info(fkey)},
            "request": data.get("request", ""), "instructions": data.get("instructions", ""), "steps": steps, "autopilot": data.get("autopilot"),
            "reply": data.get("reply"), "run": {k: run.get(k) for k in ("state", "done", "total", "current", "error")},
            "advice_only": fkey in ADVICE_FIELDS,
            "disclaimer": "Drafts by AI. They can be wrong, nothing was sent to a client and nothing was checked on real equipment. Verify with your own tools before you use or send anything."}


def _prompt(j: dict, s: dict, advice: bool, ins: str, n: int, total: int) -> str:
    base = f'Step {n} of {total} of the job "{j["title"][:100]}": "{s["title"][:180]}". '
    if advice:
        base += ("Give the exact checklist for this step, likely causes in order, what to look at and what each result means, and questions to ask. "
                 "You cannot see the equipment: never say anything was checked or fixed. ")
    else:
        base += ("DO the work now with the information given (the client's request and any file analysis are in the source text). Produce the actual result: "
                 "the numbers, the finished text, the code or configuration, the query, the plan, not advice about what to do. "
                 "Explain in plain words for someone new to this field, say what you assumed, and say clearly what you could not check. ")
    if ins:
        base += f"Owner's instructions: {ins[:300]}. "
    return base[:1190]


def _work(jid: int, instructions: str, file: tuple[str, bytes] | None) -> None:
    run = _RUNS[jid]
    try:
        j, fkey = _job(jid)
        data = _load(jid)
        data["instructions"] = instructions
        advice = fkey in ADVICE_FIELDS
        if file:
            run["current"] = "Running the analyses on your file"
            try:
                data["autopilot"] = autopilot.run(file[0], file[1], data.get("request", ""), fkey)
            except autopilot.AutoError as e:
                data["autopilot"] = {"file": file[0], "error": e.message}
            _store(jid, data)
        steps = [s for s in _steps(jid) if s["status"] != "done"][:MAX_STEPS]
        run["total"] = len(steps) + 1
        ctx = "CLIENT REQUEST:\n" + (data.get("request") or j["title"])[:3500]
        ap = data.get("autopilot")
        if ap and not ap.get("error"):
            ctx += "\n\nAUTOMATIC ANALYSIS OF THE UPLOADED FILE (" + ap["file"] + "):\n" + "\n".join(
                f"- {s['title']} [{s['status']}]: {s['plain']}" for s in ap["steps"])[:3500]
        elif ap:
            ctx += f"\n\nThe uploaded file {ap['file']} could not be analysed: {ap['error']}"
        prior: list[str] = []
        for n, s in enumerate(steps, 1):
            run["current"] = s["title"]
            src = (ctx + ("\n\nEARLIER STEPS (build on them):\n" + "\n".join(prior))[:3000] if prior else ctx)[:11800]
            try:
                r = agents.chat(fkey, _prompt(j, s, advice, instructions, n, len(steps)), [], None, "auto", None, "auto", "default", src, None, int(jid))
                text = r.reply.strip()
                try:
                    checks = codecheck.verify_blocks(text)       # code the agent wrote is compiled/simulated for real; C is never run automatically
                except Exception:  # noqa: BLE001
                    checks = []
                data["results"][str(s["id"])] = {"status": "ready", "text": text[:6000], "model": agents.AGENTS[fkey]["name"], "at": state.now(), "checks": checks}
                if any(c["status"] == "fail" for c in checks):
                    prior.append("NOTE: the code in the step below FAILED its real check: " + "; ".join(c["plain"][:140] for c in checks if c["status"] == "fail"))
                prior.append(f"Step {n} ({s['title'][:60]}): {text[:380]}")
            except agents.AgentError as e:
                data["results"][str(s["id"])] = {"status": "failed", "text": "", "error": e.message, "at": state.now()}
                if getattr(e, "status", 400) in (403, 429):
                    run["error"] = e.message
                    run["done"] += 1
                    _store(jid, data)
                    break
            except Exception as e:  # noqa: BLE001 - one provider failure must not lose the other steps
                data["results"][str(s["id"])] = {"status": "failed", "text": "", "error": str(e)[:160], "at": state.now()}
            run["done"] += 1
            _store(jid, data)
        ready = [k for k in data["results"].values() if k.get("status") == "ready"]
        if ready and not run.get("error"):
            run["current"] = "Drafting the reply to the client (not sent)"
            try:
                r = agents.chat(fkey, ("Write the reply to the client for this job: what was found or done in plain words, what they should do next, and anything "
                                       "you could not check. Short, friendly, no jargon. A DRAFT that will not be sent until I read it."), [], None, "auto", None,
                                "auto", "default", (ctx + "\n\nWORK DONE:\n" + "\n".join(prior))[:11800], None, int(jid))
                data["reply"] = {"text": r.reply.strip()[:3000], "at": state.now()}
            except Exception:  # noqa: BLE001 - the reply is a bonus; the step work is already saved
                pass
        run["done"] = run["total"]
        if not ready and not run.get("error"):
            run["error"] = "No step could be worked. Check the AI keys in Settings."
        _store(jid, data)
        run["state"] = "done" if ready else "failed"
        state.audit("workroom_run", f"job {jid} field={fkey} steps={len(ready)}/{len(steps)}")
    except Exception as e:  # noqa: BLE001
        run["state"], run["error"] = "failed", f"{e.__class__.__name__}: {str(e)[:200]}"
    finally:
        if run["state"] == "running":
            run["state"] = "done"
        run["finished"] = datetime.now().isoformat(timespec="seconds")


def run_job(jid: int, instructions: str = "", file: tuple[str, bytes] | None = None, wait: bool = False) -> dict:
    if ai_policy.describe()["mode"] == "off":
        raise RoomError("AI is switched off for this workspace in Settings, so the agents can't work the job. The checklist still works.", 403)
    _, fkey = _job(jid)
    if fkey not in agents.AGENTS:
        raise RoomError("Pick a field for this job first, so the right agent is used.")
    with _lock:
        if (_RUNS.get(jid) or {}).get("state") == "running":
            raise RoomError("The agents are already working this job.", 409)
        _RUNS[jid] = {"state": "running", "done": 0, "total": 1, "current": "Starting", "error": None}
    if wait:
        _work(jid, (instructions or "")[:400], file)
    else:
        threading.Thread(target=_work, args=(jid, (instructions or "")[:400], file), daemon=True).start()
    return view(jid)


def save_request(jid: int, text: str) -> dict:
    _job(jid)
    data = _load(jid)
    data["request"] = (text or "").strip()[:6000]
    _store(jid, data)
    return view(jid)


def tick(jid: int, wid: int, done: bool) -> dict:
    """The owner's checklist: only the owner ticks a step."""
    if not any(s["id"] == wid for s in _steps(jid)):
        raise RoomError("That step isn't on this job.", 404)
    worklog.update(wid, {"status": "done" if done else "todo"})
    return view(jid)


def json_dump(jid: int) -> str:
    return json.dumps(view(jid), indent=1)
