# Network Engineering

A network engineer designs, builds and fixes the paths data takes between machines. This track gives you practice tools that run inside the dashboard, plus an honest map of the professional tools that don't.

## The five ideas to own
1. **Layers.** Fault-find from the bottom: cable and link (1-2), addressing and routing (3), ports (4), then the application. The Reference tab has the OSI table and a troubleshooting method.
2. **Addressing.** An IPv4 address is 32 bits; the prefix says how many belong to the network. A /24 has 256 addresses and 254 usable hosts (network and broadcast are reserved). Practise on the Subnet tab until you can do a /26 in your head.
3. **Segmentation.** VLANs and subnets keep groups apart so a problem or an intruder in one doesn't reach everything. Plan with VLSM: biggest subnets first, each on its own boundary.
4. **Name resolution.** If an IP works but a name doesn't, it's DNS. Say so out loud before touching anything else.
5. **Change discipline.** Change one thing, record it, know how to undo it. Most outages follow a change.

## What is built in
| Tab | What it does | Honest limit |
|---|---|---|
| Subnet and VLSM | Subnet calculator, split, VLSM plan, overlap check, route summarisation | Exact arithmetic (Python `ipaddress`). IPv6 is shown but host counts aren't. |
| Config review | Pattern checks on a pasted router or switch config (Cisco IOS style) | Text patterns, not a CIS audit. Knows nothing about your design. |
| Packet capture | Reads `tcpdump -nn` text you paste: top talkers, ports, scan-like patterns | Reads text only; it never captures. Findings are leads. |
| DNS and reachability | A/AAAA lookup and a one-port TCP test | Public hosts only, one port per request, 12 checks a minute. Not a scanner. |
| Calculators | Transfer time, bandwidth-delay product and window limit | Printed assumptions; real links vary. |
| Reference | Ports, OSI layers, commands for Windows, Linux and Cisco | Static tables. |

## Tools you will meet that are NOT embedded
- **Wireshark / tcpdump**: capture and read packets on a network you own. The Packet capture tab reads tcpdump text so you can learn the patterns first.
- **Cisco Packet Tracer, GNS3, EVE-NG**: build virtual networks of routers and switches. Free, and where you should practise routing protocols (OSPF, BGP) and VLAN trunking.
- **iperf3**: measures real throughput between two machines you control.
- **Nmap**: discovers hosts and services. Use it only on networks you own or have written permission to test; this app doesn't scan.
- **Zabbix, Nagios, PRTG, Grafana + Prometheus, SNMP**: monitoring. Point Prometheus at `/metrics` for a first graph.
- **Ansible, Netmiko, NAPALM**: automate device changes with code instead of typing into each box.
- **pfSense / OPNsense**: free firewall and router software to run in a VM.
Cloud networking (VPCs, transit gateways) is out of scope here.

## Practice ideas
- Plan a small office: 60 staff, 20 guest Wi-Fi, 10 servers, 2 point-to-point links, all out of 10.20.0.0/22.
- Paste the sample config, fix every high finding, and explain each in one sentence.
- Paste the sample capture and decide: scan, monitoring or a broken client? What else would you check?
- Test DNS and port 443 for a site you run, then explain what each result rules out.
- Work out how long 200 GB takes over 100 Mbps at 85% efficiency, then see why one TCP stream may not fill a 1 Gbps, 80 ms link.

## Limits
Nothing here replaces a lab with real gear. The tools run against text you paste and public hosts; they don't touch your network.
