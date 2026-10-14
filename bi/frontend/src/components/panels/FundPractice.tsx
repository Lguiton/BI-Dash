"use client";
import { useEffect, useRef, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, errMsg } from "./kit";
import { Warn } from "./analysisKit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;

export function PracticeShell() {
  const [v, setV] = useState<R | null>(null);
  const [cmd, setCmd] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [sol, setSol] = useState<Record<string, string>>({});
  const [hist, setHist] = useState<string[]>([]);
  const [hi, setHi] = useState(-1);
  const [notice, setNotice] = useState<string | null>(null);
  const box = useRef<HTMLPreElement>(null);
  const load = () => getJson<R>("/api/itshell").then(setV).catch((e) => setErr(errMsg(e, "Couldn't load the practice shell.")));
  useEffect(() => { load(); }, []);
  useEffect(() => { if (box.current) box.current.scrollTop = box.current.scrollHeight; }, [v]);
  if (!v) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  const send = () => {
    const c = cmd.trim();
    if (!c) return;
    setErr(null); setNotice(null);
    postJson<R>("/api/itshell/run", { command: c }).then((r) => {
      setHist([...hist, c]); setHi(-1); setCmd("");
      if (r.newly_done.length) setNotice(`Task done: ${r.newly_done.map((id: string) => v.tasks.find((t: R) => t.id === id)?.title ?? id).join("; ")}`);
      load();
    }).catch((e) => setErr(errMsg(e, "That didn't work.")));
  };
  const reset = () => postJson("/api/itshell/reset", {}).then(() => { setSol({}); setNotice(null); load(); }).catch((e) => setErr(errMsg(e, "Couldn't reset.")));
  const show = (id: string) => getJson<R>(`/api/itshell/solution?task=${id}`).then((r) => setSol({ ...sol, [id]: r.command })).catch((e) => setErr(errMsg(e, "No answer.")));
  return (
    <div className="space-y-3">
      <Warn items={[v.limits]} />
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3"><Stat label="Tasks done" value={`${v.done} of ${v.total}`} /><Stat label="You are" value={v.user} /><Stat label="Folder" value={v.cwd} /></div>
      <pre ref={box} className="max-h-72 overflow-auto whitespace-pre-wrap rounded border border-line bg-panel2 p-2 font-mono text-xs" aria-label="Terminal output">{v.log.length ? v.log.join("\n") : "Type help to see the commands. Try ls, then pick a task below."}</pre>
      <form className="flex items-center gap-2" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <label className="font-mono text-xs" htmlFor="shell-in">{v.prompt}</label>
        <input id="shell-in" className="field flex-1 font-mono" autoComplete="off" autoCapitalize="off" spellCheck={false} value={cmd} onChange={(e) => setCmd(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowUp" && hist.length) { const i = hi < 0 ? hist.length - 1 : Math.max(0, hi - 1); setHi(i); setCmd(hist[i]); e.preventDefault(); }
            if (e.key === "ArrowDown" && hi >= 0) { const i = hi + 1; if (i >= hist.length) { setHi(-1); setCmd(""); } else { setHi(i); setCmd(hist[i]); } e.preventDefault(); }
          }} />
        <button type="submit" className="btn btn-primary">Run</button>
        <button type="button" className="btn" onClick={reset}>Reset</button>
      </form>
      {err && <ErrorBanner message={err} />}
      {notice && <p className="text-sm"><Badge tone="ok">done</Badge> {notice}</p>}
      <Section title="Tasks" note="Do each one in the terminal above. The hint is free; the answer is there when you are stuck.">
        <ul className="space-y-2 text-sm">
          {v.tasks.map((t: R) => (
            <li key={t.id} className="rounded border border-line p-2">
              <p>{t.done ? <Badge tone="ok">done</Badge> : <Badge tone="warn">to do</Badge>} {t.title}</p>
              {!t.done && <p className="mt-1 text-xs text-muted">Hint: {t.hint} {sol[t.id] ? <code className="ml-1 text-ink">{sol[t.id]}</code> : <button className="underline" onClick={() => show(t.id)}>Show a working command</button>}</p>}
            </li>
          ))}
        </ul>
      </Section>
      <Section title="Commands in this shell"><ul className="list-disc pl-5 font-mono text-xs">{v.help.map((h: string) => <li key={h}>{h}</li>)}</ul></Section>
    </div>
  );
}

export function Drills() {
  const [d, setD] = useState<R | null>(null);
  const [kind, setKind] = useState(""); const [n, setN] = useState("10");
  const [ans, setAns] = useState<Record<string, string>>({});
  const [g, setG] = useState<R | null>(null);
  const [prog, setProg] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const loadProg = () => getJson<R>("/api/itdrills/progress").then(setProg).catch(() => setProg(null));
  useEffect(() => { loadProg(); }, []);
  const start = () => { setErr(null); setG(null); setAns({}); getJson<R>(`/api/itdrills?kind=${kind}&n=${Number(n) || 10}`).then(setD).catch((e) => setErr(errMsg(e, "Couldn't load drills."))); };
  const grade = () => postJson<R>("/api/itdrills/grade", { answers: Object.fromEntries(Object.entries(ans).filter(([, v]) => v.trim() !== "")) }).then((r) => { setG(r); loadProg(); }).catch((e) => setErr(errMsg(e, "Couldn't grade.")));
  const reset = () => deleteJson("/api/itdrills/results").then(loadProg).catch((e) => setErr(errMsg(e, "Couldn't reset.")));
  const by: R = {}; (g?.results || []).forEach((r: R) => { by[r.id] = r; });
  const kinds: R[] = d?.kinds || prog?.rows?.map((r: R) => ({ id: r.kind, label: r.label })) || [];
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-4">
        <Field label="Kind"><select className="field" value={kind} onChange={(e) => setKind(e.target.value)}><option value="">Mixed</option>{kinds.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select></Field>
        <Field label="Questions"><input className="field" inputMode="numeric" value={n} onChange={(e) => setN(e.target.value)} /></Field>
        <div className="flex items-end gap-2"><button className="btn btn-primary" onClick={start}>New drill</button><button className="btn" onClick={reset}>Reset scores</button></div>
      </div>
      {err && <ErrorBanner message={err} />}
      {d && <p className="text-xs text-muted">{d.tips}</p>}
      {d?.questions.map((q: R, i: number) => {
        const r = by[q.id];
        return (
          <div key={q.id} className="rounded border border-line p-2 text-sm">
            <label htmlFor={`dq-${q.id}`}>{i + 1}. {q.prompt}</label>
            <div className="mt-1 flex items-center gap-2">
              <input id={`dq-${q.id}`} className="field max-w-xs font-mono" autoComplete="off" disabled={!!g} value={ans[q.id] || ""} onChange={(e) => setAns({ ...ans, [q.id]: e.target.value })} />
              {r && (r.ok ? <Badge tone="ok">right</Badge> : <Badge tone="bad">answer: {r.answer}</Badge>)}
            </div>
            {r && <p className="mt-1 text-xs text-muted">{r.why}</p>}
          </div>
        );
      })}
      {d && !g && <button className="btn btn-primary" disabled={Object.values(ans).every((x) => !x.trim())} onClick={grade}>Grade</button>}
      {g && <p className="text-sm"><b>{g.right} of {g.total} ({g.pct}%).</b> {g.message}</p>}
      {prog && <Section title="Your scores by kind"><Table head={["Kind", "Answered", "Correct"]} rows={prog.rows.map((r: R) => [r.label, r.answered, r.pct === null ? "no answers yet" : `${r.pct}%`])} /></Section>}
    </div>
  );
}
