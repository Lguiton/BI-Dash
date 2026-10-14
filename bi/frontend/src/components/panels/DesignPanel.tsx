"use client";
import { RelationalTab } from "./RelationalTab";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { deleteJson, getJson, patchJson, postJson, putJson } from "@/lib/api";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Badge, Field, Section, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";
import { QualTab } from "./AnalysisQual";
import { FormatsTab, GatherImportTab, SourcesGuideTab, WrangleTab } from "./FoundationsPanel";

interface Star { source: string; rows: number; grain: string; fact: string; dimensions: { name: string; key: string; attributes: string[]; rows: number; note?: string }[]; measures: { column: string; additive: boolean; note: string }[]; other: { column: string; note: string }[]; warnings: string[]; sketch: string[]; lesson: string }
interface Store { recommendation: string; reasons: string[]; practise_here: string; lesson: string }

function StarTab() {
  const [sources, setSources] = useState<{ id: string; label: string }[]>([]);
  const [src, setSrc] = useState("");
  const [d, setD] = useState<Star | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { getJson<{ sources: { id: string; label: string }[] }>("/api/stats/sources").then((m) => { setSources(m.sources); setSrc((s) => s || m.sources[0]?.id || ""); }).catch((e) => setErr(errMsg(e, "Couldn't load your data."))); }, []);
  const run = async () => {
    setBusy(true); setErr(null);
    try { setD(await getJson<Star>(`/api/pipeline/star?source=${encodeURIComponent(src)}`)); } catch (e) { setD(null); setErr(errMsg(e, "That didn't work.")); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <Section title="Suggest a star schema" note="A starting point from the shape of your data. You know what the columns mean, so correct it, then save it as a Warehouse design note.">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Table to model"><select className="field" value={src} onChange={(e) => setSrc(e.target.value)} aria-label="Table to model">{sources.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}</select></Field>
          <button className="btn btn-primary" disabled={busy || !src} onClick={run}>{busy ? "Working…" : "Suggest a design"}</button>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {d && (
        <>
          <Lesson text={d.lesson} /><Warn items={d.warnings} />
          <Section title="Grain"><p className="text-sm">One fact row means: <b>{d.grain}</b> ({d.rows.toLocaleString()} rows in the source). Fact table: <code>{d.fact}</code></p></Section>
          <Section title="Measures (in the fact table)">
            <Table head={["Column", "Adds up?", "Note"]} rows={d.measures.map((m) => [m.column, <Badge key="b" tone={m.additive ? "ok" : "warn"}>{m.additive ? "additive" : "not additive"}</Badge>, m.note])} />
            {d.other.length > 0 && <p className="mt-2 text-xs text-muted">{d.other.map((o) => `${o.column}: ${o.note}`).join(" ")}</p>}
          </Section>
          <Section title="Dimensions (ways to slice it)">
            <Table head={["Dimension", "Built from", "Attributes", "Values"]} rows={d.dimensions.map((x) => [x.name, x.key, x.attributes.join(", ") || "—", x.rows.toLocaleString()])} />
          </Section>
          <Section title="Sketch of the tables"><pre className="overflow-x-auto whitespace-pre-wrap break-words rounded bg-panel2 p-3 text-xs">{d.sketch.join("\n")}</pre></Section>
        </>
      )}
    </div>
  );
}

function StoreTab() {
  const [a, setA] = useState({ workload: "reporting", data: "structured", volume: "small", users: "few", realtime: false });
  const [d, setD] = useState<Store | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const opt = (k: "workload" | "data" | "volume" | "users", label: string, vals: [string, string][]) => (
    <Field label={label}><select className="field" value={a[k]} onChange={(e) => setA({ ...a, [k]: e.target.value })} aria-label={label}>{vals.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
  );
  return (
    <div className="space-y-4">
      <Section title="Choose a kind of data store" note="Database for running the business, warehouse for reporting on it, lake for keeping everything raw.">
        <div className="grid gap-3 sm:grid-cols-2">
          {opt("workload", "Main work", [["transactions", "Many small reads and writes (orders, payments)"], ["reporting", "Reports and analysis"], ["mixed", "Both"]])}
          {opt("data", "Kind of data", [["structured", "Tables with clear columns"], ["mixed", "Tables plus files, logs or events"], ["raw", "Mostly raw and varied (files, images, streams)"]])}
          {opt("volume", "Volume", [["small", "Fits on one computer"], ["medium", "Large but manageable"], ["huge", "Too big for one machine"]])}
          {opt("users", "People and apps using it", [["few", "A few"], ["many", "Many at once"]])}
        </div>
        <label className="mt-3 flex items-center gap-2 text-sm"><input type="checkbox" checked={a.realtime} onChange={(e) => setA({ ...a, realtime: e.target.checked })} /> Needs real-time (streaming) data</label>
        <button className="btn btn-primary mt-3" onClick={async () => { setErr(null); try { setD(await postJson<Store>("/api/pipeline/store", a)); } catch (e) { setD(null); setErr(errMsg(e, "That didn't work.")); } }}>Recommend</button>
      </Section>
      {err && <ErrorBanner message={err} />}
      {d && (
        <Section title={`Suggested: ${d.recommendation}`}>
          <ul className="list-disc space-y-1 pl-5 text-sm">{d.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>
          <p className="mt-2 text-sm">Practise it here with: {d.practise_here}.</p>
          <Lesson text={d.lesson} />
        </Section>
      )}
    </div>
  );
}

interface Meta { technical: { table: string; kind: string; rows: number; column_count: number; columns: { name: string; type: string }[] }[]; business: { table: string; owner: string; steward: string; description: string; classification: string }[]; process: { database_bytes?: number; backups?: number; backup_age_hours?: number | null; pipeline_runs: Record<string, unknown>[] }; coverage: { tables: number; described_pct: number; owned_pct: number }; gaps: string[]; lesson: string }

function MetadataTab() {
  const [term, setTerm] = useState("");
  const [d, setD] = useState<Meta | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = (t: string) => getJson<Meta>(`/api/pipeline/metadata?search=${encodeURIComponent(t)}`).then((m) => { setD(m); setErr(null); }).catch((e) => setErr(errMsg(e, "Couldn't load the metadata.")));
  useEffect(() => { load(""); }, []);
  return (
    <div className="space-y-4">
      <Section title="Metadata: data about your data" note="Edit owners and descriptions in Data governance, Catalog. Search finds a column by name across every table.">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Find a column or table"><input className="field" value={term} onChange={(e) => setTerm(e.target.value)} placeholder="for example customer" aria-label="Find a column or table" /></Field>
          <button className="btn btn-primary" onClick={() => load(term)}>Search</button>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {d && (
        <>
          <Lesson text={d.lesson} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Section title="Tables">{d.coverage.tables}</Section>
            <Section title="Described">{d.coverage.described_pct}%</Section>
            <Section title="Owned">{d.coverage.owned_pct}%</Section>
          </div>
          <Warn items={d.gaps} />
          <Section title="Technical metadata (structures)">
            <Table head={["Table", "Rows", "Columns"]} rows={d.technical.map((t) => [t.table, t.rows.toLocaleString(), `${t.column_count}: ${t.columns.slice(0, 12).map((c) => `${c.name} (${c.type})`).join(", ")}${t.columns.length > 12 ? "…" : ""}`])} />
          </Section>
          <Section title="Process metadata (what has run)">
            <p className="text-sm">Database size {d.process.database_bytes != null ? `${(d.process.database_bytes / 1048576).toFixed(1)} MB` : "unknown"}; backups {d.process.backups ?? "unknown"}{d.process.backup_age_hours != null ? `, latest ${d.process.backup_age_hours} hours old` : ""}.</p>
            {d.process.pipeline_runs.length > 0 ? <pre className="mt-2 overflow-x-auto whitespace-pre-wrap break-words rounded bg-panel2 p-3 text-xs">{d.process.pipeline_runs.map((r) => JSON.stringify(r)).join("\n")}</pre> : <p className="mt-2 text-xs text-muted">No pipeline runs yet. Run the pipeline to record some.</p>}
          </Section>
          <Section title="Business metadata (meaning and ownership)">
            <Table head={["Table", "Owner", "Class", "Description"]} rows={d.business.map((b) => [b.table, b.owner || "—", b.classification || "—", b.description || "—"])} />
          </Section>
        </>
      )}
    </div>
  );
}

const LANGS = [
  ["SQL", "Query language", "Insert, update and delete records, create tables and views, write stored procedures. Portable, close to English, fast on large data.", "SQL Lab and the Postgres practice folder."],
  ["Python", "Programming", "Easy to learn, open source, huge libraries: Pandas (cleaning), NumPy and SciPy (statistics), Beautiful Soup and Scrapy (scraping), Matplotlib and Seaborn (charts), OpenCV (images).", "Python lab and the python_practice folder."],
  ["R", "Programming", "Open source and strong for statistics and visualization (ggplot2, Plotly), reports with embedded data and scripts, interactive web apps.", "Not run here. Practise it outside this app."],
  ["Java", "Programming", "Object-oriented, platform independent, fast. Hadoop, Hive and Spark are written in Java.", "Not run here. Practise it outside this app."],
  ["Unix/Linux shell", "Shell scripting", "Plain-text series of commands for repetitive work: file handling, backups, log checks, installs, batch runs.", "The IT specialist lab and your WSL terminal; the dashboard's own backup schedule covers routine backups."],
  ["PowerShell", "Shell scripting", "Cross-platform, object-based: filter, sort, group and measure objects in a pipeline; works well with JSON, CSV, XML and REST APIs.", "The Windows scripts in this app are untested; try them in your own PowerShell."],
];

const REPOS = [
  ["Database and DBMS", "A collection of data built for input, storage, search, retrieval and change, and the programs (DBMS) that create and query it. Example: find customers inactive for six months.", "DuckDB is the app's DBMS; SQL Lab queries it."],
  ["Relational (RDBMS)", "Tables of rows (records) and columns (attributes) linked by common fields such as Customer ID; queried with SQL. Mature, flexible, little redundancy, easy backup, ACID.", "Database admin, SQL Lab, the Postgres practice folder."],
  ["Non-relational (NoSQL)", "Schema-less or free-form, built for speed, flexibility and scale: documents, key-value, wide-column, graph.", "Not run here (no MongoDB, Redis, Cassandra or Neo4j). JSON import shows the document idea."],
  ["Data warehouse", "Central repository that merges sources through ETL for analytics and BI.", "Gold layer, star-schema suggester."],
  ["Data mart", "A subset of the warehouse for one team or subject.", "A gold table or view for one purpose."],
  ["Data lake", "Holds raw data of any type and schema until it is needed.", "Bronze layer and the lake folders; Big data lab."],
  ["Big data store", "Distributed storage and computing for very large datasets.", "Not run here (no Hadoop or Spark cluster). The Apache lab teaches the ideas."],
];
const RDBMS = [
  ["Linked tables", "A customer table and a transactions table are joined on Customer ID to build a statement in one query."],
  ["Data integrity", "Restrict fields to data types and values; keep one copy of each customer and link to it."],
  ["ACID", "Atomicity (all or nothing), Consistency, Isolation, Durability: data stays correct despite failures."],
  ["Good for", "OLTP (many users making small inserts, updates and deletes), warehouses tuned for OLAP, lightweight IoT collection."],
  ["Limits", "Poor fit for semi-structured and unstructured data; fixed field lengths; migrating between systems needs matching schemas and types."],
  ["Cloud RDBMS", "Database-as-a-Service (Amazon RDS, Google Cloud SQL, Azure SQL) adds elastic compute and continuous mirroring. Not available here."],
];

const NOSQL = [
  ["Key-value", "Key-value pairs; the key is a unique id, the value can be anything up to a JSON document.", "Session data, user preferences, real-time recommendations, in-memory caching.", "Not for querying by value, relationships or several unique keys.", "Redis, Memcached, DynamoDB"],
  ["Document", "Each record and its data in one document, with flexible indexing and ad hoc queries.", "E-commerce, medical records, CRM, analytics platforms.", "Not for complex search queries or multi-operation transactions.", "MongoDB, DocumentDB, CouchDB, Cloudant"],
  ["Column family", "Cells stored by column; columns used together form a column family, so reads are fast.", "Heavy writes, time-series, weather and IoT data.", "Not for complex queries or often-changing query patterns.", "Cassandra, HBase"],
  ["Graph", "Nodes hold data, arrows are relationships.", "Social networks, recommendations, network diagrams, fraud detection, access management.", "Not for high-volume transactions or large analytics scans.", "Neo4j, CosmosDB"],
];

const WHM = [
  ["Data warehouse", "Single source of truth: current and historical data, cleansed, conformed and categorized, modeled for a purpose, so it is analysis-ready. Three tiers: database servers at the bottom, an OLAP server in the middle, query and reporting tools on top.", "Choose it when you have large operational data that must be ready for reporting. Cloud warehouses add pay-as-you-go scale and faster recovery."],
  ["Dependent data mart", "A subset of the enterprise warehouse for one function (sales, finance). Data is already cleaned, with isolated security and performance.", "Pulls from the warehouse."],
  ["Independent data mart", "Built straight from operational or external sources, so it must do its own transformation.", "Quicker to start, but risks numbers that disagree with the warehouse."],
  ["Hybrid data mart", "Combines the warehouse, operational systems and external data.", "Needs the most care over definitions."],
  ["Data lake", "Raw data of any type in its native format; no schema is needed up front and you need not know every use case. Still classified, protected and governed: not a dumping ground.", "A reference architecture, not one product: object storage, Hadoop, a relational or NoSQL system."],
];

const ETL = [
  ["ETL", "Extract, transform, then load. Gathers raw data, keeps what reporting needs, cleans and standardizes it, loads it into a repository. Historically batch and large scale; streaming ETL now exists.", "Silver is the transform step; the pipeline loads gold."],
  ["ELT", "Extract, load raw into the target (often a lake, sometimes a warehouse), then transform there only what an analysis needs. Faster from extraction to delivery, flexible for exploration, suits big and unstructured data.", "Bronze keeps data raw, then silver and gold transform it in the same database."],
  ["Extract: batch or stream", "Batch moves large chunks at scheduled times; streaming pulls events in real time and can transform in transit.", "Batch only. Streaming (Kafka, Storm, Samza) is not run here."],
  ["Transform", "Make dates and units consistent, remove duplicates, filter, enrich (split a full name), set key relationships, apply business rules and validations.", "Data cleaning, Add a column and the pipeline's silver rules."],
  ["Load: initial, incremental or full refresh", "Initial fills the repository; incremental applies periodic changes; full refresh erases and reloads.", "The pipeline loads incrementally using a watermark (only new days are re-read); Reset does a full refresh. Re-run twice to prove it is idempotent."],
  ["Load verification", "Check for missing or null values, server performance and load failures, and have a recovery plan.", "Quarantine, health checks and expectations."],
  ["Data pipeline", "The whole journey of data from source to destination, for batch, streaming or both; ETL and ELT are parts of it. Destination is usually a lake, or another application or visualization tool.", "Pipeline monitor. Airflow, Beam and Dataflow are not run here; the Apache lab teaches DAGs."],
  ["Data integration", "Ingest, transform, combine and provision data into one unified view; also covers consistency across applications, master data, data sharing, migration and consolidation. A pipeline performs integration; ETL is a process within it.", "My data and Sources import and combine files; Data governance covers quality."],
  ["Choosing an integration platform", "Look for pre-built connectors (databases, files, APIs, CRM, ERP), open-source flexibility to avoid lock-in, batch and stream support, big data support, quality, governance and security features, and portability across cloud, multi-cloud and hybrid.", "Commercial and cloud platforms (DataStage, Talend, Informatica, iPaaS) are not available here."],
];

const LAYERS = [
  ["1. Data ingestion (collection)", "Connect to sources, move data in as batch, stream or both, and record what came in (volume, source, time) in the metadata repository.", "Import, Sources and the pipeline's bronze layer. Kafka, Kinesis, Dataflow are not run here."],
  ["2. Storage and integration", "Store data for processing and the long term (reliable, scalable, fast, cost-efficient), and transform and merge it logically or physically.", "DuckDB tables, the lake folders and the gold layer."],
  ["3. Processing", "Validate, transform and apply business logic in batch or streaming; support query tools and languages, scale up, and let analysts and scientists work with the data. Structuring, normalization, denormalization and cleaning happen here. Storage and processing can be the same layer (a relational database) or processing can come before storage.", "Data wrangling and Data cleaning, SQL Lab, the pipeline's silver layer."],
  ["4. Analysis and user interface", "Delivers data to BI analysts and stakeholders (dashboards, reports), to analysts and data scientists, and to other applications through APIs.", "The dashboards, Analysis Lab, and the app's own API."],
  ["Overlay: data pipeline", "Extract, transform and load tools that keep data flowing across layers 1 to 3.", "Pipeline monitor."],
];
const STORE_FACTORS = [
  ["Type of data", "Structured data with a fixed schema suits a relational database; semi-structured and unstructured suit NoSQL (key-value, document, column, graph) or a lake."],
  ["Volume", "Raw data in native form at scale: a lake. High volume, velocity and variety needing parallel work across machines: a big data store."],
  ["Intended use", "Transactional systems need fast reads, writes and updates; analytical systems need fast complex queries over history. Plan transactions, update frequency, response time, backup and recovery. Schema design, indexing and partitioning drive performance."],
  ["Scalability", "The ability to handle more data, workload and users."],
  ["Normalization", "Organizing data to save space, ease maintenance and speed access: good for transactional systems, but it can slow analytical queries (hence denormalizing for reporting)."],
  ["Storage", "Performance (throughput and latency), availability (no downtime), integrity (safe from corruption, loss and attack) and recoverability (after failures and disasters)."],
  ["Privacy, security, governance", "Rules such as GDPR, CCPA and HIPAA limit how personal data is owned, used and managed. Design for them from the start, because adding them later means patchwork."],
];
const SECURITY = [
  ["CIA triad", "Confidentiality (control who can see), integrity (data is trustworthy and untampered), availability (authorized users can reach it when needed). Applies to every level below.", "Governance controls cover all three."],
  ["Physical infrastructure", "Perimeter access, surveillance, backup power and cooling, and sites chosen away from floods and earthquakes. In the cloud this is the provider's job.", "Not covered by software; your own computer's physical safety is yours."],
  ["Network", "Firewalls, network access control, segmentation into separate zones, secure protocols for data in transit, intrusion detection and prevention.", "The Network and Cybersecurity tracks."],
  ["Application", "Threat modeling, secure design, secure coding and security testing before release.", "The Full Stack and Cybersecurity tracks."],
  ["Data", "Authentication (passwords, tokens, biometrics) and authorization (access by role). Encrypt data at rest (databases, backups, devices) and in transit (HTTPS, TLS).", "PII scan, Protect from AI, Access log. Database-file encryption is not built: use full-disk or file encryption outside the app."],
  ["Monitoring", "Track and react to violations in time, with an audit history for triage and compliance.", "Activity log and Access page."],
];

const PERF = [
  ["Pipeline threats", "Growing data and workloads, application failures, scheduled jobs that start late, wait on dependencies or run out of order, and tools that do not fit together.", "Pipeline monitor and the idempotency check."],
  ["Pipeline metrics", "Latency (time to fulfil a request), failures (rate), resource use and its patterns, and traffic (requests per period).", "Database admin benchmarks give latency; Activity log shows failures."],
  ["Troubleshooting steps", "1) Collect facts and confirm it is really an issue. 2) Check software and code versions and what changed in recent deployments. 3) Read logs and metrics (CPU, memory, network) to decide whether it is infrastructure, data, software or a mix. 4) If logs don't say, reproduce it in a test environment. 5) Test your root-cause hypothesis, then plan the fix through your team's process.", "Ask the agent to walk you through one."],
  ["Database metrics", "Outages, capacity use, application slowdown, query performance, and conflicting queries or batch jobs competing for resources.", "Database admin: health, benchmarks, growth."],
  ["Capacity planning", "Work out the hardware and software you need as load changes day to day, and for future growth.", "The growth chart in Database admin."],
  ["Indexing", "Finds rows without scanning every one and cuts disk reads.", "Query plans show full scans."],
  ["Partitioning", "Splits very large tables into smaller pieces so queries touch less data and are easier to manage.", "Parquet partitioning in the Big data lab."],
  ["Normalization", "Reduces inconsistencies from redundancy and update, delete and insert anomalies.", "See Designing a store."],
  ["Monitoring and alerting", "Database monitors take regular snapshots so you can see when a problem began; application performance tools track response times, errors and per-process resources; query monitors track throughput and execution; job-level monitoring splits a long job into steps so failures show early instead of at the end; watching data volume shows if workload size is the slowdown.", "KPI alerts and the pipeline run history."],
  ["Preventive maintenance", "Time-based (scheduled at set intervals) or condition-based (done when performance drops or a fault is flagged); both generate data to find what causes faults.", "CHECKPOINT, backup schedule and verify-backup."],
];
const QUERY = [
  ["Count rows", "SELECT COUNT(*) FROM t;", "How much data you have."],
  ["Count distinct", "SELECT COUNT(DISTINCT dealer) FROM t;", "How many unique values a column holds."],
  ["Sum, average, spread", "SELECT SUM(price), AVG(price), STDDEV(price) FROM t;", "A large standard deviation means a wide spread; one average can hide very cheap and very dear rows."],
  ["Extremes", "SELECT MAX(price), MIN(price) FROM t;", "Highest and lowest values."],
  ["Slice (filter rows)", "SELECT * FROM t WHERE price BETWEEN 1000 AND 2000 AND area = 'North';", "Rows meeting one or more conditions. In SQL this is WHERE."],
  ["Sort", "SELECT * FROM t ORDER BY purchase_date DESC;", "Ascending or descending, for example to see if sales rise around a festival."],
  ["Filter by pattern", "SELECT * FROM t WHERE pincode LIKE '560%';", "LIKE with wildcards matches part of a value (% for any run, _ for one character)."],
  ["Group", "SELECT pincode, SUM(price) FROM t GROUP BY pincode;", "Totals per group."],
];

const REGS = [
  ["GDPR", "European Union: protects personal data and privacy of EU citizens in transactions within member states."],
  ["CCPA", "California: protects consumer data. Other US states have their own rules."],
  ["HIPAA", "US healthcare: governs collection and disclosure of protected health information."],
  ["PCI DSS", "Retail and anyone handling cards: standards for credit card data."],
  ["SOX", "US finance: handling and reporting of financial information."],
];
const LIFECYCLE = [
  ["Acquisition", "What you collect, the contract or consent that gives you the right, the intended use published as a privacy policy, and only as much data as the purpose needs (is an email enough, or do you also need phone and postal code?)."],
  ["Processing", "How personal data is processed and the legal basis, such as a contract or consent."],
  ["Storage", "Where it lives and the measures against internal and external breaches."],
  ["Sharing", "Which third-party vendors may access it, and how they are held contractually to the same rules."],
  ["Retention and disposal", "How long it is kept, and how deletion reaches every location including third-party systems."],
  ["Throughout", "Keep an auditable trail of acquisition, processing, storage, access, retention and deletion. Compliance is ongoing, not one-time; penalties include fines, damaged reputation and lost trust."],
];
const CONTROLS = [
  ["Authentication and access control", "Layered sign-in (passwords, tokens, biometrics) and access by group and role, down to tables, rows or columns.", "Personal single-user app: no logins. Roles matter in the databases you connect."],
  ["Encryption", "Encoded data readable only with a key, at rest and in transit.", "HTTPS for outside calls. Database-file encryption is not built."],
  ["Data masking", "Anonymization hides values on display; pseudonymization replaces identifiers with artificial ones so records can't be traced to a person.", "De-identify tab."],
  ["Hosting and transfer rules", "Choose on-premise or cloud hosting that meets rules on international transfers.", "Everything stays on your computer unless you send it out (see Access)."],
  ["Monitoring and alerting", "Track access and operations, with severity-based alerts to trigger action.", "Activity log, Access page and KPI alerts."],
  ["Data erasure", "Software-based permanent clearing by overwriting, which differs from ordinary deletion that can be recovered.", "Retention purge deletes expired rows; secure overwriting is not built."],
];

function DeidTab() {
  const [src, setSrc] = useState<{ id: string; label: string; columns: { name: string; kind: string }[] }[]>([]);
  const [table, setTable] = useState("");
  const [pick, setPick] = useState<Record<string, string>>({});
  const [name, setName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [assets, setAssets] = useState<{ name: string; kind: string; system: boolean; retention_days: number | null; retention_column: string; retention_eligible_rows: number | null }[]>([]);
  const [pmsg, setPmsg] = useState<string | null>(null);
  const loadAssets = useCallback(() => getJson<{ assets: typeof assets }>("/api/governance/catalog").then((c) => setAssets(c.assets.filter((a) => !a.system && a.kind === "table" && a.retention_days))).catch(() => setAssets([])), []);
  useEffect(() => {
    getJson<{ sources: typeof src }>("/api/stats/sources").then((m) => { const mine = m.sources.filter((x) => x.id !== "operations"); setSrc(mine); setTable((t) => t || mine[0]?.id || ""); }).catch((e) => setErr(errMsg(e, "Couldn't load your data.")));
    loadAssets();
  }, [loadAssets]);
  const cols = src.find((x) => x.id === table)?.columns ?? [];
  const run = async () => {
    setErr(null); setMsg(null);
    try {
      const columns = Object.fromEntries(Object.entries(pick).filter(([, v]) => v));
      const r = await postJson<{ table: string; rows: number; note: string }>("/api/governance/deidentify", { table, new_table: name, columns });
      setMsg(`Created ${r.table} (${r.rows.toLocaleString()} rows). ${r.note}`);
    } catch (e) { setErr(errMsg(e, "That didn't work.")); }
  };
  const purge = async (n: string, confirm: boolean) => {
    setErr(null);
    try { const r = await postJson<{ note: string }>("/api/governance/purge", { name: n, confirm }); setPmsg(`${n}: ${r.note}`); loadAssets(); } catch (e) { setErr(errMsg(e, "That didn't work.")); }
  };
  return (
    <div className="space-y-4">
      <Section title="De-identified copy" note="Makes a new table; your original is never changed and still holds the personal data. Pseudonyms are stable, so the same person gets the same id across tables. A copy is not proof of anonymity.">
        {src.length === 0 ? <p className="text-sm text-muted">Import a table in My data first.</p> : (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Table"><select className="field" value={table} onChange={(e) => { setTable(e.target.value); setPick({}); }} aria-label="Table">{src.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)}</select></Field>
              <Field label="New table name"><input className="field" value={name} onChange={(e) => setName(e.target.value)} placeholder="for example customers_safe" aria-label="New table name" /></Field>
            </div>
            <ul className="mt-3 space-y-2">
              {cols.map((c) => (
                <li key={c.name} className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="min-w-[8rem] break-words">{c.name}</span>
                  <select className="field" value={pick[c.name] ?? ""} onChange={(e) => setPick({ ...pick, [c.name]: e.target.value })} aria-label={`Treatment for ${c.name}`}>
                    <option value="">keep as is</option><option value="mask">mask</option><option value="pseudonym">pseudonym</option><option value="generalize">generalize</option><option value="drop">leave out</option>
                  </select>
                </li>
              ))}
            </ul>
            <button className="btn btn-primary mt-3" disabled={!name.trim() || !Object.values(pick).some(Boolean)} onClick={run}>Create the copy</button>
          </>
        )}
        {msg && <p className="mt-3 text-sm">{msg}</p>}
      </Section>
      <Section title="Retention purge" note="Deletes rows older than the retention rule you set in Data governance, Catalog. A safety backup is taken first for Real data. This is ordinary deletion, not secure overwriting: old backups keep the data until removed.">
        {assets.length === 0 ? <p className="text-sm text-muted">No table has a retention rule yet.</p> : (
          <ul className="space-y-2 text-sm">
            {assets.map((a) => (
              <li key={a.name} className="flex flex-wrap items-center gap-2">
                <span className="break-words">{a.name}: keep {a.retention_days} days by {a.retention_column}; {a.retention_eligible_rows ?? 0} rows expired</span>
                <button className="btn" onClick={() => purge(a.name, false)}>Check</button>
                <button className="btn" disabled={!a.retention_eligible_rows} onClick={() => { if (window.confirm(`Delete ${a.retention_eligible_rows} expired rows from ${a.name}?`)) purge(a.name, true); }}>Delete expired rows</button>
              </li>
            ))}
          </ul>
        )}
        {pmsg && <p className="mt-3 text-sm">{pmsg}</p>}
      </Section>
      {err && <ErrorBanner message={err} />}
    </div>
  );
}

const DATAOPS = [
  ["Establish DataOps", "Set the organization up for success in managing data: roles, tools, standards, the catalog and the delivery process."],
  ["Iterate DataOps", "Deliver the data for one defined sprint: agree the need, find and prepare the data, build and test the pipeline, deliver, and monitor."],
  ["Improve DataOps", "Channel what each sprint taught you back into the process so it keeps getting better."],
  ["Benefits", "Automated metadata and catalog, traceable lineage for trust and audit, automated workflows that protect integrity and security, faster delivery, a business-ready pipeline that is always available, fewer defects and a data-driven culture."],
  ["Core practices", "Metadata management, workflow and test automation, code repositories, collaboration tools and orchestration."],
  ["Career path", "DataOps engineers focus on the development and deployment lifecycle rather than the product itself, and can grow into data strategy, process and performance-measurement roles."],
];

interface Ready { overall: number | null; ready_at: number; ready_tables: number; note: string; backup: { ok: boolean; note: string }; review_enabled: boolean;
  tables: { table: string; rows: number; score: number; ready: boolean; by_word: Record<string, number>; fix: string[] }[];
  reviews: { at: string; overall: number | null; ready_tables: number; table_count: number; worse: { table: string; was: number; now: number }[]; better: { table: string; was: number; now: number }[]; todo: string[]; note: string }[]; weights: { id: string; label: string; weight: number; word: string }[] }

function ScorecardTab() {
  const [d, setD] = useState<Ready | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => getJson<Ready>("/api/pipeline/readiness").then((x) => { setD(x); setErr(null); }).catch((e) => setErr(errMsg(e, "Couldn't score your data."))), []);
  useEffect(() => { load(); }, [load]);
  const review = async () => { setBusy(true); try { await postJson("/api/pipeline/readiness/review", {}); await load(); } catch (e) { setErr(errMsg(e, "The review failed.")); } finally { setBusy(false); } };
  const toggle = async (on: boolean) => { try { await putJson("/api/pipeline/readiness/schedule", { enabled: on }); await load(); } catch (e) { setErr(errMsg(e, "Couldn't change the schedule.")); } };
  return (
    <div className="space-y-4">
      <Section title="Analytics-ready scorecard" note="A table is ready at 80 or more. The four words come from the data engineer's job: accurate, reliable, compliant with the rules that govern it, and accessible. It is a guide to what to fix first, not a certificate.">
        {err && <ErrorBanner message={err} />}
        {d && (d.overall == null ? <p className="text-sm text-muted">No tables to score yet. Import one in My data.</p> : (
          <>
            <p className="text-sm"><b>{d.overall}/100</b> overall; {d.ready_tables} of {d.tables.length} tables are ready. Backup: {d.backup.note}.</p>
            <div className="mt-3"><Table head={["Table", "Score", "Accurate", "Reliable", "Compliant", "Accessible", "Fix first"]} rows={d.tables.map((t) => [t.table, <Badge key="s" tone={t.ready ? "ok" : t.score >= 50 ? "warn" : "bad"}>{t.score}</Badge>, t.by_word.accurate, t.by_word.reliable, t.by_word.compliant, t.by_word.accessible, t.fix.slice(0, 3).join("; ") || "nothing"])} /></div>
          </>
        ))}
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <button className="btn btn-primary" onClick={review} disabled={busy}>{busy ? "Reviewing…" : "Run a review now"}</button>
          {d && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={d.review_enabled} onChange={(e) => toggle(e.target.checked)} /> Review automatically every week</label>}
        </div>
      </Section>
      {d && d.reviews.length > 0 && (
        <Section title="Past reviews" note="Each review compares with the one before it.">
          <Table head={["When (UTC)", "Overall", "Ready", "Got worse", "Improved", "Fix first"]} rows={d.reviews.map((r) => [r.at, r.overall ?? "—", `${r.ready_tables}/${r.table_count}`, r.worse.map((w) => `${w.table} (${w.was}→${w.now})`).join(", ") || "—", r.better.map((w) => `${w.table} (${w.was}→${w.now})`).join(", ") || "—", r.todo.slice(0, 2).join("; ") || "—"])} />
        </Section>
      )}
    </div>
  );
}

interface Issue { id: string; role: string; severity: string; table: string; column: string; summary: string; expected: string; status: string; reply: string; created: string }

function IssuesTab() {
  const [d, setD] = useState<{ issues: Issue[]; open: number; total: number; roles: string[]; severities: string[]; statuses: string[] } | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState({ role: "analyst", severity: "medium", table: "", column: "", summary: "", expected: "" });
  const [reply, setReply] = useState<Record<string, string>>({});
  const load = useCallback(() => getJson<NonNullable<typeof d>>("/api/pipeline/issues").then((x) => { setD(x); setErr(null); }).catch((e) => setErr(errMsg(e, "Couldn't load the issues."))), []);
  useEffect(() => { load(); }, [load]);
  const act = async (fn: () => Promise<unknown>) => { try { await fn(); setErr(null); await load(); } catch (e) { setErr(errMsg(e, "That didn't work.")); } };
  return (
    <div className="space-y-4">
      <Section title="Report a data problem" note="Analysts, scientists and BI users log what is wrong with the data here (the agents can also send one). The data engineer works the queue below.">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Who is reporting"><select className="field" value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })} aria-label="Who is reporting">{(d?.roles ?? ["analyst"]).map((r) => <option key={r}>{r}</option>)}</select></Field>
          <Field label="How serious"><select className="field" value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })} aria-label="How serious">{(d?.severities ?? ["medium"]).map((r) => <option key={r}>{r}</option>)}</select></Field>
          <Field label="Table (optional)"><input className="field" value={f.table} onChange={(e) => setF({ ...f, table: e.target.value })} aria-label="Table" /></Field>
          <Field label="Column (optional)"><input className="field" value={f.column} onChange={(e) => setF({ ...f, column: e.target.value })} aria-label="Column" /></Field>
        </div>
        <div className="mt-3 grid gap-3"><Field label="What is wrong"><input className="field" value={f.summary} onChange={(e) => setF({ ...f, summary: e.target.value })} aria-label="What is wrong" /></Field>
          <Field label="What you expected (optional)"><input className="field" value={f.expected} onChange={(e) => setF({ ...f, expected: e.target.value })} aria-label="What you expected" /></Field></div>
        <button className="btn btn-primary mt-3" disabled={f.summary.trim().length < 5} onClick={() => act(async () => { await postJson("/api/pipeline/issues", f); setF({ ...f, summary: "", expected: "", table: "", column: "" }); })}>Send to the data engineer</button>
      </Section>
      {err && <ErrorBanner message={err} />}
      <Section title={d ? `Queue: ${d.open} open of ${d.total}` : "Queue"}>
        {d && d.issues.length === 0 && <p className="text-sm text-muted">No issues logged.</p>}
        <ul className="space-y-3">
          {(d?.issues ?? []).map((i) => (
            <li key={i.id} className="rounded-lg border border-line p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2"><Badge tone={i.severity === "high" ? "bad" : i.severity === "medium" ? "warn" : "muted"}>{i.severity}</Badge><Badge>{i.status.replace("_", " ")}</Badge><span className="text-xs text-muted">from {i.role}, {i.created}</span></div>
              <p className="mt-1 break-words"><b>{i.table ? `${i.table}${i.column ? "." + i.column : ""}: ` : ""}</b>{i.summary}{i.expected ? ` (expected: ${i.expected})` : ""}</p>
              {i.reply && <p className="mt-1 text-muted">Engineer: {i.reply}</p>}
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <select className="field" value={i.status} aria-label={`Status of ${i.summary.slice(0, 30)}`} onChange={(e) => act(() => patchJson(`/api/pipeline/issues/${i.id}`, { status: e.target.value }))}>{(d?.statuses ?? []).map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}</select>
                <input className="field" placeholder="reply" aria-label="Reply" value={reply[i.id] ?? ""} onChange={(e) => setReply({ ...reply, [i.id]: e.target.value })} />
                <button className="btn" disabled={!(reply[i.id] ?? "").trim()} onClick={() => act(async () => { await patchJson(`/api/pipeline/issues/${i.id}`, { reply: reply[i.id] }); setReply({ ...reply, [i.id]: "" }); })}>Reply</button>
                <button className="btn" onClick={() => act(() => deleteJson(`/api/pipeline/issues/${i.id}`))}>Delete</button>
              </div>
            </li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

const ECO = [
  ["1. Data sources", "Structured and unstructured data: databases, files, clickstreams, social media, devices, streams, legacy systems, outside providers.", "Mixed formats and unreliable feeds."],
  ["2. Acquire into a repository", "Pull a copy of the data you need into one place.", "Reliability, security and integrity while pulling."],
  ["3. Organize and clean", "Make it consistent and optimized for access; follow standards, master data and privacy rules.", "Availability, flexibility, accessibility and security of the repository."],
  ["4. Deliver to users", "Analysts get raw tables, managers get reports and dashboards, applications get APIs.", "Giving each user the form they need."],
];

const IDEAS = [
  ["Structured data", "Fits rows and columns: databases and spreadsheets."],
  ["Semi-structured data", "A mix, such as an email (sender and date are structured, the body is not), JSON or XML."],
  ["Unstructured data", "Photos, video, text files, PDFs, social media. Needs a lake or object store and other tools."],
  ["OLTP", "Transactional systems for high-volume day-to-day work: banking, bookings, orders."],
  ["OLAP", "Analytical systems for complex analysis: warehouses, marts, lakes, big data stores."],
  ["Data mart", "A slice of a warehouse for one team or subject."],
  ["ETL", "Extract, transform, then load: clean before it lands in the target."],
  ["ELT", "Extract, load raw, then transform inside the target (what bronze, silver, gold does)."],
  ["Data integration", "Combine sources into one unified view users query through a single interface."],
  ["Languages", "SQL to query, Python to build data applications, shell scripts for repetitive operations."],
  ["BI and reporting tools", "Drag-and-drop dashboards used by analysts; enabled and managed by data engineers."],
];

interface CdcDiff { inserted: number; updated: number; deleted: number; unchanged: number; changed_by_column: Record<string, number>; columns_only_in_old: string[]; columns_only_in_new: string[]; feed_table: string | null; feed_rows: number | null; lesson: string }
interface CdcApply { table: string; mode: string; events: number; keys: number; rows: number; out_of_order_events: number; lesson: string; note: string }
interface Src { id: string; label: string; columns: { name: string }[] }

function CdcTab() {
  const [srcs, setSrcs] = useState<Src[]>([]);
  const [old, setOld] = useState(""); const [nw, setNw] = useState(""); const [key, setKey] = useState(""); const [feedName, setFeedName] = useState("");
  const [diff, setDiff] = useState<CdcDiff | null>(null);
  const [feed, setFeed] = useState(""); const [fkey, setFkey] = useState(""); const [opCol, setOpCol] = useState("_op"); const [seqCol, setSeqCol] = useState("_seq");
  const [mode, setMode] = useState("scd1"); const [out, setOut] = useState(""); const [res, setRes] = useState<CdcApply | null>(null);
  const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const load = useCallback(() => {
    Promise.all([getJson<{ tables?: { table_name: string }[] } | { table_name: string }[]>("/api/data/tables"), getJson<{ sources: Src[] }>("/api/stats/sources")])
      .then(([t, s]) => {
        const names = new Set((Array.isArray(t) ? t : t.tables ?? []).map((x) => x.table_name));
        setSrcs(s.sources.filter((x) => names.has(x.id)));
      })
      .catch((e) => setErr(errMsg(e, "Couldn't load your tables.")));
  }, []);
  useEffect(() => { load(); }, [load]);
  const cols = (id: string) => srcs.find((x) => x.id === id)?.columns.map((c) => c.name) ?? [];
  const pick = (v: string, set: (x: string) => void) => <select className="field" value={v} onChange={(e) => set(e.target.value)} aria-label="Table">{[<option key="" value="">Choose a table</option>, ...srcs.map((x) => <option key={x.id} value={x.id}>{x.label}</option>)]}</select>;
  const keys = (k: string) => k.split(",").map((x) => x.trim()).filter(Boolean);
  const doDiff = async () => {
    setBusy(true); setErr(null);
    try { setDiff(await postJson<CdcDiff>("/api/pipeline/cdc/diff", { old, new: nw, key: keys(key), create_feed: feedName || null })); if (feedName) load(); } catch (e) { setDiff(null); setErr(errMsg(e, "That didn't work.")); } finally { setBusy(false); }
  };
  const doApply = async () => {
    setBusy(true); setErr(null);
    try { setRes(await postJson<CdcApply>("/api/pipeline/cdc/apply", { feed, key: keys(fkey), op_col: opCol, seq_col: seqCol, mode, new_table: out })); load(); } catch (e) { setRes(null); setErr(errMsg(e, "That didn't work.")); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      <Section title="1. Compare two snapshots" note="Use this when a source gives you whole copies (yesterday and today) but no log of changes. Your tables are never changed; the optional change feed is a new table.">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Old snapshot">{pick(old, setOld)}</Field>
          <Field label="New snapshot">{pick(nw, setNw)}</Field>
          <Field label="Key column(s), comma separated"><input className="field" value={key} onChange={(e) => setKey(e.target.value)} placeholder={cols(old)[0] ?? "id"} aria-label="Key columns" /></Field>
          <Field label="Save change feed as (optional)"><input className="field" value={feedName} onChange={(e) => setFeedName(e.target.value)} aria-label="Change feed name" /></Field>
          <button className="btn btn-primary" disabled={busy || !old || !nw || !key.trim()} onClick={doDiff}>{busy ? "Working…" : "Compare"}</button>
        </div>
      </Section>
      {err && <ErrorBanner message={err} />}
      {diff && (
        <>
          <Lesson text={diff.lesson} />
          <Section title="What changed">
            <Table head={["Inserted", "Updated", "Deleted", "Unchanged"]} rows={[[diff.inserted, diff.updated, diff.deleted, diff.unchanged].map((n) => n.toLocaleString())]} />
            {Object.keys(diff.changed_by_column).length > 0 && <p className="mt-2 text-xs text-muted">Updated values by column: {Object.entries(diff.changed_by_column).map(([c, n]) => `${c} (${n})`).join(", ")}.</p>}
            {(diff.columns_only_in_old.length > 0 || diff.columns_only_in_new.length > 0) && <p className="mt-2 text-xs text-muted">Columns only in old: {diff.columns_only_in_old.join(", ") || "none"}. Only in new: {diff.columns_only_in_new.join(", ") || "none"}.</p>}
            {diff.feed_table && <p className="mt-2 text-sm">Change feed saved as <code>{diff.feed_table}</code> ({diff.feed_rows?.toLocaleString()} rows, with _op and _seq columns).</p>}
          </Section>
        </>
      )}
      <Section title="2. Apply a change feed" note="Turn a feed of inserts, updates and deletes into a current-state table (SCD type 1) or a full history (SCD type 2). Events are ordered by the sequence column, so late arrivals still land correctly.">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Change feed">{pick(feed, setFeed)}</Field>
          <Field label="Key column(s)"><input className="field" value={fkey} onChange={(e) => setFkey(e.target.value)} placeholder={cols(feed)[0] ?? "id"} aria-label="Feed key columns" /></Field>
          <Field label="Operation column"><input className="field" value={opCol} onChange={(e) => setOpCol(e.target.value)} aria-label="Operation column" /></Field>
          <Field label="Sequence column"><input className="field" value={seqCol} onChange={(e) => setSeqCol(e.target.value)} aria-label="Sequence column" /></Field>
          <Field label="Keep"><select className="field" value={mode} onChange={(e) => setMode(e.target.value)} aria-label="Mode"><option value="scd1">Latest only (SCD 1)</option><option value="scd2">Full history (SCD 2)</option></select></Field>
          <Field label="Save result as"><input className="field" value={out} onChange={(e) => setOut(e.target.value)} aria-label="Result table name" /></Field>
          <button className="btn btn-primary" disabled={busy || !feed || !fkey.trim() || !out.trim()} onClick={doApply}>{busy ? "Working…" : "Apply changes"}</button>
        </div>
      </Section>
      {res && (
        <>
          <Lesson text={res.lesson} />
          <Section title="Result"><p className="text-sm">Saved <code>{res.table}</code>: {res.rows.toLocaleString()} rows from {res.events.toLocaleString()} events across {res.keys.toLocaleString()} keys. {res.note}</p></Section>
        </>
      )}
    </div>
  );
}

const BIGBOOK = [
  ["Declarative pipelines", "Say what the result should be and let the engine work out ordering, retries and incremental updates, instead of hand-coding every step.", "Pipeline tab: stages run in a fixed order with a quality gate; Design tab: pipeline plans.", "Spark Declarative Pipelines and Lakeflow are Databricks products; not available here."],
  ["Change data capture and SCD", "Capture inserts, updates and deletes and apply them in order. Type 1 keeps the latest row, type 2 keeps history with start and end markers. Late events are placed by sequence value.", "Change capture tab: compare snapshots, build a change feed, apply as SCD 1 or 2.", "Log-based capture from a live database needs a streaming source; not available here."],
  ["Incremental intake", "Pick up only files or rows not seen before, instead of reloading everything.", "Import: Add only new rows, by key or by date column. Pipeline: gate.", "Cloud Auto Loader and file notifications are cloud features; not available here."],
  ["Schema contracts", "Decide what happens when new data does not fit: block it, or keep the odd parts aside. A gate protects downstream tables; a rescue column keeps unexpected fields.", "Import shows a schema-change warning; the pipeline gate blocks a bad run.", "Import: Keep extra columns in a _rescued column (append modes)."],
  ["Silent failures", "A pipeline can succeed and still be wrong: volume drops, no new data arrived, rows pile up in quarantine. Watch volume, freshness and reconciliation, not only errors.", "Health scorecard, reconciliation checks, weekly health review, Data issues queue.", ""],
  ["Detect, assess, remediate, verify", "A safe loop for fixing problems: detect the issue, assess impact, propose a fix, then verify it before it touches real data.", "Data issues queue, then try the fix in the Practice workspace before Real.", "Autonomous remediation (ZeroOps) is not available; you approve each step."],
  ["Agentic data engineering", "An assistant that reads the state of your pipelines and proposes changes you approve.", "The Data Engineer agent proposes plans, notes and issues; nothing runs until you accept.", "Agent Bricks and Genie are Databricks products; not available here."],
  ["Streaming and real time", "Process events as they arrive with low delay, rather than in daily batches.", "Not run here. Batch pipelines and scheduled health reviews cover the daily cases.", "Kafka, Zerobus and real-time mode need cloud or cluster services."],
  ["Governance at scale", "One catalog for access control, lineage and discovery across all data.", "Metadata tab, classification, owners, audit trail, de-identify and purge.", "Unity Catalog is a Databricks product; not available here."],
  ["Operational and analytical together", "Serve application data and analytics from linked systems so teams stop copying data around.", "Not run here (single local database).", "Lakebase and managed Postgres are cloud services."],
];

export function DesignPanel() {
  const [tab, setTab] = useState("score");
  return (
    <div className="space-y-4">
      <Tabs label="Design tools" value={tab} onChange={setTab} tabs={[{ id: "score", label: "Health scorecard" }, { id: "issues", label: "Data issues" }, { id: "arch", label: "Data architecture plan" }, { id: "store", label: "Choose a store" }, { id: "star", label: "Star schema" }, { id: "meta", label: "Metadata" }, { id: "wh", label: "Warehouse design note" }, { id: "dm", label: "Data management plan" }, { id: "eco", label: "Data ecosystem" }, { id: "repo", label: "Repositories and RDBMS" }, { id: "etl", label: "ETL, ELT and pipelines" }, { id: "cdc", label: "Change capture (CDC)" }, { id: "relational", label: "Relational design" }, { id: "bigbook", label: "Modern pipeline ideas" }, { id: "layers", label: "Platform layers" }, { id: "factors", label: "Designing a store" }, { id: "secu", label: "Security levels" }, { id: "dataops", label: "DataOps" }, { id: "dataopsnote", label: "DataOps sprint note" }, { id: "comply", label: "Governance and compliance" }, { id: "deid", label: "De-identify and erase" }, { id: "perf", label: "Performance and troubleshooting" }, { id: "query", label: "Querying basics" }, { id: "wrangle", label: "Data wrangling" }, { id: "fmt", label: "File formats" }, { id: "src", label: "Sources and gathering" }, { id: "lang", label: "Languages" }]} />
      {tab === "score" && <ScorecardTab />}
      {tab === "issues" && <IssuesTab />}
      {tab === "arch" && <QualTab kinds={["architecture"]} />}
      {tab === "store" && <StoreTab />}
      {tab === "star" && <StarTab />}
      {tab === "meta" && <MetadataTab />}
      {tab === "wh" && <QualTab kinds={["warehouse"]} />}
      {tab === "dm" && <QualTab kinds={["dmplan"]} />}
      {tab === "layers" && <Section title="Layers of a data platform" note="Each layer is a set of functions, not one product."><Table head={["Layer", "What it does", "In this app"]} rows={LAYERS} /></Section>}
      {tab === "factors" && <Section title="What to weigh when choosing and designing a data store" note="Use Choose a store for a quick recommendation, then record the decision in a Data architecture plan."><Table head={["Factor", "What to consider"]} rows={STORE_FACTORS} /></Section>}
      {tab === "secu" && <Section title="Security at four levels, plus monitoring"><Table head={["Level", "Measures", "In this app"]} rows={SECURITY} /></Section>}
      {tab === "wrangle" && <WrangleTab />}
      {tab === "dataops" && <Section title="The DataOps methodology" note="DataOps is a collaborative practice for communication, integration and automation of data flows between data managers and consumers. It aims at predictable delivery and change management of data and data models. Platforms such as IBM DataOps, Nexla and StreamSets are not available here: this app practises the method with the pipeline, tests and catalog."><Table head={["Phase or idea", "What it means"]} rows={DATAOPS} /></Section>}
      {tab === "dataopsnote" && <QualTab kinds={["dataops"]} />}
      {tab === "comply" && (
        <div className="space-y-4">
          <Section title="Data governance" note="Principles, practices and processes that keep data secure, private and accurate through its whole life, covering technologies, databases and data models. Regulations mainly protect personal and sensitive data: anything that identifies a person or could harm them, such as race, sexual orientation or genetic information."><Table head={["Regulation", "Covers"]} rows={REGS} /></Section>
          <Section title="Compliance through the data lifecycle"><Table head={["Stage", "What to establish"]} rows={LIFECYCLE} /></Section>
          <Section title="Controls and tools"><Table head={["Control", "What it does", "In this app"]} rows={CONTROLS} /></Section>
        </div>
      )}
      {tab === "deid" && <DeidTab />}
      {tab === "perf" && <Section title="Performance tuning and troubleshooting" note="Run benchmarks and read query plans in Database admin."><Table head={["Topic", "What to know", "In this app"]} rows={PERF} /></Section>}
      {tab === "query" && (
        <Section title="Querying and analysing data with SQL" note="The same ideas exist in other query languages (CQL for Cassandra, Cypher for Neo4j) and through APIs. Replace t and the column names with your own, and run it in SQL Lab.">
          <Table head={["Technique", "Example", "What it tells you"]} rows={QUERY.map(([a, b, c]) => [a, <code key={a} className="break-words text-xs">{b}</code>, c])} />
          <p className="mt-3 text-sm"><Link href="/lab" className="underline">Open SQL Lab</Link></p>
        </Section>
      )}
      {tab === "etl" && (
        <Section title="Moving and combining data" note="Run the real thing on the Pipeline tab of this dashboard.">
          <Table head={["Idea", "Meaning", "In this app"]} rows={ETL} />
        </Section>
      )}
      {tab === "repo" && (
        <div className="space-y-4">
          <Section title="Kinds of data repository" note="The choice depends on data type and structure, query style, latency, transaction speed and how the data will be used. Try Choose a store for a recommendation."><Table head={["Repository", "What it is", "In this app"]} rows={REPOS} /></Section>
          <Section title="Warehouses, data marts and lakes" note="Warehouse: structure first (schema on write). Lake: structure when you read (schema on read). A mart's purpose is to give a group the data most relevant to them, fast and with secure access. Here a mart is a gold table or view, and cloud warehouses and Hadoop-based lakes are not run.">
            <Table head={["Kind", "What it is", "Notes"]} rows={WHM} />
          </Section>
          <Section title="Four kinds of NoSQL (not only SQL)" note="NoSQL scales out across cheap commodity servers and stores any structure, but most give up full ACID guarantees and are a newer technology than RDBMS. None of these run in this app.">
            <Table head={["Model", "How it stores data", "Good for", "Poor fit", "Examples"]} rows={NOSQL} />
          </Section>
          <Section title="Relational databases in detail"><Table head={["Idea", "Meaning"]} rows={RDBMS} /></Section>
        </div>
      )}
      {tab === "cdc" && <CdcTab />}
      {tab === "relational" && <RelationalTab />}
      {tab === "bigbook" && <Section title="Modern pipeline ideas and what is available here" note="From the Big Book of Data Engineering. The ideas are general; the last column says plainly what this app can and cannot do."><Table head={["Idea", "Meaning", "Where it lives here", "Not available here"]} rows={BIGBOOK} /></Section>}
      {tab === "fmt" && <FormatsTab />}
      {tab === "src" && <div className="space-y-4"><GatherImportTab /><SourcesGuideTab /></div>}
      {tab === "lang" && (
        <Section title="Languages for data professionals" note="Know at least one query language, one programming language and one shell or scripting language.">
          <Table head={["Language", "Kind", "What it is good for", "In this app"]} rows={LANGS} />
        </Section>
      )}
      {tab === "eco" && (
        <Section title="The modern data ecosystem" note="Cloud, machine learning and big data keep changing the tools, but these four stages stay the same. Data engineering is a team sport: one person rarely holds every skill.">
          <Table head={["Stage", "What happens", "Typical challenge"]} rows={ECO} />
        </Section>
      )}
      {tab === "eco" && (
        <Section title="Key ideas" note="Which store and which tool depends on the type of data and how it will be used.">
          <Table head={["Idea", "Meaning"]} rows={IDEAS} />
        </Section>
      )}
    </div>
  );
}
