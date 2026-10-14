"""One registry of the mistakes found in the source material (posters, course readings, transcripts).

Each lab module keeps its own SLIPS list next to the code it affects. This module gathers them so that:
  * an agent can be handed the few corrections that match what the user just asked, instead of every note, and
  * a consistency check can scan the manuals, quizzes and agent notes for a claim that a correction contradicts.
Add a correction in the module where it belongs; it appears here by itself. Notes about the source, not facts about the world.
"""
from __future__ import annotations

import importlib
import re

# module -> (attribute holding a list of strings, tracks the notes help)
SOURCES: dict[str, tuple[str, tuple[str, ...]]] = {
    "ai_gov": ("SLIPS", ("ai", "security", "engineering")),
    "dax_lab": ("SLIPS", ("analyst",)),
    "doc_reader": ("SLIPS", ("analyst",)),
    "endpoint_audit": ("SLIPS", ("security", "itsupport")),
    "honeypot": ("SLIPS", ("security",)),
    "cpe_lab": ("SLIPS", ("cpe", "itsupport", "network")),
    "auto_elec": ("SLIPS", ("cpe",)),
    "cpe_sim": ("SLIPS", ("cpe",)),
    "veh_decode": ("SLIPS", ("cpe",)),
    "ai_vendor": ("SLIPS", ("ai", "pm", "sysanalyst", "engineering", "security")),
    "survey_stats": ("SLIPS", ("analyst", "scientist", "ml", "pm")),
    "courses": ("SLIPS", ("ai", "ml", "scientist")),
    "leadership": ("SLIPS", ("pm", "sysanalyst")),
    "ai_impl": ("SLIPS", ("ai", "pm", "sysanalyst", "engineering")),
    "info_audit": ("SLIPS", ("sysanalyst", "engineering", "analyst")),
    "it_fund": ("SLIPS", ("itsupport",)),
    "it_ops": ("SLIPS_IT2", ("itsupport", "network", "security")),
    "learn_path": ("SLIPS", ("ai", "ml")),
    "ml_concepts": ("SLIPS", ("ml", "ai", "scientist")),
    "mlops_lab": ("SLIPS", ("ml", "ai", "engineering")),
    "pylib_map": ("SLIPS", ("ai", "ml", "engineering", "fullstack")),
    "net_design": ("SLIPS", ("network", "itsupport")),
    "net_sim": ("SLIPS", ("network", "itsupport")),
    "net_pcap": ("SLIPS", ("network", "itsupport")),
    "net_gen": ("SLIPS", ("network",)),
    "sec_frame": ("SLIPS", ("security", "network", "itsupport")),
    "data_dbt": ("SLIPS", ("engineering", "analyst")),
    "data_calc": ("SLIPS", ("engineering", "analyst")),
    "data_flow": ("SLIPS", ("engineering",)),
    "ml_build": ("SLIPS", ("ml", "ai", "scientist")),
    "backup_lab": ("SLIPS", ("itsupport", "network", "engineering")),
    "sec_tools": ("SLIPS", ("security", "itsupport")),
    "relational_lab": ("SLIPS", ("engineering", "sysanalyst")),
    "se_lab": ("SLIPS", ("fullstack", "sysanalyst")),
}
EXTRA_TEXT = {"bi_calc": ("analyst", "scientist")}  # slips are built inside a function; read via dist_reference()

_STOP = set("the a an and or of to in on for is are was were be that this with as at by it its not no from but if then than so such can may will "
            "which what when where who how why does do did has have had into out up about over under also only more most each other these those their there "
            "they them you your one two".split())
_cache: list[dict] | None = None


def _words(t: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9+#.]{3,}", t.lower()) if w not in _STOP}


def all_items() -> list[dict]:
    global _cache
    if _cache is not None:
        return _cache
    out: list[dict] = []
    for mod, (attr, tracks) in SOURCES.items():
        m = importlib.import_module(f"app.services.{mod}")
        for i, text in enumerate(getattr(m, attr)):
            out.append({"id": f"{mod}:{i}", "module": mod, "tracks": list(tracks), "text": text, "words": _words(text)})
    try:
        from app.services import bi_calc
        for i, text in enumerate(bi_calc.dist_reference()["slips"]):
            out.append({"id": f"bi_calc:{i}", "module": "bi_calc", "tracks": list(EXTRA_TEXT["bi_calc"]), "text": text, "words": _words(text)})
    except Exception:  # noqa: BLE001 - a missing optional source must not break the agents
        pass
    _cache = out
    return out


def public(track: str | None = None) -> list[dict]:
    return [{k: v for k, v in it.items() if k != "words"} for it in all_items() if track is None or track in it["tracks"]]


def relevant(track: str, message: str, limit: int = 3, min_overlap: int = 2) -> list[dict]:
    """The few corrections that share the most distinctive words with the question, for this track."""
    q = _words(message)
    if not q:
        return []
    scored = []
    for it in all_items():
        if track in it["tracks"]:
            n = len(q & it["words"])
            if n >= min_overlap:
                scored.append((n, it))
    scored.sort(key=lambda x: -x[0])
    return [it for _, it in scored[:limit]]


def prompt_text(track: str, message: str) -> str:
    rel = relevant(track, message)
    if not rel:
        return ""
    lines = "\n".join(f"- {it['text'][:420]}" for it in rel)
    return ("\n\nKNOWN SOURCE MISTAKES that match this question (the course material or poster got these wrong; "
            "correct them if the user relies on them):\n" + lines)
