"""06 - Visualization techniques with matplotlib.

Builds the chart types from your notes: trend with forecast band, heatmap, scatter, box plot, and a
Z-pattern dashboard (KPI ribbon on top, trend in the middle, drill-down detail at the bottom) with
contextual benchmarking (every number compared against a budget or prior period).
PNGs are written to python_practice/_out/.   Run:  python 06_visualization.py
"""
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.gridspec import GridSpec

from common import OUT, ROOT, banner, daily_revenue, load_operations

sys.path.insert(0, str(ROOT / "backend"))
from app.services.forecast import forecast_series

GOOD, BAD, BLUE, GREY = "#059669", "#dc2626", "#2563eb", "#64748b"
df = load_operations()
daily = daily_revenue(df)
fc = forecast_series([(d.date(), float(v)) for d, v in daily.items()], 14)


def style(ax, title):
    ax.set_title(title, loc="left", fontsize=11, fontweight="bold")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", alpha=0.25)


banner("1. Trend + 7-day average + forecast band")
fig, ax = plt.subplots(figsize=(10, 4))
recent = daily.iloc[-90:]
ax.plot(recent.index, recent, color=BLUE, alpha=0.35, label="daily revenue")
ax.plot(recent.index, daily.rolling(7).mean().iloc[-90:], color=BLUE, lw=2, label="7-day average")
fx = pd.to_datetime([p["date"] for p in fc["points"]])
ax.plot(fx, [p["forecast"] for p in fc["points"]], color=GOOD, ls="--", lw=2, label="forecast")
ax.fill_between(fx, [p["lower"] for p in fc["points"]], [p["upper"] for p in fc["points"]], color=GOOD, alpha=0.18, label="95% range")
style(ax, "Revenue: last 90 days and 14-day forecast")
ax.legend(frameon=False, ncol=4, loc="upper left")
fig.tight_layout(); fig.savefig(OUT / "06_trend_forecast.png", dpi=130); plt.close(fig)
print("saved 06_trend_forecast.png  (rule: show uncertainty, never a bare forecast line)")

banner("2. Heatmap: average revenue by weekday x entity")
order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
pv = df.pivot_table(index="entity_name", columns="day_name", values="revenue", aggfunc="mean")[order]
fig, ax = plt.subplots(figsize=(9, 5))
im = ax.imshow(pv.to_numpy(), cmap="Blues", aspect="auto")
ax.set_xticks(range(7), [d[:3] for d in order]); ax.set_yticks(range(len(pv)), pv.index)
for i in range(pv.shape[0]):
    for j in range(7):
        v = pv.iat[i, j]
        ax.text(j, i, f"{v:,.0f}", ha="center", va="center", fontsize=8, color="white" if v > pv.to_numpy().mean() * 1.2 else "black")
ax.set_title("Average revenue per record", loc="left", fontsize=11, fontweight="bold")
fig.colorbar(im, ax=ax, shrink=0.8); fig.tight_layout(); fig.savefig(OUT / "06_heatmap.png", dpi=130); plt.close(fig)
print("saved 06_heatmap.png  (use a SEQUENTIAL palette for one-direction data; diverging only around a meaningful midpoint)")

banner("3. Scatter and box plot")
fig, (a, b) = plt.subplots(1, 2, figsize=(12, 4.5))
for name, g in df.groupby("category"):
    a.scatter(g["operational_cost"], g["revenue"], s=6, alpha=0.4, label=name)
a.set_xlabel("operational cost"); a.set_ylabel("revenue"); a.legend(frameon=False, markerscale=3); style(a, "Cost vs revenue per record")
df.boxplot(column="margin", by="category", ax=b, grid=False)
b.set_title(""); fig.suptitle(""); style(b, "Margin distribution by category"); b.set_xlabel("")
fig.tight_layout(); fig.savefig(OUT / "06_scatter_box.png", dpi=130); plt.close(fig)
print("saved 06_scatter_box.png  (a bar of averages hides spread; a box plot shows it)")

banner("4. Z-pattern dashboard with contextual benchmarking")
last30 = df[df["record_date"] > df["record_date"].max() - pd.Timedelta(days=30)]
prev30 = df[(df["record_date"] <= df["record_date"].max() - pd.Timedelta(days=30)) &
            (df["record_date"] > df["record_date"].max() - pd.Timedelta(days=60))]
fig = plt.figure(figsize=(12, 9))
gs = GridSpec(3, 4, height_ratios=[0.7, 2, 2.2], figure=fig, hspace=0.45, wspace=1.1)
kpis = [("Revenue", last30["revenue"].sum(), prev30["revenue"].sum(), "${:,.0f}", True),
        ("Profit", last30["profit"].sum(), prev30["profit"].sum(), "${:,.0f}", True),
        ("Margin", last30["profit"].sum() / last30["revenue"].sum() * 100, prev30["profit"].sum() / prev30["revenue"].sum() * 100, "{:.1f}%", True),
        ("Avg cost / record", last30["operational_cost"].mean(), prev30["operational_cost"].mean(), "${:,.0f}", False)]
for i, (name, cur, prev, fmt, up_good) in enumerate(kpis):          # TOP: the executive pulse
    ax = fig.add_subplot(gs[0, i]); ax.axis("off")
    ch = (cur / prev - 1) * 100 if "%" not in fmt else cur - prev
    good = (ch >= 0) == up_good
    ax.text(0, 0.8, name.upper(), fontsize=9, color=GREY)
    ax.text(0, 0.35, fmt.format(cur), fontsize=20, fontweight="bold")
    ax.text(0, 0.0, f"{ch:+.1f}{' pts' if '%' in fmt else '%'} vs prior 30 days", fontsize=9, color=GOOD if good else BAD)
ax = fig.add_subplot(gs[1, :])                                         # MIDDLE: the trend
ax.plot(daily.index[-120:], daily.iloc[-120:], color=BLUE, alpha=0.3)
ax.plot(daily.index[-120:], daily.rolling(7).mean().iloc[-120:], color=BLUE, lw=2)
style(ax, "Revenue trend (7-day average)")
ax = fig.add_subplot(gs[2, :2])                                        # BOTTOM-LEFT: breakdown with a target
e = last30.groupby("entity_name").agg(c=("operational_cost", "mean"), b=("baseline_target", "first"))
e["over"] = (e["c"] / e["b"] - 1) * 100
e = e.sort_values("over")
ax.barh(e.index, e["over"], color=[BAD if v > 5 else GOOD if v < 0 else GREY for v in e["over"]])
ax.axvline(0, color="black", lw=0.8); style(ax, "Cost vs budget (% over; red = over by >5%)")
ax = fig.add_subplot(gs[2, 2:])                                        # BOTTOM-RIGHT: detail
p = last30.groupby("entity_name")["profit"].sum().sort_values()
ax.barh(p.index, p, color=BLUE); style(ax, "Profit, last 30 days")
fig.savefig(OUT / "06_z_pattern_dashboard.png", dpi=130, bbox_inches="tight"); plt.close(fig)
print("saved 06_z_pattern_dashboard.png  (read it: top-left to top-right, diagonal to bottom-left, then across)")

print("""
YOUR TURN
1. Recreate the dashboard's 'Cost vs budget' column as a bullet chart (actual bar vs target tick).
2. Use a DIVERGING palette (red-white-green) on a heatmap of margin minus the overall margin. Why is the
   midpoint important?
3. Make the Z-pattern dashboard for ONE entity only (cross-filtering). Reuse your code as a function.
4. Remove the y-axis gridlines and the box-plot whiskers. What can the reader no longer judge?""")
