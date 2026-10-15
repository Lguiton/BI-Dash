# Agents and your past work

The agents (Claude, Gemini, OpenAI) do not learn between questions. What they can do is read. For the **IT Specialist, Cybersecurity and Network** agents,
the dashboard searches your fix log for fixes that share words with your question and hands the best few (up to 3) to the agent as notes.
The reply line then says "started from your past fix: ...".

* Only when the workspace AI mode is **full**. In "summaries only" nothing from your records is sent; with AI off there is no agent.
* Only fixes from that agent's area. Client names and ticket numbers are not passed on. Secrets were blanked when the fix was saved.
* A weak match (one common word) is ignored. A fix that was only a workaround, or not fixed, is labelled as such.
* It finds words, not meaning. A fix saved with different words can be missed, and a similar-looking fix may not apply. The agent is told to say when the case differs.

## Checking it (AI Lab > Agent checks)
* **Check past-work lookup (free):** uses built-in sample fixes, never your records. Six checks: it finds the fix, passes its steps, labels it as your notes, flags workarounds, passes nothing for an unrelated question, hides client names, and passes nothing in "summaries only".
* **Run field-work questions (live):** nine real questions (three per field) scored against a keyword rubric. It costs a few API calls and counts toward the daily caps. It is a floor, not a grade: read the replies.
* Runs are saved so you can compare before and after a change.

## Send to agent (Web panel)
Open the Web panel on any dashboard and press **Send to agent**. The agent is chosen from the dashboard you are on (a field page picks that field's agent; a track page picks its own; otherwise IT Specialist), and you can change it. Select text in **Reader (text)** view and press "Use my selection", or paste text from a live page, then type your case and what you want.
* The page text goes to the agent as a labelled **outside source**: data it must not obey, may be wrong or out of date, to be checked before use. Passwords and keys in it are blanked. It is capped at 4,000 characters, and you see the count.
* It goes to your AI provider, so leave out client details.
* For the IT, Cybersecurity and Network agents, **Save to fix log** stores the answer as "Not fixed yet" with a "from web" tag. Open the Fix log tab to mark it fixed once you have confirmed it works.

## Worked examples

`backend/app/content/worked_examples.json` holds hand-written "problem, steps, check" examples, two per agent. When your question shares at least two keywords with an example for that agent, up to two are added to the agent's prompt, labelled as reference material rather than instructions. They are the same for everyone, contain no client data, and are not training. To add your own, append an entry (track, keywords, problem, steps, check) and restart the backend. A question worded very differently can miss an example.
