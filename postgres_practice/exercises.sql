-- PostgreSQL practice. Run in psql:   docker exec -it bi_postgres psql -U postgres -d bi
-- or paste into any client (DBeaver, pgAdmin, VS Code).  First:  SET search_path = bi;
SET search_path = bi;

-- 1. THE SAME QUESTION AS SQL LAB: margin is a ratio of sums
SELECT round(100 * sum(revenue - operational_cost) / sum(revenue), 2) AS margin_pct FROM fact_operations;

-- 2. READ A QUERY PLAN. Look for "Seq Scan" and the actual time.
DROP INDEX IF EXISTS idx_fact_date;      -- (so you can repeat this exercise from scratch)
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM fact_operations WHERE record_date = DATE '2026-03-15';

-- 3. ADD AN INDEX, RE-RUN 2. Do you see "Index Scan" or "Bitmap Heap Scan"? Is it faster on 3,650 rows? Why or why not?
--    (Indexes pay off as tables grow. On tiny tables the planner may still choose a Seq Scan, and that is correct.)
CREATE INDEX IF NOT EXISTS idx_fact_date ON fact_operations (record_date);
ANALYZE fact_operations;
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM fact_operations WHERE record_date = DATE '2026-03-15';

-- 4. WINDOW FUNCTIONS: 7-day moving average of daily revenue
WITH d AS (SELECT record_date, sum(revenue) AS revenue FROM fact_operations GROUP BY 1)
SELECT record_date, revenue,
       round(avg(revenue) OVER (ORDER BY record_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2) AS ma7
FROM d ORDER BY record_date DESC LIMIT 10;

-- 5. A VIEW: save a definition once so everyone computes it the same way
CREATE OR REPLACE VIEW v_entity_scorecard AS
SELECT e.entity_id, e.name, count(*) AS records, sum(f.revenue) AS revenue,
       round(100 * sum(f.revenue - f.operational_cost) / sum(f.revenue), 2) AS margin_pct,
       round(100 * (sum(f.operational_cost) / sum(e.baseline_target) - 1), 2) AS vs_budget_pct
FROM fact_operations f JOIN dim_entities e USING (entity_id)
GROUP BY e.entity_id, e.name;
SELECT * FROM v_entity_scorecard ORDER BY vs_budget_pct DESC LIMIT 5;

-- 6. A MATERIALIZED VIEW: stored results, fast to read, must be refreshed (like a gold table)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily AS
SELECT record_date, sum(revenue) AS revenue, sum(operational_cost) AS cost FROM fact_operations GROUP BY 1;
REFRESH MATERIALIZED VIEW mv_daily;

-- 7. CONSTRAINTS PROTECT YOU. Each of these should FAIL. Read the error messages.
-- INSERT INTO fact_operations VALUES ('X1', '2026-01-01', 'NO-SUCH-ENTITY', 10, 5, 1, 1, 'Completed');   -- foreign key
-- INSERT INTO fact_operations VALUES ('X2', '2026-01-01', 'ENT-01', -10, 5, 1, 1, 'Completed');           -- check constraint
-- INSERT INTO fact_operations SELECT * FROM fact_operations LIMIT 1;                                       -- primary key

-- 8. TRANSACTIONS: all-or-nothing. Run these one line at a time.
-- BEGIN;
-- UPDATE dim_entities SET baseline_target = baseline_target * 2 WHERE entity_id = 'ENT-01';
-- SELECT entity_id, baseline_target FROM dim_entities WHERE entity_id = 'ENT-01';
-- ROLLBACK;   -- undo it. Check again: the budget is back.

-- 9. LEAST PRIVILEGE: an analyst who can read but never change data
-- (run as postgres; then reconnect as analyst: psql -U analyst -d bi, password practice123)
-- CREATE ROLE analyst LOGIN PASSWORD 'practice123';
-- GRANT USAGE ON SCHEMA bi TO analyst;  GRANT SELECT ON ALL TABLES IN SCHEMA bi TO analyst;
-- As analyst:  SELECT count(*) FROM bi.fact_operations;   -- works
--              DELETE FROM bi.fact_operations;            -- ERROR: permission denied
