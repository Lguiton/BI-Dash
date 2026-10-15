# Test data and the security check-up

## Test data
Run `python scripts/seed_test_data.py` from the project folder with the virtual environment active (the app must be running; a `.bat` launcher comes later). It switches to the **Practice** workspace and adds made-up data through the app's own API:

* the sample operations data (BI dashboards, KPIs, quality)
* the business dashboard packs' sample rows
* 4 clients, 8 jobs in different states, time entries, follow-ups, one invoice marked sent
* 4 items in the home-screen work log (one overdue)
* 10 fixes in the fix log (IT repair, Cybersecurity, Network) plus one that proves secrets are blanked
* a project-management example and a website scenario
* every tool of all 17 field packs, run once with its own sample inputs (61 steps in all, all passing)

It never touches Real (`--real --yes-real` is required for that, and you should not). Running it twice adds more rows; it deletes nothing. To start clean, switch Practice back with Settings > Data and backups.

## Security check-up (13 Oct 2026, run against the live backend)
Passed: host check (a foreign Host name is refused), cross-site writes refused (403), no CORS allowance for other sites, security headers present,
path traversal on document routes returns 404, SQL lab is read-only and cannot read files or write outside (COPY, ATTACH, read_csv on /etc/passwd all refused),
868 requests with junk input produced 0 server errors, an oversized upload is capped (413 path), `pip-audit` and `npm audit` found nothing, no key-shaped text in the tracked files.

Things to know:
* Login is **off by default**. That is correct only while it listens on 127.0.0.1. Before hosting, set `BI_AUTH=1` and a 12+ character `BI_OWNER_PASSWORD`.
* Computer control is the most powerful feature. Leave `computer_control.enabled` untracked (now in `.gitignore`) and keep the PIN set.
* Saved models are Python pickles: never import a model file someone else sends you.
* Keep a copy of `backend\data\backups` on another disk.

## Work log
The home screen has a "What I'm working on" list: add an item, move it To do > Doing > Waiting > Done with one button, keep a "where I left off" note, and add log lines. Overdue and due-today items show badges. Items are per workspace (Practice and Real keep separate lists) and are never deleted when finished.

## AI routing
Simple questions go to Gemini; medium ones (comparisons, trends, summaries) to OpenAI; complex ones (ML, deep learning, NLP, data science, statistics, math, code, forecasting, multi-step) to Claude. A provider with no key, a reached daily cap or an error is skipped and the next is tried. Claude's daily cap is 150 (`BI_LIMIT_ANTHROPIC`).
