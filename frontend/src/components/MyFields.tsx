"use client";
import { FIELD_GROUPS } from "@/lib/fieldMenu";
import { useMode, useMyFields } from "@/lib/mode";

/** Pick the fields you sell. The Fields menu then shows only those. Nothing is deleted: untick nothing (or press Show all) to see every field again. */
export function MyFields() {
  const [mine, setMine] = useMyFields();
  const [mode, setMode] = useMode();
  const all = mine.length === 0;
  const toggle = (id: string, on: boolean) => {
    const base = all ? FIELD_GROUPS.flatMap((g) => g.items.map((i) => i.id)) : mine;
    const next = on ? [...new Set([...base, id])] : base.filter((x) => x !== id);
    if (next.length === 0) return; // keep at least one field ticked; use Show all to reset
    setMine(next);
  };
  return (
    <section id="my-fields" className="card space-y-3 p-5" aria-label="My fields">
      <h2 className="text-sm font-semibold">Mode and my fields</h2>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span>Mode:</span>
        <button className={`btn ${mode === "work" ? "btn-primary" : ""}`} onClick={() => setMode("work")} aria-pressed={mode === "work"}>Work</button>
        <button className={`btn ${mode === "learn" ? "btn-primary" : ""}`} onClick={() => setMode("learn")} aria-pressed={mode === "learn"}>Learn</button>
        <span className="text-xs text-muted">Work hides every learning page. Nothing is deleted.</span>
      </div>
      <p className="text-sm text-muted">Tick the fields you sell. The Fields menu then shows only those. {all ? "Right now every field shows." : `Showing ${mine.length} field${mine.length === 1 ? "" : "s"}.`}</p>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {FIELD_GROUPS.map((g) => (
          <fieldset key={g.id} className="space-y-1">
            <legend className="text-xs font-semibold uppercase tracking-wide text-muted">{g.label}</legend>
            {g.items.map((i) => (
              <label key={i.id} className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={all || mine.includes(i.id)} onChange={(e) => toggle(i.id, e.target.checked)} />
                {i.label}
              </label>
            ))}
          </fieldset>
        ))}
      </div>
      <button className="btn" onClick={() => setMine([])} disabled={all}>Show all fields</button>
    </section>
  );
}
