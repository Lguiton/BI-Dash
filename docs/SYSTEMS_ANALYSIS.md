# Systems analysis: the technical vocabulary

The **Systems Analyst** dashboard (Tracks → Systems Analyst) covers the analyst's core deliverables. Parts are generated from the live database, parts are things you maintain (requirements, feasibility), and the calculators answer the sizing questions an analyst gets asked.

## Requirements and traceability
* **Functional**: what the system does. **Non-functional**: how well (speed, availability, security). **Constraint**: a fixed limit (budget, a law, a platform).
* A good requirement is **specific, testable and singular**. "The page loads in under 2 seconds on 100,000 rows" is testable; "the page is fast" is not.
* Each has a priority (MoSCoW), a status (proposed → approved → built → tested; or rejected), a source (who asked), an **acceptance criterion** (the check that proves it) and a **linked test**.
* The **traceability matrix** connects requirement → test. The dashboard flags gaps: built with no test, tested with no link, approved with no acceptance criterion, a must-have still only proposed. A requirement you can't test is a requirement you can't show you met.

## Data dictionary and ER diagram
Generated from the live schema (tables, views, columns, types, keys, nullability, % empty, distinct count) with the descriptions we know. **Relationships** are checked for orphans: a foreign key that points at nothing means broken data. The **Mermaid** text can be pasted into any Mermaid renderer (GitHub, Notion, mermaid.live) for a diagram.
* **Fact table**: events, mostly numbers (records). **Dimension**: descriptive context (entities, dates). A **star schema** is one fact surrounded by dimensions. **Grain** is what one fact row means: here, one operational record.

## Process analysis (from your data)
From records with a duration: average, median, 85th and 95th percentile time; the **coefficient of variation** (standard deviation ÷ mean: above 1 means unpredictable); units per hour and cost per unit by entity; the **bottleneck** (the slowest common case, p85). Little's law links arrivals × time to work in progress.

## Calculators
| Question | Method | Notes |
|---|---|---|
| How long will people wait? | **M/M/1** (one server) and **M/M/c Erlang C** (several) | Needs arrival rate λ and service rate μ in the same time unit. Utilisation ρ = λ ÷ (cμ) must be under 1 or the queue grows forever. Waiting climbs steeply above ~80% utilisation, which is why you add capacity before you "need" it. |
| How many people/servers do I need? | smallest c where average wait ≤ target | The result shows the probability a customer waits longer than your target. |
| Can we promise 99.9%? | **Availability and error budget** | Allowed downtime = (1 − SLO) × window. 99.9% ≈ 43 minutes a month. Serial parts multiply (all must be up); redundant parts combine as 1 − ∏(1 − a). Spent budget means freeze risky changes. |
| Is the project worth it? | **NPV, IRR, ROI, payback, benefit-cost ratio** | NPV = Σ cash flow ÷ (1 + r)ᵗ. NPV > 0 means it beats the discount rate. IRR is the rate where NPV is 0. Payback ignores the time value of money; discounted payback doesn't. |
| When will we run out? | **Capacity planning** | Compound monthly growth: months = ln(capacity ÷ load) ÷ ln(1 + g). Plan to add capacity at a headroom threshold (80%), not at 100%. |

## Feasibility (TELOS)
Score Technical, Economic, Legal, Operational and Schedule from 1 to 5 with weights. The result is a weighted score and a verdict, but a **single score under 3 needs a plan** even when the average looks fine; the dashboard names the weakest dimension.

## The analyst's loop
Elicit (interviews, observation, existing data) → model (process, data) → specify (requirements with acceptance criteria) → validate (does the stakeholder agree this is what they meant?) → trace (every requirement to a test) → check feasibility → hand over. Most failed projects fail at the first step: requirements that were never actually agreed.
