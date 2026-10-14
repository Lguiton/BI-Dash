"use client";
import { useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "@/components/panels/kit";
import { Notes, Pick } from "./common";

type Out = { title: string; language: string; code: string; explain: string[]; run_first: string[]; verify: string; safety: { severity: string; says: string }[]; caution: string };
const KINDS = [
  { id: "create_table", label: "Create a table" }, { id: "upsert", label: "Insert or update (upsert)" }, { id: "dedupe", label: "Remove duplicates into a new table" },
  { id: "load_csv", label: "Load a CSV file" }, { id: "migration", label: "Change a table (with the way back)" }, { id: "backup", label: "Backup script" }, { id: "schedule", label: "Schedule a script" },
];
const DB = ["duckdb", "postgres", "mysql", "sqlite"].map((x) => ({ id: x, label: x }));
const SH = [{ id: "bash", label: "bash (Linux, Mac, WSL)" }, { id: "powershell", label: "PowerShell (Windows)" }];
const TYPES = ["text", "integer", "number", "decimal", "date", "timestamp", "bool"];

// "id:integer:pk, email:text:unique:required, amt:decimal" -> column objects
function parseCols(t: string) {
  return t.split(",").map((x) => x.trim()).filter(Boolean).map((x) => {
    const [name, type = "text", ...flags] = x.split(":").map((s) => s.trim());
    return { name, type: TYPES.includes(type) ? type : "text", primary: flags.includes("pk"), unique: flags.includes("unique"), nullable: !(flags.includes("required") || flags.includes("pk")) };
  });
}
const list = (t: string) => t.split(",").map((x) => x.trim()).filter(Boolean);

export function Scripts() {
  const [kind, setKind] = useState("create_table");
  const [f, setF] = useState({ dialect: "duckdb", shell: "bash", table: "", cols: "id:integer:pk, name:text:required, created:date", key: "id", idx: "", keys: "", newt: "", order: "", path: "", action: "add_column", col: "", newname: "", ctype: "text", src: "", dest: "", keep: "14", when: "02:30", days: "daily" });
  const [out, setOut] = useState<Out | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const set = (k: keyof typeof f) => (v: string) => setF({ ...f, [k]: v });
  const t = (k: keyof typeof f, label: string) => <Field label={label}><input aria-label={label} className="input" value={f[k]} onChange={(e) => set(k)(e.target.value)} /></Field>;

  function params(): Record<string, unknown> {
    switch (kind) {
      case "create_table": return { dialect: f.dialect, table: f.table, columns: parseCols(f.cols), indexes: f.idx.trim() ? [list(f.idx)] : [] };
      case "upsert": return { dialect: f.dialect, table: f.table, columns: parseCols(f.cols), key: list(f.key) };
      case "dedupe": return { dialect: f.dialect, table: f.table, keys: list(f.keys), new_table: f.newt, order_col: f.order || null, keep: f.order ? "newest" : "first" };
      case "load_csv": return { dialect: f.dialect, table: f.table, path: f.path };
      case "migration": return { dialect: f.dialect, table: f.table, action: f.action, column: f.col, new_name: f.newname, col_type: f.ctype, index_cols: list(f.idx) };
      case "backup": return { shell: f.shell, engine: f.dialect, source: f.src, dest_dir: f.dest, keep_days: +f.keep };
      default: return { shell: f.shell, script_path: f.path, when: f.when, days: f.days };
    }
  }
  async function make() {
    setErr(null); setOut(null); setCopied(false);
    try { setOut(await postJson<Out>("/api/toolbox/scripts", { kind, params: params() })); } catch (e) { setErr(errMsg(e, "Could not write that script.")); }
  }
  const needsTable = ["create_table", "upsert", "dedupe", "load_csv", "migration"].includes(kind);
  const isShell = kind === "backup" || kind === "schedule";
  return (
    <Section title="Scripts to paste" note="Writes SQL and shell scripts as TEXT. Nothing is run, and nothing is installed. Names are checked, and risky statements are flagged.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2 sm:grid-cols-3">
        <Pick label="What do you need?" value={kind} onChange={(v) => { setKind(v); setOut(null); }} options={KINDS} blank="" />
        {!isShell || kind === "backup" ? <Pick label={kind === "backup" ? "Database type" : "Database"} value={f.dialect} onChange={set("dialect")} options={DB} blank="" /> : null}
        {isShell && <Pick label="Shell" value={f.shell} onChange={set("shell")} options={SH} blank="" />}
        {needsTable && t("table", "Table name")}
      </div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        {(kind === "create_table" || kind === "upsert") && t("cols", "Columns as name:type:flags (flags pk, unique, required)")}
        {kind === "create_table" && t("idx", "Index on columns (optional, comma separated)")}
        {kind === "upsert" && t("key", "Key column(s)")}
        {kind === "dedupe" && <>{t("keys", "Columns that identify a duplicate")}{t("newt", "New table name")}{t("order", "Date column to keep the newest (optional)")}</>}
        {(kind === "load_csv" || kind === "schedule") && t("path", kind === "load_csv" ? "CSV file path" : "Script path")}
        {kind === "migration" && <>
          <Pick label="Change" value={f.action} onChange={set("action")} options={[{ id: "add_column", label: "Add a column" }, { id: "rename_column", label: "Rename a column" }, { id: "drop_column", label: "Drop a column" }, { id: "add_index", label: "Add an index" }]} blank="" />
          {f.action !== "add_index" && t("col", "Column")}
          {f.action === "rename_column" && t("newname", "New column name")}
          {f.action === "add_column" && <Pick label="Type" value={f.ctype} onChange={set("ctype")} options={TYPES.map((x) => ({ id: x, label: x }))} blank="" />}
          {f.action === "add_index" && t("idx", "Index on columns")}</>}
        {kind === "backup" && <>{t("src", "Database file path or name")}{t("dest", "Backup folder")}{t("keep", "Keep copies for (days)")}</>}
        {kind === "schedule" && <>{t("when", "Time (24-hour, 02:30)")}<Pick label="How often" value={f.days} onChange={set("days")} options={[{ id: "daily", label: "Every day" }, { id: "weekdays", label: "Weekdays" }, { id: "weekly", label: "Sundays" }]} blank="" /></>}
      </div>
      <button className="btn mt-3" onClick={make}>Write the script</button>
      {out && (
        <div className="mt-3 grid gap-2">
          <h4 className="text-sm font-semibold">{out.title}</h4>
          <Notes items={out.safety.map((s) => `${s.severity === "high" ? "Careful: " : ""}${s.says}`)} />
          <div className="flex gap-2"><button className="btn" onClick={async () => { try { await navigator.clipboard.writeText(out.code); setCopied(true); } catch { setErr("Could not copy. Select the text and copy it by hand."); } }}>{copied ? "Copied" : "Copy"}</button><Badge tone="muted">not run</Badge></div>
          <pre aria-label="Script" className="max-h-96 overflow-auto whitespace-pre rounded bg-panel2 p-3 text-xs">{out.code}</pre>
          <div className="text-sm"><b>What it does</b><ul className="list-disc pl-5">{out.explain.map((e, i) => <li key={i}>{e}</li>)}</ul></div>
          <div className="text-sm"><b>Before you run it</b><ul className="list-disc pl-5">{out.run_first.map((e, i) => <li key={i}>{e}</li>)}</ul></div>
          <p className="text-sm"><Badge tone="ok">Check it worked</Badge> {out.verify}</p>
          <p className="text-xs text-muted">{out.caution}</p>
        </div>
      )}
    </Section>
  );
}
