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

## Tools you will meet that are NOT embedded
- **Active Directory, Group Policy, Windows Server**: practise in a VM (a free evaluation Windows Server). Entra ID and Intune are cloud services and are out of scope here.
- **osTicket, GLPI, Snipe-IT**: free helpdesk and asset systems; the trackers here are the same ideas at personal scale.
- **PowerShell, Bash, Python**: the scripts that save hours. Start with the cheat sheet.
- **VirtualBox, Hyper-V, Proxmox**: safe places to break things.
- **Remote tools (RDP, SSH, TeamViewer-style)**, **backup software (Veeam, restic, rsync)**: learn the 3-2-1 rule first.
- **Monitoring (Zabbix, Nagios)**: alerts before users call.

## Practice ideas
- Log five realistic tickets, resolve them, and read the mean time to resolve.
- Enter your own computers into the inventory. Which warranties end this year?
- Paste the sample event log. Which finding would you check first, and what would you do?
- Work out when a 1 TB disk at 70% used with 25 GB/month growth hits 80%, and decide when to order storage.
- Run the onboarding checklist for an imaginary new hire, then the offboarding one for a leaver.

## Limits
These are practice trackers and readers. Production support needs the real systems, an approvals process and your employer's policies.
