"""Inference Lab: back-of-envelope calculators for running AI models, from Philip Kiely's "Inference Engineering" (Baseten Books, 2026).

What is built: arithmetic you can check by hand (model memory, compute vs memory bottleneck, latency percentiles, cost,
speculative-decoding speedup, replica counts). What is not: this app does not run GPUs, inference engines or load tests.

Honest limits
* Every result is a ceiling or an estimate from peak specs. Real systems fall short of peak; measure before you decide.
* GPU figures are the ones printed in the book (dense FP8 compute, memory and bandwidth). FP16 compute is taken as half of FP8
  (the book says FP8 Tensor Cores are twice as fast); FP4 as double, on Blackwell only. Prices are never hard-coded.
* The KV cache formula and the speculative-decoding speedup formula are the standard textbook ones, not copied from the book.
"""
from __future__ import annotations

import math
import re

MAX_SAMPLES = 100_000


class InfError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


# id -> label, VRAM GB, bandwidth GB/s, dense FP8 TFLOPS (None when the book gives no figure), blackwell?, note
GPUS = {
    "h100": ("NVIDIA H100", 80, 3350, 1979, False, "Hopper. Among the most widely used inference GPUs."),
    "h200": ("NVIDIA H200", 141, 4800, 1979, False, "Hopper with more memory and bandwidth: better for decode."),
    "b200": ("NVIDIA B200", 192, 8000, 5000, True, "Blackwell. About 5 petaFLOPS FP8 and up to 8 TB/s."),
    "b300": ("NVIDIA B300", 288, 8000, 5000, True, "Blackwell with 288 GB."),
    "l4": ("NVIDIA L4", 24, 300, 242, False, "Lovelace. Cheap for small models; no NVLink."),
    "l40": ("NVIDIA L40", 48, 864, 362, False, "Lovelace. The book generally advises against it for inference."),
    "rtx5090": ("NVIDIA RTX 5090 (desktop)", 32, 1792, None, False, "Consumer card. The book gives memory and bandwidth only."),
    "m3ultra": ("Apple M3 Ultra (desktop)", 512, 819, None, False, "Unified memory: large capacity, lower bandwidth. The book gives memory and bandwidth only."),
}
# bytes per parameter, and compute speed relative to dense FP8
PRECISIONS = {
    "fp32": ("FP32", 4.0, None, "Almost never used for inference."),
    "bf16": ("BF16", 2.0, 0.5, "Common native format."),
    "fp16": ("FP16", 2.0, 0.5, "Common native format."),
    "fp8": ("FP8", 1.0, 1.0, "Hopper and later. About 1 GB per billion parameters."),
    "int8": ("INT8", 1.0, 1.0, "Integer formats have less dynamic range than floating point."),
    "fp4": ("FP4", 0.5, 2.0, "Blackwell only."),
    "int4": ("INT4", 0.5, 0.5, "Treated as weight-only here: values are computed at 16-bit speed."),
}
FORMATS = [  # name, abbreviation, first architecture (book 5.1.1)
    ("64-bit floating point", "FP64", "Fermi (2010)"), ("32-bit floating point", "FP32", "Kepler (2012)"),
    ("16-bit floating point", "FP16", "Pascal (2016)"), ("Brain floating point 16", "BF16", "Ampere (2020)"),
    ("8-bit floating point", "FP8", "Hopper (2022)"), ("Mixed-precision FP8", "MXFP8", "Blackwell (2024)"),
    ("8-bit integer", "INT8", "Pascal (2016)"), ("6-bit floating point", "FP6", "Blackwell (2024, experimental)"),
    ("4-bit floating point", "FP4", "Blackwell (2024)"), ("Mixed-precision FP4", "MXFP4", "Blackwell (2024)"),
    ("NVIDIA FP4", "NVFP4", "Blackwell (2024, proprietary)"), ("4-bit integer", "INT4", "Turing (2018)"),
]


def _num(v, name: str, lo: float, hi: float, required: bool = True):
    if v in (None, ""):
        if required:
            raise InfError(f"Enter {name}.")
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise InfError(f"{name[0].upper() + name[1:]} must be a number.") from None
    if not (lo <= f <= hi) or f != f:
        raise InfError(f"{name[0].upper() + name[1:]} must be between {lo:g} and {hi:g}.")
    return f


def catalog() -> dict:
    return {"gpus": [{"id": k, "label": v[0], "vram_gb": v[1], "bandwidth_gbs": v[2], "fp8_tflops": v[3], "note": v[5]} for k, v in GPUS.items()],
            "precisions": [{"id": k, "label": v[0], "bytes": v[1], "note": v[3]} for k, v in PRECISIONS.items()],
            "formats": [{"name": a, "abbr": b, "first": c} for a, b, c in FORMATS],
            "source": "Inference Engineering by Philip Kiely (Baseten Books, 2026). GPU figures as printed in the book."}


def _gpu(gpu: str | None, custom: dict | None) -> dict:
    if gpu == "custom":
        c = custom or {}
        vram = _num(c.get("vram_gb"), "VRAM in GB", 1, 100000)
        bw = _num(c.get("bandwidth_gbs"), "memory bandwidth in GB/s", 1, 1000000)
        tf = _num(c.get("fp8_tflops"), "FP8 teraFLOPS", 0.1, 1000000, required=False)
        return {"id": "custom", "label": "Your hardware", "vram_gb": vram, "bandwidth_gbs": bw, "fp8_tflops": tf, "blackwell": False}
    if gpu not in GPUS:
        raise InfError(f"Pick a GPU: {', '.join(GPUS)} or custom.")
    g = GPUS[gpu]
    return {"id": gpu, "label": g[0], "vram_gb": g[1], "bandwidth_gbs": g[2], "fp8_tflops": g[3], "blackwell": g[4]}


def _prec(p: str) -> tuple[str, float, float | None, str]:
    if p not in PRECISIONS:
        raise InfError(f"Pick a precision: {', '.join(PRECISIONS)}.")
    return PRECISIONS[p]


def _tflops(g: dict, precision: str) -> float | None:
    mult = _prec(precision)[2]
    if g["fp8_tflops"] is None or mult is None:
        return None
    if precision == "fp4" and not g["blackwell"]:
        raise InfError("FP4 Tensor Cores need a Blackwell GPU (B200 or B300). Pick FP8 or higher on this hardware.")
    return g["fp8_tflops"] * mult


def _kv_per_token_bytes(layers, kv_heads, head_dim, kv_bytes) -> float:
    return 2 * layers * kv_heads * head_dim * kv_bytes  # K and V


# ------------------------------------------------------------------ memory fit
def fit(params_b, precision: str, gpu: str, n_gpus=1, custom: dict | None = None, layers=None, kv_heads=None, head_dim=None,
        context=None, batch=1, kv_precision: str | None = None) -> dict:
    p = _num(params_b, "model size in billions of parameters", 0.01, 20000)
    n = int(_num(n_gpus, "number of GPUs", 1, 1024))
    g = _gpu(gpu, custom)
    label, bpp, _, _ = _prec(precision)
    weights = p * bpp
    total = g["vram_gb"] * n
    rule = weights * 1.5
    need = max(1, math.ceil(rule / g["vram_gb"]))
    out = {"gpu": g["label"], "gpus": n, "total_vram_gb": round(total, 1), "weights_gb": round(weights, 1), "precision": label,
           "book_rule_gb": round(rule, 1), "fits_book_rule": rule <= total, "min_gpus_by_rule": need,
           "headroom_gb": round(total - weights, 1),
           "lesson": "Weights take about one gigabyte per billion parameters at 8 bits. The book's rule: the VRAM should hold the weights plus at least 50 percent headroom for the KV cache, and more for long context or big batches. Weights that barely fit leave no room for the KV cache.",
           "kv": None, "warnings": []}
    if weights > total:
        out["warnings"].append("The weights alone do not fit: loading would fail with an out-of-memory error.")
    elif rule > total:
        out["warnings"].append("The weights fit but there is less than 50 percent headroom, so expect little room for the KV cache.")
    if n > 1:
        out["warnings"].append("More than one GPU needs model parallelism, and the link between GPUs matters (NVLink on Hopper and Blackwell; Lovelace has none).")
    if layers not in (None, "") or kv_heads not in (None, ""):
        L = _num(layers, "number of layers", 1, 1000)
        kh = _num(kv_heads, "number of KV heads", 1, 1000)
        hd = _num(head_dim, "head dimension", 1, 4096)
        ctx = _num(context, "context length in tokens", 1, 10_000_000)
        b = int(_num(batch, "batch size", 1, 100000))
        kvp = kv_precision or precision
        kbpp = _prec(kvp)[1]
        per_tok = _kv_per_token_bytes(L, kh, hd, kbpp)
        per_seq = per_tok * ctx / 1e9
        total_kv = per_seq * b
        usable = total * 0.9 - weights
        out["kv"] = {"per_token_kb": round(per_tok / 1024, 1), "per_sequence_gb": round(per_seq, 2), "total_gb": round(total_kv, 2),
                     "fits": weights + total_kv <= total * 0.9, "max_batch": max(0, int(usable // per_seq)) if per_seq > 0 else 0,
                     "assumption": "Reserves 10 percent of VRAM for activations and overhead (an assumption). KV cache = 2 x layers x KV heads x head dim x bytes x tokens x batch."}
        if not out["kv"]["fits"]:
            out["warnings"].append(f"At batch {b} and {int(ctx):,} tokens the KV cache does not fit; the most that fits is batch {out['kv']['max_batch']}.")
    return out


# ------------------------------------------------------------------ bottleneck
def bottleneck(params_b, precision: str, gpu: str, custom: dict | None = None, input_tokens=1000, batch=1, active_params_b=None,
               n_gpus=1) -> dict:
    p = _num(params_b, "model size in billions of parameters", 0.01, 20000)
    act = _num(active_params_b, "active parameters in billions", 0.01, 20000, required=False) or p
    n = int(_num(n_gpus, "number of GPUs", 1, 1024))
    b = int(_num(batch, "batch size", 1, 100000))
    t_in = _num(input_tokens, "input tokens", 1, 10_000_000)
    g = _gpu(gpu, custom)
    label, bpp, _, _ = _prec(precision)
    tf = _tflops(g, precision)
    bw = g["bandwidth_gbs"] * n          # GB/s across GPUs (ideal scaling)
    weights_gb = p * bpp
    flops = tf * 1e12 * n if tf else None
    out = {"gpu": g["label"], "precision": label, "weights_gb": round(weights_gb, 1), "ops_per_byte": None, "decode": {}, "prefill": {}, "warnings": [],
           "lesson": "Prefill reads the weights once and does a lot of arithmetic, so it is compute-bound and sets TTFT. Decode reloads the weights for every token and does little arithmetic per byte, so it is memory-bound and sets tokens per second. Batching makes decode less memory-bound because more work shares the same memory traffic.",
           "caveat": "These are ceilings from peak specs, assuming perfect scaling across GPUs. Real systems are slower: measure."}
    mem_step_s = weights_gb / bw                     # one decode step reads all weights
    d = {"memory_time_ms": round(mem_step_s * 1000, 2)}
    if flops:
        out["ops_per_byte"] = round(flops / (bw * 1e9), 1)
        comp_step_s = 2 * act * 1e9 * b / flops
        step = max(mem_step_s, comp_step_s)
        d.update({"compute_time_ms": round(comp_step_s * 1000, 3), "bound": "memory" if mem_step_s >= comp_step_s else "compute",
                  "balanced_batch": max(1, round(out["ops_per_byte"] * bpp / 2))})
    else:
        step = mem_step_s
        d.update({"compute_time_ms": None, "bound": "memory (compute speed not given for this hardware)", "balanced_batch": None})
        out["warnings"].append("No compute figure for this hardware, so only the memory-bandwidth limit is shown.")
    d.update({"tps_per_user_max": round(1 / step, 1), "total_tps_max": round(b / step, 1), "itl_ms_min": round(step * 1000, 2)})
    out["decode"] = d
    pre = {"memory_time_ms": round(mem_step_s * 1000, 2)}
    if flops:
        pc = 2 * act * 1e9 * t_in / flops
        pre.update({"compute_time_ms": round(pc * 1000, 1), "ttft_ms_min": round(max(pc, mem_step_s) * 1000, 1),
                    "bound": "compute" if pc >= mem_step_s else "memory"})
    else:
        pre.update({"compute_time_ms": None, "ttft_ms_min": None, "bound": "unknown"})
    pre["note"] = "Uses 2 x parameters x input tokens. The attention term that grows with the square of the length is left out, so long prompts take longer."
    out["prefill"] = pre
    if act != p:
        out["warnings"].append("Mixture-of-experts: compute uses the active parameters; the memory time conservatively reads all weights, which is realistic at larger batches.")
    return out


# ------------------------------------------------------------------ latency stats
def _pct(sorted_vals: list[float], q: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = (len(sorted_vals) - 1) * q / 100
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def _summ(vals: list[float]) -> dict:
    s = sorted(vals)
    mean = sum(s) / len(s)
    p50 = _pct(s, 50)
    return {"n": len(s), "mean": round(mean, 2), "p50": round(p50, 2), "p90": round(_pct(s, 90), 2), "p95": round(_pct(s, 95), 2),
            "p99": round(_pct(s, 99), 2), "max": round(s[-1], 2), "mean_over_p50": round(mean / p50, 2) if p50 else None}


def parse_samples(text: str) -> dict:
    """Read pasted rows: columns ttft_ms, total_ms, output_tokens (a header row names them; otherwise that order)."""
    rows = [r for r in (text or "").replace("\r", "").split("\n") if r.strip()]
    if not rows:
        raise InfError("Paste at least one row of measurements.")
    if len(rows) > MAX_SAMPLES:
        raise InfError(f"Up to {MAX_SAMPLES:,} rows.")
    split = lambda r: [c.strip() for c in re.split(r"[,\t;]", r)]  # noqa: E731
    first = split(rows[0])
    names = ["ttft_ms", "total_ms", "output_tokens"]
    header = any(re.search(r"[A-Za-z]", c) for c in first)
    idx = {n: i for i, n in enumerate(names)}
    if header:
        idx = {}
        for i, c in enumerate(first):
            k = c.lower()
            if "ttft" in k or "first" in k:
                idx["ttft_ms"] = i
            elif "total" in k or "latency" in k or "duration" in k:
                idx["total_ms"] = i
            elif "token" in k:
                idx["output_tokens"] = i
        rows = rows[1:]
        if not idx:
            raise InfError("Name at least one column ttft_ms, total_ms or output_tokens, or paste numbers with no header.")
    cols: dict[str, list[float]] = {k: [] for k in idx}
    for ln, r in enumerate(rows, 1 + (1 if header else 0)):
        cells = split(r)
        for k, i in idx.items():
            if i >= len(cells) or cells[i] == "":
                continue
            try:
                v = float(cells[i])
            except ValueError:
                raise InfError(f"Row {ln}: '{cells[i]}' is not a number.") from None
            if v < 0 or v != v:
                raise InfError(f"Row {ln}: values can't be negative.")
            cols[k].append(v)
    return {k: v for k, v in cols.items() if v}


def latency_stats(text: str | None = None, ttft_ms=None, total_ms=None, output_tokens=None, duration_s=None) -> dict:
    cols = parse_samples(text) if text else {k: [float(x) for x in v] for k, v in (("ttft_ms", ttft_ms), ("total_ms", total_ms), ("output_tokens", output_tokens)) if v}
    if not cols:
        raise InfError("Give at least one column of measurements.")
    out = {"metrics": {}, "warnings": [], "lesson": "Averages hide the slow requests. Latency is right-skewed, so the mean sits above the median; look at P90, P95 and P99, because one slow request in ten or twenty is what users remember."}
    for k, v in cols.items():
        out["metrics"][k] = _summ(v)
    n = min(len(v) for v in cols.values())
    if n < 100:
        out["warnings"].append(f"Only {n} requests: P99 needs about 100 or more to mean much, and P95 about 20 or more.")
    if "ttft_ms" in cols and "total_ms" in cols and len(cols["ttft_ms"]) != len(cols["total_ms"]):
        out["warnings"].append("TTFT and total time have different row counts, so per-request speed was skipped.")
    elif "ttft_ms" in cols and "total_ms" in cols and "output_tokens" in cols and len(cols["output_tokens"]) == len(cols["ttft_ms"]):
        tps, itl = [], []
        for t1, tt, tok in zip(cols["ttft_ms"], cols["total_ms"], cols["output_tokens"]):
            dt = (tt - t1) / 1000
            if dt > 0 and tok > 1:
                tps.append((tok - 1) / dt)
                itl.append(dt * 1000 / (tok - 1))
        if tps:
            out["metrics"]["perceived_tps"] = _summ(tps)
            out["metrics"]["itl_ms"] = _summ(itl)
            out["lesson"] += " Perceived TPS is tokens per second per user after the first token; inter-token latency (ITL) is its inverse (10 ms is 100 tokens per second)."
    if duration_s not in (None, "") and "output_tokens" in cols:
        d = _num(duration_s, "test duration in seconds", 0.001, 10_000_000)
        out["total_tps"] = round(sum(cols["output_tokens"]) / d, 1)
        out["requests_per_s"] = round(len(cols["output_tokens"]) / d, 3)
    return out


# ------------------------------------------------------------------ cost
def cost(input_m, output_m, price_in, price_out, gpus=1, gpu_hour=0, hours=730, total_tps=None, utilization_pct=50, eng_hours=0, eng_rate=0) -> dict:
    mi = _num(input_m, "monthly input tokens (millions)", 0, 1e9)
    mo = _num(output_m, "monthly output tokens (millions)", 0, 1e9)
    pi = _num(price_in, "API price per million input tokens", 0, 100000)
    po = _num(price_out, "API price per million output tokens", 0, 100000)
    n = int(_num(gpus, "number of GPUs", 1, 100000))
    rate = _num(gpu_hour, "GPU price per hour", 0, 100000)
    hrs = _num(hours, "hours per month", 1, 744)
    util = _num(utilization_pct, "utilization percent", 1, 100)
    eh = _num(eng_hours, "engineering hours per month", 0, 100000)
    er = _num(eng_rate, "engineering hourly cost", 0, 100000)
    api = mi * pi + mo * po
    gpu_cost = n * rate * hrs
    tco = gpu_cost + eh * er
    out = {"api_monthly": round(api, 2), "gpu_monthly": round(gpu_cost, 2), "engineering_monthly": round(eh * er, 2), "dedicated_monthly": round(tco, 2),
           "cheaper": "dedicated" if tco < api else "api", "difference": round(abs(api - tco), 2), "warnings": [],
           "lesson": "API cost is linear in tokens. A dedicated deployment is mostly a fixed monthly cost, so it wins only when traffic keeps the GPUs busy, and the engineering time to run it belongs in the total. Compare totals over a week or more, not per-token guesses."}
    tot_m = mi + mo
    if tot_m > 0 and api > 0:
        blended = api / tot_m
        out["api_blended_per_m"] = round(blended, 4)
        out["break_even_tokens_m"] = round(tco / blended, 1)
    if total_tps not in (None, ""):
        tps = _num(total_tps, "measured total tokens per second", 0.001, 1e9)
        cap_m = tps * n * 3600 * hrs * util / 100 / 1e6   # capacity counts only output tokens
        out["capacity_output_m"] = round(cap_m, 1)
        out["dedicated_per_m_output"] = round(tco / cap_m, 4) if cap_m else None
        if mo > cap_m:
            out["warnings"].append(f"Your {mo:,.0f}M output tokens a month is more than the {cap_m:,.0f}M this deployment can produce at {util:g}% utilization: you would need more GPUs.")
        out["tps_note"] = "Capacity assumes the measured total tokens per second per GPU and counts output tokens only."
    if rate == 0:
        out["warnings"].append("Enter your GPU price per hour: prices change often, so none is built in.")
    return out


# ------------------------------------------------------------------ speculative decoding
def speculative(acceptance, draft_len=4, draft_cost=0.1) -> dict:
    a = _num(acceptance, "token acceptance rate (0 to 1)", 0, 1)
    g = int(_num(draft_len, "draft length", 1, 32))
    c = _num(draft_cost, "draft cost relative to one target step (0 to 1)", 0, 1)
    def exp_tokens(al, gm):
        return gm + 1 if al >= 1 else (1 - al ** (gm + 1)) / (1 - al)
    rows = []
    for gm in range(1, 17):
        e = exp_tokens(a, gm)
        rows.append({"draft_len": gm, "tokens_per_step": round(e, 2), "speedup": round(e / (1 + gm * c), 2)})
    best = max(rows, key=lambda r: r["speedup"])
    cur = next(r for r in rows if r["draft_len"] == g) if g <= 16 else {"draft_len": g, "tokens_per_step": round(exp_tokens(a, g), 2), "speedup": round(exp_tokens(a, g) / (1 + g * c), 2)}
    return {"current": cur, "best": best, "table": rows,
            "lesson": "A step drafts some tokens cheaply, then the target model checks them all at once and keeps the ones that are right plus one more. Each step yields (1 - a^(k+1)) / (1 - a) tokens for acceptance rate a and k drafts, and costs about 1 + k x (draft cost) target steps.",
            "caution": "This assumes every draft token is accepted with the same chance. The book notes acceptance falls along the draft and with higher temperature, so real gains are smaller. Measure on your own traffic. Draft-target speculation also needs a draft model about ten times smaller than the target."}


# ------------------------------------------------------------------ scaling
def scaling(requests_per_s, avg_latency_s, concurrency_target, target_pct=70, spike=1, cold_start_s=0) -> dict:
    r = _num(requests_per_s, "requests per second", 0.001, 1e7)
    lat = _num(avg_latency_s, "average request time in seconds", 0.001, 100000)
    conc = _num(concurrency_target, "concurrent requests one replica can serve", 1, 100000)
    tp = _num(target_pct, "target utilization percent", 10, 100)
    sp = _num(spike, "traffic spike multiplier", 1, 1000)
    cs = _num(cold_start_s, "cold start in seconds", 0, 100000)
    inflight = r * lat
    per = conc * tp / 100
    base = max(1, math.ceil(inflight / per))
    peak = max(1, math.ceil(inflight * sp / per))
    queued = (sp - 1) * r * cs if peak > base else 0
    out = {"in_flight": round(inflight, 1), "replicas": base, "replicas_at_spike": peak, "requests_waiting_during_cold_start": round(queued),
           "lesson": "By Little's law, requests in flight equal arrival rate times time per request. Divide by the concurrency one replica can handle, run replicas below full so a burst has room, and remember new replicas take a cold start to become ready.",
           "warnings": []}
    if cs and peak > base:
        out["warnings"].append(f"During a {sp:g}x spike about {round(queued):,} extra requests arrive while new replicas start. Keep spare replicas or a minimum replica count if that is too slow.")
    if conc < 2:
        out["warnings"].append("Concurrency of 1 means no batching, which wastes GPU throughput: test several batch sizes.")
    return out


# ------------------------------------------------------------------ quantization table
def quant_table(params_b) -> dict:
    p = _num(params_b, "model size in billions of parameters", 0.01, 20000)
    rows = [{"precision": v[0], "bytes": v[1], "weights_gb": round(p * v[1], 1), "note": v[3]} for k, v in PRECISIONS.items()]
    return {"rows": rows,
            "lesson": "Halving precision halves the weight memory and makes both phases faster, but the overhead of working with quantized data means going down one level usually gains about 30 to 50 percent, not double.",
            "quality": ["Perplexity: compare the quantized and original model; look for a minimal increase.", "A public benchmark such as MMLU: look for a minimal drop.",
                        "Your own evals on your own task: the best check.", "Quantization is a scale, not a switch: FP8 is lower risk than FP4, and weights-only is lower risk than quantizing everything."]}
