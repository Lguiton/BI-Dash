"""Virtualization planner for the IT track: a 10-step vSphere deployment runbook, a host and storage sizing calculator,
a network plan checker and a cluster consistency check.

Honest limits
* ESXi installs on bare metal and vCenter is a licensed appliance. Neither can run here, so this planner does the thinking
  (sizing, addressing, order of work, what to verify) and points to free ways to practise. It never connects to a host.
* Sizing is a planning estimate from the numbers you enter, with headroom. Measure real load before you buy hardware.
* Product licensing and free-tier terms have changed more than once. Check the vendor's current terms yourself.
"""
from __future__ import annotations

import ipaddress
import math

ROLES = ["management", "vmotion", "storage", "vm", "other"]


class VirtError(Exception):
    pass


def _num(v, name, lo, hi, integer=False):
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise VirtError(f"{name} must be a number.") from None
    if x != x or not lo <= x <= hi:
        raise VirtError(f"{name} must be between {lo:g} and {hi:g}.")
    return int(x) if integer else x


def capacity(vms, vcpu_per_vm, ram_per_vm_gb, disk_per_vm_gb, host_cores, host_ram_gb, vcpu_ratio=4, headroom_pct=20,
             ha_spares=1, thin_ratio=1.0, storage_overhead_pct=25, ram_overcommit=1.0) -> dict:
    vms = _num(vms, "VMs", 1, 5000, True); vc = _num(vcpu_per_vm, "vCPU per VM", 1, 128, True)
    rm = _num(ram_per_vm_gb, "RAM per VM (GB)", 0.5, 4096); dk = _num(disk_per_vm_gb, "Disk per VM (GB)", 1, 100000)
    cores = _num(host_cores, "Cores per host", 2, 512, True); hram = _num(host_ram_gb, "RAM per host (GB)", 8, 24576)
    ratio = _num(vcpu_ratio, "vCPU:core ratio", 1, 16); head = _num(headroom_pct, "Headroom %", 0, 60)
    spares = _num(ha_spares, "Spare hosts for HA", 0, 4, True); thin = _num(thin_ratio, "Thin provisioning ratio", 1, 5)
    ov = _num(storage_overhead_pct, "Storage overhead %", 0, 100); rov = _num(ram_overcommit, "RAM overcommit", 1, 2)
    tv, tr, td = vms * vc, vms * rm, vms * dk
    cpu_per_host = cores * ratio * (1 - head / 100)
    ram_per_host = hram * rov * (1 - head / 100)
    need_cpu, need_ram = math.ceil(tv / cpu_per_host), math.ceil(tr / ram_per_host)
    working = max(need_cpu, need_ram, 1)
    total = working + spares
    if spares and total < 2:
        total = 2
    storage_tb = td / thin * (1 + ov / 100) / 1000
    actual_ratio = tv / (cores * working)
    notes = []
    if spares == 0:
        notes.append("No spare host: if one host fails, HA has nowhere to restart its VMs. Keep at least N+1 for anything that matters.")
    if total < 3:
        notes.append("Two hosts is the minimum for vMotion and HA. Three or more is more comfortable (and vSAN needs three).")
    if ratio > 4:
        notes.append(f"A vCPU:core ratio of {ratio:g} is aggressive. Around 4:1 is a common starting point for mixed servers; databases and busy apps need lower. Measure CPU ready time.")
    if rov > 1:
        notes.append("RAM overcommit relies on ballooning, compression and swapping, which slow VMs. Avoid it for anything that matters.")
    notes.append("The limiting resource was " + ("CPU" if need_cpu > need_ram else "RAM" if need_ram > need_cpu else "CPU and RAM equally") + ". Storage must also keep up with IOPS and latency, which this estimate does not cover.")
    return {"total_vcpu": tv, "total_ram_gb": round(tr, 1), "total_disk_gb": round(td, 1), "hosts_for_cpu": need_cpu, "hosts_for_ram": need_ram,
            "hosts_working": working, "hosts_total": total, "spares": total - working, "storage_tb": round(storage_tb, 2),
            "actual_vcpu_per_core": round(actual_ratio, 2), "ram_used_pct_one_host_down": round(tr / (hram * working) * 100 if working else 0, 1),
            "survives_one_host_failure": total - 1 >= working, "notes": notes,
            "lesson": "Size for the workload with headroom, add a spare host so one failure doesn't take VMs down, then confirm with real measurements."}


def check_network(rows) -> dict:
    if not isinstance(rows, list) or not rows or len(rows) > 30:
        raise VirtError("Give between 1 and 30 networks.")
    issues, clean, nets = [], [], []
    for i, r in enumerate(rows, 1):
        if not isinstance(r, dict):
            raise VirtError("Each network is a row of name, role, VLAN and subnet.")
        name = str(r.get("name") or f"net{i}").strip()[:40]
        role = r.get("role") if r.get("role") in ROLES else "other"
        try:
            vlan = int(r.get("vlan"))
        except (TypeError, ValueError):
            raise VirtError(f"'{name}': VLAN must be a whole number.") from None
        sub = str(r.get("subnet") or "").strip()
        net = None
        if sub:
            try:
                net = ipaddress.ip_network(sub, strict=False)
            except ValueError:
                raise VirtError(f"'{name}': '{sub}' isn't a valid subnet like 10.0.10.0/24.") from None
        if not 0 <= vlan <= 4095:
            raise VirtError(f"'{name}': VLAN must be 0 to 4095.")
        clean.append({"name": name, "role": role, "vlan": vlan, "subnet": str(net) if net else ""})
        nets.append((name, role, vlan, net))
        if vlan in (0, 4095):
            issues.append(("bad", f"{name}: VLAN {vlan} is reserved. Use 2 to 4094."))
        elif vlan == 1:
            issues.append(("warn", f"{name}: VLAN 1 is the default. Use a numbered VLAN so traffic is separated on purpose."))
        if net and net.num_addresses < 8:
            issues.append(("warn", f"{name}: {net} has very few addresses ({max(net.num_addresses - 2, 0)} usable)."))
    for a in range(len(nets)):
        for b in range(a + 1, len(nets)):
            na, ra, va, ia = nets[a]; nb, rb, vb, ib = nets[b]
            if va == vb:
                issues.append(("bad", f"{na} ({ra}) and {nb} ({rb}) share VLAN {va}. Traffic types meant to be separate are then on the same network."
                               + (" vMotion carries live VM memory unencrypted by default on some setups, so keep it on its own VLAN." if "vmotion" in (ra, rb) else "")))
            if ia and ib and ia.version == ib.version and ia.overlaps(ib):
                issues.append(("bad", f"{na} {ia} overlaps {nb} {ib}: routing between them will break."))
    have = {r for _, r, _, _ in nets}
    for need, why in (("management", "ESXi and vCenter management"), ("vmotion", "vMotion (live migration)"), ("vm", "VM traffic")):
        if need not in have:
            issues.append(("warn", f"No {need} network listed: needed for {why}."))
    if "storage" not in have:
        issues.append(("info", "No storage network listed. Fine if you use local disk or vSAN on its own links; iSCSI and NFS usually get their own VLAN."))
    vm_n = [(n, v) for n, r, v, _ in nets if r == "vm"]
    mg = [v for _, r, v, _ in nets if r == "management"]
    for n, v in vm_n:
        if v in mg:
            issues.append(("bad", f"VM network '{n}' is on the management VLAN. A compromised VM would then sit next to your hosts' management interfaces."))
    order = {"bad": 0, "warn": 1, "info": 2}
    out = [{"level": l, "text": t} for l, t in sorted(set(issues), key=lambda x: order[x[0]])]
    return {"networks": clean, "issues": out, "ok": not any(i["level"] == "bad" for i in out),
            "lesson": "Keep management, vMotion, storage and VM traffic on separate VLANs and subnets that don't overlap. Give each its own VMkernel adapter."}


def check_cluster(hosts) -> dict:
    if not isinstance(hosts, list) or not hosts or len(hosts) > 32:
        raise VirtError("List between 1 and 32 hosts.")
    issues, clean = [], []
    for i, h in enumerate(hosts, 1):
        if not isinstance(h, dict):
            raise VirtError("Each host is a name, cores, RAM and version.")
        name = str(h.get("name") or "").strip().lower()[:80]
        if not name:
            raise VirtError(f"Host {i} needs a name.")
        cores = _num(h.get("cores"), f"{name} cores", 1, 1024, True); ram = _num(h.get("ram_gb"), f"{name} RAM (GB)", 1, 24576)
        clean.append({"name": name, "cores": cores, "ram_gb": ram, "version": str(h.get("version") or "").strip()[:20], "cpu": str(h.get("cpu") or "").strip()[:40].lower()})
        if "." not in name:
            issues.append(("warn", f"{name}: use a fully qualified name (like esxi01.lab.local) with matching forward and reverse DNS. vCenter and certificates depend on it."))
    if len({h["name"] for h in clean}) != len(clean):
        issues.append(("bad", "Two hosts have the same name."))
    if len(clean) < 2:
        issues.append(("warn", "One host: no HA and nowhere to vMotion to. Two is the minimum for those features."))
    ver = {h["version"] for h in clean if h["version"]}
    if len(ver) > 1:
        issues.append(("warn", f"Mixed ESXi versions ({', '.join(sorted(ver))}). Run one version across the cluster except briefly while upgrading."))
    if len({h["ram_gb"] for h in clean}) > 1 or len({h["cores"] for h in clean}) > 1:
        issues.append(("warn", "Hosts differ in cores or RAM. HA reserves capacity for the biggest host, so uneven hosts waste capacity."))
    cpus = {h["cpu"] for h in clean if h["cpu"]}
    if len(cpus) > 1:
        issues.append(("warn", "Different CPU models: vMotion can fail between them unless EVC (Enhanced vMotion Compatibility) is on."))
    if len(clean) >= 2:
        big = max(h["ram_gb"] for h in clean); tot = sum(h["ram_gb"] for h in clean)
        issues.append(("info", f"With the largest host ({big:g} GB) down, {tot - big:g} of {tot:g} GB RAM remains ({(tot - big) / tot * 100:.0f}%). Make sure your VMs fit in that."))
    order = {"bad": 0, "warn": 1, "info": 2}
    return {"hosts": clean, "issues": [{"level": l, "text": t} for l, t in sorted(set(issues), key=lambda x: order[x[0]])]}


def _s(n, title, what, do, verify, mistakes, note=""):
    return {"n": n, "title": title, "what": what, "do": do, "verify": verify, "mistakes": mistakes, "note": note}


RUNBOOK = [
    _s(1, "Prepare the bare-metal server", "Hardware ready before any software.", ["Update BIOS/UEFI and firmware.", "Enable hardware virtualization (Intel VT-x or AMD-V) and, if offered, VT-d / IOMMU.", "Build the RAID set or leave disks to vSAN as designed, and confirm the hardware is on the vendor's compatibility list."], ["The BIOS shows virtualization enabled.", "The RAID volume is healthy and the boot disk is visible."], ["Forgetting to enable VT-x/AMD-V.", "Hardware not on the compatibility list."], "The poster's BIOS box reads 'VT-3'. There is no such setting: it is VT-x."),
    _s(2, "Install the ESXi hypervisor", "Put the hypervisor on the metal.", ["Boot the host from the ESXi installer ISO (virtual media or USB).", "Install to the boot device (not a data disk you plan to use for VMs).", "Set a management network adapter, a static IP, gateway, DNS and a fully qualified host name."], ["The host console shows the IP you set.", "You can ping it from your admin PC."], ["Using DHCP for a host.", "Wrong VLAN on the management port."]),
    _s(3, "Access the ESXi host", "Check the host before anything else depends on it.", ["Open https://<host> in a browser (ESXi Host Client).", "Check CPU, memory, datastore and network match the hardware.", "Set the time source (NTP) and a strong root password."], ["Time is correct and NTP is synced.", "All expected NICs and disks appear."], ["Wrong time breaks certificates and Single Sign-On later."]),
    _s(4, "Deploy the vCenter Server Appliance (VCSA)", "The management server for all hosts.", ["Mount the VCSA installer ISO on an admin PC and run the installer.", "Stage 1 deploys the appliance onto a host; stage 2 sets up Single Sign-On (SSO), the system name and the time sync.", "Give it a fully qualified name with forward and reverse DNS, and a static IP."], ["You can log in to the vSphere Client with the SSO administrator.", "DNS lookups work both ways for vCenter and each host."], ["No working DNS (the most common failure).", "Choosing too small an appliance size for the number of hosts and VMs."], "VCSA needs substantial RAM and disk even at its smallest size. Check VMware's current requirements before you start."),
    _s(5, "Add ESXi hosts to vCenter", "Build the inventory.", ["Create a Datacenter object, then a Cluster.", "Add each host (by fully qualified name) to the cluster.", "Do this before turning on cluster features so they apply to every host."], ["Every host shows as connected and not in maintenance mode.", "Hosts show matching ESXi versions."], ["Adding hosts by IP address.", "Mixed CPU generations with no EVC."]),
    _s(6, "Configure networking", "Separate the traffic types.", ["Create a standard or distributed switch.", "Make port groups with VLANs for management, vMotion, storage and VM traffic.", "Add a VMkernel adapter per host for management, vMotion and storage, with at least two uplinks each if you can."], ["Each host can reach the others on the vMotion network.", "VMs on the VM network can reach their gateway."], ["Two traffic types on one VLAN.", "Overlapping subnets.", "A single uplink for everything."], "The poster shows vMotion and VM Network both on VLAN 20. Give each its own VLAN. Use the Network plan checker here to see it flagged."),
    _s(7, "Configure shared storage", "Every host sees the same datastore.", ["Connect NFS, iSCSI or a SAN (or enable vSAN) and present the same LUN or export to all hosts.", "Create the datastore and rescan storage on each host.", "Use multipathing for iSCSI and SAN."], ["Each host lists the datastore as accessible.", "A test VM file can be read from all hosts."], ["Presenting the LUN to only some hosts.", "No separate storage network."]),
    _s(8, "Enable vSphere features", "The reason to cluster: HA, DRS and vMotion.", ["Turn on vSphere HA (restart VMs on another host after a failure) and set admission control for the spare capacity you planned.", "Turn on DRS (Distributed Resource Scheduler: balances VMs across hosts), starting in partially automated mode.", "Test vMotion by moving a running VM between hosts."], ["A test VM moves with no dropped pings.", "HA reports the cluster healthy and the failure test restarts the VM elsewhere."], ["Admission control off, so HA promises capacity it doesn't have.", "Fully automatic DRS before you trust it."], "The poster writes 'Distributed Secure Scheduler': the D in DRS is Distributed Resource Scheduler."),
    _s(9, "Create and deploy virtual machines", "Build once, clone many.", ["Create a VM, install the guest OS and VMware Tools, patch it and make it a template.", "Deploy new VMs from the template with a customization spec.", "Size CPU, RAM and disk to the workload; start small, as you can add later."], ["A VM deployed from the template boots, gets its network and has the right name.", "Tools report as running."], ["Giving every VM 8 vCPUs 'just in case': it slows the others.", "Skipping VMware Tools."]),
    _s(10, "Monitoring, backup and security", "Run it, don't just build it.", ["Set alarms for host, datastore and VM health.", "Set up backup for VMs (not only snapshots) and test a restore.", "Create roles and give people only the permissions they need; use named accounts, not shared root.", "Lock down management access and keep ESXi and vCenter patched."], ["An alarm fires on a test condition.", "You restored a VM from backup and it booted."], ["Treating snapshots as backups.", "Everyone logging in as administrator."]),
]

COMPONENTS = [
    ("ESXi", "The hypervisor that runs on the physical server and hosts the VMs."), ("vCenter Server (VCSA)", "The management server that controls many hosts, and enables clusters, HA, DRS and vMotion."),
    ("Datacenter and cluster", "Inventory objects: a datacenter holds clusters, a cluster pools hosts so features can work across them."), ("Standard / distributed switch", "A virtual switch per host, or one managed centrally across hosts."),
    ("Port group and VLAN", "A named network setting for VMs or VMkernel adapters, tagged with a VLAN id."), ("VMkernel adapter", "The host's own network interface for management, vMotion, storage and similar."),
    ("Datastore (VMFS, NFS, vSAN)", "Where VM files live. Shared across hosts for vMotion and HA to work."), ("HA", "High Availability: restarts VMs on another host if a host fails (VMs restart, so there is a short outage)."),
    ("DRS", "Distributed Resource Scheduler: places and balances VMs by CPU and memory load."), ("vMotion", "Moves a running VM between hosts with no downtime."),
    ("Template", "A prepared VM used to stamp out new, consistent VMs."), ("Snapshot", "A point-in-time state of a VM. Short-term safety net, not a backup."),
]

PRACTICE = [
    {"name": "Nested ESXi in a desktop hypervisor", "how": "Run ESXi as a VM inside VMware Workstation or Fusion, or another hypervisor with nested virtualization, to practise installing and clustering.", "needs": "A PC with plenty of RAM (32 GB is comfortable for a small lab) and CPU virtualization turned on. Check Broadcom's current licensing for personal use."},
    {"name": "Proxmox VE (free, open source)", "how": "A full virtualization platform with clustering, live migration, HA and shared storage. The concepts match vSphere.", "needs": "One or more spare machines, or nested VMs."},
    {"name": "KVM with libvirt / virt-manager", "how": "Linux's built-in hypervisor. Good to learn what a hypervisor does underneath.", "needs": "A Linux machine with VT-x/AMD-V."},
    {"name": "VMware Hands-on Labs", "how": "VMware offers free browser-based labs for vSphere. Availability changes: check the vendor's site.", "needs": "A browser and a free account."},
    {"name": "VirtualBox", "how": "Free desktop hypervisor for learning VM basics (templates, snapshots, networks). Not for vSphere clustering.", "needs": "Any recent PC."},
]
NOT_AVAILABLE = [
    "Installing or running ESXi: it needs bare metal or nested virtualization on your own machine, and a licence.",
    "Deploying or managing vCenter (VCSA), vSphere HA, DRS, vMotion, vSAN or NSX: all need the real products.",
    "Connecting to your hosts or reading their state. This planner only does sizing, checks and a runbook from what you type.",
    "Hyper-V, Citrix and other hypervisors beyond the general ideas.",
]


def catalog() -> dict:
    return {"runbook": RUNBOOK, "components": [{"name": n, "what": w} for n, w in COMPONENTS], "practice": PRACTICE, "not_available": NOT_AVAILABLE, "roles": ROLES,
            "example_network": [{"name": "Management", "role": "management", "vlan": 10, "subnet": "10.0.10.0/24"}, {"name": "VM Network", "role": "vm", "vlan": 20, "subnet": "10.0.20.0/24"}, {"name": "vMotion", "role": "vmotion", "vlan": 20, "subnet": "10.0.30.0/24"}, {"name": "Storage", "role": "storage", "vlan": 40, "subnet": "10.0.40.0/24"}],
            "example_hosts": [{"name": "esxi01.lab.local", "cores": 16, "ram_gb": 128, "version": "8.0.2"}, {"name": "esxi02.lab.local", "cores": 16, "ram_gb": 128, "version": "8.0.2"}, {"name": "esxi03.lab.local", "cores": 16, "ram_gb": 128, "version": "8.0.2"}],
            "source_note": "Based on a 10-step vSphere deployment infographic. Three slips in it are corrected here: 'VT-3' should be VT-x, DRS is the Distributed Resource Scheduler, and vMotion and the VM network are shown on the same VLAN 20. Sizing is a planning estimate, not a measurement."}
