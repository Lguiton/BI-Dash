# IT fundamentals (IT Specialist track)

IT dashboard > **IT fundamentals**. Built from the IT Technician course material (hardware, networking, Windows and Linux, system administration). Everything is original text and exact arithmetic; nothing is run on your machine.

| Part | What it does | Limit |
|---|---|---|
| Practice shell | A simulated Linux terminal over a made-up file tree: ls, cd, mkdir, touch, cat, echo, cp, mv, rm, grep, wc, head, tail, sort, uniq, chmod, chown (with sudo), pipes and redirects. Permissions are enforced, so chmod really matters. 11 graded tasks, with hints and a working command if you are stuck. | A simulation: no network, no real files, no scripts, only the listed commands. It prepares you for real labs; it does not replace them. |
| Drills | Generated, server-graded questions in 11 kinds: binary and hex conversion, chmod both ways, who can do what, umask, logic gates, circuits, drive sizes. Scores kept per kind. | Questions are rebuilt from their id, so answers are never sent to the browser. |
| Number converter | Decimal, binary, hex and octal with the place-value working, up to 64 bits. | Whole numbers only. |
| Text encoding | Shows each character's code point and its UTF-8 bytes. | Up to 100 characters. |
| Logic gates | Truth tables for NOT, AND, OR, XOR, NAND, NOR, XNOR, and any expression of up to 4 inputs such as `(A AND B) OR NOT C`. | Own parser, no code is evaluated. |
| Storage units | Decimal vs binary units and why a drive shows less than its label. | Ignores formatting overhead. |
| Permissions | chmod octal to symbolic and back, setuid, setgid, sticky, umask effect, warnings for risky modes. | Calculates only; Windows uses ACLs. |
| IPv6 | Compress, expand, classify, and the /64 network. | Does not test reachability. |
| Command finder | 45 tasks with the Windows and Linux command and a caution where it matters. | Read before you run. |
| Reference | Connections, wireless, cellular and IoT, cloud, services, sysadmin practice, hardware. | Summaries. |

## Not built
The Qwiklabs-style labs (Dnsmasq DNS and DHCP, live shells), real hardware work, and the course's own graded quizzes.

## Slips found in the source
1. The sticky-bit example says `chmod 175`; it should be `1775` (or `1777`).
2. WPA2 is described as using a 256-bit key; it uses 128-bit AES (CCMP). WPA3 is not mentioned.
3. MAC filtering is offered as a barrier; it is trivial to bypass.
4. The storage table's "-2.4%, -4.9%..." are the binary excess over decimal; what you lose on screen is 2.3%, 4.6%, 6.9%, 9.1% (TB), 11.2% (PB).
5. USB colour-coding (blue, teal) is a convention, not a rule.

## Vendor review
A `Vendor review` template (Qualitative tools) and a `Run a vendor through its life cycle` checklist cover the pre-contract, delivery and post-contract phases. Onboarding and offboarding checklists already existed.
