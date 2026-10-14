"""How to do it / how to fix it: plain-English guides for the problems Data Analysts, BI developers, Data Scientists and Data Engineers hit most.

Guides are text to follow in your own data. Nothing here changes a table. Where a step could lose or alter data, the caution says so and tells you to work on a copy.
Search matches your words against titles, keywords and the steps themselves."""
from __future__ import annotations

import json
import re

GUIDES: list[dict] = []
REF: dict[str, str] = {}      # a tool finding's ref -> guide id


def _g(gid, title, area, keywords, why, steps, verify, minutes, caution="", tool="", refs=()):
    GUIDES.append({"id": gid, "title": title, "area": area, "keywords": keywords, "why": why, "steps": list(steps), "verify": verify, "minutes": minutes, "caution": caution, "tool": tool})
    for r in refs:
        REF[r] = gid


# ------------------------------------------------------------------ Data Analyst
_g("an-avg-ratio", "Averaging percentages or rates gives the wrong answer", "Data Analyst", "average of averages ratio rate percent mean wrong weighted", "The average of daily rates is not the overall rate, because busy days count the same as quiet ones.",
   ["Find the two raw numbers behind the rate (for example orders won and orders quoted).", "Add each up over the whole period first.", "Divide the two totals once. In Question to answer choose 'ratio' with the top column and bottom column.",
    "Compare it with the average of the rates. If they differ a lot, the weighting matters and the ratio of totals is the one to report."], "Check one period by hand: total top divided by total bottom matches the tool's answer.", 10,
   "Averages of rates are only fine when every row has the same size.", "Analyst tools: Question to answer", ("ratio_warning",))
_g("an-dup-rows", "Counts look too high: duplicate rows", "Data Analyst", "duplicate duplicates double counting repeated rows count too high inflated", "Repeated rows inflate counts and totals.",
   ["Pick the columns that should identify one real record (an order number, or customer plus date).", "Open Data Engineering > Dedupe and look at the preview: how many groups repeat and a few examples.", "Decide which copy to keep (first, last, newest).",
    "Make the new table. The original stays as it was.", "Point your question at the new table and re-run it."], "The row count drops by exactly the previewed number and the key columns are now unique.", 15,
   "Two different real records can share a key. Look at the examples before you remove anything.", "Data Engineering tools: Dedupe and merge")
_g("an-join-explosion", "Totals doubled after joining two tables (join explosion)", "Data Analyst", "join explosion duplicate keys many to many multiplied rows double count merge", "If the key repeats in one table, each repeat multiplies the rows of the other table, so sums double count.",
   ["Before joining, count rows in each table and count repeated key values in each.", "If the right table repeats a key, collapse it to one row per key first (Dedupe, or summarise it).", "Join again and check the row count equals the left table for a left join.",
    "If many matches are real, sum on the many side only, never on a column from the one side."], "A left join returns the same number of rows as the left table, and the totals match the original table.", 20,
   "", "Data Engineering tools: Merge preview", ("join_explosion",))
_g("an-dates-wrong", "Dates read wrong (day and month swapped, or text)", "Data Analyst", "date format day month swapped text dates parse 03/04 american european", "A date like 03/04/2026 is March 4 in the US and 3 April elsewhere. Tools guess, and sometimes guess wrong.",
   ["Look at the largest value in the first slot: if anything is above 12 it must be the day.", "Tell the import which order your file uses (the preview shows how dates were read).", "If a column mixes formats, clean it in the Wrangle step before loading.", "Spot check three dates you know."], "Three known dates match, and no date is in the future or before your business existed.", 10,
   "Re-loading with a different format changes every date, so keep the original file.", "Data page: import preview")
_g("an-nulls", "Blank values change your answer", "Data Analyst", "null blank missing values empty na average skewed", "Averages and counts quietly skip blanks, and a blank is not the same as zero.",
   ["Count the blanks in each column you use (Profile on the data page).", "Ask why they are blank: not recorded, not applicable, or really zero.", "Choose: leave blank and say how many, fill with a known value, or remove the rows, and write the choice down in your notebook.", "Show the count of blanks next to the result."], "The result states how many rows were left out.", 10)
_g("an-outliers", "One huge value is skewing the result", "Data Analyst", "outlier outliers extreme median skew huge value mean", "A single mistake or one giant order can drag an average far from what is typical.",
   ["Sort the column high to low and look at the top ten.", "Check whether the biggest ones are errors (extra zero), one-offs, or real.", "Report the median beside the average. Use the Question builder with median.", "If a value is wrong, fix it in a cleaned copy rather than deleting it from the original."], "The median and average are close, or you can say why they are not.", 10,
   "Never remove a value only because it is inconvenient. Write down what you removed and why.")
_g("an-small-sample", "Is the difference real or luck? (small samples)", "Data Analyst", "significance small sample p value luck random difference ab test confidence", "With few rows, results swing a lot by chance.",
   ["Use A/B test analyzer for yes/no results or the means test for numbers.", "Read the range of plausible difference, not just the p-value.", "If the range includes zero, say 'no clear difference yet'.", "Use the sample-size calculator to see how many more you need."], "You can state the plausible range in plain words.", 15,
   "A p-value is not the chance the change is real. Do not stop a test the moment it looks good.", "Analyst tools: A/B and survey")
_g("an-survey", "Reading survey results fairly", "Data Analyst", "survey poll responses percent margin of error confidence small groups", "Percentages from small groups carry wide margins.",
   ["Count responses per group before comparing groups.", "Use the survey tool: it shows a range around each percentage.", "Do not compare groups whose ranges overlap and call one 'higher'.", "Say who answered: people who reply are often not typical."], "Every percentage you quote comes with its range or its count.", 10)
_g("an-pivot-total", "Pivot table totals do not match", "Data Analyst", "pivot cross tab total mismatch does not add up percent of total blank", "Totals can disagree when blanks are hidden, groups are filtered, or percent-of-total uses a different base.",
   ["Add a row for blank groups so nothing is dropped.", "Check that the grand total equals a plain total of the whole table.", "State the base of every percentage (of row, of column or of whole).", "Re-run with the same filters on both."], "Grand total equals the plain total of the column.", 10, "", "Analyst tools: Pivot")

# ------------------------------------------------------------------ BI
_g("bi-numbers-disagree", "Two dashboards show different numbers for the same thing", "BI", "different numbers mismatch kpi definition conflict two reports disagree source of truth", "Usually the two use different date ranges, filters or definitions.",
   ["Write both definitions in words: what counts, what is excluded, which dates.", "Compare the exact filters and the date range.", "Pick one definition and write it in the KPI dictionary with an owner.", "Update the other report to use it, and note the change date."], "Both reports show the same figure for the same period.", 30, "", "BI tools: KPI dictionary", ("kpi_conflict",))
_g("bi-stale", "Dashboard shows old data", "BI", "stale old data not refreshing outdated last updated schedule", "The source did not load, the scheduler was off, or the filter excludes new rows.",
   ["Check the data's latest date against today.", "Open Sources and see the last run and any error.", "Run the source now, then reload the dashboard.", "If your computer was asleep, the scheduler catches up when it wakes; confirm the 'last run' time."], "The latest date shown is yesterday or today.", 10, "", "Sources page")
_g("bi-kpi-choice", "Choosing the right KPIs for a client", "BI", "choose kpi metrics what to measure client dashboard too many vanity", "Fewer, owned numbers get used; long lists get ignored.",
   ["Ask: what decision will this number change?", "Keep 4 to 6 KPIs, each with an owner and a direction (higher or lower is good).", "Add one target per KPI only if the client can act on it.", "Put the definitions in the KPI dictionary and give it to the client."], "Each KPI answers a named question.", 30, "", "BI tools: Dashboard designer")
_g("bi-alerts-noisy", "Alerts fire too often or never", "BI", "alert noise too many alerts never fires threshold rule", "A threshold set at today's value flips constantly; one set too far away never fires.",
   ["Look at the KPI's usual range over three months.", "Set the rule just outside the usual range, or use 'worse by percent'.", "Start with a few rules, not twenty.", "Review after two weeks and adjust."], "A rule fires on a real problem and not on normal ups and downs.", 15, "", "BI tools: Alert rules")
_g("bi-client-report", "Making a report a client will actually read", "BI", "client report layout summary one page story recommendation scheduled monthly", "Clients read a headline, a recommendation and a few numbers.",
   ["Start with one sentence: what happened and why it matters.", "Show 4 to 6 KPIs and one trend.", "End with one recommendation and who does it.", "Schedule it monthly so it arrives without being asked."], "The client can say what to do next after one minute.", 20, "", "BI tools: Data story, Scheduled reports")

# ------------------------------------------------------------------ Data Science
_g("ds-no-better", "The model is no better than guessing", "Data Science", "model no better than baseline guess useless accuracy low not useful overfitting weak", "Sometimes the inputs simply do not explain the target.",
   ["Look at the baseline: the best simple guess (always the average, or always the most common class).", "If the model does not clearly beat it on unseen rows, say so; do not ship it.", "Check the target: is it measured reliably, and does it depend on things you do not record?",
    "Add inputs that plausibly cause the target, not ones that come after it.", "Try again; if it still fails, the honest answer is 'the data cannot predict this yet'."], "A model that beats the baseline by a margin you can state on rows it never saw.", 30, "A model that fails is a useful result: it saves a client from a bad bet.", "Model studio", ("no_beat_baseline",))
_g("ds-leakage", "The model looks too good: data leakage", "Data Science", "leakage leak too good accuracy perfect target future information cheating", "A column that is only known after the outcome gives the model the answer.",
   ["List every input and ask: would I know this before the outcome happens?", "Remove any column that is recorded after or because of the outcome (status, refund flag, final price).", "Rebuild and compare: honest accuracy usually drops.", "Split by time, not randomly, when the data is a timeline."], "Accuracy is believable and no input is a copy of the target.", 20, "", "Model studio", ("leakage",))
_g("ds-imbalance", "Rare outcome: 95% accuracy but useless", "Data Science", "imbalance rare class fraud churn accuracy misleading precision recall minority", "If 95% of rows are 'no', always guessing 'no' is 95% right.",
   ["Compare with the always-the-most-common baseline.", "Look at precision and recall for the rare class, not accuracy.", "Pick the threshold by cost: what does a miss cost versus a false alarm?", "Report how many real cases it catches and how many false alarms per catch."], "You can say 'it catches X of every 10 real cases with Y false alarms'.", 25)
_g("ds-time-split", "Split data by time, not at random", "Data Science", "time split random split train test future leakage temporal order validation backtest", "A random split lets the model peek at the future of the same period.",
   ["Sort by date.", "Train on the earlier part and test on the latest part.", "For forecasts use the rolling backtest in the Forecast studio.", "Report the error on the latest part only."], "No test row is older than any training row.", 15, "", "Forecast studio")
_g("ds-forecast-naive", "My forecast is no better than repeating last week", "Data Science", "forecast naive baseline seasonal no better trend repeat last value backtest", "Many business series are mostly last period plus noise.",
   ["Open the Forecast studio and read the backtest table.", "If 'repeat the last value' wins or ties, use it and say so.", "Add real drivers (prices, holidays, promotions) only if you record them.", "Show the range, not one line."], "Your chosen method beat the naive one across several test windows.", 20, "", "Forecast studio")
_g("ds-drift", "The model got worse over time (drift)", "Data Science", "drift model worse retrain decay concept drift data changed performance monitoring", "The world changes: new customers, prices or seasons make old patterns fail.",
   ["Run the drift check on recent rows.", "Look at which inputs shifted or show new values.", "Retrain on newer data and compare with the old model on the same recent rows.", "Schedule a drift check every month or quarter."], "The new model beats the old one on recent rows.", 30, "", "Model drift check", ("drift",))
_g("ds-segments-weak", "Customer segments overlap or look random", "Data Science", "segments clusters kmeans overlap weak silhouette customer groups meaningless", "KMeans always finds groups, even in data that has none.",
   ["Read the separation label: weak means the groups overlap.", "Try fewer columns that actually describe behaviour (spend, visits, recency).", "Try a different number of groups and see whether the story stays the same.", "Name a segment only if you can describe what to do differently for them."], "Each segment you keep has a different action.", 20, "", "Customer segments")
_g("ds-model-handoff", "Handing a model to a client", "Data Science", "handoff model card documentation limits deploy client explain responsible use", "A client needs to know what the model does, how well, and when not to use it.",
   ["Generate the model card from the saved model.", "Add the owner and a one-line purpose.", "Run a drift check and note the date.", "Agree who retrains it and how often."], "The client can say what the model is for and when not to trust it.", 20, "Do not use models for decisions about people without human review.", "Model card")

# ------------------------------------------------------------------ Data Engineering
_g("de-schema-drift", "A column was renamed or removed and reports broke", "Data Engineering", "schema change renamed column missing broke report drift new column type changed", "Sources change without telling you; anything reading the old name breaks or goes blank.",
   ["Run the schema change check against the saved baseline.", "For a rename, update every report, rule and query that used the old name.", "For a removed column, ask the source owner whether it is coming back.", "Once everything works, save the new shape as the baseline."], "The check reads 'same shape' and the reports show numbers again.", 20, "", "Schema change detector", ("schema_renamed", "schema_missing", "schema_type"))
_g("de-contract-fail", "The data contract check failed", "Data Engineering", "contract check failed rule broken validation not null unique range allowed values", "A rule you agreed on is broken: blanks, repeats, out-of-range or unexpected values.",
   ["Read which column and rule failed and look at the examples.", "Decide whether the source is wrong or the rule is out of date.", "If the source is wrong, send the examples to its owner or fix the cleaning step.", "If the rule is out of date, change the contract on purpose and note why."], "The next check passes.", 20, "", "Data contract", ("contract_fail",))
_g("de-types", "Numbers or dates loaded as text", "Data Engineering", "type text number date string loaded wrong cast currency comma symbol dollar", "Symbols, commas or mixed formats make a loader read the column as text.", 
   ["Look at a few raw values for the symbols that block conversion ($, commas, spaces, N/A).", "Add a cleaning step to strip them and convert.", "Convert into a new table, not the original.", "Check the min and max look right."], "Sorting works as a number or date and the totals match the source.", 15, "", "Wrangle")
_g("de-slow", "Loads or queries are slow", "Data Engineering", "slow performance load query speed large file memory laptop too slow", "Usually too much loaded at once, or unnecessary columns.",
   ["Run the volume estimator with your rows per day and columns.", "Query in the database (SQL) and pull only summaries.", "Drop columns you never use at load.", "Load only new rows each time where the source allows it."], "The estimator's memory figure fits comfortably in your RAM.", 25, "", "Volume estimator")
_g("de-excel-mess", "Replacing the weekly spreadsheet mess", "Data Engineering", "spreadsheet weekly manual excel copy paste automate replace process consolidate", "Weekly copy and paste is slow and error-prone.",
   ["Write down every step done by hand and where each file comes from.", "Put the source files in one folder and set up a Source so they load on a schedule.", "Add a data contract so a bad file is caught on arrival.", "Build the one dashboard the spreadsheet fed, and retire the spreadsheet after one clean month."], "A full cycle runs without anyone opening Excel.", 120, "Keep the old process running for a month in parallel.", "Sources, Data contract")
_g("de-backup", "Back up and restore the data safely", "Data Engineering", "backup restore database copy recover lose data duckdb file", "A backup you have not restored is a hope, not a backup.",
   ["Close the app or use the backup button so the file is not mid-write.", "Copy the database file to a second place (another drive and a cloud folder).", "Once a quarter restore a copy to a test folder and open it.", "Record the date in your records."], "A restored copy opens and shows the latest data.", 20)
_g("de-merge-keys", "Keys do not match across files (spaces, case, leading zeros)", "Data Engineering", "key mismatch merge join id leading zeros spaces case trim no match", "IDs that look the same differ by hidden spaces, capitals or zeros.",
   ["Run Merge preview and see how many rows have no partner.", "Look at examples from each side side by side.", "Clean both sides in a copy (trim spaces, same capitalisation, same padding).", "Re-run the preview: 'matched' should rise."], "The unmatched count falls to what you can explain.", 20, "", "Merge preview")


def get(gid: str) -> dict | None:
    return next((g for g in GUIDES if g["id"] == gid), None)


def _words(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", s.lower()) if len(w) > 2}


def search(q: str, limit: int = 6) -> list[dict]:
    qw = _words(q)
    if not qw:
        return []
    out = []
    for g in GUIDES:
        kw, tw, bw = _words(g["keywords"]), _words(g["title"]), _words(" ".join(g["steps"]) + " " + g["why"])
        s = 3 * len(qw & kw) + 3 * len(qw & tw) + len(qw & bw) + (2 if q.lower().strip() in g["title"].lower() else 0)
        if s:
            out.append((s, g))
    out.sort(key=lambda x: -x[0])
    top = out[0][0] if out else 0
    out = [o for o in out if o[0] * 4 >= top]
    return [{"id": g["id"], "title": g["title"], "area": g["area"], "minutes": g["minutes"], "why": g["why"], "score": s} for s, g in out[:limit]]


def for_ref(ref: str, title: str = "") -> str | None:
    base = ref.split(":")[0]
    if base in REF:
        return REF[base]
    if title:
        r = search(title, 1)
        if r and r[0]["score"] >= 4:
            return r[0]["id"]
    return None


def areas() -> dict:
    out: dict[str, list[dict]] = {}
    for g in GUIDES:
        out.setdefault(g["area"], []).append({"id": g["id"], "title": g["title"], "minutes": g["minutes"]})
    return out


TOOL_DATA_FIX = {"name": "data_fix", "description": "Look up the how-to guide for a data problem (analysis, BI reports, modelling, pipelines). action 'search': query = what the user typed or the finding (e.g. 'totals doubled after join', 'model no better than baseline', 'column renamed') -> best matching guides. "
                 "action 'guide': id -> full guide with steps, how to verify, time and cautions. Walk the user through one step at a time, give the caution before any step that could change data, and do not claim it worked until they have run the verify step.",
                 "input_schema": {"type": "object", "properties": {"action": {"type": "string", "enum": ["search", "guide"]}, "query": {"type": "string"}, "id": {"type": "string"}}, "required": ["action"]}}


def tool_result(args: dict) -> str:
    a = args or {}
    if a.get("action") == "guide":
        g = get(str(a.get("id") or ""))
        if not g:
            return json.dumps({"error": "No guide with that id.", "try": search(str(a.get("query") or a.get("id") or ""), 3)})
        return json.dumps(g)
    return json.dumps({"results": search(str(a.get("query") or ""), 5)})
