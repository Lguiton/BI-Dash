import duckdb
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "bi_warehouse.duckdb"

def get_duckdb_connection():
    return duckdb.connect(str(DB_PATH))

def init_bi_schema():
    conn = get_duckdb_connection()
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dim_entities (
            entity_id VARCHAR PRIMARY KEY,
            name VARCHAR,
            category VARCHAR,
            baseline_target DOUBLE
        );

        CREATE TABLE IF NOT EXISTS fact_operations (
            fact_id VARCHAR PRIMARY KEY,
            record_date DATE,
            entity_id VARCHAR,
            revenue DOUBLE,
            operational_cost DOUBLE,
            units_processed INTEGER,
            duration_minutes INTEGER,
            status VARCHAR
        );
    """)

    result = conn.execute("SELECT COUNT(*) FROM fact_operations").fetchone()
    if result[0] == 0:
        conn.execute("""
            INSERT INTO dim_entities VALUES 
                ('ENT-01', 'Zone North 89011', 'Logistics', 120.0),
                ('ENT-02', 'Zone West Central', 'Express', 95.0),
                ('ENT-03', 'Downtown Corridor', 'Fleet', 140.0),
                ('ENT-04', 'Henderson South', 'Logistics', 110.0);

            INSERT INTO fact_operations VALUES
                ('F-101', '2026-10-01', 'ENT-01', 450.00, 112.50, 48, 240, 'Completed'),
                ('F-102', '2026-10-02', 'ENT-01', 520.00, 130.00, 52, 260, 'Completed'),
                ('F-103', '2026-10-03', 'ENT-02', 380.00, 95.00, 40, 210, 'Completed'),
                ('F-104', '2026-10-04', 'ENT-03', 610.00, 180.00, 65, 300, 'Completed'),
                ('F-105', '2026-10-05', 'ENT-04', 490.00, 115.00, 50, 250, 'Completed'),
                ('F-106', '2026-10-06', 'ENT-01', 540.00, 125.00, 56, 270, 'Completed');
        """)
    conn.close()
