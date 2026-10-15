"""How-to videos: link recognising, uploads, chapters, notes, and related lessons for a job."""
import pytest

from app.services import howto


def _link(client, **kw):
    body = {"title": "Replace a laptop screen", "url": "https://youtu.be/dQw4w9WgXcQ", "field": "IT support and repair", **kw}
    return client.post("/api/howto/link", json=body)


@pytest.mark.parametrize("url,kind,embed", [
    ("https://youtu.be/dQw4w9WgXcQ?t=5", "youtube", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ&list=x", "youtube", "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"),
    ("https://youtube.com/shorts/abcdefghijk", "youtube", "https://www.youtube-nocookie.com/embed/abcdefghijk"),
    ("https://vimeo.com/123456789", "vimeo", "https://player.vimeo.com/video/123456789"),
    ("https://example.com/files/fix.mp4", "page", ""),
    ("https://example.com/blog/fix-a-router", "page", ""),
])
def test_classify(url, kind, embed):
    c = howto.classify(url)
    assert c["kind"] == kind and c["embed"] == embed


@pytest.mark.parametrize("bad", ["", "javascript:alert(1)", "ftp://x.com/a.mp4", "youtube.com/watch?v=abc", "https://www.youtube.com/watch?v=<script>"])
def test_bad_links_refused(client, bad):
    assert _link(client, url=bad).status_code == 400


def test_add_list_update_delete(client):
    v = _link(client).json()
    assert v["kind"] == "youtube" and v["field"] == "IT support and repair" and v["watched"] is False
    got = client.get("/api/howto").json()
    assert got["total"] == 1 and "Other" in got["fields"] and "IT support and repair" in got["fields"]
    r = client.put(f"/api/howto/{v['id']}", json={"watched": True, "rewatch": True, "notes": "Use the plastic pry tool. password: hunter2hunter2",
                                                  "chapters": [{"t": "1:05", "label": "Remove bezel"}, {"t": "0:10", "label": "Tools"}]}).json()
    assert r["watched"] and r["rewatch"]
    assert [c["t"] for c in r["chapters"]] == [10, 65]
    assert "hunter2hunter2" not in r["notes"]
    assert client.get("/api/howto").json()["watched"] == 1
    assert client.delete(f"/api/howto/{v['id']}").status_code == 200
    assert client.delete(f"/api/howto/{v['id']}").status_code == 404
    assert client.put("/api/howto/999", json={}).status_code == 404


def test_title_required_and_chapter_validation(client):
    assert _link(client, title="  ").status_code == 400
    v = _link(client).json()
    for bad in ([{"t": "99:99:99", "label": "x"}], [{"t": "1:05", "label": ""}], [{"t": "abc", "label": "x"}], "nope", [{"t": 1, "label": "x"}] * 41):
        assert client.put(f"/api/howto/{v['id']}", json={"chapters": bad}).status_code == 400


def test_no_upload_and_nothing_stored(client):
    assert client.post("/api/howto/upload", files={"file": ("a.mp4", b"abc", "video/mp4")}, data={"title": "x"}).status_code in (404, 405)
    v = _link(client).json()
    assert client.get(f"/api/howto/{v['id']}/file").status_code in (404, 405)
    assert "source" not in v and "play_url" not in v


def test_for_job_matches_title_words(client):
    cl = client.post("/api/clients", json={"name": "Practice Co"}).json()
    j = client.post("/api/clients/jobs/add", json={"client_id": cl["id"], "title": "Replace laptop screen for Sam", "quote": 150}).json()
    a = _link(client).json()
    _link(client, title="Set up a firewall", field="Network engineering")
    got = client.get(f"/api/howto/for-job/{j['id']}").json()["videos"]
    assert [x["id"] for x in got] == [a["id"]]
    assert client.get("/api/howto/for-job/9999").status_code == 404
