"use client";
import type { SqlResult } from "@/lib/types";

type Cell = SqlResult["rows"][number][number];

function show(v: Cell): string {
  if (v === null) return "NULL";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("en-US") : v.toLocaleString("en-US", { maximumFractionDigits: 4 });
  return String(v);
}

export function ResultTable({ columns, rows, caption }: { columns: string[]; rows: SqlResult["rows"]; caption?: string }) {
  return (
    <div className="max-h-96 overflow-auto rounded-lg border border-line">
      <table className="w-full text-sm">
        {caption && <caption className="sr-only">{caption}</caption>}
        <thead className="sticky top-0 bg-panel2">
          <tr>{columns.map((c, i) => <th key={`${c}-${i}`} className="th">{c}</th>)}</tr>
        </thead>
        <tbody className="divide-y divide-line">
          {rows.length === 0 && <tr><td className="td text-muted" colSpan={Math.max(columns.length, 1)}>0 rows</td></tr>}
          {rows.map((r, ri) => (
            <tr key={ri} className="hover:bg-panel2">
              {r.map((v, ci) => (
                <td key={ci} className={`td font-mono ${typeof v === "number" ? "text-right tabular-nums" : ""} ${v === null ? "italic text-muted" : ""}`}>{show(v)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
