"use client";
import { FileSpreadsheet, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { ApiError, postForm } from "@/lib/api";
import { num } from "@/lib/format";
import type { FilePreview, ImportResult, UploadResult } from "@/lib/types";

type Dest = "table" | "operations";

export function ImportPanel({ onLoaded }: { onLoaded: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pv, setPv] = useState<FilePreview | null>(null);
  const [sheet, setSheet] = useState<string>("");
  const [dest, setDest] = useState<Dest>("table");
  const [name, setName] = useState("");
  const [mode, setMode] = useState<"replace" | "append">("replace");
  const [map, setMap] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState<string | null>(null);
  const [err, setErr] = useState<{ message: string; details: string[] } | null>(null);

  const fail = (e: unknown) => setErr(e instanceof ApiError ? { message: e.message, details: e.details } : { message: "Something went wrong.", details: [] });

  async function inspect(f: File, sh?: string) {
    setBusy(true); setErr(null); setOk(null);
    try {
      const fd = new FormData();
      fd.append("file", f);
      if (sh) fd.append("sheet", sh);
      const p = await postForm<FilePreview>("/api/data/preview", fd);
      setPv(p); setName(p.suggested_name); setSheet(p.sheet ?? ""); setMap(p.operations.suggested); setDefaults({}); setConfirmed(false);
    } catch (e) { setPv(null); fail(e); } finally { setBusy(false); }
  }

  const reset = () => { setFile(null); setPv(null); setConfirmed(false); if (input.current) input.current.value = ""; };

  async function run() {
    if (!file || !pv) return;
    setBusy(true); setErr(null); setOk(null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (sheet) fd.append("sheet", sheet);
      if (dest === "table") {
        fd.append("table", name); fd.append("mode", mode);
        const r = await postForm<ImportResult>("/api/data/import", fd);
        setOk(`Loaded ${num(r.added)} rows into “${r.table}” (${num(r.rows)} in the table now, ${r.columns.length} columns).`);
      } else {
        fd.append("mapping", JSON.stringify(Object.fromEntries(Object.entries(map).filter(([, v]) => v))));
        fd.append("defaults", JSON.stringify(Object.fromEntries(Object.entries(defaults).filter(([, v]) => v.trim()))));
        fd.append("mode", mode === "replace" ? "replace" : "append");
        const r = await postForm<UploadResult>("/api/data/map-operations", fd);
        setOk(`Loaded ${num(r.rows_loaded)} rows into the operations dashboards, covering ${r.date_min} to ${r.date_max}.`);
      }
      reset(); onLoaded();
    } catch (e) { fail(e); } finally { setBusy(false); }
  }

  const needConfirm = dest === "operations" && mode === "replace";
  const opsMissing = pv?.operations.fields.filter((f) => f.required && !map[f.field] && !defaults[f.field]?.trim()) ?? [];
  const canRun = !!pv && !busy && (dest === "table" ? name.trim().length > 0 : opsMissing.length === 0) && (!needConfirm || confirmed);

  return (
    <section className="card space-y-4 p-5" aria-label="Import a file">
      <div className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide">
        <FileSpreadsheet className="h-4 w-4 text-accent" aria-hidden /> Bring in a file
      </div>
      <p className="text-sm text-muted">CSV, Excel (.xlsx) or JSON. Any columns are fine: types are detected for you, and the file is checked completely before anything is saved.</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted">
          File
          <input ref={input} type="file" accept=".csv,.tsv,.txt,.xlsx,.xlsm,.json" className="field"
                 onChange={(e) => { const f = e.target.files?.[0] ?? null; setFile(f); setPv(null); if (f) inspect(f); }} />
        </label>
        {pv?.sheets && pv.sheets.length > 1 && (
          <label className="flex flex-col gap-1 text-xs text-muted">Sheet
            <select className="field" value={sheet} onChange={(e) => { setSheet(e.target.value); if (file) inspect(file, e.target.value); }}>
              {pv.sheets.map((s) => <option key={s}>{s}</option>)}
            </select>
          </label>
        )}
        {busy && !pv && <span className="text-sm text-muted">Reading…</span>}
      </div>

      {pv && (
        <>
          <div className="text-sm text-muted">
            {num(pv.rows_total)} rows, {pv.columns.length} columns{pv.delimiter ? ` (separated by ${pv.delimiter})` : ""}.
          </div>
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full text-sm">
              <thead><tr>{pv.columns.map((c) => (
                <th key={c.name} className="th">{c.name}<div className="font-normal normal-case text-muted">{c.type}</div></th>
              ))}</tr></thead>
              <tbody>{pv.preview.slice(0, 5).map((r, i) => (
                <tr key={i} className="border-t border-line">{pv.columns.map((c) => <td key={c.name} className="td">{r[c.name] ?? <span className="text-muted">—</span>}</td>)}</tr>
              ))}</tbody>
            </table>
          </div>

          <div role="tablist" aria-label="Where should this go?" className="flex flex-wrap gap-2">
            <button role="tab" aria-selected={dest === "table"} className={`btn ${dest === "table" ? "btn-primary" : ""}`} onClick={() => setDest("table")}>Keep as its own table</button>
            <button role="tab" aria-selected={dest === "operations"} className={`btn ${dest === "operations" ? "btn-primary" : ""}`} onClick={() => setDest("operations")}>Feed the operations dashboards</button>
          </div>

          {dest === "table" ? (
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-xs text-muted">Table name
                <input className="field" value={name} onChange={(e) => setName(e.target.value)} maxLength={60} />
              </label>
              <label className="flex flex-col gap-1 text-xs text-muted">If it already exists
                <select className="field" value={mode} onChange={(e) => setMode(e.target.value as "replace" | "append")}>
                  <option value="replace">Replace it</option>
                  <option value="append">Add these rows (same columns)</option>
                </select>
              </label>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-muted">
                The revenue, cost and trend dashboards expect a fixed set of fields. Say which of your columns is which. Where your file has no such column, type a fixed value instead (for example <code>ALL</code> for entity_id, or <code>1</code> for units).
              </p>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {pv.operations.fields.map((f) => (
                  <div key={f.field} className="rounded-lg border border-line p-3">
                    <div className="text-sm font-semibold">{f.field}{f.required && <span style={{ color: "var(--bad)" }}> *</span>}</div>
                    <div className="mb-2 text-xs text-muted">{f.hint}</div>
                    <select aria-label={`Source column for ${f.field}`} className="field w-full" value={map[f.field] ?? ""} onChange={(e) => setMap({ ...map, [f.field]: e.target.value })}>
                      <option value="">{f.required ? "— none —" : "— skip —"}</option>
                      {pv.header.map((h) => <option key={h} value={h}>{h}</option>)}
                    </select>
                    {!map[f.field] && (
                      <input aria-label={`Fixed value for ${f.field}`} className="field mt-2 w-full" placeholder="or a fixed value" value={defaults[f.field] ?? ""} onChange={(e) => setDefaults({ ...defaults, [f.field]: e.target.value })} />
                    )}
                  </div>
                ))}
              </div>
              <label className="flex max-w-xs flex-col gap-1 text-xs text-muted">Existing operations data
                <select className="field" value={mode} onChange={(e) => { setMode(e.target.value as "replace" | "append"); setConfirmed(false); }}>
                  <option value="append">Add / update rows</option>
                  <option value="replace">Replace everything</option>
                </select>
              </label>
              {needConfirm && (
                <label className="flex items-center gap-2 text-sm" style={{ color: "var(--bad)" }}>
                  <input type="checkbox" checked={confirmed} onChange={(e) => setConfirmed(e.target.checked)} />
                  I understand this replaces the current records and entities in this workspace (Real takes a backup first).
                </label>
              )}
              {opsMissing.length > 0 && <p className="text-xs text-muted">Still needed: {opsMissing.map((f) => f.field).join(", ")}.</p>}
            </div>
          )}
          <button className="btn btn-primary" disabled={!canRun} onClick={run}><Upload className="h-4 w-4" aria-hidden /> {busy ? "Working…" : "Import"}</button>
        </>
      )}

      {ok && <div role="status" className="rounded-lg p-3 text-sm" style={{ background: "var(--good-bg)", color: "var(--good)" }}>{ok}</div>}
      {err && (
        <div role="alert" className="rounded-lg p-3 text-sm" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>
          <div className="font-semibold">{err.message}</div>
          {err.details.length > 0 && <ul className="mt-2 list-disc pl-5">{err.details.map((d) => <li key={d}>{d}</li>)}</ul>}
        </div>
      )}
    </section>
  );
}
