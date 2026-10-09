"use client";
import { FileSpreadsheet, FileText } from "lucide-react";
import { useState } from "react";
import { API_BASE, filterQuery } from "@/lib/api";
import type { FilterState } from "@/lib/types";

/** Downloads a report of the current filtered view. Uses fetch so a "nothing to report" error shows as text, not a broken file. */
export function ReportButtons({ filters }: { filters: FilterState }) {
  const [busy, setBusy] = useState<"xlsx" | "pdf" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function download(format: "xlsx" | "pdf") {
    setBusy(format); setError(null);
    try {
      const res = await fetch(`${API_BASE}/api/report${filterQuery(filters, { format })}`);
      if (!res.ok) {
        let msg = `Report failed (${res.status}).`;
        try { const b = await res.json(); if (typeof b?.detail === "string") msg = b.detail; } catch { /* keep generic message */ }
        throw new Error(msg);
      }
      const url = URL.createObjectURL(await res.blob());
      const a = document.createElement("a");
      a.href = url; a.download = `bi_report.${format}`; document.body.appendChild(a); a.click(); a.remove();
      URL.revokeObjectURL(url);
    } catch (e) {
      setError(e instanceof TypeError ? `Can't reach the analytics API at ${API_BASE}.` : (e as Error).message);
    } finally { setBusy(null); }
  }

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button className="btn" onClick={() => download("xlsx")} disabled={busy !== null} title="Excel workbook: summary, by entity, daily, insights">
        <FileSpreadsheet className="h-4 w-4" aria-hidden /> {busy === "xlsx" ? "Building…" : "Report (Excel)"}
      </button>
      <button className="btn" onClick={() => download("pdf")} disabled={busy !== null} title="Printable PDF summary of the current view">
        <FileText className="h-4 w-4" aria-hidden /> {busy === "pdf" ? "Building…" : "Report (PDF)"}
      </button>
      {error && <span role="alert" className="text-xs" style={{ color: "var(--bad)" }}>{error}</span>}
    </div>
  );
}
