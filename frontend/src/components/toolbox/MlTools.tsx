"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, apiFetch, deleteJson, getJson, postJson } from "@/lib/api";
import { Section, Tabs, errMsg } from "@/components/panels/kit";
import { Pick, Rows } from "./common";
import { FieldHowTo, Out, TA, TI, lines, useRun } from "./fieldcommon";

const TABS = [{ id: "how", label: "How to do / fix" }, { id: "label", label: "Text classifier" }, { id: "extract", label: "Extraction tester" }, { id: "exp", label: "Experiment tracker" }];

export function MlTools() {
  const [tab, setTab] = useState("how");
  return (
    <div className="grid gap-4">
      <Tabs label="ML and NLP tools" value={tab} onChange={setTab} tabs={TABS} />
      {tab === "how" && <FieldHowTo area="ML, NLP and deep learning" agent="ml" examples="e.g. text sorter barely better than guessing, overfitting" />}
      {tab === "label" && <Labeling />}
      {tab === "extract" && <Extract />}
      {tab === "exp" && <Experiments />}
    </div>
  );
}

type SetRow = { name: string; labels: string[]; examples: number };
type SetFull = { name: string; labels: string[]; examples: { id: number; label: string; text: string }[]; total: number };

function Labeling() {
  const [sets, setSets] = useState<SetRow[]>([]);
  const [tick, setTick] = useState(0);
  const [name, setName] = useState("");
  const [labels, setLabels] = useState("");
  const [sel, setSel] = useState("");
  const [full, setFull] = useState<SetFull | null>(null);
  const [add, setAdd] = useState("");
  const [test, setTest] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const train = useRun<Record<string, unknown>>();
  const cls = useRun<Record<string, unknown>>();
  useEffect(() => {
    let live = true;
    getJson<{ sets: SetRow[] }>("/api/fieldbox/text/sets").then((r) => { if (live) setSets(r.sets); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load label sets.")); });
    return () => { live = false; };
  }, [tick]);
  useEffect(() => {
    if (!sel) return;
    let live = true;
    getJson<SetFull>(`/api/fieldbox/text/sets/${encodeURIComponent(sel)}`).then((r) => { if (live) setFull(r); }).catch((e) => { if (live) setErr(errMsg(e, "Could not open the set.")); });
    return () => { live = false; };
  }, [sel, tick]);
  const shown = sel ? full : null;
  const base = `/api/fieldbox/text/sets/${encodeURIComponent(sel)}`;
  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Labeled text sets" note="Make a set of categories, label examples, then check honestly how well a simple model learns them. Needs at least a few examples per category.">
        <div className="flex flex-wrap items-end gap-2">
          <TI label="New set name" value={name} onChange={setName} w="w-48" />
          <TI label="Categories, separated by commas" value={labels} onChange={setLabels} w="w-72" placeholder="billing, bug, praise" />
          <button className="btn" disabled={!name.trim() || !labels.trim()} onClick={async () => { setErr(null); try { await postJson("/api/fieldbox/text/sets", { name, labels: labels.split(",").map((x) => x.trim()).filter(Boolean) }); setTick((t) => t + 1); setSel(name); setName(""); setLabels(""); } catch (e) { setErr(errMsg(e, "Could not create the set.")); } }}>Create set</button>
        </div>
        <div className="mt-3 flex flex-wrap items-end gap-2">
          <Pick label="Label set" value={sel} onChange={(v) => { setSel(v); if (!v) setFull(null); train.setRes(null); cls.setRes(null); }} options={sets.map((s) => ({ id: s.name, label: `${s.name} (${s.examples} examples)` }))} />
          {sel && <button className="btn" onClick={async () => { try { await deleteJson(base); setSel(""); setFull(null); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Could not delete.")); } }}>Delete set</button>}
        </div>
      </Section>
      {shown && (
        <>
          <Section title={`Add examples to ${shown.name}`} note={`One per line as: label, text. Categories: ${shown.labels.join(", ")}.`}>
            <TA label="Examples" value={add} onChange={setAdd} rows={5} placeholder="billing, I was charged twice this month" />
            <button className="btn mt-2" disabled={!add.trim()} onClick={async () => { setErr(null); try { await postJson(`${base}/examples`, { text: add }); setAdd(""); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Could not add the examples.")); } }}>Add examples</button>
            {shown.examples.length > 0 && <div className="mt-3 max-h-60 overflow-auto"><Rows columns={["Label", "Text"]} rows={shown.examples.slice(0, 60).map((x) => [x.label, x.text])} caption={`${shown.total} examples`} /></div>}
          </Section>
          <Section title="Train and check" note="Compared with always guessing the most common label. Scores come from texts the model had not seen.">
            <button className="btn" disabled={train.busy} onClick={() => train.run(() => postJson(`${base}/train`, {}), "Could not train.")}>{train.busy ? "Working…" : "Train and report"}</button>
            {train.err && <ErrorBanner message={train.err} />}
            <Out data={train.res} hide={["set", "history"]} />
            <div className="mt-4 border-t border-line pt-3">
              <TA label="Texts to sort (one per line)" value={test} onChange={setTest} rows={3} />
              <button className="btn mt-2" disabled={cls.busy || !test.trim()} onClick={() => cls.run(() => postJson(`${base}/classify`, { texts: lines(test) }), "Could not sort the texts.")}>Sort these</button>
              {cls.err && <ErrorBanner message={cls.err} />}
              <Out data={cls.res} />
            </div>
          </Section>
        </>
      )}
    </div>
  );
}

function Extract() {
  const [rules, setRules] = useState("amount, Total due:?\\s*\\$?([0-9,.]+)\ndate, Date:?\\s*([0-9]{4}-[0-9]{2}-[0-9]{2})");
  const [docs, setDocs] = useState("Invoice\nDate: 2026-03-01\nTotal due: $120.50\n---\nInvoice\nDate: 2026-03-09\nTotal due $98.00");
  const [exp, setExp] = useState("amount=120.50, date=2026-03-01\namount=98.00, date=2026-03-09");
  const r = useRun<Record<string, unknown>>();
  function build() {
    const ex = lines(exp).map((l) => Object.fromEntries(l.split(",").map((p) => { const i = p.indexOf("="); return [p.slice(0, i).trim(), p.slice(i + 1).trim()]; })));
    return { rules: lines(rules).map((l) => { const i = l.indexOf(","); return { field: l.slice(0, i).trim(), pattern: l.slice(i + 1).trim() }; }), docs: docs.split(/\n---\n/).map((t, i) => ({ text: t, expected: ex[i] ?? {} })) };
  }
  return (
    <Section title="Extraction tester" note="Try patterns (regular expressions) that pull fields from documents, and see which were right, wrong or missed. Separate sample documents with a line of ---.">
      {r.err && <ErrorBanner message={r.err} />}
      <div className="grid gap-2">
        <TA label="Field rules (field name, pattern with one group)" value={rules} onChange={setRules} rows={3} />
        <TA label="Sample documents" value={docs} onChange={setDocs} rows={7} />
        <TA label="Expected values for each document, one line each (field=value, field=value)" value={exp} onChange={setExp} rows={3} />
        <div><button className="btn" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/text/extract", build()), "Could not test the rules.")}>Test extraction</button></div>
      </div>
      <Out data={r.res} />
    </Section>
  );
}

type Run = { id: string; name: string; params: Record<string, string>; metrics: Record<string, number>; notes: string; dataset: string; at: string };
function Experiments() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [tick, setTick] = useState(0);
  const [f, setF] = useState({ name: "", params: "", metrics: "", dataset: "", notes: "" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    getJson<{ runs: Run[] }>("/api/fieldbox/experiments").then((r) => { if (live) setRuns(r.runs); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load runs.")); });
    return () => { live = false; };
  }, [tick]);
  const kv = (s: string) => Object.fromEntries(s.split(",").map((p) => p.split("=").map((x) => x.trim())).filter((p) => p[0] && p[1] !== undefined));
  async function csv() {
    try {
      const r = await apiFetch(`${API_BASE}/api/fieldbox/experiments.csv`);
      const u = URL.createObjectURL(await r.blob());
      const a = document.createElement("a"); a.href = u; a.download = "experiments.csv"; a.click();
      setTimeout(() => URL.revokeObjectURL(u), 2000);
    } catch (e) { setErr(errMsg(e, "Could not download.")); }
  }
  return (
    <Section title="Experiment tracker" note="Write down every run: what you changed and the scores. Change one thing at a time so you can tell what helped.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2">
        <div className="flex flex-wrap gap-2"><TI label="Run name" value={f.name} onChange={(x) => setF({ ...f, name: x })} w="w-56" /><TI label="Data used" value={f.dataset} onChange={(x) => setF({ ...f, dataset: x })} w="w-48" /></div>
        <TI label="Settings (name=value, name=value)" value={f.params} onChange={(x) => setF({ ...f, params: x })} w="w-96" placeholder="model=logreg, C=1" />
        <TI label="Scores (name=number, name=number)" value={f.metrics} onChange={(x) => setF({ ...f, metrics: x })} w="w-96" placeholder="accuracy=0.84, f1=0.8" />
        <TI label="Notes" value={f.notes} onChange={(x) => setF({ ...f, notes: x })} w="w-96" />
        <div className="flex gap-2">
          <button className="btn" disabled={!f.name.trim() || !f.metrics.trim()} onClick={async () => { setErr(null); try { await postJson("/api/fieldbox/experiments", { name: f.name, dataset: f.dataset, notes: f.notes, params: kv(f.params), metrics: kv(f.metrics) }); setF({ name: "", params: "", metrics: "", dataset: "", notes: "" }); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Could not save the run.")); } }}>Log run</button>
          {runs.length > 0 && <button className="btn" onClick={csv}>Download CSV</button>}
        </div>
      </div>
      {runs.length > 0 && <div className="mt-3"><Rows caption="Runs, newest first" columns={["Run", "Data", "Settings", "Scores", "When", "Notes"]} rows={runs.map((r) => [r.name, r.dataset, Object.entries(r.params).map(([k, v]) => `${k}=${v}`).join(", "), Object.entries(r.metrics).map(([k, v]) => `${k}=${v}`).join(", "), r.at, r.notes])} /></div>}
      {runs.length > 0 && <div className="mt-2 flex flex-wrap gap-2">{runs.slice(0, 8).map((r) => <button key={r.id} className="btn" aria-label={`Delete run ${r.name}`} onClick={async () => { try { await deleteJson(`/api/fieldbox/experiments/${r.id}`); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Could not delete.")); } }}>Delete {r.name}</button>)}</div>}
    </Section>
  );
}
