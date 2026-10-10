"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, patchJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg, num } from "./kit";

const TABS = [
  { id: "tickets", label: "Helpdesk" }, { id: "assets", label: "Inventory" }, { id: "events", label: "Event logs" },
  { id: "checklists", label: "Checklists" }, { id: "capacity", label: "Capacity and RAID" }, { id: "cheats", label: "Cheat sheets" },
];

export function ItPanel({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">
        Personal-scale practice tools: a helpdesk and an inventory you fill in by hand, plus calculators and checklists. They don&apos;t discover or manage real machines.
      </p>
      <Tabs tabs={TABS} value={tab} onChange={onTab} label="IT tools" />
      {tab === "tickets" && <TicketsTab />}
      {tab === "assets" && <AssetsTab />}
      {tab === "events" && <EventsTab />}
      {tab === "checklists" && <ChecklistsTab />}
      {tab === "capacity" && <CapacityTab />}
      {tab === "cheats" && <CheatsTab />}
    </div>
  );
}

// ---------------------------------------------------------------- helpdesk
interface Ticket { id: number; title: string; category: string; category_label: string; priority: string; status: string; requester: string; sla_hours: number; age_hours: number; is_open: boolean; breached: boolean; hours_left: number | null; timeline: { at: string; text: string }[]; checklist: { text: string; done: boolean }[] }
interface TicketData { tickets: Ticket[]; stats: { open: number; total: number; breached_open: number; mean_hours_to_resolve: number | null; resolved_within_sla_pct: number | null }; categories: { id: string; label: string }[]; sla: Record<string, number>; note: string }
const STATUSES = ["open", "in_progress", "waiting", "resolved", "closed"];

function TicketsTab() {
  const [d, setD] = useState<TicketData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState({ title: "", category: "software", priority: "medium", requester: "", note: "" });
  const [sel, setSel] = useState<number | null>(null);
  const [note, setNote] = useState("");
  const load = useCallback(async () => { try { setD(await getJson<TicketData>("/api/it/tickets")); } catch (e) { setErr(errMsg(e, "Couldn't load tickets.")); } }, []);
  useEffect(() => { getJson<TicketData>("/api/it/tickets").then(setD).catch((e) => setErr(errMsg(e, "Couldn't load tickets."))); }, []);
  const act = async (fn: () => Promise<unknown>, m: string) => { setErr(null); try { await fn(); await load(); } catch (e) { setErr(errMsg(e, m)); } };
  const cur = d?.tickets.find((t) => t.id === sel) ?? null;
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {d && (
        <div className="grid gap-3 sm:grid-cols-4">
          <Stat label="Open" value={String(d.stats.open)} sub={`${d.stats.total} total`} />
          <Stat label="Past target" value={String(d.stats.breached_open)} sub="open and over SLA" />
          <Stat label="Mean time to resolve" value={d.stats.mean_hours_to_resolve == null ? "—" : `${num(d.stats.mean_hours_to_resolve)} h`} />
          <Stat label="Resolved in SLA" value={d.stats.resolved_within_sla_pct == null ? "—" : `${d.stats.resolved_within_sla_pct}%`} />
        </div>
      )}
      <Section title="Open a ticket" note={d?.note}>
        <div className="grid gap-2 sm:grid-cols-2">
          <Field label="What is wrong?"><input className="field" maxLength={140} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Who asked?"><input className="field" maxLength={80} value={f.requester} onChange={(e) => setF({ ...f, requester: e.target.value })} /></Field>
          <Field label="Category"><select className="field" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{(d?.categories ?? []).map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}</select></Field>
          <Field label="Priority"><select className="field" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>{Object.keys(d?.sla ?? { medium: 24 }).map((p) => <option key={p} value={p}>{p}</option>)}</select></Field>
        </div>
        <button className="btn btn-primary mt-2" onClick={() => act(async () => { await postJson("/api/it/tickets", f); setF({ ...f, title: "", note: "" }); }, "Couldn't open the ticket.")}>Open ticket</button>
      </Section>
      <Section title="Tickets">
        {!d || d.tickets.length === 0 ? <p className="text-sm text-muted">No tickets yet. Open one above; each category brings a troubleshooting checklist.</p> : (
          <ul className="divide-y divide-line">
            {d.tickets.map((t) => (
              <li key={t.id} className="py-2">
                <button className="flex w-full min-w-0 flex-wrap items-center gap-2 text-left text-sm" onClick={() => setSel(sel === t.id ? null : t.id)} aria-expanded={sel === t.id}>
                  <span className="font-medium">#{t.id} {t.title}</span>
                  <Badge>{t.category_label}</Badge><Badge tone={t.priority === "urgent" || t.priority === "high" ? "warn" : "muted"}>{t.priority}</Badge>
                  <Badge tone={t.is_open ? "muted" : "ok"}>{t.status.replace("_", " ")}</Badge>
                  {t.is_open && <Badge tone={t.breached ? "bad" : "ok"}>{t.breached ? "past SLA" : `${num(t.hours_left)} h left`}</Badge>}
                </button>
              </li>
            ))}
          </ul>
        )}
        {cur && (
          <div className="mt-3 space-y-3 rounded border border-line p-3 text-sm">
            <div className="flex flex-wrap items-end gap-2">
              <Field label="Status"><select className="field" value={cur.status} onChange={(e) => act(() => patchJson(`/api/it/tickets/${cur.id}`, { status: e.target.value }), "Couldn't update.")}>{STATUSES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select></Field>
              <button className="btn" onClick={() => act(async () => { await deleteJson(`/api/it/tickets/${cur.id}`); setSel(null); }, "Couldn't delete.")}>Delete</button>
            </div>
            <div>
              <div className="mb-1 text-xs uppercase tracking-wide text-muted">Troubleshooting steps</div>
              <ul className="space-y-1">
                {cur.checklist.map((c, i) => (
                  <li key={i}><label className="flex items-start gap-2"><input type="checkbox" checked={c.done} onChange={(e) => act(() => patchJson(`/api/it/tickets/${cur.id}`, { tick: { index: i, done: e.target.checked } }), "Couldn't update.")} /><span>{c.text}</span></label></li>
                ))}
              </ul>
            </div>
            <div>
              <div className="mb-1 text-xs uppercase tracking-wide text-muted">Timeline</div>
              <ul className="space-y-1 text-xs">{cur.timeline.map((t, i) => <li key={i}><span className="text-muted">{t.at}</span> {t.text}</li>)}</ul>
              <div className="mt-2 flex gap-2">
                <input className="field min-w-0 flex-1" aria-label="Add a note" maxLength={500} value={note} onChange={(e) => setNote(e.target.value)} placeholder="What did you try or learn?" />
                <button className="btn" disabled={!note.trim()} onClick={() => act(async () => { await patchJson(`/api/it/tickets/${cur.id}`, { note }); setNote(""); }, "Couldn't add the note.")}>Add</button>
              </div>
            </div>
          </div>
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- inventory
interface Asset { id: number; hostname: string; kind: string; os: string; owner: string; serial: string; warranty_end: string | null; status: string; warranty_state: string; warranty_days_left: number | null }
interface AssetData { assets: Asset[]; kinds: string[]; statuses: string[]; stats: { total: number; in_use: number; warranty_expiring: number; warranty_expired: number; by_os: Record<string, number> }; note: string }

function AssetsTab() {
  const [d, setD] = useState<AssetData | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState({ hostname: "", kind: "laptop", os: "", owner: "", serial: "", warranty_end: "", status: "in_use" });
  const load = useCallback(async () => { try { setD(await getJson<AssetData>("/api/it/assets")); } catch (e) { setErr(errMsg(e, "Couldn't load the inventory.")); } }, []);
  useEffect(() => { getJson<AssetData>("/api/it/assets").then(setD).catch((e) => setErr(errMsg(e, "Couldn't load the inventory."))); }, []);
  const act = async (fn: () => Promise<unknown>, m: string) => { setErr(null); try { await fn(); await load(); } catch (e) { setErr(errMsg(e, m)); } };
  const tone = (s: string): "ok" | "warn" | "bad" | "muted" => (s === "ok" ? "ok" : s === "expiring" ? "warn" : s === "expired" ? "bad" : "muted");
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {d && (
        <div className="grid gap-3 sm:grid-cols-4">
          <Stat label="Assets" value={String(d.stats.total)} sub={`${d.stats.in_use} in use`} />
          <Stat label="Warranty expiring" value={String(d.stats.warranty_expiring)} sub="within 90 days" />
          <Stat label="Warranty expired" value={String(d.stats.warranty_expired)} />
          <Stat label="Operating systems" value={String(Object.keys(d.stats.by_os).length)} />
        </div>
      )}
      <Section title="Add an asset" note={d?.note}>
        <div className="grid gap-2 sm:grid-cols-3">
          <Field label="Hostname"><input className="field" maxLength={80} value={f.hostname} onChange={(e) => setF({ ...f, hostname: e.target.value })} /></Field>
          <Field label="Kind"><select className="field" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{(d?.kinds ?? ["laptop"]).map((k) => <option key={k}>{k}</option>)}</select></Field>
          <Field label="Operating system"><input className="field" maxLength={60} value={f.os} onChange={(e) => setF({ ...f, os: e.target.value })} /></Field>
          <Field label="Owner"><input className="field" maxLength={60} value={f.owner} onChange={(e) => setF({ ...f, owner: e.target.value })} /></Field>
          <Field label="Serial"><input className="field" maxLength={60} value={f.serial} onChange={(e) => setF({ ...f, serial: e.target.value })} /></Field>
          <Field label="Warranty ends"><input className="field" type="date" value={f.warranty_end} onChange={(e) => setF({ ...f, warranty_end: e.target.value })} /></Field>
        </div>
        <button className="btn btn-primary mt-2" onClick={() => act(async () => { await postJson("/api/it/assets", f); setF({ ...f, hostname: "", serial: "" }); }, "Couldn't add the asset.")}>Add asset</button>
      </Section>
      <Section title="Inventory">
        {!d || d.assets.length === 0 ? <p className="text-sm text-muted">Nothing here yet.</p> : (
          <Table head={["Host", "Kind", "OS", "Owner", "Warranty", "Status", ""]} caption="Assets" rows={d.assets.map((a) => [
            a.hostname, a.kind, a.os || "—", a.owner || "—",
            <Badge key="w" tone={tone(a.warranty_state)}>{a.warranty_end ? `${a.warranty_state}${a.warranty_days_left != null ? ` (${a.warranty_days_left} d)` : ""}` : "unknown"}</Badge>,
            <select key="s" className="field" aria-label={`Status of ${a.hostname}`} value={a.status} onChange={(e) => act(() => patchJson(`/api/it/assets/${a.id}`, { status: e.target.value }), "Couldn't update.")}>{d.statuses.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select>,
            <button key="d" className="btn" aria-label={`Delete ${a.hostname}`} onClick={() => act(() => deleteJson(`/api/it/assets/${a.id}`), "Couldn't delete.")}>Delete</button>,
          ])} />
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- event logs
interface Ev { events: number; distinct_ids: number; table: { id: number; count: number; meaning: string; level: string }[]; findings: { severity: string; title: string; detail: string; advice: string; evidence: string[] }[]; caveat: string }

function EventsTab() {
  const [text, setText] = useState("");
  const [r, setR] = useState<Ev | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const act = async (fn: () => Promise<void>, m: string) => { setErr(null); try { await fn(); } catch (e) { setErr(errMsg(e, m)); } };
  return (
    <Section title="Windows event log reader">
      {err && <ErrorBanner message={err} />}
      <textarea className="field h-40 w-full font-mono text-xs" aria-label="Event log export" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste an Event Viewer CSV export or lines containing 'Event ID: 4625'." />
      <div className="mt-2 flex flex-wrap gap-2">
        <button className="btn" onClick={() => act(async () => setText((await getJson<{ text: string }>("/api/it/events/sample")).text), "Couldn't load the sample.")}>Load sample</button>
        <button className="btn btn-primary" onClick={() => act(async () => setR(await postJson<Ev>("/api/it/events/read", { text })), "Couldn't read that.")}>Read it</button>
      </div>
      {r && (
        <div className="mt-3 space-y-3">
          <p className="text-sm">{r.events} events, {r.distinct_ids} distinct IDs.</p>
          {r.findings.length === 0 ? <p className="text-sm text-muted">No notable patterns.</p> : (
            <ul className="space-y-2">{r.findings.map((x, i) => (
              <li key={i} className="rounded border border-line p-2 text-sm">
                <div><Badge tone={x.severity === "high" ? "bad" : x.severity === "medium" ? "warn" : "muted"}>{x.severity}</Badge> <span className="font-medium">{x.title}</span></div>
                <p className="text-xs text-muted">{x.detail}</p><p className="text-xs">{x.advice}</p>
              </li>))}</ul>
          )}
          <Table head={["ID", "Count", "Meaning"]} caption="Event IDs" rows={r.table.map((t) => [String(t.id), String(t.count), t.meaning])} />
          <p className="text-xs text-muted">{r.caveat}</p>
        </div>
      )}
    </Section>
  );
}

// ---------------------------------------------------------------- checklists
interface CL { lists: { id: string; title: string; items: { text: string; done: boolean }[] }[] }

function ChecklistsTab() {
  const [d, setD] = useState<CL | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(async () => { try { setD(await getJson<CL>("/api/it/checklists")); } catch (e) { setErr(errMsg(e, "Couldn't load checklists.")); } }, []);
  useEffect(() => { getJson<CL>("/api/it/checklists").then(setD).catch((e) => setErr(errMsg(e, "Couldn't load checklists."))); }, []);
  const act = async (id: string, body: object) => { setErr(null); try { await postJson(`/api/it/checklists/${id}`, body); await load(); } catch (e) { setErr(errMsg(e, "Couldn't update.")); } };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {(d?.lists ?? []).map((l) => (
        <Section key={l.id} title={`${l.title} (${l.items.filter((i) => i.done).length}/${l.items.length})`}>
          <ul className="space-y-1 text-sm">
            {l.items.map((it, i) => <li key={i}><label className="flex items-start gap-2"><input type="checkbox" checked={it.done} onChange={(e) => act(l.id, { index: i, done: e.target.checked })} /><span>{it.text}</span></label></li>)}
          </ul>
          <button className="btn mt-2" onClick={() => act(l.id, { reset: true })}>Reset</button>
        </Section>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- capacity / availability / RAID
function CapacityTab() {
  const [c, setC] = useState({ used_gb: "620", total_gb: "1000", growth_gb_per_month: "25", warn_pct: "80" });
  const [cr, setCr] = useState<{ used_pct: number; free_gb: number; reach_warning: { months: number; date: string } | null; reach_full: { months: number; date: string } | null; advice: string; note: string } | null>(null);
  const [pct, setPct] = useState("99.9");
  const [ar, setAr] = useState<{ per_day_seconds: number; per_month_minutes: number; per_year_hours: number; nines: string; note: string } | null>(null);
  const [rd, setRd] = useState({ level: "5", disks: "4", size_tb: "4" });
  const [rr, setRr] = useState<{ raw_tb: number; usable_tb: number; efficiency_pct: number; tolerates: string; note: string; caveat: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const act = async (fn: () => Promise<void>, m: string) => { setErr(null); try { await fn(); } catch (e) { setErr(errMsg(e, m)); } };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Storage runway">
        <div className="grid gap-2 sm:grid-cols-4">
          <Field label="Used (GB)"><input className="field" inputMode="decimal" value={c.used_gb} onChange={(e) => setC({ ...c, used_gb: e.target.value })} /></Field>
          <Field label="Total (GB)"><input className="field" inputMode="decimal" value={c.total_gb} onChange={(e) => setC({ ...c, total_gb: e.target.value })} /></Field>
          <Field label="Growth (GB/month)"><input className="field" inputMode="decimal" value={c.growth_gb_per_month} onChange={(e) => setC({ ...c, growth_gb_per_month: e.target.value })} /></Field>
          <Field label="Warn at (%)"><input className="field" inputMode="decimal" value={c.warn_pct} onChange={(e) => setC({ ...c, warn_pct: e.target.value })} /></Field>
        </div>
        <button className="btn btn-primary mt-2" onClick={() => act(async () => setCr(await postJson("/api/it/capacity", { used_gb: Number(c.used_gb), total_gb: Number(c.total_gb), growth_gb_per_month: Number(c.growth_gb_per_month), warn_pct: Number(c.warn_pct) })), "Couldn't calculate.")}>Predict</button>
        {cr && <div className="mt-2 space-y-1 text-sm"><p>{cr.used_pct}% used, {num(cr.free_gb)} GB free.</p>
          <p>Warning level: {cr.reach_warning ? `${cr.reach_warning.date} (${cr.reach_warning.months} months)` : "no date"}. Full: {cr.reach_full ? `${cr.reach_full.date} (${cr.reach_full.months} months)` : "no date"}.</p>
          <p className="text-xs">{cr.advice}</p><p className="text-xs text-muted">{cr.note}</p></div>}
      </Section>
      <Section title="Availability: what does 99.9% allow?">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Availability (%)"><input className="field w-32" inputMode="decimal" value={pct} onChange={(e) => setPct(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => act(async () => setAr(await postJson("/api/it/availability", { pct: Number(pct) })), "Couldn't calculate.")}>Calculate</button>
        </div>
        {ar && <p className="mt-2 text-sm">Allowed downtime: {num(ar.per_day_seconds)} s a day, {num(ar.per_month_minutes)} min a month, {num(ar.per_year_hours, 2)} h a year ({ar.nines}). <span className="text-xs text-muted">{ar.note}</span></p>}
      </Section>
      <Section title="RAID capacity">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Level"><select className="field" value={rd.level} onChange={(e) => setRd({ ...rd, level: e.target.value })}>{["0", "1", "5", "6", "10"].map((l) => <option key={l}>{l}</option>)}</select></Field>
          <Field label="Disks"><input className="field w-24" inputMode="numeric" value={rd.disks} onChange={(e) => setRd({ ...rd, disks: e.target.value })} /></Field>
          <Field label="Size each (TB)"><input className="field w-28" inputMode="decimal" value={rd.size_tb} onChange={(e) => setRd({ ...rd, size_tb: e.target.value })} /></Field>
          <button className="btn btn-primary" onClick={() => act(async () => setRr(await postJson("/api/it/raid", { level: rd.level, disks: Number(rd.disks), size_tb: Number(rd.size_tb) })), "Couldn't calculate.")}>Calculate</button>
        </div>
        {rr && <div className="mt-2 space-y-1 text-sm"><p>{rr.usable_tb} TB usable of {rr.raw_tb} TB raw ({rr.efficiency_pct}%). Survives: {rr.tolerates}.</p><p className="text-xs">{rr.note}</p><p className="text-xs font-medium">{rr.caveat}</p></div>}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- cheat sheets
function CheatsTab() {
  const [d, setD] = useState<{ groups: Record<string, { cmd: string; what: string }[]>; method: string[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<NonNullable<typeof d>>("/api/it/cheats").then(setD).catch((e) => setErr(errMsg(e, "Couldn't load the cheat sheets."))); }, []);
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {d && <Section title="Troubleshooting method"><ol className="list-decimal space-y-1 pl-5 text-sm">{d.method.map((m) => <li key={m}>{m}</li>)}</ol></Section>}
      {d && Object.entries(d.groups).map(([g, rows]) => (
        <Section key={g} title={g}><Table head={["Command", "What it does"]} caption={g} rows={rows.map((r) => [<code key="c" className="break-all text-xs">{r.cmd}</code>, r.what])} /></Section>
      ))}
    </div>
  );
}
