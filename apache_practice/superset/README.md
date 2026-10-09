# Apache Superset practice

Superset is a **BI / visualization tool** (an open-source cousin of Tableau). Unlike Spark and Airflow
it has a point-and-click UI, so this folder is a guide, not a script.
(Heads-up: these steps follow Superset's documented Docker quickstart. They were written without
running Docker in the build environment, so if a command differs in your Superset version, trust Superset's docs.)

## 1. Get the data out of the dashboard
Start the backend, then download the flat table (facts + entity + date columns already joined):

    http://localhost:8020/api/export/operations?format=csv

(Save it as `operations.csv`. It's the same file Tableau uses; see docs/TABLEAU.md.)

## 2. Run Superset (needs Docker Desktop)

    docker run -d -p 8088:8088 -e SUPERSET_SECRET_KEY="change-me-to-a-long-random-string" --name superset apache/superset
    docker exec -it superset superset fab create-admin --username admin --firstname Admin --lastname User --email admin@example.com --password admin
    docker exec -it superset superset db upgrade
    docker exec -it superset superset init

Open http://localhost:8088 and log in with admin / admin (practice only, never reuse this on a real server).

## 3. Load the data
1. Settings > Database Connections > + Database > SQLite. SQLAlchemy URI: `sqlite:////app/superset_home/bi_practice.db`.
   In the *Advanced > Security* tab tick **Allow file uploads to database**, then save.
2. Data > Upload CSV to database. Pick `operations.csv`, database = the SQLite one, table name = `operations`.
3. Datasets > `operations` > edit: confirm `record_date` is marked **Temporal** (this enables time grains).

## 4. Add calculated metrics (this is the non-additive-measure lesson)
In the dataset's *Metrics* tab add:

| Metric name | SQL expression |
|---|---|
| `revenue_sum` | `SUM(revenue)` |
| `profit_sum` | `SUM(profit)` |
| `margin_pct` | `100.0 * SUM(profit) / SUM(revenue)` |
| `cost_vs_budget_pct` | `100.0 * (SUM(operational_cost) / COUNT(*) / AVG(baseline_target) - 1)` |

`margin_pct` is a ratio of sums. If you instead average the `margin` column Superset will happily give
you a wrong number: the same trap as in SQL Lab exercise "non-additive".

## 5. Build these charts, then a dashboard
| Chart type | Setup | Class concept |
|---|---|---|
| Big Number with Trendline | metric `revenue_sum`, time column `record_date`, grain Day, rolling mean 7 | KPI + time intelligence |
| Time-series line | metric `margin_pct`, grain Week, group by `category` | descriptive analytics |
| Bar chart | metric `profit_sum`, dimension `entity_name`, sort descending | comparison |
| Heatmap | x `day_name`, y `entity_name`, metric `revenue_sum` | diagnostic: find weekday effects |
| Pivot Table | rows `category`, columns `status`, metric `revenue_sum` | slice and dice |
| Table | `fact_id`, `record_date`, `status`, filtered with `status = 'Failed'` | drill-down |

Put them on one dashboard and add a **native filter** (date range + category). Arrange KPIs top-left
(Z-pattern reading order), details below. Compare the result with this app's dashboard.

## 6. Exercises
1. Re-create "Revenue by category" in Superset using **SQL Lab** (Superset has its own) and compare with this app's SQL Lab.
2. Add a chart-level filter and a dashboard-level filter. What is the difference?
3. Upload `data_samples/operations_messy.csv` as a second table. What breaks? (That's why we clean first: see python_practice/03.)
4. Schedule an email report (Superset > Settings > Alerts & Reports; needs extra config).

## Refresh story
Superset is a *consumer* of data. It does not update when the dashboard's DuckDB file changes. Re-export and
re-upload, or point Superset at a real database. In production, an Airflow DAG (see ../airflow) is what keeps that table fresh.
