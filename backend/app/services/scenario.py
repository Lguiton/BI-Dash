"""What-if scenarios on money (adapted from the NexusFlow scenario modeler): price change, new hire, lost account, extra cost, growth.
Pure arithmetic on the numbers you give it, so the CFO agent never guesses. Returns baseline, projected result and cash runway."""
from __future__ import annotations

KINDS = ("price_change_pct", "volume_change_pct", "new_hire_monthly_cost", "extra_monthly_cost", "lost_account_monthly_revenue", "new_account_monthly_revenue", "cost_cut_pct")


class ScenarioError(Exception):
    pass


def _runway(cash: float | None, net: float) -> float | None:
    if cash is None or net >= 0:
        return None
    return round(cash / abs(net), 1)


def run(kind: str, amount: float, monthly_revenue: float, monthly_cost: float, cash: float | None = None, months: int = 12) -> dict:
    if kind not in KINDS:
        raise ScenarioError("Unknown scenario. Use one of: " + ", ".join(KINDS))
    try:
        amount, rev, cost = float(amount), float(monthly_revenue), float(monthly_cost)
        cash = None if cash is None else float(cash)
    except (TypeError, ValueError) as e:
        raise ScenarioError("Amounts must be numbers.") from e
    if rev < 0 or cost < 0:
        raise ScenarioError("Revenue and cost must be zero or more.")
    months = max(1, min(int(months), 60))
    r2, c2 = rev, cost
    if kind in ("price_change_pct", "volume_change_pct"):
        r2 = rev * (1 + amount / 100)
    elif kind == "new_hire_monthly_cost" or kind == "extra_monthly_cost":
        c2 = cost + abs(amount)
    elif kind == "lost_account_monthly_revenue":
        r2 = max(0.0, rev - abs(amount))
    elif kind == "new_account_monthly_revenue":
        r2 = rev + abs(amount)
    elif kind == "cost_cut_pct":
        c2 = cost * (1 - abs(amount) / 100)
    net0, net1 = rev - cost, r2 - c2
    out = {"scenario": kind, "amount": amount, "baseline": {"revenue": round(rev, 2), "cost": round(cost, 2), "net": round(net0, 2), "margin_pct": round(100 * net0 / rev, 1) if rev else None},
           "projected": {"revenue": round(r2, 2), "cost": round(c2, 2), "net": round(net1, 2), "margin_pct": round(100 * net1 / r2, 1) if r2 else None},
           "net_change_per_month": round(net1 - net0, 2), f"net_change_over_{months}_months": round((net1 - net0) * months, 2),
           "runway_months": {"before": _runway(cash, net0), "after": _runway(cash, net1)} if cash is not None else None}
    out["summary"] = (f"Monthly net moves from {net0:,.2f} to {net1:,.2f} ({net1 - net0:+,.2f}); over {months} months that is {(net1 - net0) * months:+,.2f}."
                      + (f" Cash runway goes from {out['runway_months']['before'] or 'not burn-limited'} to {out['runway_months']['after'] or 'not burn-limited'} months." if cash is not None else ""))
    return out


TOOL_SCENARIO = {"name": "scenario", "description": "What-if on money. Give the scenario kind, the amount, and the current monthly revenue and cost (take them from get_dashboard or run_sql, never guess). Optional cash reserve gives runway. "
                 "Kinds: " + ", ".join(KINDS) + ". Percent kinds take a percent (e.g. 5 for +5%).",
                 "input_schema": {"type": "object", "properties": {"kind": {"type": "string", "enum": list(KINDS)}, "amount": {"type": "number"}, "monthly_revenue": {"type": "number"}, "monthly_cost": {"type": "number"},
                                                                  "cash": {"type": "number"}, "months": {"type": "integer"}}, "required": ["kind", "amount", "monthly_revenue", "monthly_cost"]}}
