# Part 10: Network Engineer

## The role in one page

A network engineer designs, builds, watches and repairs the paths that data takes between machines: from a laptop to a printer, from a branch office to a data centre, from your customers to your web server. The product is boring when it works. Nobody thanks you for a packet that arrived.

**Who you work with.** Help-desk staff who escalate "the internet is down" tickets, system administrators who need a VLAN or a firewall rule, security staff who want segmentation and logs, application teams who blame the network first, and vendors (internet providers, equipment makers) whose support lines you will learn to navigate. Part 9 (Cybersecurity) and Part 11 (IT Specialist) overlap with this role most.

**A typical day.** Check overnight alerts and the monitoring graphs. Handle two or three requests: a new VLAN for a printer group, a firewall exception, a site that cannot reach a cloud service. Spend an hour on planned work: an address plan for a new office, a switch replacement, a config template. Spend another hour on one hard fault where everyone has a theory and nobody has evidence. Write it all down before you leave.

**What good looks like.**

- Addressing is planned on paper before it is typed into a device, and there are no overlaps.
- Every device has a recorded purpose, owner, config backup and a description on each important port.
- Faults are found by method (layer by layer, one change at a time) not by superstition or rebooting everything.
- Changes are small, written down, reviewed and reversible.
- You can say what you do not know and what evidence would settle it.

**What it is not.** It is not hacking, though you must understand how attacks use networks. It is not only cabling, and it is not only certifications. It is also not the same as a systems administrator's job (servers and users) or a cloud architect's job (virtual networks in a provider's portal), though the ideas carry across. Cloud networking is out of scope for this part.

**Honest hard parts.**

- Faults are often intermittent, and the evidence disappears when you look at it.
- Production changes carry real risk; a typo on a remote router can lock you out of the box you are fixing.
- Much of the knowledge is vendor-specific syntax on top of vendor-neutral ideas. Learn the ideas first; the syntax you can look up.
- You get blamed for problems that live in DNS, certificates, applications or the user's Wi-Fi. Evidence is your defence, not argument.
- Real practice needs real or virtual gear. Reading and arithmetic teach the ideas; only a lab builds the skill.

## How to use this part

There are four levels. Times assume about five hours a week, mixing reading, hands-on practice and exercises.

| Level | Focus | Estimated time |
|---|---|---|
| 1 Foundations | Layers, addressing, subnet arithmetic, first troubleshooting | 20 hours (about 4 weeks) |
| 2 Practitioner | VLSM, VLANs, static routing, switching, DHCP, DNS, NAT | 30 hours (about 6 weeks) |
| 3 Advanced | Dynamic routing, wireless, firewalls, throughput, capture reading | 35 hours (about 7 weeks) |
| 4 Expert | Monitoring, automation, design trade-offs, review, ethics, scale | 30 hours (about 6 weeks) |

The capstones add 15 to 40 hours each. Do not rush: Level 1 skills are the ones you will use every day for years.

**Pair the reading with practice.** For each concept, first do the arithmetic by hand on paper, then check it with an independent tool: a subnet calculator or Python's `ipaddress` module. A disagreement means you made the mistake, and finding it is the learning. Each level ends with "Practice on your own": labs using a home router, virtual machines, free simulators and your own computers.

**Honest limits.**

- A config review by pattern is not a full security audit; it cannot know your design.
- Capture analysis and scan results are leads, not verdicts.
- Scanners (Nmap), live capture (Wireshark, tcpdump), simulators (Packet Tracer, GNS3, EVE-NG) and monitoring systems are powerful. Use them only on networks you own or have written permission to test.
- A connection test on one port is a diagnostic; sweeping many hosts or ports is scanning.

## Level 1: Foundations (beginner)

### What you will be able to do

- You can name the layers of the OSI and TCP/IP models and say which layer a given fault belongs to.
- You can convert an IPv4 address between dotted decimal and binary.
- You can find the network address, broadcast address, host range and host count for any prefix from /24 to /30 by hand.
- You can explain what a switch, router, access point and firewall each decide.
- You can say what ARP, a default gateway and a port number are for.
- You can run the first five diagnostic commands in the right order and explain what each result rules out.

### Core ideas

#### Layers and encapsulation

Networks are explained in layers so that each can be understood and fixed on its own. The OSI model has seven: Physical (1), Data link (2), Network (3), Transport (4), Session (5), Presentation (6), Application (7). The TCP/IP model that the internet actually uses has four: Link, Internet, Transport, Application. Layers 5 to 7 of OSI collapse into TCP/IP's Application layer.

As data goes down the stack on the sender, each layer wraps it: the application's data becomes a TCP segment (adds ports), then an IP packet (adds source and destination addresses), then an Ethernet frame (adds MAC addresses and a check sequence), then bits on the wire. The receiver unwraps in reverse. A switch looks only at the frame header. A router opens the frame, reads the packet header, and builds a new frame for the next link. That difference (frames stay on one link, packets travel end to end) explains most of networking.

A good OSI table lists the typical faults at each layer: bad cable (1), VLAN mismatch (2), wrong gateway (3), blocked port (4), bad certificate (6/7). Build one yourself; it is your fault-finding map.

**Worked example.** You browse to a site. DNS (application) turns the name into an address. TCP (transport) opens a connection to port 443. IP (network) carries packets to your gateway. Ethernet (link) carries each frame to the gateway's MAC address. Every hop replaces the frame; the IP packet stays the same (except NAT, Level 2).

#### IPv4 addresses and the prefix

An IPv4 address is 32 bits, written as four decimal numbers called octets, each 0 to 255. The prefix length (the number after the slash) says how many leading bits are the network part; the remaining bits identify the host. So 192.168.10.77/26 means the first 26 bits are the network, the last 6 are the host.

The netmask is the same idea written as an address: /24 is 255.255.255.0, /26 is 255.255.255.192, /16 is 255.255.0.0. The wildcard mask (used in Cisco ACLs and OSPF) is the inverse: /26 gives 0.0.0.63.

**Binary.** 77 is 01001101 (64 + 8 + 4 + 1). The octet values to memorise are 128, 64, 32, 16, 8, 4, 2, 1. Any octet is a sum of those.

**Worked example: 192.168.10.77/26.** The /26 leaves 6 host bits, so each subnet has 2^6 = 64 addresses and the subnets in the last octet start at 0, 64, 128, 192. The address 77 falls in the block starting at 64. So:

- Network address: 192.168.10.64
- Broadcast: 192.168.10.127 (the last address in the block)
- Usable hosts: .65 to .126, which is 64 - 2 = 62
- Netmask: 255.255.255.192

The two subtracted addresses are the network address (identifies the subnet) and the broadcast address (reaches everyone in it). Special cases: a /31 is a point-to-point link with two usable addresses (RFC 3021), and a /32 is a single host.

#### Subnet cheat table and the block-size trick

You will use these constantly until they are reflex:

| Prefix | Netmask | Addresses | Usable hosts |
|---|---|---|---|
| /30 | 255.255.255.252 | 4 | 2 |
| /29 | 255.255.255.248 | 8 | 6 |
| /28 | 255.255.255.240 | 16 | 14 |
| /27 | 255.255.255.224 | 32 | 30 |
| /26 | 255.255.255.192 | 64 | 62 |
| /25 | 255.255.255.128 | 128 | 126 |
| /24 | 255.255.255.0 | 256 | 254 |
| /23 | 255.255.254.0 | 512 | 510 |
| /22 | 255.255.252.0 | 1,024 | 1,022 |

The block-size trick works when the prefix cuts inside an octet. Find the "interesting" octet (the one that is neither 255 nor 0 in the mask). Block size = 256 minus that mask octet. The network address is your address rounded down to a multiple of the block size.

**Worked example: 172.16.45.200/20.** The mask is 255.255.240.0; the interesting octet is the third, and the block size is 256 - 240 = 16. The third octet 45 rounds down to 32 (2 x 16). So the network is 172.16.32.0, and the broadcast is the last address before the next block (third octet 48): 172.16.47.255. Hosts: 2^12 - 2 = 4,094.

#### Private, special and documentation ranges

Not every address is routable on the internet. Memorise these:

- Private (RFC 1918): 10.0.0.0/8, 172.16.0.0/12 (172.16.0.0 to 172.31.255.255), 192.168.0.0/16.
- Loopback: 127.0.0.0/8 (127.0.0.1 is "this machine").
- Link-local: 169.254.0.0/16. A Windows machine that gives itself 169.254.x.x did not get an answer from DHCP.
- Shared address space for carrier-grade NAT: 100.64.0.0/10. If your router's "internet" address is in here, you are behind your provider's NAT.
- Documentation ranges: 192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24. These are safe for examples, and for lab write-ups.

Common trap: 172.32.0.1 is public. The private block ends at 172.31.255.255 because /12 covers second-octet values 16 to 31.

Check them yourself: in Python, `ipaddress.ip_address('172.31.255.1').is_private` is True and `ipaddress.ip_address('172.32.0.1').is_private` is False.

#### Devices, MAC addresses, ARP and the gateway

A **switch** forwards frames inside one network using MAC addresses. A **router** forwards packets between networks using IP addresses. An **access point** bridges Wi-Fi to the wired network. A **firewall** permits or blocks traffic by rules. In small offices one box does several of these jobs.

A MAC address is a 48-bit hardware address (like 00:00:5e:00:53:01), used only on the local link. When host A wants to reach host B, it asks: is B on my subnet (same network bits under my mask)? If yes, A needs B's MAC, found with ARP ("who-has 192.0.2.1 tell 192.0.2.50"). If no, A sends the frame to its **default gateway's** MAC and the router takes over. So a wrong mask or gateway on a host breaks only the traffic that depends on that decision.

**Ports** identify the application at an endpoint: TCP or UDP port 443 for HTTPS, 53 for DNS, 22 for SSH. TCP sets up a connection with a three-step handshake: SYN, SYN-ACK, ACK. A closed port answers with a reset (RST); a firewall that drops silently gives no answer at all. That difference matters in Level 3.

#### The first five commands

Troubleshoot from the bottom up. On Windows (Linux equivalents in brackets):

1. `ipconfig /all` (`ip addr`): is there an address, a mask, a gateway, DNS servers? A 169.254 address means no DHCP.
2. `ping <gateway>`: Layer 1-3 on your own subnet.
3. `ping 8.8.8.8`: does traffic leave your network? (ICMP can be blocked; a failed ping is a clue, not proof.)
4. `nslookup example.com` (`dig example.com`): does name resolution work?
5. `Test-NetConnection example.com -Port 443` (`curl -I https://example.com`): is the port reachable?

**Worked example.** Gateway ping works, 8.8.8.8 ping works, `ping example.com` says "could not find host". The path is fine; names fail. It is DNS. Say that out loud before touching anything else. If instead the gateway ping fails, do not look at DNS at all; check cable, Wi-Fi, VLAN, address.

### Practice on your own

1. **Subnet by hand, then verify.** Work out 192.168.10.77/26 on paper, then check with a subnet calculator or `python3 -c "import ipaddress; n=ipaddress.ip_network('192.168.10.77/26', strict=False); print(n, n.netmask, n.broadcast_address, n.num_addresses-2)"`. Split 192.168.10.0/24 into /26 blocks and check each broadcast address.
2. **Your own network.** Log in to your home router and record the LAN range, mask, gateway, DHCP pool and connected devices. Find your own address with `ipconfig /all` or `ip addr`, and decide whether you are in the same subnet as the router.
3. **Run the five commands.** In order, on your own computer, write what each result tells you. Then turn Wi-Fi off, reconnect and repeat; note what changes.
4. **Name and port.** Look up a site you run (or a large public site) with `nslookup` or `dig`, then test port 443 with `Test-NetConnection` or `curl -I`. Write what a success rules out. Test one port only, on hosts you own or are allowed to test.

### Exercises

1. Write 10.0.0.1 and 192.168.1.1 in binary.
2. For 10.1.2.3/24, give the network, broadcast and host range.
3. For 192.168.5.130/25, give network, broadcast and usable hosts.
4. How many usable hosts does a /27 have, and what is its mask?
5. Is 172.20.5.9 private? Is 172.40.5.9?
6. Are 192.168.1.200 and 192.168.1.20 on the same network with mask 255.255.255.192? Explain.
7. For 172.16.45.200/20, give the network and broadcast.
8. A laptop has IP 169.254.88.12 and cannot browse. Name the likely cause, the layer, and your first two checks.

### Answers and hints

1. 10.0.0.1 = 00001010.00000000.00000000.00000001; 192.168.1.1 = 11000000.10101000.00000001.00000001.
2. Network 10.1.2.0, broadcast 10.1.2.255, hosts 10.1.2.1 to 10.1.2.254.
3. /25 block size 128; 130 is in 128 to 255. Network 192.168.5.128, broadcast 192.168.5.255, 126 usable.
4. 30 usable; mask 255.255.255.224.
5. 172.20.5.9 is private (second octet 16 to 31). 172.40.5.9 is public.
6. Block size 64. 200 is in the 192 block; 20 is in the 0 block. Different networks: they need a router to talk.
7. Network 172.16.32.0, broadcast 172.16.47.255.
8. The laptop self-assigned a link-local address because DHCP did not answer. Layer 2/3 boundary: check the link and the VLAN or Wi-Fi association, then whether a DHCP server (or relay) is reachable. Try `ipconfig /renew` after fixing the link.

### Checkpoint

Say aloud before moving on:

1. What are the seven OSI layers and where does a switch sit?
2. What is the difference between a frame and a packet?
3. How do you find the network address of 10.9.77.130/27?
4. Why are two addresses lost in every ordinary subnet?
5. What does a host do when the destination is not on its subnet?
6. What does a 169.254.x.x address tell you?
7. What are the three steps of the TCP handshake?
8. What is the order of your first five diagnostic commands, and why that order?

Common mistakes:

- Counting hosts as 2^n and forgetting the network and broadcast addresses.
- Rounding the network address up instead of down.
- Calling 172.x.x.x private without checking that the second octet is 16 to 31.
- Using a failed ping as proof of a dead path (ICMP is often blocked).
- Troubleshooting DNS when the gateway cannot even be reached.

## Level 2: Practitioner (intermediate)

### What you will be able to do

- You can plan a VLSM address scheme, place every subnet on its boundary, and prove there are no overlaps.
- You can summarise a set of routes into one prefix, and say when it is not possible without including extra space.
- You can configure access and trunk ports and explain what the 802.1Q tag does.
- You can predict which route a router picks using longest-prefix match.
- You can explain DHCP and DNS and read the key records.
- You can explain what NAT overload does and why it breaks some things.

### Core ideas

#### VLSM, overlaps and summarisation

Variable-length subnet masking gives each segment the size it needs. The method: add 2 to each host count, round up to a power of two, sort biggest first, and place each block at the next address that is a multiple of its own size.

**Worked example: 10.20.0.0/22** for 60 staff, 20 guest, 10 servers and two point-to-point links.

| Subnet | Hosts + 2 | Block | Network |
|---|---|---|---|
| Staff | 62 | 64 (/26) | 10.20.0.0/26 (0 to 63) |
| Guest | 22 | 32 (/27) | 10.20.0.64/27 (64 to 95) |
| Servers | 12 | 16 (/28) | 10.20.0.96/28 (96 to 111) |
| Link A | 4 | 4 (/30) | 10.20.0.112/30 |
| Link B | 4 | 4 (/30) | 10.20.0.116/30 |

That uses 120 of 1,024 addresses, leaving 904 free. Staff has 2 spare hosts, which is thin; growth matters, so add headroom (for example plan 80 staff, giving a /25). Biggest-first matters: each block must start on a multiple of its own size, so if you place the small links first, the /26 may not find a 64-aligned start and you waste addresses.

**Overlap check.** 10.0.0.0/16 and 10.0.5.0/24 overlap (the first contains the second). Overlaps cause the worst kind of fault: it works until you try to join two networks by VPN.

**Summarisation.** Four consecutive /24s that start on a multiple of four combine: 192.168.4.0/24 through 192.168.7.0/24 become 192.168.4.0/22. But 10.1.1.0/24 and 10.1.2.0/24 cannot form a /23 (a /23 must start on an even third octet: 10.1.0.0 or 10.1.2.0). The smallest single prefix covering both is 10.1.0.0/22, which also includes 10.1.0.0/24 and 10.1.3.0/24 that you may not own. Plan boundaries up front so you can summarise later.

#### VLANs and trunks

A VLAN splits one physical switch into several Layer 2 broadcast domains. Each VLAN normally maps to one subnet. Ports are **access** ports (one VLAN, untagged) or **trunk** ports (many VLANs, tagged with an IEEE 802.1Q tag). The tag adds 4 bytes including a 12-bit VLAN ID, so usable IDs are 1 to 4094. Traffic on the trunk's **native VLAN** is sent untagged; keep it the same on both ends and away from user VLANs.

```
vlan 10
 name STAFF
vlan 20
 name GUEST
interface GigabitEthernet0/1
 description Reception PC
 switchport mode access
 switchport access vlan 10
 spanning-tree portfast
interface GigabitEthernet0/24
 description UPLINK to CORE
 switchport mode trunk
 switchport trunk allowed vlan 10,20
 switchport trunk native vlan 999
```

Some older switches also need `switchport trunk encapsulation dot1q` first. Between VLANs, traffic needs a Layer 3 device: a router with sub-interfaces ("router on a stick") or a Layer 3 switch with a VLAN interface for each. Reviewers routinely flag trunks with no allowed-VLAN list and access ports left in VLAN 1; avoid both from the start.

#### Routing tables and longest-prefix match

A router forwards by finding the **most specific** matching route (longest prefix), not the first or the largest. A connected network has administrative distance 0, a static route 1, eBGP 20, OSPF 110, RIP 120; lower is preferred when two sources offer the same prefix.

**Worked example.** Table: 10.20.0.0/16 via A, 10.20.4.0/22 via B, 0.0.0.0/0 via C. For destination 10.20.5.9: the /22 covers 10.20.4.0 to 10.20.7.255, so it matches; it is longer than the /16, so the packet goes via B. For 10.20.9.9 it goes via A (the /22 does not cover it). For 8.8.8.8 only the default route matches, so via C.

A static route on Cisco IOS: `ip route 10.30.0.0 255.255.0.0 192.0.2.2` ("to reach 10.30.0.0/16, send to 192.0.2.2"). A default route is `ip route 0.0.0.0 0.0.0.0 192.0.2.1`. Static routes are right for small, stable networks and stub sites; they do not notice when the next hop dies unless you add tracking. Verify with `show ip route`. Remember the **return path**: ping often fails because the far end has no route back.

#### Switching and spanning tree

A switch learns by reading source MACs: it records "this MAC is on this port". For a destination it does not know (unknown unicast), or for broadcasts, it floods out all ports in the VLAN. `show mac address-table` shows what it learned.

If switches form a loop, flooded frames circulate forever (a broadcast storm) and the network collapses within seconds, because Ethernet frames have no hop limit. **Spanning Tree Protocol** prevents this by blocking redundant ports. The switches elect a **root bridge**: the lowest bridge ID wins, which is priority (default 32768) then MAC address. Each other switch picks its best path to the root; the rest are blocked. Modern switches use Rapid STP (802.1w), which converges in seconds. Set the root deliberately (`spanning-tree vlan 10 priority 4096` on your core) or a random old access switch may win. Put `portfast` on edge ports, and BPDU guard so a rogue switch shuts the port rather than joining the tree. Use `show spanning-tree` to see root, roles and states.

#### DHCP and DNS

**DHCP** hands out addresses by a four-step exchange (DORA): Discover (client broadcast from 0.0.0.0), Offer, Request, Acknowledge, over UDP 67 (server) and 68 (client). The lease carries address, mask, gateway, DNS servers and lease time. Broadcasts do not cross routers, so a DHCP **relay** (`ip helper-address <server>` on the VLAN interface) forwards them. Symptom of an exhausted pool: new devices get 169.254 addresses while old ones work. Reserve static addresses outside the pool (for printers, servers).

**DNS** maps names to data. Common records: A (IPv4), AAAA (IPv6), CNAME (alias), MX (mail), NS (zone servers), TXT (verification, SPF), PTR (reverse). Each record has a TTL: how long resolvers may cache it, so a change may take that long to appear everywhere. Port 53, UDP mostly, TCP for large answers.

```
dig example.com A +short
dig @8.8.8.8 example.com MX
dig -x 192.0.2.1
nslookup -type=TXT example.com
```

Query each record type separately; a plain lookup returns only addresses. Comparing your resolver with a public one (`dig @8.8.8.8`) tells you whether the fault is your resolver or the zone itself.

#### NAT and PAT

Private addresses cannot be routed on the internet, so the edge router rewrites them. **PAT** (NAT overload) maps many inside addresses to one outside address by rewriting the source port too, and keeps a translation table of each flow.

```
interface GigabitEthernet0/0
 ip nat outside
interface GigabitEthernet0/1
 ip nat inside
access-list 1 permit 10.20.0.0 0.0.3.255
ip nat inside source list 1 interface GigabitEthernet0/0 overload
```

The wildcard 0.0.3.255 matches 10.20.0.0/22. For inbound access, a static mapping forwards one port: `ip nat inside source static tcp 10.20.0.100 443 192.0.2.2 443`. NAT is not a security feature (a stateful firewall is), and it breaks things that embed addresses in payloads, causes trouble for peer-to-peer and VPNs, and times out idle entries, which looks like "the session drops after 5 minutes". IPv6 largely removes the need for it.

### Practice on your own

1. **VLSM.** In a spreadsheet, plan 10.20.0.0/22 for 60, 20, 10, 2 and 2 hosts and match the table above. Check it with Python: `ipaddress.ip_network("10.20.0.64/27")`. Then try 600 staff and explain why it cannot fit.
2. **Overlaps and summaries.** Python's `ipaddress.collapse_addresses` merges networks: it turns 192.168.4.0/24 to 192.168.7.0/24 into one /22 and leaves 10.1.1.0/24 and 10.1.2.0/24 separate. `a.overlaps(b)` tests overlap. Predict each result before running it.
3. **VLANs in a simulator.** In Packet Tracer, GNS3 or EVE-NG, build two switches, VLANs 10 and 20, a trunk and router-on-a-stick. Verify with `show vlan brief`, `show interfaces trunk` and pings. Then break each piece on purpose and note the symptom.
4. **Home router and DHCP.** Log in to your home router. Record the LAN range, DHCP pool and leases. Run `dig` against the router and against 8.8.8.8 and compare.

### Exercises

1. Plan 192.168.50.0/24 for: Sales 50 hosts, Ops 25, Printers 10, one link of 2. Give each network and mask.
2. Do 10.0.8.0/24 and 10.0.8.128/25 overlap? Do 10.0.8.0/25 and 10.0.8.128/25?
3. Summarise 172.16.8.0/24, 172.16.9.0/24, 172.16.10.0/24, 172.16.11.0/24.
4. Which route wins for 10.20.6.7 given 10.20.0.0/16 via A and 10.20.4.0/22 via B and 10.20.6.0/24 via C?
5. A VLAN 30 user cannot reach VLAN 10. Both access ports are correct. List the three things you would check.
6. A trunk has no allowed list and carries every VLAN. Why does that matter, and what is the fix?
7. New phones get 169.254 addresses, old ones are fine. What is the likely cause and the quickest evidence?
8. A host on 10.20.0.64/27 has gateway 10.20.0.1. Is the config valid?

### Answers and hints

1. Sales 50+2=52 so /26: 192.168.50.0/26. Ops 27 so /27: 192.168.50.64/27. Printers 12 so /28: 192.168.50.96/28. Link /30: 192.168.50.112/30.
2. Yes, the /24 contains the /25. No; they are adjacent halves.
3. The four /24s from third octet 8 to 11 start on a multiple of four: 172.16.8.0/22.
4. Via C (/24 is the most specific that contains 10.20.6.7).
5. Is there a Layer 3 interface or route between the VLANs? Does the trunk allow both VLANs? Does an ACL or firewall block it? Also check the hosts' gateways.
6. Any VLAN may cross the link, widening the broadcast and attack surface. Add `switchport trunk allowed vlan` with only what is needed.
7. DHCP pool exhaustion, or the phone VLAN has no relay. Check the lease table and the `ip helper-address` on the VLAN interface.
8. No. The subnet is .64 to .95; 10.20.0.1 is outside it, so the gateway is not on the host's own subnet. The gateway should be inside, such as 10.20.0.65.

### Checkpoint

1. Why sort biggest first when planning VLSM?
2. How do you decide whether two prefixes overlap?
3. What does a trunk's native VLAN do?
4. State longest-prefix match in one sentence.
5. Why does spanning tree exist and what happens without it?
6. Walk through DORA.
7. What does PAT change in a packet?
8. Why can a DNS change take hours to show up?

Common mistakes:

- Forgetting headroom and building subnets that are full on day one.
- Letting an access switch win the spanning-tree root election by default.
- Allowing all VLANs on every trunk.
- Putting a gateway outside the host's own subnet.
- Forgetting the return route when a static route "does not work".
- Calling NAT a firewall.

## Level 3: Advanced

### What you will be able to do

- You can explain how OSPF and BGP differ and write a basic OSPF configuration.
- You can choose Wi-Fi channels and read signal strength sensibly.
- You can write a firewall or ACL policy with correct order and an explicit default.
- You can calculate transfer times and the TCP window limit on a long link.
- You can read a `tcpdump -nn` capture and separate scan-like, monitoring and broken-client patterns.

### Core ideas

#### Dynamic routing: OSPF and BGP

Static routes do not scale. **OSPF** is a link-state interior protocol: every router floods descriptions of its links, builds the same map, and runs shortest-path-first. Routers are grouped in areas, with area 0 the backbone. Cost defaults to a reference bandwidth of 100 Mbps divided by link speed (minimum 1), which makes 100 Mbps and 10 Gbps links look the same; set `auto-cost reference-bandwidth` consistently on all routers. Hellos default to every 10 seconds with a 40-second dead timer on Ethernet.

```
router ospf 1
 router-id 1.1.1.1
 network 10.20.0.0 0.0.3.255 area 0
 passive-interface GigabitEthernet0/1
```

`passive-interface` advertises the user-facing network but forms no neighbours there. Check `show ip ospf neighbor` (want FULL) and `show ip route ospf`. **BGP** (TCP 179) connects separate organisations (autonomous systems). It is policy-driven, not speed-driven: you choose what to announce and accept. eBGP runs between ASes, iBGP within one. Private AS numbers are 64512 to 65534. Most engineers meet BGP only at the internet edge; learn the idea and build it in a lab, not on production.

#### Wireless

Wi-Fi is a shared, half-duplex medium: devices on a channel take turns, so airtime, not the headline speed, is the limit. On 2.4 GHz, only channels 1, 6 and 11 (20 MHz wide, in the US) do not overlap; use those and nothing else. 5 GHz has many more channels, some needing radar detection (DFS); 6 GHz arrived with Wi-Fi 6E. Standards: 802.11n is Wi-Fi 4, ac is Wi-Fi 5, ax is Wi-Fi 6, be is Wi-Fi 7.

Signal strength is in dBm, a logarithmic scale where 0 dBm is 1 milliwatt, so -30 dBm is a microwatt. Every 3 dB is double or half the power, every 10 dB is ten times. Rough guidance: around -67 dBm or stronger for reliable general use; weaker than about -80 dBm is trouble. Check the vendor's design guide; it varies. Use WPA3 or WPA2 with a strong key, or 802.1X for staff; keep guests on their own VLAN. `netsh wlan show interfaces` shows your signal, channel and rate.

#### Firewalls and ACLs

A **stateful** firewall tracks connections: allow the outbound request and the reply returns automatically. Rules are checked top to bottom and the first match wins, so order matters. End with an explicit deny and logging. Cisco ACLs end with an implicit "deny ip any any".

**Worked example.** Guests (10.20.0.64/27) may use the internet and one DNS server (10.20.0.100) but nothing else internal:

```
ip access-list extended GUEST-IN
 permit udp 10.20.0.64 0.0.0.31 host 10.20.0.100 eq 53
 permit tcp 10.20.0.64 0.0.0.31 host 10.20.0.100 eq 53
 deny   ip  10.20.0.64 0.0.0.31 10.0.0.0 0.255.255.255
 deny   ip  10.20.0.64 0.0.0.31 172.16.0.0 0.15.255.255
 deny   ip  10.20.0.64 0.0.0.31 192.168.0.0 0.0.255.255
 permit ip  10.20.0.64 0.0.0.31 any
```

Applied inbound on the guest VLAN interface (`ip access-group GUEST-IN in`). The DNS lines must come before the denies; swap them and name lookups break. Test each line, not just the last. Prefer least privilege: permit the minimum for servers and block the rest. Never expose RDP (3389), SMB (445) or database ports to the internet.

#### Throughput, latency and the TCP window

Bandwidth is how much per second; latency is how long one trip takes. TCP can have only a window of unacknowledged data in flight, so throughput is at most window divided by round-trip time.

**Worked example.** Copy 200 GB over 100 Mbps at 85% efficiency: bits = 200 x 8 x 10^9 = 1.6 x 10^12; effective rate 85 Mbps; time = 1.6 x 10^12 / 8.5 x 10^7 = about 18,824 seconds, or 5.2 hours. Now a 1 Gbps link with 80 ms round trip: the bandwidth-delay product is 1,000,000,000 / 8 x 0.08 = 10,000,000 bytes (about 9,766 KB) in flight. With a fixed 64 KB window the ceiling is 64 x 1024 x 8 / 0.08 = about 6.55 Mbps, hence a gigabit link that feels like six. Fixes: TCP window scaling (on by default in modern systems), parallel streams, or a closer server. Test real throughput with iperf3 between machines you control. State your assumptions (efficiency, units, window) whenever you quote a figure.

#### Reading a packet capture

Capture with tcpdump (`sudo tcpdump -nn -i eth0 -w out.pcap`, on networks you own) or Wireshark, then read patterns. The `-nn` flag stops name and port lookups so you see raw numbers. Learn these shapes:

- Healthy TCP: `[S]`, `[S.]`, `[.]` (SYN, SYN-ACK, ACK), then `[P.]` data.
- Closed port: SYN answered by `[R.]` (reset). Filtered port: SYN, no reply at all.
- Scan-like: one source sends SYNs to many ports or hosts in milliseconds; a simple rule such as five or more ports is a reasonable alert. A monitoring tool or a broken client can look the same, so check whether the source is yours.
- Many resets or retransmissions point at a service that is down or a path dropping packets.

Picture a capture in which 203.0.113.9 sends a SYN to each of ports 22, 23, 80, 443, 3389 and 3306 on 192.0.2.50 within a millisecond, resets come back for 22 and 23, and the others get no reply. One source, six ports, milliseconds apart: that is scan-shaped. It is still a lead; your job is to ask whose address that is and what the target logged.

### Practice on your own

1. **Throughput.** Use a spreadsheet to confirm 200 GB at 100 Mbps and 85% is about 5.2 hours, then at 50%. Between two VMs you own, run `iperf3` (a server on one, `iperf3 -c <server>` on the other) and compare with the theory. Try one stream and then `-P 4`.
2. **Capture.** On a VM you own, run `sudo tcpdump -nn -i eth0 -w out.pcap`, fetch a web page with `curl`, stop, and read the file with `tcpdump -nn -r out.pcap`. Identify the SYN, SYN-ACK, ACK and the first data packet.
3. **Closed versus filtered.** Between two lab VMs, connect to a closed port, then block another with a firewall DROP rule. Capture both and describe the difference. Probe only machines you own.
4. **Routing and ACLs.** In a simulator, connect three routers with OSPF, check `show ip ospf neighbor`, then add the guest ACL and test every line from a host.

### Exercises

1. How long does 50 GB take over 1 Gbps at 90% efficiency?
2. What is the BDP of 100 Mbps with 40 ms RTT?
3. A 5 ms RTT link carries 64 KB windows. What is the ceiling throughput?
4. Which 2.4 GHz channels should three neighbouring access points use?
5. Write an ACL line permitting HTTPS from 10.20.0.0/26 to host 10.20.0.100.
6. A capture shows 40 SYNs from 198.51.100.7 to 40 different hosts on port 445, none answered. Give two explanations and the evidence for each.
7. OSPF neighbours sit in INIT or EXSTART. Name two causes you would check.
8. Why does `permit ip any any` early in a list defeat later rules?

### Answers and hints

1. 50 x 8 x 10^9 = 4 x 10^11 bits; 900 Mbps effective; about 444 seconds (7.4 minutes).
2. 100,000,000 / 8 x 0.04 = 500,000 bytes (about 488 KB).
3. 64 x 1024 x 8 / 0.005 = about 104.9 Mbps.
4. Channels 1, 6 and 11, one each.
5. `permit tcp 10.20.0.0 0.0.0.63 host 10.20.0.100 eq 443`.
6. A scan or a worm looking for SMB, or an inventory or monitoring tool. Evidence: is the source in your asset list, is it a scheduled time, what do the hosts' logs say? Block and investigate if unknown.
7. Mismatched MTU on the two interfaces is a classic EXSTART cause; also mismatched area, authentication or timers, or ACLs blocking OSPF (IP protocol 89).
8. First match wins, so everything after it is never evaluated.

### Checkpoint

1. How is OSPF different from BGP in purpose?
2. Why only channels 1, 6 and 11 on 2.4 GHz?
3. What does a stateful firewall remember?
4. State the window limit formula.
5. How do a closed port and a filtered port look different in a capture?
6. Why is a scan finding only a lead?
7. What does `passive-interface` do?
8. Why test with iperf3 rather than a download from a website?

Common mistakes:

- Treating a high signal bar as proof of a good Wi-Fi experience (airtime and interference decide).
- Putting a broad permit above specific denies.
- Mixing decimal and binary units (network gear uses decimal: 1 GB is 10^9 bytes).
- Declaring an intrusion from a single scan-like line.
- Forgetting that a link can have a high bandwidth and still be slow on one stream.

## Level 4: Expert and professional judgement

### What you will be able to do

- You can design monitoring that alerts on symptoms users feel and calculate utilisation from counters.
- You can automate a safe, reviewable config change and say why it is idempotent.
- You can choose between designs by naming the failure modes each one trades for.
- You can review another engineer's config, plan or change with specific, kind, evidence-based comments.
- You can state the ethical and legal limits of scanning and capture.

### Core ideas

#### Monitoring that earns its keep

Collect three kinds of data: **metrics** (SNMP, Prometheus), **logs** (syslog) and **flows** (NetFlow or IPFIX: who talked to whom, how much). Use SNMPv3; keep NTP synced so logs line up. Alert on what a user would notice (link down, loss, latency, saturated uplink, DHCP pool nearly empty, certificate expiring) and send everything else to a dashboard. Too many alerts teach people to ignore them.

**Worked example: utilisation from counters.** An interface counter rises by 3,750,000,000 octets in 300 seconds on a 1 Gbps link. Bits = 3.75 x 10^9 x 8 = 3 x 10^10; per second 10^8 = 100 Mbps; utilisation 10%. Use 64-bit counters (`ifHCInOctets`): a 32-bit counter wraps at 4,294,967,296 octets, which on a busy link happens in under a minute. A first graph can be as simple as Prometheus scraping one exporter.

#### Automation and change discipline

Typing into each box does not scale and leaves no record. Keep configs in version control, generate them from templates and data, and push them with Netmiko, NAPALM or Ansible. Good automation is **idempotent** (running it twice gives the same state), shows a diff first, changes one device or group at a time, backs up the running config beforehand, and has a tested rollback. Plain Python already helps with planning:

```python
import ipaddress
site = ipaddress.ip_network("10.20.0.0/22")
for n in site.subnets(new_prefix=24):
    print(n, n.num_addresses - 2)
```

This lists four /24s with 254 hosts each. Never put device passwords in scripts; read them from a secrets store or `getpass`. Pair every change with a ticket, a reviewer and a rollback step, because most outages follow a change.

#### Design trade-offs and failure modes

Every design is a trade. A flat Layer 2 network is simple but one loop or broadcast storm takes it all down. Routing at the access layer shrinks failure domains but costs more addresses and planning. Redundant gateways (HSRP or VRRP) remove a single point of failure but need testing. Know the classic failures: spanning-tree loops, duplex or MTU mismatches (a path MTU black hole looks like "small packets work, big transfers hang"), asymmetric routing through a stateful firewall, DNS or DHCP outages that look like "the network is down", overlapping subnets when merging via VPN, and expired certificates. For IPv6, a LAN is normally a /64 and a site commonly gets a /48, which is 65,536 /64s. Plan dual-stack deliberately.

#### Review, ethics and scale

When reviewing a design, ask: what fails first, how would we know, how do we undo it, who is affected, and what is undocumented? Say "I could not verify X" rather than guessing. Tools here are leads, not verdicts; a clean config review means only that those patterns did not match.

Scanning and capture touch other people's systems. Do it only on networks you own or with written scope; scanning without permission can be illegal and can take systems down. Captures may hold passwords and personal data: limit who sees them and delete them. Configs contain secrets; do not paste real ones into online tools. At team scale, favour standards (naming, address plans, templates), a single source of truth, runbooks, and blameless post-incident reviews.

### Practice on your own

1. **Plan.** In a spreadsheet or with Python's `ipaddress` module, plan a three-site network from 10.0.0.0/16 (each site a /20), check for overlaps and summarise each site to a single route.
2. **Review.** Take a config from your own lab (or a colleague's, with permission) and review it as a senior would: write ranked, kind, specific comments against a checklist you wrote.
3. **Monitor.** In a VM, install Prometheus and Grafana or Zabbix and graph a router or VM interface. Compute utilisation by hand from two counter readings and compare it with the graph.
4. **Automate.** Against a simulator, push a VLAN change with Netmiko or Ansible. Run it twice to prove it is idempotent, and write the rollback.

### Exercises

1. Utilisation: 900,000,000 octets in 60 s on a 100 Mbps link?
2. Why alert on loss and latency rather than only CPU?
3. Give two reasons a Python script that adds a VLAN should check the device first.
4. Summarise 10.8.0.0/24 to 10.8.15.0/24 into one prefix.
5. A file transfer between sites hangs after the first few KB, but pings work. First suspicion?
6. A colleague asks you to "just scan the neighbour's Wi-Fi". What do you say?

### Answers and hints

1. 900,000,000 x 8 / 60 = 120 Mbps, which is 120% of 100 Mbps: impossible, so check the counter, the interval or the link speed.
2. They are what users feel; CPU can be high with no impact or low during an outage.
3. Idempotence (do not add a VLAN that exists) and safety (confirm you are on the right device and have a backup).
4. Sixteen /24s from 0 to 15 fit exactly: 10.8.0.0/20.
5. MTU or path MTU discovery problem (for example a VPN or tunnel); test with `ping -f -l 1472` on Windows or `ping -M do -s 1472` on Linux.
6. No: written permission is required, and it is not your network.

### Checkpoint

1. What do you alert on, and what goes only on a dashboard?
2. Why 64-bit counters?
3. What makes automation idempotent?
4. Name three failure modes of a flat network.
5. What do you say when a tool finds nothing?
6. What makes a change reviewable?
7. When may you scan or capture?
8. What goes in a blameless post-incident review?

Common mistakes:

- Alerting on everything until nobody reads alerts.
- Automating a bad process faster.
- Changing production with no rollback.
- Treating a lead as a verdict, in either direction.
- Leaving real credentials in configs, scripts and captures.

## Capstone projects

### 1. The small office

**Brief.** Design the network for an office of 60 staff, 20 guest Wi-Fi devices and 10 servers, plus two point-to-point links, out of 10.20.0.0/22. **Deliverables:** address plan with VLAN IDs and headroom, an overlap check, a summary route, a diagram (hand-drawn is fine) and a guest ACL. **Rubric (1 to 4 each):** every subnet fits its hosts with headroom; no overlaps; boundaries correct; guests isolated; every assumption written down.

### 2. Break it and fix it

**Brief.** In a free lab (Packet Tracer, GNS3 or EVE-NG), build two VLANs, a router and a DHCP relay. Introduce five faults (wrong VLAN, missing trunk VLAN, bad gateway, missing return route, closed ACL line) and document the diagnosis of each by layer. **Deliverables:** lab files, fault log with commands and outputs, one-page runbook "the internet is down". **Rubric:** method visible (bottom up); one change at a time; evidence for each conclusion; undo steps; the runbook is usable by someone else.

### 3. The network handbook

**Brief.** Produce an operating handbook for an imaginary 3-site company. **Deliverables:** IPv4 and IPv6 plan, summarisation, standard switch and router config templates, monitoring plan with alerts, change process, a hardening review of your template (using a written checklist of your own) and a failure-mode table. **Rubric:** plan scales; templates pass your own review; alerts are symptom based; failure modes are named with detection and recovery; limits of your tools are stated honestly.

## Tools reference

| Tool | What it is for | When you outgrow it |
|---|---|---|
| Subnet calculator (any, or Python's `ipaddress`) | Exact subnet, split, VLSM, overlap and summary checks | Large designs and IPAM systems with ownership data |
| Config checklist or linter | Pattern checks on a config | Real compliance audits (CIS benchmarks, vendor tools) |
| `dig`, `nslookup`, `curl`, `Test-NetConnection` | DNS and one-port reachability tests | Monitoring probes |
| Wireshark, tcpdump | Capture and analyse packets (own networks only) | Flow and probe systems at scale |
| Packet Tracer, GNS3, EVE-NG | Virtual labs for routing, VLANs and trunks | Real hardware or vendor virtual images |
| iperf3 | Real throughput between two machines you control | Continuous synthetic monitoring |
| Nmap | Host and service discovery (written permission only) | Vulnerability management platforms |
| Zabbix, Nagios, PRTG, Prometheus + Grafana | Monitoring and alerting | Observability platforms with flow and log correlation |
| Ansible, Netmiko, NAPALM | Automated config change | Full network source-of-truth and CI pipelines |
| pfSense, OPNsense | A free firewall and router in a VM | Vendor firewalls with support and clustering |

## Glossary

- **ACL**: an ordered list of permit and deny rules; first match wins.
- **ARP**: finds the MAC address for an IPv4 address on the local link.
- **AS (autonomous system)**: a network under one routing policy, identified by a number.
- **BDP**: bandwidth-delay product, the bytes in flight on a full link.
- **BGP**: the protocol that exchanges routes between autonomous systems.
- **Broadcast domain**: the set of devices that receive each other's Layer 2 broadcasts; a VLAN is one.
- **CIDR**: prefix-length notation such as /26 that replaced fixed classes.
- **DHCP**: automatic address assignment (Discover, Offer, Request, Acknowledge).
- **DNS**: the system mapping names to records.
- **Default gateway**: the router a host uses for off-subnet traffic.
- **Frame**: a Layer 2 unit; a **packet** is Layer 3.
- **Idempotent**: safe to run repeatedly with the same result.
- **MAC address**: a 48-bit link-layer address.
- **MTU**: the largest packet a link carries (1,500 bytes on standard Ethernet).
- **NAT/PAT**: rewriting addresses (and ports) at a network edge.
- **OSPF**: a link-state interior routing protocol.
- **Prefix length**: the number of network bits in an address.
- **RTT**: round-trip time.
- **STP**: spanning tree, which blocks redundant Layer 2 links to prevent loops.
- **Stateful firewall**: tracks connections so replies are allowed automatically.
- **Trunk**: a link carrying many VLANs using 802.1Q tags.
- **VLAN**: a virtual Layer 2 segment on shared switches.
- **VLSM**: variable-length subnet masks; sizing each subnet to its need.
- **Wildcard mask**: the inverse of a netmask, used in ACLs and OSPF.

## Career notes

**Roles it leads to.** Network technician, network administrator, network engineer, network security engineer, wireless engineer, NOC (network operations centre) analyst, site reliability or infrastructure engineer, and network automation engineer. Cloud networking is a natural next step.

**How to show your skill.** Publish your capstones: an address plan, a lab write-up with fault logs, a runbook and a handbook. Employers trust evidence of method more than a list of tools. Be able to subnet on a whiteboard, explain a trace, and describe a change you would make safely.

**What to learn next.** Real routing labs (OSPF, BGP), IPv6 in depth, firewalls and VPNs, wireless site surveys, monitoring and flow analysis, Python and Ansible, then cloud networking (virtual networks, routing and security groups). Vendor and neutral networking certifications exist and employers recognise them; check the current exam objectives of any you consider, and treat them as a structure for study, not a replacement for lab hours.

## Match it in the app

Everything above works with no software beyond a terminal. If you also have the practice dashboard, its Network panel (`NetPanel`, logic in `services/netlab.py`, endpoints in `routers/net.py`, notes in `docs/NETWORK_ENGINEERING.md`) matches the levels as follows. Work in the Practice workspace and do the arithmetic by hand first.

**Level 1.** Open the Subnet and VLSM tab and use the Subnet calculator: enter 192.168.10.77/26 and compare network, broadcast, host range, usable hosts, netmask, wildcard and binary mask. Use Split to cut a /24 into /26 blocks. Try 172.31.255.1/32 and 172.32.0.1/32 and watch the scope change from private to global. The Reference tab holds the OSI table with typical faults, the troubleshooting method, a port table and command lists for Windows, Linux and Cisco. On the DNS and reachability tab, look up a name and test one TCP port on a public host; you should see addresses with lookup time, then a state of open, closed, or filtered or no answer.

**Level 2.** In the VLSM planner enter base 10.20.0.0/22 and the lines `Staff,60`, `Guest,20`, `Servers,10`, `LinkA,2`, `LinkB,2`; you should get the table in this part and 904 free addresses. Change Staff to 600 and read the "too small" error. In Overlaps and route summary, enter 10.0.0.0/16 with 10.0.5.0/24 to see "a contains b", and 192.168.4.0/24 to 192.168.7.0/24 to see one /22. The Config review tab accepts a pasted Cisco-style config (a deliberately flawed sample is built in): fix every high finding and explain each in a sentence.

**Level 3.** The Calculators tab has the transfer-time calculator (200 GB, 100 Mbps, 85% gives about 5.2 hours) and the bandwidth-delay and window calculator (1000 Mbps, 80 ms, 64 KB shows the window as the limit, about 6.55 Mbps). The Packet capture tab parses pasted `tcpdump -nn` text: protocols, handshakes seen, top sources and destination ports, and scan-like findings (one source sending SYNs to five or more ports). Use the built-in sample, write a three-sentence verdict, then delete the SYN lines and see the finding disappear.

**Level 4.** Use the planner and overlap check for the three-site capstone, the Config review as a peer-review warm-up, and the capture reader to practise writing an incident note. The app's own Ops page shows request counts and timings, a first taste of monitoring.

**What the app does not cover.** It builds no real network: nothing there configures a switch or router, and VLANs, trunks, spanning tree, OSPF, BGP, NAT, ACL behaviour, wireless and DHCP are not simulated; use a simulator or lab for those. IPv6 appears in the subnet calculator but hosts are not counted, and the VLSM planner is IPv4 only. The config review is pattern checks on text, not a CIS audit, and "no findings" means only that those patterns did not match. The capture reader reads text you paste and never captures; findings are leads, not verdicts. DNS checks return A and AAAA records only, and port checks are one port per request on public hosts only, limited to 12 a minute: a diagnostic, not a scanner. Scanners, live capture, monitoring systems, automation tools and cloud networking are explained but not built. Nothing here replaces a lab with real or virtual gear.
