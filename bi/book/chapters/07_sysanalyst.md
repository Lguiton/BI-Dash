# Part 7: Systems Analyst

## The role in one page

A systems analyst works out what a system must do, describes how things work today, and then shows that what was built meets the need. You sit between the people who have a problem (the business, the founder, the customer, the nurse on the floor) and the people who build the answer (developers, database people, vendors). Your product is not code. Your product is clarity: written requirements that two people read the same way, models of the process and the data, numbers that size the system, and a trail that links every promise to a check.

You work with stakeholders (who ask for things), developers (who build them), testers (who prove them), and whoever pays. A typical day is a mix of conversations and documents. You interview someone about how a task really gets done. You rewrite a vague request into a testable sentence. You open the data and check whether the thing the stakeholder described actually shows up in it. You update a traceability table so that nothing built is missing a test. You answer a sizing question ("how many people do we need on the desk?" or "can we promise 99.9%?") with a calculation and its assumptions, not a feeling.

Good looks like this. A developer reads your requirement and does not need to ask what it means. A tester can write a check from it without calling you. A stakeholder reads your summary and says "yes, that is what I meant", and you can prove they said it. When something fails late, you can point to the line in the requirements where the disagreement started, and you can show which test would have caught it.

What the role is not: it is not project management (Part 6 covers schedules, risks and sponsors), it is not writing the software (Part 8), and it is not taking dictation. An analyst who writes down whatever is said, in whatever words, produces a document that looks complete and fails in use. You are also not the owner of the decision. You make the options and their costs clear; the stakeholder chooses.

The honest hard parts:

- People rarely know what they need until they see something wrong. Requirements move, and you must manage that without pretending they will not.
- The loudest stakeholder is not always the most important one. Quiet users (the person who actually keys the data in) often hold the facts.
- Precision is tiring. "Fast", "easy", "secure" and "flexible" feel like requirements and are not.
- Models are simplifications. A queueing formula gives a clean number from assumptions that real life only roughly meets. Your job includes saying so.

## How to use this part

There are four levels. Times assume about five hours a week, mixing reading with hands-on practice.

| Level | Focus | Time at ~5 h/week |
|---|---|---|
| 1. Foundations | Requirements, stakeholders, data basics | about 15 hours, 3 weeks |
| 2. Practitioner | Data dictionary, process analysis, traceability | about 20 hours, 4 weeks |
| 3. Advanced | Queueing, availability, capacity | about 25 hours, 5 weeks |
| 4. Expert | Cost-benefit, feasibility, judgement, scale | about 25 hours, 5 weeks |

Read a core idea, then do it yourself before you move on. All you need is a text editor or word processor, a spreadsheet, and any SQL engine (SQLite, DuckDB or Postgres all work). Use invented or public data for every lab; mistakes should be free.

Check every worked number by hand or in a spreadsheet before you trust it. The calculations in Levels 2 to 4 are short enough to redo on paper, and doing so is the fastest way to learn them.

Treat any analysis finding as a lead, not a verdict: a gap list, a bottleneck or a queueing result all rest on the data and assumptions behind them.

## Level 1: Foundations (beginner)

### What you will be able to do

- You can tell a functional requirement, a non-functional requirement and a constraint apart, and give an example of each.
- You can rewrite a vague request as a specific, testable, singular requirement.
- You can assign a MoSCoW priority and say why.
- You can name the status of a requirement from proposed through tested, and say what moves it forward.
- You can explain fact table, dimension table, key and grain in plain words.
- You can keep a requirements register in a spreadsheet with code, priority, status, source, acceptance criterion and test reference.

### Core ideas

#### Three kinds of requirement

A **functional** requirement says what the system does: "The system imports a CSV file as its own table." A **non-functional** requirement says how well it does it: speed, availability, security, usability. A **constraint** is a fixed limit you cannot negotiate with: a budget of 5,000 dollars, a law about patient records, a platform you must run on.

The reason to separate them is that they fail differently and are tested differently. A functional requirement is usually pass or fail on one action. A non-functional one needs a number and conditions ("95% of searches return in under 2 seconds with 100,000 rows"). A constraint is not tested so much as respected, and it narrows what the other two can be.

Worked example for a file-import tool: "A failed import never leaves half-loaded data" is non-functional (it is about reliability, not a feature). "Test data and live data are stored separately" is a constraint (it is a rule the design must follow). "Saved sources refresh on a schedule" is functional. If you cannot decide which kind something is, it often means the sentence mixes two ideas, which leads to the next point.

#### Specific, testable, singular

A good requirement has three properties. **Specific**: one reading only. **Testable**: someone could run a check and get yes or no. **Singular**: it says one thing, so a test can fail for one reason.

Compare "The page is fast and works on phones." It is two requirements joined by "and", and neither is testable. Split and sharpen: "The report page loads in under 2 seconds with 100,000 rows on the standard laptop." and "Every table on the report page is readable without horizontal page scrolling at 390 pixels wide." Now each has a number and a condition, and a tester can say which one failed.

Watch for weasel words: fast, easy, user-friendly, robust, flexible, secure, as appropriate, etc. Each one hides a number you have not yet asked for. The question that fixes most of them is "How would we know?"

#### Where requirements come from: stakeholders and elicitation

A **stakeholder** is anyone affected by the system or able to affect it. You find requirements by **elicitation**: interviews, watching people work, reading existing documents, and looking at existing data. 

Practical rule: ask for the last time something happened, not what usually happens. "Tell me about the last admission that went wrong" gives you facts. "What are the problems?" gives you opinions. Record the **source** of every requirement (who asked) in the panel's Source field. When two requirements conflict, you will need to know who to go back to.

#### MoSCoW priority

MoSCoW sorts requirements into **must**, **should**, **could** and **won't (this time)**. A must is something without which the release is useless or illegal. A should is important but has a workaround. A could is a pleasant extra. A won't is explicitly out of scope for now, and writing it down protects you from scope creep because you can show it was discussed.

The trap is that everything becomes a must. A test: if you removed it, would you still ship? If yes, it is not a must. A must-have that is still only proposed is a traceability gap worth chasing first.

#### Status: proposed to tested

Each requirement moves through **proposed** (someone asked), **approved** (stakeholders agreed it and it has an acceptance criterion), **built**, **tested**, or **rejected**. Status is a claim, and the matrix checks some claims. "Tested" with no test linked is a claim with no evidence.

An **acceptance criterion** is the check that proves the requirement is met: "A file with columns tier and mrr loads as its own table with detected types." Write it before building. If you cannot write one, the requirement is not yet clear enough to build.

#### Data basics: facts, dimensions, keys, grain

A **fact table** records events and holds mostly numbers. A **dimension table** holds descriptive context: who, where, which category. For example, `fact_visits` holds one row per visit record, and `dim_facilities` holds one row per facility. A **key** identifies a row; a **foreign key** points from one table to another's key, so `fact_visits.facility_id` points at `dim_facilities.facility_id`.

**Grain** is what one row of a fact table means. Here it is one operational record. Always state the grain before you count anything: "How many entities?" and "How many records?" are different questions and give different numbers. A **star schema** is one fact table surrounded by dimensions; it is the usual shape for reporting.

### Practice on your own

1. In a spreadsheet, create a register with columns: code, requirement, kind, priority (MoSCoW), status, source, acceptance criterion, test reference. Enter ten requirements for a system you know, such as a household budget sheet or a clinic sign-in.
2. Add a column that flags gaps by formula: built or tested with no test reference, and a must still proposed. Deliberately create one of each gap and confirm they light up.
3. Compute coverage: built-or-tested items with a test reference, divided by all built-or-tested items.
4. Sketch two tables for a domain you know, one fact and one dimension. Write the grain of each in one sentence.
5. Interview a friend about the last time a simple task went wrong. Write down three requirements from what they said, with a source and an acceptance criterion each.

### Exercises

1. Classify as functional, non-functional or constraint: (a) "Only staff may see patient names." (b) "The export includes every column." (c) "Total budget is 8,000 dollars." (d) "The nightly refresh finishes in under 30 minutes."
2. Why is "The system should be user-friendly" not a requirement? Rewrite it so it is.
3. Split into singular requirements: "Users can upload a file and see a chart, and it should send an email."
4. A stakeholder insists all 12 items are musts. What two questions do you ask to find the real musts?
5. For a table of daily bus trips with columns trip_id, route_id, date, minutes_late, state the grain, and say which columns are probably foreign keys.
6. Write one acceptance criterion for "A refresh that would delete most of a table is refused."
7. A requirement is marked tested but has no linked test. List two possible explanations and what you would do for each.
8. You count 40 rows in a fact table and 5 in a dimension. A manager asks "how many stores do we have?" What do you check before answering?

### Answers and hints

1. (a) Non-functional (security) or a constraint if it is a legal rule; say which. (b) Functional. (c) Constraint. (d) Non-functional (performance).
2. "User-friendly" has no check. A rewrite: "A new user completes an import, from opening the page to seeing the table, in under 3 minutes without help, in 4 of 5 observed trials."
3. Three: file upload; chart shown after upload; email sent (and the email needs a trigger and recipient, so ask more).
4. "If we shipped without it, would the release be useless or illegal?" and "What is the workaround today?" Items with a workable workaround are shoulds.
5. Grain: one bus trip. route_id is probably a foreign key to a routes table. trip_id is the primary key. date may link to a date dimension.
7. Either the test exists but nobody recorded the link (fix the reference), or nobody tested it and the status is wrong (reset it to built and write the test).
8. Count distinct entity keys in the dimension, not fact rows, and check for duplicates or retired stores in the dimension.

### Checkpoint

Answer aloud before moving on:

1. What are the three properties of a good requirement?
2. Name the three kinds of requirement and give an example of each.
3. What does MoSCoW stand for, and what is a "won't"?
4. What is an acceptance criterion and when do you write it?
5. What is the difference between a fact table and a dimension table?
6. What is grain, and why state it first?
7. Why record who asked for each requirement?
8. What does "tested" claim, and what is it missing if no test is linked?

Common mistakes:

- Writing a feature description and calling it a requirement, with no way to check it.
- Joining two ideas with "and" so a test can fail for two reasons.
- Making everything a must, so priority carries no information.
- Writing the acceptance criterion after the thing is built, so it describes what exists rather than what was needed.
- Skipping the source, then having no one to ask when requirements conflict.
- Counting rows without stating the grain.

## Level 2: Practitioner (intermediate)

### What you will be able to do

- You can read a data dictionary and spot a column that is mostly empty, or a key that is not unique.
- You can check a relationship for orphans with SQL and explain what an orphan means.
- You can compute average, median, percentile and coefficient of variation for a process, and say what each tells you.
- You can use Little's law to estimate work in progress.
- You can build a traceability table and find its gaps by hand.
- You can write acceptance criteria in a given-when-then shape.

### Core ideas

#### Reading a data dictionary

A data dictionary lists, for every table and column: the type, whether it may be empty, whether it is a key, how many values are missing, how many distinct values there are, and what it means. The first four can be read from the database's own schema; the meanings must be written by people. Where there is no description, that is itself a finding: someone must say what the column means.

Read two numbers first. **Null percent** tells you how much of a column is missing; 60% empty means any analysis built on it covers 40% of the records. **Distinct count** tells you how column behaves: a column with as many distinct values as rows is an identifier; one with three distinct values is a category. A "date" column with 5 distinct values over 10,000 rows is suspicious.

Worked example: `fact_visits.status` has 10,000 rows and 4 distinct values, with 0% null. That is a clean category, good for grouping. `duration_minutes` is 18% null. Any process analysis uses only the 82% that has a duration, and you must say so in the report.

#### Keys, cardinality and orphans

The relationship `fact_visits.facility_id` to `dim_facilities.facility_id` is **many to one**: many facts belong to one entity. In Mermaid text that is written `dim_facilities ||--o{ fact_visits`, which reads "one entity, zero or more operations". An **orphan** is a child row whose parent does not exist, a referential-integrity failure. Orphans silently drop out of inner joins, so reports lose records without any error.

The check is one query:

```sql
SELECT COUNT(*) AS orphans
FROM fact_visits f
WHERE f.facility_id IS NOT NULL
  AND NOT EXISTS (SELECT 1 FROM dim_facilities p WHERE p.facility_id = f.facility_id);
```

Rows with a null facility_id are excluded on purpose: a missing key is a different problem (completeness) from a key pointing nowhere (integrity). Run it for every foreign key you document.

#### Process analysis from data

Instead of asking people how long a task takes, measure it. For records with a duration, report the **average**, the **median** (the middle value), and **percentiles**: the 85th percentile (p85) is the time that 85% of cases beat. Averages hide pain; a few very slow cases pull the mean up and a manager sees "10 minutes" while one case in seven takes 30.

Take seven durations in minutes: 4, 5, 5, 6, 8, 12, 30. The mean is 70 ÷ 7 = 10. The median is 6. The deviations from 10 are -6, -5, -5, -4, -2, 2, 20; their squares sum to 510; divided by 6 (sample variance) gives 85, so the standard deviation is about 9.22. The p85 by linear interpolation sits at position 0.85 × 6 = 5.1 in the sorted list: 12 + 0.1 × (30 − 12) = 13.8 minutes.

#### Variability and the bottleneck

The **coefficient of variation** (CV) is standard deviation divided by mean. Here 9.22 ÷ 10 = 0.92. A common rule of thumb reads CV above 1 as hard to predict, 0.5 to 1 as moderate, and below 0.5 as steady, so this process is moderate. A process with the same average but a lower CV is easier to staff and to promise.

The **bottleneck** can be taken as the step or unit with the slowest p85, on the idea that a process is only as fast as its slowest common case. It is a lead, not a verdict: a slow entity may simply handle harder work, so look at the units processed and the mix before blaming anyone.

#### Little's law

Little's law says that average work in progress equals the arrival rate times the average time in the system: L = λ × W. If 120 records arrive per day and each takes 10 minutes, work in progress is 120 × 10 ÷ 1,440 minutes per day = 0.83 records in flight on average. That is exactly what the Process analysis tab shows as "Avg in progress". The law needs no assumptions about the shape of arrivals; it holds for any stable system. Use it as a sanity check: if you count 50 cases open and arrivals are 10 a day, average time in system must be about 5 days.

#### Traceability by hand

A traceability matrix links each requirement to a test. Useful checks flag: built with no linked test; marked tested with no link; approved, built or tested with no acceptance criterion; and a must-have still only proposed. Coverage is the share of built or tested requirements that name a test.

Example with four requirements: A (built, test linked), B (built, no test), C (tested, test linked), D (proposed, must). Built or tested: A, B, C. With a test: A and C. Coverage is 2 ÷ 3 = 66.7%. Gaps: B (built but no test) and D (a must still proposed). Rejected requirements are ignored.

#### Given-when-then acceptance criteria

A given-when-then criterion states the starting condition, the action and the observable result: "Given a table with 100 rows, when a refresh returns 40 rows, then the refresh is rejected and the table still has 100 rows." The shape forces you to name the data and the outcome, and it translates directly into an automated test.

### Practice on your own

1. In any SQL engine, create `dim_facilities(facility_id, name)` with three rows and `fact_visits(visit_id, facility_id, minutes, status)` with about twenty rows. Include two rows with a facility_id that is missing from the dimension and one with a null.
2. Run the orphan query from this level and confirm it finds exactly the two rows you planted, not the null one.
3. Profile `fact_visits`: count rows, null percent and distinct count per column, using `COUNT(*)`, `COUNT(col)` and `COUNT(DISTINCT col)`.
4. Compute mean, median, p85 and CV of minutes with SQL (or a spreadsheet). Check that the seven-value example in this level gives 10, 6, 13.8 and 0.92.
5. Group by facility and find the slowest p85. Then look at the status mix and units for that facility before calling it the bottleneck.
6. Write the Mermaid text for your two tables and paste it into any Mermaid viewer to check the arrow reads one facility, many visits.

### Exercises

1. A column has 2,000 rows, 1,500 non-null values, and 1,498 distinct values. What does that suggest?
2. Write the SQL to count rows in a table `orders` whose `customer_id` is missing from `customers`.
3. Durations 3, 4, 4, 5, 9 minutes: compute mean, median and sample standard deviation.
4. For the same data, is the CV low, moderate or high by the rule of thumb above?
5. 30 jobs arrive per hour and each spends 12 minutes in the system. How many are in progress on average?
6. Five requirements: two tested with tests linked, one built with no test, one approved with no acceptance criterion, one rejected. Give coverage and the gap list.
7. Rewrite "Reports should refresh promptly" as a given-when-then criterion.
8. The by-entity table says entity "Zone B" has the highest p85, but also processes the most units per hour. Argue both for and against calling it the bottleneck.

### Answers and hints

1. 25% are missing, and the column is nearly unique among the values present, so it looks like an identifier with gaps. If it is meant to be a key, 500 rows have none.
2. `SELECT COUNT(*) FROM orders o WHERE o.customer_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM customers c WHERE c.customer_id = o.customer_id);`
3. Mean 25 ÷ 5 = 5. Median 4. Deviations -2, -1, -1, 0, 4; squares 4, 1, 1, 0, 16 = 22; divided by 4 = 5.5; sd about 2.35.
4. CV = 2.35 ÷ 5 = 0.47, below 0.5: low (steady).
5. L = 30 per hour × 12 minutes = 30 × 0.2 hours = 6 jobs.
6. Built or tested: the two tested and the built one, so 2 of 3 = 66.7%. Gaps: the built one with no test, and the approved one with no acceptance criterion. The rejected one is ignored.
8. For: its slow common case sets the pace of anything waiting on it. Against: high throughput suggests it handles bigger or harder jobs, so the slow time may be appropriate; check job mix before acting.

### Checkpoint

1. What do null percent and distinct count each tell you?
2. What is an orphan and why do reports lose rows silently when there are some?
3. Why is p85 more informative than the average for a staffing promise?
4. What does a CV of 1.4 mean in plain words?
5. State Little's law and give its units.
6. How is test coverage computed in this chapter's definition?
7. What are the parts of a given-when-then criterion?
8. Why is the bottleneck a lead and not a verdict?

Common mistakes:

- Ignoring null percent and then reporting results as if they covered every record.
- Treating a null foreign key as an orphan, or the reverse.
- Quoting averages when a handful of slow cases drive the pain.
- Mixing units in Little's law (minutes with days).
- Reading coverage as "percent of all requirements tested" when it counts only built or tested ones.
- Blaming the slowest entity without checking the mix of work it receives.

## Level 3: Advanced

### What you will be able to do

- You can compute M/M/1 queue measures by hand and explain why waiting explodes near full utilisation.
- You can size a team with the Erlang C formula and read the probability of a long wait.
- You can convert an availability target into allowed downtime and an error budget.
- You can combine components in serial and in parallel and check the result against a target.
- You can project when growth will exhaust capacity and choose a headroom threshold.
- You can state the assumptions behind each model and when they break.

### Core ideas

#### One server: M/M/1

M/M/1 describes one server, random arrivals at rate λ and random service times with average rate μ, both in the same time unit. Utilisation is ρ = λ ÷ μ, and it must be below 1. The measures are: average number in the system L = ρ ÷ (1 − ρ); in the queue Lq = ρ² ÷ (1 − ρ); time in the system W = 1 ÷ (μ − λ); wait in the queue Wq = ρ ÷ (μ − λ).

Worked example: λ = 8 per hour, μ = 10 per hour. ρ = 0.8, L = 4, Lq = 3.2, W = 0.5 hours (30 minutes), Wq = 0.4 hours (24 minutes). Note that Wq is not small even at 80% busy.

#### Why waiting explodes

Keep μ = 10 and raise λ. At λ = 9, ρ = 0.9 and Wq = 0.9 ÷ 1 = 0.9 hours, 54 minutes. At λ = 9.5, ρ = 0.95 and Wq = 0.95 ÷ 0.5 = 1.9 hours. A 5% rise in demand more than doubled the wait. The denominator (μ − λ) shrinks toward zero, so the wait grows without bound as ρ approaches 1. At or above 1 the queue never clears. This is why a service feels fine and then suddenly does not, and why you add capacity before you "need" it. The dashboard's rule of thumb is to watch anything above about 80% utilisation.

#### Several servers: Erlang C

For c servers, the offered load is a = λ ÷ μ, and utilisation is ρ = a ÷ c. The **Erlang C** probability that an arrival has to wait is

C = [aᶜ ÷ c! ÷ (1 − ρ)] ÷ [Σ(k=0 to c−1) aᵏ ÷ k! + aᶜ ÷ c! ÷ (1 − ρ)]

and the average wait is Wq = C ÷ (cμ − λ). The chance of waiting longer than t is C × e^(−(cμ − λ)t).

Worked example, a service desk: 12 tickets an hour, each takes 10 minutes, so μ = 6 per hour and a = 2. With c = 2, ρ = 1: unstable. With c = 3: ρ = 0.667. The sum is 1 + 2 + 2 = 5; the last term is (8 ÷ 6) ÷ 0.3333 = 4; C = 4 ÷ 9 = 0.444. Wq = 0.444 ÷ (18 − 12) = 0.074 hours, about 4.4 minutes. That meets a five-minute average. But P(wait > 5 minutes) = 0.444 × e^(−6 × 0.0833) = 0.444 × 0.607 = 0.27, so 27% of callers wait more than five minutes. With c = 4, C = 0.174, Wq is about 0.9 minutes, and the 5-minute tail falls to 0.174 × e⁻¹ = 6.4%.

The lesson is to size to a tail, not an average, whenever people are waiting.

#### Availability and error budgets

An availability target (SLO, service level objective) of 99.9% allows 0.1% downtime. Over 30 days (43,200 minutes) the **error budget** is 43.2 minutes. Over a year (525,600 minutes) it is 525.6 minutes, about 8.8 hours. If you have already used 30 minutes this month, you have burned 30 ÷ 43.2 = 69% and have 13.2 minutes left. The practice that goes with a budget is simple: when it is spent, you freeze risky changes.

**Serial** components (all must work) multiply: a web tier at 99.9% and a database at 99.5% give 0.999 × 0.995 = 0.994005, so 99.4%. A chain is weaker than its weakest link. **Parallel** components (any one is enough) combine as 1 − ∏(1 − a): two independent 99% servers give 1 − 0.01 × 0.01 = 99.99%. Redundancy helps only if failures are independent; two servers on the same power strip are not.

#### Capacity planning

With compound monthly growth g, the load after m months is load × (1 + g)ᵐ. The months until it reaches capacity are m = ln(capacity ÷ load) ÷ ln(1 + g). Worked example: load 50, capacity 100, growth 10% a month: ln 2 ÷ ln 1.1 = 0.6931 ÷ 0.0953 = 7.3 months. But planning to 100% is wrong, since delay is steep near full (see M/M/1). Using an 80% headroom threshold: ln(80 ÷ 50) ÷ ln 1.1 = 0.470 ÷ 0.0953 = 4.9 months. Order capacity by month 4, not month 7, and allow for lead time.

#### What the models assume

M/M/c assumes arrivals are random and independent, service times follow an exponential distribution, one queue feeds all servers, and nobody gives up. Real queues have rush hours, tickets that take five minutes or three hours, and abandoned calls, so the result is a good first estimate and a poor guarantee. A CV well above 1 in the Process analysis tab means the model understates waiting.

### Practice on your own

1. In a spreadsheet, build an M/M/1 table for mu = 10 and lambda from 5 to 9.5. Compute rho and Wq = rho / (mu - lambda). Chart Wq against rho and note where the curve turns upward.
2. Write the Erlang C formula in a spreadsheet or a short script. Reproduce the service-desk example: 12 per hour, mu = 6, servers 3 gives C = 0.444 and a wait of about 4.4 minutes.
3. Add the tail: probability of waiting more than 5 minutes for 3 and 4 servers (27% and 6.4%).
4. Build an availability sheet: error budget minutes for 99%, 99.9%, 99.99% over 30 days; then serial and parallel combinations of three parts you invent.
5. Build a capacity projection with load, capacity, monthly growth and an 80% threshold; compute months to threshold with the logarithm formula and with a month-by-month column, and confirm they agree.

### Exercises

1. M/M/1 with λ = 3 per hour and μ = 4 per hour: find ρ, L and Wq in minutes.
2. Can one server with λ = 10 and μ = 10 be stable? Why or why not?
3. With μ = 6 per hour and λ = 12, is two servers enough?
4. Allowed downtime per 30 days at 99.95%.
5. Serial availability of web 99.9%, database 99.9%, DNS 99.99%.
6. Two redundant 99.5% servers in parallel: composite availability.
7. Load 40, capacity 100, growth 8% a month, headroom 80%: months to full and to threshold.
8. A team has a 99.9% SLO over 30 days and has had 30 minutes of downtime. What do you tell the release manager?

### Answers and hints

1. ρ = 0.75, L = 0.75 ÷ 0.25 = 3, Wq = 0.75 ÷ (4 − 3) = 0.75 hours = 45 minutes.
2. No. ρ = 1, the queue grows without limit, because there is never spare capacity to clear a backlog.
3. No. a = 2 and c = 2 gives ρ = 1. You need at least three.
4. 43,200 × 0.0005 = 21.6 minutes.
5. 0.999 × 0.999 × 0.9999 = 0.99790, so about 99.79%.
6. 1 − 0.005² = 1 − 0.000025 = 99.9975%, if the failures are independent.
7. Full: ln 2.5 ÷ ln 1.08 = 0.9163 ÷ 0.0770 = 11.9 months. Threshold: ln 2 ÷ 0.0770 = 9.0 months.
8. Budget is 43.2 minutes, 69% is burned with 13.2 left. One more incident could exhaust it; recommend freezing risky changes or shipping only small, reversible ones.

### Checkpoint

1. What must be true of ρ for a queue to be stable?
2. Why does a small rise in demand near 95% utilisation hurt so much?
3. What does the Erlang C value C represent?
4. Why size to P(wait > target) and not only the average wait?
5. What is an error budget and what do you do when it is spent?
6. When do serial parts multiply and when do parallel parts combine?
7. Why plan capacity at 80% and not 100%?
8. Name two assumptions of M/M/c that real services break.

Common mistakes:

- Mixing time units, such as arrivals per hour with service minutes.
- Treating utilisation of 90% as healthy because it is "not full".
- Quoting only the average wait while 27% of people wait over the limit.
- Assuming redundancy without checking that failures are independent.
- Reporting a model's output as a promise rather than an estimate with stated assumptions.
- Forgetting lead time when choosing the month to add capacity.

## Level 4: Expert and professional judgement

### What you will be able to do

- You can compute NPV, IRR, ROI, payback and benefit-cost ratio, and say which one to trust for which decision.
- You can run a TELOS feasibility assessment and explain why one weak dimension matters more than the average.
- You can review another analyst's requirements and find the defects that matter.
- You can name the failure modes of requirements work and how you would catch each.
- You can state your assumptions honestly, including when a number is a guess.

### Core ideas

#### Cost-benefit and the time value of money

Money later is worth less than money now. **NPV** (net present value) discounts each year's cash flow: NPV = Σ CFₜ ÷ (1 + r)ᵗ, with the upfront cost at t = 0. Take 1,000 upfront, 500 benefit and 100 cost a year (net 400), 3 years, 10% rate. The annuity factor is 1 ÷ 1.1 + 1 ÷ 1.21 + 1 ÷ 1.331 = 2.4869, so NPV = 400 × 2.4869 − 1,000 = −5.26. The simple ROI looks fine, (1,200 − 1,000) ÷ 1,000 = 20%, and simple payback is 2.5 years, yet NPV is slightly negative. The **IRR**, the rate where NPV is zero, is about 9.7%, below the 10% hurdle, and the benefit-cost ratio is 1,243.4 ÷ 1,248.7 = 0.996. All four agree it is marginal, which is the honest finding: this project neither clearly pays nor clearly fails, so the benefit estimate decides it.

Raise the benefit to 600: net 500, NPV = +243.4, simple payback 2 years, discounted payback about 2.35 years. Prefer NPV for go/no-go, IRR for comparing against a hurdle, payback only as a liquidity check.

#### Feasibility with TELOS

TELOS scores five dimensions from 1 (serious problem) to 5 (no concerns): Technical, Economic, Legal, Operational, Schedule. You weight them and take a weighted mean. With scores 4, 3, 5, 2, 4 and equal weights, the mean is 3.6, and the verdict is "Feasible with changes", because a sensible rule reserves plain "Feasible" for a mean of 3.8 or more with no score below 3 (the thresholds are a convention; set yours and say so). The weakest area here is Operational at 2.

That is the point: an average hides the dimension that kills projects. A technically brilliant system nobody will run scores 2 on operational and fails regardless. The rule is that any single score under 3 needs a written plan, and the evidence column should say why you scored it so. Weights are opinion; show them to the stakeholder and let them argue with the weights, not just the scores.

#### Reviewing others' requirements

When you review a requirements set, look for defects in this order. Ambiguity (two readings). Untestable wording. Compound requirements ("and"). Missing non-functional requirements, which are the usual omission: nobody wrote down volume, availability, retention or who may see what. Conflicts between requirements. Solutions disguised as requirements ("use a dropdown") that remove design choices without reason. Orphan requirements with no source.

Then check the trail: does each built item have a test, does each test link to something someone wanted? Treat the gap list as a checklist for your review, and the status of an item as a claim to verify, not as evidence.

#### Failure modes, honesty and scale

The common failures: requirements never agreed (silence taken as consent), scope creep without a record, models trusted past their assumptions, estimates presented as facts, and documents nobody reads. Fix them with sign-off that names a person and a date, change control that records who asked and the cost, assumptions listed beside every calculation, ranges instead of single numbers, and short documents tied to tests.

Ethics for an analyst: do not write a requirement to justify a decision already made; do not hide a weak TELOS score; do not present a queueing result as a guarantee; and say what the data cannot show. At organisation scale the work shifts to governance: shared definitions, a requirements register with owners, and an agreed rule for who may change what.

### Practice on your own

1. Take a small change you could make (buy a tool, automate a chore). Estimate upfront cost, yearly benefit and yearly running cost, and compute NPV, IRR (by trial and error or the spreadsheet function), simple and discounted payback at 10%.
2. Repeat with benefits cut by 30% and with the discount rate at 5% and 15%. Write which conclusion is robust and which is not.
3. Score the same idea on TELOS with weights, write one line of evidence per score, and give the verdict. Change the weakest score by one point and note the effect.
4. Swap requirements sets with someone, or revisit your Level 1 set after a week, and review it against the defect list. Write five comments, marking each blocking or optional.
5. List every assumption you made in steps 1 to 3, with a guess at which one matters most.

### Exercises

1. NPV for 2,000 upfront, benefit 1,200, cost 200 a year, 3 years at 10%.
2. In that case, is simple payback shorter or longer than discounted payback?
3. TELOS scores 5, 5, 5, 1, 5 with equal weights. Mean and verdict?
4. Why might you give Legal a weight of 0 in one project and 5 in another?
5. Review: "The system shall provide a user-friendly dashboard using dropdown menus and shall be secure." List four defects.
6. A stakeholder asks you to raise the benefit estimate so the project passes. What do you do?
7. Your queueing model predicts a 2-minute wait but customers report 15 minutes. Give three possible causes.
8. Propose a rule for who may change a requirement after approval, and what must be recorded.

### Answers and hints

1. Net 1,000, factor 2.4869, NPV = 2,486.9 − 2,000 = +486.9.
2. Simple payback 2.0 years; discounted is longer, about 2.35 years, because later cash is discounted.
3. Mean 4.2, so the score rule gives "Feasible with changes": one score below 3 blocks "Feasible". The Operational score of 1 needs a plan.
4. Weights express how much a dimension matters to this decision. A system with no personal data may carry little legal risk; a patient-data system carries a lot. Zero should be justified, not convenient.
5. Compound (dashboard plus security); "user-friendly" untestable; "secure" untestable; dropdown is a design choice presented as a requirement.
6. Decline to change it without evidence. Show a sensitivity range, say which assumption drives the result, and record that the request was made.
7. Arrivals not random (rush hour), service times far more variable than exponential, callers abandon or retry, a shared dependency adds delay the model leaves out.

### Checkpoint

1. Why can NPV be negative while simple ROI is positive?
2. Which measure would you use to compare a project to a 10% hurdle rate?
3. Why can a good average TELOS score still be a bad sign?
4. List four defects you look for when reviewing requirements.
5. What is a solution disguised as a requirement?
6. What should sit beside every calculation you present?
7. How do you handle a stakeholder who wants a number to come out differently?
8. What changes in your work at organisation scale?

Common mistakes:

- Trusting ROI or payback alone and ignoring discounting.
- Averaging feasibility scores and ignoring the lowest one.
- Presenting a single number where a range is honest.
- Reviewing only for wording and not checking the test trail.
- Letting the model's convenience, not the real system, decide the assumptions.
- Treating a personal spreadsheet as a substitute for team requirements tooling.

## Capstone projects

### Capstone 1: Ten testable requirements (small, about 6 hours)

**Brief.** Pick a small system you know (a household budget sheet, a delivery route log, a clinic sign-in). Write ten requirements, mixing the three kinds, and link each to a test or an acceptance check.

**Deliverables.** The ten requirements in a register with source, priority and acceptance criterion; a one-paragraph note on which are musts and why.

**Rubric (score each 0 to 2).** Every requirement is singular. Every requirement is testable with a number or an observable result. At least two are non-functional and one is a constraint. Priorities are not all musts. The gap list shows no unexplained gaps. Total of 10 or more means you are ready to move on.

### Capstone 2: The as-is process and the sizing memo (medium, about 15 hours)

**Brief.** Using a dataset you have (or invent 200 timed records), describe where time goes and size a team for a service you define.

**Deliverables.** A two-page memo with: the dictionary entries and null rates you relied on; median, p85, p95 and CV; the slowest entity and a caution about it; an arrival rate and service time; the smallest number of servers that keeps the average wait under a target and the chance of exceeding it; the assumptions behind the model.

**Rubric (0 to 2 each).** Numbers are traceable to the data. Units are consistent. The tail probability is reported, not only the mean. Assumptions are listed and at least one is challenged. The bottleneck is stated as a lead with a way to check it. Total of 9 or more is solid.

### Capstone 3: A feasibility and business case pack (large, about 30 hours)

**Brief.** Write the case for a real change (for example moving a paper tracking job into a small database). Include requirements, a data model, a feasibility assessment, cost-benefit, availability target and a review of your own work.

**Deliverables.** Requirements set with traceability; a Mermaid data model; TELOS scores with evidence and a plan for any score under 3; NPV, IRR, payback at two discount rates and with benefits cut by 30%; an availability target with error budget; a one-page risk and assumptions list; a short review of your pack as if someone else wrote it.

**Rubric (0 to 2 each).** Requirements are reviewed against the Level 4 defect list. TELOS evidence is concrete. Cost-benefit shows sensitivity, not one number. The review finds real weaknesses in your own pack. Claims stay inside what the data supports. A total of 9 or more means you can present it to a sponsor.

## Tools reference

| Tool | What it is for | When you outgrow it |
|---|---|---|
| Spreadsheet register | Requirements, traceability and calculators in one file | When several people edit requirements, or you need versions and approvals |
| Any SQL engine | Checking requirements against real data, orphan queries | Large or shared databases that need access control and review |
| Mermaid | Text-based diagrams (ER, flow, sequence) stored with the docs | Complex diagrams with many authors; use a drawing tool |
| Draw.io or Lucidchart | Process and architecture diagrams | Rarely; the limit is discipline, not the tool |
| Spreadsheet | Rebuilding cost-benefit and queueing formulas to check them | When the model needs simulation or many scenarios |
| Jira, Azure DevOps, TestRail | Team requirements, tickets and test management | Regulated work that needs formal traceability tooling |

## Glossary

- **Acceptance criterion**: the check that proves a requirement is met.
- **Availability**: the share of time a service is working, as a percentage.
- **Bottleneck**: the step that limits overall throughput.
- **Coefficient of variation (CV)**: standard deviation divided by mean; higher means less predictable.
- **Constraint**: a fixed limit such as a budget, law or platform.
- **Data dictionary**: a list of tables and columns with type, meaning and quality facts.
- **Dimension table**: descriptive context for facts (who, where, which category).
- **Erlang C**: formula for the chance of waiting and the average wait with several servers.
- **Error budget**: the downtime an SLO allows in a window.
- **Fact table**: one row per event, mostly numbers.
- **Functional requirement**: what the system does.
- **Grain**: what one row of a table means.
- **IRR**: the discount rate at which NPV is zero.
- **Little's law**: work in progress equals arrival rate times time in system.
- **M/M/1**: queue with random arrivals, random service times and one server.
- **MoSCoW**: must, should, could, won't prioritisation.
- **Non-functional requirement**: how well the system does it (speed, security).
- **NPV**: sum of discounted cash flows minus the upfront cost.
- **Orphan**: a child row whose parent key does not exist.
- **Percentile (p85)**: the value that 85% of cases are at or below.
- **SLO**: a target for service level, such as 99.9% availability.
- **TELOS**: Technical, Economic, Legal, Operational, Schedule feasibility.
- **Traceability matrix**: links from requirements to tests.
- **Utilisation (ρ)**: arrival rate divided by total service capacity.

## Career notes

**Roles this leads to.** Systems analyst, business analyst, requirements engineer, business systems analyst, data analyst with a systems focus, and, with more technical depth, solutions or technical analyst. 

**How to show your skill.** A portfolio beats a claim. Show a requirements set with acceptance criteria and a traceability table, a data dictionary with findings, a sizing memo with its assumptions, and a feasibility pack. Say what you got wrong and how you found out. Domain knowledge in a field you have worked in is a real advantage: an analyst who understands the work needs less explaining.

**What to learn next.** SQL to a confident level (Part 1), process modelling notation such as BPMN, user stories and acceptance testing, basic statistics (Part 2), and working with developers (Part 8). Certifications in business analysis exist; check the current exam objectives and prerequisites before deciding whether one is worth the cost for you.


## Match it in the app

This book is general, but the project's dashboard has a Systems Analyst track you can use as a second set of hands. Open Tracks, then Systems Analyst, and work in the Practice workspace. Do not experiment in the Real workspace. The companion reading is `docs/SYSTEMS_ANALYSIS.md`. Treat everything the app shows as a lead, not a verdict.

**Level 1 (requirements and data basics).** Open the Requirements tab and click "Load example requirements" (Practice only). You get ten rows, a coverage figure and a gap list. Read the three stat tiles, then add a requirement with the form and change its status in the register to see gaps appear. Open the Schema page to find the project's fact and dimension tables and write their grain. Expect: coverage counts only built or tested items that name a test.

**Level 2 (dictionary, process, traceability).** The Data dictionary tab lists every table and column with type, key, null percent, distinct count and the descriptions the project knows, plus a Relationships table with orphan counts and a copyable Mermaid ER diagram. Confirm its orphan count by running the Level 2 SQL in SQL Lab. The Process analysis tab reports median, p85, p95, CV (labelled high above 1, moderate above 0.5), the slowest entity as the bottleneck, and Little's law work in progress. It needs records with a duration; otherwise it says so.

**Level 3 (calculators).** The Calculators tab has four forms: queueing (one server uses M/M/1, more use Erlang C, with a target wait and the number of servers needed), availability and error budget with serial or parallel parts, cost-benefit, and capacity. Defaults of 5 arrivals and service rate 6 give utilisation 0.833; setting two servers drops the wait sharply. Reproduce your Level 3 spreadsheet numbers here; `backend/tests/test_sysanalyst.py` holds hand-checked cases to compare against.

**Level 4 (judgement).** Cost-benefit shows NPV, ROI, IRR, payback, discounted payback and a benefit-cost ratio, with a cash-flow chart. The Feasibility (TELOS) tab takes a score, weight and evidence note for each of five dimensions, shows the weighted mean, names the weakest area, and reserves "Feasible" for a mean of 3.8 or more with no score below 3.

**What the app does not cover.** It does not do interviews, workshops or stakeholder management, which are most of the job. It has one requirements list per workspace, with no versions, approvals, comments or links to real test results (the test reference is just text). Its process analysis uses one operations table, not your own processes, and it draws no flow diagrams (BPMN or swimlanes). The queueing model is M/M/c only, with no simulation. Capstones 1 to 3 are best done outside the app, then compared against it.
