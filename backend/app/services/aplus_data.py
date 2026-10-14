"""CompTIA A+ study content: the objective map, a practice question bank, symptom tables and reference tables.

Written as a study aid from the public exam-objective documents for Core 1 (220-1201) and Core 2 (220-1202), v2.0. The objective titles are
paraphrased and every question, symptom and table is written for this project. It is not affiliated with CompTIA and is not the exam: use
CompTIA's own objectives document and a practice exam as the final check. Items on the objective list can change; re-read the current version.
"""
from __future__ import annotations

EXAMS = {
    "1": {"code": "220-1201", "name": "Core 1", "questions": 90, "minutes": 90, "pass": "675 of 900",
          "domains": {"mobile": ("Mobile devices", 13), "networking": ("Networking", 23), "hardware": ("Hardware", 25),
                      "virt_cloud": ("Virtualization and cloud", 11), "troubleshooting": ("Hardware and network troubleshooting", 28)}},
    "2": {"code": "220-1202", "name": "Core 2", "questions": 90, "minutes": 90, "pass": "700 of 900",
          "domains": {"os": ("Operating systems", 28), "security": ("Security", 28), "sw_trouble": ("Software troubleshooting", 23), "ops": ("Operational procedures", 21)}},
}
METHOD = ["Identify the problem", "Establish a theory of probable cause (question the obvious)", "Test the theory to determine the cause",
          "Establish a plan of action and implement the solution", "Verify full system functionality and add preventive measures", "Document findings, actions and outcomes"]
# kind: tool = a working tool here, ref = reference table + questions, list = a checklist, find = the symptom finder, hands = needs real hardware or an OS to practise
OBJECTIVES = [
    ("1.1", "1", "mobile", "Monitor mobile hardware and choose replacement steps", "hands", "Mobile reference"),
    ("1.2", "1", "mobile", "Accessories and connection options for mobile devices", "ref", "Mobile reference"),
    ("1.3", "1", "mobile", "Mobile connectivity, MDM, app support and sync", "ref", "Mobile reference"),
    ("2.1", "1", "networking", "TCP and UDP ports, protocols and their purposes", "tool", "Port drill"),
    ("2.2", "1", "networking", "Wireless technologies: bands, channels, 802.11, NFC, RFID", "ref", "Network reference"),
    ("2.3", "1", "networking", "Services provided by networked hosts and appliances", "ref", "Network reference"),
    ("2.4", "1", "networking", "DNS records, spam controls, DHCP, VLAN and VPN", "tool", "DHCP scope, Mail records"),
    ("2.5", "1", "networking", "Common networking hardware", "ref", "Network reference"),
    ("2.6", "1", "networking", "Configure SOHO IP addressing", "tool", "IP check"),
    ("2.7", "1", "networking", "Internet connection types and network types", "ref", "Network reference"),
    ("2.8", "1", "networking", "Networking tools and their purposes", "ref", "Network reference"),
    ("3.1", "1", "hardware", "Display components and attributes", "tool", "Display calculator"),
    ("3.2", "1", "hardware", "Cable types, connectors and their purposes", "ref", "Cables reference"),
    ("3.3", "1", "hardware", "RAM characteristics", "ref", "Hardware reference"),
    ("3.4", "1", "hardware", "Storage devices and RAID", "tool", "RAID (Capacity tab)"),
    ("3.5", "1", "hardware", "Motherboards, CPUs, firmware settings and add-in cards", "ref", "Hardware reference"),
    ("3.6", "1", "hardware", "Install the appropriate power supply", "tool", "Power supply sizer"),
    ("3.7", "1", "hardware", "Deploy multifunction devices and printers", "ref", "Printers reference"),
    ("3.8", "1", "hardware", "Printer maintenance", "ref", "Printers reference"),
    ("4.1", "1", "virt_cloud", "Virtualization concepts", "ref", "Cloud reference; Virtualization tab"),
    ("4.2", "1", "virt_cloud", "Cloud computing concepts", "ref", "Cloud reference"),
    ("5.1", "1", "troubleshooting", "Troubleshoot motherboards, RAM, CPUs and power", "find", "Symptom finder"),
    ("5.2", "1", "troubleshooting", "Troubleshoot drive and RAID issues", "find", "Symptom finder"),
    ("5.3", "1", "troubleshooting", "Troubleshoot video, projector and display issues", "find", "Symptom finder"),
    ("5.4", "1", "troubleshooting", "Troubleshoot mobile device issues", "find", "Symptom finder"),
    ("5.5", "1", "troubleshooting", "Troubleshoot network issues", "find", "Symptom finder"),
    ("5.6", "1", "troubleshooting", "Troubleshoot printer issues", "find", "Symptom finder"),
    ("1.1", "2", "os", "Operating system types, filesystems and life cycle", "ref", "OS reference"),
    ("1.2", "2", "os", "OS installations and upgrades", "ref", "OS reference"),
    ("1.3", "2", "os", "Windows editions and upgrade paths", "ref", "OS reference"),
    ("1.4", "2", "os", "Windows features and tools", "ref", "Windows tools"),
    ("1.5", "2", "os", "Microsoft command-line tools", "ref", "Windows tools"),
    ("1.6", "2", "os", "Configure Windows settings", "ref", "Windows tools"),
    ("1.7", "2", "os", "Windows networking on a client", "ref", "OS reference"),
    ("1.8", "2", "os", "macOS features and tools", "hands", "OS reference"),
    ("1.9", "2", "os", "Linux client features and tools", "hands", "Linux commands"),
    ("1.10", "2", "os", "Install applications according to requirements", "ref", "OS reference"),
    ("1.11", "2", "os", "Cloud-based productivity tools", "ref", "OS reference"),
    ("2.1", "2", "security", "Security measures and their purposes", "ref", "Security reference"),
    ("2.2", "2", "security", "Windows security settings", "ref", "Security reference"),
    ("2.3", "2", "security", "Wireless security protocols and authentication", "ref", "Security reference"),
    ("2.4", "2", "security", "Malware types, detection, removal and prevention", "ref", "Security reference"),
    ("2.5", "2", "security", "Social engineering, threats and vulnerabilities", "ref", "Security reference"),
    ("2.6", "2", "security", "SOHO malware removal procedure", "list", "Checklists"),
    ("2.7", "2", "security", "Workstation security and hardening", "list", "Checklists"),
    ("2.8", "2", "security", "Securing mobile devices", "ref", "Security reference"),
    ("2.9", "2", "security", "Data destruction and disposal", "list", "Checklists"),
    ("2.10", "2", "security", "Secure SOHO wireless and wired networks", "list", "Checklists"),
    ("2.11", "2", "security", "Browser security settings", "ref", "Security reference"),
    ("3.1", "2", "sw_trouble", "Troubleshoot common Windows issues", "find", "Symptom finder"),
    ("3.2", "2", "sw_trouble", "Troubleshoot mobile OS and app issues", "find", "Symptom finder"),
    ("3.3", "2", "sw_trouble", "Troubleshoot mobile security issues", "find", "Symptom finder"),
    ("3.4", "2", "sw_trouble", "Troubleshoot PC security issues", "find", "Symptom finder"),
    ("4.1", "2", "ops", "Documentation, ticketing and asset management", "tool", "Helpdesk and Inventory tabs"),
    ("4.2", "2", "ops", "Change management", "list", "Checklists; Change request template"),
    ("4.3", "2", "ops", "Workstation backup and recovery", "tool", "Backup planner"),
    ("4.4", "2", "ops", "Safety procedures", "ref", "Operations reference"),
    ("4.5", "2", "ops", "Environmental impact and controls", "ref", "Operations reference"),
    ("4.6", "2", "ops", "Prohibited content, privacy, licensing and policy", "ref", "Operations reference"),
    ("4.7", "2", "ops", "Communication and professionalism", "ref", "Operations reference"),
    ("4.8", "2", "ops", "Scripting basics", "tool", "Script reviewer"),
    ("4.9", "2", "ops", "Remote access technologies", "ref", "Operations reference"),
    ("4.10", "2", "ops", "Artificial intelligence basics", "ref", "AI Engineering track"),
]
KIND_LABEL = {"tool": "Working tool", "ref": "Reference and questions", "list": "Checklist", "find": "Symptom finder", "hands": "Needs real hardware or an OS"}


def objectives() -> list[dict]:
    out = []
    for oid, ex, dom, title, kind, aid in OBJECTIVES:
        out.append({"id": f"{ex}:{oid}", "exam": ex, "number": oid, "domain": dom, "title": title, "kind": kind, "kind_label": KIND_LABEL[kind], "aid": aid})
    return out


# ------------------------------------------------------------------ practice questions: (objective, question, correct, [3 wrong], why)
def _q(obj, q, ok, bad, why):
    return {"obj": obj, "q": q, "ok": ok, "bad": bad, "why": why}


QUESTIONS = {
    ("1", "mobile"): [
        _q("1.1", "A tablet's case is bulging and the screen is lifting. What do you do first?", "Power it off, stop charging it, and have the battery replaced; do not puncture it", ["Charge it fully to reset the cell", "Press the screen back down", "Put it in a freezer"], "A swollen lithium battery is a fire risk. Stop using it, keep it away from heat and recycle it properly."),
        _q("1.2", "Which connection lets a phone share its cellular data with a laptop?", "Tethering or a mobile hotspot", ["A docking station", "A port replicator", "NFC pairing"], "Tethering turns the phone into a gateway for other devices, at the cost of battery and your data cap."),
        _q("1.3", "A company wants to enforce a screen-lock policy and remotely wipe lost phones, including personal ones. Which tool applies?", "Mobile device management (MDM)", ["Remote Desktop", "A VPN concentrator", "Wi-Fi analyzer"], "MDM enforces policy and can lock or wipe devices; BYOD policies decide how much it may do on personal phones."),
        _q("1.3", "Two Bluetooth devices will not connect. Which order is right?", "Enable Bluetooth, make the device discoverable, find it, enter the PIN, test", ["Enter the PIN, then enable Bluetooth", "Pair first, then turn Bluetooth on", "Reset the network settings, then test"], "Pairing needs both sides on and discoverable, then the code, then a test of the function."),
        _q("1.2", "Which connection works only at a few centimetres and is used for contactless payment?", "NFC", ["Bluetooth", "Wi-Fi", "Lightning"], "Near-field communication has a range of about 4 cm, which is part of its security."),
    ],
    ("1", "networking"): [
        _q("2.1", "Which port does HTTPS use?", "TCP 443", ["TCP 80", "TCP 22", "UDP 53"], "80 is plain HTTP, 22 is SSH and 53 is DNS."),
        _q("2.1", "A user can remote into a Windows PC from home. Which port must the firewall allow?", "TCP 3389", ["TCP 445", "TCP 23", "UDP 67"], "RDP uses 3389. 445 is SMB file sharing, 23 is Telnet and 67 is DHCP."),
        _q("2.1", "Which pair is correct?", "SMTP sends mail on 25; IMAP reads mail on 143", ["POP3 on 25; SMTP on 110", "IMAP on 110; SMTP on 143", "SMTP on 143; POP3 on 25"], "SMTP 25 sends, POP3 110 downloads, IMAP 143 syncs."),
        _q("2.1", "Why would video streaming favour UDP?", "It is connectionless, so it is faster and tolerates a few lost packets", ["It guarantees delivery", "It encrypts the stream", "It uses fewer ports"], "TCP retransmits and orders data; UDP trades reliability for speed."),
        _q("2.2", "Three nearby access points all use 2.4 GHz. Which channels avoid overlap in North America?", "1, 6 and 11", ["1, 2 and 3", "3, 6 and 9", "5, 10 and 14"], "2.4 GHz channels are 5 MHz apart but about 20 MHz wide, so only 1, 6 and 11 are clear of each other."),
        _q("2.4", "Which DNS record maps a name to an IPv6 address?", "AAAA", ["A", "MX", "CNAME"], "A is IPv4, AAAA is IPv6, MX names the mail server and CNAME is an alias."),
        _q("2.4", "A client gets 169.254.12.7 and cannot reach anything. What does that tell you?", "It could not reach a DHCP server and self-assigned an APIPA address", ["The DNS server is down", "The gateway is set wrongly on purpose", "The router has IPv6 only"], "169.254.0.0/16 is APIPA. Check the cable or Wi-Fi, the DHCP server and the scope."),
        _q("2.4", "Which DNS TXT-based control tells receiving mail servers which hosts may send for your domain?", "SPF", ["DKIM", "MX", "PTR"], "SPF lists authorised senders; DKIM signs messages; DMARC says what to do when checks fail."),
        _q("2.5", "An IP camera needs power and data over one cable. Which feature supplies this?", "Power over Ethernet (PoE)", ["A patch panel", "An optical network terminal", "A loopback plug"], "PoE comes from a PoE switch or an injector."),
        _q("2.6", "Which is a private IPv4 address?", "172.20.4.9", ["172.32.4.9", "169.254.4.9", "11.20.4.9"], "Private ranges are 10/8, 172.16.0.0 to 172.31.255.255 and 192.168/16."),
        _q("2.8", "Which tool traces which wall jack a cable goes to?", "Toner probe", ["Crimper", "Loopback plug", "Punchdown tool"], "A tone generator and probe find the far end of a cable in a bundle."),
        _q("2.8", "Which tool checks whether a NIC or port can send and receive by itself?", "Loopback plug", ["Cable stripper", "Wi-Fi analyzer", "Network tap"], "A loopback plug returns the transmit signal to the receive pins."),
    ],
    ("1", "hardware"): [
        _q("3.1", "Which LCD panel type is known for wide viewing angles and good colour?", "IPS", ["TN", "VA", "CRT"], "TN is fast but narrow-angled, VA has deep blacks, IPS has the best angles and colour."),
        _q("3.2", "Which fibre type suits a long run between buildings?", "Single-mode", ["Multimode", "Coaxial", "Cat 5e"], "Single-mode has a narrow core for long distances; multimode is for short runs."),
        _q("3.2", "Which cable and connector pair carries cable-TV or cable-modem signals?", "Coaxial with an F-type connector", ["Fibre with an LC connector", "Cat 6 with RJ11", "Serial with DB9"], "RG-6 coax with F-type connectors."),
        _q("3.3", "Which RAM form factor goes in a laptop?", "SODIMM", ["DIMM", "ECC DIMM", "PCIe card"], "SODIMM is the small module for laptops and compact PCs."),
        _q("3.4", "Which RAID level stripes with a mirror and needs at least four disks?", "RAID 10", ["RAID 0", "RAID 5", "RAID 1"], "RAID 10 mirrors pairs and stripes across them."),
        _q("3.4", "Which storage uses PCIe lanes and the NVMe protocol in a small M.2 stick?", "NVMe SSD", ["2.5-inch SATA SSD", "7200 rpm HDD", "mSATA SSD"], "NVMe is far faster than SATA because it talks over PCIe."),
        _q("3.5", "Windows 11 asks for a TPM. What is it?", "A chip that stores keys and supports secure boot and disk encryption", ["A cooling module", "A type of RAM", "A graphics accelerator"], "The Trusted Platform Module protects keys; BitLocker and Windows Hello use it."),
        _q("3.5", "A server needs to run many virtual machines. Which firmware setting must be enabled?", "CPU virtualization support", ["Boot password", "Fast boot", "USB legacy support"], "Hardware virtualisation extensions are often off by default."),
        _q("3.6", "A PC needs 450 W at full load. Which supply is the sensible choice?", "A 650 W supply", ["A 450 W supply", "A 300 W supply", "Any supply, because the wattage rating does not matter"], "Leave headroom: supplies are most efficient at about half to 70 percent load."),
        _q("3.7", "Which printer language setting suits Windows office documents?", "PCL", ["PostScript only", "ASCII", "HTML"], "PCL is common for office printing; PostScript suits graphics and publishing. Match the driver to the device."),
        _q("3.8", "Which printer type uses a ribbon and can print multipart forms?", "Impact (dot matrix)", ["Laser", "Inkjet", "Thermal"], "Impact printers strike through a ribbon, so they make carbon copies."),
    ],
    ("1", "virt_cloud"): [
        _q("4.1", "Which hypervisor runs directly on the hardware?", "Type 1", ["Type 2", "A container engine", "A hosted VM"], "Type 1 (bare metal, such as ESXi or Hyper-V) has no host OS beneath it."),
        _q("4.1", "How do containers differ from virtual machines?", "They share the host's kernel, so they are lighter", ["Each has its own full OS kernel", "They need a Type 1 hypervisor", "They cannot be isolated"], "Containers package an app and its libraries on a shared kernel."),
        _q("4.2", "A company rents virtual servers and installs its own OS and apps. Which model is this?", "IaaS", ["SaaS", "PaaS", "Community cloud"], "IaaS gives you the infrastructure; PaaS also manages the OS and runtime; SaaS is a finished app."),
        _q("4.2", "Cloud capacity grows during a sale and shrinks afterwards, and billing follows use. Which characteristics are these?", "Elasticity and metered utilisation", ["Multitenancy and file sync", "Availability and ingress", "Dedicated resources and a private cloud"], "Elastic scaling plus pay-per-use is the core cloud economics."),
    ],
    ("1", "troubleshooting"): [
        _q("5.1", "A PC powers on, the fans spin, but there is no display and it beeps repeatedly. What is the best first step?", "Look up the beep pattern and reseat the RAM", ["Reinstall Windows", "Replace the monitor", "Update the BIOS over the network"], "POST beeps are diagnostic codes, and RAM and video faults are the most common causes."),
        _q("5.1", "A desktop's clock is wrong every time it is unplugged. What is likely failing?", "The CMOS battery", ["The power supply", "The hard drive", "The RAM"], "The CR2032 coin cell keeps the clock and settings when the PC is off."),
        _q("5.2", "A hard drive is clicking and the system says 'bootable device not found'. What do you do first?", "Back up what you can, then replace the failing drive", ["Defragment it", "Format it", "Lower its spindle speed"], "Clicking and missing boot devices are signs of mechanical failure. Protect the data before anything else."),
        _q("5.2", "A RAID 5 array shows one failed disk. What is correct?", "The data is still available; replace the disk and rebuild promptly", ["All data is lost", "Nothing needs doing until a second disk fails", "Convert to RAID 0 to speed up"], "RAID 5 tolerates one failure but is vulnerable during the rebuild."),
        _q("5.3", "A projector image is dim and it shuts itself off now and then. Likely cause?", "A failing bulb or blocked cooling vents", ["A bad HDMI cable", "A low refresh rate", "Wrong colour gamut"], "Old lamps lose brightness; overheating makes projectors shut down."),
        _q("5.3", "An LCD shows a permanent dark dot. What is it?", "A dead pixel, which usually means panel replacement", ["Screen burn-in that clears with rest", "A driver fault", "A loose VGA cable"], "A dead pixel is a hardware defect. Burn-in is faint images on OLED."),
        _q("5.4", "A phone is slow, gets hot and the battery drains quickly. Which fits best?", "Malware or a runaway app", ["A bad SIM card", "A cracked screen", "A weak GPS signal"], "Hot, slow and draining together suggest something is working hard in the background."),
        _q("5.5", "Wi-Fi drops at the same time every evening only near the microwave. What is it?", "Interference on 2.4 GHz", ["A DHCP lease problem", "A bad DNS record", "Wrong subnet mask"], "Microwaves emit in the 2.4 GHz band. Move to 5 GHz or another channel."),
        _q("5.5", "A user has a link light but the PC says 'limited connectivity'. What do you check?", "Whether it received a valid IP address from DHCP", ["The monitor cable", "The printer queue", "The BIOS date"], "The link is fine; the address configuration is not."),
        _q("5.6", "Every printed page has a vertical line down the same spot. Likely cause?", "A dirty or damaged drum, roller or toner path (laser)", ["Wrong paper size", "A frozen print queue", "A missing driver"], "A repeating mark in the same place points to a consumable in the print path."),
        _q("5.6", "Jobs pile up in the queue and nothing prints. What is a sensible first fix?", "Restart the print spooler and clear the stuck job", ["Replace the toner", "Reinstall Windows", "Change the paper"], "A frozen queue is usually one bad job or a stuck spooler."),
    ],
    ("2", "os"): [
        _q("1.1", "Which filesystem should you choose for a USB drive moving files over 4 GB between Windows and macOS?", "exFAT", ["FAT32", "ext4", "NTFS on macOS by default"], "FAT32 caps files at 4 GB; exFAT works on both without that limit."),
        _q("1.2", "Which partition style is needed to boot a UEFI system from a disk over 2 TB?", "GPT", ["MBR", "FAT32", "Dynamic disk only"], "MBR is limited to 2 TB and four primary partitions."),
        _q("1.3", "Which Windows edition can join a domain and use BitLocker and Group Policy Editor?", "Pro", ["Home", "S mode only", "N edition only"], "Home lacks domain join and gpedit.msc. Pro, Enterprise and Education have them."),
        _q("1.3", "Which is a hardware requirement for Windows 11?", "TPM 2.0 and UEFI with Secure Boot", ["A touch screen", "32 GB of RAM", "A discrete graphics card"], "Check the current minimum before an upgrade."),
        _q("1.4", "Which tool shows which service or program is starting with Windows and slowing boot?", "Task Manager Startup tab", ["Device Manager", "Disk Cleanup", "Certificate Manager"], "The Startup tab lists startup items and their impact."),
        _q("1.4", "Which MMC snap-in manages partitions and drive letters?", "diskmgmt.msc", ["devmgmt.msc", "eventvwr.msc", "taskschd.msc"], "Disk Management; Device Manager is for hardware, Event Viewer for logs and Task Scheduler for jobs."),
        _q("1.5", "A user's IP configuration looks wrong. Which command shows the address, mask, gateway and DNS in full?", "ipconfig /all", ["netstat -a", "nslookup", "winver"], "ipconfig /all also shows the DHCP server, lease times and MAC address."),
        _q("1.5", "Which command repairs corrupted protected system files?", "sfc /scannow", ["chkdsk /f", "gpupdate /force", "format c:"], "System File Checker; chkdsk checks the disk, gpupdate refreshes policy."),
        _q("1.5", "Which command forces a refresh of Group Policy right away?", "gpupdate /force", ["gpresult /r", "net use", "diskpart"], "gpresult only reports what applied."),
        _q("1.7", "A laptop on a coffee-shop network should hide file sharing. Which profile?", "Public network", ["Private network", "Domain network", "Workgroup"], "Public profile restricts discovery and sharing."),
        _q("1.9", "Which Linux command shows disk space used per mounted filesystem?", "df -h", ["du -sh /", "ls -l", "fsck"], "df reports filesystem space; du reports directory usage."),
        _q("1.9", "Which file holds hashed passwords on Linux and is readable only by root?", "/etc/shadow", ["/etc/passwd", "/etc/hosts", "/etc/fstab"], "/etc/passwd lists accounts and is world-readable; hashes live in /etc/shadow."),
        _q("1.8", "Which macOS feature backs up to an external drive?", "Time Machine", ["Spotlight", "Mission Control", "Keychain"], "Time Machine keeps hourly, daily and weekly versions."),
    ],
    ("2", "security"): [
        _q("2.1", "An attacker follows an employee through a secured door. What reduces this?", "An access control vestibule and a badge policy", ["A longer password", "A VPN", "Disk encryption"], "Tailgating is stopped by physical controls and staff awareness."),
        _q("2.1", "Which is a MFA combination?", "Password plus a one-time code from an authenticator app", ["Password plus security question", "Two different passwords", "PIN plus a different PIN"], "MFA uses different factors: something you know, have or are."),
        _q("2.1", "A new hire gets only the access needed for the role. Which principle?", "Least privilege", ["Defence in depth", "Non-repudiation", "Chain of custody"], "Give the minimum rights needed and review them."),
        _q("2.2", "Which protects a whole drive, including if it is stolen?", "BitLocker", ["EFS", "NTFS permissions", "UAC"], "BitLocker encrypts the volume; EFS encrypts individual files."),
        _q("2.2", "A user can read a shared folder over the network but not write, even though NTFS allows it. Why?", "The most restrictive of share and NTFS permissions applies", ["Share permissions are ignored", "Only NTFS permissions apply remotely", "Inheritance overrides both"], "Effective access over the network is the more restrictive of the two."),
        _q("2.3", "Which wireless setting is the best choice today?", "WPA3 with AES, or WPA2 with AES if WPA3 is unavailable", ["WEP", "WPA with TKIP", "An open network with a hidden SSID"], "WEP and TKIP are broken or deprecated. Hiding the SSID is not security."),
        _q("2.3", "Which service centralises authentication for wireless users using 802.1X?", "RADIUS", ["DHCP", "NTP", "DNS"], "RADIUS authenticates, authorises and accounts for network access; TACACS+ does similar for device administration."),
        _q("2.4", "Files are encrypted and a note demands payment. What is it?", "Ransomware", ["Adware", "A keylogger", "A rootkit"], "Isolate the machine first and restore from a clean backup."),
        _q("2.4", "Malware runs only in memory and leaves no file on disk. What is it called?", "Fileless malware", ["A boot sector virus", "A PUP", "Cryptominer"], "It abuses legitimate tools, so detection relies on behaviour (EDR) rather than file scanning."),
        _q("2.5", "An email that looks like it is from the CEO asks accounting to wire money urgently. Which attack?", "Business email compromise or whaling", ["Smishing", "An on-path attack", "Dumpster diving"], "Verify by a separate channel before moving money."),
        _q("2.5", "A fake Wi-Fi network with the same name as the coffee shop's. What is it?", "An evil twin", ["A zero-day", "A DDoS", "A dictionary attack"], "Evil twins lure devices to connect so traffic can be intercepted."),
        _q("2.6", "In the SOHO malware removal steps, what comes right after identifying the symptoms?", "Quarantine the infected system", ["Reinstall the OS", "Educate the user", "Schedule scans"], "Isolate it so the problem does not spread; remediate afterwards."),
        _q("2.8", "A phone is lost. Which feature lets you erase it remotely?", "MDM or a remote-wipe locator service", ["Tethering", "NFC", "A VPN"], "Encrypt the device, require a lock, and keep a remote wipe ready."),
        _q("2.9", "A retired hard drive held customer data. Which is best?", "Shred or degauss it and get a certificate of destruction", ["Delete the files", "Do a quick format", "Hand it to a colleague"], "Deleting and quick-formatting leave data recoverable."),
        _q("2.9", "Why does degaussing not work on an SSD?", "SSDs store data in flash cells, not magnetic platters", ["SSDs are too heavy", "It makes the drive faster", "Degaussing only works on optical discs"], "Use the drive's secure erase or physical destruction for SSDs."),
        _q("2.10", "Which SOHO router changes harden it first?", "Change the default admin password, update firmware, turn off UPnP and WPS if unused", ["Enable port forwarding for everything", "Leave defaults for support", "Disable the firewall"], "Defaults are published. Reduce what is exposed."),
        _q("2.11", "A browser shows a certificate warning for a banking site. What now?", "Stop and do not enter credentials", ["Click through if the page looks right", "Disable the pop-up blocker", "Clear the cache and try again with the same warning"], "Certificate warnings can mean interception or an expired or wrong certificate."),
    ],
    ("2", "sw_trouble"): [
        _q("3.1", "A PC shows a blue screen after a driver update. What is a good first step?", "Boot to safe mode or recovery and roll the driver back", ["Replace the motherboard", "Reformat immediately", "Disable the firewall"], "Undo the recent change; the stop code and the minidump help."),
        _q("3.1", "A user logs on and waits minutes for the desktop. What is a common cause?", "A large or corrupt profile, or slow login scripts", ["A bad HDMI cable", "An empty printer queue", "Low toner"], "Slow profile load points at the profile size, redirected folders or scripts."),
        _q("3.1", "A domain PC's clock drifts and Kerberos logins start failing. What is wrong?", "Time is out of sync with the domain, so check NTP and the time source", ["The DNS cache is full", "The monitor refresh rate is low", "The page file is too small"], "Kerberos tolerates only a few minutes of skew."),
        _q("3.2", "An app crashes on launch after an OS update. What do you try first?", "Update or reinstall the app, then check storage and permissions", ["Factory reset immediately", "Replace the SIM", "Jailbreak the device"], "Start with the least destructive fix."),
        _q("3.3", "A phone shows many pop-up ads and uses lots of data. Likely cause?", "A malicious or unwanted app", ["A dead pixel", "A low-quality case", "Airplane mode"], "Remove the app, scan, update, and check app permissions."),
        _q("3.4", "A user's browser keeps redirecting to unfamiliar sites and shows pop-ups. What first?", "Check for unwanted extensions and run an anti-malware scan", ["Replace the NIC", "Reinstall office software", "Reset the BIOS"], "Redirects and pop-ups are classic extension or malware signs."),
        _q("3.4", "A user's files are renamed and a pop-up says 'your antivirus is expired, click here'. What do you do?", "Disconnect from the network and treat it as a malware incident", ["Click to renew", "Restart and carry on", "Delete the files"], "Fake security alerts are a common lure."),
    ],
    ("2", "ops"): [
        _q("4.1", "Which ticket details help the next technician most?", "A clear issue description, steps taken, and the resolution", ["Only the user's name", "The priority only", "A screenshot of the desktop"], "A good ticket lets someone else continue without asking again."),
        _q("4.2", "What must a change request include before approval?", "Purpose, scope, risk, a rollback plan and a backup plan", ["Only the change date", "Only the technician's name", "A guarantee that nothing will break"], "Know how to undo it before you start."),
        _q("4.2", "A server is down and must be patched at once. Which change type?", "Emergency change", ["Standard change", "Normal change", "Change freeze"], "Emergency changes skip some delay but still get documented and reviewed afterwards."),
        _q("4.3", "A backup takes a full copy on Sunday, then only data changed since the last backup each day. Which type?", "Incremental", ["Differential", "Full", "Synthetic full"], "Incremental needs the full plus every increment to restore; differential needs the full plus the latest."),
        _q("4.3", "What does the 3-2-1 rule say?", "Three copies, on two kinds of media, with one offsite", ["Three backups a day on two servers at one site", "Three users, two admins, one owner", "Three weeks of retention in two places"], "And test restores regularly."),
        _q("4.4", "Before opening a desktop PC to replace a part, what is the correct step?", "Power it off, unplug it and use an ESD strap", ["Leave it plugged in to ground it", "Wear a wool sweater", "Touch the PSU's output while on"], "Disconnect power and discharge static."),
        _q("4.5", "Which is the correct way to handle a swollen laptop battery?", "Recycle it as hazardous waste; never put it in the trash", ["Puncture it to release pressure", "Store it in the car", "Throw it in a landfill bin"], "Follow the SDS/MSDS and local rules."),
        _q("4.6", "You find prohibited content on a work PC. What is the right first action?", "Stop, preserve evidence, report to management and follow chain of custody", ["Delete it quickly", "Show colleagues", "Copy it to a USB"], "Do not alter evidence. Document and escalate."),
        _q("4.6", "Which evidence is the most volatile and should be collected first?", "Data in RAM", ["Files on disk", "Backup tapes", "Printed logs"], "Order of volatility goes from RAM and cache to disk, logs and archives."),
        _q("4.7", "A customer is angry about an outage. What is right?", "Listen, don't interrupt, restate the problem, and set expectations", ["Explain the technical details at length", "Tell them it is their fault", "Take a personal call"], "Active listening and clear next steps calm the situation."),
        _q("4.8", "Which file extension is a PowerShell script?", ".ps1", [".sh", ".bat", ".vbs"], ".sh is Bash, .bat is batch, .vbs is VBScript."),
        _q("4.8", "What is a risk of running a script you found online?", "It may introduce malware or change system settings unexpectedly", ["It will always run slower", "It voids the licence", "It cannot be undone by anyone"], "Read it, test it in a sandbox and back up first."),
        _q("4.9", "Which remote method encrypts a command-line session to a Linux server?", "SSH", ["Telnet", "VNC with no password", "FTP"], "SSH uses port 22. Telnet sends everything in clear text."),
        _q("4.10", "A chatbot gives a confident answer that is false. What is this limitation called?", "A hallucination", ["Plagiarism", "Latency", "Encryption"], "Verify AI output, and do not paste private data into a public AI service."),
    ],
}

# ------------------------------------------------------------------ symptom finder: (exam, objective, symptom, likely causes, first checks)
SYMPTOMS = [
    ("1", "5.1", "POST beeps or no POST", ["Loose or failed RAM", "Bad video card or seating", "Failing motherboard or CPU"], ["Look up the beep code for that BIOS", "Reseat RAM and cards, try one stick at a time", "Remove extras until it posts"]),
    ("1", "5.1", "No power at all", ["Power cable or outlet", "Failed power supply", "Front-panel switch lead"], ["Try another outlet and cable", "Check the PSU switch and the motherboard standby LED", "Test the PSU with a tester"]),
    ("1", "5.1", "Blank screen, fans spin", ["Display cable or input source", "RAM or GPU not seated", "Monitor fault"], ["Try another cable or monitor", "Use the motherboard output to rule out the GPU", "Reseat RAM"]),
    ("1", "5.1", "Random shutdowns, overheating, burning smell", ["Dust and failed fans", "Dried thermal paste or loose heat sink", "Failing power supply"], ["Power off and unplug if there is a burning smell", "Clean dust, check fans", "Watch temperatures in BIOS"]),
    ("1", "5.1", "Sluggish performance, application crashes", ["Too little RAM or failing RAM", "Overheating or throttling", "Drive nearly full or failing"], ["Check temperatures and memory use", "Run a memory test", "Check drive health"]),
    ("1", "5.1", "Wrong date and time after power loss", ["Dead CMOS battery"], ["Replace the coin cell and reset the clock"]),
    ("1", "5.1", "Capacitor swelling or leaking", ["Failed board components from age or heat"], ["Replace the board or power supply; do not keep running it"]),
    ("1", "5.2", "Clicking or grinding drive", ["Mechanical failure"], ["Stop using it", "Back up immediately if it still reads", "Replace it"]),
    ("1", "5.2", "Bootable device not found", ["Boot order changed", "Failed or disconnected drive", "Corrupt boot sector"], ["Check BIOS for the drive", "Check cables", "Try recovery tools"]),
    ("1", "5.2", "S.M.A.R.T. failure warning", ["The drive predicts its own failure"], ["Back up now", "Replace the drive"]),
    ("1", "5.2", "RAID degraded, array missing, audible alarm", ["A failed member disk", "Controller or cable fault"], ["Check the controller's status LEDs and utility", "Replace the failed disk and rebuild", "Verify backups before rebuilding"]),
    ("1", "5.2", "Very slow reads and writes, low IOPS", ["Failing drive", "Full SSD or fragmentation (HDD)", "Wrong interface mode or cable"], ["Check S.M.A.R.T.", "Free space", "Check the cable and controller mode"]),
    ("1", "5.3", "No image or wrong input", ["Wrong input source", "Loose cable", "Wrong output selected"], ["Press the input button and check the cable at both ends"]),
    ("1", "5.3", "Dim image, projector shuts off", ["Aging bulb", "Clogged filter or vents"], ["Clean vents and filters", "Replace the lamp"]),
    ("1", "5.3", "Fuzzy or distorted image, sizing problems", ["Wrong resolution or refresh rate", "Bad cable", "Focus or keystone setting"], ["Set the native resolution", "Try another cable", "Adjust focus and keystone"]),
    ("1", "5.3", "Dead pixels, burn-in, flashing screen", ["Panel defect or wear", "Loose cable or failing backlight"], ["Test with a solid-colour image", "Swap cable", "Replace the panel if needed"]),
    ("1", "5.3", "Wrong colours", ["Loose pin in the cable", "Colour profile", "Failing panel"], ["Reseat or swap the cable", "Reset the colour profile"]),
    ("1", "5.4", "Poor battery life or swollen battery", ["Aged battery", "Heavy apps or screen brightness", "Damaged cell"], ["Check battery health", "Stop charging a swollen battery and replace it safely"]),
    ("1", "5.4", "Won't charge", ["Cable, charger or port", "Debris or damage in the port", "Battery fault"], ["Try another cable and charger", "Clean the port gently"]),
    ("1", "5.4", "Touch drift, unresponsive screen, broken screen", ["Digitizer fault", "Screen protector or moisture", "Calibration"], ["Restart", "Recalibrate", "Replace the screen assembly"]),
    ("1", "5.4", "Liquid damage or overheating", ["Water ingress", "Heavy background use or malware"], ["Power off, do not charge", "Remove the battery if possible", "Check indicators"]),
    ("1", "5.4", "Can't install apps", ["Storage full", "OS too old", "Account or store issue"], ["Free space", "Update the OS", "Check the account"]),
    ("1", "5.5", "Slow network speeds", ["Congestion or a duplex mismatch", "Interference on Wi-Fi", "Bad cable"], ["Test wired and wireless", "Check channel use", "Replace the cable"]),
    ("1", "5.5", "Limited connectivity or APIPA address", ["No DHCP response"], ["Check cable and Wi-Fi", "Check the DHCP server and scope", "Run ipconfig /renew"]),
    ("1", "5.5", "Intermittent wireless connectivity", ["Interference", "Weak signal", "Roaming between access points"], ["Use a Wi-Fi analyzer", "Change channel or band", "Move the AP"]),
    ("1", "5.5", "High latency, jitter, poor VoIP quality", ["Congestion", "Wi-Fi interference", "No QoS for voice"], ["Test with ping and pathping", "Prioritise voice traffic", "Wire the phones"]),
    ("1", "5.5", "Port flapping or authentication failures", ["Bad cable or port", "Speed or duplex mismatch", "Wrong credentials or 802.1X settings"], ["Swap cable and port", "Check logs on the switch", "Verify credentials"]),
    ("1", "5.6", "Lines or streaks on pages", ["Dirty or damaged drum or fuser", "Clogged printhead (inkjet)"], ["Clean or replace the consumable", "Run printhead cleaning"]),
    ("1", "5.6", "Faded prints", ["Low toner or ink", "Wrong paper or density setting"], ["Replace the cartridge", "Check settings"]),
    ("1", "5.6", "Garbled print", ["Wrong driver or language (PCL/PostScript)", "Bad cable"], ["Install the correct driver", "Reconnect"]),
    ("1", "5.6", "Paper jams or paper not feeding", ["Worn rollers", "Wrong paper", "Overfilled tray"], ["Clear jams carefully", "Clean or replace rollers", "Use proper paper"]),
    ("1", "5.6", "Frozen queue or multiple pending jobs", ["A stuck job", "Spooler stopped"], ["Clear the queue", "Restart the Print Spooler service"]),
    ("1", "5.6", "Double or echo images, speckling", ["Worn fuser or drum", "Cleaning blade fault"], ["Run maintenance", "Replace the fuser or drum"]),
    ("2", "3.1", "Blue screen (BSOD)", ["Bad driver or update", "Failing RAM or disk", "Overheating"], ["Note the stop code", "Boot safe mode and roll back", "Run memory and disk checks"]),
    ("2", "3.1", "Slow performance or low memory warnings", ["Too many startup programs", "Not enough RAM", "Malware"], ["Task Manager: check CPU, memory, disk", "Disable startup items", "Scan for malware"]),
    ("2", "3.1", "Boot issues, no OS found", ["Boot order or boot files damaged", "Failed drive"], ["Check BIOS", "Use Startup Repair or recovery media", "Check the drive"]),
    ("2", "3.1", "Services not starting, applications crashing", ["Dependency missing", "Corrupt files", "Permissions"], ["Check Event Viewer", "Run sfc /scannow", "Reinstall the app"]),
    ("2", "3.1", "Slow profile load or time drift", ["Large profile or logon scripts", "Clock out of sync"], ["Review the profile and scripts", "Resync time with the domain"]),
    ("2", "3.2", "App fails to launch, install or update (mobile)", ["Storage full", "OS or app out of date", "Corrupt app data"], ["Free space", "Update the OS and app", "Clear cache or reinstall"]),
    ("2", "3.2", "Random reboots, battery drain, slow to respond", ["Failing app", "Aging battery", "Low storage"], ["Update and restart", "Check battery usage", "Reset settings last"]),
    ("2", "3.2", "Wi-Fi, Bluetooth or NFC not working", ["Toggled off", "Interference or stale pairing", "Airplane mode"], ["Toggle off and on", "Forget and re-pair", "Update the OS"]),
    ("2", "3.3", "Unexpected apps, ads, high data use, leaked data", ["Unofficial app store or sideloaded app", "Jailbreak or root", "Fake security warnings"], ["Remove the app", "Check permissions", "Run a mobile scan", "Reset if needed"]),
    ("2", "3.4", "Pop-ups, redirection, certificate warnings", ["Malicious extension or adware", "Hijacked DNS or proxy"], ["Remove extensions", "Check proxy and DNS", "Scan"]),
    ("2", "3.4", "Files renamed, missing or locked", ["Ransomware"], ["Disconnect from the network", "Identify the strain", "Restore from backup"]),
    ("2", "3.4", "False antivirus alerts, unwanted notifications, update failures", ["Rogue software", "Malware blocking updates"], ["Quarantine the system", "Boot a rescue environment", "Scan and remediate"]),
]
SYMPTOM_NOTE = "A starting point, not a diagnosis. Question the obvious first, change one thing at a time, and write down what you tried."

# ------------------------------------------------------------------ reference tables
PORTS = [
    ("20, 21", "FTP", "TCP", "File transfer. Clear text; use SFTP or FTPS."), ("22", "SSH / SFTP", "TCP", "Encrypted remote shell and file transfer."), ("23", "Telnet", "TCP", "Clear-text remote shell. Avoid."),
    ("25", "SMTP", "TCP", "Sending and relaying mail."), ("53", "DNS", "UDP and TCP", "Name resolution."), ("67, 68", "DHCP", "UDP", "Server 67, client 68."),
    ("80", "HTTP", "TCP", "Web, unencrypted."), ("110", "POP3", "TCP", "Download mail."), ("137-139", "NetBIOS / NetBT", "UDP and TCP", "Legacy Windows name and session services."),
    ("143", "IMAP", "TCP", "Mail kept on the server."), ("389", "LDAP", "TCP and UDP", "Directory lookups."), ("443", "HTTPS", "TCP", "Encrypted web."),
    ("445", "SMB / CIFS", "TCP", "Windows file and printer sharing."), ("3389", "RDP", "TCP", "Windows remote desktop."),
]
REFERENCE = {
    "network": [
        {"title": "Wi-Fi bands and standards", "rows": [
            ["2.4 GHz", "Longer range, penetrates walls, crowded; channels 1, 6, 11 do not overlap (North America)."],
            ["5 GHz", "More channels, faster, shorter range."], ["6 GHz", "Wi-Fi 6E and 7 only. Most capacity, shortest range, needs newer devices."],
            ["802.11b / g", "2.4 GHz, 11 and 54 Mbps (old)."], ["802.11a", "5 GHz, 54 Mbps (old)."], ["802.11n (Wi-Fi 4)", "2.4 and 5 GHz."], ["802.11ac (Wi-Fi 5)", "5 GHz."],
            ["802.11ax (Wi-Fi 6 / 6E)", "2.4, 5 (and 6) GHz."], ["802.11be (Wi-Fi 7)", "2.4, 5 and 6 GHz."],
            ["Channel width", "20, 40, 80, 160 MHz: wider is faster but crowds the band."], ["Bluetooth", "Short-range personal area network, about 10 m typical."], ["NFC", "About 4 cm. Payments, badges, pairing."], ["RFID", "Tags read by radio; passive tags have no battery."]]},
        {"title": "Network hardware", "rows": [
            ["Router", "Moves traffic between networks."], ["Switch (unmanaged / managed)", "Connects devices on a LAN; managed adds VLANs, port settings, monitoring."], ["Access point", "Wireless entry to the wired network."],
            ["Patch panel", "Fixed termination point for cable runs, with short patch cables to the switch."], ["Firewall", "Filters traffic by rules."], ["PoE", "Power over the data cable: 802.3af ≈15 W, 802.3at ≈30 W, 802.3bt up to ≈60-90 W. Use a PoE switch or an injector."],
            ["Cable modem / DSL modem / ONT", "Converts the provider's medium (coax, phone line, fibre) to Ethernet."], ["NIC", "Network card with a unique MAC address."]]},
        {"title": "Services and appliances", "rows": [
            ["DNS", "Names to addresses."], ["DHCP", "Hands out addresses, masks, gateways, DNS."], ["File share / print server", "Central files and printers."], ["Mail", "SMTP, POP3, IMAP."], ["Syslog", "Central log collection."],
            ["AAA", "Authentication, authorisation, accounting."], ["NTP", "Time sync. Kerberos and logs depend on it."], ["Spam gateway", "Filters mail."], ["UTM", "Firewall, antivirus and filtering in one box."], ["Load balancer", "Spreads requests across servers."],
            ["Proxy", "Requests go through it: filtering, caching, anonymity."], ["SCADA / IoT / embedded", "Industrial or small devices; often old, unpatched and hard to update, so isolate them."]]},
        {"title": "Connection and network types", "rows": [
            ["Fiber", "Fastest, long distance, immune to electrical interference."], ["Cable", "Shared coax segment; speed can vary at busy times."], ["DSL", "Over phone lines; speed drops with distance."],
            ["Satellite", "High latency, weather-sensitive."], ["Cellular", "Mobile data, fixed wireless."], ["WISP", "Wireless internet service provider, common in rural areas."],
            ["LAN / WLAN", "One site, wired or wireless."], ["WAN", "Sites far apart."], ["MAN", "A city."], ["PAN", "A person's devices, e.g. Bluetooth."], ["SAN", "Dedicated storage network."]]},
        {"title": "Tools", "rows": [
            ["Crimper", "Attaches an RJ45 plug to a cable."], ["Cable stripper", "Removes the jacket without nicking the wires."], ["Punchdown tool", "Seats wires into a patch panel or 110 block."], ["Cable tester", "Checks continuity and pin order."],
            ["Toner probe", "Finds the far end of a cable."], ["Loopback plug", "Tests a port or NIC."], ["Wi-Fi analyzer", "Shows channels, signal and interference."], ["Network tap", "Copies traffic for analysis."]]},
        {"title": "DNS and mail records", "rows": [
            ["A / AAAA", "Name to IPv4 / IPv6 address."], ["CNAME", "Alias to another name."], ["MX", "Mail server for the domain."], ["TXT", "Free text; carries SPF, DKIM and DMARC."],
            ["SPF", "Which servers may send for the domain."], ["DKIM", "A cryptographic signature on each message."], ["DMARC", "What to do when SPF or DKIM fail (none, quarantine, reject) and where to send reports."],
            ["DHCP", "Scope (the range), lease (how long), reservation (fixed address per MAC), exclusion (addresses never handed out)."]]},
    ],
    "cables": [
        {"title": "Copper and fibre", "rows": [
            ["Cat 5e", "1 Gbps to 100 m."], ["Cat 6", "1 Gbps to 100 m; 10 Gbps to about 55 m."], ["Cat 6a", "10 Gbps to 100 m."], ["UTP / STP", "Unshielded / shielded twisted pair. Shielding reduces interference."],
            ["Plenum-rated", "Fire-rated, low smoke; required in air-handling spaces."], ["Direct burial", "Rated for underground use."], ["Coax (RG-6) + F-type", "Cable TV and cable modems."],
            ["T568A order", "white-green, green, white-orange, blue, white-blue, orange, white-brown, brown"], ["T568B order", "white-orange, orange, white-green, blue, white-blue, green, white-brown, brown"],
            ["Single-mode fibre", "Long distance, laser."], ["Multimode fibre", "Short runs, cheaper optics."], ["ST / SC / LC", "Twist-lock round / push-pull square / small push-pull."], ["RJ11 / RJ45", "Two-pair phone and DSL / eight-pin Ethernet."]]},
        {"title": "Video, peripheral and drive", "rows": [
            ["HDMI", "Digital video + audio."], ["DisplayPort", "Digital video + audio, daisy-chaining."], ["DVI", "Digital (DVI-D) or analog (DVI-A)."], ["VGA", "Analog; no audio."], ["USB-C / Thunderbolt", "Reversible; can carry video, data and power."],
            ["USB 2.0 / 3.0", "480 Mbps / 5 Gbps."], ["Serial (DB9)", "Console and legacy devices."], ["SATA / eSATA", "Internal drive / external drive connection."], ["Molex", "Legacy 4-pin power."], ["Lightning / micro-USB / mini-USB", "Older phone and device connectors."]]},
    ],
    "hardware": [
        {"title": "RAM", "rows": [["DIMM / SODIMM", "Desktop / laptop and small PCs."], ["DDR generations", "DDR3, DDR4, DDR5 are keyed differently and not interchangeable."], ["ECC", "Detects and corrects single-bit errors; servers."], ["Dual / quad channel", "Matched sticks in the right slots raise bandwidth."]]},
        {"title": "Storage", "rows": [["HDD", "5400, 7200, 10 000 rpm; 2.5-inch and 3.5-inch."], ["SSD SATA", "About 550 MB/s."], ["NVMe (M.2, PCIe)", "Several GB/s."], ["SAS", "Server drives."], ["mSATA / M.2", "Small form factors; M.2 may be SATA or NVMe."], ["RAID 0, 1, 5, 6, 10", "See the RAID calculator in the Capacity tab."]]},
        {"title": "Motherboard, CPU and firmware", "rows": [
            ["ATX / microATX / ITX", "Large / smaller / smallest boards."], ["Sockets", "Intel and AMD sockets differ; the CPU must match."], ["x86/x64 vs ARM", "Instruction-set families."], ["BIOS/UEFI", "Boot order, passwords, TPM, Secure Boot, virtualisation, fan and temperature monitors."],
            ["TPM / HSM", "Key storage chips and modules."], ["Cooling", "Fans, heat sinks, thermal paste, liquid."], ["Power supply", "20+4 pin main connector; rails of 3.3, 5, 12 V; modular and redundant types."]]},
    ],
    "printers": [
        {"title": "Printers", "rows": [
            ["Laser steps", "Processing, charging, exposing, developing, transferring, fusing, cleaning."], ["Laser care", "Toner, maintenance kit, calibrate, clean."], ["Inkjet care", "Clean printheads, replace cartridges, calibrate, clear jams."],
            ["Thermal", "Special heat-sensitive paper; clean the heating element."], ["Impact", "Ribbon and printhead; multipart forms."], ["Setup", "Choose a place, install the right driver (PCL vs PostScript), update firmware, connect by USB, Ethernet or wireless."],
            ["Sharing", "Printer share or a print server; secure printing, badging and audit logs add control."], ["Scanning", "Scan to email, SMB or cloud; ADF or flatbed."]]},
    ],
    "mobile": [
        {"title": "Mobile devices", "rows": [
            ["Parts to replace", "Battery, screen/digitizer, keyboard, storage, RAM (often soldered), wireless cards, camera, microphone."], ["Biometrics", "Fingerprint and face unlock; NFC for payments."],
            ["Connections", "USB-C, micro-USB, Lightning, NFC, Bluetooth, tethering/hotspot."], ["Accessories", "Stylus, headsets, speakers, webcam, dock, port replicator."],
            ["Cellular", "3G/4G/5G; SIM or eSIM."], ["MDM", "Corporate vs BYOD policies, app control, remote wipe."], ["Sync", "Mail, contacts, calendar, cloud storage; watch data caps."], ["Safe handling", "A swollen battery is a hazard: stop charging, do not puncture, recycle properly."]]},
    ],
    "cloud": [
        {"title": "Virtualization and cloud", "rows": [
            ["Type 1 hypervisor", "Runs on the hardware (ESXi, Hyper-V)."], ["Type 2 hypervisor", "Runs inside an OS (VirtualBox, VMware Workstation)."], ["Container", "App plus libraries on the host's kernel."], ["VDI", "Desktops running on servers."],
            ["Private / public / hybrid / community", "Who owns and shares the infrastructure."], ["IaaS / PaaS / SaaS", "You manage more to less: servers, platform, nothing but use."], ["Characteristics", "Elasticity, metering (ingress/egress), multitenancy, availability, file sync."]]},
    ],
    "os": [
        {"title": "Operating systems", "rows": [
            ["NTFS", "Windows: permissions, encryption, large files."], ["ReFS", "Resilient, for storage."], ["FAT32", "Everywhere; 4 GB file limit."], ["exFAT", "Large removable drives."], ["ext4 / XFS", "Linux."], ["APFS", "Apple."],
            ["EOL", "End of life: no more security updates. Replace or isolate."], ["Home / Pro / Pro for Workstations / Enterprise", "Home lacks domain join, BitLocker management and gpedit.msc."],
            ["Windows 11 minimum", "64-bit CPU, 4 GB RAM, 64 GB storage, UEFI with Secure Boot, TPM 2.0."], ["Install methods", "USB, network (PXE), image, recovery partition, zero-touch; clean install vs in-place upgrade."],
            ["Partition styles", "GPT for UEFI and large disks; MBR is limited to 2 TB."], ["Before upgrading", "Back up, check app and driver compatibility, check hardware requirements."]]},
        {"title": "Windows tools (Run box / console name)", "rows": [
            ["Task Manager", "Ctrl+Shift+Esc: processes, performance, startup, users, services."], ["Event Viewer", "eventvwr.msc"], ["Disk Management", "diskmgmt.msc"], ["Task Scheduler", "taskschd.msc"], ["Device Manager", "devmgmt.msc"],
            ["Certificate Manager", "certmgr.msc"], ["Local Users and Groups", "lusrmgr.msc (not on Home)"], ["Performance Monitor", "perfmon.msc"], ["Group Policy Editor", "gpedit.msc (not on Home)"], ["Disk Cleanup / Defragment", "cleanmgr.exe / dfrgui.exe"],
            ["Registry Editor", "regedit.exe; back up before editing."], ["System Information", "msinfo32.exe"], ["Resource Monitor", "resmon.exe"], ["System Configuration", "msconfig.exe"]]},
        {"title": "Windows commands", "rows": [
            ["cd, dir, md, rmdir /s", "Navigate, list, make and remove folders."], ["ipconfig /all, /release, /renew, /flushdns", "Show and refresh addressing and the DNS cache."], ["ping, tracert, pathping", "Reachability, route, and route with loss."],
            ["netstat -ano", "Connections and listening ports with process IDs."], ["nslookup", "Query DNS."], ["net use", "Map a drive."], ["net user", "Local accounts."], ["hostname, whoami, winver", "Name, current user, version."],
            ["chkdsk /f /r", "Check a disk and repair or recover."], ["format, diskpart", "Format a volume / partition tool."], ["robocopy", "Robust copy and mirror."], ["gpupdate /force, gpresult /r", "Refresh policy / see what applied."], ["sfc /scannow", "Repair system files."], ["command /?", "Help for any command."]]},
        {"title": "macOS and Linux", "rows": [
            ["macOS", ".dmg, .pkg, .app installs; Time Machine, Spotlight, Mission Control, Keychain, FileVault, Disk Utility, Terminal, Force Quit (Cmd+Opt+Esc), Finder, Dock, Continuity."],
            ["Linux files", "ls, pwd, mv, cp, rm, chmod, chown, grep, find."], ["Linux disks", "fsck, mount, df, du."], ["Linux admin", "su, sudo; the root account is all-powerful."], ["Linux packages", "apt (Debian/Ubuntu), dnf (Fedora/RHEL)."],
            ["Linux network", "ip, ping, curl, dig, traceroute."], ["Linux info", "man, cat, top, ps."], ["Config files", "/etc/passwd, /etc/shadow, /etc/hosts, /etc/fstab, /etc/resolv.conf."], ["Components", "systemd, kernel, bootloader."]]},
    ],
    "security": [
        {"title": "Security measures", "rows": [
            ["Physical", "Bollards, vestibule, badge reader, cameras, alarms, locks, guards, fences, lighting."], ["Logical", "Least privilege, zero trust, ACLs, MFA, SSO, SAML, just-in-time access, PAM, MDM, DLP, IAM, directory services."],
            ["MFA factors", "Know, have, are. SMS is the weakest code delivery; an authenticator app or hardware token is better."], ["Wireless", "WPA3 > WPA2 (AES). TKIP and WEP are obsolete. RADIUS (802.1X), TACACS+, Kerberos for authentication."],
            ["Windows", "Defender Antivirus and Firewall, UAC, BitLocker, EFS, NTFS vs share permissions, Windows Hello, standard vs admin accounts, Active Directory and Group Policy."],
            ["Malware", "Trojan, rootkit, virus, spyware, ransomware, keylogger, boot sector virus, cryptominer, stalkerware, fileless, adware, PUP."], ["Tools", "Antivirus, anti-malware, EDR/MDR/XDR, email gateway, software firewall, recovery environment, user training, reinstall."],
            ["Social engineering", "Phishing (vishing, smishing, QR, spear, whaling), shoulder surfing, tailgating, impersonation, dumpster diving."], ["Threats", "DoS/DDoS, evil twin, zero-day, spoofing, on-path, brute force, dictionary, insider, SQL injection, XSS, BEC, supply-chain."],
            ["Mobile", "Encryption, screen lock, updates, remote wipe, locator, MDM, profiles; avoid jailbreaking and unofficial stores."], ["Browser", "Trusted sources, hashes to verify downloads, patches, extensions, password manager, valid certificates, pop-up blocker, secure DNS."]]},
    ],
    "ops": [
        {"title": "Operations", "rows": [
            ["Ticket", "User and device, description, category, severity, escalation, notes, resolution."], ["Assets", "Inventory, CMDB, tags, procurement, warranty, assigned user."], ["Documents", "SOPs, onboarding and offboarding checklists, SLAs, knowledge base."],
            ["Change types", "Standard (pre-approved), normal (reviewed), emergency (expedited)."], ["Change record", "Purpose, scope, date and window, impact, risk, rollback, backup, approval, test, acceptance."],
            ["Backup types", "Full; incremental (since last backup); differential (since last full); synthetic full (built from earlier backups)."], ["Rotation", "3-2-1; grandfather-father-son; test restores."],
            ["Safety", "ESD strap and mat, antistatic bags, disconnect power, lifting, fire safety, goggles, mask, cable management."], ["Environment", "SDS/MSDS, battery and toner disposal, temperature and humidity, dust, UPS and surge suppressors."],
            ["Incident handling", "Preserve evidence, chain of custody, order of volatility, tell management, document."], ["Licensing", "EULA, DRM, personal vs corporate, open source."], ["Regulated data", "Card data, government IDs, PII, health data; follow retention rules."],
            ["Customer service", "Listen, clarify, avoid jargon, stay professional, set expectations, follow up, protect private information."], ["Scripts", ".bat, .ps1, .vbs, .sh, .js, .py: automation, but a script can spread malware or change settings."],
            ["Remote access", "RDP, VPN, VNC, SSH, RMM, SPICE, WinRM, screen sharing. Know the risks of each."], ["AI basics", "Useful for drafting and search; limits are bias, hallucinations and accuracy; private data does not belong in public tools; follow the acceptable-use policy."]]},
    ],
}
