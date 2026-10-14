# Project and product management: the technical vocabulary

The **Project & Product** dashboard (Tracks → Project & Product) is a working board, not a picture. You add items, sprints, risks and key results; every number below is computed from them. Use **Load example project** in Practice to see it filled in. In Real, it starts empty and holds your own project.

## Prioritising what to build
| Technique | Formula | Use it when |
|---|---|---|
| **RICE** | Reach × Impact × Confidence ÷ Effort | Comparing features for a product. Reach = people affected per period; Impact = 0.25 (minimal), 0.5, 1, 2, 3 (massive); Confidence = 0 to 1 (0.8 = 80%); Effort = person-months or points. |
| **WSJF** (SAFe) | (User value + Time criticality + Risk reduction) ÷ Job size | Sequencing work by cost of delay. Score each of the first three on a relative scale (1, 2, 3, 5, 8, 13, 20). Job size here is the story points. |
| **MoSCoW** | Must / Should / Could / Won't | Fixing scope for a release. A healthy release keeps Must-haves under about 60% of the effort so there is room for surprises. |

Scores are for *ranking*, not for truth. Change one assumption and watch the rank move: if a small change reorders the list, the items are close and the decision is a judgement call.

## Agile flow metrics
* **Velocity**: story points *completed* per sprint. Use the average of the last three finished sprints to forecast. Never compare velocity between teams: points are a private scale.
* **Burndown**: points remaining each day of the sprint against a straight ideal line. Above the line means behind; a flat line then a cliff means work is finished in a rush at the end (or not updated).
* **Cumulative flow diagram (CFD)**: items by state over time. Bands that widen show a bottleneck (work piling up in a state).
* **Cycle time**: started → done. **Lead time**: created → done (includes waiting in the backlog). Quote percentiles, not just averages: "85% of items finish within N days" is a promise you can plan with.
* **Throughput**: items finished per week.
* **WIP** (work in progress) and **Little's law**: average WIP = throughput × average cycle time. If your actual WIP is far above that, work is stuck or you start more than you finish; limiting WIP shortens cycle time.
* **Forecast**: remaining points ÷ velocity = sprints left. The dashboard shows a fast, likely and slow case from your best and worst recent sprint, because one date is false precision.

## Scheduling: the critical path (CPM)
Give items a duration in days and dependencies (item ids). The dashboard computes, for each: earliest start/finish (ES, EF), latest start/finish (LS, LF) without delaying the project, and **float = LS − ES**. Items with zero float form the **critical path**: any delay there delays the whole project. Items with float can slip by that much for free. A dependency loop is reported instead of computed, because a schedule cannot contain a cycle.

## Cost and schedule: earned value (EVM)
| Term | Meaning |
|---|---|
| BAC | Budget at completion: total planned cost |
| PV | Planned value: planned cost × share of the schedule that should be done by today |
| EV | Earned value: planned cost of work actually finished (0/100 rule: counts only when done) |
| AC | Actual cost spent so far |
| CPI = EV ÷ AC | Cost efficiency. Under 1 is over budget |
| SPI = EV ÷ PV | Schedule efficiency. Under 1 is behind |
| EAC = BAC ÷ CPI | Estimate at completion if the trend continues |
| ETC = EAC − AC | Estimate to complete |
| VAC = BAC − EAC | Forecast variance at completion |
| TCPI = (BAC − EV) ÷ (BAC − AC) | Efficiency you must achieve on the rest to finish on budget. Far above 1 means the budget is probably gone |

## Risk
Each risk has a probability (0 to 1) and a dollar impact. **Expected monetary value (EMV) = probability × impact.** The sum over open risks is a starting size for a contingency reserve. The 3×3 grid places each open risk by impact (thirds of your largest risk) and probability (under 25%, 25–60%, over 60%); work the top-right first.

## OKRs
An Objective (qualitative, inspiring) with Key Results (numbers that prove it). Progress = (current − start) ÷ (target − start), capped 0 to 100%. Around 70% on a stretch goal is healthy; always hitting 100% means the targets were too safe.

## Product analytics (from your own data)
Entities stand in for accounts or users and each record is one unit of activity.
* **Active accounts** per week; **DAU / MAU stickiness** = average daily actives ÷ monthly actives (about 20% is common for business tools, 50%+ is a daily habit).
* **Funnel**: share of records in each status.
* **Cohort retention**: group entities by the month they first appear; retention at month *k* is the share of the cohort still active *k* months later. A curve that flattens above zero means you have a core of retained users; one that keeps falling means you are leaking.
* A **North Star metric** is the single number that best captures the value customers get. Pick it in the KPI builder and track it beside guardrail metrics (the things that must not get worse).

## Habits worth building
Write the problem before the solution (a one-page PRD: who, what pain, how you will know it worked). Slice work so every item finishes inside a sprint. Re-estimate rarely, re-prioritise often. Review the numbers in a retro, not to blame but to pick one thing to change.

## Time tracker
Log hours per work item on the Time tab. Earned value uses logged hours x rate for actual cost when hours exist; otherwise it uses the planned cost.
