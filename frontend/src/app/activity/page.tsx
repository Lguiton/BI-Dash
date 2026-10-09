"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson } from "@/lib/api";
import type { AuditEntry } from "@/lib/types";

export default function ActivityPage() {
  const [ws, setWs] = useState("");
  const [action, setAction] = useState("");
  const [data, setData] = useState<{ entries: AuditEntry[]; actions: string[] } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    const p = new URLSearchParams({ limit: "200" });
    if (ws) p.set("workspace", ws);
    if (action) p.set("action", action);
    getJson<{ entries: AuditEntry[]; actions: string[] }>(`/api/audit?${p}`, ctl.signal)
      .then((d) => { setData(d); setError(null); })
      .catch((e) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Could not load the log."); });
    return () => ctl.abort();
  }, [ws, action]);

  return (
    <PageShell title="Activity log" subtitle="Everything that changed data or left the app: imports, exports, emails, AI questions, refreshes, backups. Newest first.">
      {error && <ErrorBanner message={error} />}
      <div className="flex flex-wrap gap-3">
        <label className="text-xs text-muted">Workspace
          <select className="field mt-0.5 block" value={ws} onChange={(e) => setWs(e.target.value)}><option value="">Both</option><option value="practice">Practice</option><option value="real">Real</option></select></label>
        <label className="text-xs text-muted">Action
          <select className="field mt-0.5 block" value={action} onChange={(e) => setAction(e.target.value)}><option value="">All</option>{data?.actions.map((a) => <option key={a}>{a}</option>)}</select></label>
      </div>
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr><th className="th">When (UTC)</th><th className="th">Workspace</th><th className="th">Action</th><th className="th">Detail</th></tr></thead>
          <tbody>
            {data?.entries.map((e) => (
              <tr key={e.id} className="border-t border-line">
                <td className="td text-muted">{e.at}</td><td className="td">{e.workspace}</td>
                <td className="td font-medium">{e.action}</td>
                <td className="td whitespace-normal" style={e.ok ? undefined : { color: "var(--bad)" }}>{e.ok ? "" : "Failed: "}{e.detail}</td>
              </tr>
            ))}
            {data && data.entries.length === 0 && <tr><td className="td text-muted" colSpan={4}>Nothing recorded yet.</td></tr>}
          </tbody>
        </table>
      </div>
    </PageShell>
  );
}
