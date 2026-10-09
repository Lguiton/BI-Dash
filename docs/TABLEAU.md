# Tableau practice guide

Use the same data the dashboard shows, so you can compare your Tableau work with this app.

## 1. Get the data in
In the dashboard open **SQL Lab → Practice files** and download as **CSV** (or XLSX):

| File | Use it as |
|---|---|
| `operations` | One flat table: easiest to start with |
| `facts` + `entities` + `dates` | A star schema: practice Tableau *relationships* |

Tableau Public and Desktop both read CSV and Excel. Parquet support depends on your Tableau version, so use CSV/XLSX unless you have checked yours.
(The `.duckdb` file is locked while the app runs, so connect Tableau to the exports, not to the database.)

For more rows, run `python scripts/generate_sample_data.py` (a year of data, 10 entities) and import `data_samples/operations_clean.csv`, then re-download.

## 2. Star schema with relationships
1. Connect to `facts.csv`, then drag in `entities.csv` and `dates.csv` (File → *Add*).
2. Relate `facts.entity_id = entities.entity_id` and `facts.record_date = dates.date_key`.
3. Say out loud the **grain** of the fact table: *one row per entity per day*.
   Notice how every measure you build has to respect that grain.

## 3. Calculated fields to build
```
Profit            SUM([Revenue]) - SUM([Operational Cost])
Margin %          SUM([Revenue]) - SUM([Operational Cost])) / SUM([Revenue])     // ratio of sums: non-additive!
Cost vs Budget %  AVG([Operational Cost]) / AVG([Baseline Target]) - 1           // baseline_target is a cost budget
Over Budget?      [Cost vs Budget %] > 0.05
Avg Rev / Entity  { FIXED [Entity Name] : AVG([Revenue]) }                       // LOD expression
Revenue 7d Avg    WINDOW_AVG(SUM([Revenue]), -6, 0)                              // table calc: rolling window
Running Revenue   RUNNING_SUM(SUM([Revenue]))
YTD Revenue       RUNNING_SUM(SUM([Revenue]))   // compute using: Date, restarting every Year
MoM %             (ZN(SUM([Revenue])) - LOOKUP(ZN(SUM([Revenue])), -1)) / ABS(LOOKUP(ZN(SUM([Revenue])), -1))
```
Check each against the dashboard (same filters) and the SQL Lab. They must match. If **Margin %** does not, you averaged ratios.

## 4. Worksheets to make
1. **Trend**: continuous Date (month) × Revenue, Profit; add *Analytics → Forecast* and compare with the dashboard's forecast.
2. **Cost vs Budget**: bar by Entity, colour by `Over Budget?`, reference line at 0.
3. **Heatmap**: Entity (rows) × Weekday (columns), colour = AVG Revenue.
4. **Scatter**: Operational Cost vs Revenue, detail = Fact ID, colour = Category; add a trend line.
5. **KPI tiles**: Revenue, Profit, Margin %, each with a period-over-period delta.

## 5. Dashboard design checklist (from your notes)
- [ ] **Z-pattern**: KPI tiles top, trend in the middle, detail table bottom.
- [ ] **Cross-filtering**: Dashboard → Actions → *Filter*, from the entity bar chart to every other sheet.
- [ ] **Drill-through**: a *Go to Sheet* action from an entity to its records table.
- [ ] **Contextual benchmarking**: nothing shown without a target or prior period beside it.
- [ ] Colour only where it means something (over budget = red, nothing else).
- [ ] Ask: could a manager read this in 10 seconds?

## 6. Stretch
Build the same dashboard in Power BI and Superset and compare how each handles the Margin % trap.
