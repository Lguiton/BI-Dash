import sys
from pathlib import Path

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import medallion  # noqa: E402

HEADER = "fact_id,record_date,entity_id,entity_name,category,revenue,operational_cost,units_processed,duration_minutes,status,baseline_target\n"


def write(p, rows):
    p.write_text(HEADER + "\n".join(rows) + "\n")
    return p


def count(lake, rel):
    return duckdb.sql(f"select count(*) from read_parquet('{(lake / rel).as_posix()}')").fetchone()[0]


@pytest.fixture
def lake(tmp_path):
    return tmp_path / "lake"


def test_bad_rows_are_quarantined_not_dropped(tmp_path, lake):
    src = write(tmp_path / "a.csv", [
        "F1,2026-01-01,ent-01,Zone A,Logistics,100,40,10,60,Completed,50",
        "F2,not-a-date,ENT-01,Zone A,Logistics,100,40,10,60,Completed,50",
        "F3,2026-01-01,ENT-01,Zone A,Logistics,-5,40,10,60,Completed,50",
        "F4,2026-01-01,ENT-01,Zone A,Logistics,100,40,10,60,Bogus,50"])
    s = medallion.run(src, lake)
    assert s["silver_rows"] == 1 and s["quarantined"] == 3
    assert duckdb.sql(f"select entity_id from read_parquet('{(lake/'silver'/'ops.parquet').as_posix()}')").fetchone()[0] == "ENT-01"


def test_rerun_is_idempotent(tmp_path, lake):
    src = write(tmp_path / "a.csv", [f"F{i},2026-01-0{i},ENT-01,Zone A,Logistics,100,40,10,60,Completed,50" for i in range(1, 5)])
    first = medallion.run(src, lake)
    second = medallion.run(src, lake)
    assert first["silver_rows"] == second["silver_rows"] == 4
    assert count(lake, "gold/daily.parquet") == 4


def test_incremental_load_only_reads_new_days(tmp_path, lake):
    src = write(tmp_path / "a.csv", ["F1,2026-01-01,ENT-01,Zone A,Logistics,100,40,10,60,Completed,50",
                                     "F2,2026-01-02,ENT-01,Zone A,Logistics,100,40,10,60,Completed,50"])
    medallion.run(src, lake)
    write(src, ["F1,2026-01-01,ENT-01,Zone A,Logistics,100,40,10,60,Completed,50",
                "F2,2026-01-02,ENT-01,Zone A,Logistics,100,40,10,60,Completed,50",
                "F3,2026-01-03,ENT-01,Zone A,Logistics,100,40,10,60,Completed,50"])
    s = medallion.run(src, lake)
    assert s["watermark_before"] == "2026-01-02" and s["bronze_rows"] == 2  # F2 (watermark day) + F3
    assert s["silver_rows"] == 3 and s["watermark_after"] == "2026-01-03"


def test_late_correction_replaces_old_value(tmp_path, lake):
    src = write(tmp_path / "a.csv", ["F1,2026-01-01,ENT-01,Zone A,Logistics,100,40,10,60,Completed,50"])
    medallion.run(src, lake)
    write(src, ["F1,2026-01-01,ENT-01,Zone A,Logistics,150,40,10,60,Completed,50"])
    medallion.run(src, lake)
    rev = duckdb.sql(f"select revenue from read_parquet('{(lake/'silver'/'ops.parquet').as_posix()}')").fetchone()[0]
    assert rev == 150 and count(lake, "silver/ops.parquet") == 1


def test_real_sample_files(lake):
    clean = medallion.run(medallion.DEFAULT_SOURCE, lake, reset=True)
    assert clean["quarantined"] == 0 and clean["silver_rows"] > 3000
    messy = medallion.run(medallion.DEFAULT_SOURCE.with_name("operations_messy.csv"), lake, reset=True)
    assert messy["quarantined"] > 0 and messy["silver_rows"] < messy["bronze_rows"]  # dirty rows and duplicates both removed
