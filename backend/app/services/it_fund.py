"""IT fundamentals lab: number systems, logic gates, storage units, Linux permissions, IPv6,
a Windows/Linux command finder and a reference. Pure functions, nothing is executed."""
from __future__ import annotations

import ipaddress
import re


class FundError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# ------------------------------------------------------------ numbers
_BASES = {"decimal": 10, "binary": 2, "hex": 16, "octal": 8}


def convert(value: str, base: str = "decimal") -> dict:
    if base not in _BASES:
        raise FundError("Base must be decimal, binary, hex or octal.")
    s = (value or "").strip().replace(" ", "").replace("_", "")
    s = re.sub(r"^(0b|0x|0o)", "", s, flags=re.I) if base != "decimal" else s
    if not s or len(s) > 64:
        raise FundError("Enter a number (up to 64 digits).")
    try:
        n = int(s, _BASES[base])
    except ValueError:
        raise FundError(f"'{value}' is not a valid {base} number.") from None
    if n < 0 or n >= 2**64:
        raise FundError("Use a whole number from 0 to 18,446,744,073,709,551,615.")
    bits = max(8, ((n.bit_length() + 7) // 8) * 8)
    b = format(n, f"0{bits}b")
    groups = " ".join(b[i:i + 4] for i in range(0, len(b), 4))
    # working: which powers of two are switched on (for values that fit a byte, show the 128..1 table)
    on = [2**i for i in range(n.bit_length() - 1, -1, -1) if n >> i & 1]
    table = None
    if n < 256:
        table = [{"place": 2**i, "bit": (n >> i) & 1} for i in range(7, -1, -1)]
    return {"decimal": n, "binary": groups, "hex": format(n, "X"), "octal": format(n, "o"), "bits": bits,
            "bytes": bits // 8, "on_places": on, "sum": " + ".join(map(str, on)) or "0", "table": table,
            "ascii": chr(n) if 32 <= n < 127 else None,
            "lesson": "Each binary place is worth double the one to its right (128, 64, 32, 16, 8, 4, 2, 1). Add the places that are switched on. One hex digit is exactly four bits, which is why hex is used to write binary compactly.",
            "check": f"{' + '.join(map(str, on)) or '0'} = {n}"}


def encode_text(text: str) -> dict:
    if not text or len(text) > 100:
        raise FundError("Enter 1 to 100 characters.")
    rows = []
    for ch in text:
        bs = ch.encode("utf-8")
        rows.append({"char": ch if ch.isprintable() else repr(ch), "code_point": f"U+{ord(ch):04X}", "decimal": ord(ch),
                     "utf8_hex": " ".join(f"{x:02X}" for x in bs), "utf8_binary": " ".join(f"{x:08b}" for x in bs), "bytes": len(bs)})
    total = sum(r["bytes"] for r in rows)
    return {"rows": rows, "total_bytes": total, "characters": len(text),
            "lesson": "A character set maps characters to numbers; an encoding turns those numbers into bytes. UTF-8 uses one byte for ASCII (0 to 127) and two to four bytes for everything else, so plain English text is identical in ASCII and UTF-8.",
            "note": "Accented letters, symbols and emoji take more than one byte each, so a text file's byte count can exceed its character count."}


# ------------------------------------------------------------ logic gates
GATES = {
    "NOT": (1, lambda a, b=0: int(not a), "Flips the input."),
    "AND": (2, lambda a, b: int(a and b), "1 only when both inputs are 1."),
    "OR": (2, lambda a, b: int(a or b), "1 when at least one input is 1."),
    "XOR": (2, lambda a, b: int(a != b), "1 when the inputs differ."),
    "NAND": (2, lambda a, b: int(not (a and b)), "NOT AND: 0 only when both inputs are 1."),
    "NOR": (2, lambda a, b: int(not (a or b)), "NOT OR: 1 only when both inputs are 0."),
    "XNOR": (2, lambda a, b: int(a == b), "1 when the inputs are the same."),
}


def gate_table(name: str) -> dict:
    g = GATES.get((name or "").upper())
    if not g:
        raise FundError("Gate must be one of " + ", ".join(GATES) + ".")
    n, fn, what = g
    rows = [{"a": a, "out": fn(a)} for a in (0, 1)] if n == 1 else [{"a": a, "b": b, "out": fn(a, b)} for a in (0, 1) for b in (0, 1)]
    return {"gate": name.upper(), "inputs": n, "rows": rows, "rule": what}


_TOK = re.compile(r"\s*(\(|\)|[A-Za-z_][A-Za-z0-9_]*)")


def _tokens(expr: str) -> list[str]:
    out, pos = [], 0
    expr = expr.strip()
    while pos < len(expr):
        m = _TOK.match(expr, pos)
        if not m:
            raise FundError(f"Can't read the expression near '{expr[pos:pos + 8]}'. Use letters, AND, OR, NOT, XOR, NAND, NOR, XNOR and brackets.")
        out.append(m.group(1))
        pos = m.end()
    return out


def circuit(expr: str) -> dict:
    """Truth table for a boolean expression such as '(A AND B) OR NOT C'. Uses its own parser, never eval."""
    if not expr or len(expr) > 200:
        raise FundError("Enter an expression up to 200 characters.")
    toks = _tokens(expr)
    ops = set(GATES)
    names = sorted({t for t in toks if t not in ("(", ")") and t.upper() not in ops})
    if not names:
        raise FundError("Use at least one input name such as A or B.")
    if len(names) > 4:
        raise FundError("Use at most 4 inputs (16 rows).")
    if any(t.upper() in ops for t in names):
        raise FundError("Input names can't be gate names.")
    # precedence: NOT > AND/NAND > XOR/XNOR > OR/NOR
    def parse(env):
        pos = 0

        def peek():
            return toks[pos] if pos < len(toks) else None

        def eat():
            nonlocal pos
            pos += 1
            return toks[pos - 1]

        def atom():
            t = peek()
            if t is None:
                raise FundError("The expression ends too early.")
            if t == "(":
                eat()
                v = level(0)
                if peek() != ")":
                    raise FundError("A bracket is not closed.")
                eat()
                return v
            if t == ")":
                raise FundError("Unexpected closing bracket.")
            if t.upper() == "NOT":
                eat()
                return int(not atom())
            if t.upper() in ops:
                raise FundError(f"{t.upper()} needs an input on its left.")
            eat()
            return env[t]
        tiers = [("OR", "NOR"), ("XOR", "XNOR"), ("AND", "NAND")]

        def level(i):
            if i == len(tiers):
                return atom()
            v = level(i + 1)
            while peek() and peek().upper() in tiers[i]:
                op = eat().upper()
                v = GATES[op][1](v, level(i + 1))
            return v
        r = level(0)
        if pos != len(toks):
            raise FundError(f"Unexpected '{toks[pos]}'. Join inputs with AND, OR, XOR and so on.")
        return r
    rows = []
    for i in range(2 ** len(names)):
        env = {n: (i >> (len(names) - 1 - k)) & 1 for k, n in enumerate(names)}
        rows.append({**env, "out": parse(env)})
    ones = sum(r["out"] for r in rows)
    return {"inputs": names, "rows": rows, "ones": ones, "of": len(rows),
            "reading": "Always 1." if ones == len(rows) else ("Always 0." if ones == 0 else f"1 in {ones} of {len(rows)} cases."),
            "note": "Without brackets, NOT binds first, then AND/NAND, then XOR/XNOR, then OR/NOR. Add brackets when in doubt."}


# ------------------------------------------------------------ storage
_UNITS = ["B", "KB", "MB", "GB", "TB", "PB"]


def storage(value: float, unit: str = "GB") -> dict:
    u = (unit or "").upper()
    if u not in _UNITS:
        raise FundError("Unit must be one of " + ", ".join(_UNITS) + ".")
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= value <= 1e6:
        raise FundError("Enter a size between 0 and 1,000,000.")
    i = _UNITS.index(u)
    dec_bytes, bin_bytes = value * 1000 ** i, value * 1024 ** i
    rows = []
    for k, x in enumerate(_UNITS):
        rows.append({"unit": x, "decimal": round(dec_bytes / 1000 ** k, 4), "binary_name": x.replace("B", "iB") if x != "B" else "B", "binary": round(dec_bytes / 1024 ** k, 4)})
    drive = None
    if i >= 3:
        same = dec_bytes / 1024 ** i
        drive = {"marketed": f"{value:g} {u}", "shown": round(same, 3), "shown_unit": u.replace("B", "iB"),
                 "as_gib": round(dec_bytes / 1024 ** 3, 2), "difference_pct": round(100 * (1 - same / value), 2) if value else 0}
    return {"rows": rows, "drive": drive, "bytes_decimal": int(dec_bytes), "bytes_binary": int(bin_bytes),
            "lesson": "Makers count in powers of 1000 (1 TB = 10^12 bytes). Many operating systems count in powers of 1024 and still print 'GB' for what is really GiB, so a 1 TB drive shows about 931 GB. Nothing is missing: the two sides use different units.",
            "formula": "Loss is about 2.3% at KB, 4.6% at MB, 6.9% at GB, 9.1% at TB and 11.2% at PB, growing with each step."}


# ------------------------------------------------------------ Linux permissions
_WHO = ("owner", "group", "others")


def _sym_from_octal(digits: str) -> str:
    out = []
    special = int(digits[0]) if len(digits) == 4 else 0
    d3 = digits[-3:]
    for k, ch in enumerate(d3):
        d = int(ch)
        r, w, x = "r" if d & 4 else "-", "w" if d & 2 else "-", "x" if d & 1 else "-"
        if k == 0 and special & 4:
            x = "s" if x == "x" else "S"
        if k == 1 and special & 2:
            x = "s" if x == "x" else "S"
        if k == 2 and special & 1:
            x = "t" if x == "x" else "T"
        out.append(r + w + x)
    return "".join(out)


def _octal_from_sym(sym: str) -> str:
    s = sym.strip()
    if len(s) == 10 and s[0] in "-dl":
        s = s[1:]
    if not re.fullmatch(r"[r-][w-][xsS-][r-][w-][xsS-][r-][w-][xtT-]", s):
        raise FundError("Use nine characters like rwxr-xr-x (a leading - or d is allowed).")
    digits, sp = [], 0
    for k in range(3):
        a, b, c = s[3 * k:3 * k + 3]
        v = (4 if a == "r" else 0) + (2 if b == "w" else 0)
        if c in "xst":
            v += 1
        digits.append(v)
        if k == 0 and c in "sS":
            sp |= 4
        if k == 1 and c in "sS":
            sp |= 2
        if k == 2 and c in "tT":
            sp |= 1
    return (str(sp) if sp else "") + "".join(map(str, digits))


def chmod(mode: str, kind: str = "file", umask: str = "") -> dict:
    m = (mode or "").strip()
    if re.fullmatch(r"[0-7]{3,4}", m):
        octal = m
        sym = _sym_from_octal(m)
    else:
        octal = _octal_from_sym(m)
        sym = _sym_from_octal(octal)
    if kind not in ("file", "dir"):
        raise FundError("Kind must be file or dir.")
    d3 = octal[-3:]
    special = int(octal[0]) if len(octal) == 4 else 0
    meaning = []
    for k, ch in enumerate(d3):
        d = int(ch)
        can = [n for bit, n in ((4, "read"), (2, "write"), (1, "execute" if kind == "file" else "enter")) if d & bit]
        meaning.append(f"{_WHO[k].capitalize()}: {', '.join(can) if can else 'nothing'}.")
    if kind == "dir":
        meaning.append("On a directory: read lists names, write adds or removes entries, execute lets you enter it and reach files inside.")
    warn = []
    if d3[2] in "2367":
        warn.append("Others can write: any user on the machine can change this. Avoid 777 and 666 outside throwaway test folders.")
    if special & 4:
        warn.append("Set-user-ID: the program runs as its owner (often root), whoever starts it. Risky; only for audited programs, and never on scripts.")
    if special & 2:
        warn.append("Set-group-ID: runs with the file's group; on a directory, new files inherit the group.")
    if special & 1:
        warn.append("Sticky bit: in a shared directory such as /tmp everyone can add files but only a file's owner, the directory's owner or root can delete them.")
    if kind == "file" and d3[0] in "0123" and special:
        pass
    um = None
    if umask:
        if not re.fullmatch(r"[0-7]{3,4}", umask.strip()):
            raise FundError("A umask looks like 022 or 077.")
        mk = int(umask.strip()[-3:], 8)
        base = 0o666 if kind == "file" else 0o777
        um = {"umask": umask.strip(), "new_mode": format(base & ~mk, "03o"), "symbolic": _sym_from_octal(format(base & ~mk, "03o")),
              "lesson": "A new file starts from 666 (files are never created executable) and a new directory from 777; the umask removes bits from that start."}
    return {"octal": octal, "symbolic": sym, "special": {"setuid": bool(special & 4), "setgid": bool(special & 2), "sticky": bool(special & 1)},
            "meaning": meaning, "warnings": warn, "umask": um,
            "commands": [f"chmod {octal} <name>", "chmod u+x <name>   (add execute for the owner)", "chmod g-w <name>   (remove write for the group)", "ls -l <name>   (check the result)"],
            "digits": "r=4, w=2, x=1: add them per person. The optional first digit is special bits: setuid 4, setgid 2, sticky 1 (so a shared directory is 1777 or 1775, not 175).",
            "limit": "Calculates modes only; it never touches a file. Windows uses ACLs (icacls), not these bits."}


# ------------------------------------------------------------ IPv6
def ipv6(addr: str) -> dict:
    a = (addr or "").strip()
    try:
        ip = ipaddress.IPv6Address(a.split("/")[0].split("%")[0])
    except ValueError:
        raise FundError("That isn't an IPv6 address (for example 2001:db8::1 or fe80::1).") from None
    if ip.ipv4_mapped:
        kind = "IPv4-mapped address (an IPv4 host written in IPv6 form)"
    elif ip.is_loopback:
        kind = "loopback (::1): this machine itself, the IPv6 form of 127.0.0.1"
    elif ip.is_unspecified:
        kind = "unspecified (::): 'no address yet'"
    elif ip.is_link_local:
        kind = "link-local (fe80::/10): works only on the local link; every IPv6 interface has one"
    elif ip.is_multicast:
        kind = "multicast (ff00::/8): sent to a group of hosts"
    elif ip in ipaddress.IPv6Network("fc00::/7"):
        kind = "unique local (fc00::/7): private, like 10.x or 192.168.x in IPv4"
    elif ip in ipaddress.IPv6Network("2001:db8::/32"):
        kind = "documentation range (2001:db8::/32): for examples only, never routed"
    elif ip in ipaddress.IPv6Network("2000::/3"):
        kind = "global unicast (2000::/3): routable on the internet"
    else:
        kind = "reserved or other"
    net = ipaddress.IPv6Network(f"{ip}/64", strict=False)
    return {"compressed": ip.compressed, "expanded": ip.exploded, "type": kind, "network_64": str(net), "interface_id": ip.exploded.split(":", 4)[4],
            "rules": ["Drop leading zeros in each group of four hex digits.", "Replace one run of all-zero groups with '::' (only once, or the address becomes ambiguous)."],
            "lesson": "IPv6 is 128 bits written as eight groups of four hex digits. A LAN normally gets a /64: the first 64 bits are the network and the last 64 identify the host. There is no broadcast; multicast replaces it, and NAT is not needed for address supply.",
            "limit": "Classifies the text you enter. It does not test whether the address is reachable."}


# ------------------------------------------------------------ command finder
# (task, windows, linux, note)
CMDS = [
    ("List files", "dir  /  Get-ChildItem", "ls -l  (ls -a shows hidden)", ""),
    ("Show or change folder", "cd <path>", "cd <path>   (pwd shows where you are)", "Windows paths use \\ and drive letters; Linux uses / from a single root."),
    ("Make a folder", "mkdir <name>", "mkdir -p <a/b/c>", ""),
    ("Copy", "copy <a> <b>  /  robocopy src dst /E", "cp -r <a> <b>", "Add -i on Linux to be asked before overwriting."),
    ("Move or rename", "move <a> <b>  /  ren <a> <b>", "mv <a> <b>", "Moving and renaming are one command on Linux."),
    ("Delete a file", "del <file>  /  Remove-Item", "rm <file>", "There is no recycle bin on the command line: deleted means gone."),
    ("Delete a folder and contents", "rmdir /s <dir>", "rm -r <dir>", "Check the path twice; rm -rf is unforgiving."),
    ("Show a file", "type <file>  /  more <file>", "cat <file>  /  less <file>", ""),
    ("Edit a text file", "notepad <file>", "nano <file>  /  vim <file>", "nano is easier to start with; vim: i to type, Esc then :wq to save and quit."),
    ("Search inside files", "findstr /s /i \"text\" *.txt  /  Select-String", "grep -ri \"text\" <dir>", ""),
    ("Find files by name", "dir /s <name>  /  Get-ChildItem -Recurse -Filter", "find <dir> -name \"<name>\"", ""),
    ("Pipe and redirect", "cmd | more  ,  > file  ,  >> file", "cmd | less  ,  > file  ,  >> file", "> overwrites, >> appends. PowerShell pipes objects; Linux pipes text."),
    ("Command history", "doskey /history  /  Get-History", "history", ""),
    ("Who am I, what groups", "whoami  /  whoami /groups", "id  /  groups", ""),
    ("List users", "net user  /  Get-LocalUser", "cut -d: -f1 /etc/passwd", ""),
    ("Add a user", "net user <name> * /add", "sudo adduser <name>", "Give new accounts the least privilege that works."),
    ("Remove a user", "net user <name> /delete", "sudo deluser <name>", "Disable before deleting if you are unsure."),
    ("Change a password", "net user <name> *", "sudo passwd <name>", "The * makes the prompt hide what you type."),
    ("Add a user to a group", "net localgroup <group> <name> /add", "sudo usermod -aG <group> <name>", "Linux: without -a the user is removed from their other groups."),
    ("See permissions", "icacls <path>", "ls -l <path>", ""),
    ("Change permissions", "icacls <path> /grant <user>:(R)", "chmod 640 <file>", "See the permission calculator."),
    ("Change owner", "takeown /f <path>  /  icacls /setowner", "sudo chown <user>:<group> <path>", ""),
    ("Install software", "winget install <name>", "sudo apt install <name>", "Package managers verify and track what they install."),
    ("Update software", "winget upgrade --all", "sudo apt update && sudo apt upgrade", "update refreshes the list; upgrade installs."),
    ("List installed software", "winget list", "apt list --installed  /  dpkg -l", ""),
    ("Archive or compress", "Compress-Archive -Path <dir> -DestinationPath <zip>", "tar -czf <name>.tar.gz <dir>", "tar -xzf extracts."),
    ("List disks and partitions", "diskpart (list disk)  /  Get-Disk", "lsblk  /  sudo fdisk -l", "Partitioning can erase data: confirm the disk number or name."),
    ("Format a volume", "format <drive>: /fs:ntfs  /  Format-Volume", "sudo mkfs.ext4 <device>", "Destroys what is on it."),
    ("Mount a filesystem", "diskpart (assign letter)", "sudo mount <device> <dir>  /  umount <dir>", ""),
    ("Disk space", "Get-Volume  /  fsutil volume diskfree C:", "df -h  ;  du -sh <dir>", "df is per filesystem; du is per folder."),
    ("Check and repair a filesystem", "chkdsk <drive>: /f", "sudo fsck <device>", "Unmount the filesystem first on Linux."),
    ("List processes", "tasklist  /  Get-Process", "ps aux  /  top", ""),
    ("Stop a process", "taskkill /PID <pid>  /  Stop-Process", "kill <pid>  (kill -9 only if it ignores that)", "kill sends a polite request (SIGTERM); -9 cannot be caught and skips cleanup."),
    ("Watch resources", "Get-Counter  /  Task Manager  /  perfmon", "top  /  vmstat  /  free -h", ""),
    ("Services", "Get-Service  /  sc query", "systemctl status|start|stop|enable <name>", ""),
    ("Logs", "Get-WinEvent  /  Event Viewer", "journalctl -u <name>  ;  /var/log/", ""),
    ("Hardware and drivers", "driverquery  /  pnputil /enum-drivers", "lspci  ;  lsusb  ;  lsmod", ""),
    ("OS and kernel info", "systeminfo  /  winver", "uname -a  ;  lsb_release -a", ""),
    ("Remote login", "mstsc (RDP)  /  ssh <user>@<host>", "ssh <user>@<host>", "SSH replaces Telnet because it encrypts the session."),
    ("Copy over SSH", "scp <file> <user>@<host>:<path>", "scp <file> <user>@<host>:<path>", ""),
    ("Network settings", "ipconfig /all", "ip addr", ""),
    ("DNS lookup", "nslookup <name>", "dig <name>  /  nslookup <name>", ""),
    ("Test a TCP port", "Test-NetConnection <host> -Port <n>", "nc -zv <host> <n>", "A refused connection and a timeout mean different things: refused = reached the host, nothing listening; timeout = blocked or unreachable."),
    ("Scheduled jobs", "schtasks  /  Task Scheduler", "crontab -e  (cron)", ""),
    ("Shut down or restart", "shutdown /s /t 0   (/r to restart)", "sudo shutdown now  /  sudo reboot", ""),
]


def commands(query: str = "") -> dict:
    q = (query or "").strip().lower()
    rows = [{"task": t, "windows": w, "linux": lx, "note": n} for t, w, lx, n in CMDS if not q or all(x in f"{t} {w} {lx} {n}".lower() for x in q.split())]
    return {"rows": rows, "total": len(CMDS),
            "note": "Read what a command does before you run it, and try destructive ones (delete, format, kill) on a test folder or machine first. sudo and administrator rights bypass the safety checks."}


# ------------------------------------------------------------ reference
REFERENCE = {
    "connections": [
        ("Dial-up (modem)", "Up to 56 Kbps over a phone line, phone and internet can't be used together. Obsolete."),
        ("T1 / T-carrier", "Leased digital line: T1 is 1.544 Mbps (24 channels of 64 Kbps), T3 is about 45 Mbps. Symmetric and expensive; replaced mostly by fibre and Ethernet WAN."),
        ("DSL (ADSL / SDSL)", "Digital data over copper phone lines. ADSL is faster down than up; SDSL is the same both ways. Speed falls with distance from the exchange."),
        ("Cable broadband", "Shares coaxial cable with TV; speed can drop at busy times because neighbours share the segment."),
        ("Fibre", "Light in glass: highest speed and distance, immune to electrical interference. Fibre to the home gives symmetric gigabit plans."),
        ("Cellular (4G LTE, 5G)", "Radio to towers; good for mobile and backup links. Speed and latency depend on signal and congestion."),
        ("Satellite", "Reaches remote places; geostationary has high latency (about 600 ms), low-orbit constellations are much lower."),
        ("WAN / point-to-point VPN", "Joins sites over the internet or leased lines; a VPN encrypts the tunnel, a proxy relays requests for a client."),
    ],
    "wireless": [
        ("2.4 GHz", "Reaches further and through walls but is crowded; only channels 1, 6 and 11 do not overlap in North America."),
        ("5 GHz", "Faster, more channels, shorter range."),
        ("6 GHz", "Wi-Fi 6E and 7: most capacity, shortest range, needs newer devices."),
        ("WEP", "Broken; cracked in minutes. Never use."),
        ("WPA / TKIP", "A stopgap for old hardware; deprecated."),
        ("WPA2 (AES-CCMP)", "Long the standard; a strong passphrase matters."),
        ("WPA3", "Current: stronger handshake that resists offline password guessing, and protected management frames."),
        ("MAC filtering", "Not real security: MAC addresses are visible over the air and easy to copy. Use it only as an extra."),
        ("Site survey tips", "Place access points centrally, pick the least busy channel, use 5 GHz where you can, and keep the SSID and passphrase out of default."),
    ],
    "cellular_iot": [
        ("1G to 5G", "1G analog voice; 2G digital voice and text (GSM, CDMA); 3G mobile data; 4G LTE all-IP broadband; 5G higher speed, lower latency, many devices per cell."),
        ("SIM / eSIM", "Identifies the subscriber to the carrier; an eSIM is a rewritable chip instead of a card."),
        ("Bluetooth / BLE", "Short range, low power, pairing between nearby devices."),
        ("Zigbee / Z-Wave", "Low-power mesh for smart-home sensors; each device relays for others."),
        ("LoRaWAN", "Very long range, very low data rate, years on a battery: meters and field sensors."),
        ("NFC", "A few centimetres: tap to pay and tap to pair."),
        ("IoT security", "Change default passwords, put devices on their own network or VLAN, update firmware, and turn off what you don't use."),
    ],
    "cloud": [
        ("IaaS", "You rent virtual machines, storage and networks and manage the OS upward (examples: a cloud VM)."),
        ("PaaS", "You deploy code or data to a platform; the provider runs the OS and runtime."),
        ("SaaS", "You use finished software over the web (email, office suites); you manage accounts and data only."),
        ("Public / private / hybrid", "Shared provider infrastructure; your own; or a mix joined together."),
        ("Shared responsibility", "The provider secures the cloud; you secure what you put in it: accounts, data, settings."),
        ("Cloud storage", "Object, file and block storage differ: objects for files and backups, block for VM disks, file for shared folders."),
    ],
    "services": [
        ("DNS", "Names to addresses. Forward zones map name to IP, reverse zones map IP to name. Internal DNS lets staff reach printer.office by name."),
        ("DHCP", "Hands out address, mask, gateway and DNS server automatically, with a lease. Needs a scope and, for fixed devices, reservations."),
        ("NTP", "Keeps clocks in step; logs and Kerberos break when clocks drift."),
        ("Email", "SMTP sends (25 between servers, 587 for clients), IMAP keeps mail on the server and syncs devices (143/993), POP3 downloads it (110/995)."),
        ("Spam control", "SPF, DKIM and DMARC authenticate senders; filters score content; users report what slips through."),
        ("File services", "SMB shares for Windows (445), NFS for Linux, SFTP/FTPS for transfers. FTP and TFTP send in clear text: avoid on untrusted networks."),
        ("Web and certificates", "HTTPS uses TLS certificates that must be renewed before they expire."),
        ("Remote access", "RDP and VNC show a desktop, SSH gives a shell. Expose them only through a VPN or a gateway, with strong authentication."),
    ],
    "sysadmin": [
        ("Provisioning", "A new starter needs an account, groups, mailbox, a prepared machine and training; leavers need the reverse, quickly."),
        ("Routine maintenance", "Patching, backups with test restores, capacity checks, log review, certificate and licence renewals."),
        ("Change management", "Write down what will change, why, the risk, the rollback and who approved it; test first; announce; review afterwards. Emergency changes still get written up, after."),
        ("Vendor life cycle", "Before the contract: references, security and financial history. During delivery: a communication plan and regular check-ins. After: review, renewal or exit and data return."),
        ("Risk", "Weigh how likely a failure is and how bad it would be; never test in production; keep a way back."),
        ("Document what you do", "Keep a record of commands run and changes made (a session transcript or ticket notes), so you can reverse and explain them."),
        ("Imaging and deployment", "A golden image plus automation gives identical machines fast; keep the image patched and separate user data from the OS."),
    ],
    "connectors": [
        ("3.5 mm audio plugs", "TS has 2 contacts (mono), TRS has 3 (tip left, ring right, sleeve ground), TRRS has 4 and adds a microphone."),
        ("TRRS: CTIA vs OMTP", "Two layouts exist. CTIA (also called AHJ, used by Apple, most Android phones, PCs and consoles): tip left, ring 1 right, ring 2 ground, sleeve microphone. OMTP (older Nokia and some older phones): tip left, ring 1 right, ring 2 microphone, sleeve ground. A headset on the wrong layout gives no microphone or a muffled sound; a small adapter swaps the two."),
        ("Wire colours", "Colours inside a headphone cable are not standard. Trace each wire to its contact with a multimeter on continuity before you solder; never trust colour alone."),
        ("Other jack sizes", "2.5 mm (small phones, some headsets), 3.5 mm (standard), 6.35 mm or 1/4 inch (instruments, studio gear). Balanced TRS and unbalanced TS look alike but carry different signals."),
        ("Ethernet cable categories", "Cat 5e 1 Gbps, Cat 6 1 Gbps (10 Gbps to about 37 to 55 m), Cat 6a 10 Gbps to 100 m, Cat 7 (ISO only, shielded), Cat 8 for short data-centre runs. Use the network cable chooser for a pick."),
    ],
    "disks": [
        ("MBR", "Master Boot Record: boots with BIOS, up to 4 primary partitions (or 3 plus an extended one holding logical partitions), and a 2 TiB limit with 512-byte sectors."),
        ("GPT", "GUID Partition Table: boots with UEFI (BIOS needs a small boot partition), 128 partitions by default and a size limit far beyond any real disk, with a backup copy of the table at the end of the disk."),
        ("fdisk", "Interactive partition editor. Current versions (util-linux 2.23 and later) handle GPT as well as MBR. Nothing is written until you press w; q quits and discards. Safe habit: print the table (p) first."),
        ("parted", "Handles MBR and GPT and works in interactive or scripted mode. Changes take effect immediately, with no w to save, so a typo is live at once. 'mklabel' replaces the whole partition table."),
        ("gdisk / sgdisk", "The GPT-focused editors, with gdisk interactive and sgdisk scriptable. sfdisk is the scriptable fdisk."),
        ("Resizing", "Resizing a partition does not resize what is inside it. Grow the partition first, then the file system (resize2fs for ext4, xfs_growfs for XFS, ntfsresize for NTFS); to shrink, shrink the file system first. Back up before either."),
        ("After partitioning", "Make a file system (mkfs.ext4), mount it, then add it to /etc/fstab using its UUID from blkid so it still mounts if device names change. Check with lsblk and df -h."),
    ],
    "desktop_apps": [
        ("Browsers on Linux", "Firefox (Gecko), LibreWolf and Zen are Gecko-based; Brave, Vivaldi, Chromium and Chrome are Chromium-based (Blink); Mullvad Browser is built on Firefox ESR with Tor Browser's anti-fingerprinting. Falkon uses Qt WebEngine, which is Chromium underneath. Chrome itself is not open source; Chromium is."),
        ("Choosing", "Privacy focus: Firefox hardened, LibreWolf, Mullvad. Compatibility: Chromium family. Check how it installs (package, Flatpak, Snap) and how quickly it gets security updates; a browser that lags is a risk."),
        ("PowerPoint keys", "Ctrl+N new, Ctrl+M new slide, Ctrl+D duplicate slide or object, Ctrl+O open, Ctrl+S save, F12 save as, Ctrl+P print, Ctrl+Z undo, Ctrl+Y redo (also F4), Ctrl+C/X/V copy, cut, paste, Ctrl+A select all, Ctrl+G group, Ctrl+Shift+G ungroup, Ctrl+K hyperlink, Ctrl+B/I/U bold, italic, underline, Ctrl+L/E/R/J align left, centre, right, justify, Ctrl+T font dialog, F5 start the show, Shift+F5 from this slide, Esc end the show. Zoom is Ctrl plus the mouse wheel."),
    ],
    "hardware": [
        ("CPU cache", "Small fast memory on the processor: L1 is smallest and fastest, L3 is largest and shared."),
        ("32-bit vs 64-bit", "A 32-bit system addresses about 4 GB of RAM; use 64-bit unless an old driver or program needs 32."),
        ("USB", "USB 2.0 480 Mbps; USB 3.0 5 Gbps; 3.1 10 Gbps; 3.2 up to 20 Gbps; USB4 up to 40 Gbps. Connector shape (A, micro, C) is separate from speed. Colours are a hint, not a guarantee."),
        ("Charging", "More amps charge faster if the device and cable allow it; use certified cables, and a charger can't push more than the device accepts."),
        ("Display types", "IPS: good colour and angles. TN: fast, weak colour. VA: high contrast, can smear in fast motion. OLED: self-lit pixels, true black, burn-in risk. mini-LED backlights improve LCD contrast."),
        ("Storage", "HDD: spinning platters, cheap per TB, slow, fragile. SSD: flash, fast, no moving parts. Both wear or fail: back up."),
        ("Power supply", "Match wall voltage, motherboard connectors (24-pin, CPU 4/8-pin, GPU 6/8-pin) and total wattage with headroom."),
        ("Overclocking", "Raising the CPU multiplier past spec: more heat and a risk of instability or damage; warranty may be void. Not for work machines."),
    ],
}

SLIPS = [
    "Disk poster: 'fdisk supports only MBR' is out of date. Current fdisk edits GPT too; gdisk is the GPT-first tool. It also leaves out the habit that matters most: fdisk saves only on w, but parted changes the disk the moment you press Enter.",
    "Audio jack poster: it shows the OMTP order (microphone on ring 2, ground on the sleeve). Most phones, laptops and consoles since 2012 use CTIA (ground on ring 2, microphone on the sleeve). The wire colours drawn are one cable's, not a standard.",
    "PowerPoint poster: 'Ctrl+Shift+D' is given for Duplicate slide; the documented key is Ctrl+D. 'Ctrl+ +' and 'Ctrl+ -' for zoom and 'Ctrl+Alt+O' for zoom to fit are not in Microsoft-style shortcut lists I checked (zoom is Ctrl plus the mouse wheel); test them in your version before teaching them.",
    "Firewall poster: it ticks Domain, Private and Public for the rule. Public is the profile for cafe and airport networks; allow only the profiles the program needs. Also note a Block rule beats an Allow rule, so delete or disable the stray block rather than adding an allow.",
    "Linux browsers poster: Falkon is listed as 'very low CPU and RAM usage', but it uses Qt WebEngine, which is Chromium-based, so memory use is not small. 'Chrome: popular' is not an open-source claim; only Chromium is open source.",
    "'30 ChatGPT secret codes': these are not codes or commands. There is no hidden switch; each word is just a style hint inside a normal prompt, and the results vary by model. Writing 'make this a clay sculpture' does the same job.",
    "The sticky-bit example reads 'chmod 175 my folder'. A sticky shared directory is 1775 (or 1777); 175 gives the owner only execute and is not a sticky bit at all.",
    "The wireless lesson says WPA2 'uses a 256-bit key'. WPA2 normally encrypts with 128-bit AES (CCMP); 256-bit keys belong to WPA3 and its Enterprise mode. The lesson also omits WPA3.",
    "MAC filtering is presented as a barrier; it stops only the casual. Addresses are broadcast in clear and are trivial to copy.",
    "The storage table labels the difference as '-2.4%', '-4.9%' and so on; those are the binary excess over the decimal figure. What a drive loses on screen is smaller and grows with the unit: 2.3%, 4.6%, 6.9%, 9.1% (TB), 11.2% (PB).",
    "The USB 3.0 / 3.1 colour rule (blue, teal) is only a convention; there is no standard that forces it. Check the port's rated speed.",
]

NOT_BUILT = [
    "The course's hands-on labs (Qwiklabs: Dnsmasq DNS and DHCP, Linux and Windows shells). They need real virtual machines; the command finder and calculators prepare you for them.",
    "Building or repairing a real PC, crimping cables, imaging machines or installing an OS: needs hardware.",
    "The course's quizzes and graded assessments. Questions here are original.",
]


def reference(topic: str = "") -> dict:
    if topic:
        if topic not in REFERENCE:
            raise FundError("No such topic.", 404)
        return {"topic": topic, "rows": REFERENCE[topic]}
    return {"topics": list(REFERENCE), "sections": {k: [{"item": a, "note": b} for a, b in v] for k, v in REFERENCE.items()},
            "slips": SLIPS, "not_built": NOT_BUILT}
