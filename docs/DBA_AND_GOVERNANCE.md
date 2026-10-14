# Database administration and data governance

Two sections added to **Tracks → Data Engineering**: *Database admin* and *Data governance*.

## Database administration (DBA)
DuckDB is an embedded, single-file database: one writer, no user accounts. So this dashboard covers the parts of a DBA's job that apply, and states plainly what doesn't (roles, grants, replication: practise those in `postgres_practice/`).

* **Health**: engine version, file and write-ahead-log size, blocks used and free (free space left by deleted data), tables with row counts, primary keys, indexes and constraints, memory use, key settings.
* **Integrity checks**: records pointing at no entity (orphans), duplicate ids, missing required values, negative amounts, future dates, unused entities. Each says what to do.
* **Findings**: a short ranked list (no backups, stale backup, integrity failure, large WAL, missing primary key) with the action for each.
* **Growth**: file size and row count recorded at most hourly, so you can see the trend and plan disk space.
* **Query benchmarks**: six standard queries, each run three times (median shown), flagged over 250 ms, with the engine's plan. Re-run after importing more data to see how things scale; a rising time with the same plan just means more rows.
* **Checkpoint**: folds the write-ahead log into the main file. Harmless; run it before copying the file by hand.
* **Verify a backup**: opens a *copy* of the newest backup read-only, counts its tables and rows and compares them with the live data. A backup you have never opened is a hope, not a backup.

Vocabulary: **RPO** (recovery point objective: how much data you can afford to lose; set by backup frequency), **RTO** (recovery time objective: how long you can be down), **WAL** (write-ahead log: changes are written here first so a crash can be replayed), **checkpoint**, **index**, **constraint**, **vacuum/compaction**, **query plan**.

## Data governance
* **Catalog**: every table and view with an **owner** (accountable), a **steward** (looks after quality day to day), a description and a **classification**: public, internal, confidential, restricted. Each shows rows, completeness (% non-empty cells) and duplicate rows.
* **Retention**: how long you may keep data. Set a number of days and the date column it counts from; the catalog shows how many rows are past it. The app never deletes anything on its own: it tells you what is eligible and you decide.
* **PII scan**: finds probable personal data by column name and by a sample of the values (email, phone, national-ID pattern, card numbers by checksum, IP addresses). It reports *where* and *how sure*, never the values. It can miss free text and oddly named columns, so a clean result means "nothing obvious".
* **Protect from AI**: one click adds flagged columns to the workspace's blocked list. The AI then can't see them in the schema or in queries (see Settings for the limits of that guardrail).
* **Lineage**: where each table comes from (upload, saved source) and which views read it, plus what consumes the data (dashboards, exports, email, AI).
* **Controls checklist**: owners assigned, tables classified, personal data kept from the AI, a deliberate AI mode, a recent backup, retention on personal data, completeness, activity logging. Shown as "N of 8 in place" with the fix for each gap. It is a checklist, not a certification.
* **Access and egress**: the last 30 days of activity from the audit log, with exports, emailed reports and AI questions called out as the ways data leaves this computer.

Vocabulary: **data owner vs steward**, **data catalog**, **data classification**, **PII** (personally identifiable information), **data minimisation**, **retention and purge**, **lineage**, **data contract**, **least privilege**, **audit trail**. Frameworks you will meet at work: GDPR, CCPA/CPRA, HIPAA (health), SOX (financial reporting), PCI DSS (cards). This project does not make you compliant with any of them; it gives you the vocabulary and the controls to practise.

## Restore drill
The drill restores the latest backup into a temporary copy, compares row counts and reports pass or fail. It never touches the live workspace.

## Design tab: manager, architect, DBA and warehouse hats
The one Data Engineer track covers four roles. **Design** (Data Engineering, Tools) has: a Data architecture plan note, a store chooser (database, warehouse or lake), a star-schema suggester for any table (grain, additive and non-additive measures, dimensions, a table sketch), a Warehouse design note, a Data management plan note, and a data-ecosystem summary. Endpoints: `GET /api/pipeline/star?source=`, `POST /api/pipeline/store`. The agent can propose `architecture`, `warehouse` and `dmplan` notes. Not built (do by hand): NoSQL stores, Airflow/Beam, vendor ETL tools, cloud services, Hadoop/Hive/Spark clusters.

## Reliability and handoff tools (Data Engineering)
- **Stop publishing if checks fail** (Pipeline): the run happens in a staging copy and replaces your data only if quarantine, row accounting and the gold-to-silver reconciliation pass. A blocked run leaves the old data as it was and is marked in the history. Status always shows the reconciliation table.
- **Schema-change warning** (My data > Bring in a file): compares the incoming columns and types with the table of the same name before you replace it or add to it. The import result lists what changed and the audit log records it.
- **Add only new rows**: append by key (rows whose key is not already there; duplicates inside the file count once) or by date (rows after the newest date). Running it twice adds nothing the second time.
- **Health scorecard** (Design): scores each table 0 to 100 on accurate, reliable, compliant and accessible (completeness, duplicates, freshness, backup, protected personal data, classification, owner and steward, description). 80 or more is ready. A weekly review (on by default, can be switched off) records what got worse or better.
- **Data issues** (Design): analysts, scientists and BI users, or their agents, log data problems; the engineer triages by severity, replies and closes them.
- **Bundle check**: `python scripts/check_bundle.py ../your.zip` flags `.env` files, API keys, database files, run data and the computer-control flag before you share a zip. Add `--personal` for your own other computer (keys and data allowed, computer control still flagged). The personal bundle script runs it for you.
Limits: the scorecard is a guide, not a certificate; the check finds common key formats and file types, not every possible secret.

## Change capture (CDC)

Design > **Change capture (CDC)** has two steps. *Compare two snapshots* finds inserted, updated and deleted rows between an old and a new copy of a table, on a key you choose, and can save a change feed (`_op`, `_seq`). *Apply a change feed* turns a feed into a current-state table (SCD type 1) or a full history (SCD type 2, with `__start_at`, `__end_at` and `is_current`). Events are ordered by the sequence column, so late arrivals are placed correctly. Results are always new tables; your inputs are never changed. Log-based capture from a live database and streaming sources are not available here.

## Modern pipeline ideas

Design > **Modern pipeline ideas** maps the Big Book of Data Engineering to this app and lists plainly what is not available (Databricks products, cloud Auto Loader, Kafka and real-time mode). Imports can keep extra columns in a `_rescued` JSON text column (append modes). The pipeline now checks volume against the last run, flags a quarantine jump, and can skip a run when the source file has not changed.


## Relational design (ERD, keys, dependencies)

Design tab > Relational design, also under Analysis Lab > Data foundations. From a database fundamentals course.

- **ERD to tables:** list entities, attributes and relationships (1:1, 1:N, M:N). It writes DuckDB `CREATE TABLE` statements in dependency order, adds a primary key if you forget one, builds a link table for many-to-many, and runs everything on a throw-away in-memory database to prove it works. It never changes your data.
- **Keys and dependencies:** for the built-in example or any imported table (up to 12 columns): degree and cardinality, candidate keys (up to three columns, no blanks), single-column rules A -> B that hold, and hints about partial and transitive dependencies. You can also test a functional or multi-valued rule and see where it breaks. These are findings in the data, not proofs: confirm them with the data's owner.
- **Reference:** relational model terms, deployment topologies, shared disk vs shared nothing, replication, partitioning and sharding, roles and tools, and Db2, MySQL and PostgreSQL. Those servers cannot run here.
- The course notes have slips, listed in the tab: reflexivity is not "X -> X", closure is not "the minimal set of FDs", its example calls EmployeeID a candidate key when the real key is EmployeeID + ProjectID, and it stores the author inside the book table. Course statistics and free-tier limits are dated.
