"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Table, Tabs, errMsg } from "./kit";
import { Lesson } from "./analysisKit";

interface Recipe { id: string; title: string; what: string; source_sql: string; sql: string; permanent: string; destructive: boolean; note: string }
interface Qn { n: number; question: string; concept: string; sql: string; note: string }
interface Cat {
  recipes: Recipe[]; interview: Qn[]; warning: string; sites_note: string;
  pandas: { section: string; items: { code: string; what: string; sql: string }[] }[];
  sites: { category: string; sites: { name: string; url: string; what: string }[] }[];
}
interface Out { columns: string[]; rows: (string | number | boolean | null)[][]; row_count: number }
const cell = (v: string | number | boolean | null) => (v == null ? "—" : String(v));
const Code = ({ children }: { children: string }) => <pre className="overflow-x-auto whitespace-pre-wrap break-words rounded border border-line bg-panel2 p-2 text-xs">{children}</pre>;
const TABS = [{ id: "recipes", label: "SQL cleaning recipes" }, { id: "interview", label: "SQL interview (50)" }, { id: "pandas", label: "pandas cheat sheet" }, { id: "sites", label: "Learning sites" }];

export function CookbookTab() {
  const [cat, setCat] = useState<Cat | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [tab, setTab] = useState("recipes");
  const [open, setOpen] = useState<string>("");
  const [out, setOut] = useState<{ before?: Out; after?: Out; result?: Out } | null>(null);
  const [filter, setFilter] = useState("");
  useEffect(() => { getJson<Cat>("/api/cookbook").then(setCat).catch((e) => setErr(errMsg(e, "Couldn't load the cookbook."))); }, []);
  const run = (kind: "recipe" | "interview", id: string) => {
    setOpen(id); setOut(null); setErr(null);
    postJson<{ before?: Out; after?: Out; result?: Out }>("/api/cookbook/run", { kind, id }).then(setOut).catch((e) => setErr(errMsg(e, "That query didn't run.")));
  };
  const show = (o?: Out, title?: string) => o && (
    <div className="mt-2">{title && <p className="text-xs font-semibold">{title}</p>}
      <Table head={o.columns} rows={o.rows.map((r) => r.map(cell))} /></div>);
  if (!cat) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      <Lesson text={cat.warning} />
      <Tabs tabs={TABS} value={tab} onChange={(t) => { setTab(t); setOpen(""); setOut(null); }} label="Cookbook" />
      {err && <ErrorBanner message={err} />}
      {tab === "recipes" && (
        <div className="space-y-3">
          <p className="text-xs text-muted">Each recipe shows the line from the cheat sheet, the DuckDB version this app needs, and runs it on a small messy sample table (8 rows) so you can see before and after.</p>
          {cat.recipes.map((r) => (
            <Section key={r.id} title={r.title}>
              <p className="text-sm">{r.what} {r.destructive && <Badge tone="warn">changes data if made permanent</Badge>}</p>
              <p className="mt-2 text-xs font-semibold">As printed on the cheat sheet (MySQL style)</p><Code>{r.source_sql}</Code>
              <p className="mt-2 text-xs font-semibold">DuckDB, safe preview (a SELECT)</p><Code>{r.sql}</Code>
              {r.permanent && <><p className="mt-2 text-xs font-semibold">To make it permanent (try in Practice first)</p><Code>{r.permanent}</Code></>}
              <p className="mt-2 text-xs text-muted">{r.note}</p>
              <button className="btn mt-2" onClick={() => run("recipe", r.id)}>{open === r.id && !out ? "Running…" : "Run on the sample"}</button>
              {open === r.id && out && <>{show(out.before, "Sample before")}{show(out.after, "Result")}</>}
            </Section>))}
        </div>
      )}
      {tab === "interview" && (
        <div className="space-y-3">
          <p className="text-xs text-muted">The 50 questions are from a Top 50 SQL interview sheet (question and concept). The answers are written for DuckDB and each one runs on the sample (employees, departments, customers, orders). Try writing your own first in the SQL Lab, then compare. Where ties or NULLs change the answer, the note says so.</p>
          <input className="field w-full max-w-sm" placeholder="Filter, e.g. LAG or salary" aria-label="Filter questions" value={filter} onChange={(e) => setFilter(e.target.value)} />
          {cat.interview.filter((q) => !filter || `${q.question} ${q.concept}`.toLowerCase().includes(filter.toLowerCase())).map((q) => (
            <details key={q.n} className="card p-3" onToggle={(e) => { if ((e.target as HTMLDetailsElement).open && open !== String(q.n)) run("interview", String(q.n)); }}>
              <summary className="cursor-pointer text-sm"><b>{q.n}.</b> {q.question} <Badge>{q.concept}</Badge></summary>
              <div className="mt-2"><Code>{q.sql}</Code>{q.note && <p className="mt-1 text-xs text-muted">{q.note}</p>}
                {open === String(q.n) && (out?.result ? show(out.result, "Result on the sample") : <p className="text-xs text-muted">Running…</p>)}</div>
            </details>))}
        </div>
      )}
      {tab === "pandas" && (
        <div className="space-y-3">
          {cat.pandas.map((s) => (
            <Section key={s.section} title={s.section}>
              <Table head={["pandas", "What it does", "SQL equivalent"]} rows={s.items.map((i) => [<code key="c" className="text-xs">{i.code}</code>, i.what, <code key="q" className="text-xs">{i.sql}</code>])} />
            </Section>))}
          <p className="text-xs text-muted">Run pandas in the Python lab notebooks. Copy a copy of your data first (df = df.copy()) so cleaning never touches the original.</p>
        </div>
      )}
      {tab === "sites" && (
        <div className="space-y-3">
          <Lesson text={cat.sites_note} />
          {cat.sites.map((c) => (
            <Section key={c.category} title={c.category}>
              <Table head={["Site", "Address", "Good for"]} rows={c.sites.map((s) => [s.name, <code key="u" className="text-xs">{s.url}</code>, s.what])} />
            </Section>))}
        </div>
      )}
    </div>
  );
}
