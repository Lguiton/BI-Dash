"""Runs only when a PostgreSQL server is reachable at PG_DSN (default: the docker-compose database)."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

psycopg = pytest.importorskip("psycopg")
DSN = os.environ.get("PG_DSN", "postgresql://postgres:bi_practice@127.0.0.1:5433/bi")
HERE = Path(__file__).resolve().parents[1]

try:
    psycopg.connect(DSN, connect_timeout=3).close()
except Exception:
    pytest.skip("no PostgreSQL reachable at PG_DSN (run: docker compose up -d)", allow_module_level=True)


@pytest.fixture(scope="module")
def conn():
    subprocess.run([sys.executable, str(HERE / "load_data.py")], check=True, env={**os.environ, "PG_DSN": DSN})
    with psycopg.connect(DSN, autocommit=True) as c:
        yield c


def test_load_and_margin_is_ratio_of_sums(conn):
    assert conn.execute("SELECT count(*) FROM bi.fact_operations").fetchone()[0] == 3650
    m = conn.execute("SELECT 100 * sum(revenue - operational_cost) / sum(revenue) FROM bi.fact_operations").fetchone()[0]
    assert 70 < float(m) < 80


def test_constraints_reject_bad_rows(conn):
    for sql in ("INSERT INTO bi.fact_operations VALUES ('X1','2026-01-01','NOPE',1,1,1,1,'Completed')",
                "INSERT INTO bi.fact_operations VALUES ('X2','2026-01-01','ENT-01',-1,1,1,1,'Completed')",
                "INSERT INTO bi.fact_operations SELECT * FROM bi.fact_operations LIMIT 1"):
        with pytest.raises(psycopg.errors.IntegrityError):
            conn.execute(sql)


def test_index_changes_the_plan_on_a_selective_query(conn):
    q = "EXPLAIN SELECT * FROM bi.fact_operations WHERE fact_id = 'F-000100'"
    assert "Index" in "\n".join(r[0] for r in conn.execute(q).fetchall())        # primary key index
    conn.execute("DROP INDEX IF EXISTS bi.idx_fact_date")
    conn.execute("CREATE INDEX idx_fact_date ON bi.fact_operations (record_date)")
    conn.execute("SET enable_seqscan = off")
    plan = "\n".join(r[0] for r in conn.execute("EXPLAIN SELECT * FROM bi.fact_operations WHERE record_date = DATE '2026-03-15'").fetchall())
    conn.execute("RESET enable_seqscan")
    assert "idx_fact_date" in plan


def test_read_only_role(conn):
    conn.execute("DROP ROLE IF EXISTS analyst_t")
    conn.execute("CREATE ROLE analyst_t")
    conn.execute("GRANT USAGE ON SCHEMA bi TO analyst_t")
    conn.execute("GRANT SELECT ON ALL TABLES IN SCHEMA bi TO analyst_t")
    try:
        conn.execute("SET ROLE analyst_t")
        assert conn.execute("SELECT count(*) FROM bi.fact_operations").fetchone()[0] == 3650
        with pytest.raises(psycopg.errors.InsufficientPrivilege):
            conn.execute("DELETE FROM bi.fact_operations")
    finally:
        conn.execute("RESET ROLE")
        conn.execute("REVOKE ALL ON ALL TABLES IN SCHEMA bi FROM analyst_t")
        conn.execute("REVOKE ALL ON SCHEMA bi FROM analyst_t")
        conn.execute("DROP ROLE analyst_t")


def test_messy_file_is_rejected_by_constraints():
    r = subprocess.run([sys.executable, str(HERE / "load_data.py"), "--messy"], capture_output=True, text=True, env={**os.environ, "PG_DSN": DSN})
    assert r.returncode != 0 and "constraints" in (r.stdout + r.stderr)
