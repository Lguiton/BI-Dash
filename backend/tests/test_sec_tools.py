import base64
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.services import known_errors, sec_tools as st
from app.services.security import SecError


def _b(d):
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def test_jwt_findings_and_signature():
    r = st.jwt_inspect(_b({"alg": "none"}) + "." + _b({"sub": "x", "password": "p"}) + ".")
    msgs = " ".join(f["finding"] for f in r["findings"])
    assert "unsigned" in msgs and "No expiry" in msgs and "password" in msgs
    h = _b({"alg": "HS256"}) + "." + _b({"exp": 9999999999, "iss": "a", "aud": "b", "sub": "c"})
    sig = base64.urlsafe_b64encode(hmac.new(b"k", h.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    assert st.jwt_inspect(h + "." + sig, "k")["signature_checked"] is True
    assert st.jwt_inspect(h + "." + sig, "z")["signature_checked"] is False
    for bad in ("abc", "a.b.c", ""):
        with pytest.raises(SecError):
            st.jwt_inspect(bad)


def test_cert_inspector():
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID
    key = rsa.generate_private_key(65537, 2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "lab.test")])
    now = datetime.now(timezone.utc)
    c = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key()).serial_number(1)
         .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=10))
         .add_extension(x509.SubjectAlternativeName([x509.DNSName("lab.test")]), False).sign(key, hashes.SHA256()))
    pem = c.public_bytes(serialization.Encoding.PEM).decode()
    r = st.cert_inspect(pem)
    assert r["names"] == ["lab.test"] and r["key"] == "RSA 2048 bits" and 9 <= r["days_left"] <= 10
    assert any("Expires in" in f["finding"] for f in r["findings"]) and any("Self-issued" in f["finding"] for f in r["findings"])
    with pytest.raises(SecError):
        st.cert_inspect("-----BEGIN " + "PRIVATE KEY-----\nabc\n-----END " + "PRIVATE KEY-----")
    with pytest.raises(SecError):
        st.cert_inspect("nope")


def test_cvss_known_scores():
    assert st.cvss31("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H")["base_score"] == 9.8
    assert st.cvss31("AV:N/AC:L/PR:N/UI:R/S:C/C:L/I:L/A:N")["base_score"] == 6.1
    assert st.cvss31("AV:N/AC:H/PR:N/UI:N/S:C/C:H/I:H/A:H")["base_score"] == 9.0
    assert st.cvss31("AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N")["severity"] == "None"
    with pytest.raises(SecError):
        st.cvss31("AV:N")


def test_stride_and_scanner():
    r = st.stride(st.STRIDE_SAMPLE)
    assert r["total_questions"] == 2 + 6 + 4 + 3 + 3
    with pytest.raises(SecError):
        st.stride("x | wizard")
    f = st.code_scan(st.CODE_SAMPLE)["findings"]
    assert {x["line"] for x in f} == {2, 3, 4, 5, 6}
    assert "hunter2hunter2" not in json.dumps(f)
    assert st.code_scan("x = 1\n")["findings"] == []


def test_sigma_and_playbook():
    r = st.sigma(**st.SIGMA_SAMPLE)
    assert r["matches"] == 1 and r["hits"][0]["line"] == 1
    with pytest.raises(SecError):
        st.sigma("title: x", "{}")
    with pytest.raises(SecError):
        st.sigma("detection:\n  a:\n    x: 1\n  condition: b", '{"x": 1}')
    p = st.playbook(**st.PLAYBOOK_SAMPLE)
    assert p["fired"] == 2 and p["log"][0]["actions"][2]["status"].startswith("waiting for approval")
    assert p["log"][2]["actions"][0]["status"] == "skipped"
    with pytest.raises(SecError):
        st.playbook("when severity >= high -> launch_missiles", "{}")


def test_endpoints_and_sources(client):
    ref = client.get("/api/sectools/reference").json()
    assert client.post("/api/sectools/cvss", json={"vector": ref["samples"]["cvss"]}).json()["base_score"] == 9.8
    assert client.post("/api/sectools/sigma", json=ref["samples"]["sigma"]).json()["matches"] == 1
    assert client.post("/api/sectools/jwt", json={"token": "x"}).status_code == 400
    assert "sec_tools" in known_errors.SOURCES and len(st.SLIPS) == 4
