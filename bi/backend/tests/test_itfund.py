import pytest

from app.services import it_fund as f


def test_convert():
    r = f.convert("87")
    assert r["binary"] == "0101 0111" and r["hex"] == "57" and r["sum"] == "64 + 16 + 4 + 2 + 1" and r["ascii"] == "W"
    assert f.convert("01010111", "binary")["decimal"] == 87
    assert f.convert("0xFF", "hex")["decimal"] == 255 and f.convert("179")["binary"] == "1011 0011"
    for bad in [("", "decimal"), ("12", "binary"), ("-1", "decimal"), ("1", "base3"), ("9" * 30, "decimal")]:
        with pytest.raises(f.FundError):
            f.convert(*bad)


def test_encode():
    r = f.encode_text("Aé€")
    assert [x["bytes"] for x in r["rows"]] == [1, 2, 3] and r["rows"][0]["utf8_hex"] == "41" and r["total_bytes"] == 6
    with pytest.raises(f.FundError):
        f.encode_text("")


def test_gates_and_circuit():
    assert [x["out"] for x in f.gate_table("nand")["rows"]] == [1, 1, 1, 0]
    assert [x["out"] for x in f.gate_table("XOR")["rows"]] == [0, 1, 1, 0]
    c = f.circuit("(A AND B) OR NOT C")
    assert len(c["rows"]) == 8 and c["inputs"] == ["A", "B", "C"]
    assert [x["out"] for x in f.circuit("A xnor B")["rows"]] == [1, 0, 0, 1]
    assert f.circuit("A OR A")["reading"] != "Always 1."
    for bad in ["", "A AND", "(A OR B", "AND B", "A B", "A; import os", "A AND B AND C AND D AND E"]:
        with pytest.raises(f.FundError):
            f.circuit(bad)


def test_storage():
    r = f.storage(1, "TB")
    assert r["drive"]["as_gib"] == pytest.approx(931.32, abs=0.01) and r["drive"]["difference_pct"] == pytest.approx(9.05, abs=0.01)
    r2 = f.storage(1000, "GB")
    assert r2["drive"]["as_gib"] == pytest.approx(931.32, abs=0.01)
    with pytest.raises(f.FundError):
        f.storage(1, "XB")
    with pytest.raises(f.FundError):
        f.storage(-1, "GB")


def test_chmod():
    r = f.chmod("754")
    assert r["symbolic"] == "rwxr-xr--" and f.chmod("rwxr-xr--")["octal"] == "754"
    assert f.chmod("1775")["symbolic"] == "rwxrwxr-t" and f.chmod("1775")["special"]["sticky"]
    assert f.chmod("4755")["symbolic"] == "rwsr-xr-x" and f.chmod("rwsr-xr-x")["octal"] == "4755"
    assert f.chmod("-rw-r--r--")["octal"] == "644"
    assert f.chmod("777")["warnings"]
    assert f.chmod("644", "file", "022")["umask"]["new_mode"] == "644" and f.chmod("755", "dir", "077")["umask"]["new_mode"] == "700"
    assert f.chmod("175")["symbolic"] == "--xrwxr-x"
    for bad in ["999", "rwx", "", "8"]:
        with pytest.raises(f.FundError):
            f.chmod(bad)


def test_ipv6():
    r = f.ipv6("2001:0db8:0000:0000:0000:0000:0000:0001")
    assert r["compressed"] == "2001:db8::1" and "documentation" in r["type"] and r["network_64"] == "2001:db8::/64"
    assert "link-local" in f.ipv6("fe80::1")["type"] and "loopback" in f.ipv6("::1")["type"] and "unique local" in f.ipv6("fd00::1")["type"]
    with pytest.raises(f.FundError):
        f.ipv6("192.168.1.1")


def test_commands_and_reference(client):
    assert f.commands("chmod")["rows"] and not f.commands("zzzz")["rows"]
    assert f.commands("")["total"] == len(f.CMDS) >= 40
    assert all(len(r) == 4 for r in f.CMDS)
    r = client.get("/api/itfund").json()
    assert set(r["topics"]) == {"connections", "wireless", "cellular_iot", "cloud", "services", "sysadmin", "hardware", "connectors", "disks", "desktop_apps"} and len(r["slips"]) >= 4
    assert client.get("/api/itfund?topic=nope").status_code == 404
    assert client.post("/api/itfund/convert", json={"value": "255", "base": "decimal"}).json()["hex"] == "FF"
    assert client.post("/api/itfund/convert", json={"value": "xyz", "base": "binary"}).status_code == 400
    assert client.post("/api/itfund/circuit", json={"text": "A AND B"}).json()["ones"] == 1
    assert client.get("/api/itfund/gate?name=OR").json()["rows"][3]["out"] == 1
    assert client.get("/api/itfund/gate?name=FOO").status_code == 400
    assert client.post("/api/itfund/chmod", json={"mode": "640"}).json()["symbolic"] == "rw-r-----"
    assert client.post("/api/itfund/storage", json={"value": 1, "unit": "TB"}).status_code == 200
    assert client.post("/api/itfund/ipv6", json={"address": "::1"}).status_code == 200
    assert client.get("/api/itfund/commands?q=disk").json()["rows"]
