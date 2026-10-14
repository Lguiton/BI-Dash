import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "apache_practice"


def test_lists_three_tools(client):
    tools = client.get("/api/apache/tools").json()["tools"]
    assert [t["id"] for t in tools] == ["spark", "airflow", "superset"]
    for t in tools:
        assert t["summary"] and t["files"] and t["steps"]
        for f in t["files"]:
            assert f["content"].strip()


def test_file_content_matches_disk(client):
    spark = next(t for t in client.get("/api/apache/tools").json()["tools"] if t["id"] == "spark")
    disk = (ROOT / "spark" / "01_spark_basics.py").read_text(encoding="utf-8")
    assert spark["files"][0]["content"] == disk


def _load_steps():
    spec = importlib.util.spec_from_file_location("etl_steps", ROOT / "airflow" / "etl_steps.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_transform_and_quality_gate(tmp_path, monkeypatch):
    steps = _load_steps()
    monkeypatch.setattr(steps, "WORK", tmp_path)
    raw = tmp_path / "raw.csv"
    raw.write_text(
        "fact_id,record_date,entity_id,revenue,operational_cost\n"
        "F1,2026-01-01,E1,10,4\nF1,2026-01-01,E1,10,4\nF2,2026-01-02,E1,,4\nF3,2026-01-03,E1,8,3\n",
        encoding="utf-8")
    stats = steps.transform(str(raw), "t")
    assert stats["rows_out"] == 2 and stats["dropped"] == {"missing_required": 1, "duplicate": 1}
    import pytest
    with pytest.raises(ValueError):  # 50% dropped > 5% limit
        steps.validate(stats)
    assert steps.validate({"rows_in": 100, "rows_out": 99})["rows_out"] == 99
