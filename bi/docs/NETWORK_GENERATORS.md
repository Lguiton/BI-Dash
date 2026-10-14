# Network config generators, honeypot logs and the poster slips

Built from a set of posters on VLANs, trunks, router-on-a-stick, loopbacks, DHCP, routing protocols, network devices, cable categories, Cowrie honeypot logs, passwords and a few IT topics.

## Network track > Config generators
| Part | What it does | Limit |
|---|---|---|
| VLAN and router-on-a-stick | Builds the switch config (VLANs, access ports, trunk, allowed list, native VLAN) and the router subinterfaces, or the Layer 3 switch (SVI) form, plus an optional loopback. Validates ids (1 to 4094, not 1002 to 1005), overlapping subnets, gateways, duplicate ports, and warns about native VLAN 1. | Text only. Nothing connects to a device. |
| Trunk checker | Reads two pasted switch configs and reports mode, native VLAN, allowed VLAN and missing-VLAN faults. | Pasted text; doesn't see live state or spanning tree. |
| Route selection | Longest prefix first, then administrative distance, then metric, with the steps shown. | Models selection only. No protocol runs. |
| Cable chooser | Cat 5e to Cat 8 pick by speed and run length, with the standards caveats. | Twisted pair only. |
| Reference | Devices by layer, DHCP DORA addressing, OSPF/EIGRP/BGP/RIP comparison, administrative distances, loopback facts. | Summaries. |

## Cybersecurity track > Honeypot logs
Reads pasted Cowrie logs (cowrie.json lines or cowrie.log text): counts, top IPs, usernames, passwords, commands classified as recon, download, execute, persistence, destructive or miner, defanged URLs and a per-hour count. Nothing is fetched, resolved or run. Not built: Cowrie, Grafana, ELK, SIEM alerts, IP geolocation.

## IT track additions
Reference topics in IT fundamentals: connectors (audio plugs, cable categories), disks (MBR, GPT, fdisk, parted), desktop apps (Linux browsers, PowerPoint keys). Checklists: an app blocked by Windows Firewall, and a personal digital-footprint audit. Cheat groups: disks and partitions, Windows Firewall.

## Slips found in the source posters
1. Loopback poster: "Success rate is 10% percent (5/5)" should be 100 percent.
2. Loopback poster: the two routers have no route to each other's loopback, so the ping example would fail as shown.
3. VLAN poster and trunk lab: `switchport trunk encapsulation dot1q` is rejected by switches that only support 802.1Q (for example the 2960); older Layer 3 switches require it.
4. Router-on-a-stick poster: masks are cut off at the image edge; no mention of the native VLAN.
5. DHCP poster: key points call Discover, Request and Acknowledge broadcasts while the table shows the Offer to 255.255.255.255 as well. Offer and Acknowledge are usually unicast unless the client sets the broadcast flag.
6. OSPF/EIGRP/BGP poster: "EIGRP: Cisco proprietary" is dated (RFC 7868, 2016).
7. Cat 6 vs Cat 7 poster: omits Cat 6a; Cat 7 is not a TIA category and its GG45 connector isn't RJ45; "future-proofing" oversells it.
8. Network devices poster: a modem is described only as a digital/analog converter; most home boxes combine modem, router, switch and access point.
9. Audio jack poster: shows OMTP order; most modern devices use CTIA. Wire colours are not standard.
10. fdisk vs parted poster: "fdisk supports only MBR" is out of date; the real difference is when changes are written (fdisk on w, parted at once). Blurred edit marks remain in the image.
11. Firewall poster: ticks all three profiles including Public; a Block rule overrides Allow, so remove the block.
12. Linux browsers poster: Falkon is Chromium-based (Qt WebEngine) despite "very low RAM".
13. PowerPoint poster: duplicate slide is Ctrl+D, not Ctrl+Shift+D; the zoom keys Ctrl+Plus, Ctrl+Minus and Ctrl+Alt+O aren't in the Microsoft-style lists checked.
14. Password length poster: the entropy formula is applied to a four-word passphrase as if its 28 characters were random (131 bits); the real figure is about 51.7 bits (four words from 7,776), still strong. "P@ssword!" falls to a pattern, not to its length. The 8, 16 and 24 character counts don't follow one pool size. "Less reliance on password managers" is the wrong advice.
15. Digital footprint poster: "permanent" is overstated (much can be removed); items 2 and 7 are the same check; deactivating an account is not deleting it.
16. Honeypot posters: the "log/*.txt" files are ones you create, not Cowrie logs; `cowriectl` is not Cowrie's control script (it is `bin/cowrie`); "real attack data" contradicts "isolated lab only"; 185.199.108.23 sits in GitHub's range; poster 08's printed output doesn't match its code.
17. "30 ChatGPT secret codes": not codes. Each slash word is an ordinary style hint in a prompt.
18. The Cyveer, HighTech, Network Mentor, Networking with Israr and The Cyber Bite logos are the authors' branding; nothing from them is copied here.

## Skipped (already built)
Password strength checking and passphrase generation (Cybersecurity > Crypto labs).
