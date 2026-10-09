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
