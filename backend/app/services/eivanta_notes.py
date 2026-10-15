"""'Learned for Eivanta': one line after a job about what this client's data or questions taught you for the product you sell.

Kept per workspace. Client names are removed when a note is saved (and secrets blanked), so the list can be exported and shared with
Eivanta's notes without carrying a client into them. Practice-workspace notes are marked as sample. Nothing here is sent anywhere."""
from __future__ import annotations

from app.services import clients, experience, state, workspaces

TAGS = {"ingestion": "Messy file or import", "forecast": "Short history or forecast", "brief": "Owner's brief or report", "onboarding": "Time to first number",
        "questions": "A question the owner asked", "other": "Something else"}
MAX_TEXT = 300
MAX_NOTES = 500


class NoteError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _load() -> list[dict]:
    return list(state.setting_get(workspaces.active(), "eivanta_notes", []) or [])


def add(b: dict) -> dict:
    tag = b.get("tag") or "other"
    if tag not in TAGS:
        raise NoteError("Pick one of: " + ", ".join(TAGS) + ".")
    text = experience.scrub(str(b.get("text") or "").strip())[:MAX_TEXT]
    if not text:
        raise NoteError("Write a line first.")
    job_title, jid = "", None
    if b.get("job_id") not in (None, "", 0):
        try:
            jid = int(b["job_id"])
            job_title = experience.scrub(clients.job_totals(jid)["job"]["title"])[:120]
        except (TypeError, ValueError, clients.ClientError):
            raise NoteError("No such job.", 404) from None
    rows = _load()
    if len(rows) >= MAX_NOTES:
        raise NoteError(f"You already have {MAX_NOTES} notes. Export and delete some.")
    n = {"id": max([r["id"] for r in rows], default=0) + 1, "job_id": jid, "job": job_title, "tag": tag, "tag_label": TAGS[tag], "text": text,
         "at": state.now()[:10], "sample": clients.sample()}
    state.setting_set(workspaces.active(), "eivanta_notes", rows + [n])
    state.audit("eivanta_note", tag)
    return n


def listing(job_id: int | None = None) -> dict:
    rows = _load()
    if job_id is not None:
        rows = [r for r in rows if r["job_id"] == job_id]
    return {"notes": list(reversed(rows)), "tags": TAGS, "note": "Client names are removed when a note is saved."}


def delete(nid: int) -> dict:
    rows = _load()
    if not any(r["id"] == nid for r in rows):
        raise NoteError("No such note.", 404)
    state.setting_set(workspaces.active(), "eivanta_notes", [r for r in rows if r["id"] != nid])
    return {"deleted": nid}


def markdown() -> str:
    rows = _load()
    out = ["# Learned for Eivanta", "", "Lines from freelance jobs. Client names removed. Entries marked (sample) came from the Practice workspace.", ""]
    for tag, label in TAGS.items():
        mine = [r for r in rows if r["tag"] == tag]
        if mine:
            out += [f"## {label}", ""] + [f"- {r['text']}" + (f" ({r['job']})" if r["job"] else "") + (" (sample)" if r["sample"] else "") + f" [{r['at']}]" for r in mine] + [""]
    if not rows:
        out.append("No notes yet.")
    return "\n".join(out)
