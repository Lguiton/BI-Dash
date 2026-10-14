select
    entity_id,
    entity_name,
    count(*)                                        as records,
    sum(revenue)                                    as revenue,
    sum(profit)                                     as profit,
    sum(operational_cost) / nullif(sum(baseline_target), 0) as cost_vs_budget,
    avg(case when status = 'Completed' then 1.0 else 0.0 end) as completion_rate
from {{ ref('stg_ops') }}
group by 1, 2
