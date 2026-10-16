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

## One place for a job (pinned job bar)

- Type the job in the top box. **Go** suggests dashboards; **Start as job** asks for a client and a field (guessed from your words, changeable), creates an active job with a first step, pins it and opens that field's dashboard.
- The pinned bar (work mode, every page) shows the job, its total time, a Start/Stop timer per step, Done, add a step, a note on the current step, Field, Switch job, and Close job (choose what to invoice; a draft invoice only, nothing is sent). Collapse it with the arrow; Unpin removes it. It is remembered in this browser only.
- Only one timer runs at a time. If one runs on another job, the bar says so and has Stop it.
- Home > Open jobs: **Work on it** pins that job and opens its field dashboard.

## Known issues and support dates

On the IT repair and Cybersecurity dashboards (work mode), under the tools: **Is this still supported?** (endoflife.date: type windows, ubuntu, macos and so on, with an optional version) and **Flaws attackers are using now** (CISA Known Exploited Vulnerabilities: search by vendor, product or CVE). No key. The CISA list is downloaded about once a day and searched locally, so your search words stay on your computer; only the product name goes to endoflife.date. Both keep a saved copy for 24 hours and fall back to it, with its date, if the site is unreachable. A match means check the vendor's fix; no match does not prove a machine is safe. Dates can change, so confirm on the vendor's page before telling a client.

## Work team and practice kits

**Practice kits** (job page > Practice materials, Practice workspace only): each practice job except IT repair and Cybersecurity has made-up files (download, copy or look), the ask, what done looks like, and an answer key you reveal after trying. The data is generated the same every time and the key is computed from it. Everything is labelled practice.

**Work team** (pinned job bar > Draft with the team): off until you turn it on, with a daily run cap (default 3, max 20; each run is up to four AI calls: Gemini, OpenAI and Claude draft, Claude judges, falling back to another judge if Claude fails). Works in both workspaces.
- Practice: the team reads the job's practice files automatically (never the answer key).
- Real: AI access must be allowed for the workspace in Settings (off by default). The team sees only the title, your instructions and what you paste; client names and secrets are removed; a pasted table is summarised on this computer (counts, ranges, duplicates, blanks) and the rows are not sent.
- IT repair, Networking, Cybersecurity: advice and checklists only, never "it is fixed".
- The result (final, judge notes, the three drafts) is a draft in the Assistant desk. Nothing is sent to a client and nothing is run. Check it against the real data or equipment, then accept or discard.
- If one AI has no key or fails, the others continue; with one answer there is no judge and it says so. Not yet tested against the live providers.

## Agents and tools together

In work mode on a wide screen the field's AI agent sits to the right of the Tools, so you can ask while you work. The agent can run the same calculators as the tools (Networking: subnet, VLSM, summarize, overlaps, contains, split, transfer time, bandwidth-delay, config audit, capture reader. IT: capacity, availability, RAID, event logs. Security: log analysis and search. Data analyst and Data scientist: forecast, variance, profit what-if, distribution fit, DAX) and quotes the result. These are local calculations on numbers or text it is given: no DNS, port or website checks, nothing saved, nothing sent to a client. If a job is pinned in the job bar, the agent can read it (title, steps, your notes; practice jobs also show the practice files, never the answer key) and its "How it answered" panel lists every tool it used. It still cannot change anything: drafts come with an Add button. Other fields' agents keep their existing tools.

## Debate (agents)

Type a question in a dashboard's ask box and press **Debate**. Gemini and OpenAI each answer as the field agent (using the dashboard tools and your pinned job); Claude only judges and writes one report: Answer, Agreed, Disagreed (which side the tool results back), Verify. Off by default with its own daily cap (Agent panel). The result shows the token count for each AI and the judge. If one debater fails, the other is shown as a single unjudged answer; if Claude fails, another AI judges. Typing a job in the top box and clicking a suggested dashboard now puts your text in that dashboard's ask box (press Send or Debate; nothing is sent automatically).

## Faster job flow
- **Standard steps by field**: starting a job (quick start, paste intake, or the top box) creates that field's usual steps in order; the first is ready to time.
- **Paste a client message** (Home, Work mode): paste an email or text, press Read it. Rules (no AI, no tokens) suggest client, job, dashboard, due date and a draft quote from your price list. You edit anything, then Start this job. Nothing is created until you confirm and nothing is sent to the client.
- **Do the next step** (job bar): the field's agent drafts help for the current step using the pinned job, its tools and your past fixes. It is a draft you can copy into a note; nothing changes on its own. Needs an AI key.
- **Keys** (job bar, when not typing in a box): T timer, D done and start next step, N note, A add step, C close job, ? help.
- **Today strip** (top of Home): next or late job, late invoices, follow-ups, steps due, jobs ready to close, running timer; one click each.
- **Lazy loading**: dashboard panels load when opened. The IT dashboard's JavaScript dropped from about 1770 KB to about 1100 KB.

## Client messages and outreach
- **Write a client message** (Home, Work mode): pick a type (reply, quote follow-up, job finished, review request, late payment nudge, set up a time, extra work, thank you, check in, intro), optionally paste their message, press Make the draft. A free template always appears. Tick "Also write an AI version" for an AI draft (names, emails, phone numbers and secrets are removed first; it never promises a price or date). Copy button on each. Nothing is sent.
- **Who to contact this week** (top of Leads): built from your own records, no AI: leads due, contacted/quoted leads with no next step after 3 days, quotes older than 3 days, and past clients you have not worked with for 45 days. Each row has a Free draft and an AI draft button.

## Upload a file (every page)
An **Upload a file** button sits under the top box on every page. It reads csv, tsv, txt, log, json and md files (up to 25 MB), looks at the first row, and picks the reader: a Windows Event Viewer export goes to the event log reader (findings shown right there); business data (record_date, entity_id, revenue...) is pointed to the Import box on Home, where you see the checks first; anything else is previewed for the agent. "Get agent output" sends the first 4,000 characters (secrets removed) to the dashboard's agent and gives a Copy button. Nothing is stored and nothing changes your data. The event reader now also accepts an `event_id` column name, and the Home importer's error says when a file is really an event log.

## Technician skills for the Computer Engineer and IT agents
Both agents now have a `repair_guide` tool that searches the 78 built-in repair guides (the How to repair tab) and returns the best match: symptoms, likely causes, steps, tools, the safety note and when to escalate. The Computer Engineer agent's scope now includes hardware diagnosis and repair (no power, no display or POST beeps, overheating, bad battery or charging, failing drives, power supply and component checks with a multimeter). Agents walk you through one step at a time with the safety note first. Read-only; nothing is changed or sent.

## Computer science (Computer Engineer dashboard)
A **Computer science** section under the Computer Engineer tools: **Big-O estimate** (paste a function; Python is parsed and never run, other languages are read as text; flags nested loops, unmemoised recursion, `in` on a list inside a loop, string building in a loop), **Step through** (bubble, insertion, selection, merge and quick sort, and linear and binary search, on your own numbers with comparison and move counts and the first 60 steps), and a **Cheat sheet** (data structures, growth rates, sorting costs). The Computer Engineer agent can use the same three tools (`big_o`, `sort_steps`, `search_steps`) and its scope now covers algorithms, data structures, Big-O and how code uses memory and time. All local; no AI needed for the screen.

## Electrical, HVAC and appliances (Computer Engineer dashboard)
For reference, planning and quoting; **licensed trades do the licensed work** (household wiring and panels, gas, refrigerant and sealed systems).
- **13 new repair guides** (How to repair tab and the `repair_guide` agent tool): washer, dryer, refrigerator, dishwasher, microwave, oven and range, water heater, garbage disposal, window and portable AC, central AC, furnace, thermostat, and airflow and sizing. Each leads with safety and says when to stop and call a licensed professional.
- **Electrical and HVAC lab** under the Computer Engineer tools: wire size and voltage drop, circuit load (with the 80% continuous rule), energy cost, rough AC sizing, AC air-temperature split check, Ohm's law, and a "who does what" table. The agent has the same calculators. A rough sizing is only a starting point; a contractor's load calculation decides.
- Jobs with appliance, HVAC or electrical words in the title go to the Computer Engineer dashboard with matching starter steps.

