import pytest

from app.services import it_shell as sh


@pytest.fixture(autouse=True)
def _fresh(client):
    client.post("/api/itshell/reset")


def run(client, c):
    r = client.post("/api/itshell/run", json={"command": c})
    assert r.status_code == 200, r.text
    return r.json()


def test_view_and_unknown(client):
    v = client.get("/api/itshell").json()
    assert v["total"] == len(sh.TASKS) == 11 and v["done"] == 0 and "~" in v["prompt"] and "simulation" in v["limits"]
    assert "command not found" in run(client, "frobnicate")["error"]
    assert "not available" in run(client, "curl http://x")["error"]
    assert client.post("/api/itshell/run", json={"command": " "}).status_code == 400


def test_navigation_and_files(client):
    assert run(client, "pwd")["output"] == "/home/student"
    assert "data.txt" in run(client, "ls")["output"]
    assert "-rw-r--r--" in run(client, "ls -l secret.txt")["output"]
    run(client, "mkdir -p a/b")
    assert run(client, "cd a/b")["cwd"] == "/home/student/a/b"
    assert run(client, "cd ../..")["cwd"] == "/home/student"
    run(client, "echo hi there > a/f.txt")
    assert run(client, "cat a/f.txt")["output"] == "hi there"
    run(client, "echo more >> a/f.txt")
    assert run(client, "wc -l a/f.txt")["output"].startswith("2")
    run(client, "cp -r a b")
    assert run(client, "ls b")["output"].strip()
    assert "is a directory" in run(client, "rm a")["error"].lower() or "-r" in run(client, "rm a")["error"]
    assert run(client, "rm -r a")["error"] is None
    assert "No such file" in run(client, "cat a/f.txt")["error"]


def test_pipes_and_grep(client):
    assert run(client, "grep ERROR /var/log/app.log | wc -l")["output"] == "3"
    assert run(client, "grep -c error /var/log/app.log")["output"] == "0"
    assert run(client, "grep -ic error /var/log/app.log")["output"] == "3"
    assert run(client, "cat /var/log/app.log | grep ERROR | sort | uniq")["output"].count("\n") == 1
    assert run(client, "echo 'a > b'")["output"] == "a > b"


def test_permissions_enforced(client):
    run(client, "chmod 000 secret.txt")
    assert "Permission denied" in run(client, "cat secret.txt")["error"]
    assert run(client, "sudo cat secret.txt")["error"] is None
    run(client, "chmod u+r secret.txt")
    assert run(client, "cat secret.txt")["error"] is None
    assert "Operation not permitted" in run(client, "chown bob shared.txt")["error"]
    assert run(client, "sudo chown bob:staff shared.txt")["error"] is None
    assert "bob staff" in run(client, "ls -l shared.txt")["output"]
    assert "Permission denied" in run(client, "echo x > /etc/hosts")["error"]
    assert "protects" in run(client, "rm -rf /home/student")["error"]
    assert "invalid" in run(client, "chmod zz data.txt")["error"].lower()
    run(client, "chmod 1777 team")
    assert "rwxrwxrwt" in run(client, "ls -ld team")["output"]


def test_all_tasks_can_be_solved_and_persist(client):
    seen = []
    for t in sh.TASKS:
        sol = client.get(f"/api/itshell/solution?task={t[0]}").json()["command"]
        r = run(client, sol)
        assert r["error"] is None, (t[0], r)
        seen += r["newly_done"]
    assert set(seen) == {t[0] for t in sh.TASKS}
    v = client.get("/api/itshell").json()
    assert v["done"] == v["total"] and all(x["done"] for x in v["tasks"])
    assert client.get("/api/itshell/solution?task=nope").status_code == 404
    client.post("/api/itshell/reset")
    assert client.get("/api/itshell").json()["done"] == 0


def test_wrong_attempts_do_not_pass(client):
    assert run(client, "chmod 644 secret.txt")["newly_done"] == []
    assert run(client, "chmod 700 deploy.sh")["newly_done"] == []
    assert run(client, "mkdir report")["newly_done"] == []
    assert run(client, "grep error /var/log/app.log > errors.txt")["newly_done"] == []
    assert run(client, "cat users.csv")["newly_done"] == []
