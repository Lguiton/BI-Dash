"use client";
import { FileSpreadsheet, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { ApiError, getJson, postForm } from "@/lib/api";
import { num } from "@/lib/format";
import type { FilePreview, ImportResult, SchemaDiff, UploadResult } from "@/lib/types";

type Dest = "table" | "operations";

export function ImportPanel({ onLoaded }: { onLoaded: () => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [pv, setPv] = useState<FilePreview | null>(null);
  const [sheet, setSheet] = useState<string>("");
  const [dest, setDest] = useState<Dest>("table");
  const [name, setName] = useState("");
  const [mode, setMode] = useState<"replace" | "append" | "append_new">("replace");
  const [newBy, setNewBy] = useState<"key" | "date">("key");
  const [newCol, setNewCol] = useState("");
  const [rescue, setRescue] = useState(false);
  const [diff, setDiff] = useState<SchemaDiff | null>(null);
  const [map, setMap] = useState<Record<string, string>>({});
  const [defaults, setDefaults] = useState<Record<string, string>>({});
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [guide, setGuide] = useState<{ id: string; name: string; ext: string; in_app: string }[] | null>(null);
  const [showGuide, setShowGuide] = useState(false);
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
      setPv(p); setDiff(p.schema_diff ?? null); setNewCol(p.header[0] ?? ""); setName(p.suggested_name); setSheet(p.sheet ?? ""); setMap(p.operations.suggested); setDefaults({}); setConfirmed(false);
    } catch (e) { setPv(null); fail(e); } finally { setBusy(false); }
  }

  async function recheck(tbl: string) {
    if (!file || !tbl.trim()) return;
    try {
      const fd = new FormData();
      fd.append("file", file); fd.append("table", tbl);
      if (sheet) fd.append("sheet", sheet);
      const p = await postForm<FilePreview>("/api/data/preview", fd);
      setDiff(p.schema_diff ?? null);
    } catch { /* the import itself will report any real problem */ }
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
        if (rescue && mode !== "replace") fd.append("rescue", "true");
        if (mode === "append_new") fd.append(newBy === "key" ? "key" : "date_column", newCol);
        const r = await postForm<ImportResult>("/api/data/import", fd);
        const d = r.schema_diff;
        setOk(`Loaded ${num(r.added)} ${mode === "append_new" ? "new " : ""}rows into “${r.table}”${r.skipped_existing ? ` (${num(r.skipped_existing)} already there were skipped)` : ""}; ${num(r.rows)} in the table now, ${r.columns.length} columns.${r.rescued_columns?.length ? ` Kept ${r.rescued_columns.join(", ")} in the _rescued column.` : ""}${d && !d.identical ? " The columns differed from before: " + [d.added.length ? `added ${d.added.join(", ")}` : "", d.removed.length ? `removed ${d.removed.join(", ")}` : "", d.type_changed.length ? `type changed ${d.type_changed.map((t) => t.column).join(", ")}` : ""].filter(Boolean).join("; ") + "." : ""}`);
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
      <p className="text-sm text-muted">CSV, Excel (.xlsx), JSON, JSON lines, XML, or a PDF that contains a ruled table. Any columns are fine: types are detected for you, and the file is checked completely before anything is saved.</p>
      <div className="flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted">
          File
          <input ref={input} type="file" accept=".csv,.tsv,.txt,.xlsx,.xlsm,.json,.jsonl,.ndjson,.xml,.pdf" className="field"
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
      <div className="text-xs">
        <button type="button" className="underline" aria-expanded={showGuide} onClick={() => { const next = !showGuide; setShowGuide(next); if (next && !guide) getJson<{ formats: { id: string; name: string; ext: string; in_app: string }[] }>("/api/data/formats").then((d) => setGuide(d.formats)).catch(() => setGuide([])); }}>
          {showGuide ? "Hide" : "Which file formats can I use?"}
        </button>
        {showGuide && (guide === null ? <p className="mt-1 text-muted">Loading…</p> : (
          <ul className="mt-2 space-y-1 text-muted">{guide.map((g) => <li key={g.id}><b>{g.name}</b> ({g.ext}): {g.in_app}</li>)}</ul>
        ))}
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

          {dest === "table" && diff && (
            <div role="status" className="rounded-lg border border-line p-3 text-sm" style={diff.identical ? undefined : { background: "var(--bad-bg)", color: "var(--bad)" }}>
              <b>{diff.identical ? "No schema change." : "Schema change detected."}</b> {diff.summary}
              {!diff.identical && (
                <ul className="mt-1 list-disc pl-5">
                  {diff.added.length > 0 && <li>New columns: {diff.added.join(", ")}</li>}
                  {diff.removed.length > 0 && <li>Missing columns: {diff.removed.join(", ")}</li>}
                  {diff.type_changed.map((t) => <li key={t.column}>{t.column} was {t.was}, now {t.now}</li>)}
                  {diff.reordered && <li>Same columns in a different order</li>}
                </ul>
              )}
            </div>
          )}

          <div role="tablist" aria-label="Where should this go?" className="flex flex-wrap gap-2">
            <button role="tab" aria-selected={dest === "table"} className={`btn ${dest === "table" ? "btn-primary" : ""}`} onClick={() => setDest("table")}>Keep as its own table</button>
            <button role="tab" aria-selected={dest === "operations"} className={`btn ${dest === "operations" ? "btn-primary" : ""}`} onClick={() => setDest("operations")}>Feed the operations dashboards</button>
          </div>

          {dest === "table" ? (
            <div className="flex flex-wrap items-end gap-3">
              <label className="flex flex-col gap-1 text-xs text-muted">Table name
                <input className="field" value={name} onChange={(e) => setName(e.target.value)} onBlur={() => recheck(name)} maxLength={60} />
              </label>
              <label className="flex flex-col gap-1 text-xs text-muted">If it already exists
                <select className="field" value={mode} onChange={(e) => setMode(e.target.value as "replace" | "append" | "append_new")}>
                  <option value="replace">Replace it</option>
                  <option value="append">Add these rows (same columns)</option>
                  <option value="append_new">Add only new rows</option>
                </select>
              </label>
              {mode !== "replace" && (
                <label className="flex items-center gap-2 self-end text-xs text-muted"><input type="checkbox" checked={rescue} onChange={(e) => setRescue(e.target.checked)} /> Keep extra columns in a _rescued column instead of refusing</label>
              )}
              {mode === "append_new" && (
                <>
                  <label className="flex flex-col gap-1 text-xs text-muted">A row is new when
                    <select className="field" value={newBy} onChange={(e) => setNewBy(e.target.value as "key" | "date")} aria-label="How to tell a row is new">
                      <option value="key">its key is not in the table yet</option>
                      <option value="date">its date is after the newest date there</option>
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-muted">{newBy === "key" ? "Key column" : "Date column"}
                    <select className="field" value={newCol} onChange={(e) => setNewCol(e.target.value)} aria-label="Column used to find new rows">
                      {pv.header.map((h) => <option key={h} value={h}>{h}</option>)}
                    </select>
                  </label>
                </>
              )}
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
