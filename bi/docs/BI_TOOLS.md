# Build the same dashboard in Tableau, Superset and Power BI

You already have a working dashboard. The best way to learn a BI tool is to recreate something you understand and compare.
Export the data, then rebuild the **Analyst dashboard** (`/tracks/analyst`): KPI row, weekly margin line, over-budget bar, status mix.

## 1. Get the data
- With the backend running: `http://localhost:8020/api/export/operations?format=csv` (also `xlsx`, `parquet`, `json`).
- Or open the **Data files** panel on the dashboard and download the file you want.
- The gold layer from `data_engineering/` (`lake/gold/daily.parquet`) is a good "already modelled" source.

## 2. The five things to build in any tool
| Build | Definition (see the Glossary page) |
|---|---|
| KPI cards: revenue, profit, margin %, cost vs budget % | margin = SUM(profit) / SUM(revenue), **not** AVG of a margin column |
| Weekly margin line | group by week, then compute the ratio of sums |
| Bar: entities by cost vs budget | SUM(cost) / SUM(cost_budget_per_record) - 1, sorted |
| Status mix | COUNT by status |
| Filters: date range, category | applied to every chart |

## 3. Tool notes
**Tableau Public** (free): connect to the CSV, set `record_date` as a date, then create calculated fields.
Margin: `(SUM([Revenue]) - SUM([Operational Cost])) / SUM([Revenue])`. Full walkthrough: `docs/TABLEAU.md`.
Tableau Public workbooks are public, so use sample data only.

**Apache Superset** (free, needs Docker): follow the Superset section of the Apache page (`/apache`). Define `margin_pct` as a saved metric `SUM(profit)/SUM(revenue)`.

**Power BI Desktop** (free, Windows): Get Data -> Text/CSV. DAX measure: `Margin % = DIVIDE(SUM(ops[profit]), SUM(ops[revenue]))`. Use measures, not calculated columns, for ratios.

**Metabase / Looker Studio** (free): both can read the CSV or the Postgres lab database (`postgres_practice/`).

## 4. Check your work
Compare your tool's totals with the dashboard: total revenue, net margin and the most over-budget entity must match to the cent. A mismatch usually means an average of ratios, a filter that wasn't applied, or a join that duplicated rows. Finding that bug is the lesson.

> Honesty note: these tools weren't run in the environment where this project was built, so the steps are guidance, not tested scripts.
