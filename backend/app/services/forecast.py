"""Predictive analytics: a transparent trend + weekday-seasonality forecast.

Method (all computed here, nothing estimated by an LLM):
  1. Weekday factor  = average of (value / trend) for that weekday   (needs >= 2 full weeks)
  2. De-seasonalize  = value / weekday factor
  3. Trend           = ordinary least-squares line through the de-seasonalized series
     (steps 1-3 are repeated a few times, because trend and weekday pattern depend on each other)
  4. Forecast        = trend(t) * weekday factor
  5. Interval        = forecast +/- 1.96 * residual std-dev (about 95% if residuals are roughly normal)
  6. Backtest        = refit without the last 7 days, forecast them, report MAPE (mean abs % error)

It is deliberately simple so you can reproduce it in a spreadsheet, and so you can compare it with
fancier models (ARIMA, Holt-Winters, Prophet) in the Python practice scripts.
"""
import statistics
from datetime import date, timedelta

MIN_DAYS = 14
BACKTEST_DAYS = 7


def _fit(points: list[tuple[date, float]]):
    start = points[0][0]
    xs = [(d - start).days for d, _ in points]
    ys = [v for _, v in points]
    overall = statistics.fmean(ys)
    seasonal = len(points) >= 14 and overall > 0
    factors = {i: 1.0 for i in range(7)}
    slope, intercept = statistics.linear_regression(xs, ys)
    if seasonal:
        # Trend and weekday pattern are estimated together. Taking raw weekday means would mix
        # the two (in a growing series, later weekdays look "higher"), so alternate a few times:
        # fit the trend on de-seasonalized data, then re-estimate each weekday's ratio to that trend.
        for _ in range(8):
            des = [y / factors[d.weekday()] for d, y in points]
            slope, intercept = statistics.linear_regression(xs, des)
            ratios: dict[int, list[float]] = {i: [] for i in range(7)}
            for x, (d, y) in zip(xs, points):
                t = intercept + slope * x
                if t > 0:
                    ratios[d.weekday()].append(y / t)
            new = {i: (statistics.fmean(r) if r else 1.0) for i, r in ratios.items()}
            norm = statistics.fmean(new.values())
            factors = {i: f / norm for i, f in new.items()}
        des = [y / factors[d.weekday()] for d, y in points]
        slope, intercept = statistics.linear_regression(xs, des)
    fitted = [(intercept + slope * x) * factors[d.weekday()] for x, (d, _) in zip(xs, points)]
    resid = [y - f for (_, y), f in zip(points, fitted)]
    sd = statistics.stdev(resid) if len(resid) > 2 else 0.0
    return {"start": start, "slope": slope, "intercept": intercept, "factors": factors, "sd": sd, "seasonal": seasonal}


def _predict(m: dict, d: date) -> float:
    x = (d - m["start"]).days
    return max(0.0, (m["intercept"] + m["slope"] * x) * m["factors"][d.weekday()])


def forecast_series(daily: list[tuple[date, float]], horizon: int = 14) -> dict:
    if len(daily) < MIN_DAYS:
        return {"available": False, "reason": f"Need at least {MIN_DAYS} days of data to forecast (this selection has {len(daily)})."}
    daily = sorted(daily)
    m = _fit(daily)
    last = daily[-1][0]
    z = 1.96
    points = []
    for i in range(1, horizon + 1):
        d = last + timedelta(days=i)
        f = _predict(m, d)
        points.append({"date": d.isoformat(), "forecast": round(f, 2),
                       "lower": round(max(0.0, f - z * m["sd"]), 2), "upper": round(f + z * m["sd"], 2)})

    backtest = None
    if len(daily) >= MIN_DAYS + BACKTEST_DAYS:
        train, test = daily[:-BACKTEST_DAYS], daily[-BACKTEST_DAYS:]
        mb = _fit(train)
        errs = [abs(_predict(mb, d) - v) / v for d, v in test if v > 0]
        if errs:
            backtest = {"days": len(errs), "mape_pct": round(statistics.fmean(errs) * 100, 1)}

    # slope of the deseasonalized trend, per day, relative to the series mean
    mean = statistics.fmean(v for _, v in daily)
    return {
        "available": True,
        "method": "Linear trend with weekday seasonality" if m["seasonal"] else "Linear trend (too little data for weekday seasonality)",
        "trend_per_day": round(m["slope"], 2),
        "trend_pct_per_day": round(m["slope"] / mean * 100, 2) if mean else None,
        "residual_sd": round(m["sd"], 2),
        "backtest": backtest,
        "points": points,
    }
