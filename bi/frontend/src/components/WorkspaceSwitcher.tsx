"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { FlaskRound, Landmark } from "lucide-react";
import { ApiError, getJson, postJson } from "@/lib/api";
import type { WorkspaceList, WorkspaceName } from "@/lib/types";

/** Practice / Real switch. Switching reloads the page so every number on screen comes from the other database. */
export function WorkspaceSwitcher() {
  const [ws, setWs] = useState<WorkspaceList | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    getJson<WorkspaceList>("/api/workspaces", ctl.signal).then(setWs).catch(() => { /* the page itself shows API errors */ });
    return () => ctl.abort();
  }, []);

  if (!ws) return null;
  const switchTo = async (name: WorkspaceName) => {
    if (name === ws.active) return;
    setBusy(true); setErr(null);
    try {
      await postJson("/api/workspaces/active", { name });
      window.location.reload();
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : "Could not switch.");
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col items-end gap-1">
      <div role="group" aria-label="Workspace" className="inline-flex overflow-hidden rounded-lg border border-line text-sm">
        {(["practice", "real"] as const).map((n) => {
          const on = ws.active === n;
          const Icon = n === "practice" ? FlaskRound : Landmark;
          return (
            <button key={n} type="button" disabled={busy} aria-pressed={on} onClick={() => switchTo(n)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 ${on ? "font-semibold" : "text-muted hover:bg-panel2"}`}
                    style={on ? { background: n === "real" ? "var(--warn-bg)" : "var(--info-bg)" } : undefined}>
              <Icon className="h-4 w-4" aria-hidden /> {n === "practice" ? "Practice" : "Real"}
            </button>
          );
        })}
      </div>
      {err && <span role="alert" className="text-xs" style={{ color: "var(--bad)" }}>{err}</span>}
    </div>
  );
}

/** Reminder bar shown on every page while the Real workspace is open. */
export function RealBanner() {
  const [info, setInfo] = useState<WorkspaceList | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<WorkspaceList>("/api/workspaces", ctl.signal).then(setInfo).catch(() => {});
    return () => ctl.abort();
  }, []);
  const real = info?.workspaces.find((w) => w.name === "real" && w.active);
  if (!real) return null;
  const ai = real.settings.ai_mode;
  return (
    <div role="status" className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg px-4 py-2 text-sm" style={{ background: "var(--warn-bg)" }}>
      <strong>Real workspace.</strong>
      <span>Your own data. Destructive actions take a backup first.</span>
      <span>AI: {ai === "off" ? "off" : ai === "aggregate" ? "summaries only" : "full access"}.</span>
      <Link href="/settings" className="ml-auto underline">Settings</Link>
    </div>
  );
}
