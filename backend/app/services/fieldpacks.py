"""Field packs: small, honest tool sets for extra professional fields.

Each pack has a label, a few tools (a form in, a plain-English result out) and its how-to/fix guides (added to field_howto).
Tools are calculators, checkers and document writers. They never run commands, never send anything anywhere and never change your data."""
from __future__ import annotations

import html
import re

PACKS: dict[str, dict] = {}


class PackError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def I(name, label, kind="text", default="", options=None, help=""):  # noqa: E741, N802
    return {"name": name, "label": label, "kind": kind, "default": default, "options": options or [], "help": help}


def pack(pid, label, group, blurb, agent, examples, keywords):
    PACKS[pid] = {"id": pid, "label": label, "group": group, "blurb": blurb, "agent": agent, "examples": examples, "keywords": keywords, "tools": {}}


def tool(pid, tid, title, note, inputs):
    def deco(fn):
        PACKS[pid]["tools"][tid] = {"id": tid, "title": title, "note": note, "inputs": inputs, "fn": fn}
        return fn
    return deco


# ---------------------------------------------------------------- input helpers
def txt(v, name, n=300, required=False) -> str:
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", str(v.get(name) if v.get(name) is not None else ""))[:n].strip()
    if required and not s:
        raise PackError(f"{name.replace('_', ' ').capitalize()} is needed.")
    return s


def num(v, name, lo=None, hi=None, default=None, label=None) -> float:
    raw = v.get(name)
    if raw in (None, ""):
        if default is not None:
            return float(default)
        raise PackError(f"{label or name.replace('_', ' ').capitalize()} is needed.")
    try:
        x = float(str(raw).replace(",", "").replace("$", "").replace("%", ""))
    except ValueError:
        raise PackError(f"{label or name.replace('_', ' ').capitalize()} must be a number.") from None
    if x != x or x in (float("inf"), float("-inf")):
        raise PackError(f"{label or name.replace('_', ' ').capitalize()} must be a real number.")
    if lo is not None and x < lo:
        raise PackError(f"{label or name.replace('_', ' ').capitalize()} must be at least {lo:g}.")
    if hi is not None and x > hi:
        raise PackError(f"{label or name.replace('_', ' ').capitalize()} must be at most {hi:g}.")
    return x


def rows(v, name, n=200, each=300) -> list[str]:
    return [re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", ln).strip()[:each] for ln in str(v.get(name) or "").splitlines() if ln.strip()][:n]


def split(line: str) -> list[str]:
    return [c.strip() for c in re.split(r"\s*[,|\t]\s*", line.strip())]


def numlist(v, name, min_n=2, max_n=5000) -> list[float]:
    out = []
    for tok in re.split(r"[\s,;]+", str(v.get(name) or "")):
        if not tok:
            continue
        try:
            out.append(float(tok))
        except ValueError:
            raise PackError(f"'{tok[:20]}' in {name.replace('_', ' ')} is not a number.") from None
    if len(out) < min_n:
        raise PackError(f"Give at least {min_n} numbers for {name.replace('_', ' ')}.")
    return out[:max_n]


def md(title: str, sections: list[tuple[str, list[str] | str]]) -> str:
    out = [f"# {title}", ""]
    for h, body in sections:
        out += [f"## {h}", ""]
        out += [f"- {b}" for b in body] if isinstance(body, list) else [body]
        out.append("")
    return "\n".join(out).strip() + "\n"


def page(title: str, body_html: str) -> str:
    return (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><title>{html.escape(title)}</title><style>body{{font-family:system-ui,sans-serif;max-width:820px;margin:24px auto;padding:0 16px;color:#111}}"
            "table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:6px;text-align:left;vertical-align:top}th{background:#f3f3f3}h2{font-size:15px;border-bottom:1px solid #ccc;margin-top:20px}</style></head>"
            f"<body><h1>{html.escape(title)}</h1>{body_html}</body></html>")


E = html.escape


def table_html(head: list[str], body: list[list]) -> str:
    return "<table><tr>" + "".join(f"<th>{E(str(h))}</th>" for h in head) + "</tr>" + "".join("<tr>" + "".join(f"<td>{E(str(c))}</td>" for c in r) + "</tr>" for r in body) + "</table>"


# ---------------------------------------------------------------- public api
PLACE = {"biz": "/toolbox?role=pm&pack=biz", "itpm": "/toolbox?role=pm&pack=itpm", "revops": "/toolbox?role=bi&pack=revops", "devops": "/toolbox?role=fs&pack=devops", "cv": "/toolbox?role=ml&pack=cv",
         "devsecops": "/toolbox?role=sec&pack=devsecops", "revsec": "/toolbox?role=sec&pack=revsec", "cds": "/fields?f=health&pack=cds", "hana": "/fields?f=health&pack=hana", "hbi": "/fields?f=health&pack=hbi", "hinf": "/fields?f=health&pack=hinf",
         "stat": "/fields?f=science&pack=stat", "gen": "/fields?f=science&pack=gen", "sci": "/fields?f=science&pack=sci", "cloud": "/fields?f=cloud&pack=cloud", "ux": "/fields?f=cloud&pack=ux", "mkt": "/fields?f=cloud&pack=mkt"}


def listing() -> list[dict]:
    return [{k: p[k] for k in ("id", "label", "group", "blurb", "agent", "examples", "keywords")} | {"href": PLACE.get(p["id"], "/fields")} | {"tools": [{"id": t["id"], "title": t["title"]} for t in p["tools"].values()]} for p in PACKS.values()]


def schema(pid: str) -> dict:
    p = PACKS.get(pid)
    if not p:
        raise PackError("No such field.", 404)
    return {k: p[k] for k in ("id", "label", "group", "blurb", "agent", "examples")} | {"tools": [{k: t[k] for k in ("id", "title", "note", "inputs")} for t in p["tools"].values()]}


def plain(x):
    """Turn numpy scalars (from scipy and friends) into ordinary Python values so the result can always be sent as JSON."""
    if isinstance(x, dict):
        return {str(k): plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [plain(v) for v in x]
    if hasattr(x, "item") and not isinstance(x, (str, bytes)):
        try:
            return plain(x.item())
        except (ValueError, TypeError):
            return str(x)
    if isinstance(x, float) and (x != x or x in (float("inf"), float("-inf"))):
        return None
    return x


def run(pid: str, tid: str, values: dict) -> dict:
    p = PACKS.get(pid)
    t = p and p["tools"].get(tid)
    if not t:
        raise PackError("No such tool.", 404)
    if not isinstance(values, dict):
        raise PackError("Send the form values as an object.")
    clean = {i["name"]: values.get(i["name"], i["default"]) for i in t["inputs"]}
    try:
        out = t["fn"](clean)
    except PackError as e:
        msg = e.message
        for i in t["inputs"]:
            nm = i["name"].replace("_", " ").capitalize()
            if msg.startswith(nm + " "):
                msg = i["label"].split(" (")[0].split(":")[0].strip().rstrip(".?") + msg[len(nm):]
                break
        raise PackError(msg, e.status) from None
    except (ValueError, ZeroDivisionError, OverflowError, KeyError, TypeError, IndexError, ArithmeticError):
        raise PackError("That input could not be worked out. Check that every number is filled in and sensible.") from None
    out = plain(out)
    out.setdefault("caution", "A starting point built from what you typed. Check it against your real situation before relying on it.")
    return out


def _load_all():
    from app.services import packs_business, packs_health, packs_science, packs_tech  # noqa: F401
    from app.services import pack_examples  # noqa: F401


_load_all()
