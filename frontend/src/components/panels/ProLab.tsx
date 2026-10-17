"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Table, Tabs, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
type Field = { k: string; label: string; default: string; area?: boolean };
type RefSection = { title: string; items?: string[]; head?: string[]; rows?: string[][] };
type Tab = { id: string; label: string; kind: "tool" | "ref"; help?: string; fields?: Field[]; sections?: RefSection[] };
type Spec = { track: string; title: string; tabs: Tab[]; note: string };

let indexPromise: Promise<string[]> | null = null;
function labTracks(): Promise<string[]> {
  if (!indexPromise) indexPromise = getJson<{ tracks: string[] }>("/api/prolab").then((r) => r.tracks).catch(() => { indexPromise = null; return []; });
  return indexPromise;
}

const label = (k: string) => k.replace(/_/g, " ");
const CODE = new Set(["verilog", "workflow_yaml", "mermaid", "report_text", "sql", "document", "text"]);
const isScalar = (v: unknown) => ["string", "number", "boolean"].includes(typeof v) || v === null;
const show = (v: unknown) => (v === null ? "n/a" : typeof v === "boolean" ? (v ? "yes" : "no") : String(v));

function Value({ v }: { v: any }) {
  if (isScalar(v)) return <>{show(v)}</>;
  if (Array.isArray(v)) {
    if (v.length && v.every((x) => x && typeof x === "object" && !Array.isArray(x))) {
      const head = Array.from(new Set(v.flatMap((x) => Object.keys(x))));
      return <Table head={head.map(label)} rows={v.map((x) => head.map((h) => <Value key={h} v={x[h]} />))} />;
    }
    return <ul className="list-disc pl-5">{v.map((x, i) => <li key={i}><Value v={x} /></li>)}</ul>;
  }
  return <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5">{Object.entries(v).map(([k, x]) => <div key={k} className="contents"><dt className="text-muted">{label(k)}</dt><dd><Value v={x} /></dd></div>)}</dl>;
}

function Result({ out }: { out: R }) {
  const scalars = Object.entries(out).filter(([k, v]) => isScalar(v) && !CODE.has(k) && k !== "note" && k !== "verdict");
  const rest = Object.entries(out).filter(([k, v]) => !isScalar(v) && !["note"].includes(k));
  const code = Object.entries(out).filter(([k, v]) => CODE.has(k) && typeof v === "string");
  return (
    <div className="mt-3 space-y-3 text-sm" role="status">
      {typeof out.verdict === "string" && <p><Badge tone="muted">result</Badge> <strong>{out.verdict}</strong></p>}
      {scalars.length > 0 && <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1">{scalars.map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{label(k)}</dt><dd>{show(v)}</dd></div>)}</dl>}
      {rest.map(([k, v]) => <div key={k}><div className="text-xs font-semibold uppercase tracking-wide text-muted">{label(k)}</div><div className="text-xs"><Value v={v} /></div></div>)}
      {code.map(([k, v]) => <div key={k}><div className="text-xs font-semibold uppercase tracking-wide text-muted">{label(k)}</div><pre className="overflow-x-auto whitespace-pre-wrap rounded border border-line p-2 font-mono text-xs">{v as string}</pre></div>)}
      {out.note && <p className="text-xs text-muted">{out.note}</p>}
    </div>
  );
}

/** Advanced lab for a field: calculators and reference tabs defined once on the server. Shows nothing when a field has no lab. */
export function ProLab({ track }: { track: string }) {
  const [has, setHas] = useState(false);
  const [spec, setSpec] = useState<Spec | null>(null);
  const [tab, setTab] = useState("");
  const [vals, setVals] = useState<Record<string, string>>({});
  const [out, setOut] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    labTracks().then((t) => { if (live) setHas(t.includes(track)); });
    return () => { live = false; };
  }, [track]);
  useEffect(() => {
    if (!has) return;
    let live = true;
    getJson<Spec>(`/api/prolab/${track}`).then((s) => { if (live) { setSpec(s); setTab(s.tabs[0]?.id ?? ""); } }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load the advanced lab.")); });
    return () => { live = false; };
  }, [has, track]);

  if (!has) return null;
  const cur = spec?.tabs.find((t) => t.id === tab);
  const val = (f: Field) => vals[`${tab}.${f.k}`] ?? f.default;
  async function go() {
    if (!cur?.fields) return;
    setErr(null);
    setBusy(true);
    const body: Record<string, string> = {};
    cur.fields.forEach((f) => { body[f.k] = val(f); });
    try { setOut(await postJson<R>(`/api/prolab/${track}/run/${cur.id}`, body)); } catch (e) { setOut(null); setErr(errMsg(e, "Check what you entered.")); }
    setBusy(false);
  }
  return (
    <section className="card space-y-3 p-4" aria-label="Advanced lab">
      <h2 className="text-base font-semibold">{spec?.title ?? "Advanced lab"}</h2>
      <p className="text-xs text-muted">{spec?.note ?? "Loading…"} Everything runs on this computer from what you type. Estimates to check, not answers.</p>
      {err && <ErrorBanner message={err} />}
      {spec && <Tabs tabs={spec.tabs.map((t) => ({ id: t.id, label: t.label }))} value={tab} onChange={(v) => { setTab(v); setOut(null); setErr(null); }} label="Advanced tools" />}
      {cur?.kind === "tool" && (
        <Section title={cur.label} note={cur.help}>
          <div className="grid gap-2 sm:grid-cols-2">
            {cur.fields?.map((f) => (
              <label key={f.k} className={`text-xs ${f.area ? "sm:col-span-2" : ""}`}>{f.label}
                {f.area ? <textarea className="input mt-1 w-full font-mono" rows={5} value={val(f)} onChange={(e) => setVals((s) => ({ ...s, [`${tab}.${f.k}`]: e.target.value }))} />
                  : <input className="input mt-1 w-full" value={val(f)} onChange={(e) => setVals((s) => ({ ...s, [`${tab}.${f.k}`]: e.target.value }))} />}
              </label>
            ))}
          </div>
          <button className="btn mt-2" onClick={go} disabled={busy}>{busy ? "Working…" : "Run"}</button>
          {out && <Result out={out} />}
        </Section>
      )}
      {cur?.kind === "ref" && (
        <div className="space-y-3 text-sm">
          {cur.sections?.map((s) => (
            <Section key={s.title} title={s.title}>
              {s.items && <ul className="list-disc pl-5 text-xs">{s.items.map((x, i) => <li key={i}>{x}</li>)}</ul>}
              {s.head && s.rows && <Table head={s.head} rows={s.rows} />}
            </Section>
          ))}
        </div>
      )}
    </section>
  );
}
