from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_tools, cloud_lab

c = TestClient(app)


def test_reference_has_all_models_and_responsibility():
    r = c.get("/api/cloud/reference").json()
    ids = {m["id"] for m in r["models"]}
    assert {"iaas", "paas", "saas", "dbaas", "faas", "caas", "baas", "daas-desktop", "daas-data", "secaas", "idaas", "draas", "naas", "staas", "aiaas", "xaas", "iac"} <= ids
    for m in r["models"]:
        assert m["what"] and m["you_manage"] and m["watch_out"] and m["small_business"]
    saas = next(x for x in r["responsibility"]["rows"] if x["model"] == "SaaS")
    assert next(x for x in saas["cells"] if x["layer"] == "Data")["who"] == "you"
    onprem = next(x for x in r["responsibility"]["rows"] if x["model"].startswith("On-prem"))
    assert all(x["who"] == "you" for x in onprem["cells"])


def test_pick():
    assert c.post("/api/cloud/pick", json={"need": "database for a booking app"}).json()["matches"][0]["id"] == "dbaas"
    assert c.post("/api/cloud/pick", json={"need": "email for 8 people office"}).json()["matches"][0]["id"] == "saas"
    assert c.post("/api/cloud/pick", json={"need": ""}).status_code == 400


BAD = '''resource "aws_security_group" "x" {
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
resource "aws_s3_bucket" "b" { acl = "public-read" }
resource "aws_db_instance" "d" {
  publicly_accessible = true
  password = "SuperSecret123"
  storage_encrypted = false
}
''' + 'access_key = "AKIA' + 'ABCDEFGHIJKLMNOP"\n'


def test_review_flags_risks_and_hides_secrets():
    r = c.post("/api/cloud/review", json={"text": BAD}).json()
    probs = " ".join(f["problem"] for f in r["findings"])
    for word in ("sensitive port", "public", "reachable from the internet", "Encryption", "AWS access key", "hard-coded"):
        assert word in probs
    assert r["counts"]["high"] >= 5
    assert "SuperSecret123" not in str(r) and ("AKIA" + "ABCDEFGHIJKLMNOP") not in str(r)


def test_review_clean_and_templates_pass_reviewer():
    for t in cloud_lab.TEMPLATES:
        if t["id"] in ("tf", "ans-linux", "ans-win", "net-backup"):
            r = cloud_lab.review(t["text"])
            assert r["counts"]["high"] == 0, (t["id"], r["findings"])
    assert c.post("/api/cloud/review", json={"text": "x"}).status_code == 400
    assert c.post("/api/cloud/review", json={"text": "a" * 30000}).status_code == 400


def test_iac_content_and_quiz():
    j = c.get("/api/cloud/iac").json()
    assert j["lesson"] and j["templates"] and len(j["checklist"]) >= 10
    q = c.get("/api/cloud/quiz").json()
    assert "answer" not in str(q) and len(q["questions"]) == len(cloud_lab.QUIZ)
    perfect = {str(i): a for i, (_, _, a, _) in enumerate(cloud_lab.QUIZ)}
    assert c.post("/api/cloud/quiz/grade", json={"answers": perfect}).json()["passed"] is True
    assert c.post("/api/cloud/quiz/grade", json={"answers": {}}).json()["passed"] is False


def test_agent_tools():
    for tr in ("itsupport", "network", "security"):
        txt, err = agent_tools.run_tool(tr, {"tool": "iac_review", "args": {"text": BAD}})
        assert not err and "sensitive port" in txt
    txt, err = agent_tools.run_tool("itsupport", {"tool": "cloud_pick", "args": {"need": "database for an app"}})
    assert not err and "DBaaS" in txt
