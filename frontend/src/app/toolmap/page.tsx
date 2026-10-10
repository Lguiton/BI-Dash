"use client";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Badge, Section, errMsg } from "@/components/panels/kit";
import { getJson } from "@/lib/api";

interface Tool { tool: string; status: string; where: string; note: string; href: string | null }
interface Map { categories: { category: string; tools: Tool[] }[]; counts: Record<string, number>; legend: Record<string, string> }
const LABEL: Record<string, string> = { built: "Built", partial: "Partly built", taught: "Taught, not built", not_embedded: "Not embedded" };
const TONE: Record<string, "ok" | "warn" | "muted" | "bad"> = { built: "ok", partial: "warn", taught: "muted", not_embedded: "bad" };

export default function ToolMapPage() {
  const [m, setM] = useState<Map | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [f, setF] = useState("");
  const [q, setQ] = useState("");
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Map>("/api/toolmap", ctl.signal).then(setM).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load the tool map.")); });
    return () => ctl.abort();
  }, []);
  const cats = useMemo(() => (m?.categories ?? []).map((c) => ({ ...c, tools: c.tools.filter((t) => (!f || t.status === f) && (!q || `${t.tool} ${t.note} ${t.where}`.toLowerCase().includes(q.toLowerCase()))) })).filter((c) => c.tools.length), [m, f, q]);
  return (
    <PageShell title="Tool map" subtitle="The tools people name in job ads: what this app has, what it stands in for, and what it deliberately doesn't embed.">
      {err && <ErrorBanner message={err} />}
      {!m && !err && <p className="text-sm text-muted">Loading…</p>}
      {m && (
        <>
          <div className="flex flex-wrap items-center gap-2">
            {Object.keys(LABEL).map((k) => <button key={k} className={`btn ${f === k ? "btn-primary" : ""}`} aria-pressed={f === k} onClick={() => setF(f === k ? "" : k)}>{LABEL[k]} ({m.counts[k] ?? 0})</button>)}
            <input className="field ml-auto w-56 max-w-full" aria-label="Search tools" placeholder="Search tools…" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <p className="text-xs text-muted">{Object.entries(m.legend).map(([k, v]) => `${LABEL[k]}: ${v}`).join(" · ")}</p>
          {cats.length === 0 && <p className="text-sm text-muted">No tools match.</p>}
          {cats.map((c) => (
            <Section key={c.category} title={c.category}>
              <ul className="divide-y divide-line">{c.tools.map((t) => (
                <li key={t.tool} className="flex flex-wrap items-start gap-2 py-2 text-sm">
                  <Badge tone={TONE[t.status]}>{LABEL[t.status]}</Badge>
                  <div className="min-w-0 flex-1"><b>{t.tool}</b><p className="text-xs text-muted">{t.note}</p>{t.where !== "-" && <p className="text-xs">In this app: {t.href ? <Link className="underline" href={t.href}>{t.where}</Link> : t.where}</p>}</div>
                </li>
              ))}</ul>
            </Section>
          ))}
        </>
      )}
    </PageShell>
  );
}
