"""Tool map: for the tools people name in job ads, what this app has, what it replaces, and what it deliberately doesn't embed.

Status
  built         a working feature in this app does the same job at personal scale
  partial       covers the core idea only; the note says what is missing
  taught        explained in a manual, but not embedded (offensive or dual-use, or needs a lab)
  not_embedded  cloud, paid or too large to embed here; the note says the free route
"""
from __future__ import annotations

from app.services import content

S = lambda tool, status, where, note, href=None: {"tool": tool, "status": status, "where": where, "note": note, "href": href}  # noqa: E731

MAP: dict[str, list[dict]] = content.load_toolmap()   # content/toolmap.json, checked when loaded


def tool_map() -> dict:
    cats = [{"category": c, "tools": t} for c, t in MAP.items()]
    counts: dict[str, int] = {}
    for c in cats:
        for t in c["tools"]:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
    return {"categories": cats, "counts": counts,
            "legend": {"built": "A working feature does the same job at personal scale", "partial": "Covers the core idea; the note says what is missing",
                       "taught": "Explained, not embedded", "not_embedded": "Cloud, paid or offensive: not built here"}}
