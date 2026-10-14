# Security frameworks, network design and glossary

From the IBM/Coursera Cybersecurity Fundamentals reading, "Designing a Basic Network Structure" and "Glossary: Networking Fundamentals".

## Built
- **Cybersecurity > Principles and NIST CSF**: the five principles and the obscurity anti-pattern with a red flag and a question each; a *principles check* (keyword match on a described design); a *CIA classifier*; a *NIST CSF 2.0 self-check* (Govern, Identify, Protect, Detect, Respond, Recover) that returns scores per function and the next actions.
- **Network > Network design**: planner (groups, growth, sites, redundancy, guest Wi-Fi, remote access -> VLSM address plan, topology, devices, zones, risks), the nine design steps, a searchable glossary with corrections, and a default-port table.
- IT support cheat sheets: *Linux services and run levels* and *Microsoft Defender Antivirus (PowerShell)*.
- Steps `sec-principles`, `sec-csf`, `net-design`, `net-glossary`, with 20 questions, four agent notes and seven tool-map rows.

## Already in the app, so skipped
Windows, Linux and macOS commands, Kerberos, virtualization, cron, firewalls, OSI, password managers, SSO, VPN, RBAC, separation of duties (earlier lessons).

## Not built
Commercial design and monitoring suites (IBM Netcool, SevOne, Cloud Pak, SolarWinds, NetBrain, Cisco Network Assistant), Visio, MDM/Intune, blockchain nodes, a real packet simulator. Links are in the Tool map.

## Mistakes in the sources (all in `SLIPS` of `sec_frame.py` and `net_design.py`)
NIST CSF put incident plans under Identify and omitted Govern; obscurity counted as a sixth principle; SYN flood "crashes" the server; garbled rainbow-table description; SysV run levels presented as current; Quick Scan described as a full scan; 65,536 ports and "ports never change"; SMB on 137-139; socket definition; 802.20/802.22 as cellular standards; "Crypto Classic" filler; ARP as a troubleshooting protocol; WMAN as 802.15; WISP as cellular; Telnet with no warning; the design steps list that skips logical design, security and testing and calls storage and monitoring products design tools.

## Limits
The principles check and CIA classifier match words. The design planner is a sizing sketch, not a vendor design or a site survey. The CSF self-check is your opinion, not an audit.
