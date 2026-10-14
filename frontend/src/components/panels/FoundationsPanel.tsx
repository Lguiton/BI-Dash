"use client";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson } from "@/lib/api";
import { QualTab } from "./AnalysisQual";
import { Badge, Section, Stat, Table, bytes, errMsg, num } from "./kit";

// ---------------------------------------------------------------- file formats
interface Fmt { id: string; name: string; ext: string; family: string; structure: string; benefits: string; limits: string; in_app: string }
export function FormatsTab() {
  const [f, setF] = useState<Fmt[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<{ formats: Fmt[] }>("/api/data/formats").then((d) => setF(d.formats)).catch((e) => setErr(errMsg(e, "Couldn't load the guide."))); }, []);
  if (err) return <ErrorBanner message={err} />;
  if (!f) return <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-3">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">A file format is the way data is laid out in a file. Structured data fits rows and columns; semi-structured has tags or nesting; unstructured is free text. Load any of these in My data, then analyze it here.</p>
      {f.map((x) => (
        <Section key={x.id} title={x.name}>
          <div className="mb-2 flex flex-wrap gap-2"><Badge>{x.family}</Badge><Badge>{x.ext}</Badge></div>
          <dl className="space-y-1 text-sm">
            <div><dt className="inline font-semibold">Structure: </dt><dd className="inline">{x.structure}</dd></div>
            <div><dt className="inline font-semibold">Good for: </dt><dd className="inline">{x.benefits}</dd></div>
            <div><dt className="inline font-semibold">Watch out: </dt><dd className="inline">{x.limits}</dd></div>
            <div><dt className="inline font-semibold">In this app: </dt><dd className="inline">{x.in_app}</dd></div>
          </dl>
        </Section>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- big data practice
interface Dataset { rows: number; csv_bytes: number; parquet_bytes: number; partitioned_bytes: number; partition_files: number; partitions: number }
interface Job { status: string; step: string; progress: number; error: string | null; result: Record<string, unknown> | null }
interface State {
  machine: { cpus: number | null; ram_bytes: number | null; disk_free_bytes: number }; max_rows: number; memory_limit: string; threads: number;
  presets: { rows: number; estimate_bytes: number; ok: boolean }[]; dataset: Dataset | null; job: Job; honest_note: string;
}
interface Bench {
  rows: number; all_formats_agree: boolean; compression_vs_csv: number | null; partition_note: string;
  queries: { query: string; ms: { csv: number; parquet: number; partitioned: number }; speedup_parquet: number | null }[];
  sample: { exact: number; approx: number; error_pct: number; exact_ms: number; sample_ms: number };
}
export function BigDataTab() {
  const [s, setS] = useState<State | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [bench, setBench] = useState<Bench | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [rows, setRows] = useState(1_000_000);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);
  const load = () => getJson<State>("/api/stats/bigdata").then((d) => { setS(d); setJob(d.job); if (d.job.status === "running") poll(); }).catch((e) => setErr(errMsg(e, "Couldn't read the machine.")));
  const stop = () => { if (timer.current) { clearInterval(timer.current); timer.current = null; } };
  const poll = () => {
    stop();
    timer.current = setInterval(() => {
      getJson<Job>("/api/stats/bigdata/job").then((j) => {
        setJob(j);
        if (j.status !== "running") {
          stop();
          if (j.status === "done" && j.result && "queries" in j.result) setBench(j.result as unknown as Bench);
          getJson<State>("/api/stats/bigdata").then(setS).catch(() => undefined);
        }
      }).catch(() => stop());
    }, 1500);
  };
  useEffect(() => { void load(); return stop; }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const go = async (path: string, body?: object) => {
    setErr(null); setBench(null);
    try { await postJson(path, body ?? {}); setJob({ status: "running", step: "starting", progress: 0, error: null, result: null }); poll(); } catch (e) { setErr(errMsg(e, "Couldn't start that.")); }
  };
  const clean = async () => { setErr(null); try { await deleteJson("/api/stats/bigdata"); setBench(null); await load(); } catch (e) { setErr(errMsg(e, "Couldn't clean up.")); } };
  if (!s) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Reading this computer…</p>;
  const running = job?.status === "running";
  const d = s.dataset;
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">{s.honest_note}</p>
      <div className="grid gap-3 sm:grid-cols-4">
        <Stat label="CPU cores" value={String(s.machine.cpus ?? "?")} />
        <Stat label="Memory" value={s.machine.ram_bytes ? bytes(s.machine.ram_bytes) : "?"} />
        <Stat label="Free disk" value={bytes(s.machine.disk_free_bytes)} />
        <Stat label="Most rows safe here" value={num(s.max_rows, 0)} sub={`limits: ${s.memory_limit} memory, ${s.threads} threads`} />
      </div>
      {err && <ErrorBanner message={err} />}
      <Section title="1. Make practice data (made-up orders)">
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-xs text-muted">How many rows
            <select className="field mt-1" value={rows} onChange={(e) => setRows(Number(e.target.value))}>
              {s.presets.map((p) => <option key={p.rows} value={p.rows} disabled={!p.ok}>{num(p.rows, 0)} rows (about {bytes(p.estimate_bytes)} on disk){p.ok ? "" : " – not enough disk"}</option>)}
            </select></label>
          <button className="btn btn-primary" disabled={running} onClick={() => go("/api/stats/bigdata/generate", { rows })}>{running ? "Working…" : "Make the data"}</button>
          {d && <button className="btn" disabled={running} onClick={clean}>Clean up files</button>}
        </div>
        {running && job && <div className="mt-3 text-sm" role="status"><p>{job.step}…</p><progress className="w-full" max={100} value={job.progress} aria-label="Progress" /></div>}
        {job?.status === "error" && <div className="mt-2"><ErrorBanner message={job.error ?? "That failed."} /></div>}
        {d && <p className="mt-3 text-sm">You have <b>{num(d.rows, 0)}</b> rows: CSV {bytes(d.csv_bytes)}, Parquet {bytes(d.parquet_bytes)}, Parquet split into {d.partitions} month folders {bytes(d.partitioned_bytes)}.</p>}
      </Section>
      {d && (
        <Section title="2. Race the formats">
          <button className="btn btn-primary" disabled={running} onClick={() => go("/api/stats/bigdata/benchmark")}>Run the race</button>
          {bench && (
            <div className="mt-3 space-y-3">
              <Table head={["Question", "CSV (ms)", "Parquet (ms)", "Month folders (ms)", "Parquet vs CSV"]} rows={bench.queries.map((q) => [q.query, num(q.ms.csv, 1), num(q.ms.parquet, 1), num(q.ms.partitioned, 1), q.speedup_parquet ? `${q.speedup_parquet}x faster` : "—"])} />
              <p className="text-sm">Parquet is {bench.compression_vs_csv ?? "?"}x smaller than CSV. {bench.partition_note} {bench.all_formats_agree ? "All three formats gave the same answers." : "The formats disagreed on an answer, so treat the timings with care."}</p>
              <p className="text-sm"><b>Sampling:</b> the exact average was {num(bench.sample.exact, 2)} ({num(bench.sample.exact_ms, 1)} ms); a 1% sample gave {num(bench.sample.approx, 2)} ({num(bench.sample.sample_ms, 1)} ms), off by {bench.sample.error_pct}%. Sampling saves work when a file must be read in full, and it is not always faster on Parquet.</p>
            </div>
          )}
        </Section>
      )}
      <Section title="What makes data big (the 5 Vs)">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li><b>Volume:</b> too much to open in a spreadsheet or hold in memory.</li>
          <li><b>Velocity:</b> arrives fast, like clicks or sensor readings.</li>
          <li><b>Variety:</b> tables, text, logs, images, JSON all together.</li>
          <li><b>Veracity:</b> how trustworthy it is. More data does not fix bad data.</li>
          <li><b>Value:</b> whether answering the question is worth the cost.</li>
        </ul>
        <p className="mt-2 text-sm text-muted">You need a cluster (Spark, Hadoop) when the data no longer fits one machine&apos;s disk or the job takes too long on one machine. Before that, columnar files, partitions and a streaming engine like DuckDB go a long way.</p>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- challenges of implementing BI
const CHALLENGES: { id: string; name: string; problem: string; fix: string; here: string }[] = [
  { id: "software", name: "Choosing the right software", problem: "Needs differ, the market keeps changing, and licences, roles and permissions all have to fit.", fix: "Write down what you need first, then pick a vendor with real industry experience. Judge by return on investment.", here: "This dashboard is yours, runs on your computer and has no licences or logins. Re-check that it still fits your needs every few months." },
  { id: "integration", name: "Data integration", problem: "Data arrives from many sources in many formats, and raw unstructured data causes mismatched reports.", fix: "Pull it into one central place, structured and pre-summarized, before analysing.", here: "My data and Sources bring files into one database (CSV, Excel, JSON, XML, PDF tables). See the File formats tab." },
  { id: "quality", name: "Data quality", problem: "Typing mistakes, duplicates, invalid values and inconsistent formats lead to bad decisions.", fix: "Agree standard ways to collect, store and check data, and name who owns each part.", here: "Imports are checked completely before saving. On the Prescriptive type, 'Check my data is fit to act on' tests size, gaps and freshness." },
  { id: "skills", name: "Shortage of skilled people", problem: "A good plan still fails if nobody can read the data correctly.", fix: "Give tailored, ongoing training that matches what people actually do.", here: "Each Analysis Lab tool has a short plain-language lesson, and the Learn tracks teach the skills step by step." },
  { id: "adoption", name: "Culture and low adoption", problem: "People used to gut feeling resist new tools. (Coca-Cola met this and answered with data-literacy training and leadership backing.)", fix: "Train people, show the benefits, and have leaders use the numbers themselves.", here: "For one person, adoption is a habit: pick a weekly time to open the dashboard and log one decision in 'Track the result'." },
  { id: "cost", name: "Cost", problem: "Software, infrastructure, licences, training and maintenance add up and need buy-in.", fix: "Plan strategically, automate repetitive work, and put effort where it earns revenue or keeps customers.", here: "Everything here is free and local. The scheduled jobs and backups automate the repetitive parts." },
  { id: "kpis", name: "Choosing the right KPIs", problem: "Tracking the wrong measures means steering by the wrong gauge, and too many drown you.", fix: "Start from business objectives, pick a few KPIs that show progress against them, and give each audience what they need.", here: "Business metrics (Quantitative, Descriptive) shows margin, monthly revenue and burn. Write your goal first, then keep only the numbers that move it." },
  { id: "governance", name: "Data governance", problem: "Without rules you get inconsistent data, security slips and compliance trouble.", fix: "Set policies for existing and new data: owners, controls, audit trails, and a master version of key records.", here: "Practice and Real workspaces keep test data apart, Settings & backups protect your data, and the Activity log records changes." },
  { id: "scale", name: "Scalability", problem: "Data and users grow, and a setup that worked small slows down or breaks.", fix: "Choose storage and formats that grow (columnar files, partitions) and test with bigger data before you need it.", here: "The Big data (practice) tab shows how far this computer can go and when you would need more." },
  { id: "feedback", name: "Listening to users", problem: "A BI project without feedback drifts from what people need.", fix: "Say what the scope, timeline and benefits are, then gather feedback and adjust.", here: "Use Observations (Qualitative) to note what annoys or helps you, and review them monthly." },
];
const LEVELS = [{ v: "", l: "Not rated" }, { v: "weak", l: "Needs work" }, { v: "ok", l: "Getting there" }, { v: "strong", l: "In good shape" }];
const KEY = "bi_challenges_v1";
export function ChallengesTab() {
  const [rate, setRate] = useState<Record<string, string>>({});
  useEffect(() => {
    try { const raw = window.localStorage.getItem(KEY); if (raw) Promise.resolve(JSON.parse(raw) as Record<string, string>).then(setRate); } catch { /* storage unavailable */ }
  }, []);
  const set = (id: string, v: string) => {
    const next = { ...rate, [id]: v };
    setRate(next);
    try { window.localStorage.setItem(KEY, JSON.stringify(next)); } catch { /* ignore */ }
  };
  const rated = CHALLENGES.filter((c) => rate[c.id]);
  const weak = CHALLENGES.filter((c) => rate[c.id] === "weak");
  return (
    <div className="space-y-3">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Most BI projects stumble on the same ten things. For each: why it hurts, the usual cure, and where this dashboard helps. Rate yourself honestly; the list of what needs work builds below. The ratings stay in this browser.</p>
      <Section title="Where you stand">
        <p className="text-sm">{rated.length === 0 ? "Rate the challenges below to see your list." : weak.length === 0 ? `Rated ${rated.length} of ${CHALLENGES.length}. Nothing marked as needing work.` : `Needs work (${weak.length}): ${weak.map((c) => c.name).join(", ")}.`}</p>
      </Section>
      {CHALLENGES.map((c) => (
        <Section key={c.id} title={c.name}>
          <dl className="space-y-1 text-sm">
            <div><dt className="inline font-semibold">The problem: </dt><dd className="inline">{c.problem}</dd></div>
            <div><dt className="inline font-semibold">The usual cure: </dt><dd className="inline">{c.fix}</dd></div>
            <div><dt className="inline font-semibold">In this dashboard: </dt><dd className="inline">{c.here}</dd></div>
          </dl>
          <label className="mt-2 block text-xs text-muted">How are you doing here?
            <select className="field mt-1 max-w-xs" value={rate[c.id] ?? ""} onChange={(e) => set(c.id, e.target.value)} aria-label={`Your rating for ${c.name}`}>
              {LEVELS.map((l) => <option key={l.v} value={l.v}>{l.l}</option>)}
            </select></label>
        </Section>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- key components of BI
const COMPONENTS: { name: string; what: string; example: string; here: { label: string; href: string }[]; note?: string }[] = [
  { name: "Data sources and integration", what: "Gathering data from many places (databases, ERP, CRM, web apps, web services, flat files, RSS feeds) and consolidating it, usually with ETL: extract, transform, load.", example: "A multinational pulling supply-chain data from several systems into one place.", here: [{ label: "My data", href: "/data" }, { label: "Pipeline", href: "/pipeline" }] },
  { name: "Data warehouse and data marts", what: "A central store that structures data for analysis. A data mart is a slice of it for one business function or subject. Modeling, indexing and storage tuning keep queries fast. (Cloud examples: Redshift, Snowflake, BigQuery.)", example: "Historical sales kept together to plan seasonal offers.", here: [{ label: "Star schema", href: "/schema" }, { label: "Dataset hub", href: "/hub" }], note: "Your DuckDB file is a small warehouse on this computer." },
  { name: "Data analysis and data mining", what: "Analysis slices and dices data into something simple to read. Mining detects patterns in large data and predicts what may come.", example: "Finding which product groups sell together.", here: [{ label: "Analysis Lab", href: "/analysis" }], note: "Clusters, Bought together and Machine learning are the mining tools." },
  { name: "Reporting and visualization", what: "Dashboards, reports and charts that show KPIs and trends in a form people can act on.", example: "A dashboard that turns the supply-chain data into charts.", here: [{ label: "Dashboard", href: "/" }, { label: "KPIs", href: "/kpis" }] },
  { name: "OLAP (online analytical processing)", what: "Multi-dimensional analysis: the same numbers broken down by dimensions such as place, time and product, then sliced or rolled up.", example: "Smartphone sales in Q3, in Asia, for ages 20-29.", here: [{ label: "SQL Lab", href: "/lab" }, { label: "Analysis Lab", href: "/analysis" }], note: "GROUP BY queries and Filters do the slicing. A full OLAP cube is not built in." },
  { name: "Corporate performance management (CPM)", what: "Methods, metrics and systems for tracking and managing performance, tying KPIs to plans and financial planning.", example: "A fast-food chain judging a new dish's sales to set its menu.", here: [{ label: "KPIs", href: "/kpis" }, { label: "Company", href: "/company" }], note: "Business metrics and Track the result in the Analysis Lab cover the personal version." },
  { name: "Advanced analytics", what: "Predictive modeling, machine learning, process automation and deep learning to find trends, patterns and anomalies.", example: "Spotting unusual orders or forecasting demand.", here: [{ label: "Analysis Lab", href: "/analysis" }, { label: "ML Lab", href: "/ml" }] },
  { name: "Real-time BI", what: "Up-to-the-minute data so KPIs can be watched live and decisions made fast.", example: "Uber's surge pricing, set from live traffic, drivers and demand.", here: [], note: "Honest limit: this dashboard updates when you load data or a scheduled job runs. It is not a live stream." },
  { name: "Self-serve BI", what: "Letting people explore data on their own, without waiting for an analyst: spotting trends and patterns with friendly tools.", example: "A manager answering their own question in minutes.", here: [{ label: "Analysis Lab", href: "/analysis" }], note: "The plain-language lessons and warnings exist so you can read results without an analyst." },
];
export function ComponentsTab() {
  return (
    <div className="space-y-3">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">A BI system is a chain: data comes in, is stored and organized, is analyzed, then shown so people can decide. Here is each link, with where it lives in this dashboard.</p>
      {COMPONENTS.map((c, i) => (
        <Section key={c.name} title={`${i + 1}. ${c.name}`}>
          <dl className="space-y-1 text-sm">
            <div><dt className="inline font-semibold">What it is: </dt><dd className="inline">{c.what}</dd></div>
            <div><dt className="inline font-semibold">Example: </dt><dd className="inline">{c.example}</dd></div>
            <div><dt className="inline font-semibold">In this dashboard: </dt><dd className="inline">{c.here.length ? c.here.map((h, j) => <span key={h.href + h.label}>{j > 0 && ", "}<Link href={h.href} className="underline">{h.label}</Link></span>) : "Not built in."}{c.note ? ` ${c.note}` : ""}</dd></div>
          </dl>
        </Section>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- categories of BI tools
type Cover = "built" | "partial" | "guide" | "no";
const COVER: Record<Cover, { label: string; tone: "ok" | "warn" | "muted" | "bad" }> = { built: { label: "Built in", tone: "ok" }, partial: { label: "Partly built in", tone: "warn" }, guide: { label: "Use an outside tool (guide)", tone: "muted" }, no: { label: "Not covered", tone: "bad" } };
const TOOL_CATS: { name: string; examples: string; cover: Cover; here: string; href?: string }[] = [
  { name: "UML and diagramming", examples: "Draw.io, Lucidchart", cover: "built", here: "Diagram studio draws flow and architecture diagrams; Star schema shows the data model.", href: "/diagrams" },
  { name: "ETL (extract, transform, load)", examples: "DataStage, Informatica, Talend, AWS Glue, Azure Data Factory", cover: "built", here: "Pipeline, Pipelines, Workflow builder and the Apache page practise the same extract-transform-load steps on a small scale.", href: "/pipeline" },
  { name: "Data warehousing", examples: "Redshift, BigQuery, Snowflake, Synapse, Db2 Warehouse", cover: "partial", here: "DuckDB is a real columnar warehouse engine, on one computer. The cloud services are not used (you chose to skip cloud add-ons).", href: "/schema" },
  { name: "Data preparation and cleaning", examples: "Excel, Talend Data Preparation, Informatica", cover: "built", here: "Imports are validated, and the Data quality page and Analysis Lab input check find gaps, duplicates and stale data.", href: "/quality" },
  { name: "Visualization and dashboarding", examples: "Tableau, Power BI, Looker, Qlik, Sisense, Domo", cover: "built", here: "The Dashboard, Company and KPIs pages, plus charts in every Analysis Lab tool. docs/TABLEAU.md and docs/BI_TOOLS.md show how to rebuild it in Tableau, Superset and Power BI.", href: "/" },
  { name: "Reporting and querying", examples: "Cognos, Business Objects, MicroStrategy, Zoho, Oracle BI", cover: "built", here: "SQL Lab runs ad-hoc queries; data can be exported as CSV, Excel, Parquet or JSON for reports.", href: "/lab" },
  { name: "Mobile BI", examples: "Power BI mobile, QuickSight", cover: "partial", here: "Every page works at phone width in a browser on the same network. A phone app (PWA) is on hold.", },
  { name: "Cloud / SaaS BI", examples: "Looker, Domo, Alteryx, Power BI service", cover: "no", here: "On purpose: this is a personal, local tool with no logins. Skipped by your choice." },
  { name: "Spreadsheets", examples: "Excel, LibreOffice Calc, Google Sheets", cover: "guide", here: "Export your data (xlsx or csv) and open it in LibreOffice Calc, or bring a spreadsheet in with My data. See the LibreOffice steps below.", href: "/data" },
];
export function ToolCategoriesTab() {
  return (
    <div className="space-y-3">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">BI tools fall into nine families, and one product can span several. This is where each family stands in your dashboard.</p>
      <ul className="space-y-2">
        {TOOL_CATS.map((c) => (
          <li key={c.name} className="card min-w-0 space-y-1 p-3 text-sm">
            <div className="flex flex-wrap items-center gap-2"><b>{c.name}</b><Badge tone={COVER[c.cover].tone}>{COVER[c.cover].label}</Badge></div>
            <p className="text-xs text-muted">Examples: {c.examples}</p>
            <p>{c.here} {c.href && <Link href={c.href} className="underline">Open</Link>}</p>
          </li>
        ))}
      </ul>
      <Section title="Spreadsheets with LibreOffice Calc">
        <ol className="list-decimal space-y-1 pl-5 text-sm">
          <li>Export the data: open <code className="break-all">http://localhost:8020/api/export/operations?format=xlsx</code> (or <code>csv</code>), or use the Data files panel on the dashboard.</li>
          <li>Open the file in LibreOffice Calc. For CSV, choose comma as the separator and set the date column to a date type.</li>
          <li>Slice it like OLAP: Insert &gt; Pivot Table, put region or product in rows, month in columns, revenue in values.</li>
          <li>Clean it: Data &gt; More Filters &gt; Standard Filter, Data &gt; Duplicates, and Find &amp; Replace for fixes.</li>
          <li>Save as .xlsx or .csv and load it back in My data. Check totals match the dashboard (revenue and margin to the cent).</li>
        </ol>
        <p className="mt-2 text-xs text-muted">Honest limit: LibreOffice runs on your computer next to the dashboard; the dashboard does not embed or control it. Margin should be SUM(profit)/SUM(revenue), not the average of a margin column.</p>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- BI project requirements
const REQ_STEPS = [
  "Identify stakeholders, internal and external: your direct contacts for requirements.",
  "Set objectives and KPIs, and sketch a roadmap (plan, platform, data collection, governance).",
  "Meet stakeholders: interviews, questionnaires, a mind map around the main goal, or a prototype to react to.",
  "Sort what you heard into functional (what it does) and non-functional (how well: scale, speed, security, backup, support).",
  "List assumptions, risks and deliverables; prioritize; decide how changes will be handled.",
  "Share the findings and timeline, then get written sign-off. That protects you from scope creep.",
];
export function RequirementsTab() {
  return (
    <div className="space-y-4">
      <Section title="The six steps before you build">
        <ol className="list-decimal space-y-1 pl-5 text-sm">{REQ_STEPS.map((s) => <li key={s}>{s}</li>)}</ol>
        <p className="mt-2 text-xs text-muted">Even for a personal dashboard, a one-page requirements note stops you building the wrong thing. For example, a retail company losing customers might set the goal &ldquo;raise loyalty&rdquo; with retention as the KPI.</p>
      </Section>
      <QualTab kinds={["requirements"]} />
    </div>
  );
}

// ---------------------------------------------------------------- privacy, security and compliance
const PRIV_STEPS: { step: string; what: string; here: string; gap?: string }[] = [
  { step: "1. Identify and classify data", what: "Know what is personal (PII: names, ID numbers) or sensitive (SPI: health data), and which rules attach to it.", here: "The governance catalog scans every table for likely personal data (it reports where, never the values) and suggests a classification such as confidential or internal." },
  { step: "2. Know where data comes from and goes", what: "Map the sources feeding your BI tools and where the results are used.", here: "Sources and Pipelines list inputs, and the lineage view in governance shows how tables feed each other." },
  { step: "3. Know who uses it", what: "Give each person only the access they need (need-to-know), such as read-only for most.", here: "There are no users to manage: it is single-person and no logins by design. Keep it that way by running it only on your own computer and not exposing the port to your network.", gap: "If someone else ever uses it, you would need sign-in and roles first." },
  { step: "4. Protect it", what: "Encryption, authentication, authorization, anonymization, plus firewalls and anti-virus.", here: "Columns with personal data can be protected from the AI features. Backups are available in Settings & backups. Use your computer's disk encryption (BitLocker on Windows) and your firewall for the rest.", gap: "The database file itself is not encrypted by the app, and there is no built-in anonymized export yet. Before sharing data, drop or replace name, email, phone and ID columns first." },
  { step: "5. Keep watching", what: "Review who touched data, audit regularly, and delete data you no longer need (retention and disposal).", here: "The Activity log records changes, governance has retention rules for tables with personal data, and the controls check shows what is still unprotected." },
];
const REGS = [
  { n: "GDPR", d: "EU rules on personal data of people in the EU: lawful reason, minimization, rights to access and erasure, breach reporting." },
  { n: "PCI DSS", d: "Card industry standard for storing or handling payment card data. Easiest to comply with by never storing card numbers." },
  { n: "HIPAA", d: "US rules for health information held by healthcare providers, insurers and their partners." },
  { n: "FERPA", d: "US rules for student education records." },
];
export function PrivacyTab() {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted"><b>Privacy</b> protects personal information from unauthorized access, use and disclosure. <b>Security</b> is broader: protecting all digital information from unauthorized access, tampering or theft across its life. Mishandling either can bring legal, financial and reputation costs.</p>
      <Section title="The steps, and where this dashboard stands">
        <Table head={["Step", "What it means", "In this dashboard"]} rows={PRIV_STEPS.map((s) => [<b key="s">{s.step}</b>, s.what, <span key="h">{s.here}{s.gap && <span className="mt-1 block rounded px-2 py-1" style={{ background: "var(--warn-bg)" }}><b>Gap:</b> {s.gap}</span>}</span>])} />
        <p className="mt-2 text-sm">See the controls in <Link href="/tracks" className="underline">Tracks</Link> (data governance and DBA), <Link href="/quality" className="underline">Data quality</Link>, and <Link href="/activity" className="underline">Activity log</Link>.</p>
      </Section>
      <Section title="Regulations, in one line each">
        <dl className="space-y-1 text-sm">{REGS.map((r) => <div key={r.n}><dt className="inline font-semibold">{r.n}: </dt><dd className="inline">{r.d}</dd></div>)}</dl>
        <p className="mt-2 text-xs text-muted">For personal use with your own business numbers these rarely bite. They start to matter the moment the data holds other people&apos;s details (customers, patients, students, card numbers). This is general education, not legal advice.</p>
      </Section>
      <Section title="A personal checklist">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Keep real customer details out of Practice; use made-up data there.</li>
          <li>Do not store card numbers or government ID numbers at all.</li>
          <li>Turn on disk encryption and keep the app on your own computer only.</li>
          <li>Back up, and test a restore now and then.</li>
          <li>Remove personal columns before you share any file or screenshot.</li>
          <li>Review the governance scan after every new import, and delete what you no longer need.</li>
        </ul>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- identifying data for analysis
const DATA_STEPS = [
  "Start from the problem: where you are, where you want to be, and the metric that will tell you.",
  "Decide what information you need and where it could come from. Let the goal decide: a campaign aimed at one age group needs profile, purchases, complaints and survey ratings, maybe social media reactions.",
  "Plan the collection: how long (one-off period or ongoing), how much is enough to be credible, and what depends on what.",
  "Choose collection methods that fit the type, timeframe and volume of the data, then start, and update the plan as conditions change.",
  "Set quality traits and checkpoints: free of errors, accurate, complete, relevant, accessible.",
  "Settle governance and privacy up front: confidentiality, licence to use, regulations, and an audit trail.",
];
export function DataPlanTab() {
  return (
    <div className="space-y-4">
      <Section title="Identifying the data you need">
        <ol className="list-decimal space-y-1 pl-5 text-sm">{DATA_STEPS.map((s) => <li key={s}>{s}</li>)}</ol>
        <p className="mt-2 text-xs text-muted">Right data first makes the findings credible. Once data is in, use My data to import it, <Link href="/quality" className="underline">Data quality</Link> and the Prescriptive &ldquo;Check my data is fit to act on&rdquo; to test the quality traits, and the Privacy and security tab for the rules.</p>
      </Section>
      <QualTab kinds={["dataplan"]} />
    </div>
  );
}

// ---------------------------------------------------------------- where data comes from
const KINDS_OF_DATA = [
  { n: "Primary", d: "Collected by you, straight from the source: your own records, CRM or workflow data, and surveys, interviews, discussions, observations and focus groups you run.", here: "Your own files in My data; interviews and observations in the Qualitative notes (Observations); survey comments in the Theme finder." },
  { n: "Secondary", d: "Already collected by someone else: external databases, research articles, publications, training material, internet searches, public financial records, and surveys others ran.", here: "Public files you download and import, and the practice datasets in the Dataset hub." },
  { n: "Third party", d: "Bought from aggregators who combine data from many sources purely to sell it, including data from data exchanges.", here: "Import the file you buy. Check its licence for what you may do with it.", },
];
const SOURCE_TYPES = [
  { n: "Databases", d: "Internal applications for processes, workflows and customers, or external databases you subscribe to or buy. Can hold primary, secondary or third-party data.", here: "SQL Lab and Sources read databases; DuckDB and SQLite files import directly." },
  { n: "Cloud", d: "Where more and more business data now lives, giving real-time and on-demand access.", here: "Skipped by your choice. Export from the cloud service as a file and import it." },
  { n: "The web", d: "Free or licensed public data: government records, papers, articles.", here: "Download and import, mindful of each site's terms." },
  { n: "Social media", d: "Opinions and reactions from Facebook, X, Google, YouTube, Instagram, used for qualitative and quantitative insight.", here: "No live feeds. Export or copy comments and run them through the Theme finder." },
  { n: "Sensor data", d: "Wearables, smart buildings and cities, phones, medical devices, appliances.", here: "Import the logs as CSV or JSON lines, then use Trends and Outliers." },
  { n: "Data exchange", d: "Voluntary sharing between providers and consumers: individuals, organizations, governments.", here: "Treat as third-party data: import the file and note the licence." },
  { n: "Surveys", d: "Questionnaires to a chosen group, on the web or paper, such as asking customers if they would pay for an updated product.", here: "Import the answers as a table; use Probability and the Theme finder for free-text answers." },
  { n: "Census", d: "Household-level wealth, income and population data.", here: "Secondary data: import it and join it to your own tables." },
  { n: "Interviews", d: "Qualitative opinions and experiences, by phone, web or face to face.", here: "Record them as Observations and look for repeating themes." },
  { n: "Observation studies", d: "Watching people in a setting or doing a task, like how easily shoppers find products.", here: "Observations notes and Post-mortems." },
];
export function SourcesGuideTab() {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Sources can be inside or outside your organization, and the data can be primary, secondary or third party. Mixing them (adding secondary and third-party data to your own) often shows a problem from a new angle. Whatever the source, it needs the quality, privacy and governance checks from the other tabs.</p>
      <Section title="Primary, secondary and third-party data">
        <ul className="space-y-2 text-sm">{KINDS_OF_DATA.map((k) => <li key={k.n}><b>{k.n}.</b> {k.d} <span className="text-muted">In this dashboard: {k.here}</span></li>)}</ul>
      </Section>
      <Section title="Where data comes from">
        <ul className="space-y-2 text-sm">{SOURCE_TYPES.map((k) => <li key={k.n}><b>{k.n}.</b> {k.d} <span className="text-muted">In this dashboard: {k.here}</span></li>)}</ul>
        <p className="mt-2 text-xs text-muted">Honest limit: the dashboard works from files and databases you load. It does not pull live social, sensor or cloud feeds, which keeps it simple and local. <Link href="/sources" className="underline">Sources</Link> and <Link href="/data" className="underline">My data</Link> are where you bring data in.</p>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- gathering and importing data
const GATHER: { n: string; d: string; here: string }[] = [
  { n: "SQL", d: "Extract from relational databases: say what to get, from which table, how to group, sort and limit it. Non-relational stores use SQL-like tools (CQL for Cassandra, GraphQL for Neo4j).", here: "SQL Lab runs SQL on your tables. No Cassandra or Neo4j tools are built in." },
  { n: "APIs", d: "An application calls an end-point (database, web service, data marketplace) to fetch data. Also used to validate data, such as postal addresses.", here: "Not built in as live calls. Download the result as a file and import it." },
  { n: "Web scraping", d: "Pulls chosen text, contacts, images or product items from web pages by set rules.", here: "Not built in. Check a site's terms first, and save the result as CSV to import." },
  { n: "RSS feeds", d: "Repeatedly refreshed updates from forums and news sites.", here: "Not built in. Copy items into a text file and use the Theme finder." },
  { n: "Data streams", d: "Constant flows from instruments, IoT devices, apps, car GPS and social feeds.", here: "Not live. Import saved logs (CSV, JSON lines) and use Trends and Outliers." },
  { n: "Data exchanges", d: "Platforms (AWS Data Exchange, Snowflake and others) that move data between providers and consumers with standards, licensing, de-identification and legal terms.", here: "Treat the delivered file as third-party data and keep its licence." },
  { n: "Research and advisory firms", d: "Trusted sources for market, ad-spend, user-behavior and demographic data (Gartner, Forrester).", here: "Import the files or tables you are licensed to use." },
];
const STORES: { type: string; kinds: string; store: string; here: string }[] = [
  { type: "Structured", kinds: "OLTP systems, spreadsheets, online forms, sensors, network and web logs", store: "Relational database (NoSQL can hold it too)", here: "CSV and Excel import into DuckDB tables." },
  { type: "Semi-structured", kinds: "Email, XML, JSON, zipped files, binary executables, TCP/IP protocol data", store: "NoSQL clusters. JSON is preferred for web services", here: "JSON, JSON lines and XML are flattened into columns on import." },
  { type: "Unstructured", kinds: "Web pages, social feeds, images, video, documents, media logs, surveys", store: "NoSQL or a data lake (holds every type and schema)", here: "Text and PDF go to the Theme finder; the lake/ folders act as a small data lake." },
];
export function GatherImportTab() {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Gathering pulls data from its sources. Importing loads it into a repository, combined into one view you can query, before it is wrangled, mined and analyzed. The right tool depends on the data type, the volume and the destination.</p>
      <Section title="Ways to gather data">
        <ul className="space-y-2 text-sm">{GATHER.map((g) => <li key={g.n}><b>{g.n}.</b> {g.d} <span className="text-muted">In this dashboard: {g.here}</span></li>)}</ul>
      </Section>
      <Section title="Where each kind of data is stored">
        <ul className="space-y-2 text-sm">{STORES.map((s) => <li key={s.type}><b>{s.type}</b> ({s.kinds}). Store in: {s.store}. <span className="text-muted">In this dashboard: {s.here}</span></li>)}</ul>
      </Section>
      <Section title="Importing">
        <p className="text-sm">ETL tools and pipelines automate importing (Talend and Informatica are the classic names; Python is the usual code route). Here, <Link href="/data" className="underline">My data</Link> checks a file completely and then loads it, <Link href="/pipeline" className="underline">Pipeline</Link> and <Link href="/pipelines" className="underline">Pipelines</Link> practise automated loads, and the <Link href="/python" className="underline">Python lab</Link> shows the code route.</p>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- data wrangling
const WRANGLE_PHASES = [
  { n: "1. Discovery", d: "Understand the data for your use case: how best to clean, structure, organize and map it.", here: "Summary and Filtering in the Analysis Lab, SQL Lab, and the preview when you import." },
  { n: "2. Transformation", d: "The bulk of the work: structuring, normalizing or denormalizing, cleaning and enriching (below).", here: "SQL Lab, Pipeline, the Python lab." },
  { n: "3. Validation", d: "Check quality after transforming, using repeatable rules for consistency, quality and security.", here: "Data quality page, import checks, and the Prescriptive input check." },
  { n: "4. Publishing", d: "Deliver the transformed, validated data with its metadata for downstream use, and document every step.", here: "Save the result as a table in My data, then record it in a Wrangling log below." },
];
const WRANGLE_TASKS: { n: string; d: string; sql?: string }[] = [
  { n: "Structuring: join", d: "Joins combine columns: each result row has columns from both tables.", sql: "SELECT o.*, c.segment FROM orders o JOIN customers c ON c.customer_id = o.customer_id" },
  { n: "Structuring: union", d: "Unions stack rows: each result row comes from one table or the other (columns must line up).", sql: "SELECT * FROM orders_2024 UNION ALL SELECT * FROM orders_2025" },
  { n: "Normalizing", d: "Reduce redundancy and inconsistency, as transactional systems do, by keeping each fact once.", sql: "SELECT DISTINCT customer_id, region FROM orders" },
  { n: "Denormalizing", d: "Merge tables into one wide table so reports query faster.", sql: "CREATE TABLE orders_wide AS SELECT o.*, c.segment FROM orders o JOIN customers c USING (customer_id)" },
  { n: "Cleaning", d: "Fix irregularities: missing, inaccurate, biased or outlier values. Either source the missing field or leave those records out, and write down which.", sql: "SELECT * FROM orders WHERE customer_id IS NOT NULL AND amount >= 0" },
  { n: "Enriching", d: "Add data that makes analysis more meaningful: public datasets, other systems, or metadata such as a sentiment score or a weather or location tag.", sql: "SELECT o.*, w.avg_temp FROM orders o LEFT JOIN weather w ON w.day = o.order_date" },
];
const WRANGLE_TOOLS: { n: string; d: string; status: string; tone: "ok" | "warn" | "muted" | "bad" }[] = [
  { n: "Spreadsheets (Excel Power Query, Google Sheets, LibreOffice Calc)", d: "Built-in formulas and filters to spot problems, clean and transform; add-ins like Power Query import from many sources.", status: "Use LibreOffice Calc (free); see BI tool categories", tone: "muted" },
  { n: "OpenRefine", d: "Free, open source, menu-driven (no syntax to learn). Reads and writes TSV, CSV, XLS, XML and JSON; cleans, converts and extends data with web services.", status: "Optional free download you run yourself; import its CSV output", tone: "muted" },
  { n: "Google DataPrep, Watson Studio Refinery, Trifacta Wrangler", d: "Cloud services that explore, clean and prepare data visually with suggestions, schema detection and, in Refinery's case, governance rules.", status: "Skipped: cloud add-ons", tone: "bad" },
  { n: "Python: Jupyter, NumPy, pandas", d: "Jupyter for cleaning, modeling and charts; NumPy for fast arrays and maths; pandas for merging, joining and transforming data in one-line commands that avoid misaligned data.", status: "Python lab", tone: "ok" },
  { n: "R: dplyr, data.table, jsonlite", d: "Packages built for messy data: dplyr for clear wrangling syntax, data.table for fast aggregation, jsonlite for JSON from web APIs.", status: "Skipped: R by your choice", tone: "bad" },
];
export function WrangleTab() {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Data wrangling (also called munging) is the iterative work of turning raw data, already collected in a repository, into data that is ready for credible analysis. Every round can send you back to an earlier phase.</p>
      <Section title="The four phases">
        <ul className="space-y-2 text-sm">{WRANGLE_PHASES.map((p) => <li key={p.n}><b>{p.n}.</b> {p.d} <span className="text-muted">In this dashboard: {p.here}</span></li>)}</ul>
      </Section>
      <Section title="Transformation tasks, with a SQL starter for each" note="Examples use made-up table names. Swap in yours, and try them in SQL Lab.">
        <ul className="space-y-3 text-sm">{WRANGLE_TASKS.map((t) => <li key={t.n}><b>{t.n}.</b> {t.d}{t.sql && <pre className="mt-1 overflow-x-auto whitespace-pre-wrap break-words rounded border border-line bg-panel2 p-2 text-xs">{t.sql}</pre>}</li>)}</ul>
        <p className="mt-2 text-sm"><Link href="/lab" className="underline">Open SQL Lab</Link></p>
      </Section>
      <Section title="Tools for wrangling" note="Pick by data size, data structures, cleaning power, infrastructure needs, ease of use and learnability.">
        <ul className="space-y-2 text-sm">{WRANGLE_TOOLS.map((t) => <li key={t.n}><b>{t.n}.</b> {t.d} <Badge tone={t.tone}>{t.status}</Badge></li>)}</ul>
        <p className="mt-2 text-sm">Open the <Link href="/python" className="underline">Python lab</Link> or <Link href="/lab" className="underline">SQL Lab</Link> to wrangle here.</p>
      </Section>
      <QualTab kinds={["wrangle"]} />
    </div>
  );
}

// ---------------------------------------------------------------- storytelling
const STORY_RULES = [
  { n: "Start with the audience and the decision", d: "Who will read this and what must they decide? A story for you, a lender or a client each stresses different numbers." },
  { n: "Lead with the takeaway", d: "State the one-sentence finding first, then show why. Do not make people wait for the point." },
  { n: "Shape it: beginning, middle, end", d: "Where things stood, what changed or went wrong (the tension the data reveals), and what to do about it." },
  { n: "One chart, one point", d: "Pick the chart that makes that point easy: a line for change over time, bars for comparing groups, a scatter for two numbers. Cut anything that doesn't serve the point, and label what to notice." },
  { n: "Show the evidence and where it came from", d: "Every number should trace back to an analysis. Use the Decision brief and Track the result in the Analysis Lab as your source." },
  { n: "Be honest about limits", d: "Say what the data can't tell you: association is not cause, small samples, missing data. A story that hides doubt loses trust when it breaks." },
  { n: "End with a specific ask", d: "Who does what by when. A finding with no next step is just a fact." },
];
export function StoryTab() {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Data storytelling is turning analysis into a message that changes a decision: the right data, a clear visual, and a narrative. Analysis finds the answer; the story gets it understood and acted on.</p>
      <Section title="Seven rules">
        <ol className="list-decimal space-y-2 pl-5 text-sm">{STORY_RULES.map((r) => <li key={r.n}><b>{r.n}.</b> {r.d}</li>)}</ol>
        <p className="mt-2 text-sm">Get the numbers from the <Link href="/analysis" className="underline">Analysis Lab</Link> (Prescriptive &gt; Decision brief writes the four steps for you) and the charts from the <Link href="/bi" className="underline">Dashboard</Link>.</p>
      </Section>
      <QualTab kinds={["story"]} />
    </div>
  );
}

// ---------------------------------------------------------------- data visualization
const CHART_CHOICES: { q: string; chart: string; why: string; here: string }[] = [
  { q: "How do parts make up a whole?", chart: "Pie or donut (a stacked bar if more than about five parts)", why: "Shows each share of 100%, such as each product line's part of revenue.", here: "Pie and Donut in the My data chart builder." },
  { q: "How do several values compare?", chart: "Bar or column", why: "Side-by-side lengths are the easiest thing for the eye to compare. Columns suit showing negative and positive values and change over time; bars suit long labels.", here: "Bar in the chart builder." },
  { q: "How does one value change over time?", chart: "Line (area if the total matters)", why: "Time is continuous, and a line shows trend, pattern and variation. Several lines compare related series.", here: "Line and Area in the chart builder; Analysis Lab > Trends and patterns adds trend and seasonality." },
  { q: "Are two variables related?", chart: "Scatter plot", why: "Each dot is a row, so you see direction, strength and odd points. Weather against ski bookings is the classic example.", here: "Scatter in the chart builder; Analysis Lab > Correlation." },
  { q: "How are the values spread?", chart: "Histogram or box plot", why: "Shows the shape, the middle and the extremes in one picture.", here: "Histogram and Box plot in the chart builder; Analysis Lab > Distribution." },
  { q: "Is anything unusual?", chart: "Line or scatter with the odd points marked", why: "Anomalies can skew findings, so make them visible and annotate the likely cause.", here: "Analysis Lab > Trends and patterns marks unusual points; Outliers ranks them." },
  { q: "Where are things (place)?", chart: "Map", why: "Good for density or regional differences.", here: "Not built. Use a spreadsheet or Tableau Public with your exported data." },
];
const VIZ_TECHNIQUES: { group: string; items: string[] }[] = [
  { group: "Give context", items: ["Add a benchmark or a trend line so people see performance relative to something.", "Show the share of the whole, not only the raw number: a segment can look weak in dollars yet be growing as a share of the business.", "Mark anomalies and annotate the likely cause.", "Make data relatable (a smile or a frown for satisfaction) when it helps."] },
  { group: "Present it well", items: ["Match the chart to the question (table above).", "Offer a table of the numbers too, maybe in an appendix, depending on the audience."] },
  { group: "Be clear", items: ["One central point per chart.", "Label axes and slices, annotate the standout bar, include a legend, and use tooltips for exact values.", "Plain words, no jargon."] },
  { group: "Be consistent and appealing", items: ["Same colour for the same measure in every chart (revenue is always the same colour).", "Same fonts and layout throughout; a small picture can speed up reading."] },
  { group: "Engage", items: ["Filters, slicers and drill-down let people explore, and seeing the real data builds trust.", "Check it works on a phone: fewer points, simple charts."] },
];
const VIZ_TOOLS: { n: string; d: string; status: string; tone: "ok" | "muted" | "bad" }[] = [
  { n: "Spreadsheets (Excel, Google Sheets, LibreOffice Calc)", d: "Everyday charts (bar, line, pie, scatter, trend lines, combination charts) that update when the data changes. Sheets is best for several editors.", status: "LibreOffice Calc: export and chart there", tone: "muted" },
  { n: "Jupyter with Matplotlib, Bokeh, Dash", d: "Matplotlib for 2D and 3D plots, Bokeh for interactive charts over large or streaming data, Dash for interactive web apps in Python.", status: "Python lab covers plotting; Bokeh and Dash are optional installs", tone: "ok" },
  { n: "RStudio and Shiny", d: "R charts from histograms to heat maps and correlograms; Shiny turns them into interactive web apps and dashboards.", status: "Skipped: R by your choice", tone: "bad" },
  { n: "IBM Cognos Analytics", d: "End-to-end analytics with forecasting, recommended visuals, conditional formatting and geospatial overlays.", status: "Skipped: licensed software", tone: "bad" },
  { n: "Tableau", d: "Drag-and-drop interactive dashboards and worksheets, plus stories; reads Excel, text files and databases.", status: "Guide: docs/TABLEAU.md rebuilds this dashboard in Tableau Public", tone: "muted" },
  { n: "Microsoft Power BI", d: "Report and dashboard service with pinned tiles that respond to each other, shareable on mobile.", status: "Guide: docs/BI_TOOLS.md (Windows desktop is free)", tone: "muted" },
];
export function VizTab() {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Data visualization communicates information with charts, graphs and maps so it is easy to understand and remember, and shows relationships, trends and patterns that thousands of rows hide. A chart that only presents data differs from one that tells the story: showing a segment&apos;s share of total revenue can reveal growth that a plain revenue bar chart hides. Start with the question, then the audience&apos;s key takeaway.</p>
      <Section title="Which chart answers your question?">
        <ul className="space-y-2 text-sm">{CHART_CHOICES.map((c) => <li key={c.q}><b>{c.q}</b> {c.chart}. {c.why} <span className="text-muted">In this dashboard: {c.here}</span></li>)}</ul>
        <p className="mt-2 text-sm">Try them in <Link href="/data" className="underline">My data</Link> (open a table, then the chart builder) or on the <Link href="/bi" className="underline">Dashboard</Link>. Also decide: static, or interactive so viewers can change values and see the effect.</p>
      </Section>
      <Section title="Techniques that make a chart work">
        {VIZ_TECHNIQUES.map((g) => <div key={g.group} className="mb-2"><b className="text-sm">{g.group}</b><ul className="list-disc pl-5 text-sm">{g.items.map((i) => <li key={i}>{i}</li>)}</ul></div>)}
        <p className="mt-1 text-xs text-muted">Honest gaps: the chart builder has no annotations, benchmark lines, picture icons, conditional formatting or maps. Add those in a spreadsheet or Tableau when a presentation needs them.</p>
      </Section>
      <Section title="Dashboards">
        <p className="text-sm">A dashboard puts reports and charts from several sources on one screen to watch daily progress or the health of a process. It can show operational data (live campaign numbers) and analytical data (this campaign against past ones), gives a bird&apos;s-eye view with drill-down, is easy for non-experts, and helps teams collaborate. This dashboard&apos;s <Link href="/bi" className="underline">Dashboard</Link>, <Link href="/company" className="underline">Company</Link> and <Link href="/kpis" className="underline">KPIs</Link> pages do this for you; it updates when you load data or a scheduled job runs, not in real time.</p>
      </Section>
      <Section title="Visualization tools">
        <ul className="space-y-2 text-sm">{VIZ_TOOLS.map((t) => <li key={t.n}><b>{t.n}.</b> {t.d} <Badge tone={t.tone}>{t.status}</Badge></li>)}</ul>
        <p className="mt-2 text-xs text-muted">Choose by ease of use and the purpose of the visual. If you can visualize it, a tool can draw it.</p>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- communicating findings
const REPORT_PARTS = [
  { n: "Cover page", d: "Title, your name, the date." },
  { n: "Executive summary", d: "About three paragraphs that stand alone, with nothing that isn't in the report." },
  { n: "Table of contents", d: "Sections and subsections, so readers can jump to what matters to them." },
  { n: "Introduction", d: "The nature of the analysis, the problem, and the questions it answers." },
  { n: "Methodology", d: "Data sources and the plan for the data, including any new collection, variables and methods." },
  { n: "Results", d: "Charts and graphs that back up the findings and highlight the crucial ones." },
  { n: "Discussion", d: "Your main arguments, built on the results, using narrative to give numbers meaning." },
  { n: "Conclusion", d: "Restate the problem, summarize the findings and the outcome, and name next steps." },
  { n: "Appendix", d: "Important material that didn't fit the body, such as references and original data." },
];
export function ReportTab() {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Weeks of analysis can be lost if the findings are not organized for the audience. Decide first whether you need a brief report (five pages or fewer, to the point) or a detailed one (builds the argument step by step, with method and intermediate findings), or slides. Then write the outline before the prose.</p>
      <Section title="The nine parts">
        <ol className="list-decimal space-y-1 pl-5 text-sm">{REPORT_PARTS.map((p) => <li key={p.n}><b>{p.n}.</b> {p.d}</li>)}</ol>
      </Section>
      <Section title="Four habits that keep the message clear">
        <ul className="list-disc space-y-1 pl-5 text-sm">
          <li>Make charts big and clearly labelled. Check them from the distance your audience will sit.</li>
          <li>Use data only as evidence: write the key messages first, then insert the numbers that support them.</li>
          <li>One point per chart.</li>
          <li>Cut data that doesn&apos;t support the key message, even if it was hard to collect.</li>
        </ul>
        <p className="mt-2 text-sm">For the story shape see Data storytelling, and for chart choice see Data visualization. This dashboard stores the outline; paste the text into a document or slides to publish. It does not lay out pages or export a report file.</p>
      </Section>
      <QualTab kinds={["report"]} />
    </div>
  );
}

// ---------------------------------------------------------------- data science methodology
const DS_STAGES = [
  { n: "Business understanding", q: "What is the problem you are trying to solve?", here: "Write the goal and objectives below. Ask until the question is clear: effort spent on what people THINK the question is will not solve the real one." },
  { n: "Analytic approach", q: "How can you use data to answer the question?", here: "Match the question to an approach (guide below), then use that approach's tabs in the Analysis Lab." },
  { n: "Data requirements", q: "What data do you need?", here: "Identify the data tab and the Data plan note. Set the cohort rules (who is in, who is out) and plan one row per entity: One row per entity tool." },
  { n: "Data collection", q: "Where does it come from, and how will you receive it?", here: "Where data comes from, Gather and import, and My data. Merge sources with a JOIN in SQL Lab. After the first look revise the requirements: it is fine to defer data you can't get yet and fetch it only if early results show it matters." },
  { n: "Data understanding", q: "Does the data represent the problem?", here: "Summary (mean, median, min, max, spread), Distribution (histograms), Correlation (very high pairs are redundant) and the Data quality page. Ask what missing means (no, zero, or unknown?) and whether placeholder codes like 999 hide in the data. If the definition misses cases you expected, loop back to collection." },
  { n: "Data preparation", q: "What work is needed to make it usable?", here: "Data cleaning (fix, then Add a column for feature engineering and for outcomes such as returns within 30 days), One row per entity, and the Wrangling log. Write the definitions precisely: what counts as the event, the time window, and which codes or categories qualify." },
  { n: "Modeling", q: "Which models show patterns, groups and outliers?", here: "Regression, Decision tree, Clusters, Sequences, Associations, ARIMA, and the ML Lab (including nearest neighbor)." },
  { n: "Evaluation", q: "Does the model answer the original question, or must the data change?", here: "Holdout scores against a baseline in the ML Lab; Before you act." },
  { n: "Deployment", q: "Can you put the model into practice?", here: "Write the deployment plan below: owner, stakeholders, delivery, a pilot first, training, monitoring. Use dashboards, the Findings report and scheduled refreshes; the ML Lab registry scores new rows and checks drift." },
  { n: "Feedback", q: "What do stakeholders and new data say?", here: "Write a Feedback review note. Measure impact by comparing before and after the launch date (Data cleaning, Add a column, then Compare groups) when a control group isn't possible. Refine, redeploy, loop back to stage 1." },
];
export function MethodologyTab() {
  return (
    <div className="space-y-4">
      <Section title="The data science methodology: 10 stages for any business question">
        <p className="mb-2 text-sm">A methodology keeps you from jumping to solutions. It follows the sequence popularised by John Rollins (IBM): define the issue, choose an approach, organise the data, then validate and keep improving. It works for churn, pricing, inventory, marketing, staffing or any other question, not only the hospital readmission example in the course.</p>
        <Table head={["#", "Stage", "The question it answers", "Where in this app"]} rows={DS_STAGES.map((s, i) => [String(i + 1), s.n, s.q, s.here])} />
        <p className="mt-2 text-xs text-muted">Stage 1 in practice: find the goal behind the question, break it into objectives, name a sponsor who keeps involved, then write the requirements the model must meet (for example: predict the outcome, predict the risk, explain the combination of events behind it, and be easy to apply to new cases).</p>
      </Section>
      <Section title="Stage 2: pick the analytic approach from the question">
        <Table head={["Question type", "Approach and techniques", "Where here"]} rows={[
          ["Descriptive: what is the current status? (how are sales doing?)", "Descriptive analytics: aggregation, mining, visualization, dashboards, reports", "Summary, Trend, Business view, Data visualization, Findings report"],
          ["Diagnostic: why did it happen? (why did sales fall last quarter?)", "Diagnostic analytics: drill-down, data discovery, correlation, root causes", "Why did it change, Compare groups, Correlation, Outliers"],
          ["Predictive: what is likely to happen? (next year's forecast, churn, demand)", "Predictive analytics: regression, time series forecasting, machine learning", "Forecast (trend or ARIMA), Regression, ML Lab"],
          ["Prescriptive: what should we do? (how do we raise traffic?)", "Prescriptive analytics: optimization, simulation, decision analysis", "Goal planner, Budget allocation, Scenario notes, Before you act"],
          ["Classification: which category, or yes/no? (spam, churn, diagnosis)", "Supervised learning: logistic regression, decision trees (answer plus likelihood from each leaf), neural networks, nearest neighbor", "Decision tree, ML Lab"],
          ["Groups or behavior: what patterns or segments exist?", "Clustering and association", "Clusters, Associations, Sequences"],
        ]} />
        <p className="mt-2 text-xs text-muted">Confirm the choice with the person asking, in terms of their business requirements, before you collect data.</p>
      </Section>
      <QualTab kinds={["dsproject", "deployment", "feedback"]} />
    </div>
  );
}
