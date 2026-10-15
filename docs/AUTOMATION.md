# Automation: what runs by itself, and what never does

## Runs by itself (no AI, no cost, sends nothing)
- **Today panel** (Home): built from your data each time you open Home. Late invoices come with a polite reminder already written; you copy it and send it yourself.
- **Recurring jobs** (Clients, per client): "monthly on day 1" or "weekly on Monday". The job and its steps are created the first time the app runs on or after that day, once per period. If the computer was off, it catches up next time it runs.
- **Timer warning**: after 2 hours on one timer the Today panel flags it. The 12-hour cap still applies when you stop it.
- **Ready to close**: when every work item on a job is done, the job page and Today say so.
- **Backup reminder**: for the Real workspace, if no outside backup folder is set or the last outside copy is a week old.
- Already there before: weekly plan snapshot, weekly restore drill, alert check, daily backup of Real data.

## AI prep drafts (opt-in, capped)
Turn on in the Today panel under "AI prep drafts". Off by default.
- Always **OpenAI**. If its key is missing you get a plain message, nothing is sent.
- **Daily cap**: 1 to 50, default 10. Counted per workspace per UTC day and kept across restarts. Every call that reaches OpenAI counts, including failures, so a broken setup cannot loop. At the cap it stops until tomorrow.
- **Per work item**: "Draft a first pass (AI)" gives likely causes, questions to ask the client, and what to verify. **Per table**: "AI first look at this table".
- **Automatic drafts** for new work items are a separate switch, need AI mode "full", and handle at most 3 items per check, still inside the cap.
- **What is sent**: the item's title, note and job title, plus matching hand-written reference approaches. Never the client name or contact details. For a table: column names, types, counts and number ranges only (common text values only in AI mode "full"). Blocked columns are left out. AI mode "off" blocks everything.
- Drafts are labelled as AI first passes and can be deleted. They can be wrong. Nothing a draft says is run or sent anywhere.

## Deliberately not automated
Emailing clients, sending invoices, taking payments, running generated code, changing client systems, live capture or scanning.

## Assistants, not decision-makers
- **Assistant desk** (Home): every draft waits here. Read it, edit it, then **Accept** or **Discard**. "Accept and save as my example" keeps your edited version so the assistants read it first the next time a similar case comes up (client names are removed when saved; it is reference material, not training).
- **Job descriptions**: each of the 12 field assistants has a "does" and a "never" line, shown to the agent. Rewrite them in the Assistant desk; "Back to default" restores mine. Your lines cannot switch off the safety rules the app already enforces.
- **Activity and used rate**: how many drafts were made, accepted, edited and discarded, and the share of decided drafts you used. A low rate means the drafts aren't helping yet.
- **Closing note**: on a job page, "Draft the closing note (AI)" writes what was done, how to avoid it next time and what to watch, from the job's steps only (no client name). It appears in the client summary only after you accept it, and is shown as plain text.

## Learned for Eivanta
On every job page, one line after (or during) the job: what did this client's data or questions teach you for Eivanta Analytics? Pick a type (messy file, short history or forecast, owner's brief, time to first number, a question the owner asked, other). Client names and secrets are removed when saved. "Download all notes" gives a markdown file grouped by type, with Practice-workspace lines marked (sample). Only use a client's data in Eivanta testing with their permission.

## My projects (Settings, General tab)
Quick links to Eivanta Analytics and Project AIDA: Open the app in a new tab, copy a folder path (a web page can't open a folder, so paste it into File Explorer), and "Check what is running" shows which links answer on this computer. The check only ever contacts localhost addresses, with a one-second limit. The starting links were read from the project-aida and nexusflow-portal folders (AIDA dashboard 8501, AIDA API 8006, Eivanta app 3000, Eivanta API 8000, plus both folder paths). Change any of them and press Save. If you already saved your own list, it is kept.

## How-to videos

Home, More, Watch and learn, **How-to videos** (also linked from every job page, which lists lessons that share a word with the job title).
A lesson is a title, a field, an optional job type and a pasted link (YouTube, Vimeo or any web page). **Watch** opens the link in a new tab. Nothing is downloaded or stored: a lesson is a few KB.
Add chapters (one per line, like `1:05 Remove the bezel`); on YouTube and Vimeo each chapter opens the video at that time. Keep notes (passwords and keys are blanked) and mark a lesson watched or watch-again. Remove a lesson with Remove, then Yes, remove (the video on its own site is not touched).

## Triage checklists

More, Watch and learn, **Triage checklists**, and a **Triage checklists** section on every job page. Three starting lists: **Slow database triage**, **Network rack and cabling tidy-up** and **Huge data file cleanup**, each in five stages with a short reason under every step.
On a job, press the list's button to start it, tick steps as you go (ticks and a note are saved with the job), print it, or remove it. The checklists page shows them read-only for printing.
They were written from the three PDFs you supplied: the database one (CC BY 4.0, reworded and shortened for small databases) and two vendor whitepapers (only the problems they describe; their statistics and product claims are not used). They are a first pass, not a standard: change what doesn't fit the job.
Nothing is sent to an AI, and nothing runs commands. Notes have passwords and keys blanked.

## PDF downloads
Real PDFs (made on the backend, no browser print dialog): invoice (Clients), client job summary (Job page), quote (Quote builder), price list and triage checklists (Settings, Quotes and prices; Checklists page). Dashboards and Packs/Company/BI already had PDF reports.
Every page also has a "Save page as PDF" button in the header. It opens the browser print window; choose "Save as PDF" as the printer. A print stylesheet forces light colors and hides menus and buttons.

## Money, leads, site notes and business backups
- **Money** (`/money`): who owes you (invoices marked sent, grouped by how late; polite reminder drafts that get firmer with age but never threaten; thank-you and review-ask drafts), profit per job (charged minus parts, per hour, flagged under 75% of your rate), and expenses, mileage and a tax set-aside. The set-aside is a percent you choose and the mileage rate is one you keep current; it is a planning aid, not tax advice. CSV export for a tax preparer. Everything is a draft you send yourself.
- **Quote to job to invoice:** the quote builder (Settings, Quotes and prices) saves a quote as a job in "quoted" status; "Quote accepted" on the job page makes it active; closing the job invoices it.
- **Leads** (`/leads`): source, quote and outcome; "Won it" creates the client and job. Win rates are shown only as a hint until about five leads are finished.
- **Site notes** (Clients and Job pages): devices, network layout and recurring problems per client, secrets blanked on save, printable site sheet.
- **Fix library:** the existing Fix log now has a "Checklist (PDF)" button that turns a saved fix into a printable checklist.
- **Business data backup** (Settings, Data and backups): zips the state file (clients, jobs, invoices, leads, books, fix log, notes), about once a day while the app runs, each with a restore test (checksum, health and record counts on a scratch copy). Restore takes a safety bundle first. The older Backups copy only the DuckDB file, which did not include these records.
- **Also worth doing** on Home: leads waiting, unbilled work, drafts, quotes waiting for a yes, thank-yous and the business backup warning.
