# IT Specialist (support and administration)

An IT specialist keeps people productive: fix the problem, protect the data, know what you own, and write it down so the next person can repeat it.

## The habits that matter
1. **Ask before you touch.** What changed? When did it last work? Who else is affected?
2. **Cheapest explanation first.** Power, cable, restart, typo, expired password.
3. **One change at a time**, recorded.
4. **Confirm with the person**, then document the fix.
5. **Least privilege and a tested backup** beat any clever tool.

## What is built in
| Tab | What it does | Honest limit |
|---|---|---|
| Helpdesk | Tickets with a category checklist, timeline and an SLA clock | A personal tracker. No email intake, user portal or business hours. |
| Inventory | Assets with owner, serial, warranty and status; flags expiring warranties | You type it in; no discovery agent. |
| Event log reader | Reads a Windows Event Viewer export (CSV or text): counts known IDs, flags patterns | Only well-known IDs are named. Findings are leads. |
| Checklists | Onboard, offboard, new PC and outage checklists with ticks | Generic; adapt them to your organisation. |
| Capacity and RAID | Disk-full forecast, availability to downtime, RAID usable space | Straight-line growth; RAID is not a backup. |
| Cheat sheets | PowerShell, Active Directory, Linux and backup basics | Static; check a command before running it on a production machine. |
| Software guide | Ten categories of IT software with the March 2026 G2 and Capterra ratings from the NinjaOne SysAdmin Software Guide 2026; a stack coverage check, a weighted shortlist and an IT tool decision note | A snapshot from a vendor-published guide that ranks its own product. It does not install, discover or manage software. |

## Tools you will meet that are NOT embedded
- **Active Directory, Group Policy, Windows Server**: practise in a VM (a free evaluation Windows Server). Entra ID and Intune are cloud services and are out of scope here.
- **osTicket, GLPI, Snipe-IT**: free helpdesk and asset systems; the trackers here are the same ideas at personal scale.
- **PowerShell, Bash, Python**: the scripts that save hours. Start with the cheat sheet.
- **VirtualBox, Hyper-V, Proxmox**: safe places to break things.
- **Remote tools (RDP, SSH, TeamViewer-style)**, **backup software (Veeam, restic, rsync)**: learn the 3-2-1 rule first.
- **Monitoring (Zabbix, Nagios)**: alerts before users call.

## Choosing software
Ten categories cover most IT work: all-in-one management, endpoint monitoring (RMM and UEM), mobile device management, software and patch management, asset management, service desk, remote desktop, cloud backup, network monitoring and endpoint detection and response. Mark each as have it, planned, gap or not needed, then shortlist tools for one gap. Ratings are one input; trial two or three on test machines, check the cost, the contract terms and how to export your data, and write the decision down.

## Practice ideas
- Log five realistic tickets, resolve them, and read the mean time to resolve.
- Enter your own computers into the inventory. Which warranties end this year?
- Paste the sample event log. Which finding would you check first, and what would you do?
- Work out when a 1 TB disk at 70% used with 25 GB/month growth hits 80%, and decide when to order storage.
- Mark your stack in the Software guide, pick the biggest gap, rank three tools and write the decision note.
- Run the onboarding checklist for an imaginary new hire, then the offboarding one for a leaver.

## Limits
These are practice trackers and readers. Production support needs the real systems, an approvals process and your employer's policies.


## Reading your own event log
In Event Viewer open Windows Logs, Security, then Action, Save All Events As, and choose CSV. In the Event logs tab use **Open file…** (up to 25 MB, UTF-8 or UTF-16) or paste rows. Text copied straight from the Event Viewer list also works. .evtx files are binary and are not read.


## Virtualization (vSphere) tab

From a 10-step vSphere deployment infographic: the runbook (do, check, common mistakes for each step), a host and storage sizing calculator with an N+1 spare, a network plan checker (shared VLANs, overlapping subnets, VM traffic on the management VLAN, reserved VLAN ids), a cluster checker (names, mixed versions, uneven hosts, CPU models and EVC) and a **Virtualization plan** note.

- The infographic has three slips, corrected here: "VT-3" is VT-x, DRS is the Distributed Resource Scheduler, and vMotion and VM Network are both drawn on VLAN 20.
- ESXi and vCenter need bare metal (or nested virtualization) and a licence, so they cannot run in this app. It never connects to a host. Sizing is a planning estimate; measure real load.
- Practise with nested ESXi on a desktop hypervisor, Proxmox VE or KVM. VMware's licensing for free and personal use has changed more than once, so check the current terms.
