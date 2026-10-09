"use client";
import { Download } from "lucide-react";
import { useEffect, useState } from "react";
import { API_BASE, getJson } from "@/lib/api";
import type { ExportDatasets } from "@/lib/types";

const FORMAT_NOTE: Record<string, string> = {
  csv: "delimited text", tsv: "tab-delimited", json: "JSON records", xml: "XML", xlsx: "Excel workbook", parquet: "Apache Parquet",
};

export function DataFilesPanel() {
  const [info, setInfo] = useState<ExportDatasets | null>(null);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<ExportDatasets>("/api/export/datasets", ctl.signal).then(setInfo).catch(() => { /* panel just stays empty */ });
    return () => ctl.abort();
  }, []);
  if (!info) return null;
  return (
    <section className="card p-4" aria-label="Practice files">
      <h2 className="text-sm font-semibold uppercase tracking-wide">Practice files</h2>
      <p className="mt-0.5 text-xs text-muted">
        Take the data into Tableau, Excel, Python or Spark. The database file itself is locked while this app runs, so use these exports.
      </p>
      <ul className="mt-3 space-y-3">
        {info.datasets.map((d) => (
          <li key={d.id}>
            <div className="text-sm font-medium"><span className="font-mono">{d.id}</span></div>
            <div className="text-xs text-muted">{d.description}</div>
            <div className="mt-1.5 flex flex-wrap gap-1">
              {info.formats.map((f) => (
                <a key={f} className="btn !px-2 !py-0.5 text-xs" href={`${API_BASE}/api/export/${d.id}?format=${f}`} download title={FORMAT_NOTE[f] ?? f}>
                  <Download className="h-3 w-3" aria-hidden /> {f}
                </a>
              ))}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
