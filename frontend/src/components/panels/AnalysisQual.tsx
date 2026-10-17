"use client";
import { acceptFor, checkFile, readableFile } from "@/lib/fileCheck";
import { useEffect, useRef, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postForm, postJson, putJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, errMsg, num } from "./kit";
import { ColSelect, Lesson, Sentences, useRun, type Col } from "./analysisKit";

// ---------------------------------------------------------------- notes (post-mortems, SWOT, scenarios...)
interface FieldDef { name: string; type: string; choices: string[] | null; label: string; hint: string }
interface Kind { kind: string; horizon: string; label: string; blurb: string; fields: FieldDef[] }
interface Opt { name: string; probability: number; payoff: number; note: string }
interface Risk { reason: string; likelihood: string; impact: string; mitigation: string }
type Val = string | string[] | Opt[] | Risk[];
interface Item {
  id: string; kind: string; title: string; created: string; data: Record<string, Val>;
  computed?: { expected_value?: number; probability_total?: number; balanced?: boolean; best?: string; worst?: string; spread?: number; warning?: string | null;
    ranked?: (Risk & { score: number })[]; unmitigated_high?: number; counts?: Record<string, number> };
}
interface Payload { schema: Kind[]; items: Item[] }

const LEVELS = ["low", "medium", "high"];

function emptyFor(f: FieldDef): Val {
  if (f.type === "list" || f.type === "options" || f.type === "risks") return [];
  if (f.type === "enum") return f.choices?.[0] ?? "";
  return "";
}

function FieldEditor({ f, v, set }: { f: FieldDef; v: Val; set: (v: Val) => void }) {
  if (f.type === "text") return <Field label={f.label}><textarea className="field min-h-20" maxLength={4000} value={v as string} placeholder={f.hint} onChange={(e) => set(e.target.value)} /></Field>;
  if (f.type === "line") return <Field label={f.label}><input className="field" maxLength={200} value={v as string} placeholder={f.hint} onChange={(e) => set(e.target.value)} /></Field>;
  if (f.type === "date") return <Field label={f.label}><input className="field" type="date" value={v as string} onChange={(e) => set(e.target.value)} /></Field>;
  if (f.type === "enum") return <Field label={f.label}><select className="field" value={v as string} onChange={(e) => set(e.target.value)}>{f.choices?.map((c) => <option key={c}>{c}</option>)}</select></Field>;
  if (f.type === "list") {
    const arr = v as string[];
    return (
      <Field label={`${f.label} (one per line)`}>
        <textarea className="field min-h-16" value={arr.join("\n")} onChange={(e) => set(e.target.value.split("\n"))} />
      </Field>
    );
  }
  if (f.type === "options") {
    const arr = v as Opt[];
    const upd = (i: number, p: Partial<Opt>) => set(arr.map((o, j) => (j === i ? { ...o, ...p } : o)));
    return (
      <fieldset className="space-y-2"><legend className="text-xs text-muted">{f.label}: name, chance of it happening (%), payoff</legend>
        {arr.map((o, i) => (
          <div key={i} className="grid gap-2 sm:grid-cols-[2fr_1fr_1fr_auto]">
            <input className="field" aria-label={`Scenario ${i + 1} name`} placeholder="Scenario" value={o.name} onChange={(e) => upd(i, { name: e.target.value })} />
            <input className="field" aria-label={`Scenario ${i + 1} chance in percent`} inputMode="decimal" placeholder="Chance %" value={o.probability} onChange={(e) => upd(i, { probability: e.target.value as unknown as number })} />
            <input className="field" aria-label={`Scenario ${i + 1} payoff`} inputMode="decimal" placeholder="Payoff" value={o.payoff} onChange={(e) => upd(i, { payoff: e.target.value as unknown as number })} />
            <button className="btn" aria-label={`Remove scenario ${i + 1}`} onClick={() => set(arr.filter((_, j) => j !== i))}>×</button>
          </div>
        ))}
        <button className="btn" onClick={() => set([...arr, { name: "", probability: 0, payoff: 0, note: "" }])}>Add a scenario</button>
      </fieldset>
    );
  }
  const arr = v as Risk[];
  const upd = (i: number, p: Partial<Risk>) => set(arr.map((o, j) => (j === i ? { ...o, ...p } : o)));
  return (
    <fieldset className="space-y-2"><legend className="text-xs text-muted">{f.label}</legend>
      {arr.map((o, i) => (
        <div key={i} className="grid gap-2 sm:grid-cols-[3fr_1fr_1fr_3fr_auto]">
          <input className="field" aria-label={`Risk ${i + 1} reason`} placeholder="What goes wrong" value={o.reason} onChange={(e) => upd(i, { reason: e.target.value })} />
          <select className="field" aria-label={`Risk ${i + 1} likelihood`} value={o.likelihood} onChange={(e) => upd(i, { likelihood: e.target.value })}>{LEVELS.map((l) => <option key={l} value={l}>likely: {l}</option>)}</select>
          <select className="field" aria-label={`Risk ${i + 1} impact`} value={o.impact} onChange={(e) => upd(i, { impact: e.target.value })}>{LEVELS.map((l) => <option key={l} value={l}>impact: {l}</option>)}</select>
          <input className="field" aria-label={`Risk ${i + 1} mitigation`} placeholder="What prevents it" value={o.mitigation} onChange={(e) => upd(i, { mitigation: e.target.value })} />
          <button className="btn" aria-label={`Remove risk ${i + 1}`} onClick={() => set(arr.filter((_, j) => j !== i))}>×</button>
        </div>
      ))}
      <button className="btn" onClick={() => set([...arr, { reason: "", likelihood: "medium", impact: "medium", mitigation: "" }])}>Add a way it could fail</button>
    </fieldset>
  );
}

function ItemView({ it, k }: { it: Item; k: Kind }) {
  const c = it.computed;
  return (
    <div className="space-y-2 text-sm">
      {k.fields.map((f) => {
        const v = it.data[f.name];
        if (f.type === "options") {
          const o = (v as Opt[]) ?? [];
          return o.length ? <div key={f.name}><Table head={["Scenario", "Chance", "Payoff"]} rows={o.map((x) => [x.name, `${num(x.probability, 1)}%`, num(x.payoff, 2)])} />
            {c && <p className="mt-1">Probability-weighted value: <b>{num(c.expected_value, 2)}</b>. Best {c.best}, worst {c.worst}, spread {num(c.spread, 2)}.</p>}
            {c?.warning && <p className="mt-1 rounded px-2 py-1" style={{ background: "var(--warn-bg)" }}>{c.warning}</p>}</div> : null;
        }
        if (f.type === "risks") {
          const r = c?.ranked ?? [];
          return r.length ? <div key={f.name}><Table head={["Way it could fail", "Likely", "Impact", "Score", "Prevention"]} rows={r.map((x) => [x.reason, x.likelihood, x.impact, String(x.score), x.mitigation || <Badge key="b" tone="warn">none yet</Badge>])} />
            {!!c?.unmitigated_high && <p className="mt-1 text-muted">{c.unmitigated_high} serious risk(s) have no prevention written yet.</p>}</div> : null;
        }
        if (f.type === "list") {
          const l = (v as string[]) ?? [];
          return l.length ? <div key={f.name}><b>{f.label}</b><ul className="list-disc pl-5">{l.map((x, i) => <li key={i}>{x}</li>)}</ul></div> : null;
        }
        return v ? <p key={f.name}><b>{f.label}:</b> <span className="whitespace-pre-wrap">{String(v)}</span></p> : null;
      })}
    </div>
  );
}

export function QualTab({ kinds }: { kinds: string[] }) {
  const [kind, setKind] = useState(kinds[0]);
  const [p, setP] = useState<Payload | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [form, setForm] = useState<Record<string, Val>>({});
  const [editing, setEditing] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { getJson<Payload>("/api/stats/qual").then(setP).catch((e) => setErr(errMsg(e, "Couldn't load your notes."))); }, []);
  const reload = () => getJson<Payload>("/api/stats/qual").then(setP).catch((e) => setErr(errMsg(e, "Couldn't load your notes.")));
  const k = p?.schema.find((s) => s.kind === kind);
  const reset = () => { setTitle(""); setForm({}); setEditing(null); };
  const items = (p?.items ?? []).filter((i) => i.kind === kind);
  const val = (f: FieldDef): Val => form[f.name] ?? emptyFor(f);
  const save = async () => {
    if (!k) return;
    setBusy(true); setErr(null);
    const data: Record<string, Val> = {};
    k.fields.forEach((f) => { data[f.name] = val(f); });
    try {
      if (editing) await putJson(`/api/stats/qual/${editing}`, { title, data });
      else await postJson("/api/stats/qual", { kind, title, data });
      reset(); await reload();
    } catch (e) { setErr(errMsg(e, "Couldn't save that.")); } finally { setBusy(false); }
  };
  const edit = (it: Item) => { setEditing(it.id); setTitle(it.title); setForm({ ...it.data }); };
  const remove = async (id: string) => { setErr(null); try { await deleteJson(`/api/stats/qual/${id}`); if (editing === id) reset(); await reload(); } catch (e) { setErr(errMsg(e, "Couldn't delete that.")); } };
  if (!p) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  const offered = p.schema.filter((s) => kinds.includes(s.kind));
  return (
    <div className="space-y-4">
      {offered.length > 1 && (
        <Field label="What kind of note?"><select className="field" value={kind} onChange={(e) => { setKind(e.target.value); reset(); }}>{offered.map((s) => <option key={s.kind} value={s.kind}>{s.label}</option>)}</select></Field>
      )}
      {k && <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">{k.blurb} These are your own judgement written down: the page stores them and does the arithmetic, it does not decide for you.</p>}
      {err && <ErrorBanner message={err} />}
      {k && (
        <Section title={editing ? `Editing: ${k.label}` : `New ${k.label.toLowerCase()}`}>
          <div className="space-y-3">
            <Field label="Title"><input className="field" maxLength={140} value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
            {k.fields.map((f) => <FieldEditor key={`${kind}-${f.name}`} f={f} v={val(f)} set={(v) => setForm({ ...form, [f.name]: v })} />)}
            <div className="flex gap-2">
              <button className="btn btn-primary" disabled={busy || !title.trim()} onClick={save}>{busy ? "Saving…" : editing ? "Save changes" : "Save note"}</button>
              {editing && <button className="btn" onClick={reset}>Cancel</button>}
            </div>
          </div>
        </Section>
      )}
      <Section title={k ? `Saved: ${k.label}` : "Saved notes"}>
        {items.length === 0 ? <p className="text-sm text-muted">Nothing saved yet.</p> : (
          <ul className="divide-y divide-line">
            {items.map((it) => (
              <li key={it.id} className="space-y-2 py-3">
                <div className="flex flex-wrap items-center gap-2"><b>{it.title}</b><span className="text-xs text-muted">{it.created.slice(0, 10)}</span>
                  <span className="ml-auto flex gap-2"><button className="btn" onClick={() => edit(it)}>Edit</button><button className="btn" aria-label={`Delete ${it.title}`} onClick={() => remove(it.id)}>Delete</button></span></div>
                {k && <ItemView it={it} k={k} />}
              </li>
            ))}
          </ul>
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- theme finder
interface Themes {
  documents: number; origin: string[]; sentences: string[]; lesson: string;
  terms: { term: string; count: number; docs: number; doc_pct: number }[];
  phrases: { phrase: string; docs: number }[];
  sentiment: { counts: Record<string, number>; top_positive: [string, number][]; top_negative: [string, number][]; items: { snippet: string; label: string }[] };
  examples: Record<string, string>;
}
export function ThemesTab({ source, cols }: { source: string; cols: Col[] }) {
  const texts = cols.filter((c) => c.kind === "text");
  const [text, setText] = useState("");
  const [col, setCol] = useState("");
  const [notes, setNotes] = useState(false);
  const r = useRun<Themes>();
  const [upErr, setUpErr] = useState<string | null>(null);
  const [upBusy, setUpBusy] = useState(false);
  const [up, setUp] = useState<Themes | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const data = up ?? r.data;
  const upload = async (f: File) => {
    setUpErr(null);
    const bad = checkFile(f, "text");
    if (bad) { setUpErr(bad); return; }
    setUpBusy(true);
    try { const fd = new FormData(); fd.append("file", await readableFile(f)); setUp(await postForm<Themes>("/api/stats/themes/upload", fd)); } catch (e) { setUpErr(errMsg(e, "Couldn't read that file.")); } finally { setUpBusy(false); }
  };
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Turn comments, notes or reviews into counts: which words and phrases come up most, and a rough positive/negative lean. Paste text (separate comments with a blank line), pick a text column from your data, include your saved notes, or upload a .txt, .md, .log, .csv or .pdf file.</p>
      <Field label="Paste text"><textarea className="field min-h-28" maxLength={200000} value={text} onChange={(e) => setText(e.target.value)} placeholder={"The delivery was late again.\n\nGreat support, fast answer."} /></Field>
      <div className="grid gap-2 sm:grid-cols-2">
        <ColSelect label={`Or a text column from ${source === "operations" ? "operations" : source}`} value={col} onChange={setCol} cols={texts} none="None" />
        <label className="flex items-center gap-2 pt-5 text-sm"><input type="checkbox" checked={notes} onChange={(e) => setNotes(e.target.checked)} />Include my saved notes</label>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn btn-primary" disabled={r.busy || (!text.trim() && !col && !notes)} onClick={() => { setUp(null); r.run("/api/stats/themes", { text: text || null, source: col ? source : null, text_col: col || null, include_notes: notes, top: 15 }); }}>{r.busy ? "Reading…" : "Find themes"}</button>
        <input ref={fileRef} type="file" accept={acceptFor("text")} className="sr-only" aria-label="Upload a text file or PDF" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ""; }} />
        <button className="btn" disabled={upBusy} onClick={() => fileRef.current?.click()}>{upBusy ? "Reading…" : "Upload a file instead"}</button>
      </div>
      {(r.err || upErr) && <ErrorBanner message={(r.err || upErr) as string} />}
      {data && (
        <div className="space-y-4">
          <Sentences items={data.sentences} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Positive lean" value={String(data.sentiment.counts.positive)} />
            <Stat label="Neutral" value={String(data.sentiment.counts.neutral)} />
            <Stat label="Negative lean" value={String(data.sentiment.counts.negative)} />
          </div>
          <Section title="Most common words"><Table head={["Word", "Times", "In pieces of text", "Share", "Example"]} rows={data.terms.map((t) => [t.term, String(t.count), String(t.docs), `${t.doc_pct}%`, <span key="e" className="text-xs text-muted">{data.examples[t.term] ?? ""}</span>])} /></Section>
          {data.phrases.length > 0 && <Section title="Phrases that repeat"><Table head={["Phrase", "In pieces of text"]} rows={data.phrases.map((p) => [p.phrase, String(p.docs)])} /></Section>}
          <Section title="What drives the lean">
            <p className="text-sm"><b>Positive words:</b> {data.sentiment.top_positive.map(([w, n]) => `${w} (${n})`).join(", ") || "none"}</p>
            <p className="text-sm"><b>Negative words:</b> {data.sentiment.top_negative.map(([w, n]) => `${w} (${n})`).join(", ") || "none"}</p>
          </Section>
          <Lesson text={data.lesson} />
        </div>
      )}
    </div>
  );
}
