"use client";
import { Save, Trash2 } from "lucide-react";
import { useState } from "react";
import { useStoredJson } from "@/lib/useStoredJson";

interface Saved { id: string; name: string; sql: string }
const MAX = 30;

export function SavedQueries({ sql, onLoad }: { sql: string; onLoad: (sql: string) => void }) {
  const [items, setItems] = useStoredJson<Saved[]>("bi-saved-queries", []);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState<string | null>(null);

  function save() {
    const n = name.trim();
    if (!n || !sql.trim()) return;
    const existing = items.find((i) => i.name.toLowerCase() === n.toLowerCase());
    if (!existing && items.length >= MAX) { setMsg(`Limit of ${MAX} saved queries. Delete one first.`); return; }
    const entry: Saved = { id: existing?.id ?? `${items.length}-${n}`, name: n, sql };
    setItems(existing ? items.map((i) => (i.id === existing.id ? entry : i)) : [...items, entry]);
    setMsg(existing ? `Updated "${n}".` : `Saved "${n}".`);
    setName("");
  }

  return (
    <section className="card p-4" aria-label="Saved queries">
      <h2 className="text-sm font-semibold uppercase tracking-wide">Saved queries</h2>
      <p className="mt-0.5 text-xs text-muted">Kept in this browser only.</p>
      <form className="mt-3 flex gap-2" onSubmit={(e) => { e.preventDefault(); save(); }}>
        <input className="field min-w-0 flex-1" value={name} onChange={(e) => { setName(e.target.value); setMsg(null); }} placeholder="Name this query" maxLength={40} aria-label="Query name" />
        <button className="btn" disabled={!name.trim() || !sql.trim()} aria-label="Save the current query"><Save className="h-4 w-4" aria-hidden /> Save</button>
      </form>
      {msg && <p role="status" className="mt-2 text-xs text-muted">{msg}</p>}
      {items.length === 0 ? (
        <p className="mt-3 text-sm text-muted">Nothing saved yet. Write a query, name it, save it.</p>
      ) : (
        <ul className="mt-3 space-y-1">
          {items.map((i) => (
            <li key={i.id} className="flex items-center gap-1">
              <button className="flex-1 truncate rounded-md px-2 py-1.5 text-left text-sm hover:bg-panel2" onClick={() => onLoad(i.sql)} title={i.sql}>{i.name}</button>
              <button className="btn !px-1.5 !py-1" aria-label={`Delete ${i.name}`} onClick={() => setItems(items.filter((x) => x.id !== i.id))}><Trash2 className="h-3.5 w-3.5" aria-hidden /></button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
