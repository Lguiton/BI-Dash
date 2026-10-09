"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { getJson } from "@/lib/api";
import type { SchemaObject } from "@/lib/types";

type Tag = "PK" | "FK" | "measure" | "attr";
interface Col { name: string; tag: Tag; note?: string }
interface Table { id: string; title: string; kind: string; x: number; y: number; w: number; cols: Col[] }

const FACT: Table = {
  id: "fact_operations", title: "fact_operations", kind: "FACT", x: 340, y: 20, w: 300,
  cols: [
    { name: "fact_id", tag: "PK" }, { name: "record_date", tag: "FK", note: "→ dim_date" }, { name: "entity_id", tag: "FK", note: "→ dim_entities" },
    { name: "revenue", tag: "measure", note: "additive" }, { name: "operational_cost", tag: "measure", note: "additive" },
    { name: "units_processed", tag: "measure", note: "additive" }, { name: "duration_minutes", tag: "measure", note: "additive (avg is not)" },
    { name: "status", tag: "attr", note: "degenerate dimension" },
  ],
};
const ENT: Table = {
  id: "dim_entities", title: "dim_entities", kind: "DIMENSION", x: 10, y: 60, w: 250,
  cols: [{ name: "entity_id", tag: "PK" }, { name: "name", tag: "attr" }, { name: "category", tag: "attr", note: "changes over time? see SCD lab" }, { name: "baseline_target", tag: "attr", note: "cost budget per record" }],
};
const DATE: Table = {
  id: "dim_date", title: "dim_date", kind: "DIMENSION (view)", x: 730, y: 20, w: 240,
  cols: [{ name: "date_key", tag: "PK" }, { name: "year", tag: "attr" }, { name: "quarter", tag: "attr" }, { name: "month / month_name", tag: "attr" },
         { name: "week_of_year", tag: "attr" }, { name: "day_of_week / day_name", tag: "attr" }, { name: "is_weekend", tag: "attr" }],
};
const ROW_H = 22, HEAD_H = 46;
const height = (t: Table) => HEAD_H + t.cols.length * ROW_H + 10;

const TAG_STYLE: Record<Tag, string> = { PK: "var(--accent)", FK: "var(--cat-3)", measure: "var(--good)", attr: "var(--muted)" };

const MEASURES = [
  { name: "revenue, operational_cost, units_processed, duration_minutes", type: "Additive", how: "SUM over any dimension (any category, any month).", example: "Total revenue by month, by entity, by anything." },
  { name: "margin %, revenue per unit, avg cost per record, cost vs budget %", type: "Non-additive", how: "Never sum or average the stored ratios. Re-compute as a ratio of sums.", example: "Margin = SUM(profit) / SUM(revenue), not AVG(margin)." },
  { name: "(none here) account balance, inventory level, headcount", type: "Semi-additive", how: "Add across entities, but not across time. Use the last value or an average over time.", example: "Total inventory today is a sum; 'inventory this year' is not the sum of 365 days." },
];

function TableBox({ t, count }: { t: Table; count?: number }) {
  return (
    <g>
      <rect x={t.x} y={t.y} width={t.w} height={height(t)} rx={10} fill="var(--panel)" stroke="var(--line)" strokeWidth={1.5} />
      <rect x={t.x} y={t.y} width={t.w} height={HEAD_H - 6} rx={10} fill={t.kind === "FACT" ? "var(--accent)" : "var(--panel-2)"} />
      <text x={t.x + 12} y={t.y + 19} fontSize={13} fontWeight={700} fill={t.kind === "FACT" ? "var(--accent-fg)" : "var(--fg)"}>{t.title}</text>
      <text x={t.x + 12} y={t.y + 33} fontSize={10} fill={t.kind === "FACT" ? "var(--accent-fg)" : "var(--muted)"}>
        {t.kind}{count !== undefined ? ` · ${count.toLocaleString("en-US")} rows` : ""}
      </text>
      {t.cols.map((c, i) => {
        const y = t.y + HEAD_H + i * ROW_H + 14;
        return (
          <g key={c.name}>
            <text x={t.x + 12} y={y} fontSize={11} fontFamily="ui-monospace, monospace" fill="var(--fg)" fontWeight={c.tag === "PK" ? 700 : 400}>{c.name}</text>
            <text x={t.x + t.w - 10} y={y} fontSize={10} textAnchor="end" fill={TAG_STYLE[c.tag]} fontWeight={600}>
              {c.tag === "attr" ? (c.note ?? "") : c.tag === "measure" ? `measure · ${c.note}` : `${c.tag}${c.note ? " " + c.note : ""}`}
            </text>
          </g>
        );
      })}
    </g>
  );
}

export default function SchemaPage() {
  const [flat, setFlat] = useState(false);
  const [objects, setObjects] = useState<SchemaObject[]>([]);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ objects: SchemaObject[] }>("/api/sql/schema", ctl.signal).then((r) => setObjects(r.objects)).catch(() => { /* counts just stay hidden */ });
    return () => ctl.abort();
  }, []);
  const rows = (n: string) => objects.find((o) => o.name === n)?.row_count;
  const flatCols = objects.find((o) => o.name === "v_operations_flat")?.columns ?? [];
  const factMid = FACT.y + HEAD_H + 1 * ROW_H + 9, factMid2 = FACT.y + HEAD_H + 2 * ROW_H + 9;

  return (
    <PageShell title="Star schema" subtitle="How this dashboard's data is modelled: one fact table in the middle, dimensions around it.">
      <div role="tablist" aria-label="Model view" className="flex gap-1">
        <button role="tab" aria-selected={!flat} className={`btn ${!flat ? "btn-primary" : ""}`} onClick={() => setFlat(false)}>Star schema (3 tables)</button>
        <button role="tab" aria-selected={flat} className={`btn ${flat ? "btn-primary" : ""}`} onClick={() => setFlat(true)}>Flat table (1 wide table)</button>
      </div>

      {!flat ? (
        <section className="card overflow-x-auto p-3" aria-label="Star schema diagram">
          <svg viewBox="0 0 980 260" className="min-w-[760px] w-full" role="img"
               aria-label="fact_operations in the center, joined to dim_entities by entity_id and to dim_date by record_date">
            <line x1={ENT.x + ENT.w} y1={factMid2} x2={FACT.x} y2={factMid2} stroke="var(--cat-3)" strokeWidth={2} />
            <line x1={FACT.x + FACT.w} y1={factMid} x2={DATE.x} y2={factMid} stroke="var(--cat-3)" strokeWidth={2} />
            <text x={(ENT.x + ENT.w + FACT.x) / 2} y={factMid2 - 6} fontSize={10} textAnchor="middle" fill="var(--muted)">N : 1</text>
            <text x={(FACT.x + FACT.w + DATE.x) / 2} y={factMid - 6} fontSize={10} textAnchor="middle" fill="var(--muted)">N : 1</text>
            <TableBox t={ENT} count={rows("dim_entities")} />
            <TableBox t={FACT} count={rows("fact_operations")} />
            <TableBox t={DATE} count={rows("dim_date")} />
          </svg>
          <p className="px-2 pb-1 text-xs text-muted">N : 1 means many fact rows point to one dimension row. Purple lines are foreign key joins.</p>
        </section>
      ) : (
        <section className="card p-5" aria-label="Flat table">
          <h2 className="text-lg font-semibold">v_operations_flat <span className="ml-2 text-xs font-normal text-muted">{rows("v_operations_flat")?.toLocaleString("en-US")} rows</span></h2>
          <p className="mt-1 text-sm text-muted">Facts, entity attributes and date attributes joined into one wide row per fact. This is what Tableau and Power BI prefer, and what the CSV exports contain.</p>
          <ul className="mt-3 flex flex-wrap gap-1.5">
            {flatCols.map((c) => <li key={c.name} className="rounded-md bg-panel2 px-2 py-1 font-mono text-xs">{c.name}</li>)}
          </ul>
          <p className="mt-3 text-sm"><b>Trade-off:</b> simple to query and fast to chart, but entity and date attributes repeat on every row (bigger, and changing a category means touching many rows).</p>
        </section>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card p-5" aria-label="Grain">
          <h2 className="text-lg font-semibold">Grain</h2>
          <p className="mt-2 text-sm">One row in <span className="font-mono">fact_operations</span> = <b>one operation record</b> (one entity, one day, one status). State the grain first: every measure and every join follows from it.</p>
          <h3 className="mt-4 text-sm font-semibold">Fact vs dimension</h3>
          <ul className="mt-1 list-disc space-y-1 pl-5 text-sm">
            <li><b>Fact</b>: events with numbers you add up (measures) plus keys pointing at dimensions.</li>
            <li><b>Dimension</b>: the who / what / when you slice by. Descriptive, few rows, rarely summed.</li>
            <li><b>Degenerate dimension</b>: a descriptor that lives in the fact table because it has no table of its own (<span className="font-mono">status</span>).</li>
          </ul>
        </section>
        <section className="card p-5" aria-label="Try it in SQL">
          <h2 className="text-lg font-semibold">Query the star</h2>
          <pre className="mt-2 overflow-x-auto rounded-lg bg-panel2 p-3 font-mono text-xs leading-relaxed" tabIndex={0}>{`SELECT d.year, d.quarter, e.category,
       ROUND(SUM(f.revenue), 2) AS revenue,
       ROUND(SUM(f.revenue - f.operational_cost)
             / SUM(f.revenue) * 100, 2) AS margin_pct
FROM fact_operations f
JOIN dim_entities e ON f.entity_id = e.entity_id
JOIN dim_date d     ON f.record_date = d.date_key
GROUP BY d.year, d.quarter, e.category
ORDER BY 1, 2, 3`}</pre>
          <p className="mt-2 text-sm text-muted">Fact in the middle, one JOIN per dimension, GROUP BY the attributes you want. <Link href="/lab" className="underline">Open SQL Lab</Link> and run it.</p>
        </section>
      </div>

      <section className="card overflow-x-auto" aria-label="Measure types">
        <table className="w-full min-w-[640px] text-sm">
          <caption className="p-4 text-left text-lg font-semibold">Additive, semi-additive and non-additive measures</caption>
          <thead><tr><th className="th">Measures</th><th className="th">Type</th><th className="th">How to aggregate</th><th className="th">Example</th></tr></thead>
          <tbody>
            {MEASURES.map((m) => (
              <tr key={m.type} className="border-t border-line align-top">
                <td className="px-4 py-3 font-mono text-xs">{m.name}</td>
                <td className="px-4 py-3 font-semibold">{m.type}</td>
                <td className="px-4 py-3">{m.how}</td>
                <td className="px-4 py-3 text-muted">{m.example}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </PageShell>
  );
}
