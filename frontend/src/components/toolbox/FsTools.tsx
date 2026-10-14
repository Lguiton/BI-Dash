"use client";
import { useState } from "react";
import { useWorkTabs } from "@/lib/mode";
import { ErrorBanner } from "@/components/ErrorBanner";
import { postJson } from "@/lib/api";
import { Section, Tabs } from "@/components/panels/kit";
import { fetchText, HtmlFrame, Pick } from "./common";
import { FieldHowTo, Out, TA, TI, lines, cols, useRun } from "./fieldcommon";

const TABS = [{ id: "how", label: "How to do / fix" }, { id: "scaffold", label: "Scaffold writer" }, { id: "contract", label: "API contract" }, { id: "review", label: "Code review report" }, { id: "deploy", label: "Deploy runbook" }, { id: "quote", label: "Quote helper" }];

export function FsTools() {
  const [want, setTab] = useState("how");
  const { tabs, current: tab } = useWorkTabs(TABS, ["how"], want, true); // the field dashboard has its own fix-it panel
  return (
    <div className="grid gap-4">
      <Tabs label="Full stack tools" value={tab} onChange={setTab} tabs={tabs} />
      {tab === "how" && <FieldHowTo area="Full stack" agent="fullstack" examples="e.g. api has no login, how do I deploy safely" />}
      {tab === "scaffold" && <Scaffold />}
      {tab === "contract" && <Contract />}
      {tab === "review" && <Review />}
      {tab === "deploy" && <Deploy />}
      {tab === "quote" && <Quote />}
    </div>
  );
}

function Scaffold() {
  const [table, setTable] = useState("orders");
  const [fields, setFields] = useState("item, text, required\nquantity, integer\nordered_on, date");
  const [dialect, setDialect] = useState("sqlite");
  const r = useRun<Record<string, unknown>>();
  return (
    <Section title="Scaffold writer" note="Writes a database table, a FastAPI router and an HTML form as text for you to paste. Nothing runs and nothing is saved.">
      {r.err && <ErrorBanner message={r.err} />}
      <div className="grid gap-2">
        <div className="flex flex-wrap items-end gap-2"><TI label="Table name" value={table} onChange={setTable} w="w-48" /><Pick label="Database" value={dialect} onChange={setDialect} options={[{ id: "sqlite", label: "SQLite" }, { id: "postgres", label: "PostgreSQL" }, { id: "mysql", label: "MySQL" }, { id: "duckdb", label: "DuckDB" }]} blank="Database" /></div>
        <TA label="Fields: name, type (text, integer, number, decimal, date, timestamp, bool), optional 'required'" value={fields} onChange={setFields} rows={5} />
        <div><button className="btn" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/fs/scaffold", { table, dialect, fields: lines(fields).map((l) => { const c = cols(l); return { name: c[0], type: c[1] || "text", required: c[2] === "required" }; }) }), "Could not write the scaffold.")}>Write scaffold</button></div>
      </div>
      <Out data={r.res} />
    </Section>
  );
}

function Contract() {
  const [title, setTitle] = useState("Orders API");
  const [eps, setEps] = useState("GET, /orders, List orders\nPOST, /orders, Create an order\nGET, /orders/{id}, Get one order");
  const r = useRun<Record<string, unknown>>();
  return (
    <Section title="API contract writer" note="Writes the agreement between front end and back end as readable notes and as an OpenAPI file, before any code exists.">
      {r.err && <ErrorBanner message={r.err} />}
      <div className="grid gap-2">
        <TI label="API name" value={title} onChange={setTitle} w="w-64" />
        <TA label="Endpoints: method, path, what it does" value={eps} onChange={setEps} rows={5} />
        <div><button className="btn" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/fs/contract", { title, endpoints: lines(eps).map((l) => { const c = cols(l); return { method: c[0], path: c[1], summary: c.slice(2).join(", ") }; }) }), "Could not write the contract.")}>Write contract</button></div>
      </div>
      <Out data={r.res} />
    </Section>
  );
}

function Review() {
  const [code, setCode] = useState("");
  const [lang, setLang] = useState("auto");
  const [project, setProject] = useState("");
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Section title="Code review report" note="Runs the built-in checks (security smells, mistakes, style) over code you paste and makes a report for the client. A tool finds patterns; it does not replace a person reading the code.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2">
        <div className="flex flex-wrap items-end gap-2"><TI label="Project" value={project} onChange={setProject} w="w-56" /><Pick label="Language" value={lang} onChange={setLang} options={[{ id: "auto", label: "Detect" }, { id: "python", label: "Python" }, { id: "javascript", label: "JavaScript" }, { id: "sql", label: "SQL" }, { id: "shell", label: "Shell" }]} blank="Language" /></div>
        <TA label="Code to review" value={code} onChange={setCode} rows={10} />
        <div><button className="btn" disabled={!code.trim()} onClick={async () => { setErr(null); try { setHtml(await fetchText("/api/fieldbox/fs/review", { code, language: lang, project })); } catch (e) { setErr(e instanceof Error ? e.message : "Failed."); setHtml(null); } }}>Build report</button></div>
      </div>
      {html && <HtmlFrame html={html} name="code-review.html" />}
    </Section>
  );
}

function Deploy() {
  const [kind, setKind] = useState("web_app");
  const [host, setHost] = useState("vps");
  const [domain, setDomain] = useState("");
  const r = useRun<Record<string, unknown>>();
  return (
    <Section title="Deploy runbook" note="A tick-box checklist for putting an app on the internet and rolling it back.">
      {r.err && <ErrorBanner message={r.err} />}
      <div className="flex flex-wrap items-end gap-2">
        <Pick label="What you are deploying" value={kind} onChange={setKind} options={[{ id: "web_app", label: "Web app" }, { id: "api", label: "API" }, { id: "static_site", label: "Static site" }]} blank="Kind" />
        <Pick label="Where" value={host} onChange={setHost} options={[{ id: "vps", label: "Your own server (VPS)" }, { id: "paas", label: "Hosting platform" }, { id: "docker", label: "Docker" }]} blank="Host" />
        <TI label="Domain (optional)" value={domain} onChange={setDomain} w="w-56" placeholder="example.com" />
        <button className="btn" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/fs/runbook", { kind, host, domain }), "Could not build the runbook.")}>Build runbook</button>
      </div>
      <Out data={r.res} />
    </Section>
  );
}

function Quote() {
  const [feat, setFeat] = useState("Login, 6, 10\nOrder form, 8, 14\nReports, 10, 20");
  const [v, setV] = useState({ rate: "90", buffer_pct: "20", discount_pct: "0", deposit_pct: "40" });
  const r = useRun<Record<string, unknown>>();
  const set = (k: keyof typeof v) => (x: string) => setV({ ...v, [k]: x });
  return (
    <Section title="Quote helper" note="Hours for each feature, a buffer for changes, your rate, and a payment schedule. A suggestion to start from, not a market price.">
      {r.err && <ErrorBanner message={r.err} />}
      <div className="grid gap-2">
        <TA label="Features: name, low hours, high hours" value={feat} onChange={setFeat} rows={5} />
        <div className="flex flex-wrap gap-2"><TI label="Hourly rate" value={v.rate} onChange={set("rate")} w="w-28" /><TI label="Buffer %" value={v.buffer_pct} onChange={set("buffer_pct")} w="w-24" /><TI label="Discount %" value={v.discount_pct} onChange={set("discount_pct")} w="w-24" /><TI label="Deposit %" value={v.deposit_pct} onChange={set("deposit_pct")} w="w-24" /></div>
        <div><button className="btn" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/fs/quote", { features: lines(feat).map((l) => { const c = cols(l); return { name: c[0], hours_low: Number(c[1]), hours_high: Number(c[2]) }; }), rate: Number(v.rate), buffer_pct: Number(v.buffer_pct), discount_pct: Number(v.discount_pct), deposit_pct: Number(v.deposit_pct) }), "Could not build the quote.")}>Build quote</button></div>
      </div>
      <Out data={r.res} />
    </Section>
  );
}
