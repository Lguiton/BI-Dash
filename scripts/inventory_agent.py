#!/usr/bin/env python3
"""Inventory agent: prints one JSON report about THIS computer. Standard library only (Windows, macOS, Linux).

    python inventory_agent.py                 # print the report
    python inventory_agent.py --out pc01.json # save it, then paste/upload it in the app: IT > Inventory > Import

WHAT IT COLLECTS: computer name, kind guess, operating system and version, CPU name and core count, memory size,
disk sizes and free space, IP addresses, serial number if the system will tell an ordinary user, uptime, report time.
WHAT IT DOES NOT COLLECT: files, documents, browsing history, passwords, keystrokes, installed-app lists or user names.
It only reads, never changes anything, and sends nothing over the network. You decide where the file goes.
Run it on computers you own or administer, and tell their users it is happening."""
import argparse
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone

SCHEMA = 1


def _run(cmd, timeout=6):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return (out.stdout or "").strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def _ram_gb():
    try:
        if sys.platform.startswith("linux"):
            for ln in open("/proc/meminfo"):
                if ln.startswith("MemTotal"):
                    return round(int(ln.split()[1]) / 1024 / 1024, 1)
        if sys.platform == "darwin":
            return round(int(_run(["sysctl", "-n", "hw.memsize"]) or 0) / 1024 ** 3, 1) or None
        if os.name == "nt":
            import ctypes

            class MS(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong), ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
            m = MS()
            m.dwLength = ctypes.sizeof(MS)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return round(m.ullTotalPhys / 1024 ** 3, 1)
    except (OSError, ValueError, AttributeError):
        pass
    return None


def _cpu():
    name = platform.processor() or ""
    try:
        if sys.platform.startswith("linux"):
            for ln in open("/proc/cpuinfo"):
                if ln.lower().startswith("model name"):
                    name = ln.split(":", 1)[1].strip()
                    break
        elif sys.platform == "darwin":
            name = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or name
        elif os.name == "nt":
            name = os.environ.get("PROCESSOR_IDENTIFIER", name)
    except OSError:
        pass
    return name or "unknown"


def _serial():
    s = ""
    if sys.platform.startswith("linux"):
        for p in ("/sys/class/dmi/id/product_serial", "/sys/class/dmi/id/board_serial"):
            try:
                s = open(p).read().strip()
            except OSError:
                s = ""
            if s:
                break
    elif sys.platform == "darwin":
        for ln in _run(["system_profiler", "SPHardwareDataType"]).splitlines():
            if "Serial Number" in ln:
                s = ln.split(":", 1)[1].strip()
    elif os.name == "nt":
        out = _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_BIOS).SerialNumber"])
        s = out.splitlines()[0].strip() if out else ""
    return "" if s.lower() in ("", "none", "default string", "to be filled by o.e.m.", "system serial number", "0") else s[:60]


def _kind():
    try:
        if sys.platform.startswith("linux"):
            if any(os.path.exists(f"/sys/class/power_supply/BAT{i}") for i in range(3)):
                return "laptop"
            chassis = open("/sys/class/dmi/id/chassis_type").read().strip() if os.path.exists("/sys/class/dmi/id/chassis_type") else ""
            return "laptop" if chassis in ("8", "9", "10", "14") else "server" if chassis in ("17", "23") else "desktop"
        if sys.platform == "darwin":
            return "laptop" if "book" in _run(["sysctl", "-n", "hw.model"]).lower() else "desktop"
        if os.name == "nt":
            out = _run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_Battery | Measure-Object).Count"])
            return "laptop" if out.strip().isdigit() and int(out.strip()) > 0 else "desktop"
    except OSError:
        pass
    return "other"


def _disks():
    seen, out = set(), []
    roots = []
    if os.name == "nt":
        roots = [f"{c}:\\" for c in "CDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{c}:\\")]
    else:
        roots = ["/"] + [p for p in ("/home", "/data", "/mnt", "/Volumes") if os.path.ismount(p)]
    for r in roots:
        try:
            u = shutil.disk_usage(r)
        except OSError:
            continue
        if u.total in seen or u.total == 0:
            continue
        seen.add(u.total)
        out.append({"mount": r, "total_gb": round(u.total / 1024 ** 3, 1), "free_pct": round(u.free / u.total * 100, 1)})
    return out


def _uptime_days():
    try:
        if sys.platform.startswith("linux"):
            return round(float(open("/proc/uptime").read().split()[0]) / 86400, 2)
        if os.name == "nt":
            import ctypes
            return round(ctypes.windll.kernel32.GetTickCount64() / 86400000, 2)
        if sys.platform == "darwin":
            out = _run(["sysctl", "-n", "kern.boottime"])
            if "sec =" in out:
                return round((datetime.now().timestamp() - int(out.split("sec =")[1].split(",")[0])) / 86400, 2)
    except (OSError, ValueError, AttributeError):
        pass
    return None


def _ips():
    ips = set()
    try:
        for ai in socket.getaddrinfo(socket.gethostname(), None):
            ip = ai[4][0]
            if ":" not in ip and not ip.startswith("127."):
                ips.add(ip)
    except OSError:
        pass
    return sorted(ips)[:6]


def report() -> dict:
    return {"schema": SCHEMA, "hostname": socket.gethostname()[:80], "kind": _kind(), "os": f"{platform.system()} {platform.release()}"[:60], "os_version": platform.version()[:120],
            "cpu": _cpu()[:80], "cores": os.cpu_count(), "ram_gb": _ram_gb(), "disks": _disks(), "ip_addresses": _ips(), "serial": _serial(), "uptime_days": _uptime_days(),
            "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Print a JSON inventory report about this computer.")
    ap.add_argument("--out", help="write the report to this file instead of printing it")
    a = ap.parse_args(argv)
    text = json.dumps(report(), indent=2)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"Saved {a.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
