"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Table, Tabs, errMsg } from "./kit";

type Fn = { name: string; estimate: string; loop_depth: number; notes: string[] };
type Cx = { language: string; functions: Fn[]; caveat: string; scale: { n: number; [k: string]: number }[] };
type Step = { what: string; list: (number | string)[] };
type SortR = { algorithm: string; input: number[]; sorted: number[]; comparisons: number; moves: number; steps: Step[]; steps_shown: number; best: string; average: string; worst: string; note: string; n: number };
type SearchR = { algorithm: string; list: number[]; found_at: number | null; comparisons: number; steps: Step[]; average: string; note: string };
type Ref = { structures: { name: string; access: string; search: string; insert: string; use: string }[]; growth: { big_o: string; name: string; example: string }[]; sorts: { id: string; name: string; best: string; average: string; worst: string; note: string }[]; note: string };
const TABS = [{ id: "bigo", label: "Big-O estimate" }, { id: "algo", label: "Step through" }, { id: "sheet", label: "Cheat sheet" }];
const SAMPLE = "def has_duplicate(items):\n    for a in items:\n        for b in items:\n            if a is not b and a == b:\n                return True\n    return False\n";

/** Computer science for the Computer Engineer dashboard: estimate Big-O, watch sorting and searching run, and keep a cheat sheet. Pasted code is never run. */
export function CsLab() {
  const [tab, setTab] = useState("bigo");
  const [code, setCode] = useState(SAMPLE);
  const [cx, setCx] = useState<Cx | null>(null);
  const [kind, setKind] = useState("sort");
  const [algo, setAlgo] = useState("bubble");
  const [data, setData] = useState("5, 2, 9, 1, 5, 6");
  const [target, setTarget] = useState("9");
  const [sr, setSr] = useState<SortR | null>(null);
  const [fr, setFr] = useState<SearchR | null>(null);
  const [ref, setRef] = useState<Ref | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (tab === "sheet" && !ref) getJson<Ref>("/api/cs/reference").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load the cheat sheet."))); }, [tab, ref]);
  const act = async (fn: () => Promise<void>, m: string) => { setErr(null); try { await fn(); } catch (e) { setErr(errMsg(e, m)); } };
  const steps = (s: Step[]) => (
    <ol className="max-h-72 list-decimal space-y-1 overflow-auto pl-5 text-xs" tabIndex={0}>{s.map((x, i) => <li key={i}>{x.what} <span className="font-mono text-muted">[{x.list.join(", ")}]</span></li>)}</ol>
  );
  return (
    <section className="card space-y-3 p-4" aria-label="Computer science lab">
      <h2 className="text-base font-semibold">Computer science: speed, memory and how algorithms work</h2>
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="Computer science lab" />
      {err && <ErrorBanner message={err} />}
      {tab === "bigo" && (
        <Section title="Estimate Big-O from code" note="Paste one function. Python is parsed and never run; other languages are read as text. It is an estimate in terms of input size n.">
          <textarea className="field h-40 w-full font-mono text-xs" aria-label="Code to analyse" value={code} onChange={(e) => setCode(e.target.value)} />
          <div className="mt-2"><button className="btn btn-primary" disabled={code.trim().length < 5} onClick={() => act(async () => setCx(await postJson<Cx>("/api/cs/complexity", { code })), "Couldn't analyse that.")}>Estimate</button></div>
          {cx && (
            <div className="mt-3 space-y-2">
              <p className="text-xs text-muted">{cx.language}</p>
              {cx.functions.map((f) => (
                <div key={f.name} className="rounded border border-line p-2 text-sm">
                  <div><strong>{f.name}</strong> <Badge tone={f.estimate === "O(2^n)" || f.estimate.includes("^3") ? "bad" : f.estimate.includes("^2") ? "warn" : "ok"}>{f.estimate}</Badge></div>
                  {f.notes.map((n, i) => <p key={i} className="text-xs">{n}</p>)}
                </div>
              ))}
              <Table head={["Items (n)", "O(n)", "O(n log n)", "O(n^2)"]} caption="Rough work for different sizes" rows={cx.scale.map((r) => [r.n.toLocaleString(), r["O(n)"].toLocaleString(), r["O(n log n)"].toLocaleString(), r["O(n^2)"].toLocaleString()])} />
              <p className="text-xs text-muted">{cx.caveat}</p>
            </div>
          )}
        </Section>
      )}
      {tab === "algo" && (
        <Section title="Watch an algorithm run on your numbers" note="Up to 200 numbers; the first 60 steps are shown. Counts cover the whole run.">
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs">Kind<select className="input block" value={kind} onChange={(e) => { setKind(e.target.value); setAlgo(e.target.value === "sort" ? "bubble" : "linear"); setSr(null); setFr(null); }}><option value="sort">Sort</option><option value="search">Search</option></select></label>
            <label className="text-xs">Algorithm<select className="input block" value={algo} onChange={(e) => setAlgo(e.target.value)}>
              {kind === "sort" ? ["bubble", "insertion", "selection", "merge", "quick"].map((a) => <option key={a} value={a}>{a}</option>) : ["linear", "binary"].map((a) => <option key={a} value={a}>{a}</option>)}
            </select></label>
            <label className="min-w-48 flex-1 text-xs">Numbers<input className="input block w-full" value={data} onChange={(e) => setData(e.target.value)} /></label>
            {kind === "search" && <label className="text-xs">Find<input className="input block w-24" value={target} onChange={(e) => setTarget(e.target.value)} /></label>}
            <button className="btn btn-primary" onClick={() => act(async () => { if (kind === "sort") { setFr(null); setSr(await postJson<SortR>("/api/cs/sort", { algorithm: algo, data })); } else { setSr(null); setFr(await postJson<SearchR>("/api/cs/search", { algorithm: algo, data, target })); } }, "Couldn't run that.")}>Run</button>
          </div>
          {sr && (
            <div className="mt-3 space-y-2 text-sm">
              <p><strong>{sr.algorithm}</strong>: {sr.comparisons} comparisons, {sr.moves} moves on {sr.n} numbers. Best {sr.best}, average {sr.average}, worst {sr.worst}.</p>
              <p className="font-mono text-xs">Result: [{sr.sorted.join(", ")}]</p>
              {steps(sr.steps)}
              <p className="text-xs text-muted">{sr.note}</p>
            </div>
          )}
          {fr && (
            <div className="mt-3 space-y-2 text-sm">
              <p><strong>{fr.algorithm}</strong>: {fr.found_at ? `found at position ${fr.found_at}` : "not found"} after {fr.comparisons} checks. Average {fr.average}.</p>
              {steps(fr.steps)}
              <p className="text-xs text-muted">{fr.note}</p>
            </div>
          )}
        </Section>
      )}
      {tab === "sheet" && ref && (
        <div className="space-y-3">
          <Table head={["Structure", "Read by position", "Search", "Insert", "Use it for"]} caption="Data structures" rows={ref.structures.map((s) => [s.name, s.access, s.search, s.insert, s.use])} />
          <Table head={["Big-O", "Name", "Example"]} caption="How fast work grows" rows={ref.growth.map((g) => [g.big_o, g.name, g.example])} />
          <Table head={["Sort", "Best", "Average", "Worst", "Note"]} caption="Sorting" rows={ref.sorts.map((s) => [s.name, s.best, s.average, s.worst, s.note])} />
          <p className="text-xs text-muted">{ref.note}</p>
        </div>
      )}
    </section>
  );
}
