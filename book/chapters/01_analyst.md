# Part 1: Data Analyst

## The role in one page

A data analyst turns questions people have about a business into numbers they can trust and a recommendation they can act on. The raw material is tables: sales, costs, tickets, visits, shifts, deliveries. The product is rarely a chart. It is a decision: "stop doing this", "look at that team", "this change worked, that one did not".

**Who you work with.** Managers and owners who own a decision but not the data. Operations people who know why a number moved but cannot prove it. Engineers or a database administrator who own the tables you query. Sometimes a data scientist (see Part 2) and a data engineer who keeps the pipeline running (see Part 4).

**A typical day.** Read a request and ask what decision it feeds. Check whether the data can answer it. Write a query. Check the numbers against something you already know. Build a chart or table. Write three to five sentences. Send it, and answer the follow-up that always comes. Roughly a third of the time goes to understanding the question, a third to wrangling and checking data, and a third to communication.

**What good looks like.**

- Your number matches the finance report, or you can explain why not.
- You state every metric's definition before anyone asks.
- A manager can read your one-page memo in two minutes and act on it.
- You say what the data cannot tell you. "Revenue fell after the price change" is a finding. "The price change caused it" is a claim that needs more.
- Someone else can rerun your work next month and get the same answer.

**What it is not.** Not building models for their own sake (Parts 2 and 3), not building pipelines and warehouses (Part 4), not making pretty dashboards nobody uses, and not being a human query service, though some jobs drift that way.

**The honest hard parts.**

- *Vague requests.* "Pull the numbers on performance" means nothing until you ask which performance, compared with what, to decide what.
- *Dirty data.* Duplicates, missing days, a column whose meaning changed in March. It takes more time than you expect.
- *Definitions fight.* Two departments report "revenue" and get different figures, and you will be in the middle.
- *Being right is not enough.* A correct analysis nobody understands changes nothing.
- *Pressure to find something.* People want the analysis to support a conclusion they already hold. Part of the job is saying "the data does not show that".

This part is a self-study route from "I have never written a query" to "I can own an analysis from question to memo and review other people's work". It assumes only that you will check your own arithmetic.

## How to use this part

There are four levels. Each has outcomes, core ideas with worked examples, labs you run on your own, exercises with answers or hints, and a checkpoint. Do not move on until you can answer the checkpoint questions aloud without looking.

| Level | Aim | Time at about 5 hours a week |
|---|---|---|
| 1 Foundations | Read tables, write basic SQL, avoid the ratio trap | about 25 hours, 5 weeks |
| 2 Practitioner | Window functions, CTEs, data quality, KPIs, a second tool | about 40 hours, 8 weeks |
| 3 Advanced | Mix effects, like-for-like comparison, uncertainty, rebuilding in a BI tool | about 45 hours, 9 weeks |
| 4 Expert | Metric design, reviewing work, honesty, team scale | about 35 hours, 7 weeks, then ongoing |

That is roughly eight months at a steady pace. If you are quicker, skip ahead, but pass the Level 1 checkpoint first: most real analyst bugs live there.

**What you need.** Any SQL engine (SQLite, DuckDB and Postgres are all free), a spreadsheet, and optionally a scripting language with a table library (Python with pandas is a common choice; R works equally well). A free dashboard tool such as Tableau Public, Power BI Desktop, Metabase, Superset or Looker Studio matters from Level 3. Nothing here needs a download beyond these tools: every example uses small tables you can type in.

**A good rhythm.** Read a core idea, type its example into your SQL engine, then do the matching exercises. Say your expected answer before you press run. That one habit, predicting before you check, teaches more than any amount of reading.

**The toy tables.** Worked examples use a nine-row table you can check by hand. Create it once and keep it. The `ops` table has one row per unit per day; `units` describes each unit and carries a per-record cost budget.

```sql
CREATE TABLE units (unit_id TEXT, name TEXT, category TEXT, budget INT);
INSERT INTO units VALUES
  ('E1','North','Logistics',100),
  ('E2','West','Express',90),
  ('E3','East','Logistics',120);

CREATE TABLE ops (op_id TEXT, op_date DATE, unit_id TEXT,
                  revenue INT, cost INT, status TEXT);
INSERT INTO ops VALUES
  ('F1','2025-10-01','E1',400, 90,'Completed'),
  ('F2','2025-10-01','E2',300,100,'Completed'),
  ('F3','2025-10-01','E3',500,150,'Delayed'),
  ('F4','2025-10-02','E1',420,110,'Completed'),
  ('F5','2025-10-02','E2',280,130,'Cancelled'),
  ('F6','2025-10-02','E3',520,140,'Completed'),
  ('F7','2025-10-03','E1',450, 95,'Completed'),
  ('F8','2025-10-03','E2',310,105,'Completed'),
  ('F9','2025-10-03','E3',480,160,'Completed');
```

Call this **T9**. Totals: revenue 3,660, cost 1,080, profit 2,580 (profit means revenue minus cost). Units: E1 North (Logistics, budget 100), E2 West (Express, budget 90), E3 East (Logistics, budget 120). SQL dialects differ in small ways, such as date functions; where it matters the text says so.

## Level 1: Foundations (beginner)

### What you will be able to do

- You can say, for any table, what one row represents (its grain) and tell a fact table from a dimension table.
- You can write `SELECT` queries with `WHERE`, `GROUP BY`, `ORDER BY` and `LIMIT` to answer a plain question.
- You can predict how `NULL` changes `SUM`, `AVG` and `COUNT` before you run the query.
- You can compute a margin correctly as a ratio of sums and explain why averaging row margins is wrong.
- You can join a fact table to a dimension and notice when the join has duplicated rows.
- You can check your own result against a number you can verify by hand.

### Core ideas

#### 1. Tables, grain, facts and dimensions

A table is rows and columns, and the first question about any table is: what does one row mean? That is its **grain**. In `ops` one row is one unit on one day, so 10 units over 365 days would give 3,650 rows. If you do not know the grain you cannot know what a `SUM` or a `COUNT` is counting.

A **fact table** records events and carries measures you can add up (revenue, cost, units shipped). A **dimension table** describes the things the events happened to (a unit's name and category, a calendar date). Analysts live in the join between them.

Practise reading a schema like this: `ops` has a key (`op_id`), a date, a `unit_id` pointing at `units`, two measures and a `status`. Say aloud, "one row per unit per day", before running anything. Then run `SELECT COUNT(*) FROM ops` and see whether the answer (9) fits the grain: three units times three days.

#### 2. Select, filter, group, sort

`SELECT` chooses columns, `WHERE` filters rows before grouping, `GROUP BY` collapses rows into one per group, and aggregates (`SUM`, `COUNT`, `AVG`, `MIN`, `MAX`) summarise each group. `ORDER BY` sorts the result and `LIMIT` trims it.

```sql
SELECT status, COUNT(*) AS records
FROM ops
GROUP BY status
ORDER BY records DESC;
```

On T9 this returns Completed 7, Delayed 1, Cancelled 1. Every selected column is either in `GROUP BY` or inside an aggregate. Add `WHERE status = 'Completed'` and `SUM(revenue)` and you get 2,880, because seven rows survive the filter: 400 + 300 + 420 + 520 + 450 + 310 + 480.

SQL filters rows, then groups, then aggregates, then sorts. If a result looks wrong, ask which step changed the rows. Before running a query, say how many rows you expect back (here, three).

#### 3. NULL: the silent number-changer

`NULL` means "unknown", not zero. Aggregates skip it. Suppose F5's revenue were missing in T9. Then `SUM(revenue)` is 3,380 (3,660 minus 280), `COUNT(revenue)` is 8, `COUNT(*)` is 9, and `AVG(revenue)` is 3,380 / 8 = 422.5. If you computed `SUM(revenue) / COUNT(*)` you would get 375.6, a different answer to a different question: "average over all rows, treating missing as zero".

Neither is automatically right. The honest move is to count the NULLs first (`SELECT COUNT(*) - COUNT(revenue) FROM ops`) and decide whether a missing revenue means "no sale" or "we do not know". Use `COALESCE(x, 0)` only when you have decided that missing really means zero. Write the decision beside the query, because the next reader cannot see it. Beware blanks that are not NULL: an empty string or the text "N/A" counts as a value, so scan `SELECT DISTINCT status` for oddities.

#### 4. Ratio of sums: the most common analyst bug

A **ratio** such as margin is not additive. Take two rows: one with revenue 100 and profit 20 (margin 20%), one with revenue 900 and profit 90 (margin 10%). The average of the two margins is 15%. The real margin is total profit over total revenue: 110 / 1,000 = 11%. The average treats a 100-dollar row as equal to a 900-dollar row.

The rule: **sum the numerator, sum the denominator, then divide.**

```sql
SELECT SUM(revenue - cost) * 100.0 / SUM(revenue) AS margin_pct
FROM ops;
```

On T9 this is 2,580 / 3,660 = 70.49%, while averaging the nine row margins gives 69.59%. The gap is small because T9's rows are similar in size; with big and small rows it can reach several points. (The `100.0` forces decimal division; in some engines integer division would truncate.) The same trap applies to average price, cost per unit, failure rate and anything with "per" or "%" in its name.

#### 5. Joins, and how they quietly duplicate rows

A join attaches dimension columns to fact rows. `JOIN units u ON o.unit_id = u.unit_id` should return exactly as many rows as the fact table, because each unit appears once in the dimension. Check it:

```sql
SELECT COUNT(*) FROM ops;                                  -- 9 on T9
SELECT COUNT(*) FROM ops o
JOIN units u ON o.unit_id = u.unit_id;                     -- must also be 9
```

Now imagine the dimension wrongly listed E1 twice. Each of E1's three fact rows would match two dimension rows, and total revenue would become 3,660 + 1,270 = 4,930. This is **fan-out**: a join on a key that is not unique on one side. Nothing errors; the number is simply wrong. The defence is a habit: after every join, compare row counts or totals with the table you started from, and prove the dimension key is unique with `SELECT unit_id, COUNT(*) FROM units GROUP BY unit_id HAVING COUNT(*) > 1`, which should return nothing.

### Practice on your own

1. Load T9 into a SQL engine using the script above. Run `SELECT COUNT(*)` on each table and say each grain aloud first.
2. Paste the nine rows into a spreadsheet too. Compute total revenue with a sum, and check it matches 3,660.
3. Write each of the queries in the core ideas yourself, predicting the row count and the first value before you run.
4. Break it on purpose: update F5's revenue to NULL and rerun `SUM`, `AVG`, `COUNT(*)` and `COUNT(revenue)`. Match each to the figures above.
5. Insert a second row for E1 into `units`, rerun the joined revenue total, and see 4,930. Then delete it.
6. Compute margin by category two ways, as a ratio of sums and by averaging row margins, and write down the gap.

### Exercises

1. In one sentence, state the grain of `ops` and of `units`.
2. On T9, write the query for total revenue where status is Completed. What should it return?
3. On T9, which date has the highest total revenue, and what is it?
4. On T9, revenue by category (join to `units`). What are the two totals?
5. On T9, margin percent per category as a ratio of sums.
6. A colleague has a table with a column `margin` (profit divided by revenue per row) and writes `SELECT category, AVG(margin) FROM sales GROUP BY category`. Explain what is wrong and rewrite it.
7. If three of 3,650 rows have NULL `cost`, how does that change `SUM(cost)` and `AVG(cost)`, and what would you check first?

### Answers and hints

1. One unit on one day; one unit (one row per unit).
2. `SELECT SUM(revenue) FROM ops WHERE status = 'Completed'` returns 2,880.
3. Group by `op_date`: the days total 1,200, 1,220 and 1,240, so 2025-10-03 with 1,240.
4. Logistics 2,770 (E1 1,270 plus E3 1,500) and Express 890.
5. Logistics 2,025 / 2,770 = 73.10%; Express 555 / 890 = 62.36%.
6. `AVG(margin)` weights every row equally. Use `SUM(profit) * 100.0 / SUM(revenue)` per category, from the original profit and revenue columns.
7. Both skip the three rows (`AVG` divides by the number of non-NULL values). Check whether those rows have revenue, and why cost is missing, before filling anything.

### Checkpoint

Answer aloud:

1. What is the grain of the table you are querying, and how do you know?
2. What is the difference between `COUNT(*)` and `COUNT(column)`?
3. Why is `WHERE` different from `HAVING`? (Say what you think; Level 2 confirms.)
4. How do you compute margin for a group, and why not average?
5. How can you tell a join duplicated rows?
6. What is a dimension, and what is a fact?

Common mistakes:

- Averaging a ratio column instead of dividing sums.
- Not checking row counts after a join.
- Treating NULL as zero without deciding that it is.
- Reporting a number without saying which date range and filters it covers.

## Level 2: Practitioner (intermediate)

### What you will be able to do

- You can filter on aggregates with `HAVING` and build calculated columns such as percent over budget.
- You can write window-function queries (`LAG`, moving average, `RANK`, running total) inside a CTE.
- You can run and read data-quality checks, and fix duplicates without silently changing totals.
- You can turn a metric into a KPI with a target, a direction and a warning band, and predict its status by hand.
- You can reproduce a SQL answer in a spreadsheet or a scripting language and reconcile the two.
- You can write a five-part memo from an analysis.

### Core ideas

#### 1. Filtering aggregates: WHERE versus HAVING

`WHERE` filters rows before they are grouped; `HAVING` filters groups after aggregation. To list units whose average cost per record is above budget you must use `HAVING`, because the average does not exist until the rows are grouped.

```sql
SELECT u.name,
       AVG(o.cost) AS avg_cost,
       u.budget,
       (AVG(o.cost) / u.budget - 1) * 100 AS pct_over
FROM ops o
JOIN units u ON o.unit_id = u.unit_id
GROUP BY u.name, u.budget
HAVING AVG(o.cost) > u.budget
ORDER BY pct_over DESC;
```

On T9: East averages 150 against a budget of 120, so 25.0% over; West averages 111.67 against 90, so 24.1% over; North averages 98.33 against 100 and is not listed.

Say in memos which definition of "cost versus budget" you used: average per record, or total spend over total budget. They differ when units have different record counts, because the second weights units by volume.

#### 2. Window functions: compare a row with its neighbours

A window function computes across related rows without collapsing them. Three patterns cover most needs. `LAG` fetches the previous row's value; an `AVG ... ROWS BETWEEN` frame gives a moving average; `RANK() OVER (PARTITION BY ...)` ranks within a group. Build the aggregate in a CTE (a named sub-query introduced by `WITH`) first, then apply the window to it.

```sql
WITH m AS (
  SELECT strftime('%Y-%m', op_date) AS month, SUM(revenue) AS revenue
  FROM ops GROUP BY 1
)
SELECT month, revenue,
       (revenue * 1.0 / LAG(revenue) OVER (ORDER BY month) - 1) * 100 AS mom_pct
FROM m ORDER BY month;
```

`strftime` is SQLite's way to cut a date to a month; Postgres and DuckDB use `DATE_TRUNC('month', op_date)`. With monthly revenue 1,000, 1,100 and 990 this returns NULL, +10.0% and -10.0%. A 10% rise then a 10% fall ends at 990, not 1,000. For a 7-day moving average use `AVG(revenue) OVER (ORDER BY op_date ROWS BETWEEN 6 PRECEDING AND CURRENT ROW)` on a daily table; the first six days average fewer values. On T9, ranking units by profit within category with `RANK() OVER (PARTITION BY category ORDER BY profit DESC)` puts East (profit 1,050) ahead of North (975) in Logistics, and West alone at rank 1 in Express.

#### 3. Data quality: trust before analysis

Before any analysis, ask whether the data can bear it. Common failures: missing required values, negative amounts, impossible durations, duplicate loads, orphan keys (a fact pointing at a dimension row that does not exist) and calendar gaps. Duplicates are nastiest: they inflate totals without any error.

Suppose F10 is loaded as an exact copy of F1: same date, same unit, revenue 400. Revenue now reads 4,060 instead of 3,660, which is 400 too high. Find it with the business key (the combination that should be unique):

```sql
SELECT op_date, unit_id, COUNT(*) AS n
FROM ops GROUP BY op_date, unit_id HAVING COUNT(*) > 1;
```

Remove it in a query (never by hand) with `ROW_NUMBER() OVER (PARTITION BY op_date, unit_id ORDER BY op_id)`, keeping `rn = 1`; the total returns to 3,660. But first ask whether it is a true duplicate or two real events on one day. The check is a lead, not a verdict. A sensible routine runs a fixed list of checks each time (completeness, uniqueness, valid ranges, valid keys, no date gaps), separates "stop and fix" failures from "look, then decide" warnings, and records the result.

#### 4. From metric to KPI

A **metric** measures; a **KPI** is a metric tied to a goal: a target, a direction (higher or lower is better), a time window and an owner. A common status rule: good when the value meets the target, warn when it misses by no more than `abs(target) * warn_pct / 100`, and bad beyond that. Rules vary between tools, so write yours down.

Example: revenue target 20,000, higher is better, warn band 10% (so 2,000). A value of 19,000 is warn; 18,000 is still warn (the band's edge is inclusive under this rule); 17,000 is bad. Now a subtle case: "cost vs budget %" with target -10 (lower is better) and warn 15%. The band is `abs(-10) * 0.15 = 1.5`, so -9 and -8.5 are warn, but -8 and 0 are bad. A negative target works, but the band is built from its absolute value, so check the arithmetic whenever a target is near zero or negative.

If nobody would act differently when a KPI turns red, delete it.

#### 5. The same question in a spreadsheet or a script

Everything above has a twin outside SQL, and doing both is the best check you have. In pandas, with a data frame `df` joined to the unit names:

```python
g = df.groupby("category")[["revenue", "cost"]].sum()
g["margin_pct"] = (g.revenue - g.cost) / g.revenue * 100   # ratio of sums
daily = df.groupby("op_date")["revenue"].sum()
daily.pct_change()                 # day-over-day growth
daily.rolling(3).mean()            # 3-day moving average
```

On T9, margin_pct is 62.36 for Express and 73.10 for Logistics, matching SQL; the daily series is 1,200, 1,220, 1,240, so the growth is 1.67% and 1.64%. Monthly totals come from `df.set_index("op_date")["revenue"].resample("MS").sum()`. A spreadsheet pivot table does the same grouping: drag category to rows, and sum revenue and cost, then add a margin cell that divides the two totals (never a pivot "average of margin"). Both pandas and spreadsheets skip missing values in sums, like SQL. If SQL and the second tool disagree, one has a filter, join or NULL difference. Finding which is the lesson.

### Practice on your own

1. Run the over-budget query on T9 and confirm 25.0% and 24.1%. Then change it to total spend over total budget and compare.
2. Build a longer table: generate 90 days for the three units in a spreadsheet or script (revenue about 300 to 500, cost about 90 to 160, random), load it, and compute the monthly growth with `LAG` and a 7-day moving average.
3. Insert a copy of F1 as F10. Find it with the business-key query, remove it with `ROW_NUMBER`, and show the total returns to 3,660.
4. Write a checklist of five data-quality queries (NULLs, negatives, duplicates, orphan unit ids, missing dates) and run them on the table before and after you insert a deliberately bad row.
5. Define two KPIs on paper (target, direction, warn band) and predict each one's status for three invented values, then check with a spreadsheet formula.
6. Reproduce the margin-by-category result in a spreadsheet pivot or pandas and reconcile it with SQL.

### Exercises

1. Explain in one sentence why `WHERE AVG(cost) > 100` is an error.
2. On T9, which units are over budget and by what percent (two decimals)?
3. A series is 1,000, 1,100, 990. Give each month's growth, and the total change from the first to the last month.
4. Write a query that returns each unit's cost spikes: records whose cost is more than twice that unit's own average. Why do you need a CTE or subquery?
5. With target 50 (higher is better) and warn 20%, classify values 45, 40 and 39.
6. After adding F10 (a copy of F1) to T9, what does `COUNT(*)` return, and what does revenue per record become?

### Answers and hints

1. Aggregates are not available until grouping; `WHERE` runs first, so use `HAVING`.
2. East 25.00% over; West 24.07% over; North is not over (-1.67%).
3. NULL, +10.0%, -10.0%; the total change is 990 / 1,000 - 1 = -1.0%.
4. Compute each unit's average in a CTE, join it back to the facts, and filter on `cost > 2 * avg_cost`. The average must exist before you can compare each row with it.
5. The band is 50 * 20% = 10, so the warn zone is 40 to just under 50: 45 is warn, 40 is warn (the edge is inclusive) and 39 is bad.
6. `COUNT(*)` is 10 and revenue per record is 4,060 / 10 = 406 instead of 3,660 / 9 = 406.67. A small shift in the average, but a 400 shift in the total.

### Checkpoint

Answer aloud:

1. When do you need `HAVING` rather than `WHERE`?
2. What does `LAG` give you, and why do you build the aggregate in a CTE first?
3. Why can a 10% rise followed by a 10% fall not return to the start?
4. Name four data-quality checks and what each protects you from.
5. What is the difference between a metric and a KPI?
6. How is the warn band calculated, and what is odd about negative targets?

Common mistakes:

- Putting an aggregate in `WHERE`.
- Deleting suspected duplicates without confirming they are duplicates.
- Setting a KPI target with no owner or action attached.
- Comparing a partial period (a half-finished month) with a full one.

## Level 3: Advanced

### What you will be able to do

- You can explain a change in an overall ratio by splitting it into a mix effect and a rate effect.
- You can compare periods like for like, and judge a forecast against a naive baseline.
- You can report a difference between groups with an interval and an effect size, and choose the right unit of analysis.
- You can rebuild a dashboard in a BI tool and reconcile its totals to the cent.
- You can profile an unfamiliar table before you query it.
- You can write the case-study memo with a headline, evidence, recommendation and caveats.

### Core ideas

#### 1. Mix effects: why the total can fall while every part rises

An overall ratio is a weighted average of its parts, so it moves when the weights move, even if every part improves. Take two categories, A (low margin) and B (high margin).

| Period | A revenue | A margin | B revenue | B margin | Overall margin |
|---|---|---|---|---|---|
| 1 | 100 | 10% | 900 | 40% | (10 + 360) / 1,000 = 37.0% |
| 2 | 900 | 12% | 100 | 42% | (108 + 42) / 1,000 = 15.0% |

Both categories improved by two points, yet the overall margin fell 22 points. Decompose: hold period-1 mix (10% A, 90% B) and apply period-2 margins: 0.1 x 12 + 0.9 x 42 = 39.0%, so the **rate effect** is +2.0 points. Then move from period-1 mix to period-2 mix at period-2 margins: 15.0% - 39.0% = -24.0 points, the **mix effect**. Together: +2.0 - 24.0 = -22.0.

The lesson for the manager: "Margin fell because our revenue shifted toward the low-margin line, not because either line got worse." Whenever an overall ratio moves, ask which parts moved and whether the mix changed. Other orderings of the decomposition give slightly different splits when both effects are large; say which one you used.

#### 2. Like-for-like time comparisons, and forecasts you must beat

Most misleading comparisons are mismatched periods: 12 days against a full month, five weekends against four, a holiday week against an ordinary one. Compare equal-length windows, align weekdays (compare Tuesday with Tuesday), and label partial periods "month to date".

A forecast is only useful if it beats a naive rule. Two baselines: **naive** (repeat the last value) and **seasonal naive** (repeat the same weekday from earlier). The usual error measure is MAPE, the mean of |actual - forecast| / actual. Suppose three held-out days have actuals 100, 120, 90. A model predicting 110, 115, 100 has errors of 10.0%, 4.2% and 11.1%, a MAPE of 8.4%. The naive forecast (105 each time, the last value seen in training) has errors of 5.0%, 12.5% and 16.7%, a MAPE of 11.4%. The model wins, but with only three points that is anecdote, not evidence.

Hold out the most recent stretch (a backtest), never a random sample of days, because a forecast is always used on days that come after the data it learned from. MAPE misbehaves when actuals are near zero. Always plot forecast against actuals before you trust the number.

#### 3. How sure are you? Intervals, effect sizes and the unit of analysis

A difference in a chart is not yet a finding. Ask three things: how large is it, how uncertain, and could it be noise?

Suppose weekend days average 1,300 revenue (standard deviation 80, 10 days) and weekdays 1,200 (standard deviation 90, 25 days). The gap is 100. Its standard error is the square root of (80²/10 + 90²/25), which is sqrt(640 + 324) = 31.0. A Welch t-based 95% interval is about 35 to 165 and the p-value is about 0.005. So report: "weekends earned about 100 more per day (95% interval roughly 35 to 165)", which gives size and uncertainty.

The **unit of analysis** is the thing you can treat as one independent observation. Records on the same day share conditions, so test days, not records. Testing 3,650 records instead of 365 days makes the p-value absurdly small: false confidence (pseudo-replication).

Finally, count your tests. Run 20 independent tests at the 5% level and the chance of at least one false positive is 1 - 0.95^20, about 64%.

#### 4. Rebuilding in a BI tool and reconciling

A BI tool is only a faster way to show numbers you can already compute. The best way to learn one is to rebuild something you understand from an exported CSV and compare totals. Five builds cover most dashboards: KPI cards, a weekly margin line, a cost-versus-budget bar, a status mix, and shared filters.

The key definitions, written correctly:

```
Tableau   Margin %   (SUM([Revenue]) - SUM([Cost])) / SUM([Revenue])
Tableau   Avg rev per unit   { FIXED [Unit Name] : AVG([Revenue]) }
Power BI  Margin %   DIVIDE(SUM(ops[profit]), SUM(ops[revenue]))
```

Use measures, not calculated columns, for ratios, so the division happens after aggregation at whatever level the chart shows. Reconcile three numbers to the cent: total revenue, net margin, and the most over-budget unit. A mismatch usually means an average of ratios, a filter you forgot, or a join that duplicated rows.

Two cautions. Public dashboard services publish what you upload, so use sample data only. And follow a tool's own documentation for exact steps, since menus change between versions.

#### 5. Profiling an unfamiliar table

Before querying a table you did not build, profile it: row count, the number of distinct values and NULLs per column, minimum and maximum of each measure, the date range, and the five most common values of each category column. In DuckDB `SUMMARIZE tablename` does most of this in one line; in any engine a handful of `COUNT(DISTINCT ...)`, `MIN` and `MAX` queries do the same. In pandas, `df.describe()` and `df.isna().sum()` are the start. Ten minutes of profiling prevents hours of confident nonsense, because it shows the grain, the date range and the oddities before you rely on them.

### Practice on your own

1. Build a two-category, two-period table in a spreadsheet using the mix example's numbers. Compute overall margins, then the rate and mix effects, and confirm they sum to -22.0.
2. Extend your 90-day table to 180 days. Forecast the last 14 days with the naive rule and with a seasonal naive rule (average of the same weekday in the previous four weeks). Compute MAPE for both and plot them against actuals.
3. Simulate it: generate 35 days of revenue with weekends higher, compute the weekend minus weekday gap, and a 95% interval by the formula above or by bootstrap (resample each group with replacement 5,000 times, take the 2.5th and 97.5th percentiles).
4. Run the same comparison once on days and once on individual records, and compare the p-values.
5. Export the 180-day table as CSV, rebuild a KPI card, a weekly margin line and a cost-versus-budget bar in a free BI tool, and reconcile three totals to your SQL.
6. Profile a table you did not make (any public CSV) and write five lines about what you learned before analysing it.

### Exercises

1. Using the Level 3 mix table, what would period-2 margin be if the mix had stayed at 10% A and 90% B?
2. Compute MAPE for actuals 80, 100 with forecasts 88, 90.
3. Why is comparing the first 10 days of a month with the whole previous month misleading? Give two fixes.
4. A manager asks whether the weekend premium is real. Name the unit of analysis and write the sentence you would report.
5. Write SQL for each category's share of total revenue by month.
6. Your BI tool's margin is 38.1% but SQL says 41.0%. List three causes, in the order you would check them.

### Answers and hints

1. 0.1 x 12 + 0.9 x 42 = 39.0%.
2. Errors are 8/80 = 10.0% and 10/100 = 10.0%, so MAPE is 10.0%.
3. Different length and weekday mix. Compare the same number of days (first 10 days to first 10 days), or use a trailing window of whole weeks.
4. The day. Report the difference in dollars per day with an interval, and add that records within a day are not independent.
5. A CTE of revenue by month and category, then `revenue * 1.0 / SUM(revenue) OVER (PARTITION BY month)`.
6. Averaging row margins instead of a ratio of sums; an unapplied filter or date range; a join that duplicated or dropped rows.

### Checkpoint

Answer aloud:

1. What is a mix effect, and how do you separate it from a rate effect?
2. Why must a forecast beat a naive baseline?
3. What does a 95% interval tell a manager that a p-value does not?
4. What is the unit of analysis here, and what goes wrong if you pick the wrong one?
5. How many false positives should you expect from 20 tests at the 5% level?
6. What do you check first when a BI tool disagrees with SQL?

Common mistakes:

- Explaining a drop in a ratio as performance when the mix moved.
- Comparing partial periods with full ones.
- Saying "significant" with no size and no interval.
- Testing records instead of days and trusting the tiny p-value.
- Trusting a BI tool's number without reconciling it.

## Level 4: Expert and professional judgement

### What you will be able to do

- You can write a metric definition complete enough that two people compute the same number.
- You can predict how a target will be gamed and add a guardrail metric.
- You can review another analyst's query and conclusions and list what you would ask before approving.
- You can spot the timing and denominator failures that make real dashboards lie.
- You can state what an analysis does not show, and refuse to overclaim under pressure.
- You can set up shared definitions and review habits for a small team.

### Core ideas

#### 1. Metric design and the way targets get gamed

A usable metric definition has a name, a formula, a grain, filters, a time window, an owner and a statement of what it is not. "Cost vs budget %" is not a definition until you say whether it is average cost over budget per record, or total spend over total budget, because the two differ when units have different record counts.

People optimise whatever you measure. Suppose the non-completed rate is 7 of 100 records (7%) and a manager is rewarded for reducing it. The cheapest fix is not better operations: it is to stop logging the five hardest jobs, so the rate becomes 2 of 95, or 2.1%. The number improved and nothing else did. The defence is a **guardrail metric** reported beside it (records logged, revenue per day) so a collapse in the guardrail exposes the gaming. Ask of every KPI: how could someone hit this and make the business worse?

#### 2. Reviewing someone else's analysis

Review is where you add the most value now. Ask the same questions every time: what is the grain, what is the definition, do the totals reconcile to a known figure, were rows duplicated or dropped by a join, are the periods comparable, is the sample large enough for the claim, and would a different reasonable choice change the conclusion?

Example. A colleague reports "East has a 45% margin" from this query: `SELECT AVG(margin) FROM sales WHERE unit = 'East'`. That averages row margins, so recompute as SUM(profit)/SUM(revenue). On T9, East's rows are 70.0%, 73.1% and 66.7%, an average of 69.9%, while the ratio of sums is 1,050/1,500 = 70.0%. A 45% figure cannot come from these rows, so something else differs: the date range, a filter or the definition. Ask for the query, the date range and the reconciliation, in that order, and review the work, not the person.

#### 3. How real dashboards lie

Four failures recur. **Late-arriving data**: the last day is only half loaded, so "revenue fell 40% yesterday" is really 6 rows against the usual 10. Check row counts per day before reading the final day, and compare it with the count on a normal day. **Time zones and cut-offs**: a record at 11 p.m. local belongs to a different day in UTC; fix the convention and write it down. **Denominator drift**: a rate whose denominator changed definition (all records, then only closed ones) shows a break that is bookkeeping, not behaviour. **Survivorship**: analysing only units that still exist hides the ones that failed.

A cheap habit catches most of these: before reading any trend, run counts per period beside the values, and look at the last point and the first point with suspicion. Date-gap and duplicate checks are the same idea at table level.

#### 4. Honesty: findings are leads, not verdicts

Automated insights, anomaly flags and AI-written summaries are computed from rules, and the honest label for them is "a lead". Treat your own analyses the same way. Say what the data shows, how sure you are, and what it cannot show. "Weekends earned about 100 more per day (interval 35 to 165)" is honest. "Weekends are better" is not, and "we should open on Sundays because of this" ignores cost, staffing and a sample of a few dozen weekends.

Never choose the axis, filter or period to produce the story you want; show the full range and note exclusions. Do not report one significant test out of many. Query the minimum personal data, share aggregates, and do not export identifiable rows to places not meant for them. If an AI tool wrote your SQL, you still own it: run the reconciliation yourself. And when someone asks you to "find something", say what you found, including "nothing clear".

#### 5. Operating at team scale

One analyst can keep definitions in their head; a team cannot. The scalable pieces are a **metric dictionary** (one agreed definition per metric, with an owner), a small set of **certified datasets** that people query instead of raw tables, SQL kept in version control with review, and a rule that dashboards carry their definitions and last-refresh time on the page. Put an owner beside every shared metric: the person to ask when the number looks wrong.

Watch for dashboard sprawl: forty dashboards with no owner means nobody trusts any. Retire what nobody opens, and merge duplicates. Many one-off questions deserve a one-line answer, not a dashboard. At work, access control, audit and data retention are governed by the organisation's rules; learn them before you copy data anywhere.

### Practice on your own

1. Write the full definition (formula, grain, window, owner, anti-goal) for each KPI you made at Level 2, and add a guardrail metric to each.
2. Take an analysis you wrote earlier and review it as a stranger: reconcile every number to the data and write five review comments.
3. Add a deliberate fan-out join to a query, find it with a row-count check, and write one sentence on what a manager would have seen.
4. Plant a half-loaded last day in your 180-day table, and show how counts per day expose it.
5. Pick a KPI from any job you have had, list two ways it could be gamed, and design a guardrail for each.

### Exercises

1. Write a complete definition for "Non-completed rate %" using the checklist in idea 1.
2. For a KPI "average duration per record, lower is better", name one way to game it and a guardrail.
3. A dashboard says revenue fell 40% on the last day. Give three checks, in order.
4. Review this claim: "Unit N is 25% over budget, so cut its budget." List five questions you would ask.
5. Two teams report different revenue for last quarter. Plan how you would resolve it.

### Answers and hints

1. Name; formula 100 x count of status other than Completed / count of records with a status; grain one record; window stated; owner named; what it excludes (records with a missing status); anti-goal (do not drop hard records).
2. Quit logging long jobs or split one job into two. Guardrail: records per day and revenue per record.
3. Records per day for the last day versus normal; the load time of the last file; whether any unit is absent. Only then discuss causes.
4. Over budget measured how and over what window; whether the budget is realistic; mix of work; whether the cause is price, volume or waste; what cutting would do to revenue.
5. Get both definitions and queries in writing; compare grain, filters, date boundaries and time zones; reconcile each to the finance ledger; find the first point where the two diverge; agree one definition and its owner; record it in the dictionary.

### Checkpoint

Answer aloud:

1. What belongs in a metric definition?
2. How would you find out a KPI is being gamed?
3. What are your first five review questions for a query?
4. Why can the last data point be misleading?
5. What should an honest sentence about a finding contain?
6. What would you put in a team metric dictionary, and who owns it?

Common mistakes:

- Defining a KPI by its name alone.
- Reviewing only the final chart, not the query or the totals.
- Reading trends before checking counts per period.
- Treating a computed insight as a conclusion.

## Capstone projects

### 1. Where are we losing money? (small, about 10 hours)

**Brief.** Take a year of daily records for at least eight units (build a realistic synthetic set, or use any open dataset with revenue, cost and a category). Answer a manager's question: "Margin looks fine overall; is anything costing more than it should?"

**Deliverables.** A one-page memo (headline, evidence, so what, recommendation, caveats) with three charts and one recommendation; an appendix of the SQL used; a reconciliation line showing your totals match a second tool.

**Self-assessment rubric** (score each line 0 = missing, 1 = partly, 2 = solid; aim for 9 of 12):

- The headline answers the question in one sentence
- Margin is a ratio of sums everywhere
- The most over-budget unit and its dollar overspend are right
- Every number reconciles to a second calculation
- Caveats say what the data cannot show
- A stranger could act on the recommendation

### 2. SQL portfolio with a mix analysis (medium, about 25 hours)

**Brief.** Choose ten queries (joins, window functions, a CTE, a dedupe, a cost-spike hunt) and write the business question above each. Add one original analysis: a monthly mix-versus-rate decomposition of margin by category.

**Deliverables.** Ten questions with queries and results; the decomposition with a table and a manager-readable paragraph; a short data-quality note of what you checked first.

**Rubric** (0 to 2 per line; aim for 11 of 14):

- Each query answers its stated question
- At least three window-function or CTE queries are correct
- The decomposition's rate and mix effects sum to the total change
- The data-quality note names specific checks and results
- Definitions are written beside each metric
- No query fans out or averages a ratio
- Results are explained in plain words

### 3. A rebuilt dashboard with a metric dictionary (large, about 50 hours)

**Brief.** Build a dashboard (KPI row, weekly margin line, cost-versus-budget bar, status mix, shared filters) in a free BI tool using sample data only. Add a metric dictionary and a quality report, and have someone review it.

**Deliverables.** The dashboard with the most important number top left; a metric dictionary of at least eight metrics with formula, grain, owner and anti-goal; a reconciliation table (tool versus SQL); a one-page quality report; the reviewer's comments and your responses.

**Rubric** (0 to 2 per line; aim for 14 of 18):

- Totals reconcile to the cent
- Ratios are measures, not averaged columns
- Every chart carries a comparison (target or prior period)
- Colour is used only where it carries meaning
- The dictionary would let two people compute the same number
- A manager can read it in ten seconds
- Review comments were answered, not ignored
- Limits and refresh time are stated on the page

## Tools reference

| Tool | What it is for | When you outgrow it |
|---|---|---|
| SQL (SQLite or DuckDB to learn; Postgres, BigQuery or Snowflake at work) | Querying and aggregating tables | Never; you learn the dialect differences |
| Spreadsheet (Excel, Sheets) | Quick looks, pivots, sharing with non-technical people | When data exceeds a few hundred thousand rows or the work must be repeatable |
| pandas (or R) and a plotting library | Reshaping, checks, one-off charts, reconciling SQL | When you need scheduled, tested pipelines (see Part 4) |
| Jupyter-style notebooks | Exploration with notes beside the code | When others must run it unattended |
| Tableau Public or Desktop | Interactive dashboards with a rich chart set | When you need governed, shared metrics across a team |
| Power BI Desktop (Windows) | Dashboards and measures in the Microsoft world | Same, plus when you need a semantic layer shared by everyone |
| Superset, Metabase, Looker Studio | Free or open dashboards over SQL | When you need enterprise access control and support |

Practice setups are guardrails, not vaults: keep real or confidential data out of public tools.

## Glossary

- **Grain**: what one row of a table represents.
- **Fact table**: events with measures you can add up.
- **Dimension table**: descriptions of the things the events happened to.
- **Additive measure**: one you can sum across any dimension.
- **Non-additive measure**: a ratio or average that cannot be summed; recompute from totals.
- **Ratio of sums**: sum the numerator and the denominator, then divide.
- **Fan-out**: a join on a non-unique key that duplicates rows.
- **NULL**: unknown value; aggregates skip it.
- **Business key**: the combination of columns that should identify a real-world record.
- **Orphan key**: a fact row pointing at a dimension row that does not exist.
- **CTE**: a named sub-query introduced with `WITH`.
- **Window function**: a calculation across related rows without collapsing them.
- **Time intelligence**: period-over-period, year-to-date and rolling calculations.
- **Metric**: a measurement with a definition.
- **KPI**: a metric tied to a target, direction, warn band and owner.
- **Guardrail metric**: a second metric that exposes gaming of the first.
- **Mix effect**: a change in an overall ratio caused by shifting weights.
- **Rate effect**: the part of a change due to the parts themselves changing.
- **MAPE**: mean absolute percentage error.
- **Seasonal naive**: forecast equal to the same period earlier.
- **Backtest**: testing a forecast on a recent stretch held out from training.
- **Confidence interval**: a range of values consistent with the data; report it with the effect size (how large the difference is).
- **Unit of analysis**: what counts as one independent observation.
- **Pseudo-replication**: treating dependent rows as independent.
- **Reconciliation**: proving two tools give the same number.
- **Metric dictionary**: the agreed definitions of shared metrics, with owners.
- **LOD expression**: a Tableau calculation at a level you name.

## Career notes

**Titles this leads to.** Data analyst, business analyst, BI analyst or developer, reporting analyst, analytics engineer (with more engineering), operations or finance analyst. With more statistics it leads towards data scientist (Part 2); with more pipeline work, towards data engineering (Part 4).

**How to show your skill.** A small public portfolio beats a list of tools: the Capstone 1 memo, the Capstone 2 document, and a public dashboard on sample data (never confidential data). Each piece should state the question, definition, check and caveat. Link them from your CV. If you have domain experience, build one analysis on that domain's questions; context separates a good analyst from a competent query writer.

**What to learn next.** Statistics for decisions (Part 2), a second SQL dialect, dbt-style modelling and testing (Part 4), experiment design, and writing and presenting.

**Certifications.** Several vendors offer analyst and BI certifications, and they can help get a first interview. Check the current exam objectives before paying: they change, and the portfolio usually counts for more.

## Match it in the app

This section is for readers who have the companion dashboard running. Nothing above depends on it. Use the Practice workspace (the Practice / Real switcher at the top of each page), which holds a made-up year of operations data and cannot damage your own data. For a bigger dataset, run `python scripts/generate_sample_data.py` and import `data_samples/operations_clean.csv` in Replace mode: 3,650 rows (10 entities by 365 days) with a weekday pattern, a few anomalies and some entities built to run over budget. The app's `fact_operations` table is the book's `ops`, with `entity_id`, `operational_cost` and `dim_entities.baseline_target` in place of `unit_id`, `cost` and `budget`. Compare the shape of your answers, not the digits.

**Level 1.** Open SQL Lab at `/lab`. Expand each table in the schema browser and say its grain aloud. In the Exercises tab solve `totals`, `status-counts`, `top-days`, `by-category` and `non-additive`; use Show hint before Show solution. "Check answer" compares your query's result with the reference, not the text, so a different but correct query passes. The sandbox is read-only with a 5-second timeout. Download the operations file from Practice files as CSV and check in a spreadsheet that total revenue matches the home dashboard.

**Level 2.** In SQL Lab solve `budget`, `moving-avg`, `rank-in-category`, `mom-growth`, `dedupe` and `cost-spikes`. Open Data quality at `/quality`, press Re-run checks and read each card (nine checks, some marked bad, some warn). Import `data_samples/operations_messy.csv`, read the validator's line-numbered errors, re-run the checks, then restore the clean file. At `/kpis` press Add starter KPIs to see good, warn and bad, then define Net margin % (higher) and Non-completed rate % (lower) and predict each status first. The builder uses the warn rule from idea 4. Notebook `02_pandas_explore` has "Your turn" cells that reproduce SQL in pandas.

**Level 3.** In the sandbox, `SUMMARIZE fact_operations` and `DESCRIBE fact_operations` are allowed, as is `EXPLAIN SELECT`. Solve `ytd`, `running-profit` and `below-avg-margin`. Open notebook `10_analyst_case_study`, finish its three "Your turn" cells (worst entity, overspend in dollars, best weekday margin) and write the memo in the last cell. Notebook `11_hypothesis_testing` has the permutation test and bootstrap interval, and shows the records-versus-days p-value trap. For BI tools follow `docs/TABLEAU.md` and `docs/BI_TOOLS.md`: export the data, rebuild the five builds, and reconcile revenue, margin and the most over-budget entity to SQL Lab. The repo's own note says these tool steps were not run in its build environment, so treat them as guidance.

**Level 4.** On `/kpis` write the full definition and a guardrail for each KPI, and compare with the Glossary page. In the Dataset hub add quality rules to an imported table and break one on purpose. Re-read your notebook-10 memo as its reviewer and reconcile every number.

**What the app does not cover.** It teaches no spreadsheet pivots or dashboard-tool skills beyond the guides, has no stakeholder conversation or requirements gathering, no version control or review workflow, and no governance: the Practice lab is a personal-scale tool, not an access-controlled system. Its insights and anomaly flags are rule-based leads, not verdicts. Metric dictionaries, review comments, memo writing and honest caveats you do by hand.
