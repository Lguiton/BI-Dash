"""Study progress: tick off steps of each career track; powers the widget on the main dashboard."""
import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.routers import tracks
from app.services import study

router = APIRouter(prefix="/api/progress", tags=["progress"])


class ProgressIn(BaseModel):
    item: str = Field(min_length=3, max_length=120)
    done: bool


@router.get("")
def get_progress():
    done = study.done_items()
    out, last_done = [], None
    for t in tracks.TRACKS:
        steps = t["path"]
        finished = [s for s in steps if s["id"] in done]
        nxt = next((s for s in steps if s["id"] not in done), None)
        latest = max((done[s["id"]] for s in finished), default=None)
        out.append({"id": t["id"], "name": t["name"], "done": len(finished), "total": len(steps),
                    "pct": round(100 * len(finished) / len(steps)) if steps else 0,
                    "next": ({k: nxt.get(k) for k in ("id", "kind", "label", "href", "path", "why")} if nxt else None),
                    "last_activity": latest})
    active = [t for t in out if t["next"] and t["last_activity"]]
    cont = max(active, key=lambda t: t["last_activity"]) if active else next((t for t in out if t["next"]), None)
    total, finished_total = sum(t["total"] for t in out), sum(t["done"] for t in out)
    return {"done": sorted(done), "tracks": out, "overall_pct": round(100 * finished_total / total) if total else 0,
            "continue": {"track": cont["id"], "track_name": cont["name"], "step": cont["next"]} if cont else None}


@router.put("")
def set_progress(body: ProgressIn):
    if not re.fullmatch(r"[a-z]+:[a-z0-9-]+", body.item) or body.item not in tracks.STEP_IDS:
        raise HTTPException(404, "Unknown study item.")
    study.set_done(body.item, body.done)
    return {"item": body.item, "done": body.done}
