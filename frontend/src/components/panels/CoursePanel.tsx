"use client";
import { useCallback, useEffect, useState } from "react";
import { getJson, putJson } from "@/lib/api";
import { Badge, Section, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;

export function CoursePanel() {
  const [cat, setCat] = useState<R | null>(null);
  const [ref, setRef] = useState<R | null>(null);
  const [goal, setGoal] = useState("");
  const [path, setPath] = useState<R | null>(null);
  const [q, setQ] = useState("");
  const [err, setErr] = useState("");
  const load = useCallback(() => { getJson<R>(`/api/courses?q=${encodeURIComponent(q)}`).then(setCat).catch((e) => setErr(errMsg(e, "Could not load courses."))); }, [q]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { getJson<R>("/api/courses/reference").then(setRef).catch(() => setRef(null)); }, []);
  useEffect(() => { if (goal) getJson<R>(`/api/courses/path/${goal}`).then(setPath).catch((e) => setErr(errMsg(e, "Could not load the path."))); }, [goal, cat?.done_count]);
  const tick = (id: number, done: boolean) => { setErr(""); putJson<R>(`/api/courses/${id}`, { done }).then(load).catch((e) => setErr(errMsg(e, "Could not save."))); };
  return (
    <Section title="Free AI course catalog" note="The list as published, with its mistakes marked. This app cannot check that a course is still free or open today: look at the course page first.">
      <div className="flex flex-wrap gap-2 mb-2 items-center">
        <input className="field" aria-label="Search courses" placeholder="Search title or provider" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="field" aria-label="Suggested path" value={goal} onChange={(e) => setGoal(e.target.value)}>
          <option value="">Suggested path...</option>
          {ref && Object.entries(ref.paths).map(([k, v]) => <option key={k} value={k}>{String(v)}</option>)}
        </select>
        {cat && <span className="text-sm text-gray-600">{cat.done_count} done</span>}
      </div>
      {err && <p role="alert" className="text-red-600 text-sm">{err}</p>}
      {goal && path && (
        <div className="mb-3 text-sm"><p className="font-medium">{path.title}</p><ol className="list-decimal pl-5">{path.steps.map((s: R) => <li key={s.id}>{s.done ? "✓ " : ""}{s.title} <span className="text-gray-500">({s.provider})</span></li>)}</ol><p className="italic">{path.caution}</p></div>
      )}
      {cat && (
        <ul className="text-sm space-y-1 max-h-96 overflow-y-auto">
          {cat.courses.map((c: R) => (
            <li key={c.id}><label className="flex gap-2 items-start"><input type="checkbox" checked={c.done} onChange={(e) => tick(c.id, e.target.checked)} aria-label={`Done: ${c.title}`} />
              <span>{c.id}. {c.title} <span className="text-gray-500">({c.provider}; {c.section_name})</span> <Badge tone={c.free_status === "usually free" ? "ok" : "warn"}>{c.free_status}</Badge>{c.note && <span className="block text-gray-500">{c.note}</span>}</span></label></li>
          ))}
        </ul>
      )}
      {ref && <details className="mt-3 text-sm"><summary className="cursor-pointer">Mistakes in the source list</summary><ul className="list-disc pl-5">{ref.slips.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></details>}
    </Section>
  );
}
