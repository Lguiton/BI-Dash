"use client";
import { useEffect, useState } from "react";
import { getJson, postJson } from "@/lib/api";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Badge, Field, Section, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";

interface Gpu { id: string; label: string; vram_gb: number; bandwidth_gbs: number; fp8_tflops: number | null; note: string }
interface Catalog { gpus: Gpu[]; precisions: { id: string; label: string; bytes: number; note: string }[]; formats: { name: string; abbr: string; first: string }[]; source: string }
type R = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

const TABS = [
  { id: "fit", label: "Will it fit?" }, { id: "speed", label: "Speed limits" }, { id: "latency", label: "Measure latency" }, { id: "cost", label: "API or own GPUs?" },
  { id: "spec", label: "Speculation" }, { id: "scale", label: "Replicas" }, { id: "quant", label: "Quantization" }, { id: "ref", label: "Ideas and limits" },
];

function useCatalog() {
  const [c, setC] = useState<Catalog | null>(null);
  const [e, setE] = useState<string | null>(null);
  useEffect(() => { getJson<Catalog>("/api/ai/inference/catalog").then(setC).catch((x) => setE(errMsg(x, "Couldn't load the hardware list."))); }, []);
  return { c, e };
}

function Num({ label, v, set, ph }: { label: string; v: string; set: (s: string) => void; ph?: string }) {
  return <Field label={label}><input className="field" inputMode="decimal" value={v} placeholder={ph} aria-label={label} onChange={(e) => set(e.target.value)} /></Field>;
}

function HwPick({ c, gpu, setGpu, custom, setCustom }: { c: Catalog | null; gpu: string; setGpu: (s: string) => void; custom: R; setCustom: (r: R) => void }) {
  return (
    <>
      <Field label="Hardware"><select className="field" value={gpu} onChange={(e) => setGpu(e.target.value)} aria-label="Hardware">{(c?.gpus ?? []).map((g) => <option key={g.id} value={g.id}>{g.label} ({g.vram_gb} GB)</option>)}<option value="custom">My own hardware</option></select></Field>
      {gpu === "custom" && (
        <>
          <Num label="Memory (GB)" v={custom.vram_gb ?? ""} set={(s) => setCustom({ ...custom, vram_gb: s })} />
          <Num label="Bandwidth (GB/s)" v={custom.bandwidth_gbs ?? ""} set={(s) => setCustom({ ...custom, bandwidth_gbs: s })} />
          <Num label="FP8 teraFLOPS (optional)" v={custom.fp8_tflops ?? ""} set={(s) => setCustom({ ...custom, fp8_tflops: s })} />
        </>
      )}
    </>
  );
}

function PrecPick({ c, v, set, label = "Precision" }: { c: Catalog | null; v: string; set: (s: string) => void; label?: string }) {
  return <Field label={label}><select className="field" value={v} onChange={(e) => set(e.target.value)} aria-label={label}>{(c?.precisions ?? []).map((p) => <option key={p.id} value={p.id}>{p.label} ({p.bytes} bytes)</option>)}</select></Field>;
}

function useCalc(path: string) {
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async (body: R) => {
    setBusy(true); setErr(null);
    try { setRes(await postJson<R>(`/api/ai/inference/${path}`, body)); } catch (e) { setRes(null); setErr(errMsg(e, "That didn't work.")); } finally { setBusy(false); }
  };
  return { res, err, busy, run };
}

const n = (x: unknown, d = 1) => (x == null ? "—" : typeof x === "number" ? x.toLocaleString(undefined, { maximumFractionDigits: d }) : String(x));

function FitTab({ c }: { c: Catalog | null }) {
  const [f, setF] = useState({ params_b: "8", precision: "fp16", gpu: "h100", n_gpus: "1", layers: "", kv_heads: "", head_dim: "", context: "8192", batch: "4" });
  const [custom, setCustom] = useState<R>({});
  const { res, err, busy, run } = useCalc("fit");
  const set = (k: string) => (s: string) => setF({ ...f, [k]: s });
  return (
    <div className="space-y-4">
      <Section title="Will this model fit on this hardware?" note="Weights take about one gigabyte per billion parameters at 8 bits. Add the model's layers, KV heads and head dimension (from its config) to size the KV cache too.">
        <div className="flex flex-wrap items-end gap-3">
          <Num label="Model size (billions of parameters)" v={f.params_b} set={set("params_b")} />
          <PrecPick c={c} v={f.precision} set={set("precision")} />
          <HwPick c={c} gpu={f.gpu} setGpu={set("gpu")} custom={custom} setCustom={setCustom} />
          <Num label="Number of GPUs" v={f.n_gpus} set={set("n_gpus")} />
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <Num label="Layers (optional)" v={f.layers} set={set("layers")} ph="32" />
          <Num label="KV heads" v={f.kv_heads} set={set("kv_heads")} ph="8" />
          <Num label="Head dimension" v={f.head_dim} set={set("head_dim")} ph="128" />
          <Num label="Context (tokens)" v={f.context} set={set("context")} />
          <Num label="Batch size" v={f.batch} set={set("batch")} />
          <button className="btn btn-primary" disabled={busy} onClick={() => run({ ...f, custom, layers: f.layers || null, kv_heads: f.kv_heads || null, head_dim: f.head_dim || null })}>{busy ? "Working…" : "Check"}</button>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {res && (
        <>
          <Lesson text={res.lesson} /><Warn items={res.warnings} />
          <Section title="Result">
            <Table head={["Weights", "Total memory", "Weights plus 50% headroom", "Fits the rule?", "Fewest GPUs by the rule"]} rows={[[`${n(res.weights_gb)} GB`, `${n(res.total_vram_gb)} GB`, `${n(res.book_rule_gb)} GB`, <Badge key="b" tone={res.fits_book_rule ? "ok" : "warn"}>{res.fits_book_rule ? "yes" : "no"}</Badge>, res.min_gpus_by_rule]]} />
            {res.kv && <p className="mt-3 text-sm">KV cache: {n(res.kv.per_token_kb)} KB per token, {n(res.kv.per_sequence_gb, 2)} GB per request, {n(res.kv.total_gb, 2)} GB for this batch. {res.kv.fits ? "It fits" : "It does not fit"}; the largest batch that fits is {n(res.kv.max_batch, 0)}. <span className="text-xs text-muted">{res.kv.assumption}</span></p>}
          </Section>
        </>
      )}
    </div>
  );
}

function SpeedTab({ c }: { c: Catalog | null }) {
  const [f, setF] = useState({ params_b: "8", precision: "fp16", gpu: "h100", n_gpus: "1", input_tokens: "2000", batch: "1", active_params_b: "" });
  const [custom, setCustom] = useState<R>({});
  const { res, err, busy, run } = useCalc("bottleneck");
  const set = (k: string) => (s: string) => setF({ ...f, [k]: s });
  return (
    <div className="space-y-4">
      <Section title="Speed limits from the hardware" note="Ceilings from peak specs. Real systems fall short, so treat these as the best you could hope for and measure.">
        <div className="flex flex-wrap items-end gap-3">
          <Num label="Model size (billions of parameters)" v={f.params_b} set={set("params_b")} />
          <Num label="Active parameters (mixture-of-experts, optional)" v={f.active_params_b} set={set("active_params_b")} />
          <PrecPick c={c} v={f.precision} set={set("precision")} />
          <HwPick c={c} gpu={f.gpu} setGpu={set("gpu")} custom={custom} setCustom={setCustom} />
          <Num label="Number of GPUs" v={f.n_gpus} set={set("n_gpus")} />
          <Num label="Input tokens" v={f.input_tokens} set={set("input_tokens")} />
          <Num label="Batch size" v={f.batch} set={set("batch")} />
          <button className="btn btn-primary" disabled={busy} onClick={() => run({ ...f, custom, active_params_b: f.active_params_b || null })}>{busy ? "Working…" : "Calculate"}</button>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {res && (
        <>
          <Lesson text={res.lesson} /><Warn items={res.warnings} />
          <Section title="Result" note={res.caveat}>
            <p className="mb-2 text-sm">Hardware balance point: {res.ops_per_byte == null ? "unknown" : `${n(res.ops_per_byte)} operations per byte`}.</p>
            <Table head={["Phase", "Bound by", "Limit"]} rows={[
              ["Prefill (sets time to first token)", res.prefill.bound, res.prefill.ttft_ms_min == null ? "—" : `at least ${n(res.prefill.ttft_ms_min)} ms`],
              ["Decode (sets tokens per second)", res.decode.bound, `up to ${n(res.decode.tps_per_user_max)} tokens/s per user (${n(res.decode.itl_ms_min, 2)} ms between tokens), ${n(res.decode.total_tps_max, 0)} tokens/s in total`],
            ]} />
            {res.decode.balanced_batch != null && <p className="mt-2 text-xs text-muted">Decode stops being memory-bound at a batch of about {n(res.decode.balanced_batch, 0)} requests (weights only, estimate).</p>}
            <p className="mt-1 text-xs text-muted">{res.prefill.note}</p>
          </Section>
        </>
      )}
    </div>
  );
}

const SAMPLE = "ttft_ms,total_ms,output_tokens\n180,2400,150\n210,2600,160\n195,2300,140\n950,6100,155\n205,2500,150\n190,2450,148\n220,2700,162\n185,2350,145\n200,2550,152\n1400,7800,158";
function LatencyTab() {
  const [text, setText] = useState(SAMPLE);
  const [dur, setDur] = useState("");
  const { res, err, busy, run } = useCalc("latency");
  const labels: Record<string, string> = { ttft_ms: "Time to first token (ms)", total_ms: "Total time (ms)", output_tokens: "Output tokens", perceived_tps: "Tokens per second per user", itl_ms: "Inter-token latency (ms)" };
  return (
    <div className="space-y-4">
      <Section title="Latency percentiles from your own measurements" note="One row per request, with columns ttft_ms, total_ms and output_tokens (a header row names them; with no header give numbers in that order). Measure from your own app or load tests.">
        <textarea className="field h-40 w-full font-mono text-xs" value={text} aria-label="Measurements" onChange={(e) => setText(e.target.value)} />
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <Num label="Test duration in seconds (optional, for total tokens per second)" v={dur} set={setDur} />
          <button className="btn btn-primary" disabled={busy} onClick={() => run({ text, duration_s: dur || null })}>{busy ? "Working…" : "Summarise"}</button>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {res && (
        <>
          <Lesson text={res.lesson} /><Warn items={res.warnings} />
          <Section title="Percentiles">
            <Table head={["Metric", "Requests", "Mean", "P50", "P90", "P95", "P99", "Mean over P50"]} rows={Object.entries(res.metrics as R).map(([k, m]: [string, R]) => [labels[k] ?? k, m.n, n(m.mean, 2), n(m.p50, 2), n(m.p90, 2), n(m.p95, 2), n(m.p99, 2), m.mean_over_p50 ?? "—"])} />
            {res.total_tps != null && <p className="mt-2 text-sm">Total throughput: {n(res.total_tps)} tokens/s, {n(res.requests_per_s, 3)} requests/s.</p>}
          </Section>
        </>
      )}
    </div>
  );
}

function CostTab() {
  const [f, setF] = useState({ input_m: "200", output_m: "40", price_in: "", price_out: "", gpus: "1", gpu_hour: "", hours: "730", total_tps: "", utilization_pct: "50", eng_hours: "10", eng_rate: "" });
  const { res, err, busy, run } = useCalc("cost");
  const set = (k: string) => (s: string) => setF({ ...f, [k]: s });
  return (
    <div className="space-y-4">
      <Section title="Pay per token, or run your own GPUs?" note="Enter your own prices: they change often, so none are built in. Use a month or at least a week of real traffic.">
        <div className="flex flex-wrap items-end gap-3">
          <Num label="Monthly input tokens (millions)" v={f.input_m} set={set("input_m")} />
          <Num label="Monthly output tokens (millions)" v={f.output_m} set={set("output_m")} />
          <Num label="API price per million input tokens ($)" v={f.price_in} set={set("price_in")} />
          <Num label="API price per million output tokens ($)" v={f.price_out} set={set("price_out")} />
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-3">
          <Num label="GPUs" v={f.gpus} set={set("gpus")} />
          <Num label="GPU price per hour ($)" v={f.gpu_hour} set={set("gpu_hour")} />
          <Num label="Hours per month" v={f.hours} set={set("hours")} />
          <Num label="Measured output tokens/s per GPU (optional)" v={f.total_tps} set={set("total_tps")} />
          <Num label="Utilization (%)" v={f.utilization_pct} set={set("utilization_pct")} />
          <Num label="Engineering hours a month" v={f.eng_hours} set={set("eng_hours")} />
          <Num label="Engineering hourly cost ($)" v={f.eng_rate} set={set("eng_rate")} />
          <button className="btn btn-primary" disabled={busy || !f.price_in || !f.price_out} onClick={() => run({ ...f, total_tps: f.total_tps || null, eng_rate: f.eng_rate || 0, gpu_hour: f.gpu_hour || 0 })}>{busy ? "Working…" : "Compare"}</button>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {res && (
        <>
          <Lesson text={res.lesson} /><Warn items={res.warnings} />
          <Section title="Monthly totals">
            <Table head={["Option", "Cost per month"]} rows={[["Per-token API", `$${n(res.api_monthly, 2)}`], ["Own GPUs", `$${n(res.gpu_monthly, 2)}`], ["Engineering time", `$${n(res.engineering_monthly, 2)}`], ["Own GPUs in total", `$${n(res.dedicated_monthly, 2)}`]]} />
            <p className="mt-2 text-sm">Cheaper here: <b>{res.cheaper === "api" ? "the API" : "your own GPUs"}</b>, by ${n(res.difference, 2)} a month.
              {res.break_even_tokens_m != null && ` Break-even is about ${n(res.break_even_tokens_m, 0)} million tokens a month at your blended API price of $${n(res.api_blended_per_m, 3)} per million.`}
              {res.capacity_output_m != null && ` This deployment could produce about ${n(res.capacity_output_m, 0)} million output tokens a month (about $${n(res.dedicated_per_m_output, 2)} per million output tokens in total).`}</p>
          </Section>
        </>
      )}
    </div>
  );
}

function SpecTab() {
  const [f, setF] = useState({ acceptance: "0.8", draft_len: "4", draft_cost: "0.1" });
  const { res, err, busy, run } = useCalc("speculative");
  const set = (k: string) => (s: string) => setF({ ...f, [k]: s });
  return (
    <div className="space-y-4">
      <Section title="What would speculative decoding gain?" note="A small draft proposes tokens and the big model checks them together. Acceptance rate is the share of drafted tokens that are right; draft cost is how much one draft token costs relative to one big-model step.">
        <div className="flex flex-wrap items-end gap-3">
          <Num label="Acceptance rate (0 to 1)" v={f.acceptance} set={set("acceptance")} />
          <Num label="Draft length (tokens)" v={f.draft_len} set={set("draft_len")} />
          <Num label="Draft cost (0 to 1)" v={f.draft_cost} set={set("draft_cost")} />
          <button className="btn btn-primary" disabled={busy} onClick={() => run(f)}>{busy ? "Working…" : "Estimate"}</button>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {res && (
        <>
          <Lesson text={res.lesson} />
          <Section title="Result" note={res.caution}>
            <p className="mb-2 text-sm">At {res.current.draft_len} drafted tokens: about {n(res.current.tokens_per_step, 2)} tokens per step, {n(res.current.speedup, 2)}x faster. Best draft length here: {res.best.draft_len} ({n(res.best.speedup, 2)}x).</p>
            <Table head={["Draft length", "Tokens per step", "Speedup"]} rows={(res.table as R[]).filter((r) => r.draft_len <= 8).map((r) => [r.draft_len, n(r.tokens_per_step, 2), `${n(r.speedup, 2)}x`])} />
          </Section>
        </>
      )}
    </div>
  );
}

function ScaleTab() {
  const [f, setF] = useState({ requests_per_s: "10", avg_latency_s: "2", concurrency: "8", target_pct: "70", spike: "3", cold_start_s: "60" });
  const { res, err, busy, run } = useCalc("scaling");
  const set = (k: string) => (s: string) => setF({ ...f, [k]: s });
  return (
    <div className="space-y-4">
      <Section title="How many replicas?" note="Concurrency is how many requests one replica can serve at once (test several batch sizes to find it).">
        <div className="flex flex-wrap items-end gap-3">
          <Num label="Requests per second" v={f.requests_per_s} set={set("requests_per_s")} />
          <Num label="Average request time (s)" v={f.avg_latency_s} set={set("avg_latency_s")} />
          <Num label="Concurrency per replica" v={f.concurrency} set={set("concurrency")} />
          <Num label="Target utilization (%)" v={f.target_pct} set={set("target_pct")} />
          <Num label="Spike multiplier" v={f.spike} set={set("spike")} />
          <Num label="Cold start (s)" v={f.cold_start_s} set={set("cold_start_s")} />
          <button className="btn btn-primary" disabled={busy} onClick={() => run(f)}>{busy ? "Working…" : "Calculate"}</button>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {res && (
        <>
          <Lesson text={res.lesson} /><Warn items={res.warnings} />
          <Section title="Result"><Table head={["Requests in flight", "Replicas now", "Replicas at the spike", "Requests waiting during cold start"]} rows={[[n(res.in_flight), res.replicas, res.replicas_at_spike, n(res.requests_waiting_during_cold_start, 0)]]} /></Section>
        </>
      )}
    </div>
  );
}

function QuantTab({ c }: { c: Catalog | null }) {
  const [p, setP] = useState("70");
  const { res, err, busy, run } = useCalc("quantization");
  return (
    <div className="space-y-4">
      <Section title="Model size at each precision" note="Check quality after quantizing, never assume.">
        <div className="flex flex-wrap items-end gap-3"><Num label="Model size (billions of parameters)" v={p} set={setP} /><button className="btn btn-primary" disabled={busy} onClick={() => run({ params_b: p })}>{busy ? "Working…" : "Show sizes"}</button></div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {res && (
        <>
          <Lesson text={res.lesson} />
          <Section title="Weights at each precision"><Table head={["Precision", "Bytes per value", "Weights", "Note"]} rows={(res.rows as R[]).map((r) => [r.precision, r.bytes, `${n(r.weights_gb)} GB`, r.note])} /></Section>
          <Section title="How to check quality after quantizing"><ul className="list-disc space-y-1 pl-5 text-sm">{(res.quality as string[]).map((q) => <li key={q}>{q}</li>)}</ul></Section>
        </>
      )}
      <Section title="Number formats you will see"><Table head={["Format", "Abbreviation", "First architecture"]} rows={(c?.formats ?? []).map((f) => [f.name, f.abbr, f.first])} /></Section>
    </div>
  );
}

const IDEAS = [
  ["Two phases", "Prefill reads the whole prompt at once and is compute-bound; it sets time to first token. Decode generates one token at a time and is memory-bound; it sets tokens per second.", "Speed limits tab."],
  ["Latency metrics", "Time to first token, tokens per second per user, inter-token latency, and percentiles (P50, P90, P95, P99) rather than the mean. Inference-only time and end-to-end time answer different questions.", "Measure latency tab."],
  ["Batching", "Static waits for a full batch, dynamic adds a time limit, continuous swaps requests in at token level. Bigger batches raise throughput and slow each user.", "Replicas tab (concurrency)."],
  ["Quantization", "Lower precision shrinks memory and speeds both phases, about 30 to 50 percent per step in practice, at some risk to quality. Check with perplexity, a benchmark and your own evals.", "Quantization tab."],
  ["Speculative decoding", "Draft tokens cheaply, verify them in one pass. Draft-target, Medusa, EAGLE and n-gram methods differ in overhead and acceptance rate.", "Speculation tab."],
  ["Caching", "Reuse the KV cache for repeated prefixes, store it in cheaper tiers, and route requests to where the cache lives.", "Not run here; the Will it fit tab sizes the cache."],
  ["Model parallelism", "Split a model that does not fit one GPU across several: tensor parallelism for latency, expert parallelism for throughput, multi-node when needed. Fast links between GPUs matter.", "Will it fit tab warns when more than one GPU is needed."],
  ["Disaggregation", "Run prefill and decode on separate engines so each can be tuned for its bottleneck.", "Taught here, not run."],
  ["Autoscaling", "Scale replicas on traffic using a concurrency target; plan for cold starts and choose a minimum replica count.", "Replicas tab."],
  ["Cost", "Per-token pricing is linear; dedicated GPUs are mostly fixed cost. Include engineering time and compare over a week or more.", "API or own GPUs tab."],
  ["Local inference", "On-device inference removes network latency and keeps data private, but desktop hardware is slower, hotter and more varied than a datacenter.", "Use Your own hardware in the calculators."],
];
const NOT_HERE = [
  ["GPUs and CUDA", "This app does not run GPU code. The calculators use spec-sheet numbers.", "Rent a GPU instance or use a local GPU to try it."],
  ["Inference engines (vLLM, SGLang, TensorRT-LLM) and NVIDIA Dynamo", "Not installed or run.", "Install one on a machine with a supported GPU."],
  ["Load testing and profiling", "No benchmark runs against a model here.", "Use your engine's benchmark tool, then paste the numbers into Measure latency."],
  ["Disaggregation, multi-node and multi-cloud capacity", "Taught, not run.", "Needs a cluster."],
  ["Containers for models, NIMs, zero-downtime deploys", "Not built.", "Docker and your cloud provider."],
  ["Image, video, speech and embedding model serving", "Only the LLM arithmetic is built.", "The book's chapter on modalities."],
  ["Baseten or any hosted inference platform", "Not connected.", "Use the vendor's own console."],
];

function RefTab({ c }: { c: Catalog | null }) {
  return (
    <div className="space-y-4">
      <Section title="Ideas from the book, and where to practise them" note={c?.source}><Table head={["Idea", "What it is", "In this app"]} rows={IDEAS} /></Section>
      <Section title="Hardware figures used" note="As printed in the book: dense FP8 compute, memory and bandwidth. Blackwell figures are approximate."><Table head={["Hardware", "Memory", "Bandwidth", "FP8 compute", "Note"]} rows={(c?.gpus ?? []).map((g) => [g.label, `${g.vram_gb} GB`, `${g.bandwidth_gbs.toLocaleString()} GB/s`, g.fp8_tflops == null ? "not given" : `${g.fp8_tflops.toLocaleString()} teraFLOPS`, g.note])} /></Section>
      <Section title="Not available here" note="Do these by hand on real hardware."><Table head={["Topic", "Status", "What to do"]} rows={NOT_HERE} /></Section>
    </div>
  );
}

export function InferencePanel() {
  const [tab, setTab] = useState("fit");
  const { c, e } = useCatalog();
  return (
    <section className="space-y-4" aria-label="Inference Lab">
      <h2 className="text-base font-semibold">Inference Lab</h2>
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">
        Back-of-envelope calculators for running AI models, from Philip Kiely&apos;s Inference Engineering. They use spec-sheet numbers, give ceilings rather than promises, and never call a model or a GPU.
      </p>
      {e && <ErrorBanner message={e} />}
      <Tabs label="Inference tools" value={tab} onChange={setTab} tabs={TABS} />
      {tab === "fit" && <FitTab c={c} />}
      {tab === "speed" && <SpeedTab c={c} />}
      {tab === "latency" && <LatencyTab />}
      {tab === "cost" && <CostTab />}
      {tab === "spec" && <SpecTab />}
      {tab === "scale" && <ScaleTab />}
      {tab === "quant" && <QuantTab c={c} />}
      {tab === "ref" && <RefTab c={c} />}
    </section>
  );
}
