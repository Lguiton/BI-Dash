"use client";
import { useEffect, useState } from "react";
import { getJson, postJson } from "@/lib/api";
import { Section, Table, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;

export function LeadPanel() {
  const [ref, setRef] = useState<R | null>(null);
  const [r, setR] = useState<Record<string, number[]>>({});
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJson<R>("/api/leadership/reference").then(setRef).catch((e) => setErr(errMsg(e, "Could not load."))); }, []);
  if (!ref) return err ? <p role="alert" className="text-red-600 text-sm">{err}</p> : null;
  const set = (id: string, i: number, v: number) => setR({ ...r, [id]: Object.assign([3, 3, 3], r[id] ?? [], { [i]: v }) });
  const run = () => { setErr(""); postJson<R>("/api/leadership/review", { ratings: r }).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "Could not score.")); }); };
  return (
    <Section title="Five leadership disciplines: self-review" note="A common framework summary, not an official Harvard Business School publication. Rate each behaviour 1 (rarely) to 5 (always), and back each rating with a real example.">
      {ref.framework.map((d: R) => (
        <div key={d.id} className="mb-2 text-sm">
          <p className="font-medium">{d.name}</p>
          {d.behaviours.map((b: string, i: number) => (
            <label key={b} className="flex gap-2 items-center">
              <select className="field w-16" aria-label={b} value={(r[d.id] ?? [3, 3, 3])[i]} onChange={(e) => set(d.id, i, Number(e.target.value))}>{[1, 2, 3, 4, 5].map((x) => <option key={x}>{x}</option>)}</select>{b}
            </label>
          ))}
        </div>
      ))}
      <button className="btn" onClick={run}>Find my weakest discipline</button>
      {err && <p role="alert" className="text-red-600 text-sm mt-2">{err}</p>}
      {res && (
        <div className="mt-3 text-sm">
          <Table head={["Discipline", "Average", "Weakest behaviour"]} rows={res.ranked_weakest_first.map((d: R) => [d.name, d.average, d.weakest_behaviour])} />
          <p className="mt-2"><b>Start with:</b> {res.focus_first.practice}</p>
          <p className="italic">{res.note}</p>
        </div>
      )}
      <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes in the source infographic</summary><ul className="list-disc pl-5">{ref.slips.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></details>
    </Section>
  );
}
