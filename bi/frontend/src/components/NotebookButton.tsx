"use client";
import { BookOpen } from "lucide-react";
import { useState } from "react";
import { API_BASE } from "@/lib/api";

/** "Send this to a notebook": asks the backend for a ready-to-run .ipynb and saves it. Works from SQL Lab, Workflow and ML Lab. */
export function NotebookButton({ kind, body, disabled }: { kind: "sql" | "workflow" | "ml"; body: () => Record<string, unknown>; disabled?: boolean }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<{ ok: boolean; text: string } | null>(null);
  async function go() {
    setBusy(true); setMsg(null);
    try {
      const res = await fetch(`${API_BASE}/api/notebook/export`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ kind, ...body() }) });
      if (!res.ok) {
        let detail = "Couldn't build the notebook.";
        try { const j = await res.json(); if (typeof j.detail === "string") detail = j.detail; } catch { /* keep default */ }
        throw new Error(detail);
      }
      const name = /filename="([^"]+)"/.exec(res.headers.get("content-disposition") ?? "")?.[1] ?? "notebook.ipynb";
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
      setMsg({ ok: true, text: `Saved ${name}. Put it in notebooks/ (or anywhere Jupyter can see) and open it.` });
    } catch (e) {
      setMsg({ ok: false, text: e instanceof Error ? e.message : "Couldn't build the notebook." });
    } finally { setBusy(false); }
  }
  return (
    <span className="inline-flex flex-wrap items-center gap-2">
      <button type="button" className="btn" onClick={go} disabled={busy || disabled} title="Download this as a Jupyter notebook">
        <BookOpen className="h-4 w-4" aria-hidden /> {busy ? "Building…" : "Send to a notebook"}
      </button>
      {msg && <span role={msg.ok ? "status" : "alert"} className="text-xs" style={{ color: msg.ok ? "var(--good)" : "var(--bad)" }}>{msg.text}</span>}
    </span>
  );
}
