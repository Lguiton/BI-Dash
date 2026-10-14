# Part 4: Data Engineering

## The role in one page

A data engineer moves data reliably from where it is created to where it is used, and makes sure it is trustworthy when it arrives. The data comes from files, applications, exports and APIs. It ends up in tables that analysts, scientists and dashboards read. In between, you clean it, check it, reshape it, schedule it and watch it.

You work closely with analysts, who tell you which numbers matter and notice when they look wrong. You work with data scientists and machine learning practitioners (see Parts 2 and 3), who need stable, well-labelled tables. You work with application developers, who own the source systems, and with security and compliance people, who care who can see what.

A typical day starts with a check of overnight runs: did every job finish, is the newest data fresh, did the count of rejected rows jump? Then you fix or improve one pipeline: a new source, a new validation rule, a slow query. You write a test for whatever you touched. Later you answer "why does this number differ?", which usually ends at a definition, a duplicate or a late row. You finish by writing down what you changed.

Good looks like this. Pipelines are incremental, so they process only what is new. They are idempotent, so running one twice does no harm. They are tested, so a change that breaks a rule fails loudly. They are observable, so you know about a problem before an analyst does. Bad rows are quarantined with a reason, never silently dropped. Backups are proven by restoring them.

What it is not: it is not building dashboards (that is analysis), and it is not choosing the fanciest tool. A cron job and a SQL file are often the right answer.

The hard parts, honestly:

- The source data is always messier than promised, and it changes without notice.
- Failures are often partial: half a load succeeds and nobody sees.
- Much of the work is invisible when it goes well, so you must make it visible through monitoring.

## How to use this part

Four levels, at about five hours a week.

| Level | Focus | Hours | Weeks at 5 h/week |
|---|---|---|---|
| 1 Foundations | ETL and ELT, cleaning, medallion layers | 15 to 20 | 3 to 4 |
| 2 Practitioner | Incremental, idempotent, tested pipelines; dbt | 25 to 30 | 5 to 6 |
| 3 Advanced | Orchestration, Spark, Postgres, observability | 25 to 30 | 5 to 6 |
| 4 Expert | Backups, governance, failure modes, team practice | 20 to 25 | 4 to 5 |

That is about four to five months.

Pair reading with doing. Each level has a "Practice on your own" section of labs that need only a laptop, a SQL engine (SQLite, DuckDB or PostgreSQL), a scripting language such as Python, and a text editor. The labs build their own small data, so nothing needs downloading. Some labs suggest optional tools (an orchestrator, a distributed engine, a BI tool, containers); these are heavier, so treat them as stretch goals and say honestly in your notes what you did and did not verify.

Read a concept, do the lab, then try the exercises. Say the checkpoint answers aloud. A final optional section, "Match it in the app", maps each level to a companion application.

## Level 1: Foundations (beginner)

### What you will be able to do

- You can explain ETL and ELT and choose between them for a small case.
- You can profile a messy file by counting its problems before you fix any.
- You can decide, for each problem, whether to fix, drop or quarantine, and say why.
- You can explain bronze, silver and gold in one sentence each.
- You can reconcile rows in against rows out and explain any gap.
- You can run a small bronze, silver and gold pipeline and read its row counts and checks.

### Core ideas

#### ETL and ELT: where the transformation happens

ETL means extract, transform, load: the pipeline reshapes data in its own code (pandas, Spark) and loads only the finished result. ELT means extract, load, transform: raw data lands first and the transformation runs inside the warehouse as SQL. The answer is the same; the difference is where the work happens and what you keep. ELT keeps the raw data, so you can re-transform it when a definition changes. A good first exercise is to do both on the same table and check that they agree.

Worked example, with the one trap worth learning early. Category A has revenue 1,000 and profit 400. Category B has revenue 3,000 and profit 1,800. Margins are 40 and 60 percent. The overall margin is (400 + 1,800) / (1,000 + 3,000) = 55 percent. The average of the two margins, 50 percent, is wrong. Margin is a ratio, so you sum first and divide last: in SQL, SUM(profit) / SUM(revenue). Write that rule as a comment next to every margin you define.

#### Profile first, then clean

Real exports are messy. A typical messy file has dollar signs and commas in numbers, text such as N/A, two date formats, impossible dates, spelling variants in categories, and duplicates. Start with a rule: read everything as text (in pandas, dtype=str) so nothing is silently converted, and count each problem before touching it.

Worked example. To find revenue values that are not plain numbers, use the pattern -?\d+(\.\d+)? with str.fullmatch, and count the failures. To fix "$1,234.50", strip the symbols with str.replace(r"[$,]", "", regex=True), then convert with pd.to_numeric(errors="coerce"). Anything that cannot convert becomes missing, so you can count it: a before number and an after number you can explain.

#### Fix, drop or quarantine

Each problem gets one of three treatments. Fix when the intended value is certain: trimming spaces, "$1,234.50" to 1234.50. Drop when the row is an exact duplicate and nothing is lost. Quarantine when the row is wrong in a way you cannot repair, such as an unparseable date or a negative revenue: set it aside with a reason so a person can look.

Never throw rows away without a trace. Keep a rejected table with a reason column and report how many rows were rejected. If the count suddenly doubles, something upstream changed, and that is a finding. Never silently throw rows away.

#### Bronze, silver and gold

The medallion pattern names three layers. Bronze holds the raw rows exactly as received, all as text, plus load information. You never edit bronze, so you can always replay. Silver holds typed, de-duplicated, validated rows; the rejects go to quarantine. Gold holds business-ready aggregates, which is what dashboards read.

A small pipeline can implement this with DuckDB and Parquet files, or with plain tables in SQLite or Postgres named bronze_ops, silver_ops, quarantine_ops and gold_daily. Suppose a clean file of 8 valid rows over 4 days goes in: you expect 8 bronze rows, 8 silver rows, 0 quarantined and 4 gold daily rows (one per day). Parquet is a compressed, column-oriented file format that DuckDB can query directly.

#### Reconcile rows in against rows out

Every pipeline should be able to say where each row went. Suppose a messy raw file has 12 rows. One is an exact duplicate of another. One has the date 2026-13-45, one has revenue of -50, and one has the status "Bogus". The pipeline should report 12 bronze rows, 8 silver rows and 3 quarantined rows with reasons (unparseable date, bad revenue, unknown status), and it should know the duplicate was collapsed.

Now account for it: 12 = 8 silver + 3 quarantined + 1 duplicate. Every row is accounted for. If a count came to 11 you would stop and find the missing row before anyone used the output. You can be strict: a looser rule such as "silver plus quarantine must be at least 90 percent of distinct raw ids" would let a small loss slip through. A small unexplained gap deserves a sentence in your notes, not a shrug.

### Practice on your own

Create a file messy.csv of about 20 rows with columns fact_id, record_date, unit_id, category, revenue, cost and status. Plant these problems: two exact duplicates, a "$1,200.50" revenue, an "N/A", a date of 2026-13-45, a negative revenue, a category typo ("Logistcs") and a status "Bogus".

1. Profile first: count each problem with a query or script before changing anything.
2. Do the same aggregation (revenue and margin per category) twice, once ETL style in pandas and once ELT style, loading the raw table into a SQL engine and using a query. Check that they agree.
3. Build bronze (raw text), silver (typed, de-duplicated) and quarantine (with a reason column) tables, then a gold daily table.
4. Reconcile rows in against rows out in one sentence.
5. Decide, for each planted problem, whether you fixed, dropped or quarantined it, and write why.

### Exercises

1. A query shows margins of 30 percent for a row with revenue 200 and 70 percent for a row with revenue 800. What is the combined margin?
2. Name one benefit of ELT over ETL.
3. Write a Python expression that removes "$" and "," from a text column called revenue.
4. For each, choose fix, drop or quarantine: " ENT-01 "; a date of 2026-13-45; an exact duplicate row; revenue of -50.
5. Which layer is never edited, and why?
6. A load reads 1,000 rows and writes 940 clean plus 50 rejected. What do you do?
7. Write SQL against a table raw_ops that returns total revenue per category and a margin percent rounded to 2 places.

### Answers and hints

1. Profit is 60 + 560 = 620 on revenue 1,000, so 62 percent, not 50.
3. df["revenue"].str.replace(r"[$,]", "", regex=True)
4. Fix (trim and upper-case); quarantine; drop; quarantine.
5. Bronze, so you can always reconstruct later layers.
6. Ten rows are unaccounted for. Find them: duplicates removed, rows lost in a join, or a counting bug. Do not publish until the gap is explained.
7. SELECT category, ROUND(SUM(profit) / SUM(revenue) * 100, 2) AS margin_pct FROM raw_ops GROUP BY category;

### Checkpoint

Say aloud:

1. What is the difference between ETL and ELT?
2. Why is margin a ratio of sums?
3. What does each medallion layer hold?
4. When do you quarantine rather than fix?
5. What is Parquet?
6. Why count problems before cleaning?
7. What does "rows accounted for" check?

Common mistakes:

- Averaging row-level ratios instead of dividing sums.
- Dropping bad rows without recording how many.
- Reading files with automatic type conversion and trusting it.
- Editing raw data instead of keeping it untouched.

## Level 2: Practitioner (intermediate)

### What you will be able to do

- You can explain a watermark and say why a re-run reads the watermark day again.
- You can make a load idempotent with a key and a "latest wins" rule.
- You can add a validation rule to the pipeline and write a test that proves it.
- You can build and test a small dbt project and say what its tests guarantee.
- You can find a weakness in a pipeline by running it twice and comparing counts.
- You can describe a pipeline's behaviour using its run history.

### Core ideas

#### Incremental loads and the watermark

A full reload copies everything every time. An incremental load copies only what is new. The usual device is a watermark: remember the largest date (or id) already loaded, and next time read only rows at or after it. In a typical medallion pipeline the watermark is the newest date in silver, saved in a small state file.

Worked example. A source file holds 100 rows, 10 per day over ten days. The first run reads all 100 into bronze and saves the watermark, day 10. The second run, with no new data, reads only rows dated day 10 or later: 10 rows. The filter is date >= watermark, not >, on purpose. Late rows for the watermark day may arrive after the first load, and ">" would miss them forever. Re-reading the day costs a few rows; the key in silver makes the repeat harmless.

A test shows the rule: with F1 on 1 January and F2 on 2 January loaded, adding F3 on 3 January should read two rows (F2 and F3), and silver should then hold three.

#### Idempotency: running twice changes nothing

A job is idempotent if running it twice gives the same result as once. You need it because jobs get retried, re-run by hand, and backfilled. The technique has two parts: a business key (fact_id) and a rule for duplicates. Here silver is rebuilt from all bronze files, keeping the latest copy of each key:

```sql
SELECT * EXCLUDE (_loaded_at, reason, rn) FROM (
  SELECT *, row_number() OVER (PARTITION BY fact_id ORDER BY _loaded_at DESC) AS rn
  FROM verdict WHERE reason IS NULL
) WHERE rn = 1
```

The same query handles late corrections. A test for late corrections loads F1 with revenue 100, then a later file with F1 at 150. Silver then holds one row for F1, with revenue 150. Gold is always rebuilt from silver, so it follows. Compare the mistake: appending to silver instead of de-duplicating would double every row on a re-run, and a re-run test comparing counts would fail. Break it on purpose once; it teaches faster than reading.

#### Validation rules and the tests that prove them

Rules live in one place: a CASE expression that gives each bad row a reason. In order, the first matching reason wins: missing fact_id, unparseable date, bad revenue, bad cost, unknown status. To add a rule that rejects zero or negative durations, insert one line before the ELSE:

```sql
WHEN duration_minutes IS NOT NULL AND duration_minutes <= 0 THEN 'bad duration'
```

Then write a test (in pytest style, say): build a tiny CSV with one good row and one row with duration 0, run the pipeline into a temporary folder, and assert one silver row and one quarantined row. A rule without a test is a hope.

A caution worth testing for. Suppose a messy file has 12 rows and the first run quarantines 3. Now re-run with no new data. The rows of the watermark day are read into bronze again, and a bad row among them is quarantined again, so the count reads 4. Silver stays the same, so the pipeline is idempotent where it matters, but the quarantine count is not. The fix is to de-duplicate quarantine by key, as silver does. Finding things like this is the job.

#### dbt: SQL models with tests and a dependency graph

dbt turns SQL files into tables or views, in dependency order, and tests them. A small project has a staging model (stg_ops, a thin renamed view of silver with no business logic) and two marts (daily_kpis and entity_scorecard). Models refer to each other with {{ ref('stg_ops') }}, which is how dbt knows the order and draws the lineage graph.

Tests come in two kinds. Generic tests are declared in schema.yml: unique, not_null and accepted_values. A singular test is a SQL file that returns the rows that break a rule, so zero rows means pass: tests/revenue_not_negative.sql is select * from stg_ops where revenue < 0. A project like this has 3 models and 8 tests: 3 on staging (unique and not_null on the key, accepted_values on status), 2 each on the marts (unique and not_null on their keys), and 1 singular.

Run dbt build from inside the project folder, because a model that reads Parquet by relative path depends on where you run it.

A mart is a promise: the daily mart is unique by date.

### Practice on your own

Using your Level 1 tables, write a small pipeline script in any language.

1. Add a watermark saved to a file, and a re-read of the watermark day. Run it twice with the same file and compare every count, including quarantine.
2. Make silver idempotent with a key and a "latest wins" rule. Then break it on purpose by appending, and watch your count test fail.
3. Add a rule rejecting durations of zero or less, and write a test with one good row and one bad row.
4. Simulate a late correction: change one row's revenue in a second file and confirm silver updates and keeps one row.
5. Optional: build a dbt staging model and one mart with tests (a DuckDB adapter works), and run dbt build.

### Exercises

1. The watermark is 2026-03-10 and the source has 5 rows on 10 March and 20 rows after. How many rows does the next run read?
2. Why would ">" instead of ">=" lose data?
3. A file is loaded twice and silver doubles. What was missing?
4. Write the dedupe rule in words.
5. A row arrives with status "Test". What does the pipeline do with it today, and why?
6. What does a dbt singular test return when it passes?
7. Where does business logic belong, in staging or in a mart, and why?

### Answers and hints

1. 25 (the watermark day is re-read).
2. Late rows for the watermark day, arriving after the first load, would fall below the cut-off forever.
3. A key with a "latest wins" rule, so duplicates are collapsed.
4. For each fact_id keep the row with the newest load time.
5. It is quarantined as "unknown status", because the verdict step rejects any status not in Completed, Delayed, Cancelled or Failed.
6. Zero rows.
7. In a mart. Staging stays thin so every mart builds on the same clean basis.

### Checkpoint

Say aloud:

1. What is a watermark?
2. Why does the filter use >=?
3. What two things make a load idempotent?
4. How do you add a validation rule safely?
5. What are generic and singular dbt tests?
6. What does ref() give you?
7. What does re-running with no new data teach you?
8. Why is gold rebuilt from silver?

Common mistakes:

- Appending in a "load" step without a key.
- Using a watermark you cannot compare correctly (mixed date formats).
- Putting business rules in staging.
- Adding a rule without a test.

## Level 3: Advanced

### What you will be able to do

- You can describe what an orchestrator does and does not do, and read a DAG.
- You can reason about retries and quality gates, including what runs after a failure.
- You can explain when Spark is the right tool and when it is not.
- You can connect a BI tool to a data source and reconcile its totals to the source.
- You can use constraints, query plans, indexes, views and roles in PostgreSQL.
- You can design monitors for freshness, volume and rejection rate.

### Core ideas

#### Orchestration: when, in what order, and what happens on failure

An orchestrator schedules steps, orders them, retries failures and records what happened. It does not crunch data. The standard pattern keeps the work in ordinary functions and has the DAG (directed acyclic graph: tasks with arrows that never loop) simply call them. A good layout keeps extract, transform, validate, load and verify as plain functions that run without any orchestrator, and has the DAG wire them as extract >> transform >> validate >> load >> verify. Airflow, Prefect and Dagster are common choices.

Key settings in the DAG: schedule "@daily", catchup=False (do not back-fill every day since the start date), and default retries of 2 with a one-minute delay. A task that keeps failing is attempted three times in all, after waiting about two minutes in total, and its downstream tasks do not run.

Worked example. The validate step is a quality gate: it raises an error if more than 5 percent of rows were dropped. With 1,000 rows in and 940 out, 6 percent was lost, so the task fails and load never runs. With 960 out, 4 percent, it passes. Be honest about what you tested: a command-line run proves the tasks work, not that the scheduler is set up.

#### Spark: when one machine is not enough

Spark distributes work across machines, or across cores with local[*] on a laptop. It is lazy: transformations (select, filter, groupBy) build a plan, and nothing runs until an action (show, count, write) asks for a result. The DataFrame API and Spark SQL are two spellings of the same plan; .explain() shows it.

Be honest about scale. A practice table of a few thousand rows is tiny. DuckDB answers in milliseconds, and Spark's startup takes longer than the query. Reach for Spark when data does not fit one machine or one engine, not because it is on job adverts. It needs Java 17 or newer.

#### A BI tool is a consumer you must reconcile

Superset and Metabase are open-source BI web applications, cousins of Tableau. They do not move or clean data; they read a table and draw charts. The usual steps are to connect a database or upload a CSV, mark the date column as temporal and define metrics.

The engineering lesson is reconciliation. Define the margin metric once as SUM(profit) / SUM(revenue), then compare the tool's total revenue and margin with the warehouse. When they differ, the cause is nearly always a definition (a filter, an average of ratios), a duplicate or a time zone, and you find it by narrowing from the total down to a day. Some BI tools refuse certain sources by default for security reasons; relax such settings for practice only, never on a real server.

#### PostgreSQL: the database most employers run

DuckDB is built for analysis on one machine. PostgreSQL is a server with users, constraints and concurrent writers. Install it directly or run it in a container, create a schema with keys and constraints, and load a few thousand rows. PostgreSQL listens on port 5432 by default; a practice copy may use another port to avoid clashes.

Three habits to learn there. First, constraints refuse bad data at the door: a foreign key rejects an unknown unit, a CHECK rejects negative revenue, a primary key rejects a repeat. Second, read plans with EXPLAIN (ANALYZE, BUFFERS). With 3,650 rows over 365 days, a query for one date scans every row (a Seq Scan). After CREATE INDEX on record_date and ANALYZE, you may still see a Seq Scan, which is correct: on a table this small, scanning everything is cheap and the planner knows it. Indexes pay off as tables grow. Third, give people least privilege: an analyst role with USAGE on the schema and SELECT on its tables can read but gets "permission denied" on DELETE.

#### Observability: know before the analyst does

A pipeline that ran is not a pipeline that worked. The cheap checks that catch most trouble are freshness (how old is the newest day), volume (how many rows, compared with normal), rejection rate (how much went to quarantine) and reconciliation (rows in against rows out).

Worked example. Suppose a source normally delivers 10 rows a day, one per unit. If today's load brings 3, volume is 30 percent of normal: that is a data problem even though every job succeeded and silver has rows. A volume check compares today with the median of the last several days and alerts below, say, 70 percent. Write thresholds down and name who is alerted; an alert nobody owns is noise.

### Practice on your own

1. Wrap your Level 2 pipeline in a scheduler: cron is enough, or an orchestrator such as Airflow, Prefect or Dagster if you can install one. Add retries (2, one minute apart) and a quality gate that fails when more than 5 percent of rows are dropped. Make the first step fail on purpose and read what happens downstream.
2. Install PostgreSQL (or run it in a container). Create a table with a primary key, a foreign key and a CHECK on revenue, and try one failing insert of each kind. Read the error messages.
3. Load a few thousand generated rows. Run EXPLAIN (ANALYZE, BUFFERS) for one date, add an index, run ANALYZE and compare. Create an analyst role with SELECT only and test a DELETE.
4. Write a script that checks freshness, volume against the median of the last seven runs, and rejection rate, and prints PASS or FAIL for each.
5. Optional: redo one aggregation in PySpark (needs Java) or reconcile a BI tool's totals to your SQL.

### Exercises

1. A task has retries 2 and a delay of 1 minute. How many attempts, and how long is the total wait before it finally fails?
2. Set the gate to 5 percent. 2,000 rows in, 1,880 out. Pass or fail?
3. Give two reasons not to use Spark on a 3,650-row table.
4. Write a Spark SQL query for total revenue per category.
5. Superset shows total revenue 3 percent above the warehouse. List three causes to check.
6. Why can a Seq Scan be the right plan?
7. Write the GRANT statements for a read-only analyst.

### Answers and hints

1. Three attempts, about 2 minutes of waiting.
2. 120 / 2,000 = 6 percent lost. Fail.
3. Startup cost exceeds the work, and it adds infrastructure and a Java requirement for no gain.
5. A filter or date range differs; a duplicate in the upload; a definition (for example revenue before or after refunds, or a time zone shift on the date).
6. On a small table, or when the query needs most rows, reading everything is cheaper than using an index.
7. GRANT USAGE ON SCHEMA bi TO analyst; GRANT SELECT ON ALL TABLES IN SCHEMA bi TO analyst;

### Checkpoint

Say aloud:

1. What does an orchestrator do, and not do?
2. What happens downstream of a failed task?
3. What does lazy evaluation mean in Spark?
4. When is Spark the wrong tool?
5. How do you reconcile a BI tool with the warehouse?
6. What does a constraint protect you from?
7. What are the four observability checks?
8. How do you say honestly which parts of a setup you tested?

Common mistakes:

- Putting heavy logic inside the orchestrator instead of in testable functions.
- Letting a quality gate pass with no owner for its failure.
- Trusting a BI total without reconciling it.
- Treating "the job succeeded" as "the data is right".

## Level 4: Expert and professional judgement

### What you will be able to do

- You can state a recovery point and recovery time for a system and prove them with a restore drill.
- You can classify data, assign owners and stewards, and set retention you can defend.
- You can explain what an access guardrail does and does not protect, and say so plainly.
- You can use an audit trail to answer "who did what, and what left the building".
- You can review someone else's pipeline for failure modes using a short list of probing questions.
- You can describe the practices a team needs that a personal-scale project cannot give you.

### Core ideas

#### Backups, RPO and RTO, and the restore drill

RPO (recovery point objective) is how much data you can afford to lose, set by how often you back up. RTO (recovery time objective) is how long you can be down. A nightly backup at 02:00 means a failure at 01:00 loses 23 hours of changes, so the worst case is about 24 hours. To get an RPO of 4 hours you need a backup at least every 4 hours, six a day.

A backup for a single-file database can be a plain copy taken while no one is writing, so it is consistent. Restore copies one back after taking a safety backup of what is there now, so a restore can itself be undone. Automate it, and decide how many copies to keep; an automatic backup that only runs while some program is running is only as reliable as that program.

The engineer's point is that an unopened backup is a hope, not a backup. Verifying means opening a copy of the newest backup read-only and comparing table and row counts with the live data. A restore drill restores into a temporary copy and reports pass or fail, never touching live data. Time a drill: six measured minutes is evidence for an RTO; a guess is not. And RAID is not a backup: it keeps a disk failure from stopping you, but it faithfully copies a mistaken delete.

#### Governance: owners, classification, retention and personal data

Governance makes responsibility explicit. The owner is accountable for a dataset; the steward looks after its quality day to day. Classification labels sensitivity: public, internal, confidential or restricted. A data catalog lists every table with its owner, steward, classification, completeness and duplicates.

Retention says how long you may keep data, counted from a date column. Reporting is safer than automatic deletion: count the rows past the limit and let a person decide. Worked example: a 365-day rule on record_date, checked on 9 October 2026, has the cutoff 2025-10-09. If the table's first day is 2025-10-07 with 10 rows a day, two days, 20 rows, are eligible. Check again tomorrow and it is 30.

The PII scan finds probable personal data by column name and by a sample of values (email, phone, national-ID pattern, card numbers by checksum, IP addresses). It reports where and how sure, never the values, and it can miss free text and oddly named columns, so a clean result means "nothing obvious". The controls checklist ("N of 8 in place") is a checklist, not a certification. Frameworks such as GDPR, CCPA, HIPAA, SOX and PCI DSS exist; learning the vocabulary and the controls does not make you compliant with any of them.

#### A guardrail is not a vault

Many tools now put an AI assistant in front of your data. A sensible design offers access modes: off (nothing is sent), summaries only (totals, counts and averages, with a small cap on result rows), or full read-only queries. It also lets you list columns the assistant must never see, ideally seeded from your PII scan. These controls stop the assistant reading what you blocked through its normal tools, and they stop accidents.

They do not make the data safe. Anything the assistant may see is sent to the provider you chose. If the tool has no login, anyone who can open it on the machine or network can see the data. The honest wording is "guardrail, not vault". Real protection needs authentication, encryption and access control in the systems that hold the data. Practise data minimisation: if a column is not needed, do not load it.

#### The audit trail answers "who did what, and what left"

An audit trail records when, in which environment, which action and what detail, for imports, exports, emailed reports, AI questions, refreshes and backups, and it marks failed actions. Exports, emails and AI questions are the ways data leaves the computer, so review them over a recent window such as 30 days.

Worked example. An analyst asks, "did anyone export the operations data last week?" You filter the log for exports, find two, read the times and details, and answer from evidence. The log is also how you reconstruct an incident: a model version changed stage at 14:02, a backup was restored at 14:10. An audit trail is only worth having if you read it and if nothing can quietly edit it; a plain file on a machine with no login is only a learning model of the idea.

#### Reviewing a pipeline for failure modes

Reviewing is asking probing questions. Run it twice: do all counts hold, including side tables? (The quarantine growth in Level 2 is one result.) Kill it halfway: what state is left, and does the next run repair it? Change a column name or type at the source: does it fail loudly or load nulls? Send a late row, a duplicate, an empty file, a file twice the size: what happens? Change the time zone or the date format: do dates shift? Ask where the alert goes, who owns it, and what the runbook says.

Write findings as leads with evidence ("second run changed the quarantine count from 3 to 4"), not verdicts.

#### Operating at team scale

Teams need what a personal project does not provide. Data contracts are agreements with source owners about columns, types and change notice. Environments separate development from production. Access is by role, with reviews. Changes go through code review and tests in CI. There is an on-call rota and runbooks. Sensitive data (health data is the example that needs most care) is handled with minimum access and a clear legal basis from your compliance people.

Be honest about a personal project: it is single-user and local. When you present it, say what is not covered, and do not claim compliance.

### Practice on your own

1. Back up a database file, then restore it into a temporary copy. Compare table and row counts, and time the whole drill. Write down your RPO (from your backup frequency) and your measured RTO.
2. Build a catalog as a spreadsheet or table: every table, owner, steward, classification, a retention rule and its date column. Compute how many rows are past retention.
3. Write a short script that scans column names with patterns (email, phone, ssn, card) and a sample of values with regular expressions, and reports where and how sure, never the values. Test it on a table with one hidden email column and note what it misses.
4. Create an audit table (when, action, detail, ok) and write to it from your pipeline and backup scripts. Answer "did anything leave this week?" from it.
5. Review your own Level 3 pipeline with the failure-mode questions above, and write three findings as leads with evidence.

### Exercises

1. Daily backups at 03:00; a disk fails at 02:00. How much data can you lose in the worst case?
2. What is the RPO if backups run every 6 hours?
3. Why is a RAID mirror not a backup?
4. Explain the difference between an owner and a steward.
5. A 90-day retention rule counts from record_date. Today is 1 June. What cutoff date applies?
6. Why can the PII scan return a clean result on data that holds personal information?
7. List four questions you would ask when reviewing a pipeline someone else built.
8. Write a one-page recovery plan with RPO, RTO, how you will prove each, and who is told.

### Answers and hints

1. Up to 23 hours of changes.
2. 6 hours in the worst case.
3. It mirrors changes immediately, including mistakes and corruption, so a bad delete is copied.
4. The owner is accountable for the dataset and its use; the steward looks after quality day to day.
5. The cutoff is 90 days before 1 June, which is 3 March. Rows dated before that are eligible.
6. It works by column name and sample patterns, so free text or an unusual column name can hide personal data.
7. For example: what happens on a re-run, on a half-finished run, on a schema change, and who is alerted?

### Checkpoint

Say aloud:

1. What are RPO and RTO, and what sets each?
2. Why is an unverified backup a hope?
3. What does a retention rule do in this app, and what does it not do?
4. What does the PII scan report, and what can it miss?
5. What does "guardrail, not vault" mean?
6. What can an audit trail tell you?
7. What are four ways to probe a pipeline?
8. What does a team have that a personal project does not?

Common mistakes:

- Declaring an RTO nobody has timed.
- Believing a guardrail protects data from the provider.
- Claiming compliance because a checklist is green.
- Treating RAID or a sync folder as a backup.

## Capstone projects

### Capstone 1: A trustworthy cleaning step (small)

Brief: clean a messy export (one you build, or a public sample) and report on it.

Deliverables: the clean table; a rejected table with a reason per row; a one-page note giving rows in, rows kept, rows rejected and the three biggest problems.

Rubric (0 to 2 each): problems counted before cleaning; each problem fixed, dropped or quarantined with a reason; no silent row loss; rows reconcile; the note is readable by an analyst.

### Capstone 2: A tested incremental pipeline (medium)

Brief: extend your own medallion-style pipeline with a new rule and a freshness check, and prove both.

Deliverables: the duration rule plus a test; a freshness test that fails when the newest day is older than N days; a fix for the quarantine count growing on re-runs, with a test; a dbt build or equivalent SQL tests that pass.

Rubric (0 to 2 each): each change has a test that fails without it; re-run leaves every count unchanged; the watermark rule is explained in the notes; dbt tests (or equivalent) pass; the README says what was and was not verified.

### Capstone 3: A pipeline with a recovery plan (large)

Brief: run the pipeline on a schedule and make it recoverable and governed.

Deliverables: an orchestrated schedule (an Airflow-style DAG or a documented cron alternative) wrapping your pipeline with retries and a quality gate; volume and freshness monitors with thresholds and an owner; a backup and recovery plan with RPO and RTO proven by a restore drill; a catalog with owners, classifications and retention for every table, and a controls checklist you wrote yourself, with every item met or an honest gap noted; a short failure-mode review of your own work.

Rubric (0 to 2 each): schedule, retries and gate behave as claimed; monitors have owners; RTO measured, not guessed; governance entries are specific; the review lists real weaknesses; untested parts are labelled untested.

## Tools reference

| Tool | What it is for | When you outgrow it |
|---|---|---|
| A run log and check script | Watching one pipeline | You need many pipelines, alerting and long history |
| DuckDB and Parquet | Fast analytics on files and one machine | Many concurrent writers, or data beyond one machine |
| pandas | Cleaning and exploring in memory | Data larger than memory |
| pytest | Testing pipeline behaviour | Rarely; add data-quality tools alongside it |
| dbt (dbt-duckdb) | SQL models, tests and lineage | You need orchestration across many sources and teams |
| Apache Airflow | Scheduling, ordering and retrying jobs | You need managed scale or event-driven flows |
| Apache Spark | Distributed processing of very large data | Never for small data; consider managed services at scale |
| Apache Superset | BI dashboards on top of a database | You need governed semantic layers and wide rollout |
| PostgreSQL | A production relational database | Very large analytics or global scale |
| Backup scripts and an audit table | Backups and an audit trail at personal scale | Real access control, encryption, off-site backups |

## Glossary

- **ETL**: extract, transform, then load the finished result.
- **ELT**: load raw data first, transform inside the warehouse.
- **Pipeline**: a repeatable chain of steps moving and shaping data.
- **Bronze**: raw data exactly as received.
- **Silver**: typed, de-duplicated, validated data.
- **Gold**: business-ready aggregates.
- **Medallion**: the bronze, silver, gold layering pattern.
- **Quarantine**: a holding table for rejected rows with their reasons.
- **Parquet**: a compressed, column-oriented file format.
- **Watermark**: the newest value already loaded, used to find new rows.
- **Incremental load**: loading only new or changed data.
- **Idempotent**: running twice gives the same result as once.
- **Backfill**: re-running a pipeline over past periods.
- **DAG**: directed acyclic graph of tasks with dependencies and no loops.
- **Orchestrator**: a tool that schedules, orders and retries tasks.
- **Data quality gate**: a check that stops a pipeline when data is unacceptable.
- **Data lineage**: where data came from and what depends on it.
- **Constraint**: a database rule such as a key or a check that rejects bad rows.
- **Index**: a structure that speeds lookups at some write cost.
- **RPO**: recovery point objective, the data loss you can accept.
- **RTO**: recovery time objective, the downtime you can accept.
- **WAL**: write-ahead log, where changes are recorded first so a crash can be replayed.
- **Data steward**: the person who looks after a dataset's quality day to day.
- **PII**: personally identifiable information.
- **Retention**: how long data may be kept.
- **Audit trail**: a record of who did what and when.

## Career notes

Roles this part leads to: data engineer, analytics engineer, ETL or pipeline developer, data platform engineer, database administrator, and (with Part 3) MLOps or machine learning engineer. Titles vary a great deal between employers, so read the duties.

How to show your skill: publish the three capstones with tests and a README that states what was and was not verified. Show a pipeline that survives a re-run, a rule with its test, a dbt docs site and a recovery plan with a timed restore. Write short post-incident notes on things you broke.

What to learn next: deeper SQL and query plans, a cloud warehouse and object storage, streaming concepts, infrastructure as code, and security basics (see Part 9). Cloud and vendor certifications exist for data engineering and databases; check the current exam objectives before choosing one, and use them alongside a portfolio.

## Match it in the app

This section maps the part to the project's dashboard, for readers who have it running. Nothing above depends on it. Use the Practice workspace, which holds a made-up year of operations data (3,650 records, 10 units, 365 days, newest day 2026-10-06) that you can break freely.

**Level 1.** Open the Pipeline monitor at /pipeline, choose the clean source and press "Run pipeline". Expect bronze 3,650, silver 3,650, quarantine 0 and gold 365. Read the four checks (freshness, silver has rows, rows accounted for, quarantine under 20 percent). Freshness allows 2 days, so depending on the date it can fail; that is the check working. Tick "Start over (wipe the lake)", pick the messy source and run again: expect bronze 3,684, silver 3,146 and 511 quarantined (unparseable date 200, bad revenue 171, bad cost 83, unknown status 57). Those 511 rows cover 504 distinct ids, and 3,146 + 504 = 3,650. Notebooks 04_etl_vs_elt and 03_clean_messy_data (with a worked solution in python_practice/solutions) match the two Level 1 labs.

**Level 2.** In data_engineering, run python medallion.py twice: the second run reads 10 bronze rows, the watermark day 2026-10-06, and silver stays at 3,650. Run python -m pytest tests -q and read tests/test_medallion.py (quarantine, idempotent re-run, incremental load, late correction). Re-run the messy file with no new data and watch the quarantine count move from 511 to 527 while silver stays at 3,146: the caution in Level 2. In dbt_project, dbt build runs 3 models and 8 tests; run it from inside that folder.

**Level 3.** Open /apache and read Spark, Airflow and Superset in turn (concepts and "Try it" steps). apache_practice/airflow/etl_steps.py runs without Airflow; the DAG bi_daily_etl has retries of 2, a one-minute delay, catchup off and a 5 percent gate. The DAG's five tasks were run with airflow dags test; the Docker routes for Airflow and Superset were not verified. In postgres_practice, Docker starts Postgres 16 on port 5433, load_data.py loads 3,650 rows into schema bi, and exercises.sql covers plans, indexes, constraints and a read-only role (the loader was checked on a real server; the compose file was not run).

**Level 4.** In Settings & backups, take two backups, set "Keep the latest" to 1 and watch pruning, then restore one. Set AI access (Off, Summaries only with up to 20 rows, Full with up to 40) and add blocked columns; read the note that it is a guardrail, not a vault. On the Database admin tab (under /tracks/engineering) run "Verify a backup"; on Data governance set owners, classifications and retention, run the PII scan and read the controls checklist ("N of 8"). Then find your actions in the Activity log (/activity).

**What the app does not cover.** Streaming, cloud warehouses and object storage, infrastructure as code, CI, data contracts with real source teams, multi-user access control, encryption, off-site backups, and on-call practice. The pipeline monitor keeps 25 runs, the quarantine count is not de-duplicated, and it is a single-user local tool.
