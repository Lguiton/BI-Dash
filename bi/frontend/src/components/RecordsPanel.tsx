"use client";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Download } from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE, ApiError, filterQuery, getJson } from "@/lib/api";
import { money, num } from "@/lib/format";
import type { FilterState, RecordsPage } from "@/lib/types";
import { ErrorBanner } from "./ErrorBanner";

const PAGE = 25;
const COLS: { key: string; label: string; right?: boolean }[] = [
  { key: "record_date", label: "Date" },
  { key: "entity_name", label: "Entity" },
  { key: "revenue", label: "Revenue", right: true },
  { key: "operational_cost", label: "Cost", right: true },
  { key: "profit", label: "Profit", right: true },
  { key: "units_processed", label: "Units", right: true },
  { key: "status", label: "Status" },
];

export function RecordsPanel({ filters, refreshKey }: { filters: FilterState; refreshKey: number }) {
  const [result, setResult] = useState<{ key: string; page?: RecordsPage; error?: string } | null>(null);
  const [offset, setOffset] = useState(0);
  const [sort, setSort] = useState("record_date");
  const [order, setOrder] = useState<"asc" | "desc">("desc");
  const [retry, setRetry] = useState(0);
  const filterKey = JSON.stringify(filters);

  // Changing the filters sends you back to the first page. Done during render
  // (React's documented "reset state on prop change" pattern), not in an effect.
  const [seenFilterKey, setSeenFilterKey] = useState(filterKey);
  if (seenFilterKey !== filterKey) {
    setSeenFilterKey(filterKey);
    setOffset(0);
  }

  const query = `/api/analytics/records${filterQuery(filters, { limit: PAGE, offset, sort, order })}`;
  const requestKey = `${query}|${refreshKey}|${retry}`;

  useEffect(() => {
    const ctl = new AbortController();
    getJson<RecordsPage>(query, ctl.signal)
      .then((page) => setResult({ key: requestKey, page }))
      .catch((e) => {
        if (!ctl.signal.aborted) setResult({ key: requestKey, error: e instanceof ApiError ? e.message : "Couldn't load records." });
      });
    return () => ctl.abort();
  }, [query, requestKey]);

  const page = result?.page ?? null; // keep showing the last page while the next one loads
  const error = result?.key === requestKey ? result.error ?? null : null;

  const toggleSort = (key: string) => {
    if (key === sort) setOrder(order === "asc" ? "desc" : "asc");
    else { setSort(key); setOrder(key === "record_date" || key === "entity_name" || key === "status" ? "asc" : "desc"); }
    setOffset(0);
  };

  const total = page?.total ?? 0;
  const from = total ? offset + 1 : 0;
  const to = Math.min(offset + PAGE, total);

  return (
    <section className="card overflow-hidden" aria-label="Records">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wide">Records</h2>
          <p className="mt-0.5 text-xs text-muted">Every row behind the numbers above, for the current filters.</p>
        </div>
        <a className="btn" href={`${API_BASE}/api/analytics/records/export${filterQuery(filters)}`} download>
          <Download className="h-4 w-4" aria-hidden /> Export CSV
        </a>
      </div>
      {error && <div className="p-4"><ErrorBanner message={error} onRetry={() => setRetry((n) => n + 1)} /></div>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-panel2"><tr>
            {COLS.map((c) => (
              <th key={c.key} className={`th ${c.right ? "text-right" : ""}`} aria-sort={sort === c.key ? (order === "asc" ? "ascending" : "descending") : "none"}>
                <button className="inline-flex items-center gap-1 uppercase" onClick={() => toggleSort(c.key)}>
                  {c.label}
                  {sort === c.key && (order === "asc" ? <ArrowUp className="h-3 w-3" aria-hidden /> : <ArrowDown className="h-3 w-3" aria-hidden />)}
                </button>
              </th>
            ))}
          </tr></thead>
          <tbody className="divide-y divide-line">
            {page && page.rows.length === 0 && <tr><td className="td text-muted" colSpan={COLS.length}>No records match.</td></tr>}
            {page?.rows.map((r) => (
              <tr key={r.fact_id} className="hover:bg-panel2">
                <td className="td tabular-nums">{r.record_date}</td>
                <td className="td">{r.entity_name}</td>
                <td className="td text-right font-mono">{money(r.revenue)}</td>
                <td className="td text-right font-mono">{money(r.operational_cost)}</td>
                <td className="td text-right font-mono" style={{ color: r.profit >= 0 ? "var(--good)" : "var(--bad)" }}>{money(r.profit)}</td>
                <td className="td text-right tabular-nums">{num(r.units_processed)}</td>
                <td className="td text-muted">{r.status ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="flex items-center justify-between border-t border-line px-5 py-3 text-xs text-muted">
        <span>{total ? `${from}–${to} of ${num(total)}` : "0 records"}</span>
        <div className="flex gap-1">
          <button className="btn" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></button>
          <button className="btn" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></button>
        </div>
      </div>
    </section>
  );
}
