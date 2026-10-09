-- Staging: one thin, renamed view of the silver layer. Never put business logic here.
select
    fact_id,
    record_date,
    entity_id,
    entity_name,
    category,
    revenue,
    operational_cost,
    revenue - operational_cost as profit,
    baseline_target,
    status
from read_parquet('../lake/silver/ops.parquet')
