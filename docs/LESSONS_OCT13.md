# Survey numbers, free courses, leadership self-review

- **Survey numbers** (Analyst and Scientist tracks): `services/survey_stats.py`, `/api/surveystats/...`. Margin of a percentage, is a gap real, sample size, pick-one vs pick-several, joint/marginal/conditional tables with an independence check. Assumes a simple random sample.
- **Free AI course catalog** (AI, ML, Scientist tracks): `services/courses.py`, `/api/courses`. 60 courses as published with their mistakes marked (a duplicate, mixed sections, "free" that may not be), progress ticks, five suggested paths. Cannot check free status today.
- **Leadership self-review** (PM track): `services/leadership.py`, `/api/leadership`. Five disciplines, 15 behaviours, finds the weakest and one practice. The source graphic is not an official Harvard Business School framework.

Source mistakes are listed in each service's `SLIPS` and shown in the app. Not buildable: weighted survey error, live course status, hosting courses, coaching.
