# Chapter brief (for authors of The Practitioner's Library)

Audience: one self-taught adult learner (Lamarcus), personal use, no prior degree assumed in the field. Plain, direct, warm-but-professional prose. No hype. Honest about limits.

## File format
One Markdown file per discipline at /home/claude/bi/book/chapters/<NN>_<id>.md (pandoc-flavoured markdown). Start with `# Part N: <Discipline>` then `##` for sections, `###` for subsections. No YAML. No raw HTML. Tables are pipe tables. Code in fenced blocks with a language. Do not include images. Do not invent URLs; name books/standards/certifications only if you are confident they exist, and say "check the current exam objectives" for certs.

## Required structure (use these exact `##` headings, in this order)
1. `## The role in one page` - what the person does, who they work with, a typical day, what good looks like, what it is NOT, and honest hard parts.
2. `## How to use this part` - the 4 levels, the time estimate per level (hours/weeks at ~5 h/week), how to pair reading with the dashboard.
3. `## Level 1: Foundations (beginner)` 
4. `## Level 2: Practitioner (intermediate)`
5. `## Level 3: Advanced`
6. `## Level 4: Expert and professional judgement`
7. `## Capstone projects` (three, increasing in size, each with a brief, deliverables, and a self-assessment rubric)
8. `## Tools reference` (table: tool, what it is for, when you outgrow it)
9. `## Glossary` (20-30 terms, one or two lines each)
10. `## Career notes` (roles/titles it leads to, how to show your skill, what to learn next; no salary figures; certifications only generically with a "check current objectives" note)

## Each Level section (3-6) must contain, with `###` subheadings
- **What you will be able to do** (4-7 verifiable outcomes, "you can ...")
- **Core ideas** : 4-8 concept subsections, each 150-350 words, with a concrete worked example (real numbers, real commands, real SQL/Python/config as relevant) that you have mentally checked for correctness.
- **Practice in the dashboard** : specific, using the Practice workspace and the named screens/tools of this discipline (listed in your assignment). Say what to click or run and what you should see/decide.
- **Exercises** : 5-8 numbered exercises, progressively harder, each answerable without the author. Put worked answers for at least half of them in a `### Answers and hints` subsection.
- **Checkpoint** : 6-10 questions the learner should answer aloud before moving on, plus 'common mistakes' (4-6 bullets).
Level 1 assumes nothing. Level 4 covers design trade-offs, failure modes, reviewing others' work, ethics/honesty, and operating at team/organisation scale.

## Length and quality
Target 5,500 to 7,500 words per part. Depth over breadth; worked examples over definitions. Every number, formula, command, port, protocol fact, and SQL must be correct; if unsure, leave it out or say it varies. Keep the dashboard's honest labels: guardrail not vault; findings are leads not verdicts; offensive/cloud tools are taught about, not built; tools run on pasted text and public hosts; RAID is not a backup; helpdesk/inventory are personal-scale trackers.
Cross-reference other parts sparingly as "see Part N".

## Parts list
1 Data Analyst (analyst); 2 Data Scientist (scientist); 3 Machine Learning (ml); 4 Data Engineering (engineering); 5 AI Engineering (ai); 6 Project and Product (pm); 7 Systems Analyst (sysanalyst); 8 Full Stack Developer (fullstack); 9 Cybersecurity (security); 10 Network Engineer (network); 11 IT Specialist (itsupport).

## Source material in the repo (read first, do not copy verbatim)
/home/claude/bi/docs/*.md, /home/claude/bi/LEARNING.md, /home/claude/bi/README.md, and the track definition in /home/claude/bi/backend/app/routers/tracks.py (learning path, tools, projects). For dashboard screens, read the matching panel in /home/claude/bi/frontend/src/components/panels/ and the service in /home/claude/bi/backend/app/services/. Do not modify any file except your own chapter files.


## REVISION (overrides anything above that conflicts) - general learning book first
The book must teach each discipline as a GENERAL learning path that works with any tools (a reader with no dashboard must lose nothing). Therefore:
- Remove the `### Practice in the dashboard` subsection from every level. Replace it with `### Practice on your own`: tool-agnostic labs (free/open tools named generically, e.g. "any SQL engine such as SQLite, DuckDB or Postgres", "a spreadsheet", "a virtual machine", "a home router").
- Exercises and examples must not depend on the app's screens, endpoints or file paths. Use self-contained data (small inline tables) so they work anywhere.
- Opening sections ("The role in one page", "How to use this part") should not mention the dashboard.
- Keep the honest-limits ethos (defensive only; own systems; findings are leads) but phrase it generally.
- ADD, as the LAST `##` section of the part, `## Match it in the app` : a short section (400-900 words) mapping each Level to the dashboard's matching screens/tools/notebooks, saying what to click or run and what to expect, plus which parts of the discipline the app does NOT cover (be honest). Put app-specific content ONLY here. In "Career notes" and "Glossary" remain general.
- Section order therefore: role, how to use, Levels 1-4, Capstone projects, Tools reference, Glossary, Career notes, Match it in the app. Capstones must be general (app match goes in the last section).
