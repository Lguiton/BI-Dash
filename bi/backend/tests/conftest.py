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


@pytest.fixture(scope="session")
def _clean_template(tmp_path_factory):
    """Import the clean sample CSV once per test run. Importing it takes about 8 seconds, and 35 tests need it."""
    import pathlib
    d = tmp_path_factory.mktemp("clean_template")
    mp = pytest.MonkeyPatch()
    mp.setenv("BI_DB_PATH", str(d / "t.duckdb"))
    mp.setenv("BI_SEED_DEMO", "1")
    mp.setenv("BI_SCHEDULER", "0")
    state.close_all()
    db.close_connection()
    try:
        from app.main import app
        root = pathlib.Path(__file__).resolve().parents[2]
        csv = root / "data_samples" / "operations_clean.csv"
        if not csv.exists():
            import subprocess
            import sys
            subprocess.run([sys.executable, str(root / "scripts" / "generate_sample_data.py")], check=True)
        with TestClient(app) as c:
            assert c.post("/api/ingest/csv?mode=replace", files={"file": ("d.csv", csv.read_bytes(), "text/csv")}).status_code == 200
        db.close_connection()
        state.close_all()
    finally:
        mp.undo()
    return d / "t.duckdb", d / "t_state.sqlite"


@pytest.fixture()
def load_clean(client, _clean_template):
    """Call it to get the clean sample loaded into this test's databases, the same result as the CSV import but instant."""
    import shutil

    from app.config import db_path, state_path

    def load():
        duck, sql = _clean_template
        with db.exclusive():
            shutil.copyfile(duck, db_path())
        state.close_all()
        shutil.copyfile(sql, state_path())
        return client
    return load


# Tests that are slow because they train several models or work on a large table. Everything that uses the imported
# sample year (the load_clean fixture) is marked automatically. "pytest -m 'not slow'" is the quick tier.
SLOW_BY_NAME = {
    "test_scatter_samples_large_selections_deterministically", "test_exercises_also_work_on_larger_data", "test_neural_net_trains_alone_and_warns_about_class_balance",
    "test_mlflow_copy_is_optional_and_works_when_installed", "test_predict_classification_regression_and_guards", "test_endpoints_cover_all_four_types",
    "test_clean_generated_data_imports_and_has_findable_anomalies", "test_generate_benchmark_and_cleanup",
}


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "load_clean" in item.fixturenames or getattr(item, "originalname", item.name) in SLOW_BY_NAME:
            item.add_marker(pytest.mark.slow)
