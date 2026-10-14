# Analysis Lab

Page: **Labs > Analysis Lab** (`/analysis`). Three dropdowns pick what you see: **Method**, **Type of analytics**, **Data to analyze**.

| Method | Descriptive | Diagnostic | Predictive | Prescriptive |
|---|---|---|---|---|
| Quantitative | Summary, distribution (centre, spread, shape, confidence interval), trends and patterns, business metrics (margin, monthly revenue, burn), filtering | What drives it, compare groups (t-test, ANOVA), correlation, probability, regression, outliers | Forecast (trend + pattern, or ARIMA-style), regression what-if, probability, clusters, bought together, machine learning | Decision brief, opportunities, reach a goal, best allocation, track the result |
| Qualitative | Observations, theme finder | Post-mortems, theme finder | SWOT, scenario plan | Pre-mortem, pivot decisions |
| Data foundations | File formats, big data practice, BI challenges, BI components, BI tool categories (with LibreOffice steps), BI project requirements, Identify the data, Where data comes from, Gather and import, Data wrangling, Data cleaning, Privacy and security |

## Honest limits
- ARIMA here is AR + differencing only (no moving-average or seasonal terms); it is always compared with "same as last time".
- "MRR" is monthly revenue, not true subscription MRR.
- Word-list sentiment is rough; read the examples.
- Prescriptive output rests on historical association, not proven cause. It never changes data by itself; "Before you act" checks inputs and "Track the result" watches what happens next.
- Big data practice runs on this computer (DuckDB, 1 GB memory, 2 threads, rows capped by free disk). It teaches the ideas; a real cluster is only needed at hundreds of GB.

## Files it can import
CSV/TSV/TXT, Excel, JSON (nested is flattened), JSON lines, XML (DOCTYPE/ENTITY refused), PDF with ruled tables (needs `pdfplumber`, in `backend/requirements.txt`). Guide: `GET /api/data/formats`.

## API (`/api/stats/*`)
`sources`, `describe`, `filter`, `probability`, `timeseries`, `arima`, `regression`, `diagnose`, `opportunities`, `business`, `cluster`, `associations`, `outliers`, `predict`, `ml-models`, `goal`, `allocate`, `brief`, `input-check`, `track`, `qual`, `themes`, `themes/upload`, `bigdata`, `bigdata/job`, `bigdata/generate`, `bigdata/benchmark`.

## Data cleaning
Data foundations > Data cleaning inspects an imported table (missing, duplicate, extra spaces, inconsistent case, numbers or dates stored as text, outliers), lets you pick a fix per problem, writes a cleaned COPY (the original is never changed), re-inspects it, and saves a Wrangling log note. API: `GET /api/stats/clean/inspect`, `POST /api/stats/clean`.

## Statistics
`POST /api/stats/distribution`, `/compare`, `/correlation`.

## AI agents
The Analyst and Scientist agents have a read-only `analyze` tool (describe, distribution, compare, correlation, timeseries, arima, business, diagnose). Agents still cannot change data.

## Not built (do by hand when needed)
Live APIs, web scraping, RSS and streams; cloud services (Dataprep, Watson, Trifacta, Snowflake and similar); R and SAS; OpenRefine; encryption of the database file (use disk encryption); a built-in anonymized export; sign-in and roles.

## AI mode: the AI does the whole job

Data Analyst and Data Scientist pages (AI agent tab) and AI Lab → "AI mode: full BI work" have a **Do the full job for me** button. The agent works through the role's manual with the same read-only, privacy-checked tools as the chat (up to 16 tool rounds) and returns a full written deliverable ending with a list of every number it relied on and its source. Your own findings go in a box beside it for comparison (not saved). Last 12 runs are kept per workspace (`/api/agents/{analyst|scientist|bi}/complete`, `/work`). It changes nothing in your data. It needs an AI provider key, and numbers should be verified.

## Statistics fundamentals
Descriptive tabs: **Data types** (nominal, ordinal, interval, ratio), **Frequency table** (absolute, relative, cumulative; bar, pie, Pareto), **Distribution** (adds population sd, coefficient of variation, interval table), **Cross table** (counts, row %, chi-square, Cramér's V). Diagnostic tabs: **Hypothesis test** (mean, z or t, one- or two-sided, power; margin of error and sample size calculator) and **Sampling (CLT)**. Data foundations has a **Statistics reference** with Excel, Sheets and LibreOffice formulas. Endpoints: `/api/stats/variables`, `/frequency`, `/crosstab`, `/meantest`, `/sampling`, `/margin`. Not built: SVM, a calibration chart.


## SQL and pandas cookbook (Data foundations)

Four tabs from a set of cheat sheets: **SQL cleaning recipes** (13: NULLs, duplicates, trim and case, split a name, dates, special characters, phone digits, outliers, typos), **SQL interview (50)** (each answer runs on a built-in sample), **pandas cheat sheet** (with the SQL equivalent for each command) and **Learning sites** (copied from a poster; the app cannot check them).

- Everything runs as a SELECT on a throw-away in-memory sample, never your data. UPDATE and DELETE versions are shown as text with a warning.
- The sheets used MySQL words. This app runs DuckDB, so the recipes use COALESCE, strpos, try_strptime, strftime, string_split and `regexp_replace(..., 'g')`. Without the `g` flag only the first match is replaced.
- The sheet's `df.append` was removed in pandas 2.0; use `pd.concat`.
- The Data cleaning tab gained three steps that apply to a cleaned copy and log it: keep only digits or letters (`strip_chars`), split a column in two at a delimiter (`split_text`), and find and replace text (`replace_text`).
