# Inference Lab (AI Engineering track)

Inference engineering is making AI models faster, cheaper and more reliable without losing the quality that makes them useful. The lab turns the arithmetic from Philip Kiely's *Inference Engineering* (Baseten Books, 2026) into calculators. It sits below the usage panels on the AI Engineering track's Tools view.

| Tab | What it tells you | Honest limit |
|---|---|---|
| Will it fit? | Weights in GB for a model size and precision, the book's weights-plus-50%-headroom rule, the fewest GPUs by that rule, and (with layers, KV heads and head size) the KV cache and largest batch that fits | KV formula is the standard one; assumes 10% of memory is reserved for overhead |
| Speed limits | Compute-bound prefill (a floor for time to first token), memory-bound decode (a ceiling for tokens per second), the hardware balance point (about 295 operations per byte for an H100 at 16-bit), and the batch where decode stops being memory-bound | Peak specs, perfect scaling across GPUs, attention's quadratic term ignored: real systems are slower |
| Measure latency | P50, P90, P95, P99 and the mean for time to first token, total time, tokens per second per user and inter-token latency, from timings you paste | Needs about 100 requests before P99 means much |
| API or own GPUs? | Monthly API cost against own GPUs plus engineering time, break-even, and whether the deployment can carry your output tokens | No prices are built in; you enter yours |
| Speculation | Tokens per step and speedup for an acceptance rate, draft length and draft cost | Assumes constant acceptance; real acceptance falls along the draft and at higher temperature |
| Replicas | Requests in flight (Little's law), replicas for a concurrency target, spike and cold-start waiting | Needs your measured concurrency per replica |
| Quantization | Model size at each precision and how to check quality | Quality is not computed here |
| Ideas and limits | The book's ideas mapped to the app, the hardware figures used, and what is not available | |

Hardware figures are those printed in the book (dense FP8 compute, memory, bandwidth). FP16 compute is taken as half of FP8 and FP4 as double on Blackwell only. You can enter your own hardware.

## Not available here
GPUs and CUDA, inference engines (vLLM, SGLang, TensorRT-LLM, NVIDIA Dynamo), load testing and profiling, disaggregated and multi-node serving, multi-cloud capacity, model containers, image, video, speech and embedding model serving, and hosted platforms. Run those on real hardware, then paste the timings into Measure latency.
