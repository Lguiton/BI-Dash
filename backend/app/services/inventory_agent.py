"""Import reports made by scripts/inventory_agent.py into the IT inventory (adds new computers, updates known ones)."""
from __future__ import annotations

import json
from pathlib import Path

from app.services import itlab, state

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "inventory_agent.py"
MAX_REPORTS = 200
KINDS = set(itlab.KINDS)


def script_text() -> str:
    try:
        return SCRIPT.read_text(encoding="utf-8")
    except OSError:
        raise itlab.ItError("The agent script is not in this install (scripts/inventory_agent.py).", 404) from None


def _load(text: str) -> list[dict]:
    t = (text or "").strip()
    if not t:
        raise itlab.ItError("Paste the JSON from the agent first.")
    if len(t) > 2_000_000:
        raise itlab.ItError("That is too large; import fewer reports at a time.")
    try:
        v = json.loads(t)
        items = v if isinstance(v, list) else [v]
    except json.JSONDecodeError:
        items = []
        for i, ln in enumerate(t.splitlines(), 1):
            if ln.strip():
                try:
                    items.append(json.loads(ln))
                except json.JSONDecodeError:
                    raise itlab.ItError(f"Line {i} is not valid JSON. Paste one report, a list, or one report per line.") from None
    if not items or len(items) > MAX_REPORTS or not all(isinstance(x, dict) for x in items):
        raise itlab.ItError(f"Give 1 to {MAX_REPORTS} reports (each a JSON object).")
    return items


def _notes(r: dict) -> str:
    bits = []
    if r.get("cpu"):
        bits.append(f"CPU {str(r['cpu'])[:40]}")
    if r.get("cores"):
        bits.append(f"{r['cores']} cores")
    if r.get("ram_gb"):
        bits.append(f"{r['ram_gb']} GB RAM")
    d = r.get("disks")
    if isinstance(d, list) and d:
        bits.append("disks " + ", ".join(f"{x.get('mount')} {x.get('total_gb')} GB ({x.get('free_pct')}% free)" for x in d[:3] if isinstance(x, dict)))
    if r.get("ip_addresses"):
        bits.append("IP " + ", ".join(map(str, r["ip_addresses"][:2])))
    note = "Agent: " + "; ".join(bits)
    if r.get("collected_at"):
        note += f" (seen {str(r['collected_at'])[:10]})"
    return note[:300]


def import_reports(text: str) -> dict:
    items = _load(text)
    existing = state.rows("SELECT id, hostname, serial FROM it_assets WHERE workspace = ?", (itlab._ws(),))
    created, updated, skipped = [], [], []
    for r in items:
        host = str(r.get("hostname") or "").strip()[:80]
        if not host:
            skipped.append("a report with no hostname")
            continue
        if r.get("schema") not in (None, 1):
            skipped.append(f"{host}: unknown report version")
            continue
        serial = str(r.get("serial") or "").strip()[:60]
        kind = r.get("kind") if r.get("kind") in KINDS else "other"
        osn = str(r.get("os") or "")[:60]
        match = next((a for a in existing if serial and a["serial"] and a["serial"].lower() == serial.lower()), None) or next((a for a in existing if a["hostname"].lower() == host.lower()), None)
        try:
            if match:
                ch = {"os": osn, "notes": _notes(r)}
                if serial and not match["serial"]:
                    ch["serial"] = serial
                itlab.update_asset(match["id"], ch)
                updated.append(host)
            else:
                a = itlab.add_asset(host, kind, osn, "", serial, "", "", "in_use", _notes(r))
                existing.append({"id": a["id"], "hostname": host, "serial": serial})
                created.append(host)
        except itlab.ItError as e:
            skipped.append(f"{host}: {e}")
    return {"created": created, "updated": updated, "skipped": skipped,
            "note": "A computer is matched by serial number first, then by name. Owner, purchase date and warranty are never touched; you fill those in. Notes are replaced with the latest specs."}
