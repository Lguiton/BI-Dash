"""02 - Descriptive analytics with pandas ("What happened?").

Covers: aggregation, KPIs, the non-additive measure trap, pivot tables, and time intelligence
(rolling averages, period-over-period, month-to-date, year-to-date).
Run:  python 02_pandas_explore.py
"""
import pandas as pd

from common import banner, daily_revenue, load_operations

pd.set_option("display.width", 120)
pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
df = load_operations()

banner("1. Descriptive KPIs (revenue, profit, margin)")
total_rev, total_profit = df["revenue"].sum(), df["profit"].sum()
print(f"Revenue ${total_rev:,.0f} | Profit ${total_profit:,.0f} | Margin {total_profit / total_rev:.1%}")

banner("2. The non-additive measure trap")
naive = df.groupby("category")["margin"].mean()                                  # average of per-row ratios
correct = df.groupby("category")["profit"].sum() / df.groupby("category")["revenue"].sum()  # ratio of sums
print(pd.DataFrame({"avg of row margins (WRONG)": naive * 100, "sum(profit)/sum(revenue) (RIGHT)": correct * 100}))
print("\nRatios (margin %, stops per hour, cost per unit) are NON-additive: add up the numerator and the")
print("denominator first, then divide. Averaging ratios gives small rows the same weight as big ones.")

banner("3. Group + pivot: average revenue per record, weekday x category")
print(df.pivot_table(index="day_name", columns="category", values="revenue", aggfunc="mean")
        .reindex(["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]))

banner("4. Cost vs budget (baseline_target = cost budget per record)")
e = df.groupby("entity_name").agg(avg_cost=("operational_cost", "mean"), budget=("baseline_target", "first"),
                                 revenue=("revenue", "sum"), profit=("profit", "sum"))
e["pct_over_budget"] = (e["avg_cost"] / e["budget"] - 1) * 100
print(e.sort_values("pct_over_budget", ascending=False))

banner("5. Time intelligence")
d = daily_revenue(df).to_frame("revenue")
d["rolling_7d_avg"] = d["revenue"].rolling(7).mean()                      # Rolling 7-day average
d["dod_pct"] = d["revenue"].pct_change() * 100                            # Day-over-day
d["mtd"] = d.groupby(d.index.to_period("M"))["revenue"].cumsum()           # Month-to-date: resets each month
d["ytd"] = d.groupby(d.index.year)["revenue"].cumsum()                     # Year-to-date: resets each January
print(d.tail(8))
m = d["revenue"].resample("MS").sum().to_frame("revenue")                  # Month buckets
m["mom_pct"] = m["revenue"].pct_change() * 100                             # Month-over-month (Period-over-Period)
m["yoy_pct"] = m["revenue"].pct_change(12) * 100                           # Year-over-year needs 12+ months
print("\nMonthly with period-over-period:\n", m.tail(6))

print("""
YOUR TURN
1. Add a 30-day rolling average and a 'vs same weekday last week' column (hint: .shift(7)).
2. Which single entity-weekday combination has the highest average revenue per record?
3. Recreate the dashboard's 'Net margin' KPI for just the last 30 days. Does it match the app?
4. Compare these results with the SQL Lab exercises 'Monthly revenue' and 'Year-to-date revenue'.""")
