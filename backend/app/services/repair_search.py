"""Search the repair guides by exact words, near-matches (typos, plurals) and related words. Runs locally, no AI."""
from __future__ import annotations

import re
from difflib import get_close_matches

from app.services import it_repair

RELATED = {
    "wifi": ["wireless", "router", "network", "internet"], "slow": ["lag", "freezing", "performance"], "wont": ["not", "dead", "no"], "boot": ["start", "startup", "power"],
    "screen": ["display", "monitor", "cracked", "lcd"], "battery": ["charge", "charging", "power", "drain"], "virus": ["malware", "popup", "infected"],
    "noise": ["sound", "audio", "speaker", "whine"], "printer": ["print", "toner", "ink", "paper"], "camera": ["cctv", "dash", "doorbell"],
    "bike": ["ebike", "scooter", "motor"], "car": ["vehicle", "obd", "engine"], "password": ["login", "locked", "profile"],
}
_W = re.compile(r"[a-z0-9]+")


def _tok(s: str) -> list[str]:
    return [w[:-1] if len(w) > 3 and w.endswith("s") else w for w in _W.findall(s.lower().replace("'", ""))]


def _blob(g: dict) -> dict[str, set[str]]:
    return {"title": set(_tok(g["title"] + " " + g["area"])), "symptoms": set(_tok(" ".join(g["symptoms"]))), "causes": set(_tok(" ".join(g["causes"]))),
            "steps": set(_tok(" ".join(g["steps"]))), "tools": set(_tok(" ".join(g["tools"])))}


def search(q: str, limit: int = 8, extra: list[dict] | None = None) -> dict:
    words = _tok(q)[:12]
    if not words:
        return {"query": q, "results": []}
    guides = it_repair.GUIDES
    vocab = sorted({w for g in guides for part in _blob(g).values() for w in part})
    exp = set()
    for w in words:
        exp.add(w)
        for m in get_close_matches(w, vocab, n=2, cutoff=0.82):
            exp.add(m)
        exp.update(RELATED.get(w, []))
    weights = {"title": 5, "symptoms": 4, "causes": 2, "tools": 1.5, "steps": 1}
    out = []
    for g in guides:
        b = _blob(g)
        score = 0.0
        hit = set()
        for w in exp:
            direct = w in words
            for part, wt in weights.items():
                if w in b[part]:
                    score += wt * (1 if direct else 0.5)
                    hit.add(w)
        if score:
            out.append({"id": g["id"], "title": g["title"], "area": g["area"], "score": round(score, 1), "matched": sorted(hit)[:6], "symptoms": g["symptoms"][:3]})
    for e in extra or []:
        text = set(_tok(" ".join(str(v) for v in e.values())))
        s = sum(2 for w in exp if w in text)
        if s:
            out.append({"id": "job-" + str(e.get("id", "")), "title": "Your past job: " + str(e.get("title", ""))[:80], "area": "Your saved fixes", "score": float(s), "matched": sorted(set(words) & text), "symptoms": []})
    out.sort(key=lambda r: -r["score"])
    return {"query": q, "results": out[:limit]}
