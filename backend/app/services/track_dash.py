"""Data behind each career track's own practice dashboard (GET /api/tracks/{id}/dashboard).

Each function returns plain JSON for one dashboard. Anything that needs an optional package (scipy, scikit-learn) says
so in an "available: false" block instead of failing, so the page still renders.
"""
from __future__ import annotations

import math

from app.services import llm_router, pipeline, study
from app.services.db import fetch_all, fetch_one, get_cursor


def analyst() -> dict:
    with get_cursor() as cur:
        k = fetch_one(cur, """SELECT COUNT(*) AS records, SUM(f.revenue) AS revenue, SUM(f.operational_cost) AS cost,
            SUM(f.revenue - f.operational_cost) AS profit,
            100.0 * SUM(f.revenue - f.operational_cost) / NULLIF(SUM(f.revenue), 0) AS margin_pct,
            100.0 * (SUM(f.operational_cost) / NULLIF(SUM(e.baseline_target), 0) - 1) AS vs_budget_pct,
            100.0 * AVG(CASE WHEN f.status = 'Completed' THEN 1.0 ELSE 0.0 END) AS completion_pct
            FROM fact_operations f LEFT JOIN dim_entities e ON e.entity_id = f.entity_id""")
        over = fetch_all(cur, """SELECT COALESCE(e.name, f.entity_id) AS entity, e.category,
            SUM(f.operational_cost) - SUM(e.baseline_target) AS overspend_usd,
            100.0 * (SUM(f.operational_cost) / NULLIF(SUM(e.baseline_target), 0) - 1) AS vs_budget_pct, COUNT(*) AS records
            FROM fact_operations f JOIN dim_entities e ON e.entity_id = f.entity_id
            GROUP BY 1, 2 HAVING SUM(e.baseline_target) > 0 ORDER BY vs_budget_pct DESC LIMIT 6""")
        weekly = fetch_all(cur, """SELECT strftime(date_trunc('week', record_date), '%Y-%m-%d') AS week,
            100.0 * SUM(revenue - operational_cost) / NULLIF(SUM(revenue), 0) AS margin_pct, SUM(revenue) AS revenue
            FROM fact_operations GROUP BY 1 ORDER BY 1 DESC LIMIT 26""")[::-1]
        status_mix = fetch_all(cur, "SELECT COALESCE(status, 'Unknown') AS status, COUNT(*) AS n FROM fact_operations GROUP BY 1 ORDER BY 2 DESC")
    from app.routers import quality
    q = quality.report()
    return {"kpis": k, "over_budget": over, "weekly_margin": weekly, "status_mix": status_mix,
            "quality": {"score_pct": q["score_pct"], "passed": q["passed"], "total": q["total_checks"],
                        "failing": [c["title"] for c in q["checks"] if c["status"] != "ok"][:4]},
            "ideas": ["Which entity should a manager visit first, and why? Back it with the over-budget table.",
                      "Write the 3-sentence summary an executive would read. Lead with the number that changed.",
                      "Rebuild the weekly margin chart in Tableau or Superset and compare."]}


def scientist() -> dict:
    out: dict = {"ideas": ["Is the weekend premium still significant if you drop the first month? (notebook 11)",
                           "Name each entity segment and say what you'd do differently for each.",
                           "Which correlation is strong but meaningless? Why?"]}
    with get_cursor() as cur:
        days = fetch_all(cur, """SELECT record_date, SUM(revenue) AS revenue, isodow(record_date) >= 6 AS weekend
                                 FROM fact_operations GROUP BY 1 ORDER BY 1""")
        prof = fetch_all(cur, """SELECT COALESCE(e.name, f.entity_id) AS entity, AVG(f.revenue) AS avg_revenue,
            SUM(f.revenue - f.operational_cost) / NULLIF(SUM(f.revenue), 0) AS margin,
            SUM(f.operational_cost) / NULLIF(SUM(e.baseline_target), 0) AS cost_ratio,
            AVG(CASE WHEN f.status = 'Completed' THEN 1.0 ELSE 0.0 END) AS completion
            FROM fact_operations f JOIN dim_entities e ON e.entity_id = f.entity_id GROUP BY 1""")
        cols = fetch_all(cur, "SELECT revenue, operational_cost, units_processed, duration_minutes FROM fact_operations "
                              "WHERE revenue IS NOT NULL AND operational_cost IS NOT NULL AND units_processed IS NOT NULL "
                              "AND duration_minutes IS NOT NULL LIMIT 20000")
    # --- weekend vs weekday: Welch t-test on DAILY totals (the day is the independent unit) ---
    we = [float(d["revenue"]) for d in days if d["weekend"]]
    wd = [float(d["revenue"]) for d in days if not d["weekend"]]
    if len(we) >= 5 and len(wd) >= 5:
        try:
            from scipy import stats
            t = stats.ttest_ind(we, wd, equal_var=False)
            m1, m2 = sum(we) / len(we), sum(wd) / len(wd)
            v1 = sum((x - m1) ** 2 for x in we) / (len(we) - 1); v2 = sum((x - m2) ** 2 for x in wd) / (len(wd) - 1)
            se = math.sqrt(v1 / len(we) + v2 / len(wd))
            df = se ** 4 / ((v1 / len(we)) ** 2 / (len(we) - 1) + (v2 / len(wd)) ** 2 / (len(wd) - 1))
            crit = float(stats.t.ppf(0.975, df))
            diff = m1 - m2
            out["weekend_test"] = {"available": True, "weekend_days": len(we), "weekday_days": len(wd), "weekend_mean": round(m1, 2),
                                   "weekday_mean": round(m2, 2), "diff": round(diff, 2), "ci_low": round(diff - crit * se, 2),
                                   "ci_high": round(diff + crit * se, 2), "t": round(float(t.statistic), 3), "p_value": float(t.pvalue),
                                   "verdict": "significant at 5%" if t.pvalue < 0.05 else "not significant at 5%"}
        except ImportError:
            out["weekend_test"] = {"available": False, "reason": "Needs scipy: pip install scipy"}
    else:
        out["weekend_test"] = {"available": False, "reason": "Needs at least 5 weekend days and 5 weekday days of data."}
    # --- segments ---
    if len(prof) >= 4:
        try:
            import numpy as np
            from sklearn.cluster import KMeans
            from sklearn.preprocessing import StandardScaler
            keys = ["avg_revenue", "margin", "cost_ratio", "completion"]
            X = np.array([[float(r[k] or 0) for k in keys] for r in prof])
            k = min(3, len(prof) - 1)
            labels = KMeans(n_clusters=k, n_init=10, random_state=0).fit_predict(StandardScaler().fit_transform(X))
            segs = []
            for c in range(k):
                idx = [i for i, l in enumerate(labels) if l == c]
                segs.append({"segment": c + 1, "entities": sorted(prof[i]["entity"] for i in idx),
                             "means": {key: round(float(X[idx, j].mean()), 3) for j, key in enumerate(keys)}})
            out["segments"] = {"available": True, "keys": keys, "segments": sorted(segs, key=lambda s: -len(s["entities"]))}
        except ImportError:
            out["segments"] = {"available": False, "reason": "Needs scikit-learn: pip install scikit-learn"}
    else:
        out["segments"] = {"available": False, "reason": "Needs at least 4 entities to cluster."}
    # --- correlations ---
    names = ["revenue", "operational_cost", "units_processed", "duration_minutes"]
    if len(cols) >= 10:
        import numpy as np
        M = np.array([[float(r[n]) for n in names] for r in cols])
        with np.errstate(invalid="ignore"):
            C = np.corrcoef(M, rowvar=False)
        out["correlations"] = {"available": True, "names": names, "matrix": [[None if math.isnan(v) else round(float(v), 3) for v in row] for row in C]}
    else:
        out["correlations"] = {"available": False, "reason": "Needs at least 10 complete records."}
    return out


def ml() -> dict:
    runs = study.ml_runs(30)
    best: dict[str, dict] = {}
    for r in runs:
        if r["model_score"] is None:
            continue
        cur = best.get(r["task"])
        if cur is None or r["model_score"] > cur["model_score"]:
            best[r["task"]] = r
    return {"runs": runs[:12], "total_runs": len(runs),
            "best": [{**b, "lift": None if b["baseline_score"] is None else round(b["model_score"] - b["baseline_score"], 4)} for b in best.values()],
            "ideas": ["Beat your best score using fewer features. What does that tell you?",
                      "Train 'Predict a problem record' twice: balanced and not. Compare recall and false alarms.",
                      "Remove 'Units processed' and watch the score drop: that is what 'important' means."]}


def engineering() -> dict:
    return {"pipeline": pipeline.status(),
            "ideas": ["Take a backup, then run 'Verify backup' on the Database admin tab. What would you do if it failed?",
                      "Run the PII scan after importing a file with an email column. Which columns would you restrict, and who should own the table?","Run the messy file, then read the quarantine reasons. Which rule would you add?",
                      "Run twice in a row: why do the silver counts not change?",
                      "Wrap this in an Airflow DAG (Apache page) and add a freshness alert."]}


def ai() -> dict:
    st = llm_router.status()
    return {"providers": st["providers"], "ready": st["ready"], "log": study.ai_summary(),
            "ideas": ["Ask the same question with each provider forced. Do the SQL queries differ?",
                      "Ask for a chart of weekly margin by category. Check the SQL it used.",
                      "Run python ai_engineering/03_evals.py --compare and record the scores."]}


def pm_ideas() -> dict:
    return {"ideas": ["Score five backlog items with RICE, then change one confidence value. Did the order move? What does that say about the decision?",
                      "Open the critical path. Which task would you shorten first, and which would be wasted effort?",
                      "Is your WIP above what Little's law expects? What would you stop starting?",
                      "Read the retention table: at what month does your oldest cohort flatten, and what does it mean for the product?"]}


def sysanalyst_ideas() -> dict:
    return {"ideas": ["Write a requirement that is not testable, then rewrite it so it is.",
                      "Use the queue calculator with your real arrival and service times. At what utilisation does waiting explode?",
                      "Find a relationship in the data dictionary with orphans. What requirement would prevent it?",
                      "Score a change you are considering with TELOS. Which dimension would you raise first with the sponsor?"]}


def fullstack_ideas() -> dict:
    return {"ideas": [
        "Scaffold one of your tables, read every generated line, and find where user input could have become SQL (it shouldn't).",
        "Use the API tester to send a bad body to a POST endpoint. Is the 422 message good enough for a user?",
        "Open the codebase tab: which file is largest, and what two jobs could it be split into?",
        "Add a column to a table and follow it through the API, the type and the form. What did you forget?",
    ]}


BUILDERS = {"analyst": analyst, "scientist": scientist, "ml": ml, "engineering": engineering, "ai": ai, "pm": pm_ideas, "sysanalyst": sysanalyst_ideas, "fullstack": fullstack_ideas}
