"use client";
import { Download, RotateCcw, Save, Trash2 } from "lucide-react";
import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ExportEverything } from "@/components/DataExtras";
import { BriefingSettings, LaptopSettings, PasswordSettings } from "@/components/SettingsExtras";
import { MyFields } from "@/components/MyFields";
import { ProjectLinks } from "@/components/ProjectLinks";
import { BusinessProfile, ServiceRates } from "@/components/BusinessSettings";
import { PageShell } from "@/components/PageShell";
import { PwaSetup } from "@/components/PwaSetup";
import { ThemeChoice } from "@/components/ThemeChoice";
import { WorkspaceSwitcher } from "@/components/WorkspaceSwitcher";
import { Tabs } from "@/components/panels/kit";
import { AlertsSettings } from "@/components/panels/OpsPanels";
import { API_BASE, ApiError, deleteJson, getJson, postJson, putJson } from "@/lib/api";
import type { AiMode, BackupItem, WorkspaceInfo, WorkspaceList, WorkspaceSettings } from "@/lib/types";

const MODES: [AiMode, string, string][] = [
  ["off", "Off", "Nothing is sent to any AI provider."],
  ["aggregate", "Summaries only", "The AI can only run totals, counts and averages, and sees at most 20 result rows."],
  ["full", "Full", "The AI can run any read-only query and see up to 40 rows."],
];
const size = (b: number) => (b > 1e6 ? `${(b / 1e6).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1e3))} KB`);

const TABS = [
  { id: "general", label: "General" },
  { id: "business", label: "Business and services" },
  { id: "ai", label: "AI and privacy" },
  { id: "data", label: "Data and backups" },
  { id: "alerts", label: "Alerts and reports" },
  { id: "security", label: "Security and device" },
];

function Body() {
  const sp = useSearchParams();
  const [tab, setTab] = useState(() => (TABS.some((t) => t.id === sp.get("tab")) ? (sp.get("tab") as string) : "general"));
  const [ws, setWs] = useState<WorkspaceList | null>(null);
  const [error, setError] = useState<string | null>(null);
  const load = useCallback((signal?: AbortSignal) => {
    getJson<WorkspaceList>("/api/workspaces", signal).then((w) => { setWs(w); setError(null); })
      .catch((e) => { if (!signal?.aborted) setError(e instanceof ApiError ? e.message : "Could not load settings."); });
  }, []);
  useEffect(() => { const ctl = new AbortController(); load(ctl.signal); return () => ctl.abort(); }, [load]);

  return (
    <>
      <Tabs label="Settings sections" value={tab} onChange={setTab} tabs={TABS} />
      {error && <ErrorBanner message={error} onRetry={() => load()} />}
      {tab === "general" && (
        <div className="grid gap-4">
          <section className="card space-y-3 p-5" aria-label="Workspace">
            <h2 className="text-lg font-semibold">Practice or Real</h2>
            <p className="text-sm text-muted">Practice is for learning and example data. Real is your own business data: the screen turns green and destructive actions take a backup first. Switching reloads the page so every number comes from the other database.</p>
            <WorkspaceSwitcher />
          </section>
          <section className="card space-y-3 p-5" aria-label="Appearance">
            <h2 className="text-lg font-semibold">Appearance</h2>
            <ThemeChoice />
          </section>
          <MyFields />
          <ProjectLinks />
          <section className="card space-y-2 p-5" aria-label="Install on this device">
            <h2 className="text-lg font-semibold">Install on this device</h2>
            <p className="text-sm text-muted">Add the dashboard to your home screen or desktop so it opens like an app.</p>
            <PwaSetup showButton />
          </section>
        </div>
      )}
      {tab === "business" && <div className="grid gap-4"><BusinessProfile /><ServiceRates /></div>}
      {tab === "ai" && (
        <div className="grid gap-4">
          {ws?.workspaces.map((w) => <WorkspaceCard key={w.name} w={w} onSaved={() => load()} />)}
          <section className="card space-y-2 p-5 text-sm text-muted" aria-label="About privacy">
            <h2 className="text-sm font-semibold uppercase tracking-wide text-fg">What these settings do and don&apos;t do</h2>
            <p>The AI settings are guardrails, not a vault. They stop the assistant from reading what you blocked through its normal tools, and they stop accidents. Anything it is allowed to see is sent to the provider you configured, so keep client secrets out of the data.</p>
            <p>Everything else stays on this computer: your databases, backups and the activity log are plain files next to the app. Set a password in Security and device if anyone else can open the app on this machine or your network.</p>
          </section>
        </div>
      )}
      {tab === "data" && (
        <div className="grid gap-4">
          {ws && <Backups workspace={ws.active} />}
          <ExportEverything />
        </div>
      )}
      {tab === "alerts" && (
        <div className="grid gap-4">
          {ws && <AlertsSettings key={ws.active} />}
          <BriefingSettings />
        </div>
      )}
      {tab === "security" && (
        <div className="grid gap-4">
          <PasswordSettings />
          <LaptopSettings />
        </div>
      )}
    </>
  );
}

export default function SettingsPage() {
  return (
    <PageShell title="Settings" subtitle="Workspace, appearance, business details and service rates, AI access, backups, alerts and security.">
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Body /></Suspense>
    </PageShell>
  );
}

function WorkspaceCard({ w, onSaved }: { w: WorkspaceInfo; onSaved: () => void }) {
  const [s, setS] = useState<WorkspaceSettings>(w.settings);
  const [blocked, setBlocked] = useState(w.settings.blocked_columns.join(", "));
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function save() {
    try {
      await putJson(`/api/workspaces/${w.name}/settings`, { ...s, blocked_columns: blocked.split(",").map((x) => x.trim()).filter(Boolean) });
      setMsg({ ok: true, text: "Saved." }); onSaved();
    } catch (e) { setMsg({ ok: false, text: e instanceof ApiError ? e.message : "Failed." }); }
  }
  return (
    <section className="card space-y-4 p-5" aria-label={`${w.label} settings`}>
      <div className="flex flex-wrap items-baseline gap-3">
        <h2 className="text-lg font-semibold">{w.label} workspace</h2>
        {w.active && <span className="rounded-full px-2 py-0.5 text-xs" style={{ background: "var(--info-bg)" }}>open now</span>}
        <span className="text-sm text-muted">{w.exists ? size(w.size_bytes) : "not created yet"}{w.records != null ? ` · ${w.records} operations records · ${w.tables} tables` : ""}</span>
      </div>
      <fieldset className="space-y-2">
        <legend className="text-xs uppercase tracking-wide text-muted">AI access</legend>
        {MODES.map(([m, label, hint]) => (
          <label key={m} className="flex items-start gap-2 text-sm">
            <input type="radio" name={`ai-${w.name}`} checked={s.ai_mode === m} onChange={() => setS({ ...s, ai_mode: m })} className="mt-1" />
            <span><span className="font-medium">{label}</span> <span className="text-muted">· {hint}</span></span>
          </label>
        ))}
      </fieldset>
      <label className="block text-xs text-muted">Columns the AI must never see (comma separated)
        <input className="field mt-1 w-full" value={blocked} onChange={(e) => setBlocked(e.target.value)} placeholder="email, phone, salary" />
      </label>
      <div className="flex flex-wrap items-center gap-4 text-sm">
        <label className="flex items-center gap-2"><input type="checkbox" checked={s.auto_backup} onChange={(e) => setS({ ...s, auto_backup: e.target.checked })} /> Back up automatically once a day (while the app is running)</label>
        <label className="flex items-center gap-2">Keep the latest
          <input type="number" min={1} max={365} className="field w-20" value={s.backup_keep} onChange={(e) => setS({ ...s, backup_keep: Number(e.target.value) || 1 })} /> backups</label>
      </div>
      <div className="flex items-center gap-3">
        <button className="btn btn-primary" onClick={save}><Save className="h-4 w-4" aria-hidden /> Save</button>
        {msg && <span role={msg.ok ? "status" : "alert"} className="text-sm" style={{ color: msg.ok ? "var(--good)" : "var(--bad)" }}>{msg.text}</span>}
      </div>
    </section>
  );
}

function Backups({ workspace }: { workspace: string }) {
  const [items, setItems] = useState<BackupItem[] | null>(null);
  const [note, setNote] = useState("manual");
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  const [confirm, setConfirm] = useState<string | null>(null);
  const load = useCallback(() => { getJson<{ backups: BackupItem[] }>("/api/backups").then((r) => setItems(r.backups)).catch(() => setItems([])); }, []);
  useEffect(() => { load(); }, [load, workspace]);
  const wrap = async (fn: () => Promise<unknown>, ok: string) => {
    try { await fn(); setMsg({ ok: true, text: ok }); } catch (e) { setMsg({ ok: false, text: e instanceof ApiError ? e.message : "Failed." }); }
    load(); setConfirm(null);
  };
  return (
    <section className="card space-y-3 p-5" aria-label="Backups">
      <h2 className="text-lg font-semibold">Backups of the {workspace} workspace</h2>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted">Label<input className="field" value={note} onChange={(e) => setNote(e.target.value)} maxLength={30} /></label>
        <button className="btn btn-primary" onClick={() => wrap(() => postJson("/api/backups", { note }), "Backup created.")}>Back up now</button>
        {msg && <span role={msg.ok ? "status" : "alert"} className="text-sm" style={{ color: msg.ok ? "var(--good)" : "var(--bad)" }}>{msg.text}</span>}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr><th className="th">Taken (UTC)</th><th className="th">Label</th><th className="th">Size</th><th className="th" /></tr></thead>
          <tbody>
            {items?.map((b) => (
              <tr key={b.name} className="border-t border-line">
                <td className="td">{b.created_at}</td><td className="td">{b.kind}</td><td className="td">{size(b.size_bytes)}</td>
                <td className="td text-right">
                  {confirm === b.name ? (
                    <span className="inline-flex items-center gap-2">Replace current data with this?
                      <button className="btn" style={{ color: "var(--bad)" }} onClick={() => wrap(() => postJson("/api/backups/restore", { name: b.name }), "Restored. The page will reload.").then(() => window.location.reload())}>Yes, restore</button>
                      <button className="btn" onClick={() => setConfirm(null)}>Cancel</button></span>
                  ) : (
                    <span className="inline-flex gap-2">
                      <button className="btn" onClick={() => setConfirm(b.name)}><RotateCcw className="h-4 w-4" aria-hidden /> Restore</button>
                      <a className="btn" href={`${API_BASE}/api/backups/${b.name}/download`} download><Download className="h-4 w-4" aria-hidden /> Download</a>
                      <button className="btn" aria-label={`Delete backup ${b.name}`} onClick={() => wrap(() => deleteJson(`/api/backups/${b.name}`), "Deleted.")}><Trash2 className="h-4 w-4" aria-hidden /></button>
                    </span>
                  )}
                </td>
              </tr>
            ))}
            {items && items.length === 0 && <tr><td className="td text-muted" colSpan={4}>No backups yet.</td></tr>}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">Restoring first saves what you have now as a “safety” backup, so a restore can be undone. In Real, imports that replace data and table deletes also take a safety backup automatically.</p>
    </section>
  );
}
