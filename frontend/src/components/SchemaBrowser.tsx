"use client";
import { ChevronDown, ChevronRight, Eye, Table2 } from "lucide-react";
import { useState } from "react";
import type { SchemaObject } from "@/lib/types";

export function SchemaBrowser({ objects, onInsert }: { objects: SchemaObject[]; onInsert: (text: string) => void }) {
  const [open, setOpen] = useState<Record<string, boolean>>({ fact_operations: true });
  return (
    <section className="card p-4" aria-label="Schema browser">
      <h2 className="text-sm font-semibold uppercase tracking-wide">Schema</h2>
      <p className="mt-0.5 text-xs text-muted">Click a name to insert it into your query.</p>
      <ul className="mt-3 space-y-1">
        {objects.map((o) => {
          const isOpen = !!open[o.name];
          return (
            <li key={o.name}>
              <div className="flex items-center gap-1">
                <button className="btn !px-1.5 !py-1" aria-expanded={isOpen} aria-label={`${isOpen ? "Collapse" : "Expand"} ${o.name}`}
                        onClick={() => setOpen({ ...open, [o.name]: !isOpen })}>
                  {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
                </button>
                <button className="flex min-w-0 flex-1 items-center gap-1.5 text-left text-sm font-medium hover:underline" onClick={() => onInsert(o.name)}>
                  {o.kind === "view" ? <Eye className="h-3.5 w-3.5 shrink-0 text-muted" aria-label="view" /> : <Table2 className="h-3.5 w-3.5 shrink-0 text-accent" aria-label="table" />}
                  <span className="truncate font-mono">{o.name}</span>
                </button>
                <span className="shrink-0 text-xs text-muted">{o.row_count.toLocaleString("en-US")}</span>
              </div>
              {isOpen && (
                <ul className="ml-8 mt-1 space-y-0.5 border-l border-line pl-3">
                  {o.columns.map((c) => (
                    <li key={c.name} className="flex justify-between gap-2 text-xs">
                      <button className="truncate font-mono hover:underline" onClick={() => onInsert(c.name)}>{c.name}</button>
                      <span className="shrink-0 text-muted">{c.type.toLowerCase()}</span>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
