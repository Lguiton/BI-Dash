"""Per-client site notes: the devices you looked after, how their network is laid out, and the problems that keep coming back.

This is for repeat visits ("what router do they have?"). It never stores passwords: anything that looks like a secret is blanked when you save,
and the page tells you to keep real logins in a password manager. Stored per workspace, removed when the client is deleted."""
from __future__ import annotations

import json

from app.services import clients as cl
from app.services import state, workspaces
from app.services.clients import ClientError, _find, _txt
from app.services.fixlog import hide_secrets

KINDS = ("computer", "laptop", "router", "switch", "access point", "firewall", "printer", "server", "NAS", "phone", "camera", "other")


def _key() -> str:
    return f"clientnotes:{workspaces.active()}"


def _all() -> dict:
    raw = state.kv_get(_key())
    try:
        d = json.loads(raw) if raw else {}
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


def _blank() -> dict:
    return {"network": "", "issues": "", "notes": "", "devices": []}


def get(cid: int) -> dict:
    c = _find(cl._load(), "clients", cid)
    return {"client_id": cid, "client": c["name"], **{**_blank(), **_all().get(str(cid), {})}, "kinds": list(KINDS), "sample": cl.sample()}


def save(cid: int, b: dict) -> dict:
    _find(cl._load(), "clients", cid)
    masked = 0

    def t(v, name, lim):
        nonlocal masked
        s, n = hide_secrets(_txt(v, name, lim))
        masked += n
        return s

    devs = []
    for i, x in enumerate((b.get("devices") or [])[:60], 1):
        if not isinstance(x, dict):
            raise ClientError("Each device must be a set of fields.")
        name = t(x.get("name"), "device name", 80)
        if not name:
            continue
        kind = _txt(x.get("kind") or "other", "kind", 30)
        devs.append({"id": i, "name": name, "kind": kind if kind in KINDS else "other", "where": t(x.get("where"), "location", 100), "model": t(x.get("model"), "model", 100),
                     "address": t(x.get("address"), "address", 80), "notes": t(x.get("notes"), "notes", 300)})
    rec = {"network": t(b.get("network"), "network", 3000), "issues": t(b.get("issues"), "issues", 3000), "notes": t(b.get("notes"), "notes", 3000), "devices": devs}
    d = _all()
    d[str(cid)] = rec
    state.kv_set(_key(), json.dumps(d))
    return {**get(cid), "masked": masked}


def purge(cid: int) -> None:
    d = _all()
    if str(cid) in d:
        del d[str(cid)]
        state.kv_set(_key(), json.dumps(d))
