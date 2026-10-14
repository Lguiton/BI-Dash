"use client";
import { GitBranch } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ApiError, getJson } from "@/lib/api";

interface L {
  kpi: { name: string; formula: string }; tables: string[]; columns: { table: string; column: string }[];
  workflows: { id: number; name: string }[]; rules: { id: number; table: string; text: string }[];
  pipelines: { id: number; name: string; because: string[] }[]; sources: { id: number; name: string; kind: string }[]; note: string;
}

/** Click a KPI and see what feeds it: tables and columns, plus your workflows, rules, pipelines and sources that touch them. */
export function LineageButton({ kpiId }: { kpiId: string }) {
  const [l, setL] = useState<L | null>(null);
  const [open, setOpen] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function toggle() {
    if (open) { setOpen(false); return; }
    setOpen(true); setErr(null);
    try { setL(await getJson<L>(`/api/lineage/kpi/${kpiId}`)); } catch (e) { setErr(e instanceof ApiError ? e.message : "Couldn't load the lineage."); }
  }
  return (
    <div className="mt-1">
      <button className="btn !px-2 !py-1 text-xs" onClick={toggle} aria-expanded={open}><GitBranch className="h-3.5 w-3.5" aria-hidden /> Where does this come from?</button>
      {open && (
        <div className="mt-2 space-y-2 rounded-md border border-line p-3 text-xs">
          {err && <p role="alert" style={{ color: "var(--bad)" }}>{err}</p>}
          {l && (
            <>
              <p><b>Formula:</b> <code className="break-all">{l.kpi.formula}</code></p>
              <p><b>Reads:</b> {l.columns.map((c) => `${c.table}.${c.column}`).join(", ")}</p>
              <List title="Quality rules on those tables" empty="None yet. Add one on the Data quality page." href="/quality" items={l.rules.map((r) => `${r.table}: ${r.text}`)} />
              <List title="Your workflows that read them" empty="None." href="/workflow" items={l.workflows.map((w) => w.name)} />
              <List title="Pipelines involved" empty="None." href="/pipelines" items={l.pipelines.map((p) => `${p.name} (${p.because.join(", ")})`)} />
              <List title="Sources that load them" empty="None." href="/sources" items={l.sources.map((s) => `${s.name} (${s.kind})`)} />
              <p className="text-muted">{l.note}</p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function List({ title, items, empty, href }: { title: string; items: string[]; empty: string; href: string }) {
  return (
    <div><b>{title}:</b>{" "}
      {items.length === 0 ? <span className="text-muted">{empty}</span> : <Link href={href} className="underline">{items.join("; ")}</Link>}
    </div>
  );
}
