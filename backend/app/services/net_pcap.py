"""Read a saved packet capture (.pcap or .pcapng) and summarise it. Reads a file only; it never captures live traffic."""
from __future__ import annotations

import base64
import binascii
import ipaddress
import struct
from collections import Counter, defaultdict

from app.services.netlab import NetError

MAX_BYTES = 6_000_000
MAX_PACKETS = 50_000


def _decode(b64: str) -> bytes:
    try:
        raw = base64.b64decode(b64 or "", validate=False)
    except (binascii.Error, ValueError):
        raise NetError("The file could not be read. Choose a .pcap or .pcapng file.") from None
    if not raw:
        raise NetError("The file is empty.")
    if len(raw) > MAX_BYTES:
        raise NetError("That capture is over 6 MB. Trim it first, for example with tcpdump -c 20000 or Wireshark's export.")
    return raw


def _packets(raw: bytes):
    """Yield (timestamp, linktype, data)."""
    magic = raw[:4]
    if magic in (b"\xd4\xc3\xb2\xa1", b"\xa1\xb2\xc3\xd4", b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d"):
        le = magic in (b"\xd4\xc3\xb2\xa1", b"\x4d\x3c\xb2\xa1")
        nano = magic in (b"\x4d\x3c\xb2\xa1", b"\xa1\xb2\x3c\x4d")
        e = "<" if le else ">"
        if len(raw) < 24:
            raise NetError("The capture header is cut short.")
        link = struct.unpack(e + "I", raw[20:24])[0] & 0xFFFF
        i = 24
        while i + 16 <= len(raw):
            sec, frac, cl, ol = struct.unpack(e + "IIII", raw[i:i + 16])
            i += 16
            if cl > 262144 or i + cl > len(raw):
                break
            yield sec + frac / (1e9 if nano else 1e6), link, raw[i:i + cl]
            i += cl
        return
    if raw[:4] == b"\x0a\x0d\x0d\x0a":
        i, e, links, res = 0, "<", [], {}
        while i + 12 <= len(raw):
            if raw[i:i + 4] == b"\x0a\x0d\x0d\x0a":
                e = "<" if raw[i + 8:i + 12] == b"\x4d\x3c\x2b\x1a" else ">"
                links = []
            t, ln = struct.unpack(e + "II", raw[i:i + 8])
            if ln < 12 or i + ln > len(raw):
                break
            body = raw[i + 8:i + ln - 4]
            if t == 1:
                links.append(struct.unpack(e + "H", body[:2])[0])
                res[len(links) - 1] = 1e-6
            elif t == 6 and len(body) >= 20:
                ifid, th, tl, cap, _ = struct.unpack(e + "IIIII", body[:20])
                yield ((th << 32) | tl) * res.get(ifid, 1e-6), links[ifid] if ifid < len(links) else 1, body[20:20 + cap]
            i += ln
        return
    raise NetError("This is not a pcap or pcapng file. Save the capture as .pcap from Wireshark or tcpdump -w.")


def _mac(b: bytes) -> str:
    return ":".join(f"{x:02x}" for x in b)


def _dns_name(d: bytes) -> str | None:
    try:
        if len(d) < 13 or struct.unpack(">H", d[4:6])[0] < 1:
            return None
        i, parts = 12, []
        while i < len(d) and d[i]:
            n = d[i]
            if n & 0xC0:
                return None
            parts.append(d[i + 1:i + 1 + n].decode("ascii", "replace"))
            i += n + 1
        return ".".join(parts) or None
    except (struct.error, IndexError):
        return None


def read(b64: str) -> dict:
    raw = _decode(b64)
    n = 0
    t0 = t1 = None
    proto, talkers, convs, dports = Counter(), Counter(), Counter(), Counter()
    flags = Counter()
    syn, synack = {}, set()
    seen = set()
    retrans = 0
    dns = Counter()
    arp = defaultdict(set)
    skipped = 0
    sizes = []
    for ts, link, d in _packets(raw):
        n += 1
        if n > MAX_PACKETS:
            n -= 1
            break
        t0 = ts if t0 is None else t0
        t1 = ts
        sizes.append(len(d))
        try:
            if link == 1:
                et = struct.unpack(">H", d[12:14])[0]
                off = 14
                if et == 0x8100:
                    et = struct.unpack(">H", d[16:18])[0]
                    off = 18
                    proto["VLAN-tagged"] += 1
            elif link == 101:
                et, off = (0x0800 if d[0] >> 4 == 4 else 0x86DD), 0
            elif link == 113:
                et, off = struct.unpack(">H", d[14:16])[0], 16
            else:
                skipped += 1
                continue
            if et == 0x0806:
                proto["ARP"] += 1
                op = struct.unpack(">H", d[off + 6:off + 8])[0]
                if op == 1:
                    arp[str(ipaddress.ip_address(d[off + 24:off + 28]))].add(str(ipaddress.ip_address(d[off + 14:off + 18])))
                continue
            if et == 0x0800:
                ihl = (d[off] & 15) * 4
                p = d[off + 9]
                src, dst = str(ipaddress.ip_address(d[off + 12:off + 16])), str(ipaddress.ip_address(d[off + 16:off + 20]))
                tp = off + ihl
                tot = struct.unpack(">H", d[off + 2:off + 4])[0]
                end = min(len(d), off + tot) if tot else len(d)
            elif et == 0x86DD:
                p = d[off + 6]
                src, dst = str(ipaddress.ip_address(d[off + 8:off + 24])), str(ipaddress.ip_address(d[off + 24:off + 40]))
                tp = off + 40
                end = len(d)
            else:
                proto[f"Other (0x{et:04x})"] += 1
                continue
            talkers[src] += 1
            if p == 6:
                sp, dp, seq, ack, fl = struct.unpack(">HHIIxB", d[tp:tp + 14])[0:2] + struct.unpack(">II", d[tp + 4:tp + 12]) + (d[tp + 13],)
                proto["TCP"] += 1
                convs[tuple(sorted([f"{src}:{sp}", f"{dst}:{dp}"]))] += 1
                dports[dp] += 1
                if fl & 2 and not fl & 16:
                    flags["SYN"] += 1
                    syn[(src, sp, dst, dp)] = syn.get((src, sp, dst, dp), 0) + 1
                if fl & 2 and fl & 16:
                    flags["SYN-ACK"] += 1
                    synack.add((dst, dp, src, sp))
                if fl & 4:
                    flags["RST"] += 1
                if fl & 1:
                    flags["FIN"] += 1
                hl = (d[tp + 12] >> 4) * 4
                plen = max(0, end - tp - hl)
                if plen > 0:
                    k = (src, sp, dst, dp, seq, plen)
                    if k in seen:
                        retrans += 1
                    seen.add(k)
            elif p == 17:
                sp, dp = struct.unpack(">HH", d[tp:tp + 4])
                proto["UDP"] += 1
                convs[tuple(sorted([f"{src}:{sp}", f"{dst}:{dp}"]))] += 1
                dports[dp] += 1
                if dp == 53 or sp == 53:
                    proto["DNS"] += 1
                    if dp == 53 and (nm := _dns_name(d[tp + 8:end])):
                        dns[nm] += 1
            elif p in (1, 58):
                proto["ICMP" if p == 1 else "ICMPv6"] += 1
            else:
                proto[f"IP protocol {p}"] += 1
        except (IndexError, struct.error, ValueError):
            skipped += 1
    if n == 0:
        raise NetError("No packets were found in that file.")
    unanswered = [f"{a}:{b} -> {c}:{e}" for (a, b, c, e), cnt in syn.items() if (a, b, c, e) not in synack][:10]
    findings = []
    if unanswered:
        findings.append(f"{len(unanswered)} connection attempt(s) got no SYN-ACK back (firewall drop, host down or port closed without a reset). Example: {unanswered[0]}.")
    if flags["RST"]:
        findings.append(f"{flags['RST']} reset packet(s): something refused or aborted a connection.")
    if retrans:
        findings.append(f"{retrans} packet(s) repeat a sequence number already seen. That suggests retransmission, which means loss or delay on the path (or the capture saw a duplicate).")
    scans = [a for a, ports in _scan(syn).items() if ports >= 10]
    if scans:
        findings.append(f"{scans[0]} sent connection attempts to 10 or more different ports on one host. That pattern can be a port scan, or a busy client; look at the timing.")
    asks = [ip for ip, a in arp.items() if len(a) >= 1]
    return {"packets": n, "skipped": skipped, "seconds": round((t1 or 0) - (t0 or 0), 3), "avg_bytes": round(sum(sizes) / len(sizes), 1),
            "protocols": proto.most_common(), "top_talkers": talkers.most_common(8), "top_conversations": [{"pair": " <-> ".join(k), "packets": v} for k, v in convs.most_common(8)],
            "top_dest_ports": dports.most_common(8), "tcp_flags": flags.most_common(), "dns_names": dns.most_common(10), "arp_requests_for": len(asks), "findings": findings,
            "lesson": "Start with the summary (who talks, which protocols), then look for the odd one: connections with no answer, resets, repeats. Then open the capture in Wireshark for the exact packets."}


def _scan(syn):
    out = defaultdict(set)
    for (a, _sp, c, dp) in syn:
        out[(a, c)].add(dp)
    return {f"{a} -> {c}": len(v) for (a, c), v in out.items()}


NOT_BUILT = ["Live capture (it needs the computer's network card and permission); capture with Wireshark or tcpdump and load the saved file here.", "TLS decryption, TCP stream reassembly, and protocols beyond Ethernet, ARP, IP, TCP, UDP, ICMP and DNS names.", "Files over 6 MB or 50,000 packets."]
SLIPS = ["Capture guides say a SYN with no reply 'proves a firewall block'. It can also be a down host, a routing problem, or the capture point missing the reply.", "Retransmission counts from a capture taken on the sending host can look high because of offloading; check where the capture was taken."]
