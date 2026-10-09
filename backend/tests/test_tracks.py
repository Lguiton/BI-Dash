from pathlib import Path

from app.routers import tracks

ROOT = Path(__file__).resolve().parents[2]


def test_five_tracks(client):
    ts = client.get("/api/tracks").json()["tracks"]
    assert [t["id"] for t in ts] == ["analyst", "scientist", "ml", "engineering", "ai"]
    assert all(t["tools"] and t["path"] and t["projects"] for t in ts)


def test_every_reference_exists_on_disk():
    pages = {"/"} | {"/" + p.parent.name for p in (ROOT / "frontend/src/app").glob("*/page.tsx")}
    for t in tracks.TRACKS:
        for step in t["path"]:
            if step["kind"] == "file":
                assert (ROOT / step["path"]).is_file(), step["path"]
            elif step["kind"] == "notebook":
                assert (ROOT / "python_practice/notebooks" / f"{step['label']}.ipynb").is_file(), step["label"]
            else:
                assert step["href"] in pages, step["href"]
        for f in t["files"]:
            assert (ROOT / f).is_file(), f


def test_file_endpoint_is_allow_listed(client):
    ok = client.get("/api/tracks/file", params={"path": "data_engineering/medallion.py"})
    assert ok.status_code == 200 and ok.json()["language"] == "python" and "bronze" in ok.json()["content"]
    for bad in ["backend/.env", "../../etc/passwd", "backend/app/main.py", "data_engineering/../backend/app/main.py"]:
        assert client.get("/api/tracks/file", params={"path": bad}).status_code == 404
