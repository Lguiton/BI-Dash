"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { useWorkTabs } from "@/lib/mode";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, patchJson, postFile, postJson, putJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg, num } from "./kit";
import { QualTab } from "./AnalysisQual";
import { AplusTab } from "./AplusTab";
import { FundTab } from "./FundTab";
import { InfraTab } from "./InfraTab";
import { CoachTab } from "./CoachTab";
import { BackupLab, InventoryImport } from "./ItBuild";
import { FixForm, FixLog, SeenBefore, type Fix } from "./FixLog";

const TABS = [
  { id: "tickets", label: "Helpdesk" }, { id: "fixlog", label: "Fix log" }, { id: "repair", label: "How to repair" }, { id: "assets", label: "Inventory" }, { id: "backup", label: "Backup lab" }, { id: "events", label: "Event logs" },
  { id: "checklists", label: "Checklists" }, { id: "capacity", label: "Capacity and RAID" }, { id: "cheats", label: "Cheat sheets" }, { id: "keys", label: "Windows shortcuts" }, { id: "software", label: "Software guide" }, { id: "virt", label: "Virtualization (vSphere)" }, { id: "aplus", label: "CompTIA A+" }, { id: "fund", label: "IT fundamentals" }, { id: "infra", label: "Infrastructure labs" }, { id: "coach", label: "Ticket coach" },
];

export function ItPanel({ tab: wanted, onTab }: { tab: string; onTab: (t: string) => void }) {
  const { tabs: shownTabs, current: tab } = useWorkTabs(TABS, ["cheats", "aplus", "fund", "infra", "virt", "coach", "keys"], wanted);
  const [ver, setVer] = useState(0);
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">
        Personal-scale practice tools: a helpdesk and an inventory you fill in by hand, plus calculators and checklists. They don&apos;t discover or manage real machines.
      </p>
      <Tabs tabs={shownTabs} value={tab} onChange={onTab} label="IT tools" />
      {tab === "tickets" && <TicketsTab />}
      {tab === "fixlog" && <FixLog area="it" />}
      {tab === "repair" && <RepairTab />}
      {tab === "assets" && <><AssetsTab key={ver} /><InventoryImport onDone={() => setVer((v) => v + 1)} /></>}
      {tab === "backup" && <BackupLab />}
      {tab === "events" && <EventsTab />}
      {tab === "checklists" && <ChecklistsTab />}
      {tab === "capacity" && <CapacityTab />}
      {tab === "cheats" && <CheatsTab />}
      {tab === "keys" && <ShortcutsTab />}
      {tab === "software" && <SoftwareTab />}
      {tab === "virt" && <VirtTab />}
      {tab === "aplus" && <AplusTab />}
      {tab === "fund" && <FundTab />}
      {tab === "infra" && <InfraTab />}
      {tab === "coach" && <CoachTab />}
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
  const [seenQ, setSeenQ] = useState("");
  const [draft, setDraft] = useState<{ id: number; d: Partial<Fix> } | null>(null);
  const [saved, setSaved] = useState<string | null>(null);
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
          <Field label="What is wrong?"><input className="field" maxLength={140} value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} onBlur={(e) => setSeenQ(e.target.value)} /></Field>
          <Field label="Who asked?"><input className="field" maxLength={80} value={f.requester} onChange={(e) => setF({ ...f, requester: e.target.value })} /></Field>
          <Field label="Category"><select className="field" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{(d?.categories ?? []).map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}</select></Field>
          <Field label="Priority"><select className="field" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}>{Object.keys(d?.sla ?? { medium: 24 }).map((p) => <option key={p} value={p}>{p}</option>)}</select></Field>
        </div>
        <div className="mt-2"><SeenBefore q={seenQ} area="it" /></div>
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
            {cur.is_open && <SeenBefore q={cur.title} area={cur.category === "network" ? "network" : "it"} />}
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
            <div>
              {draft?.id === cur.id ? (
                <FixForm key={cur.id} area={(draft.d.area as "it" | "network") ?? "it"} draft={draft.d} ticketId={cur.id} onSaved={() => { setDraft(null); setSaved(`Saved ticket #${cur.id} to the fix log.`); void load(); }} onCancel={() => setDraft(null)} />
              ) : (
                <div className="flex flex-wrap items-center gap-2">
                  <button className="btn" onClick={() => act(async () => { setSaved(null); setDraft({ id: cur.id, d: await getJson<Partial<Fix>>(`/api/fixlog/draft/ticket/${cur.id}`) }); }, "Couldn't start the fix record.")}>Save this fix to the fix log</button>
                  <span className="text-xs text-muted">Starts from the steps you ticked and the notes you added. You can edit before saving.</span>
                  {saved && <span className="text-sm text-emerald-600" role="status">{saved}</span>}
                </div>
              )}
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
  const [fname, setFname] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const act = async (fn: () => Promise<void>, m: string) => { setErr(null); try { await fn(); } catch (e) { setErr(errMsg(e, m)); } };
  return (
    <Section title="Windows event log reader" note="Export from Event Viewer: Windows Logs, Security, then Action, Save All Events As, and choose CSV. A .evtx file is binary and can't be read here. Files up to 25 MB; nothing is stored.">
      {err && <ErrorBanner message={err} />}
      <textarea className="field h-40 w-full font-mono text-xs" aria-label="Event log export" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste an Event Viewer CSV export or lines containing 'Event ID: 4625'." />
      <div className="mt-2 flex flex-wrap gap-2">
        <button className="btn" onClick={() => act(async () => setText((await getJson<{ text: string }>("/api/it/events/sample")).text), "Couldn't load the sample.")}>Load sample</button>
        <button className="btn btn-primary" disabled={!text.trim()} onClick={() => act(async () => { setFname(null); setR(await postJson<Ev>("/api/it/events/read", { text })); }, "Couldn't read that.")}>Read it</button>
        <button className="btn" onClick={() => fileRef.current?.click()}>Open file…</button>
        <input ref={fileRef} type="file" accept=".csv,.txt,.log" className="hidden" aria-label="Open an event log export" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) void act(async () => { setFname(f.name); setR(await postFile<Ev>("/api/it/events/upload", f)); }, "Couldn't read that file."); }} />
      </div>
      {r && (
        <div className="mt-3 space-y-3">
          <p className="text-sm">{fname ? `${fname}: ` : ""}{r.events.toLocaleString()} events, {r.distinct_ids} distinct IDs.</p>
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


interface Guide { id: string; objective: string; area: string; title: string; symptoms: string[]; causes: string[]; steps: string[]; tools: string[]; safety: string; escalate: string }
interface Toolkit { title: string; problems: string[]; tools: { name: string; fixes: string; how: string }[]; commands: { name: string; run: string[]; note: string }[]; links: { name: string; url: string }[]; tips: string[] }
function RepairTab() {
  const [d, setD] = useState<{ method: { step: number; name: string; what: string }[]; safety: string[]; areas: string[]; guides: Guide[]; note: string; toolkit: Toolkit } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [area, setArea] = useState("");
  useEffect(() => { getJson<NonNullable<typeof d>>("/api/it/repair").then(setD).catch((e) => setErr(errMsg(e, "Couldn't load the repair guides."))); }, []);
  const needle = q.trim().toLowerCase();
  const [rank, setRank] = useState<{ q: string; ids: string[] } | null>(null);
  useEffect(() => {
    if (needle.length < 2) return;
    const t = setTimeout(() => {
      getJson<{ results: { id: string }[] }>(`/api/it/repair/search?q=${encodeURIComponent(needle)}&limit=20`).then((r) => setRank({ q: needle, ids: r.results.map((x) => x.id) })).catch(() => setRank(null));
    }, 250);
    return () => clearTimeout(t);
  }, [needle]);
  const ranked = needle.length >= 2 && rank?.q === needle ? rank.ids : null;
  const all = (d?.guides ?? []).filter((g) => !area || g.area === area);
  const guides = !needle ? all : ranked ? ranked.map((id) => all.find((g) => g.id === id)).filter((g): g is Guide => !!g)
    : all.filter((g) => [g.title, g.area, ...g.symptoms, ...g.causes, ...g.steps].some((t) => t.toLowerCase().includes(needle)));
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      {d && <Section title="Before you open anything: safety"><ul className="list-disc space-y-1 pl-5 text-sm">{d.safety.map((x) => <li key={x}>{x}</li>)}</ul></Section>}
      {d && <Section title="The six-step repair method"><ol className="list-decimal space-y-1 pl-5 text-sm">{d.method.map((m) => <li key={m.step}><strong>{m.name}.</strong> {m.what}</li>)}</ol></Section>}
      {d && (
        <details className="card p-4">
          <summary className="cursor-pointer font-semibold">{d.toolkit.title}</summary>
          <div className="mt-3 space-y-3 text-sm">
            <p><strong>Covers:</strong> {d.toolkit.problems.join(" · ")}</p>
            <Table head={["Tool", "What it fixes", "How to use it"]} caption="Essential tools" rows={d.toolkit.tools.map((t) => [t.name, t.fixes, t.how])} />
            <div className="space-y-2">{d.toolkit.commands.map((c) => (
              <div key={c.name}><h4 className="font-medium">{c.name}</h4>{c.run.map((r) => <code key={r} className="block break-all rounded bg-black/10 px-2 py-1 text-xs">{r}</code>)}<p className="text-xs text-muted">{c.note}</p></div>))}</div>
            <div><h4 className="font-medium">Official downloads</h4><ul className="list-disc pl-5">{d.toolkit.links.map((l) => <li key={l.url}><a className="underline" href={l.url} target="_blank" rel="noopener noreferrer">{l.name}</a></li>)}</ul></div>
            <ul className="list-disc pl-5">{d.toolkit.tips.map((t) => <li key={t}>{t}</li>)}</ul>
          </div>
        </details>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <input className="input min-w-64 flex-1" placeholder="Search a symptom, e.g. printer offline, no power, beeps, 169.254 (typos are fine)" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search repair guides" />
        <select className="input" value={area} onChange={(e) => setArea(e.target.value)} aria-label="Area"><option value="">All areas</option>{d?.areas.map((a) => <option key={a}>{a}</option>)}</select>
        {d && <span className="text-xs text-muted">{guides.length} of {d.guides.length} guides</span>}
      </div>
      {d && guides.length === 0 && <p className="text-sm text-muted">No guide matches. Try a shorter word.</p>}
      {guides.map((g) => (
        <details key={g.id} className="card p-4">
          <summary className="cursor-pointer font-semibold">{g.title} <span className="ml-2 text-xs font-normal text-muted">{g.area}{g.objective === "General" ? "" : ` · A+ objective ${g.objective}`}</span></summary>
          <div className="mt-3 space-y-3 text-sm">
            <div><h4 className="font-medium">What you see</h4><ul className="list-disc pl-5">{g.symptoms.map((x) => <li key={x}>{x}</li>)}</ul></div>
            <div><h4 className="font-medium">Likely causes, easiest to check first</h4><ol className="list-decimal pl-5">{g.causes.map((x) => <li key={x}>{x}</li>)}</ol></div>
            <div><h4 className="font-medium">Steps</h4><ol className="list-decimal space-y-1 pl-5">{g.steps.map((x) => <li key={x}>{x}</li>)}</ol></div>
            <p><strong>Tools:</strong> {g.tools.join(", ")}</p>
            <p className="rounded-lg p-2" style={{ background: "var(--warn-bg)" }}><strong>Safety:</strong> {g.safety}</p>
            <p><strong>Stop and escalate when:</strong> {g.escalate}</p>
          </div>
        </details>
      ))}
      {d && <p className="text-xs text-muted">{d.note}</p>}
    </div>
  );
}


function ShortcutsTab() {
  const [d, setD] = useState<{ groups: Record<string, { keys: string; what: string }[]>; count: number; note: string } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [q, setQ] = useState("");
  useEffect(() => { getJson<NonNullable<typeof d>>("/api/it/shortcuts").then(setD).catch((e) => setErr(errMsg(e, "Couldn't load the shortcuts."))); }, []);
  const needle = q.trim().toLowerCase();
  const groups = d ? Object.entries(d.groups).map(([g, rows]) => [g, rows.filter((r) => !needle || r.keys.toLowerCase().includes(needle) || r.what.toLowerCase().includes(needle) || g.toLowerCase().includes(needle))] as const).filter(([, rows]) => rows.length) : [];
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-center gap-2">
        <input className="input min-w-64 flex-1" placeholder="Search by key or task, e.g. lock, snip, Win+R" value={q} onChange={(e) => setQ(e.target.value)} aria-label="Search shortcuts" />
        {d && <span className="text-xs text-muted">{d.count} shortcuts</span>}
      </div>
      {d && <p className="text-xs text-muted">{d.note}</p>}
      {d && groups.length === 0 && <p className="text-sm text-muted">Nothing matches “{q}”.</p>}
      {groups.map(([g, rows]) => (
        <Section key={g} title={g}><Table head={["Keys", "What it does"]} caption={g} rows={rows.map((r) => [<kbd key="k" className="rounded border border-current/30 px-1.5 py-0.5 text-xs">{r.keys}</kbd>, r.what])} /></Section>
      ))}
    </div>
  );
}


// ---------------------------------------------------------------- software guide
interface SwProduct { name: string; change: number | null; rank: number; [k: string]: string | number | null }
interface SwCat { id: string; label: string; what: string; free: string; count: number; products: SwProduct[] }
interface SwCatalog { source: string; metrics: { key: string; label: string; max: number }[]; categories: SwCat[]; notes: string[] }
interface SwRank { label: string; rows: { name: string; score: number; weight_covered_pct: number; missing: string[]; guide_rank: number; position: number }[]; lesson: string; caution: string }
interface SwStack { rows: { id: string; label: string; tool: string; status: string; note: string }[]; statuses: string[]; have: number; counted: number; gaps: string[]; lesson: string }
const STACK_LABEL: Record<string, string> = { have: "Have it", planned: "Planned", none: "Gap", not_needed: "Not needed" };

function SoftwareTab() {
  const [cat, setCat] = useState<SwCatalog | null>(null);
  const [stack, setStack] = useState<SwStack | null>(null);
  const [rows, setRows] = useState<SwStack["rows"]>([]);
  const [sel, setSel] = useState("rmm");
  const [w, setW] = useState<Record<string, number>>({});
  const [skip, setSkip] = useState("");
  const [rank, setRank] = useState<SwRank | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    getJson<SwCatalog>("/api/it/software").then((c) => { setCat(c); setW(Object.fromEntries(c.metrics.map((m) => [m.key, 1]))); }).catch((e) => setErr(errMsg(e, "Couldn't load the guide.")));
    getJson<SwStack>("/api/it/software/stack").then((s) => { setStack(s); setRows(s.rows); }).catch((e) => setErr(errMsg(e, "Couldn't load your stack.")));
  }, []);
  const cur = cat?.categories.find((c) => c.id === sel);
  const doRank = async () => {
    setErr(null);
    try { setRank(await postJson<SwRank>("/api/it/software/shortlist", { category: sel, weights: w, exclude: skip.split(",").map((x) => x.trim()).filter(Boolean) })); } catch (e) { setRank(null); setErr(errMsg(e, "That didn't work.")); }
  };
  const save = async () => {
    setErr(null); setMsg(null);
    try { const s = await putJson<SwStack>("/api/it/software/stack", { items: rows }); setStack(s); setRows(s.rows); setMsg("Saved."); } catch (e) { setErr(errMsg(e, "Couldn't save.")); }
  };
  const setRow = (id: string, patch: Partial<SwStack["rows"][number]>) => setRows((rs) => rs.map((r) => (r.id === id ? { ...r, ...patch } : r)));
  const val = (v: string | number | null) => (v == null ? "—" : String(v));
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">
        Ratings from the NinjaOne SysAdmin Software Guide 2026 (G2 and Capterra, March 2026). The guide is published by a vendor that is also ranked in it, and ratings are one input among price, fit and support. This tab helps you plan and shortlist; it does not install or manage any software.
      </p>
      <Section title="What do you cover today?" note={stack?.lesson}>
        {stack && <p className="mb-2 text-sm">{stack.have} of {stack.counted} categories covered{stack.gaps.length > 0 ? `. Gaps: ${stack.gaps.join(", ")}.` : "."}</p>}
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.id} className="grid gap-2 sm:grid-cols-[1.4fr_1fr_1fr_1.4fr]">
              <p className="self-center text-sm">{r.label}</p>
              <select className="field" aria-label={`Status for ${r.label}`} value={r.status} onChange={(e) => setRow(r.id, { status: e.target.value })}>{(stack?.statuses ?? []).map((st) => <option key={st} value={st}>{STACK_LABEL[st] ?? st}</option>)}</select>
              <input className="field" aria-label={`Tool for ${r.label}`} placeholder="Tool you use" maxLength={80} value={r.tool} onChange={(e) => setRow(r.id, { tool: e.target.value })} />
              <input className="field" aria-label={`Note for ${r.label}`} placeholder="Note" maxLength={200} value={r.note} onChange={(e) => setRow(r.id, { note: e.target.value })} />
            </div>
          ))}
        </div>
        <div className="mt-3 flex items-center gap-3"><button className="btn btn-primary" onClick={save}>Save my stack</button>{msg && <span className="text-xs text-muted" role="status">{msg}</span>}</div>
      </Section>
      <Section title="Shortlist a tool" note="Weight what matters to you (0 to 10). Each rating is put on a 0 to 10 scale and averaged; ratings a product lacks are left out.">
        {cat && (
          <>
            <div className="flex flex-wrap items-end gap-3">
              <Field label="Kind of tool"><select className="field" value={sel} onChange={(e) => { setSel(e.target.value); setRank(null); }}>{cat.categories.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}</select></Field>
              <Field label="Leave out (names, comma separated)"><input className="field" value={skip} onChange={(e) => setSkip(e.target.value)} /></Field>
              <button className="btn btn-primary" onClick={doRank}>Rank them</button>
            </div>
            <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {cat.metrics.map((m) => (
                <Field key={m.key} label={`${m.label}: ${w[m.key] ?? 0}`}><input type="range" min={0} max={10} step={1} value={w[m.key] ?? 0} aria-label={`Weight for ${m.label}`} onChange={(e) => setW({ ...w, [m.key]: Number(e.target.value) })} /></Field>
              ))}
            </div>
          </>
        )}
      </Section>
      {rank && (
        <Section title={`Your ranking: ${rank.label}`} note={`${rank.lesson} ${rank.caution}`}>
          <Table head={["#", "Tool", "Score (0 to 10)", "Weight covered", "Missing ratings", "Guide rank"]} rows={rank.rows.map((r) => [r.position, r.name, r.score.toFixed(2), `${r.weight_covered_pct}%`, r.missing.length ? r.missing.join(", ") : "—", r.guide_rank])} />
        </Section>
      )}
      {cur && cat && (
        <Section title={`${cur.label}: the guide's ratings`} note={`${cur.what} Free options to practise on (not from the guide): ${cur.free}`}>
          <Table head={["Rank", "Tool", "Change", ...cat.metrics.map((m) => m.label)]} rows={cur.products.map((p) => [p.rank, p.name, p.change == null || p.change === 0 ? "—" : p.change > 0 ? `+${p.change}` : String(p.change), ...cat.metrics.map((m) => val(p[m.key]))])} />
        </Section>
      )}
      <Section title="Write down the decision" note="Save why you chose a tool, what you tried and what it costs, so it can be reviewed later."><QualTab kinds={["toolchoice"]} /></Section>
      {cat && <Section title="Read this first"><ul className="list-disc space-y-1 pl-5 text-sm">{cat.notes.map((n) => <li key={n}>{n}</li>)}</ul><p className="mt-2 text-xs text-muted">{cat.source}.</p></Section>}
    </div>
  );
}


// ---------------------------------------------------------------- virtualization planner
interface VCat { runbook: { n: number; title: string; what: string; do: string[]; verify: string[]; mistakes: string[]; note: string }[]; components: { name: string; what: string }[]; practice: { name: string; how: string; needs: string }[]; not_available: string[]; roles: string[]; example_network: VNet[]; example_hosts: VHost[]; source_note: string }
interface VNet { name: string; role: string; vlan: number; subnet: string }
interface VHost { name: string; cores: number; ram_gb: number; version: string }
interface VIssues { issues: { level: string; text: string }[]; ok?: boolean }
interface VCap { total_vcpu: number; total_ram_gb: number; total_disk_gb: number; hosts_for_cpu: number; hosts_for_ram: number; hosts_working: number; hosts_total: number; storage_tb: number; actual_vcpu_per_core: number; ram_used_pct_one_host_down: number; survives_one_host_failure: boolean; notes: string[]; lesson: string }
const LV: Record<string, "bad" | "warn" | "muted"> = { bad: "bad", warn: "warn", info: "muted" };

function VirtTab() {
  const [cat, setCat] = useState<VCat | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [cap, setCap] = useState({ vms: "50", vcpu_per_vm: "2", ram_per_vm_gb: "8", disk_per_vm_gb: "100", host_cores: "16", host_ram_gb: "128", vcpu_ratio: "4", headroom_pct: "20", ha_spares: "1" });
  const [capRes, setCapRes] = useState<VCap | null>(null);
  const [nets, setNets] = useState<VNet[]>([]);
  const [netRes, setNetRes] = useState<VIssues | null>(null);
  const [hosts, setHosts] = useState<VHost[]>([]);
  const [hostRes, setHostRes] = useState<VIssues | null>(null);
  useEffect(() => { getJson<VCat>("/api/it/virt").then((c) => { setCat(c); setNets(c.example_network); setHosts(c.example_hosts); }).catch((e) => setErr(errMsg(e, "Couldn't load the planner."))); }, []);
  const calc = () => { setErr(null); postJson<VCap>("/api/it/virt/capacity", Object.fromEntries(Object.entries(cap).map(([k, v]) => [k, Number(v)]))).then(setCapRes).catch((e) => { setCapRes(null); setErr(errMsg(e, "Check the numbers.")); }); };
  const chkNet = () => { setErr(null); postJson<VIssues>("/api/it/virt/network", { rows: nets }).then(setNetRes).catch((e) => { setNetRes(null); setErr(errMsg(e, "Check the networks.")); }); };
  const chkHost = () => { setErr(null); postJson<VIssues>("/api/it/virt/cluster", { rows: hosts }).then(setHostRes).catch((e) => { setHostRes(null); setErr(errMsg(e, "Check the hosts.")); }); };
  const issues = (r: VIssues | null) => r && (r.issues.length === 0 ? <p className="mt-2 text-sm"><Badge tone="ok">No problems found</Badge></p> : <ul className="mt-2 space-y-1 text-sm">{r.issues.map((i, k) => <li key={k}><Badge tone={LV[i.level] ?? "muted"}>{i.level}</Badge> {i.text}</li>)}</ul>);
  if (!cat) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  const CAPF: [keyof typeof cap, string][] = [["vms", "VMs"], ["vcpu_per_vm", "vCPU per VM"], ["ram_per_vm_gb", "RAM per VM (GB)"], ["disk_per_vm_gb", "Disk per VM (GB)"], ["host_cores", "Cores per host"], ["host_ram_gb", "RAM per host (GB)"], ["vcpu_ratio", "vCPU per core"], ["headroom_pct", "Headroom %"], ["ha_spares", "Spare hosts (HA)"]];
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Plan a VMware vSphere build: the 10 steps in order, how many hosts and how much storage you need, and whether your VLANs and cluster hold together. ESXi and vCenter can&apos;t run here (they need your own hardware and a licence), so this tab plans and checks; it never connects to a host. {cat.source_note}</p>
      {err && <ErrorBanner message={err} />}
      <Section title="The 10 steps">
        <div className="space-y-2">{cat.runbook.map((s) => (
          <details key={s.n} className="rounded border border-line p-2"><summary className="cursor-pointer text-sm"><b>{s.n}. {s.title}</b> <span className="text-muted">{s.what}</span></summary>
            <div className="mt-2 grid gap-3 text-sm sm:grid-cols-3">
              <div><p className="text-xs font-semibold">Do</p><ul className="list-disc pl-4">{s.do.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
              <div><p className="text-xs font-semibold">Check it worked</p><ul className="list-disc pl-4">{s.verify.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
              <div><p className="text-xs font-semibold">Common mistakes</p><ul className="list-disc pl-4">{s.mistakes.map((x, i) => <li key={i}>{x}</li>)}</ul></div>
            </div>{s.note && <p className="mt-2 text-xs text-muted">{s.note}</p>}</details>))}</div>
      </Section>
      <Section title="How many hosts and how much storage">
        <div className="grid gap-2 sm:grid-cols-3">{CAPF.map(([k, l]) => <Field key={k} label={l}><input className="field" inputMode="decimal" value={cap[k]} onChange={(e) => setCap({ ...cap, [k]: e.target.value })} /></Field>)}</div>
        <button className="btn mt-2" onClick={calc}>Work it out</button>
        {capRes && <div className="mt-3 space-y-2">
          <div className="grid gap-3 sm:grid-cols-4"><Stat label="Hosts to buy" value={String(capRes.hosts_total)} sub={`${capRes.hosts_working} working + ${capRes.hosts_total - capRes.hosts_working} spare`} /><Stat label="Needed for CPU / RAM" value={`${capRes.hosts_for_cpu} / ${capRes.hosts_for_ram}`} /><Stat label="Shared storage" value={`${num(capRes.storage_tb, 1)} TB`} /><Stat label="RAM used, one host down" value={`${num(capRes.ram_used_pct_one_host_down, 0)}%`} /></div>
          <ul className="list-disc pl-5 text-sm">{capRes.notes.map((n, i) => <li key={i}>{n}</li>)}</ul><p className="text-xs text-muted">{capRes.lesson}</p></div>}
      </Section>
      <Section title="Network plan checker" note="The sample has vMotion and the VM network both on VLAN 20, as the source infographic does. Check it, then fix the VLAN.">
        <div className="space-y-1">{nets.map((n, i) => (
          <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            <input className="field" aria-label="Name" value={n.name} onChange={(e) => setNets(nets.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
            <select className="field" aria-label="Role" value={n.role} onChange={(e) => setNets(nets.map((x, j) => j === i ? { ...x, role: e.target.value } : x))}>{cat.roles.map((r) => <option key={r}>{r}</option>)}</select>
            <input className="field" aria-label="VLAN" inputMode="numeric" value={n.vlan} onChange={(e) => setNets(nets.map((x, j) => j === i ? { ...x, vlan: Number(e.target.value) } : x))} />
            <input className="field" aria-label="Subnet" value={n.subnet} onChange={(e) => setNets(nets.map((x, j) => j === i ? { ...x, subnet: e.target.value } : x))} />
            <button className="btn" onClick={() => setNets(nets.filter((_, j) => j !== i))}>Remove</button></div>))}</div>
        <div className="mt-2 flex gap-2"><button className="btn" onClick={() => setNets([...nets, { name: "", role: "other", vlan: 50, subnet: "" }])}>Add network</button><button className="btn btn-primary" onClick={chkNet}>Check</button></div>
        {issues(netRes)}
      </Section>
      <Section title="Cluster check">
        <div className="space-y-1">{hosts.map((h, i) => (
          <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            <input className="field" aria-label="Host name" value={h.name} onChange={(e) => setHosts(hosts.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} />
            <input className="field" aria-label="Cores" inputMode="numeric" value={h.cores} onChange={(e) => setHosts(hosts.map((x, j) => j === i ? { ...x, cores: Number(e.target.value) } : x))} />
            <input className="field" aria-label="RAM GB" inputMode="decimal" value={h.ram_gb} onChange={(e) => setHosts(hosts.map((x, j) => j === i ? { ...x, ram_gb: Number(e.target.value) } : x))} />
            <input className="field" aria-label="ESXi version" value={h.version} onChange={(e) => setHosts(hosts.map((x, j) => j === i ? { ...x, version: e.target.value } : x))} />
            <button className="btn" onClick={() => setHosts(hosts.filter((_, j) => j !== i))}>Remove</button></div>))}</div>
        <div className="mt-2 flex gap-2"><button className="btn" onClick={() => setHosts([...hosts, { name: "", cores: 16, ram_gb: 128, version: "8.0.2" }])}>Add host</button><button className="btn btn-primary" onClick={chkHost}>Check</button></div>
        {issues(hostRes)}
      </Section>
      <Section title="Terms"><Table head={["Term", "What it is"]} rows={cat.components.map((c) => [c.name, c.what])} /></Section>
      <Section title="Free ways to practise"><Table head={["Option", "What it gives you", "You need"]} rows={cat.practice.map((p) => [p.name, p.how, p.needs])} />
        <p className="mt-2 text-xs font-semibold">Not available in this app</p><ul className="list-disc pl-5 text-sm">{cat.not_available.map((x, i) => <li key={i}>{x}</li>)}</ul></Section>
      <QualTab kinds={["virtplan"]} />
    </div>
  );
}
