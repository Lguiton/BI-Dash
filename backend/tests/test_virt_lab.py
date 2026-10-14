import pytest

from app.services import virt_lab as v


def test_capacity_n_plus_1_and_limits():
    r = v.capacity(100, 2, 8, 100, 32, 256, vcpu_ratio=4, headroom_pct=20, ha_spares=1)
    assert r["total_vcpu"] == 200 and r["total_ram_gb"] == 800
    assert r["hosts_for_cpu"] == 2 and r["hosts_for_ram"] == 4     # 800 / (256*0.8) = 3.9 -> 4
    assert r["hosts_working"] == 4 and r["hosts_total"] == 5 and r["survives_one_host_failure"]
    assert r["storage_tb"] == 12.5                                   # 10,000 GB * 1.25
    assert "RAM" in r["notes"][-1]
    z = v.capacity(2, 1, 1, 10, 8, 64, ha_spares=0)
    assert any("No spare host" in n for n in z["notes"]) and z["hosts_total"] == 1
    with pytest.raises(v.VirtError):
        v.capacity(0, 1, 1, 1, 8, 64)
    with pytest.raises(v.VirtError):
        v.capacity("x", 1, 1, 1, 8, 64)


def test_network_flags_the_poster_mistake():
    r = v.check_network([{"name": "Mgmt", "role": "management", "vlan": 10, "subnet": "10.0.10.0/24"},
                         {"name": "VM", "role": "vm", "vlan": 20, "subnet": "10.0.20.0/24"},
                         {"name": "vMotion", "role": "vmotion", "vlan": 20, "subnet": "10.0.30.0/24"}])
    assert not r["ok"] and any("share VLAN 20" in i["text"] for i in r["issues"])
    good = v.check_network([{"name": "M", "role": "management", "vlan": 10, "subnet": "10.0.10.0/24"}, {"name": "V", "role": "vm", "vlan": 20, "subnet": "10.0.20.0/24"},
                            {"name": "vm", "role": "vmotion", "vlan": 30, "subnet": "10.0.30.0/24"}, {"name": "S", "role": "storage", "vlan": 40, "subnet": "10.0.40.0/24"}])
    assert good["ok"] and not [i for i in good["issues"] if i["level"] != "info"]
    ov = v.check_network([{"name": "A", "role": "management", "vlan": 10, "subnet": "10.0.0.0/16"}, {"name": "B", "role": "vm", "vlan": 20, "subnet": "10.0.5.0/24"}])
    assert any("overlaps" in i["text"] for i in ov["issues"])
    for bad in ([{"name": "x", "vlan": 5000}], [{"name": "x", "vlan": "a"}], [{"name": "x", "vlan": 5, "subnet": "nope"}], []):
        with pytest.raises(v.VirtError):
            v.check_network(bad)


def test_cluster_checks():
    r = v.check_cluster([{"name": "esxi01", "cores": 16, "ram_gb": 128, "version": "8.0.2"}, {"name": "esxi02.lab.local", "cores": 8, "ram_gb": 64, "version": "7.0"}])
    t = " ".join(i["text"] for i in r["issues"])
    assert "fully qualified" in t and "Mixed ESXi" in t and "differ" in t and "remains" in t
    assert any("One host" in i["text"] for i in v.check_cluster([{"name": "a.b", "cores": 4, "ram_gb": 16}])["issues"])


def test_runbook_and_endpoints(client):
    assert [s["n"] for s in v.RUNBOOK] == list(range(1, 11))
    c = client.get("/api/it/virt").json()
    assert len(c["runbook"]) == 10 and "VT-x" in c["source_note"]
    r = client.post("/api/it/virt/capacity", json={"vms": 50, "vcpu_per_vm": 2, "ram_per_vm_gb": 8, "disk_per_vm_gb": 100, "host_cores": 16, "host_ram_gb": 128})
    assert r.status_code == 200 and r.json()["hosts_total"] >= 2
    assert client.post("/api/it/virt/capacity", json={"vms": 0, "vcpu_per_vm": 2, "ram_per_vm_gb": 8, "disk_per_vm_gb": 100, "host_cores": 16, "host_ram_gb": 128}).status_code == 400
    assert client.post("/api/it/virt/network", json={"rows": c["example_network"]}).json()["ok"] is False
    assert client.post("/api/it/virt/cluster", json={"rows": c["example_hosts"]}).status_code == 200
