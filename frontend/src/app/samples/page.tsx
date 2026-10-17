"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Badge, Field, Section, errMsg } from "@/components/panels/kit";
import { API_BASE, deleteJson, getJson, postJson, putJson } from "@/lib/api";

/* eslint-disable @typescript-eslint/no-explicit-any */
type It = Record<string, any>;
type Svc = { name: string; blurb: string };
interface S { profile: { name: string; headline: string; about: string; area: string; contact: string; services: Svc[] }; items: It[]; kinds: Record<string, string>; label: string; rules: string[]; starters: { n: number; title: string; kind: string }[] }

const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

function ItemForm({ kinds, init, onSave, onCancel }: { kinds: Record<string, string>; init: It | null; onSave: (b: It) => Promise<void>; onCancel: () => void }) {
  const [kind, setKind] = useState<string>(init?.kind ?? "before_after");
  const [f, setF] = useState<Record<string, string>>((): Record<string, string> => {
    if (!init) return {};
    return {
      title: init.title ?? "", summary: init.summary ?? "", before: init.before ?? "", after: init.after ?? "", what_i_did: init.what_i_did ?? "", terms: init.terms ?? "", takeaway: init.takeaway ?? "",
      lines: (init.lines ?? []).map((x: It) => `${x.desc}, ${x.qty}, ${x.rate}`).join("\n"), steps: (init.steps ?? []).join("\n"), kpis: (init.kpis ?? []).map((x: It) => `${x.label}, ${x.value}`).join("\n"),
    };
  });
  const [err, setErr] = useState<string | null>(null);
  const v = (k: string) => f[k] ?? "";
  const set = (k: string) => (e: { target: { value: string } }) => setF((s) => ({ ...s, [k]: e.target.value }));
  async function save() {
    setErr(null);
    const b: It = { kind, title: v("title"), summary: v("summary") };
    try {
      if (kind === "before_after") Object.assign(b, { before: v("before"), after: v("after"), what_i_did: v("what_i_did") });
      else if (kind === "quote") {
        b.terms = v("terms");
        b.lines = lines(v("lines")).map((l) => { const p = l.split(","); const rate = p.pop() ?? ""; const qty = p.pop() ?? ""; return { desc: p.join(",").trim(), qty: qty.trim(), rate: rate.trim().replace("$", "") }; });
      } else if (kind === "checklist") b.steps = lines(v("steps"));
      else { b.takeaway = v("takeaway"); b.kpis = lines(v("kpis")).map((l) => { const i = l.indexOf(","); return { label: l.slice(0, i).trim(), value: l.slice(i + 1).trim() }; }); }
      await onSave(b);
    } catch (e) { setErr(errMsg(e, "Could not save that sample.")); }
  }
  return (
    <div className="space-y-2 rounded border border-line p-3">
      {err && <ErrorBanner message={err} />}
      <Field label="Type"><select className="input" value={kind} onChange={(e) => setKind(e.target.value)} disabled={!!init}>{Object.entries(kinds).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
      <Field label="Title"><input className="input" value={v("title")} onChange={set("title")} maxLength={100} /></Field>
      <Field label="One-line summary (optional)"><input className="input" value={v("summary")} onChange={set("summary")} maxLength={400} /></Field>
      {kind === "before_after" && (<>
        <Field label="Before"><textarea className="input" rows={2} value={v("before")} onChange={set("before")} /></Field>
        <Field label="After"><textarea className="input" rows={2} value={v("after")} onChange={set("after")} /></Field>
        <Field label="What I did"><textarea className="input" rows={3} value={v("what_i_did")} onChange={set("what_i_did")} /></Field>
      </>)}
      {kind === "quote" && (<>
        <Field label="Lines, one per line: description, quantity, rate (the total is worked out for you)"><textarea className="input font-mono" rows={4} value={v("lines")} onChange={set("lines")} placeholder="Wi-Fi survey, 1, 85" /></Field>
        <Field label="Terms (optional)"><textarea className="input" rows={2} value={v("terms")} onChange={set("terms")} /></Field>
      </>)}
      {kind === "checklist" && <Field label="Steps, one per line"><textarea className="input" rows={6} value={v("steps")} onChange={set("steps")} /></Field>}
      {kind === "dashboard" && (<>
        <Field label="Made-up numbers, one per line: label, value"><textarea className="input font-mono" rows={4} value={v("kpis")} onChange={set("kpis")} placeholder="Revenue, $18,400" /></Field>
        <Field label="Takeaway (optional)"><textarea className="input" rows={2} value={v("takeaway")} onChange={set("takeaway")} /></Field>
      </>)}
      <p className="text-xs text-muted">No names, emails, phone numbers or reviews. Use practice data only.</p>
      <div className="flex gap-2"><button className="btn btn-primary" onClick={save}>Save sample</button><button className="btn" onClick={onCancel}>Cancel</button></div>
    </div>
  );
}

export default function SamplesPage() {
  const [s, setS] = useState<S | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ok, setOk] = useState("");
  const [p, setP] = useState<S["profile"] | null>(null);
  const [svc, setSvc] = useState("");
  const [editing, setEditing] = useState<string | "new" | null>(null);
  const [prev, setPrev] = useState("");
  const [showPrev, setShowPrev] = useState(false);

  const apply = useCallback((r: S) => { setS(r); setP(r.profile); setSvc(r.profile.services.map((x) => `${x.name}: ${x.blurb}`).join("\n")); }, []);
  useEffect(() => { getJson<S>("/api/samples").then(apply).catch((e) => setErr(errMsg(e, "Couldn't load the sample page."))); }, [apply]);
  useEffect(() => {
    if (!showPrev) return;
    let live = true;
    fetch(`${API_BASE}/api/samples/html`).then((r) => r.text()).then((t) => { if (live) setPrev(t); }).catch(() => { if (live) setPrev("<p>Couldn't build the preview.</p>"); });
    return () => { live = false; };
  }, [showPrev, s]);

  async function act(fn: () => Promise<S>, msg = "") {
    setErr(null);
    setOk("");
    try { apply(await fn()); if (msg) setOk(msg); } catch (e) { setErr(errMsg(e, "That didn't work.")); }
  }
  const saveProfile = () => p && act(() => putJson<S>("/api/samples/profile", { ...p, services: lines(svc).map((l) => { const i = l.indexOf(":"); return i < 0 ? { name: l, blurb: "" } : { name: l.slice(0, i).trim(), blurb: l.slice(i + 1).trim() }; }) }), "Saved.");

  return (
    <PageShell title="Sample work page" subtitle="A separate page for prospects, built only from labelled practice work. Nothing is published or sent from here.">
      <div className="grid gap-4">
        {err && <ErrorBanner message={err} />}
        {ok && <p role="status" className="text-sm text-emerald-600">{ok}</p>}
        {s && p && (<>
          <Section title="Rules this page follows" note="Built into the page, so it cannot drift.">
            <ul className="list-disc pl-5 text-sm">{s.rules.map((r) => <li key={r}>{r}</li>)}</ul>
          </Section>
          <Section title="About you">
            <div className="grid gap-2 sm:grid-cols-2">
              <Field label="Business name"><input className="input" value={p.name} onChange={(e) => setP({ ...p, name: e.target.value })} maxLength={80} /></Field>
              <Field label="Service area"><input className="input" value={p.area} onChange={(e) => setP({ ...p, area: e.target.value })} maxLength={120} /></Field>
              <div className="sm:col-span-2"><Field label="Headline"><input className="input" value={p.headline} onChange={(e) => setP({ ...p, headline: e.target.value })} maxLength={140} /></Field></div>
              <div className="sm:col-span-2"><Field label="About (optional, only things you can prove)"><textarea className="input" rows={3} value={p.about} onChange={(e) => setP({ ...p, about: e.target.value })} /></Field></div>
              <div className="sm:col-span-2"><Field label="Services, one per line as: name: short description"><textarea className="input" rows={4} value={svc} onChange={(e) => setSvc(e.target.value)} placeholder="Computer repair: diagnosis, fixes and data backup" /></Field></div>
              <div className="sm:col-span-2"><Field label="Your contact line (the only place a real email or phone belongs)"><input className="input" value={p.contact} onChange={(e) => setP({ ...p, contact: e.target.value })} maxLength={160} /></Field></div>
            </div>
            <button className="btn btn-primary mt-2" onClick={saveProfile}>Save details</button>
          </Section>
          <Section title={`Sample work (${s.items.length})`} note="Each one is stamped with the sample label on the page.">
            <div className="mb-3 flex flex-wrap gap-2">
              <button className="btn" onClick={() => setEditing("new")}>Add a sample</button>
              {s.starters.map((st) => <button key={st.n} className="btn" onClick={() => act(() => postJson<S>(`/api/samples/starters/${st.n}`, {}), "Added. Edit it so it shows your own work.")}>Start from: {st.title}</button>)}
            </div>
            {editing === "new" && <ItemForm kinds={s.kinds} init={null} onCancel={() => setEditing(null)} onSave={async (b) => { apply(await postJson<S>("/api/samples/items", b)); setEditing(null); }} />}
            <ul className="space-y-2">
              {s.items.map((it, i) => (
                <li key={it.id} className="rounded border border-line p-3">
                  {editing === it.id ? <ItemForm kinds={s.kinds} init={it} onCancel={() => setEditing(null)} onSave={async (b) => { apply(await putJson<S>(`/api/samples/items/${it.id}`, b)); setEditing(null); }} /> : (
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div><Badge>{s.kinds[it.kind]}</Badge> <strong>{it.title}</strong></div>
                      <div className="flex gap-1 text-xs">
                        <button className="btn" disabled={i === 0} onClick={() => act(() => postJson<S>(`/api/samples/items/${it.id}/move/-1`, {}))} aria-label="Move up">Up</button>
                        <button className="btn" disabled={i === s.items.length - 1} onClick={() => act(() => postJson<S>(`/api/samples/items/${it.id}/move/1`, {}))} aria-label="Move down">Down</button>
                        <button className="btn" onClick={() => setEditing(it.id)}>Edit</button>
                        <button className="btn" onClick={() => act(() => deleteJson<S>(`/api/samples/items/${it.id}`))}>Remove</button>
                      </div>
                    </div>
                  )}
                </li>
              ))}
            </ul>
            {s.items.length === 0 && <p className="text-sm text-muted">No samples yet. Start from one of the examples above and change it to your own practice work.</p>}
          </Section>
          <Section title="Preview and download" note="Preview shows exactly what the file contains. The file makes no outside requests and has no scripts.">
            <div className="flex flex-wrap gap-2">
              <button className="btn" onClick={() => setShowPrev((x) => !x)}>{showPrev ? "Hide preview" : "Show preview"}</button>
              <a className="btn btn-primary" href={`${API_BASE}/api/samples/html?download=true`}>Download sample-work.html</a>
            </div>
            {showPrev && <iframe title="Sample work page preview" sandbox="" srcDoc={prev} className="mt-3 h-[34rem] w-full rounded border border-line bg-white" />}
            <p className="mt-2 text-xs text-muted">Before you share it: read every line, confirm nothing is a real client&apos;s, and remember a page you host is public.</p>
          </Section>
        </>)}
      </div>
    </PageShell>
  );
}
