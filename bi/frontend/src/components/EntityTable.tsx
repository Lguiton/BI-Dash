"use client";
import { money, num, pct, signed } from "@/lib/format";
import type { EntityRow } from "@/lib/types";

interface Props {
  rows: EntityRow[];
  selectedId: string;
  onSelect: (id: string) => void;
}

export function EntityTable({ rows, selectedId, onSelect }: Props) {
  return (
    <section className="card overflow-hidden" aria-label="Entity performance">
      <div className="border-b border-line px-5 py-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide">Entity performance</h2>
        <p className="mt-0.5 text-xs text-muted">
          Select a row to filter everything below to that entity. “Cost vs budget” compares average cost per record with the entity’s baseline target (a cost budget). Red means over budget.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-panel2"><tr>
            <th className="th">Entity</th><th className="th">Category</th>
            <th className="th text-right">Records</th><th className="th text-right">Units</th>
            <th className="th text-right">Revenue</th><th className="th text-right">Profit</th>
            <th className="th text-right">Margin</th><th className="th text-right">Cost vs budget</th>
          </tr></thead>
          <tbody className="divide-y divide-line">
            {rows.length === 0 && (
              <tr><td className="td text-muted" colSpan={8}>No data for this selection.</td></tr>
            )}
            {rows.map((r) => {
              const sel = r.entity_id === selectedId;
              return (
                <tr key={r.entity_id} aria-selected={sel} className={`cursor-pointer hover:bg-panel2 ${sel ? "bg-panel2" : ""}`}
                    onClick={() => onSelect(sel ? "" : r.entity_id)}>
                  <td className="td font-medium">
                    <button className="text-left font-medium underline-offset-2 hover:underline" aria-pressed={sel}
                            onClick={(e) => { e.stopPropagation(); onSelect(sel ? "" : r.entity_id); }}>
                      {r.entity_name}
                    </button>
                  </td>
                  <td className="td text-muted">{r.category}</td>
                  <td className="td text-right tabular-nums">{num(r.records)}</td>
                  <td className="td text-right tabular-nums">{num(r.volume)}</td>
                  <td className="td text-right font-mono">{money(r.revenue)}</td>
                  <td className="td text-right font-mono" style={{ color: r.profit >= 0 ? "var(--good)" : "var(--bad)" }}>{money(r.profit)}</td>
                  <td className="td text-right tabular-nums">{pct(r.margin_pct)}</td>
                  <td className="td text-right tabular-nums"
                      style={{ color: r.vs_baseline_pct == null || r.vs_baseline_pct === 0 ? "var(--muted)" : r.vs_baseline_pct > 0 ? "var(--bad)" : "var(--good)" }}>
                    {r.vs_baseline_pct == null ? "—" : `${signed(r.vs_baseline_pct)}%`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </section>
  );
}
