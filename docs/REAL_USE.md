# Using the dashboard for real data

This is a single-user tool: no logins, one person, one machine. It is built so your own numbers can live next to the practice material without ever touching it.

## Two workspaces
| | Practice | Real |
|---|---|---|
| Database file | `backend/data/bi_warehouse.duckdb` (the original) | `backend/data/bi_warehouse_real.duckdb` |
| Starts with | demo data | nothing |
| AI | full | **off** until you turn it on |
| Backups | manual | manual + daily (on by default) and a safety backup before destructive actions |

Switch with the Practice / Real buttons at the top of any page; the page reloads so every number comes from the other file. Your choice is remembered. Study progress, ML run history, settings, sources and the activity log live in a small SQLite file (`bi_warehouse_state.sqlite`) shared by both.

## Getting data in
1. **One-off file.** My data → pick a CSV, Excel (.xlsx) or JSON file. You see the detected columns and types before anything is saved. Semicolon, tab and pipe separators are detected. Numbers like `$4,200.50` become numbers; codes like `02134` stay text; dates are read as `YYYY-MM-DD` or `MM/DD/YYYY` (day-first dates such as `31/12/2026` are not guessed, to avoid silently swapping day and month).
2. **Straight into the operations dashboards.** Choose "Feed the operations dashboards" and say which of your columns is the date, the entity, revenue, cost and units. If your file has no such column, type a fixed value (for example `ALL`).
3. **Sources.** Save a file in a folder, a web link, or a database query once, then refresh on demand or on a schedule.

### Source types
* **File in a folder**: files in `backend/data/inbox/` (or any folder listed in `BI_SOURCE_DIRS`). Paths outside those folders are refused, including `..` tricks and symlinks.
* **Web link**: an `http(s)` CSV, JSON or Excel URL. For a private API put the token in `backend/.env` (`MY_API_TOKEN=...`) and enter only the variable name. Redirects are followed; the download is capped at 50 MB.
* **Database query**: Postgres (put `PG_URL=postgresql://user:pw@host/db` in `.env`, enter `PG_URL`) or a SQLite file in an allowed folder. Only a single `SELECT` is accepted, and the connection itself is read-only, so the database refuses writes even if a query tried to sneak one in. Use a read-only database user anyway.

### What makes a refresh safe
* The new data is read and type-checked completely before the old table is touched, then swapped in as one step. A failure leaves the old table exactly as it was.
* A "replace" that would leave the table with under 50% of its old rows is refused (usually a broken export).
* In Real, a safety backup is taken first.
* Every run, good or bad, is recorded in the source's history and the activity log.

Scheduled refreshes run inside the API process, for the workspace that is open, while the app is running. If the app is off, nothing refreshes. To refresh from the command line (cron or Task Scheduler), stop the API first (DuckDB allows one process to write at a time) and run `python scripts/refresh_sources.py --workspace real`. Turn the built-in scheduler off with `BI_SCHEDULER=0`.

## AI and privacy
Per workspace, in Settings:
* **Off**: nothing is sent to any AI provider.
* **Summaries only**: the assistant may only run totals, counts and averages, and sees at most 20 result rows.
* **Full**: any read-only query, up to 40 rows.
* **Blocked columns**: hidden from the assistant's view of the schema, rejected in its queries, and rejected if they appear in a result.

These are guardrails, not a vault. They stop the assistant from reading what you blocked through its normal tools and they stop accidents. Whatever it is allowed to see is sent to the provider you chose. A column could still leak if you rename it in a view or paste its values into your question. If the data must not leave your computer, keep AI off.

## Backups
Settings → Backups. A backup is a copy of the database file taken in a few milliseconds while the connection is closed. Restoring first saves the current state as a "safety" backup, so a restore can be undone. Keep the latest N (default 14); safety copies are kept separately (latest 10). Download a backup to store it somewhere else. **Backups sit on the same disk as the data**, so copy them off the machine now and then (an external drive or cloud folder) if the data matters.

## Where it runs
* **On your own computer (recommended).** Start the backend and frontend as in the README. Nothing is exposed to anyone else.
* **Reachable from your phone or another computer.** Use a private network tool such as Tailscale and open the dashboard through the machine's private address, with `BI_CORS_ORIGINS` set to that address and `NEXT_PUBLIC_API_URL` pointing at the API. Do **not** put it on the public internet: there is no login, so anyone who finds it can read and delete your data.
* **A hosted server or Docker.** Not set up here. Without a login that would be unsafe, and the Docker files in this repo have not been tested. If you want this, the next step is adding authentication first.

## Limits
Up to 1,000,000 rows and 300 columns per table, 50 MB per upload. There is no multi-user access control, no row-level security, and no encryption of the files on disk (use disk encryption if the machine could be lost).
