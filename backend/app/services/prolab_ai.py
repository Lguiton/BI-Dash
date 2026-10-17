"""AI engineering depth: fine-tune memory, vector search sizing, retrieval metrics, chunking, quantization, KV cache, cost, evals."""
from __future__ import annotations

import math

from app.services.prolab import ProError, lab, lines, num, r, ref, tool, txt

T = "ai"
lab(T, "AI engineering depth: fine-tuning, retrieval, serving, cost and evaluation maths")

_BYTES = {"fp32": 4, "fp16": 2, "bf16": 2, "int8": 1, "int4": 0.5}


def lora(a):
    n, prec = num(a, "params_b", lo=0, strict=True) * 1e9, txt(a, "precision").lower()
    if prec not in _BYTES:
        raise ProError("Precision must be fp32, fp16, bf16, int8 or int4.")
    d, layers, rank, tgt = int(num(a, "hidden", lo=1)), int(num(a, "layers", lo=1)), int(num(a, "rank", lo=1)), int(num(a, "target_matrices_per_layer", lo=1))
    lora_p = layers * tgt * 2 * d * rank
    base = n * _BYTES[prec] / 1e9
    train = lora_p * (2 + 4 + 8) / 1e9      # fp16 weights + fp32 master + Adam states
    full = n * 16 / 1e9
    return {"trainable_lora_params_m": r(lora_p / 1e6, 2), "trainable_pct": r(100 * lora_p / n, 3), "base_model_gb": r(base, 1), "lora_training_state_gb": r(train, 2), "gpu_memory_estimate_gb": r(base + train * 1.0 + 0.2 * base, 1), "full_fine_tune_gb_adam": r(full, 0),
            "tips": ["Add activations: they scale with batch size and sequence length; gradient checkpointing trades speed for memory.", "Higher rank adds capacity and cost; 8 to 64 is usual.", "QLoRA keeps the base in 4-bit: far less memory, slightly slower.", "Full fine-tuning with Adam needs about 16 bytes per parameter."]}


tool(T, "lora_memory", "LoRA memory and parameters", "Trainable parameters and GPU memory for LoRA.", [("params_b", "Model size (billions of parameters)", 7), ("precision", "Base precision: fp32, fp16, bf16, int8, int4", "fp16"), ("hidden", "Hidden size", 4096), ("layers", "Layers", 32), ("rank", "LoRA rank", 16), ("target_matrices_per_layer", "LoRA matrices per layer (attention q,k,v,o = 4)", 4)], lora)


def vdb(a):
    n, dim, prec, m = num(a, "vectors", lo=1), int(num(a, "dims", lo=1)), txt(a, "precision").lower(), int(num(a, "hnsw_m", lo=4))
    if prec not in _BYTES:
        raise ProError("Precision must be fp32, fp16, bf16, int8 or int4.")
    raw = n * dim * _BYTES[prec]
    graph = n * m * 2 * 4 * 1.1
    meta = n * float(a.get("metadata_bytes", 200) or 200)
    tot = (raw + graph + meta)
    return {"vectors_gb": r(raw / 1e9, 2), "hnsw_graph_gb": r(graph / 1e9, 2), "metadata_gb": r(meta / 1e9, 2), "total_ram_gb": r(tot / 1e9, 2), "with_replica_gb": r(2 * tot / 1e9, 2),
            "tips": ["HNSW wants the index in RAM for speed; disk indexes (DiskANN) trade latency for size.", "Quantizing vectors to int8 cuts raw size 4 times with a small recall loss: measure recall.", "Smaller embedding dimensions (or truncation, where the model supports it) cut cost directly."]}


tool(T, "vector_db_size", "Vector database sizing", "Memory for an HNSW index.", [("vectors", "Number of vectors", 5000000), ("dims", "Dimensions", 1024), ("precision", "Stored precision", "fp32"), ("hnsw_m", "HNSW M (links per node)", 16), ("metadata_bytes", "Metadata per vector (bytes)", 200)], vdb)


def retrieval(a):
    k = int(num(a, "k", lo=1))
    rec, mrr, prec, hit = [], [], [], 0
    for ln in txt(a, "queries").splitlines():
        if not ln.strip() or ln.strip().startswith("#"):
            continue
        if "|" not in ln:
            raise ProError("Each line: relevant ids | returned ids in rank order (space separated).")
        left, right = ln.split("|", 1)
        rel, got = set(left.split()), right.split()
        if not rel:
            continue
        top = got[:k]
        found = [x for x in top if x in rel]
        rec.append(len(set(found)) / len(rel))
        prec.append(len(found) / k)
        hit += 1 if found else 0
        rr = 0.0
        for i, x in enumerate(got, 1):
            if x in rel:
                rr = 1 / i
                break
        mrr.append(rr)
    if not rec:
        raise ProError("No usable lines.")
    n = len(rec)
    return {"queries": n, f"recall_at_{k}": r(sum(rec) / n, 3), f"precision_at_{k}": r(sum(prec) / n, 3), f"hit_rate_at_{k}": r(hit / n, 3), "mrr": r(sum(mrr) / n, 3),
            "tips": ["Recall at k is the ceiling for the answer quality: the model cannot use what was not retrieved.", "Low recall: improve chunking, add a keyword (hybrid) search, or re-rank a wider top-k.", "Build a labeled set from real questions; 50 to 100 beats guessing."]}


tool(T, "retrieval_metrics", "Retrieval metrics", "Recall, precision, hit rate and MRR from a labeled set.", [("k", "k (how many results are used)", 3), ("queries", "Lines of: relevant ids | returned ids in order", "d1 d4 | d2 d1 d9 d4\nd3 | d3 d5 d6\nd7 | d1 d2 d3 d4 d5", "area")], retrieval)


def chunking(a):
    words, ctx_tok, top_k = num(a, "doc_words", lo=1), num(a, "model_context_tokens", lo=100), int(num(a, "top_k", lo=1))
    size, ov = num(a, "chunk_tokens", lo=50), num(a, "overlap_pct", lo=0, hi=50) / 100
    toks = words * 1.33
    step = size * (1 - ov)
    chunks = math.ceil(max(0.0, toks - size) / step) + 1
    used = top_k * size
    return {"document_tokens": r(toks, 0), "chunks": chunks, "storage_multiplier_from_overlap": r(1 / (1 - ov), 2), "tokens_sent_per_question": int(used), "context_used_pct": r(100 * used / ctx_tok, 1),
            "verdict": "Retrieved text does not fit: lower top-k or chunk size." if used > ctx_tok * 0.6 else "Fits, with room for the question and the answer.",
            "tips": ["Split on headings and paragraphs, not mid-sentence.", "256 to 512 tokens with 10 to 15% overlap is a common start; test against your questions.", "Keep the title and section name in each chunk so it makes sense alone."]}


tool(T, "chunk_plan", "Chunking planner", "Chunks and context use for retrieval.", [("doc_words", "Document length (words)", 12000), ("chunk_tokens", "Chunk size (tokens)", 400), ("overlap_pct", "Overlap (%)", 12), ("top_k", "Chunks sent to the model", 5), ("model_context_tokens", "Model context (tokens)", 8000)], chunking)


def quant(a):
    n, prec = num(a, "params_b", lo=0, strict=True) * 1e9, txt(a, "precision").lower()
    bw, ctxgb = num(a, "memory_bandwidth_gb_s", lo=1), num(a, "gpu_memory_gb", lo=0.5)
    if prec not in _BYTES:
        raise ProError("Precision must be fp32, fp16, bf16, int8 or int4.")
    gb = n * _BYTES[prec] / 1e9
    tps = bw / gb
    return {"weights_gb": r(gb, 1), "fits_in_gpu": gb * 1.15 <= ctxgb, "max_tokens_per_s_one_stream": r(tps, 1),
            "how": "Each generated token reads every weight once, so single-stream speed is capped near memory bandwidth / model size. Batching shares that read across users and raises total throughput.",
            "tips": ["Leave room for the KV cache and activations (about 15% or more).", "int8 and int4 raise speed and cut memory; check quality on your own tasks.", "Real speed is lower than the cap because of overheads."]}


tool(T, "quant_speed", "Quantization size and speed bound", "Model size and best-case tokens per second.", [("params_b", "Model size (billions)", 8), ("precision", "Precision", "int4"), ("memory_bandwidth_gb_s", "GPU memory bandwidth (GB/s)", 900), ("gpu_memory_gb", "GPU memory (GB)", 16)], quant)


def kv(a):
    layers, kvh, hd, ctx, batch, prec = int(num(a, "layers", lo=1)), int(num(a, "kv_heads", lo=1)), int(num(a, "head_dim", lo=1)), int(num(a, "context_tokens", lo=1)), int(num(a, "batch", lo=1)), txt(a, "precision").lower()
    if prec not in _BYTES:
        raise ProError("Precision must be fp32, fp16, bf16, int8 or int4.")
    per_tok = 2 * layers * kvh * hd * _BYTES[prec]
    tot = per_tok * ctx * batch
    return {"kv_bytes_per_token": int(per_tok), "kv_cache_gb": r(tot / 1e9, 2), "tip": "Grouped-query attention (fewer KV heads), shorter contexts, KV quantization and paged attention all cut this. Cache grows with context x concurrent users."}


tool(T, "kv_cache", "KV cache size", "Memory for the attention cache.", [("layers", "Layers", 32), ("kv_heads", "Key/value heads", 8), ("head_dim", "Head dimension", 128), ("context_tokens", "Context length (tokens)", 8192), ("batch", "Concurrent sequences", 16), ("precision", "Precision", "fp16")], kv)


def llmcost(a):
    q, tin, tout, pin, pout = num(a, "requests_per_day", lo=0), num(a, "input_tokens", lo=0), num(a, "output_tokens", lo=0), num(a, "price_in_per_m", lo=0), num(a, "price_out_per_m", lo=0)
    cached, disc = num(a, "cached_input_pct", lo=0, hi=100) / 100, num(a, "cache_discount_pct", lo=0, hi=100) / 100
    in_eff = tin * (1 - cached * disc)
    per = in_eff * pin / 1e6 + tout * pout / 1e6
    base = tin * pin / 1e6 + tout * pout / 1e6
    return {"cost_per_request": r(per, 5), "per_day": r(per * q, 2), "per_month": r(per * q * 30, 2), "without_caching_per_month": r(base * q * 30, 2), "caching_saves_pct": r(100 * (1 - per / base), 1) if base else 0,
            "tips": ["Output tokens usually cost several times input tokens: ask for concise answers.", "Cache the long fixed prefix (instructions, documents) and keep it first in the prompt.", "Route easy requests to a smaller model; measure quality before switching.", "Check the current price list: prices change."]}


tool(T, "llm_cost", "LLM cost with caching", "Monthly cost for a workload.", [("requests_per_day", "Requests per day", 2000), ("input_tokens", "Input tokens per request", 3000), ("output_tokens", "Output tokens per request", 400), ("price_in_per_m", "Input price (per million tokens)", 3), ("price_out_per_m", "Output price (per million tokens)", 15), ("cached_input_pct", "Input that is cached (%)", 70), ("cache_discount_pct", "Cache discount (%)", 90)], llmcost)


def evalcmp(a):
    rows = lines(a, "results", "the results", 4)
    ap, bp, wa, wb, tie = [], [], 0, 0, 0
    for p in rows:
        if len(p) < 2:
            raise ProError("Each line: score A, score B for one test case.")
        x, y = float(p[0]), float(p[1])
        ap.append(x)
        bp.append(y)
        wa += x > y
        wb += y > x
        tie += x == y
    n = len(ap)
    d = [y - x for x, y in zip(ap, bp)]
    md = sum(d) / n
    sd = math.sqrt(sum((v - md) ** 2 for v in d) / (n - 1)) if n > 1 else 0
    se = sd / math.sqrt(n) if sd else 0
    lo, hi = md - 1.96 * se, md + 1.96 * se
    # sign test, two-sided
    k, m = max(wa, wb), wa + wb
    pval = min(1.0, 2 * sum(math.comb(m, i) for i in range(k, m + 1)) / 2 ** m) if m else 1.0
    return {"cases": n, "mean_a": r(sum(ap) / n, 3), "mean_b": r(sum(bp) / n, 3), "b_minus_a": r(md, 3), "ci95": f"{r(lo, 3)} to {r(hi, 3)}", "a_wins": int(wa), "b_wins": int(wb), "ties": int(tie), "sign_test_p": r(pval, 3),
            "verdict": ("B is reliably different from A." if pval < 0.05 else "The averages differ but the win count is not conclusive: add test cases before switching.") if (lo > 0 or hi < 0) else "No reliable difference yet: add test cases before switching.",
            "tips": ["Run both versions on the same cases.", "30 cases rarely settle a small gain: use 100 or more.", "Read the failures, not just the average."]}


tool(T, "eval_compare", "Prompt or model comparison", "Is version B really better than A?", [("results", "Lines of: score A, score B per test case", "0.6,0.7\n0.5,0.8\n0.9,0.9\n0.4,0.6\n0.7,0.65\n0.3,0.5\n0.8,0.85\n0.6,0.75", "area")], evalcmp)

ref(T, "redteam", "Red teaming", [
    {"title": "Test list", "items": ["Prompt injection: instructions hidden in documents, web pages or emails.", "Jailbreaks and role play that ask for forbidden content.", "Data leakage: system prompt, other users' data, secrets in context.", "Tool abuse: getting the agent to run a harmful action or call with bad arguments.", "Harmful, biased or false output in your domain; confident wrong answers.", "Denial of wallet: huge inputs or loops that run up cost."]},
    {"title": "Process", "items": ["Write attacks as test cases and keep them in the regression set.", "Fix with layers: least privilege, input and output checks, human approval for risky actions.", "Retest after every prompt or model change."]}])
ref(T, "guardrails", "Guardrails", [
    {"title": "Layers", "items": ["Input: size limits, format checks, injection screening.", "Prompt: clear role and rules; separate trusted instructions from untrusted data.", "Output: schema validation, a moderation check, citation checks, refusal to guess.", "Actions: scoped credentials, allow-lists, confirmation before anything irreversible.", "Fallback: a safe answer or a human hand-off when checks fail."]}])
ref(T, "llmops", "LLMOps monitoring", [
    {"title": "Watch", "items": ["Quality: sampled human review and automated evals on live traffic.", "Cost and tokens per request, cache hit rate.", "Latency (time to first token and total), timeouts, error rate.", "Drift: new kinds of questions, retrieval hit rate falling.", "Safety: flagged outputs, refusals, user reports."]},
    {"title": "Release", "items": ["Version prompts, models and retrieval settings together.", "Gate releases on the eval set; roll out gradually; keep a rollback."]}])
ref(T, "multimodal", "Multimodal basics", [
    {"title": "Notes", "items": ["Images cost tokens by size: resize before sending.", "OCR first when you need exact text and numbers, then reason over the text.", "Audio: transcribe, then process; keep timestamps for citations.", "Check the same safety and privacy rules for images: faces, documents, screens."]}])
