# How-to manuals and AI agents

Every discipline dashboard (Analyst, Scientist, ML, Data Engineering, AI, Project & Product, Systems Analyst, Full Stack) has three views:

* **How-to manual**: an ordered playbook. Each step says what to do, how, the tool to open (the button jumps to the right tab), how you know you are done, and the usual mistakes. Ticking steps is your own record.
* **Tools**: the working dashboards for that discipline.
* **AI agent**: a chat for that discipline. A **search bar sits at the top of every discipline page**: type a question ("which risk is biggest?") or an instruction ("draft 5 requirements for a billing portal", "take me to the schedule tab").

## What an agent can and cannot do
It can read a summary of your workspace's numbers, run read-only SQL (the same policy-checked tools as the AI Lab), explain the manual step you are on, suggest opening a tab or page, and **draft** things for you to approve: backlog items, risks and OKRs (Project & Product), requirements (Systems Analyst), KPIs (Analyst), catalog entries and safe maintenance actions such as a checkpoint (Data Engineering).

It **cannot** change anything by itself. A draft appears as a card with an Add button; the existing, validated API does the write only when you press it. Links open only when you click.

## Privacy
Agents follow the workspace's AI privacy mode (Settings): **off** = the agent refuses (Real starts off); **summaries only** = it sees counts and scores but no titles or names; **full** = titles are included. This is a guardrail, not a vault: whatever the agent reads is sent to the AI provider whose key you configured. Each chat is logged in the Activity log.

## Which model answers
Agents use the same routing as the AI Lab, decided from what you typed: simple questions go to Gemini, medium ones (comparisons, trends, summaries, drafts) to OpenAI, complex ones (code, statistics, forecasting, multi-part or 'why' questions) to Claude. If that provider has no key, has hit its daily cap or errors, the next one is tried. Each agent reply shows the tier and provider it used.

## Setup
Put at least one key in `backend/.env` (see `.env.example`), restart the backend, and check the status chip on the agent view. Without a key the manual and tools still work; the agent says so plainly. Limits: 10 AI questions per minute (shared with the AI Lab) and the per-provider daily caps.

## Honest limits
The agent plumbing is covered by tests that use a scripted fake model (no network, no cost). Real model quality depends on the provider you use, so verify its numbers (SQL Lab) and treat its drafts as drafts.

## Transparency, usage, evals and quizzes
Every agent reply can show its trace (tools used, what each returned, sizes). The AI Lab Usage tab counts calls per provider and tier; cost appears only if you set `BI_PRICE_<PROVIDER>_IN` / `_OUT`. Agent evals: the route check is free; a live check makes up to 6 real calls and tests structure only, so it cannot tell you an answer is good. Each manual has a checkpoint quiz. Replies render safe markdown; daily caps reset when the backend restarts.
