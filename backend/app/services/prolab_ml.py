"""Machine learning depth: network shapes and cost, explanations, tuning budget, recommenders, forecasting metrics, drift, serving, bandits."""
from __future__ import annotations

import itertools
import math
import random

from app.services.prolab import ProError, lab, lines, num, r, ref, tool, txt

T = "ml"
lab(T, "Machine learning depth: model maths, explanations, tuning, recommenders, forecasting, drift and serving")


def cnn(a):
    h, w, cin, cout, k, s, p = (int(num(a, x, lo=0)) for x in ("height", "width", "in_channels", "out_channels", "kernel", "stride", "padding"))
    if k < 1 or s < 1 or cin < 1 or cout < 1:
        raise ProError("Kernel, stride and channels must be at least 1.")
    oh, ow = (h + 2 * p - k) // s + 1, (w + 2 * p - k) // s + 1
    if oh < 1 or ow < 1:
        raise ProError("The kernel is larger than the padded input.")
    params = (k * k * cin + 1) * cout
    return {"output_height": oh, "output_width": ow, "output_shape": f"{oh} x {ow} x {cout}", "parameters": params, "multiply_adds": k * k * cin * cout * oh * ow, "how": "Output = floor((size + 2 x padding - kernel) / stride) + 1. Parameters = (kernel x kernel x input channels + 1 bias) x output channels."}


tool(T, "cnn_layer", "Convolution layer shape", "Output size, parameters and cost.", [("height", "Input height", 224), ("width", "Input width", 224), ("in_channels", "Input channels", 3), ("out_channels", "Filters", 64), ("kernel", "Kernel size", 3), ("stride", "Stride", 1), ("padding", "Padding", 1)], cnn)


def transformer(a):
    d, L, v, ff, seq = int(num(a, "d_model", lo=1)), int(num(a, "layers", lo=1)), int(num(a, "vocab", lo=1)), int(num(a, "ff_mult", lo=1)), int(num(a, "seq_len", lo=1))
    attn = 4 * d * d
    mlp = 2 * d * d * ff
    per = attn + mlp
    emb = v * d
    tot = L * per + emb
    flops_tok = 2 * tot + 4 * L * seq * d
    return {"parameters_m": r(tot / 1e6, 1), "per_layer_m": r(per / 1e6, 2), "embedding_m": r(emb / 1e6, 1), "forward_flops_per_token_g": r(flops_tok / 1e9, 2), "training_flops_6nd_per_token_g": r(6 * tot / 1e9, 2),
            "how": "Per layer: attention 4 x d^2 plus feed-forward 2 x d^2 x multiplier. Forward cost is about 2 x parameters per token; training about 6 x. Layer norms and biases are ignored (small)."}


tool(T, "transformer_size", "Transformer parameters and FLOPs", "Size and compute of a decoder model.", [("d_model", "Hidden size", 768), ("layers", "Layers", 12), ("vocab", "Vocabulary size", 50000), ("ff_mult", "Feed-forward multiplier", 4), ("seq_len", "Sequence length", 1024)], transformer)


def lstm(a):
    i, h, layers = int(num(a, "input_size", lo=1)), int(num(a, "hidden_size", lo=1)), int(num(a, "layers", lo=1))
    tot = 0
    for ly in range(layers):
        ins = i if ly == 0 else h
        tot += 4 * (h * (ins + h) + h)
    return {"parameters": tot, "gates": "4 (input, forget, cell, output)", "how": "Per layer: 4 x (hidden x (input + hidden) + bias). Frameworks may add a second bias vector."}


tool(T, "lstm_params", "LSTM parameters", "Count parameters of stacked LSTM layers.", [("input_size", "Input size", 32), ("hidden_size", "Hidden size", 128), ("layers", "Layers", 2)], lstm)


def shap(a):
    rows = lines(a, "weights", "the model")
    names, w = [p[0] for p in rows], [float(p[1]) for p in rows]
    x = [float(v) for v in txt(a, "instance", "the instance").split(",")]
    b = [float(v) for v in txt(a, "baseline", "the baseline").split(",")]
    if not (len(w) == len(x) == len(b)):
        raise ProError("Weights, instance and baseline need the same number of values.")
    contrib = [wi * (xi - bi) for wi, xi, bi in zip(w, x, b)]
    n = len(w)
    # exact Shapley by enumeration for a linear model, check against closed form
    def v(S):
        return sum(w[j] * (x[j] if j in S else b[j]) for j in range(n))
    if n <= 8:
        exact = []
        for i in range(n):
            tot = 0.0
            others = [j for j in range(n) if j != i]
            for k in range(n):
                for S in itertools.combinations(others, k):
                    wt = math.factorial(k) * math.factorial(n - k - 1) / math.factorial(n)
                    tot += wt * (v(set(S) | {i}) - v(set(S)))
            exact.append(tot)
    else:
        exact = contrib
    base_pred, pred = v(set()), v(set(range(n)))
    return {"baseline_prediction": r(base_pred, 4), "prediction": r(pred, 4), "contributions": [{"feature": nm, "shapley": r(e, 4), "closed_form": r(c, 4)} for nm, e, c in zip(names, exact, contrib)],
            "adds_up": abs(sum(exact) - (pred - base_pred)) < 1e-6, "how": "Shapley value = a feature's average effect on the prediction over every order the features could be added. For a linear model it equals weight x (value - baseline). The values always add up to prediction minus baseline."}


tool(T, "shapley_linear", "Exact Shapley values (linear model)", "Explain one prediction feature by feature.", [("weights", "Lines of: feature, weight", "age,0.5\nincome,0.2\nvisits,1.5", "area"), ("instance", "Feature values to explain (comma)", "40,60,3"), ("baseline", "Baseline values (comma)", "35,50,2")], shap)


def hpo(a):
    t, secs, par = num(a, "trials", lo=1), num(a, "seconds_per_trial", lo=0), int(num(a, "parallel", lo=1))
    folds, space = int(num(a, "cv_folds", lo=1)), num(a, "grid_points", lo=1)
    total = t * secs * folds
    wall = total / par
    return {"total_compute_hours": r(total / 3600, 2), "wall_clock_hours": r(wall / 3600, 2), "grid_search_trials": int(space), "random_search_trials_to_hit_top_5pct_with_95pct_chance": 59, "grid_hours_if_exhaustive": r(space * secs * folds / par / 3600, 2),
            "tips": ["Random search beats a grid when only a few parameters matter: 59 random trials give a 95% chance to land in the best 5%.", "Use early stopping (successive halving) to drop weak trials.", "Tune on a validation set, report on a untouched test set."]}


tool(T, "tuning_budget", "Tuning budget", "Compute time for a search.", [("trials", "Trials", 60), ("seconds_per_trial", "Seconds per training run", 120), ("cv_folds", "Cross-validation folds", 5), ("parallel", "Runs in parallel", 4), ("grid_points", "Points in a full grid", 1500)], hpo)


def recommender(a):
    rows = lines(a, "ratings", "the ratings", 3)
    data: dict[str, dict[str, float]] = {}
    for p in rows:
        if len(p) < 3:
            raise ProError("Each line: user, item, rating.")
        data.setdefault(p[0], {})[p[1]] = float(p[2])
    user = txt(a, "user")
    if user not in data:
        raise ProError("That user is not in the ratings.")
    items = {i for d in data.values() for i in d}

    def vec(i):
        return {u: d[i] for u, d in data.items() if i in d}

    def cos(i, j):
        x, y = vec(i), vec(j)
        com = set(x) & set(y)
        if not com:
            return 0.0
        n = sum(x[u] * y[u] for u in com)
        return n / (math.sqrt(sum(x[u] ** 2 for u in com)) * math.sqrt(sum(y[u] ** 2 for u in com)))
    seen = data[user]
    recs = []
    for it in sorted(items - set(seen)):
        num_, den = 0.0, 0.0
        for j, rt in seen.items():
            s = cos(it, j)
            num_ += s * rt
            den += abs(s)
        if den:
            recs.append({"item": it, "predicted_rating": r(num_ / den, 2)})
    recs.sort(key=lambda x: -x["predicted_rating"])
    return {"user": user, "already_rated": len(seen), "recommendations": recs[:5] or ["Not enough overlap to recommend."], "limits": ["Cold start: new users and items have no ratings yet.", "Tiny data gives noisy neighbours: use real volumes before trusting it.", "Popular items get recommended to everyone: measure diversity too."], "how": "Item-based collaborative filtering: items rated alike by the same people are similar (cosine similarity); predict a rating as the similarity-weighted average of the user's own ratings."}


tool(T, "item_recommender", "Item-based recommender", "Predict what a user would like from ratings.", [("user", "User to recommend for", "ana"), ("ratings", "Lines of: user, item, rating", "ana,coffee,5\nana,tea,2\nbo,coffee,4\nbo,tea,1\nbo,cocoa,5\ncy,tea,5\ncy,cocoa,2\ncy,juice,4\ndee,coffee,5\ndee,juice,2\ndee,cocoa,4", "area")], recommender)


def tsmetrics(a):
    act = [float(x) for x in txt(a, "actual").split(",")]
    fc = [float(x) for x in txt(a, "forecast").split(",")]
    if len(act) != len(fc) or len(act) < 3:
        raise ProError("Give the same number of actual and forecast values (at least 3).")
    season = int(num(a, "season", lo=1))
    hist = [float(x) for x in txt(a, "history", required=False).split(",")] if txt(a, "history", required=False) else act
    e = [x - y for x, y in zip(act, fc)]
    rmse = math.sqrt(sum(v * v for v in e) / len(e))
    mae = sum(abs(v) for v in e) / len(e)
    smape = 100 * sum(2 * abs(v) / (abs(x) + abs(y)) if (abs(x) + abs(y)) else 0 for v, x, y in zip(e, act, fc)) / len(e)
    if len(hist) <= season:
        raise ProError("History must be longer than the season length.")
    naive = sum(abs(hist[i] - hist[i - season]) for i in range(season, len(hist))) / (len(hist) - season)
    mase = mae / naive if naive else None
    return {"rmse": r(rmse, 3), "mae": r(mae, 3), "smape_pct": r(smape, 2), "mase": r(mase, 3) if mase is not None else None, "bias": r(sum(e) / len(e), 3),
            "verdict": "Beats the naive seasonal forecast." if mase is not None and mase < 1 else "Not better than repeating last season: simplify or fix the model.", "how": "MASE divides your error by the error of the naive seasonal forecast, so under 1 means you add value. sMAPE is a percentage that handles zeros better than MAPE."}


tool(T, "forecast_metrics", "Forecast accuracy (MASE, sMAPE, RMSE)", "Score a forecast fairly.", [("actual", "Actual values (comma)", "102,98,110,120,115,130"), ("forecast", "Forecast values (comma)", "100,101,108,118,121,126"), ("history", "Earlier history for the naive baseline (comma, optional)", "90,95,92,97,100,99,104,101"), ("season", "Season length (1 = previous value)", 1)], tsmetrics)


def psi(a):
    exp = [float(x) for x in txt(a, "expected").split(",")]
    act = [float(x) for x in txt(a, "actual").split(",")]
    if len(exp) != len(act) or len(exp) < 2:
        raise ProError("Give matching bucket shares for expected and actual.")
    te, ta = sum(exp), sum(act)
    pe, pa = [max(x / te, 1e-4) for x in exp], [max(x / ta, 1e-4) for x in act]
    parts = [(a_ - e) * math.log(a_ / e) for e, a_ in zip(pe, pa)]
    v = sum(parts)
    return {"psi": r(v, 4), "verdict": "No meaningful shift." if v < 0.1 else "Moderate shift: investigate." if v < 0.25 else "Large shift: retrain or fix the data.", "biggest_bucket": int(max(range(len(parts)), key=lambda i: parts[i])) + 1,
            "how": "Population stability index compares the share in each bucket now versus at training. Under 0.1 stable, 0.1 to 0.25 watch, over 0.25 act. Check input drift and the prediction outcomes."}


tool(T, "drift_psi", "Drift (PSI)", "Has the data changed since training?", [("expected", "Training bucket counts or shares (comma)", "30,40,20,10"), ("actual", "Live bucket counts or shares (comma)", "20,35,25,20")], psi)


def serving(a):
    rps, ms, workers = num(a, "peak_requests_per_s", lo=0), num(a, "latency_ms", lo=0, strict=True), int(num(a, "concurrency_per_replica", lo=1))
    target = num(a, "target_utilization_pct", lo=10, hi=100) / 100
    per = workers * 1000 / ms
    need = math.ceil(rps / (per * target))
    gpu_hr = num(a, "cost_per_replica_hour", lo=0)
    return {"capacity_per_replica_rps": r(per, 1), "replicas_needed": need, "monthly_cost": r(need * gpu_hr * 730, 0), "tips": ["Batch requests when latency allows: throughput rises sharply.", "Scale on queue depth or latency, not CPU alone.", "Keep one spare replica for a failure or deploy.", "Load-test with real input sizes."]}


tool(T, "serving_capacity", "Model serving capacity", "Replicas and monthly cost for a peak load.", [("peak_requests_per_s", "Peak requests per second", 120), ("latency_ms", "Latency per request (ms)", 80), ("concurrency_per_replica", "Parallel requests per replica", 4), ("target_utilization_pct", "Target utilization (%)", 60), ("cost_per_replica_hour", "Cost per replica-hour", 1.2)], serving)


def bandit(a):
    rates = [float(x) for x in txt(a, "true_rates", "the true rates").split(",")]
    n, eps, seed = int(num(a, "pulls", lo=10, hi=200000)), num(a, "epsilon", lo=0, hi=1), int(num(a, "seed", lo=0))
    if len(rates) < 2 or any(not 0 <= x <= 1 for x in rates):
        raise ProError("Give two or more rates between 0 and 1.")
    rnd = random.Random(seed)
    k = len(rates)
    best = max(rates)

    def run(policy):
        cnt, win, reg = [0] * k, [0] * k, 0.0
        for t in range(1, n + 1):
            if policy == "eps":
                i = rnd.randrange(k) if rnd.random() < eps or 0 in cnt else max(range(k), key=lambda j: win[j] / cnt[j])
            elif policy == "ucb":
                i = cnt.index(0) if 0 in cnt else max(range(k), key=lambda j: win[j] / cnt[j] + math.sqrt(2 * math.log(t) / cnt[j]))
            elif policy == "thompson":
                i = max(range(k), key=lambda j: rnd.betavariate(win[j] + 1, cnt[j] - win[j] + 1))
            else:
                i = rnd.randrange(k)
            cnt[i] += 1
            win[i] += rnd.random() < rates[i]
            reg += best - rates[i]
        return {"policy": policy, "regret": r(reg, 1), "best_arm_share_pct": r(100 * cnt[rates.index(best)] / n, 1)}
    res = [run(p) for p in ("random", "eps", "ucb", "thompson")]
    return {"pulls": n, "results": res, "how": "Regret is the reward lost by not always pulling the best option. Random split (a plain A/B test) keeps losing; bandits shift traffic to the winner as evidence builds.", "tips": ["Bandits suit many options and quick feedback; a fixed A/B test is cleaner for one clear decision.", "Seeded: the same seed gives the same run."]}


tool(T, "bandit_sim", "Bandit regret simulation", "Compare exploration policies.", [("true_rates", "True success rates (comma)", "0.04,0.05,0.07"), ("pulls", "Pulls", 5000), ("epsilon", "Epsilon (random share)", 0.1), ("seed", "Seed", 3)], bandit)

ref(T, "tracking", "Experiment tracking", [
    {"title": "Record every run", "items": ["Code version (git commit), data version or hash, parameters, random seed.", "Metrics on training, validation and the untouched test set.", "Environment: library versions and hardware.", "The model file and the plots; a one-line note about why you tried it."]},
    {"title": "Habits", "items": ["Change one thing at a time.", "Compare against a simple baseline before anything fancy.", "Never tune on the test set; look at it once.", "A result you cannot reproduce is not a result."]}])
