"""Knowledge base search over this project's own docs and the track manuals.

Honest label: this is keyword search ranked with TF-IDF (rare words count more). It finds passages that share words with your
question; it does not understand meaning, so "cost" will not find a passage that only says "spend". It is not a vector database or RAG.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

from app.services import manuals

ROOT = Path(__file__).resolve().parents[3]
STOP = set("a an and are as at be by for from has have how i in is it its of on or that the this to was what when where which who why will with you your do does can".split())
MAX_FILE = 400_000
_cache: dict = {"key": None, "chunks": [], "df": Counter(), "n": 0}


def _tok(text: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9_]{2,}", text.lower()) if w not in STOP]


def _doc_files() -> list[Path]:
    files = [p for p in (ROOT / "README.md", ROOT / "LEARNING.md") if p.is_file()]
    d = ROOT / "docs"
    if d.is_dir():
        files += sorted(d.glob("*.md"))
    return files


def _chunks_for(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE]
    except OSError:
        return []
    out, head, buf = [], path.stem.replace("_", " ").title(), []

    def flush():
        body = "\n".join(buf).strip()
        if len(body) > 40:
            out.append({"source": f"{path.parent.name}/{path.name}" if path.parent.name == "docs" else path.name, "title": head, "text": body[:1500], "href": None})
    for line in text.splitlines():
        if re.match(r"^#{1,3}\s", line):
            flush(); buf = []
            head = line.lstrip("# ").strip()[:100]
        else:
            buf.append(line)
    flush()
    return out


def _manual_chunks() -> list[dict]:
    out = []
    for tid, m in manuals.MANUALS.items():
        for s in m["steps"]:
            txt = f"{s['what']} " + " ".join(s["how"]) + f" Done when: {s['done_when']} " + " ".join(s["mistakes"])
            out.append({"source": f"Manual: {tid}", "title": s["title"], "text": txt, "href": f"/tracks/{tid}?view=manual&step={s['id']}"})
    return out


def _index() -> dict:
    files = _doc_files()
    key = tuple((str(p), p.stat().st_mtime_ns) for p in files)
    if _cache["key"] == key and _cache["chunks"]:
        return _cache
    chunks = [c for p in files for c in _chunks_for(p)] + _manual_chunks()
    df: Counter = Counter()
    for c in chunks:
        c["tf"] = Counter(_tok(c["title"] + " " + c["title"] + " " + c["text"]))
        c["len"] = max(1, sum(c["tf"].values()))
        df.update(c["tf"].keys())
    _cache.update(key=key, chunks=chunks, df=df, n=len(chunks))
    return _cache


def _snippet(text: str, terms: set[str], width: int = 220) -> str:
    flat = re.sub(r"\s+", " ", text)
    low = flat.lower()
    pos = min((low.find(t) for t in terms if t in low), default=0)
    start = max(0, pos - 60)
    return ("…" if start else "") + flat[start:start + width] + ("…" if start + width < len(flat) else "")


def search(query: str, limit: int = 8) -> dict:
    q = _tok(query or "")
    if not q:
        return {"query": query, "results": [], "indexed": _index()["n"], "note": "Type a few words to search."}
    ix = _index()
    n = ix["n"]
    scored = []
    for c in ix["chunks"]:
        s = 0.0
        for t in set(q):
            tf = c["tf"].get(t, 0)
            if tf:
                s += (1 + math.log(tf)) * math.log(1 + n / ix["df"][t])
        if s:
            scored.append((s / math.sqrt(c["len"]), c))
    scored.sort(key=lambda x: -x[0])
    top = scored[:max(1, min(limit, 20))]
    best = top[0][0] if top else 1
    return {"query": query, "indexed": n, "results": [{"title": c["title"], "source": c["source"], "href": c["href"], "score": round(s / best, 2), "snippet": _snippet(c["text"], set(q))} for s, c in top],
            "note": "Keyword search ranked by TF-IDF over this project's docs and manuals. It matches words, not meaning."}
