-- Mart: what a dashboard reads. Margin is a ratio of sums, never an average of row margins.
select
    record_date,
    sum(revenue)                                   as revenue,
    sum(profit)                                    as profit,
    sum(profit) / nullif(sum(revenue), 0)          as margin,
    sum(operational_cost) / nullif(sum(baseline_target), 0) as cost_vs_budget
from {{ ref('stg_ops') }}
group by 1
