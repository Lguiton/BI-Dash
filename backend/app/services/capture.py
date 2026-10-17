"""Live packet capture on the computer that runs the backend, through scapy (which uses Npcap on Windows or libpcap on Linux).
Only capture a network you own or have written permission to test. The capture is saved in memory as a pcap and read by the
same summary code as a saved file: nothing is stored on disk and nothing is sent anywhere."""
from __future__ import annotations

import base64
import io
import os
import platform
import re
import time

from app.services import net_pcap

MAX_SECONDS = 60
MAX_PACKETS = 5000
HEADER_SNAP = 128
_BPF = re.compile(r"^[A-Za-z0-9 .:/_()!&|=<>\-\[\]]{0,200}$")

INSTALL = {
    "windows": ["Install Npcap from npcap.com (the free personal-use installer). Tick 'Install Npcap in WinPcap API-compatible Mode'.",
                "Run the backend from a terminal opened with 'Run as administrator' so it may read the network card.",
                "The backend must run in Windows Python, not inside WSL: WSL cannot see your real network card, only its own virtual one."],
    "linux": ["sudo apt install -y libpcap0.8", "Run the backend as root, or give Python the capture right once: sudo setcap cap_net_raw,cap_net_admin=eip $(readlink -f $(which python3))"],
    "check": "Reload this page after installing: the status below shows whether the network cards are visible.",
}


class CaptureError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _scapy():
    try:
        import scapy.all as sc
        return sc
    except Exception:  # noqa: BLE001 - scapy may be missing or fail to find the capture driver
        return None


def _is_admin() -> bool | None:
    try:
        if platform.system() == "Windows":
            import ctypes
            return bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        return os.geteuid() == 0
    except Exception:  # noqa: BLE001
        return None


def interfaces() -> list[dict]:
    sc = _scapy()
    if not sc:
        return []
    out = []
    try:
        for i in sc.get_if_list():
            out.append({"name": i, "label": _label(sc, i)})
    except Exception:  # noqa: BLE001
        return []
    return out


def _label(sc, name: str) -> str:
    try:
        for ic in sc.conf.ifaces.values():
            if ic.name == name or getattr(ic, "network_name", None) == name:
                ip = getattr(ic, "ip", "") or ""
                desc = getattr(ic, "description", "") or ic.name
                return f"{desc}" + (f" ({ip})" if ip and ip != "0.0.0.0" else "")
    except Exception:  # noqa: BLE001
        pass
    return name


def status() -> dict:
    sc = _scapy()
    system = platform.system()
    in_wsl = "microsoft" in platform.release().lower()
    if not sc:
        return {"available": False, "system": system, "in_wsl": in_wsl, "admin": _is_admin(), "interfaces": [], "install": INSTALL,
                "message": "The capture library (scapy) is not installed. Run: pip install -r backend/requirements.txt, then restart the backend."}
    ifs = interfaces()
    msgs = []
    if in_wsl:
        msgs.append("The backend is running inside WSL, so it can only see WSL's own virtual network, not your real network card. To capture your real network, run the backend in Windows Python with Npcap and administrator rights.")
    if _is_admin() is False:
        msgs.append("The backend is not running with administrator (root) rights, so capture will probably be refused.")
    if system == "Windows" and not getattr(sc.conf, "use_pcap", False):
        msgs.append("Npcap does not seem to be installed: install it, then restart the backend.")
    if not ifs:
        msgs.append("No network cards were found.")
    return {"available": bool(ifs), "system": system, "in_wsl": in_wsl, "admin": _is_admin(), "interfaces": ifs, "install": INSTALL,
            "message": " ".join(msgs) or "Ready. Only capture a network you own or have written permission to test."}


def _to_pcap(sc, pkts) -> bytes:
    buf = io.BytesIO()
    w = sc.PcapWriter(buf, sync=True)
    for p in pkts:
        w.write(p)
    data = buf.getvalue()
    return data


def run(iface: str, seconds: int, count: int, bpf: str, confirm: bool, headers_only: bool = True) -> dict:
    if not confirm:
        raise CaptureError("Tick the box to confirm this is a network you own or have written permission to capture.")
    sc = _scapy()
    if not sc:
        raise CaptureError("The capture library (scapy) is not installed. Run pip install -r backend/requirements.txt and restart the backend.", 503)
    if not 1 <= seconds <= MAX_SECONDS:
        raise CaptureError(f"Capture time must be 1 to {MAX_SECONDS} seconds.")
    if not 1 <= count <= MAX_PACKETS:
        raise CaptureError(f"Packet limit must be 1 to {MAX_PACKETS}.")
    bpf = (bpf or "").strip()
    if not _BPF.match(bpf):
        raise CaptureError("The filter has characters a capture filter does not use. Example: tcp port 443 or host 192.168.1.10.")
    names = [i["name"] for i in interfaces()]
    if iface not in names:
        raise CaptureError("Choose one of the listed network cards.")
    try:
        kw = {"iface": iface, "timeout": seconds, "count": count, "store": True}
        if bpf:
            kw["filter"] = bpf
        pkts = sc.sniff(**kw)
    except PermissionError:
        raise CaptureError("The network card refused access. Run the backend as administrator (Windows) or root (Linux).", 403) from None
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if "filter" in msg.lower() or "syntax" in msg.lower():
            raise CaptureError("That capture filter was not accepted. Example: tcp port 443 or host 192.168.1.10.") from None
        if "permission" in msg.lower() or "denied" in msg.lower() or "operation not permitted" in msg.lower():
            raise CaptureError("The network card refused access. Run the backend as administrator (Windows) or root (Linux).", 403) from None
        raise CaptureError("The capture could not start: " + msg[:160]) from None
    if len(pkts) == 0:
        raise CaptureError("No packets were seen. Check the network card, the filter, and that something was talking during the capture.")
    if headers_only:
        for p in pkts:
            raw = bytes(p)
            if len(raw) > HEADER_SNAP:
                p.wirelen = len(raw)
        pkts = [sc.Ether(bytes(p)[:HEADER_SNAP]) if len(bytes(p)) > HEADER_SNAP else p for p in pkts]
    data = _to_pcap(sc, pkts)
    summary = net_pcap.read(base64.b64encode(data).decode())
    return {"captured": len(pkts), "seconds": seconds, "interface": iface, "filter": bpf or "(none)", "headers_only": headers_only, "summary": summary,
            "pcap_base64": base64.b64encode(data).decode(),
            "notes": ["Headers only: the first 128 bytes of each packet were kept, so passwords and page contents were not saved." if headers_only else "Full packets were kept, so the capture may contain private data. Delete it when you are done.",
                      "Capture where the traffic passes: a laptop on Wi-Fi only sees its own traffic unless a switch mirrors ports."]}
