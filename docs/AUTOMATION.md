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
