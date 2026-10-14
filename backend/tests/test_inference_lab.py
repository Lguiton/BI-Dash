import pytest

from app.services import inference_lab as il


def post(client, path, **body):
    return client.post(f"/api/ai/inference/{path}", json=body)


def test_catalog_has_book_gpus(client):
    c = client.get("/api/ai/inference/catalog").json()
    h100 = next(g for g in c["gpus"] if g["id"] == "h100")
    assert (h100["vram_gb"], h100["bandwidth_gbs"], h100["fp8_tflops"]) == (80, 3350, 1979)
    assert {"h100", "h200", "b200", "b300", "l4", "l40", "rtx5090", "m3ultra"} <= {g["id"] for g in c["gpus"]}
    assert any(f["abbr"] == "NVFP4" for f in c["formats"])


def test_fit_uses_book_rule(client):
    r = post(client, "fit", params_b=70, precision="fp16", gpu="h100", n_gpus=2).json()
    assert r["weights_gb"] == 140 and r["total_vram_gb"] == 160 and not r["fits_book_rule"] and r["min_gpus_by_rule"] == 3
    ok = post(client, "fit", params_b=8, precision="fp8", gpu="h100").json()
    assert ok["weights_gb"] == 8 and ok["fits_book_rule"]
    bad = post(client, "fit", params_b=200, precision="fp16", gpu="l4").json()
    assert any("do not fit" in w for w in bad["warnings"])


def test_fit_kv_cache_formula(client):
    # Llama-style 8B: 32 layers, 8 KV heads, head dim 128, FP16: 2*32*8*128*2 = 131072 bytes = 128 KB per token
    r = post(client, "fit", params_b=8, precision="fp16", gpu="h100", layers=32, kv_heads=8, head_dim=128, context=8192, batch=4).json()
    assert r["kv"]["per_token_kb"] == 128.0
    assert r["kv"]["per_sequence_gb"] == pytest.approx(1.07, abs=0.01) and r["kv"]["total_gb"] == pytest.approx(4.29, abs=0.01)
    assert r["kv"]["fits"] and r["kv"]["max_batch"] > 4


def test_bottleneck_matches_book_ops_byte(client):
    r = post(client, "bottleneck", params_b=8, precision="fp16", gpu="h100", input_tokens=2000, batch=1).json()
    assert r["ops_per_byte"] == pytest.approx(295, abs=1)          # the book's H100 FP16 example
    assert r["decode"]["bound"] == "memory" and r["prefill"]["bound"] == "compute"
    assert r["decode"]["tps_per_user_max"] == pytest.approx(3350 / 16, abs=0.5)
    assert r["decode"]["balanced_batch"] == pytest.approx(295, abs=2)
    big = post(client, "bottleneck", params_b=8, precision="fp16", gpu="h100", batch=1000).json()
    assert big["decode"]["bound"] == "compute"


def test_bottleneck_hardware_without_compute_and_fp4_rules(client):
    r = post(client, "bottleneck", params_b=8, precision="fp8", gpu="m3ultra").json()
    assert r["decode"]["compute_time_ms"] is None and r["prefill"]["ttft_ms_min"] is None and r["decode"]["tps_per_user_max"] > 0
    assert post(client, "bottleneck", params_b=8, precision="fp4", gpu="h100").status_code == 400
    assert post(client, "bottleneck", params_b=8, precision="fp4", gpu="b200").status_code == 200
    c = post(client, "bottleneck", params_b=8, precision="fp16", gpu="custom", custom={"vram_gb": 24, "bandwidth_gbs": 500, "fp8_tflops": 100}).json()
    assert c["gpu"] == "Your hardware"
    assert post(client, "bottleneck", params_b=8, precision="fp16", gpu="custom", custom={"vram_gb": 24}).status_code == 400


def test_latency_percentiles_and_per_user_speed(client):
    rows = "ttft_ms,total_ms,output_tokens\n" + "\n".join(f"{100 + i},{1100 + i * 10},101" for i in range(100))
    r = post(client, "latency", text=rows, duration_s=50).json()
    m = r["metrics"]
    assert m["ttft_ms"]["n"] == 100 and m["ttft_ms"]["p50"] == pytest.approx(149.5) and m["ttft_ms"]["p99"] == pytest.approx(198.01, abs=0.01)
    assert m["total_ms"]["mean_over_p50"] >= 1.0
    assert "perceived_tps" in m and m["itl_ms"]["p50"] > 0
    assert r["total_tps"] == pytest.approx(202.0) and not r["warnings"]
    small = post(client, "latency", text="120\n150\n900").json()
    assert small["warnings"] and small["metrics"]["ttft_ms"]["p99"] > 800


def test_latency_errors(client):
    assert post(client, "latency", text="").status_code == 400
    assert post(client, "latency", text="ttft_ms\nabc").status_code == 400
    assert post(client, "latency", text="-5").status_code == 400
    assert post(client, "latency", text="foo,bar\n1,2").status_code == 400


def test_cost_break_even_and_capacity(client):
    r = post(client, "cost", input_m=100, output_m=20, price_in=1, price_out=4, gpus=2, gpu_hour=3, hours=730, eng_hours=10, eng_rate=100, total_tps=500, utilization_pct=50).json()
    assert r["api_monthly"] == 180 and r["gpu_monthly"] == 4380 and r["dedicated_monthly"] == 5380 and r["cheaper"] == "api"
    assert r["break_even_tokens_m"] == pytest.approx(5380 / 1.5, abs=0.2)
    assert r["capacity_output_m"] == pytest.approx(500 * 2 * 3600 * 730 * 0.5 / 1e6, abs=0.1)
    assert post(client, "cost", input_m=1, output_m=1, price_in=1, price_out=1).json()["warnings"]
    assert post(client, "cost", input_m=-1, output_m=1, price_in=1, price_out=1).status_code == 400


def test_speculative_formula(client):
    r = post(client, "speculative", acceptance=0.8, draft_len=4, draft_cost=0.1).json()
    assert r["current"]["tokens_per_step"] == pytest.approx(3.36, abs=0.01) and r["current"]["speedup"] == pytest.approx(2.40, abs=0.01)
    assert r["best"]["speedup"] >= r["current"]["speedup"]
    zero = post(client, "speculative", acceptance=0, draft_len=4, draft_cost=0.1).json()
    assert zero["current"]["tokens_per_step"] == 1.0 and zero["current"]["speedup"] < 1
    assert post(client, "speculative", acceptance=1.5).status_code == 400


def test_scaling_littles_law(client):
    r = post(client, "scaling", requests_per_s=10, avg_latency_s=2, concurrency=8, target_pct=70, spike=3, cold_start_s=60).json()
    assert r["in_flight"] == 20 and r["replicas"] == 4 and r["replicas_at_spike"] == 11
    assert r["requests_waiting_during_cold_start"] == 1200 and r["warnings"]
    assert post(client, "scaling", requests_per_s=0, avg_latency_s=1, concurrency=1).status_code == 400


def test_quantization_table(client):
    r = post(client, "quantization", params_b=70).json()
    sizes = {x["precision"]: x["weights_gb"] for x in r["rows"]}
    assert sizes["FP16"] == 140 and sizes["FP8"] == 70 and sizes["INT4"] == 35 and r["quality"]
