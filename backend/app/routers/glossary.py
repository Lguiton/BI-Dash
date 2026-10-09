"""Metrics glossary: the vocabulary of this dashboard, each with a formula, a runnable SQL example and the classic mistake.

Think of it as a tiny semantic layer: one agreed definition per metric, so every chart, KPI and report means the same thing.
Every SQL example is executed by the test-suite, so the glossary can't drift away from the data model.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/glossary", tags=["glossary"])

J = "FROM fact_operations f JOIN dim_entities e ON e.entity_id = f.entity_id"

TERMS = [
    # ---- metrics ----
    {"id": "revenue", "term": "Revenue", "kind": "Metric", "additive": True,
     "definition": "Money earned from the records in scope.", "formula": "SUM(revenue)",
     "sql": "SELECT SUM(revenue) AS revenue FROM fact_operations",
     "pitfall": "Safe to add across days, entities and categories (additive)."},
    {"id": "cost", "term": "Operational cost", "kind": "Metric", "additive": True,
     "definition": "Money spent to produce those records.", "formula": "SUM(operational_cost)",
     "sql": "SELECT SUM(operational_cost) AS cost FROM fact_operations",
     "pitfall": "Additive, like revenue."},
    {"id": "profit", "term": "Net profit", "kind": "Metric", "additive": True,
     "definition": "What is left after cost.", "formula": "SUM(revenue - operational_cost)",
     "sql": "SELECT SUM(revenue - operational_cost) AS profit FROM fact_operations",
     "pitfall": "Additive. Compute it per row, then sum, or sum then subtract: the answer is identical."},
    {"id": "margin", "term": "Net margin %", "kind": "Metric", "additive": False,
     "definition": "Profit as a share of revenue.", "formula": "SUM(profit) / SUM(revenue)",
     "sql": "SELECT 100.0 * SUM(revenue - operational_cost) / SUM(revenue) AS margin_pct FROM fact_operations",
     "pitfall": "A ratio, so NEVER average the margin column or add margins together. Sum the parts first, then divide."},
    {"id": "cost_vs_budget", "term": "Cost vs budget %", "kind": "KPI", "additive": False,
     "definition": "Spend compared with the per-record cost budget (baseline_target). Positive means over budget.",
     "formula": "SUM(operational_cost) / SUM(baseline_target) - 1",
     "sql": f"SELECT 100.0 * (SUM(f.operational_cost) / SUM(e.baseline_target) - 1) AS over_budget_pct {J}",
     "pitfall": "baseline_target is a budget PER RECORD, so it is summed once per record (join to the entity), never once per entity."},
    {"id": "units", "term": "Units processed", "kind": "Metric", "additive": True,
     "definition": "Volume handled.", "formula": "SUM(units_processed)",
     "sql": "SELECT SUM(units_processed) AS units FROM fact_operations", "pitfall": "Additive."},
    {"id": "rev_per_unit", "term": "Revenue per unit", "kind": "Metric", "additive": False,
     "definition": "How much each unit earns on average.", "formula": "SUM(revenue) / SUM(units_processed)",
     "sql": "SELECT SUM(revenue) / SUM(units_processed) AS rev_per_unit FROM fact_operations",
     "pitfall": "Ratio of sums, not the average of per-row ratios (that over-weights tiny records)."},
    {"id": "completion", "term": "Completion rate", "kind": "KPI", "additive": False,
     "definition": "Share of records whose status is Completed.", "formula": "COUNT(Completed) / COUNT(*)",
     "sql": "SELECT 100.0 * SUM(CASE WHEN status = 'Completed' THEN 1 ELSE 0 END) / COUNT(*) AS completion_pct FROM fact_operations",
     "pitfall": "Check the denominator: records with a NULL status shouldn't silently count as failures."},
    {"id": "avg_duration", "term": "Average duration", "kind": "Metric", "additive": False,
     "definition": "Typical minutes per record.", "formula": "AVG(duration_minutes)",
     "sql": "SELECT AVG(duration_minutes) AS avg_minutes FROM fact_operations",
     "pitfall": "An average of averages is wrong unless every group has the same size. Average the raw rows."},
    # ---- concepts ----
    {"id": "grain", "term": "Grain", "kind": "Concept",
     "definition": "What one row of a table represents. Here: one operation record per entity per day.", "formula": "one row = one fact_id",
     "sql": "SELECT COUNT(*) AS rows, COUNT(DISTINCT fact_id) AS distinct_facts FROM fact_operations",
     "pitfall": "If rows != distinct keys the grain is broken (duplicates) and every SUM is inflated."},
    {"id": "fact_dim", "term": "Fact vs dimension", "kind": "Concept",
     "definition": "Facts are measurements (revenue, cost). Dimensions describe them (entity, category, date).", "formula": "fact JOIN dimension ON key",
     "sql": f"SELECT e.category, SUM(f.revenue) AS revenue {J} GROUP BY 1 ORDER BY 2 DESC",
     "pitfall": "Join on the dimension's primary key; a many-to-many join multiplies rows."},
    {"id": "scd", "term": "Slowly changing dimension", "kind": "Concept",
     "definition": "A dimension attribute (like an entity's category) that changes over time. Type 1 overwrites it; Type 2 keeps history.", "formula": "see the SCD lab",
     "sql": "SELECT category, COUNT(*) AS entities FROM dim_entities GROUP BY 1 ORDER BY 2 DESC",
     "pitfall": "With Type 1, old revenue silently moves to the new category."},
    {"id": "moving_avg", "term": "7-day moving average", "kind": "Method",
     "definition": "Average of the last 7 days, to smooth day-of-week noise.", "formula": "AVG(x) OVER (ORDER BY day ROWS 6 PRECEDING)",
     "sql": "WITH d AS (SELECT record_date, SUM(revenue) AS revenue FROM fact_operations GROUP BY 1) "
            "SELECT record_date, AVG(revenue) OVER (ORDER BY record_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW) AS ma7 FROM d ORDER BY 1",
     "pitfall": "The first 6 days average fewer points; don't read meaning into them."},
    {"id": "mape", "term": "MAPE (forecast error)", "kind": "Method",
     "definition": "Mean absolute percentage error: how far off a forecast is, on average, in percent.", "formula": "AVG(|actual - forecast| / actual)",
     "sql": "WITH d AS (SELECT record_date, SUM(revenue) AS a FROM fact_operations GROUP BY 1), "
            "p AS (SELECT record_date, a, LAG(a, 1) OVER (ORDER BY record_date) AS naive FROM d) "
            "SELECT 100 * AVG(ABS(a - naive) / a) AS naive_mape_pct FROM p WHERE naive IS NOT NULL",
     "pitfall": "Always compare with a naive forecast (yesterday's value). A model must beat it to be worth keeping."},
    {"id": "pseudo_replication", "term": "Pseudo-replication", "kind": "Method",
     "definition": "Treating rows that belong together (many records from one day) as independent evidence, which makes results look more certain than they are.",
     "formula": "aggregate to the independent unit (the day) before testing",
     "sql": "SELECT record_date, SUM(revenue) AS daily_revenue FROM fact_operations GROUP BY 1 ORDER BY 1",
     "pitfall": "Run a t-test on daily totals, not on every record (notebook 11)."},
    {"id": "leakage", "term": "Data leakage", "kind": "Method",
     "definition": "Giving a model information it would not have at prediction time (for example, profit when predicting revenue).", "formula": "features must exist BEFORE the outcome",
     "sql": "SELECT corr(revenue, revenue - operational_cost) AS corr_with_profit FROM fact_operations",
     "pitfall": "A suspiciously perfect score is usually leakage, not genius."},
    {"id": "class_imbalance", "term": "Class imbalance", "kind": "Method",
     "definition": "When the outcome you want to predict is rare, so 'always guess the common case' scores high accuracy.", "formula": "baseline accuracy = share of the majority class",
     "sql": "SELECT status, COUNT(*) AS n, 100.0 * COUNT(*) / SUM(COUNT(*)) OVER () AS pct FROM fact_operations GROUP BY 1 ORDER BY 2 DESC",
     "pitfall": "Judge by precision, recall and F1 against that baseline, never accuracy alone."},
]


@router.get("")
def glossary():
    return {"terms": TERMS, "kinds": sorted({t["kind"] for t in TERMS})}
