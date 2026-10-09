"""Exercise 3 - evals: how you know an AI feature works (and keep knowing after you change it).

    python 03_evals.py

A text-to-SQL feature is graded by RESULTS, not wording: run the model's SQL and the reference SQL and compare rows.
Rule of thumb: no eval, no claim of "it works". Re-run this every time you change the prompt, model, or schema text.
"""
import re
import sys

from data import SCHEMA, connect, is_select_only
import llm
from llm import complete, live, offline

SYSTEM = f"You write one DuckDB SELECT for the table {SCHEMA}. Reply with only SQL."

GOLDEN = [
    {"q": "How many records are there?", "sql": "SELECT count(*) FROM operations"},
    {"q": "Total revenue?", "sql": "SELECT sum(revenue) FROM operations"},
    {"q": "Which category has the most records?", "sql": "SELECT category FROM operations GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT 1"},
    {"q": "Overall profit margin?", "sql": "SELECT sum(revenue - operational_cost) / sum(revenue) FROM operations"},
    {"q": "How many records were not completed?", "sql": "SELECT count(*) FROM operations WHERE status <> 'Completed'"},
]


@offline(r"QUESTION: (.*)")
def _stub(m, system):
    q = m.group(1).lower()
    if "how many" in q and "not completed" in q: return "SELECT count(*) FROM operations WHERE status <> 'Completed'"
    if "how many" in q: return "SELECT count(*) FROM operations"
    if "total revenue" in q: return "SELECT sum(revenue) FROM operations"
    if "margin" in q: return "SELECT avg((revenue - operational_cost) / revenue) FROM operations"  # the classic mistake: average of ratios
    if "category" in q: return "SELECT category FROM operations GROUP BY 1 ORDER BY count(*) DESC LIMIT 1"
    return "SELECT 1"


def rows(con, sql):
    return [tuple(round(v, 6) if isinstance(v, float) else v for v in r) for r in con.execute(sql).fetchall()]


def run_eval(generate=None, provider=None):
    gen = generate or (lambda q: complete(SYSTEM, f"QUESTION: {q}", kind="complex", provider=provider))
    con, results = connect(), []
    for case in GOLDEN:
        sql = re.sub(r"^```(?:sql)?|```$", "", gen(case["q"]).strip(), flags=re.M).strip().rstrip(";")
        if not is_select_only(sql):
            results.append({**case, "got": sql, "ok": False, "why": "blocked by guardrail"}); continue
        try:
            ok = rows(con, sql) == rows(con, case["sql"])
            results.append({**case, "got": sql, "ok": ok, "why": "" if ok else "different result"})
        except Exception as e:
            results.append({**case, "got": sql, "ok": False, "why": f"SQL error: {str(e)[:60]}"})
    return results


def report(res, name):
    for r in res:
        print(("PASS " if r["ok"] else "FAIL ") + r["q"] + ("" if r["ok"] else f"   -> {r['why']}: {r['got']}"))
    score = sum(r["ok"] for r in res) / len(res)
    print(f"{name}: {score:.0%} ({sum(r['ok'] for r in res)}/{len(res)})\n")
    return score


if __name__ == "__main__":
    if "--compare" in sys.argv:       # same golden set, every provider you have a key for: a real model bake-off
        scores = {p: report(run_eval(provider=p), llm.model_for(p)) for p in llm.available()}
        print("Summary:", ", ".join(f"{p} {s:.0%}" for s, p in sorted(((v, k) for k, v in scores.items()), reverse=True)) or "no keys set - add some to backend/.env")
        sys.exit(0)
    res = run_eval()
    score = report(res, "live " + llm.last_provider if live() else "offline stub")
    print("If a FAIL appeared: the stub averaged row-level margins instead of sum(profit)/sum(revenue) - the same trap as notebook 02. Evals catch it.")
    print("Tip: python 03_evals.py --compare   runs the same questions on every provider you have a key for.")
    print("Your turn: add 5 harder golden questions (a join-free GROUP BY with HAVING, a date filter, ...). Which does the model miss?")
    sys.exit(0 if score >= 0.8 else 1)
