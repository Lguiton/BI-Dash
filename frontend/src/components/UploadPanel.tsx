"use client";
import { Download, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { API_BASE, ApiError, postFile } from "@/lib/api";
import { num } from "@/lib/format";
import type { UploadResult } from "@/lib/types";

export function UploadPanel({ onLoaded }: { onLoaded: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [mode, setMode] = useState<"append" | "replace">("append");
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<{ message: string; details: string[] } | null>(null);

  const canSubmit = !!file && !busy && (mode === "append" || confirmed);

  const submit = async () => {
    if (!file) return;
    setBusy(true); setError(null); setResult(null);
    try {
      const r = await postFile<UploadResult>(`/api/ingest/csv?mode=${mode}`, file);
      setResult(r);
      setFile(null); setConfirmed(false);
      if (input.current) input.current.value = "";
      onLoaded();
    } catch (e) {
      setError(e instanceof ApiError ? { message: e.message, details: e.details } : { message: "Upload failed.", details: [] });
    } finally {
      setBusy(false);
    }
  };

  return (
    <details className="card group">
      <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-4 text-sm font-semibold uppercase tracking-wide">
        <Upload className="h-4 w-4 text-accent" aria-hidden /> Import data (CSV)
        <span className="ml-auto text-xs font-normal normal-case text-muted group-open:hidden">Show</span>
      </summary>
      <div className="space-y-4 border-t border-line p-5">
        <p className="text-sm text-muted">
          Required columns: <code>record_date, entity_id, revenue, operational_cost, units_processed</code>. Optional:{" "}
          <code>entity_name, category, baseline_target, duration_minutes, status, fact_id</code>. The file is checked completely first, so a bad row never leaves you with half-imported data.
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted">
            CSV file
            <input ref={input} type="file" accept=".csv,text/csv" className="field"
                   onChange={(e) => { setFile(e.target.files?.[0] ?? null); setResult(null); setError(null); }} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted">
            Mode
            <select className="field" value={mode} onChange={(e) => { setMode(e.target.value as "append" | "replace"); setConfirmed(false); }}>
              <option value="append">Add / update rows</option>
              <option value="replace">Replace all existing data</option>
            </select>
          </label>
          <button className="btn btn-primary" disabled={!canSubmit} onClick={submit}>
            <Upload className="h-4 w-4" aria-hidden /> {busy ? "Importing…" : "Import"}
          </button>
          <a className="btn" href={`${API_BASE}/api/ingest/template`} download><Download className="h-4 w-4" aria-hidden /> Template</a>
        </div>
        {mode === "replace" && (
          <label className="flex items-center gap-2 text-sm" style={{ color: "var(--bad)" }}>
            <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
            I understand this permanently deletes all current records and entities (including the demo data).
          </label>
        )}
        {result && (
          <div role="status" className="rounded-lg p-3 text-sm" style={{ background: "var(--good-bg)", color: "var(--good)" }}>
            Imported {num(result.rows_loaded)} rows ({num(result.rows_new)} new, {num(result.rows_updated)} updated;{" "}
            {num(result.entities_created)} new entities) covering {result.date_min} to {result.date_max}.
          </div>
        )}
        {error && (
          <div role="alert" className="rounded-lg p-3 text-sm" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>
            <div className="font-semibold">{error.message}</div>
            {error.details.length > 0 && <ul className="mt-2 list-disc pl-5">{error.details.map((d) => <li key={d}>{d}</li>)}</ul>}
          </div>
        )}
      </div>
    </details>
  );
}
