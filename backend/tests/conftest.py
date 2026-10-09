import pytest
from fastapi.testclient import TestClient

from app.services import db, state


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BI_DB_PATH", str(tmp_path / "test.duckdb"))
    monkeypatch.setenv("BI_SEED_DEMO", "1")
    monkeypatch.setenv("BI_SCHEDULER", "0")
    state.close_all()
    db.close_connection()
    from app.main import app
    with TestClient(app) as c:  # runs lifespan -> init_bi_schema
        yield c
    db.close_connection()
    state.close_all()


def csv_file(text: str, name="data.csv"):
    return {"file": (name, text.encode(), "text/csv")}
