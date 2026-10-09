-- A singular test: returns the rows that BREAK the rule. Zero rows = pass.
select * from {{ ref('stg_ops') }} where revenue < 0
