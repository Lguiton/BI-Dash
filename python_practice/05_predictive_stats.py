"""05 - Diagnostic and predictive analytics ("Why?" and "What is likely?").

Outlier detection three ways, regression, and a forecasting competition with an honest backtest.
The golden rule of forecasting: a model only counts if it beats a simple baseline on data it has NOT seen.
Run:  python 05_predictive_stats.py
"""
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from common import ROOT, banner, daily_revenue, load_operations

sys.path.insert(0, str(ROOT / "backend"))
from app.services.forecast import forecast_series  # the dashboard's own forecasting model (stdlib only)

pd.set_option("display.float_format", lambda v: f"{v:,.2f}")
df = load_operations()
daily = daily_revenue(df)

banner("1. Diagnostic: three ways to flag unusual cost per record")
cost = df["operational_cost"]
z = (cost - cost.mean()) / cost.std()
q1, q3 = cost.quantile([0.25, 0.75])
iqr = q3 - q1
med = cost.median()
mad = (cost - med).abs().median()
modz = 0.6745 * (cost - med) / mad
flags = pd.DataFrame({
    "z-score > 3": (z.abs() > 3), "IQR fences (1.5x)": (cost < q1 - 1.5 * iqr) | (cost > q3 + 1.5 * iqr),
    "modified z > 3.5 (MAD)": (modz.abs() > 3.5)})
print(flags.sum().to_string(), "\n")
print("Cost differs a lot between entities (95 vs 190 per record), so a GLOBAL threshold is the wrong tool.")
print("Better: standardize WITHIN each entity, then flag.")
df["cost_z_within_entity"] = df.groupby("entity_id")["operational_cost"].transform(lambda s: (s - s.mean()) / s.std())
print(df.loc[df["cost_z_within_entity"] > 3, ["record_date", "entity_name", "operational_cost", "cost_z_within_entity"]].head(10).to_string(index=False))

banner("2. Regression: does more volume mean more revenue?")
slope, intercept = np.polyfit(df["units_processed"], df["revenue"], 1)
r = np.corrcoef(df["units_processed"], df["revenue"])[0, 1]
print(f"revenue = {intercept:,.1f} + {slope:,.2f} x units | correlation r = {r:.3f} | R^2 = {r * r:.3f}")
print("Correlation is not causation: in this data units are generated FROM revenue, so the fit is almost too good.")

banner("3. Predictive: forecasting competition (rolling-origin backtest, 7-day horizon)")
H = 7


def naive(train: pd.Series) -> np.ndarray:            # tomorrow = today
    return np.repeat(train.iloc[-1], H)


def seasonal_naive(train: pd.Series) -> np.ndarray:   # same weekday last week
    return train.iloc[-7:].to_numpy()


def moving_avg(train: pd.Series) -> np.ndarray:       # flat line at the last-28-day average
    return np.repeat(train.iloc[-28:].mean(), H)


def linear_trend(train: pd.Series) -> np.ndarray:     # straight line, ignores weekdays
    x = np.arange(len(train))
    m, b = np.polyfit(x, train.to_numpy(), 1)
    return b + m * np.arange(len(train), len(train) + H)


def dashboard_model(train: pd.Series) -> np.ndarray:  # trend + weekday seasonality (the app's /forecast)
    pts = [(d.date(), float(v)) for d, v in train.items()]
    return np.array([p["forecast"] for p in forecast_series(pts, H)["points"]])


models = {"naive": naive, "seasonal naive": seasonal_naive, "28-day average": moving_avg,
          "linear trend": linear_trend, "dashboard model": dashboard_model}
origins = range(len(daily) - 8 * H, len(daily) - H + 1, H)   # 8 forecasts, each scored on unseen days
scores = {name: [] for name in models}
for o in origins:
    train, test = daily.iloc[:o], daily.iloc[o:o + H]
    for name, fn in models.items():
        pred = fn(train)
        scores[name].append(np.mean(np.abs(pred - test.to_numpy()) / test.to_numpy()) * 100)
result = pd.Series({k: np.mean(v) for k, v in scores.items()}, name="MAPE %").sort_values()
print(result.to_string())
winner, base = result.index[0], result["naive"]
print(f"\nBest: {winner}. It cuts error by {(1 - result.iloc[0] / base) * 100:.0f}% versus the naive baseline.")
print("MAPE = mean absolute percentage error: lower is better. Always compare against 'naive' first.")
print("CAUTION: this sample data was GENERATED as trend x weekday pattern x noise, which is exactly what the dashboard")
print("model assumes, so it has a home-field advantage. On real data expect a smaller win, and test again.")

banner("4. Prediction interval from residuals")
f = forecast_series([(d.date(), float(v)) for d, v in daily.items()], 7)
print(f"Method: {f['method']} | residual SD ${f['residual_sd']:,.0f} | app backtest MAPE {f['backtest']['mape_pct']}%")
for p in f["points"][:3]:
    print(f"  {p['date']}: ${p['forecast']:,.0f}  (95% range ${p['lower']:,.0f} to ${p['upper']:,.0f})")

print("""
YOUR TURN
1. Add Holt-Winters (statsmodels.tsa.holtwinters.ExponentialSmoothing, seasonal_periods=7) and ARIMA to the
   competition (pip install statsmodels). Do they beat 'dashboard model'?
2. Forecast PROFIT instead of revenue. Is it harder? Why? (profit = revenue - cost, both noisy)
3. Predict per entity instead of in total. Where do the errors get worse?
4. Prescriptive: given the forecast, how many extra records could Strip Core handle on weekends?""")
