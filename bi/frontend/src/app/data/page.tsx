"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { PacksCard } from "@/components/DataExtras";
import { ImportPanel } from "@/components/data/ImportPanel";
import { TableExplorer } from "@/components/data/TableExplorer";
import { ApiError, getJson } from "@/lib/api";
import { num } from "@/lib/format";
import type { UserTable } from "@/lib/types";

export default function DataPage() {
  const [tables, setTables] = useState<UserTable[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<string | null>(null);

  const load = useCallback((signal?: AbortSignal) => {
    getJson<{ tables: UserTable[] }>("/api/data/tables", signal)
      .then((r) => { setTables(r.tables); setError(null); setPicked((p) => (p && r.tables.some((t) => t.table_name === p) ? p : r.tables[0]?.table_name ?? null)); })
      .catch((e) => { if (!signal?.aborted) setError(e instanceof ApiError ? e.message : "Could not load your tables."); });
  }, []);
  useEffect(() => { const ctl = new AbortController(); load(ctl.signal); return () => ctl.abort(); }, [load]);

  const table = tables?.find((t) => t.table_name === picked);
  return (
    <PageShell title="My data" subtitle="Bring in any spreadsheet or export, look at it, chart it. Nothing leaves this computer.">
      {error && <ErrorBanner message={error} onRetry={() => load()} />}
      <ImportPanel onLoaded={() => load()} />
      <PacksCard onLoaded={() => load()} />
      <section aria-label="Your tables" className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide text-muted">Your tables</h2>
        {tables && tables.length === 0 && <p className="card p-5 text-sm text-muted">Nothing here yet. Import a file above and it shows up as a table you can chart.</p>}
        {tables && tables.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {tables.map((t) => (
              <button key={t.table_name} className={`btn ${t.table_name === picked ? "btn-primary" : ""}`} aria-pressed={t.table_name === picked} onClick={() => setPicked(t.table_name)}>
                {t.table_name} <span className="opacity-70">· {num(t.rows_count)}</span>
              </button>
            ))}
          </div>
        )}
        {table && <TableExplorer key={table.table_name} table={table} onChanged={() => load()} />}
      </section>
    </PageShell>
  );
}
