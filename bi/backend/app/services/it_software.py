"""IT software guide: the ten categories of IT management software, the March 2026 user ratings from the NinjaOne
SysAdmin Software Guide 2026 (G2 and Capterra), a weighted shortlist scorer and a stack coverage check.

Honest limits
* The guide is published by a vendor (NinjaOne), who is also ranked in it. The ratings come from G2 and Capterra, were
  collected in March 2026 and are a snapshot. User ratings are one input, not the answer.
* Nothing here installs, discovers or manages software. It helps you shortlist and plan; you evaluate the tools yourself.
* A '-' in the guide means no data or fewer than five reviews; here that is None and the scorer ignores it.
"""
from __future__ import annotations

import json

from app.services import state, workspaces

SOURCE = "NinjaOne SysAdmin Software Guide 2026; ratings from G2 and Capterra, collected March 2026"

METRICS = {  # key -> (label, scale max)
    "g2_overall": ("G2 overall", 5), "g2_meets": ("G2 meets requirements", 10), "g2_setup": ("G2 ease of setup", 10),
    "g2_use": ("G2 ease of use", 10), "g2_support": ("G2 quality of support", 10),
    "cap_overall": ("Capterra overall", 5), "cap_use": ("Capterra ease of use", 5), "cap_service": ("Capterra customer service", 5),
}
_KEYS = list(METRICS)

# name, change from 2025 (None = not shown), printed rank, then the eight metrics in METRICS order (None = '-')
N = None
CATS: dict[str, dict] = {
    "mgmt": {"label": "IT management (all-in-one)", "what": "From backup to endpoint management, platforms that cover several IT jobs in one place.",
             "free": "GLPI covers inventory and tickets; Tactical RMM is an open-source remote monitoring tool.",
             "rows": [
                 ("NinjaOne", 0, 1, 4.7, 9.0, 9.3, 9.2, 9.1, 4.7, 4.7, 4.7), ("Druva", 0, 2, 4.7, 9.4, 9.2, 9.4, 9.4, 4.7, 4.5, 4.7),
                 ("ClickUp", 0, 3, 4.7, 8.9, 8.2, 8.5, 8.9, 4.6, 4.3, 4.5), ("Veeam", 0, 4, 4.6, 9.4, 8.8, 9.1, 8.9, 4.8, 4.6, 4.5),
                 ("Freshservice", 0, 5, 4.6, 8.9, 8.8, 9.2, 9.0, 4.5, 4.5, 4.5), ("Cove Data Protection", 1, 6, 4.5, 8.9, 9.1, 9.0, 8.5, 4.7, 4.7, 4.5),
                 ("NewgenONE", -1, 7, 4.5, 8.5, 7.5, 8.5, 8.4, N, N, N), ("IBM Storage", 2, 8, 4.4, 8.9, 8.2, 8.7, 8.7, N, N, N),
                 ("Unitrends", 0, 9, 4.2, 8.7, 9.1, 9.1, 9.1, 4.7, 4.1, 4.6), ("ManageEngine ServiceDesk Plus", -2, 10, 4.2, 8.6, 8.1, 8.5, 8.1, 4.4, 4.3, 4.2)]},
    "rmm": {"label": "Endpoint monitoring and management", "what": "Central management of a varied set of systems and devices (RMM and UEM); MDM and Apple-only tools are ranked separately.",
            "free": "Tactical RMM and MeshCentral are open-source; Intune and Windows Group Policy are the Microsoft routes.",
            "rows": [
                ("NinjaOne", 0, 1, 4.7, 9.1, 9.2, 9.2, 9.2, 4.7, 4.7, 4.7), ("Atera", 1, 2, 4.7, 8.9, 9.1, 9.3, 9.2, 4.5, 4.6, 4.5),
                ("Pulseway (owned by Kaseya)", -1, 3, 4.6, 9.0, 9.0, 9.1, 9.2, 4.7, 4.7, 4.7), ("ManageEngine Endpoint Central MSP", 3, 4, 4.5, 8.8, 8.7, 8.7, 8.4, 4.7, 4.6, 4.4),
                ("Datto RMM (owned by Kaseya)", 0, 5, 4.5, 9.0, 8.8, 8.9, 8.4, 4.3, 4.2, 4.0), ("Microsoft Intune", 3, 6, 4.5, 8.9, 8.3, 8.6, 8.4, 4.5, 4.2, 3.7),
                ("HCL BigFix", -1, 7, 4.4, 9.2, 7.7, 8.3, 9.2, 4.0, 4.0, 4.3), ("LogMeIn Resolve (formerly GoToResolve)", -4, 8, 4.4, 8.9, 9.1, 9.0, 8.5, N, N, N),
                ("Ivanti Neurons for UEM", -1, 9, 4.2, 8.7, 8.1, 8.8, 8.5, N, N, N)]},
    "mdm": {"label": "Mobile device management", "what": "Securely support remote and hybrid workforces and keep phones and tablets under control.",
            "free": "Headwind MDM (Android) is open-source; Apple and Android both have built-in enrollment tools.",
            "rows": [
                ("AirDroid Business", 0, 1, 4.9, 9.8, 9.7, 9.7, 9.7, 4.8, 4.8, 4.6), ("NinjaOne", 0, 2, 4.7, 9.1, 9.3, 9.2, 9.3, 4.7, 4.7, 4.7),
                ("Scalefusion (formerly MobiLock Pro)", 0, 3, 4.7, 9.0, 8.6, 8.9, 9.5, 4.8, N, 4.9), ("Miradore", 0, 4, 4.6, 9.0, 8.9, 9.1, 9.3, 4.5, N, 4.4),
                ("Hexnode UEM", 0, 5, 4.5, 9.1, 8.9, 9.0, 9.2, 4.6, N, 4.7), ("Esper", 0, 6, 4.5, 8.9, 8.8, 9.0, 8.9, 4.5, N, 4.3),
                ("ManageEngine Endpoint Central MSP", 0, 7, 4.1, 8.3, 8.1, 8.7, 8.0, 4.7, 4.6, 4.4)]},
    "patch": {"label": "Software and patch management", "what": "Keep operating systems and third-party apps patched against the latest vulnerabilities, and deploy or remove applications.",
              "free": "winget for apps, built-in OS update tools, and unattended-upgrades on Linux.",
              "rows": [
                  ("Action1", 2, 1, 4.9, 9.3, 9.7, 9.5, 9.3, 4.9, 4.7, 4.8), ("Patch My PC", 0, 2, 4.8, 9.3, 9.4, 9.3, 9.7, 4.9, 4.8, 4.9),
                  ("PDQ Deploy & Inventory", -2, 3, 4.8, 9.4, 9.6, 9.5, 9.5, 4.8, 4.7, 4.8), ("NinjaOne", 0, 4, 4.7, 9.1, 9.2, 9.2, 9.2, 4.7, 4.7, 4.7),
                  ("Pulseway (owned by Kaseya)", 0, 5, 4.6, 9.1, 9.3, 9.2, 9.4, 4.7, 4.7, 4.7), ("Atera", 0, 6, 4.6, 8.9, 9.2, 9.3, 9.3, 4.5, 4.6, 4.5),
                  ("ManageEngine Patch Manager Plus", 4, 7, 4.5, 9.2, 8.9, 8.5, 8.5, 4.6, 4.4, 4.5), ("Syxsense", -1, 8, 4.5, 9.0, 8.4, 8.7, 8.8, 4.6, 4.5, 4.7),
                  ("Tenable Nessus", 0, 9, 4.5, 9.0, 8.8, 8.9, 8.4, 4.7, 4.5, 4.3), ("Datto RMM (owned by Kaseya)", 0, 10, 4.5, 8.9, 8.7, 8.8, 8.3, 4.3, 4.2, 4.0),
                  ("Automox", -3, 8, 4.5, 8.8, 9.0, 8.9, 8.7, 4.7, 4.5, 4.7), ("Ivanti UEM", 0, 12, 4.2, 8.7, 8.3, 8.7, 8.5, N, N, N)]},
    "asset": {"label": "IT asset management", "what": "You can't secure or manage what you can't see: discover, track and report on all IT assets.",
              "free": "Snipe-IT and GLPI are free asset systems; this app's Inventory tab is the personal-scale version.",
              "rows": [
                  ("PDQ Deploy & Inventory", 0, 1, 4.8, 9.4, 9.5, 9.3, 9.5, 4.8, 4.7, 4.8), ("Proactivanet", 2, 2, 4.8, 9.4, 9.0, 9.4, 9.5, N, N, N),
                  ("Setyl", -1, 3, 4.8, 9.3, 9.3, 9.0, 9.6, 4.9, 4.9, 4.9), ("NinjaOne", -1, 4, 4.7, 9.1, 9.2, 9.2, 9.2, 4.7, 4.7, 4.7),
                  ("Genuity", 0, 5, 4.7, 9.0, 9.3, 9.4, 9.8, N, N, N), ("Device42", 0, 6, 4.7, 9.0, 8.5, 8.9, 9.5, 4.8, 4.8, 4.9),
                  ("Oomnitza", 1, 7, 4.6, 8.9, 8.1, 8.8, 9.5, 4.4, 3.7, 4.5), ("ServiceNow IT Asset Management", 0, 9, 4.6, 8.9, 7.9, 8.3, 8.8, N, N, N),
                  ("ScalePad", -2, 7, 4.5, 8.8, 9.0, 9.1, 8.8, 4.6, 4.6, 4.3)]},
    "desk": {"label": "Service desk", "what": "Ticketing that saves technicians time and gives end users a better experience.",
             "free": "osTicket and GLPI are free; this app's Helpdesk tab practises the same ideas.",
             "rows": [
                 ("Splashtop SOS", 1, 1, 4.8, 9.5, 9.5, 9.4, 9.5, 4.7, 4.7, 4.7), ("Rezolve.ai", -1, 2, 4.8, 9.1, 9.2, 9.5, 9.7, 4.8, 4.5, 4.5),
                 ("Halp", 0, 3, 4.7, 9.2, 9.3, 9.5, 9.6, N, N, N), ("Xurrent", 0, 4, 4.6, 8.9, 8.7, 9.1, 9.1, 4.7, 4.6, 4.8),
                 ("Halo Service Desk", 0, 5, 4.6, 8.7, 8.0, 9.3, 9.5, N, N, N), ("Freshservice", 0, 6, 4.6, 8.9, 8.8, 9.2, 9.0, 4.5, 4.5, 4.5),
                 ("SysAid", 0, 7, 4.5, 8.9, 8.5, 9.0, 9.0, 4.5, 4.5, 4.5), ("ServiceNow", 2, 8, 4.4, 8.9, 8.2, 8.5, 8.5, 4.2, 4.2, 4.3),
                 ("Zoho Desk", 0, 9, 4.4, 8.7, 8.1, 8.5, 8.3, 4.4, 4.5, 4.3), ("Salesforce Service Cloud", -2, 10, 4.4, 8.6, 7.9, 8.4, 8.3, 4.5, 4.1, 4.3),
                 ("SolarWinds Service Desk", 0, 11, 4.3, 8.6, 8.6, 9.0, 8.9, 4.6, 4.5, 4.6), ("Zendesk", 0, 12, 4.3, 8.6, 8.0, 8.6, 8.4, 4.4, 4.1, 4.2),
                 ("ManageEngine Service Desk Plus", 0, 13, 4.2, 8.5, 8.0, 8.5, 8.1, 4.4, 4.3, 4.3)]},
    "remote": {"label": "Remote desktop", "what": "Quick and reliable remote access to machines for hands-on troubleshooting.",
               "free": "RDP and SSH are built in; MeshCentral and RustDesk are open-source.",
               "rows": [
                   ("Getscreen.me", 1, 1, 4.8, 9.4, 9.4, 9.5, 9.2, 4.8, 4.8, 4.8), ("Splashtop", -1, 2, 4.8, 9.6, 9.4, 9.6, 9.3, 4.7, 4.7, 4.7),
                   ("BeyondTrust Remote Support (formerly Bomgar)", 1, 3, 4.7, 9.5, 8.8, 9.4, 9.3, 4.6, 4.5, 4.5), ("RemotePC by iDrive", -1, 4, 4.7, 9.4, 9.4, 9.5, 9.2, 4.7, 4.6, 4.6),
                   ("Devolutions Remote Desktop Manager", 1, 5, 4.7, 9.4, 9.0, 9.0, 9.0, 4.6, 4.4, 4.4), ("RealVNC", -1, 6, 4.7, 9.3, 9.0, 9.3, 9.0, 4.5, 4.6, 4.2),
                   ("ConnectWise ScreenConnect", 1, 7, 4.7, 9.3, 8.9, 9.3, 8.8, 4.7, 4.6, 4.6), ("Zoho Assist", 1, 8, 4.6, 9.2, 9.4, 9.3, 8.9, 4.7, 4.7, 4.6),
                   ("ISL Online", 1, 9, 4.6, 8.9, 9.1, 9.3, 9.1, N, N, N), ("TeamViewer", 2, 10, 4.5, 9.1, 9.1, 9.1, 8.6, 4.6, 4.6, 4.3),
                   ("AnyDesk", -4, 11, 4.5, 9.2, 9.3, 9.3, 8.8, 4.6, 4.7, 4.3), ("SolarWinds DameWare", 2, 12, 4.3, 9.2, 8.9, 8.9, 8.3, 4.5, 4.4, 4.2),
                   ("LogMeIn Pro", -2, 13, 4.4, 9.2, 9.4, 9.2, 8.4, 4.3, 4.2, 4.0), ("Go To Resolve", -1, 14, 4.4, 9.1, 8.7, 9.1, 8.7, 4.4, 4.5, 4.2)]},
    "backup": {"label": "Cloud backup", "what": "Backup that survives ransomware and other destructive threats; this list covers cloud-based solutions.",
               "free": "restic, rsync and Duplicati are free; learn the 3-2-1 rule and test a restore first.",
               "rows": [
                   ("Druva", 1, 1, 4.7, 9.5, 9.3, 9.5, 9.4, 4.7, 4.5, 4.7), ("Rewind Backups", -1, 2, 4.7, 9.2, 9.5, 9.4, 9.5, 4.2, 4.3, 3.9),
                   ("NinjaOne", 0, 3, 4.7, 9.0, 9.1, 9.1, 9.1, 4.7, 4.7, 4.7), ("Redstor Backup and Archiving", 3, 4, 4.6, 9.1, 9.0, 9.2, 9.1, N, N, N),
                   ("Veeam", 0, 5, 4.5, 9.0, 8.6, 9.0, 8.9, 4.7, 4.5, 4.5), ("Datto SIRIS", 0, 6, 4.5, 8.8, 9.0, 8.7, 8.8, 4.5, 4.5, 4.4),
                   ("Cove Data Protection (previously N-Able Backup)", 2, 7, 4.5, 8.9, 9.0, 9.0, 8.4, 4.7, 4.5, 4.5), ("Backblaze", -4, 8, 4.4, 9.1, 8.7, 8.5, 8.2, 4.3, 4.8, 4.8),
                   ("Barracuda Backup", -1, 9, 4.4, 8.8, 8.5, 8.9, 9.1, 4.7, 4.3, 4.4), ("IDrive Online Backup", 0, 10, 4.4, 8.9, 9.0, 8.7, 8.7, 4.6, 4.5, 4.5),
                   ("Acronis Cyber Backup", 0, 11, 4.3, 8.8, 8.5, 8.7, 8.4, 4.1, 4.2, 3.6), ("Unitrends (a Kaseya company)", 0, 12, 4.2, 8.8, 8.3, 8.7, 8.7, 4.7, 4.1, 4.6)]},
    "netmon": {"label": "Network monitoring", "what": "Visibility and management over SNMP devices (routers, switches, firewalls, printers, IoT) and more.",
               "free": "Zabbix, Nagios Core, LibreNMS and Prometheus with Grafana are free; this app exposes /metrics for Prometheus.",
               "rows": [
                   ("Domotz", 0, 1, 4.8, 9.2, 9.1, 9.4, 9.5, 4.9, 4.8, 4.9), ("Entuity", 1, 2, 4.7, 9.3, 9.4, 9.5, 9.3, N, N, N),
                   ("PRTG", 2, 3, 4.7, 9.2, 8.6, 8.8, 8.5, 4.6, 4.4, 4.2), ("NinjaOne", -2, 4, 4.7, 9.1, 9.2, 9.3, 9.2, 4.7, 4.7, 4.7),
                   ("Atera", 1, 5, 4.6, 9.1, 9.3, 9.3, 9.3, 4.6, 4.6, 4.5), ("ManageEngine OpManager", 4, 6, 4.6, 9.1, 9.0, 8.8, 8.7, 4.5, 4.5, 4.5),
                   ("Nagios XI", 2, 7, 4.5, 9.5, 7.5, 9.0, 8.9, 4.5, 4.2, 4.0), ("LogicMonitor", -1, 8, 4.5, 8.9, 8.5, 8.5, 8.9, 4.6, 4.3, 4.6),
                   ("Auvik", -5, 9, 4.5, 8.6, 8.7, 8.7, 8.8, 4.7, 4.5, 4.6), ("Datadog", 2, 10, 4.4, 8.8, 8.4, 8.0, 8.4, 4.6, 4.3, 4.3),
                   ("Zabbix", 1, 11, 4.4, 8.8, 7.4, 7.3, 7.8, 4.7, 4.0, 4.2), ("Progress WhatsUp Gold", -1, 12, 4.4, 8.8, 8.2, 8.5, 8.8, 4.5, 4.2, 4.4)]},
    "edr": {"label": "Endpoint detection and response", "what": "Endpoint security that identifies, stops and reacts to threats that got past other defenses. True endpoint protection products only.",
            "free": "Microsoft Defender is built into Windows; Wazuh is an open-source detection platform.",
            "rows": [
                ("Huntress", 0, 1, 4.8, 9.5, 9.6, 9.6, 9.7, 4.9, 4.8, 5.0), ("SentinelOne", 1, 2, 4.7, 9.3, 8.9, 8.9, 8.9, 4.8, 4.5, 4.5),
                ("Webroot Endpoint Protection", 2, 3, 4.6, 9.3, 9.4, 9.2, 8.8, 4.5, 4.6, 4.4), ("CrowdStrike Falcon", -2, 4, 4.6, 9.3, 9.2, 9.1, 8.9, 4.7, 4.3, 4.2),
                ("ESET", 2, 5, 4.6, 9.2, 8.7, 8.9, 8.9, 4.8, 4.8, 4.5), ("Threatdown (aka Malwarebytes)", -2, 6, 4.6, 9.2, 9.2, 9.3, 8.8, 4.5, 4.6, 4.4),
                ("Cisco Secure Endpoints", 1, 7, 4.5, 9.1, 8.3, 8.8, 9.4, 4.7, 5.0, 4.6), ("WatchGuard Endpoint Security", 2, 8, 4.4, 9.1, 8.3, 8.9, 8.7, 4.4, 4.5, 4.1),
                ("Microsoft Defender for Endpoint", 2, 9, 4.4, 8.6, 8.5, 8.6, 8.5, 4.7, 4.5, 4.1), ("Heimdal Security", 2, 10, 4.3, 9.0, 8.3, 9.0, 9.5, 4.8, 4.8, 4.9),
                ("Bitdefender GravityZone", 1, 11, 4.0, 8.4, 8.3, 8.0, 8.2, 4.6, 4.5, 4.3), ("Sophos Intercept X", -6, 12, 3.9, 9.1, 8.1, 8.5, 7.8, 4.5, 4.3, 4.1)]},
}


class SoftError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _product(r: tuple) -> dict:
    return {"name": r[0], "change": r[1], "rank": r[2], **dict(zip(_KEYS, r[3:]))}


def catalog() -> dict:
    cats = [{"id": cid, "label": c["label"], "what": c["what"], "free": c["free"], "count": len(c["rows"]),
             "products": [_product(r) for r in c["rows"]]} for cid, c in CATS.items()]
    return {"source": SOURCE, "metrics": [{"key": k, "label": v[0], "max": v[1]} for k, v in METRICS.items()], "categories": cats,
            "notes": ["The guide is published by NinjaOne, which is also ranked in it, so read it as a starting point for your own research.",
                      "User ratings are one input. Price, the devices you run, integrations and the support you need matter as much.",
                      "A blank value means no data or fewer than five reviews, and the scorer ignores it.",
                      "Nothing here installs or manages software; this tab helps you shortlist and plan."]}


def shortlist(category: str, weights: dict | None = None, exclude: list[str] | None = None) -> dict:
    """Rank a category by the weighted average of its ratings, each put on a 0-10 scale. Missing values are skipped."""
    if category not in CATS:
        raise SoftError(f"Unknown category. Choose one of: {', '.join(CATS)}.")
    w = {k: 0.0 for k in _KEYS}
    for k, v in (weights or {}).items():
        if k not in METRICS:
            raise SoftError(f"Unknown rating: {k}.")
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise SoftError(f"Weight for {k} must be a number.") from None
        if f < 0 or f > 10:
            raise SoftError("Weights go from 0 to 10.")
        w[k] = f
    if not weights:
        w = {k: 1.0 for k in _KEYS}
    if sum(w.values()) <= 0:
        raise SoftError("Give at least one rating a weight above zero.")
    skip = {x.strip().lower() for x in (exclude or []) if x}
    rows = []
    for r in CATS[category]["rows"]:
        p = _product(r)
        if p["name"].lower() in skip:
            continue
        used = tot = 0.0
        missing = []
        for k in _KEYS:
            if w[k] == 0:
                continue
            if p[k] is None:
                missing.append(METRICS[k][0])
                continue
            tot += w[k] * p[k] * (10 / METRICS[k][1])
            used += w[k]
        if used == 0:
            continue
        rows.append({"name": p["name"], "score": round(tot / used, 2), "weight_covered_pct": round(100 * used / sum(w.values())), "missing": missing, "guide_rank": p["rank"]})
    rows.sort(key=lambda x: (-x["score"], x["guide_rank"]))
    for i, x in enumerate(rows, 1):
        x["position"] = i
    close = bool(len(rows) > 1 and rows[0]["score"] - rows[1]["score"] < 0.2)
    return {"category": category, "label": CATS[category]["label"], "weights": w, "rows": rows,
            "lesson": "Each rating is put on a 0 to 10 scale, multiplied by your weight, and averaged; ratings a product lacks are left out and its row says how much of your weight it covers.",
            "caution": ("The top two are within 0.2 points, which is noise: decide on price, fit and a trial, not the order." if close else
                        "Differences of a few tenths are noise. Use this to pick two or three to trial, not to pick a winner.")}


# ---- stack coverage -------------------------------------------------------------------
STATUSES = ("have", "planned", "none", "not_needed")


def _ws() -> str:
    return workspaces.active()


def _key() -> str:
    return f"it_stack:{_ws()}"


def stack() -> dict:
    raw = state.kv_get(_key())
    saved = json.loads(raw) if raw else {}
    rows = []
    for cid, c in CATS.items():
        s = saved.get(cid) or {}
        rows.append({"id": cid, "label": c["label"], "tool": s.get("tool", ""), "status": s.get("status", "none"), "note": s.get("note", "")})
    gaps = [r["label"] for r in rows if r["status"] == "none"]
    have = sum(r["status"] == "have" for r in rows)
    counted = sum(r["status"] != "not_needed" for r in rows)
    return {"rows": rows, "statuses": list(STATUSES), "have": have, "counted": counted, "gaps": gaps,
            "lesson": "You can't secure or manage what you can't see. A gap is not always a problem: mark a category not needed when it truly is, and write down why."}


def save_stack(items: list[dict]) -> dict:
    saved = {}
    for it in items or []:
        cid = str(it.get("id", ""))
        if cid not in CATS:
            raise SoftError(f"Unknown category: {cid}.")
        st = str(it.get("status", "none"))
        if st not in STATUSES:
            raise SoftError(f"Status must be one of: {', '.join(STATUSES)}.")
        saved[cid] = {"tool": str(it.get("tool", ""))[:80].strip(), "status": st, "note": str(it.get("note", ""))[:200].strip()}
    state.kv_set(_key(), json.dumps(saved))
    state.audit("it_stack_save", f"{sum(v['status'] == 'have' for v in saved.values())} categories covered")
    return stack()
