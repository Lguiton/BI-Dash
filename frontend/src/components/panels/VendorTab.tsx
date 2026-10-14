"use client";
import { useEffect, useState } from "react";
import { getJson, postJson } from "@/lib/api";
import { Badge, Table, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;

export function VendorTab() {
  const [qs, setQs] = useState<R[]>([]);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [extra, setExtra] = useState(true);
  const [res, setRes] = useState<R | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => { getJson<R>("/api/aiimpl/vendor/reference").then((r) => setQs(r.questions)).catch((e) => setErr(errMsg(e, "Failed."))); }, []);
  const run = async () => { setErr(""); try { setRes(await postJson<R>("/api/aiimpl/vendor/score", { answers: ans, include_extra: extra })); } catch (e) { setErr(errMsg(e, "Failed.")); } };
  const load = async () => { const s = await getJson<R>("/api/aiimpl/vendor/sample"); setAns(Object.values(s.vendors)[0] as Record<string, string>); };
  const shown = qs.filter((q) => extra || !q.extra);
  return (
    <div>
      <p className="text-sm text-gray-600 mb-2">Answer from what the vendor showed or put in writing. Leave &quot;unknown&quot; if you have not asked: unknown is not yes. Questions marked MUST must be a confirmed yes.</p>
      <div className="flex gap-2 mb-2 items-center"><button className="btn" onClick={load}>Load sample</button><label className="text-sm"><input type="checkbox" checked={extra} onChange={(e) => setExtra(e.target.checked)} /> Include the 7 extra questions the checklist leaves out</label></div>
      <div className="space-y-1">
        {shown.map((q) => (
          <div key={q.id} className="flex items-center gap-2 text-sm">
            <select className="field w-28" aria-label={q.question} value={ans[q.id] ?? "unknown"} onChange={(e) => setAns({ ...ans, [q.id]: e.target.value })}><option>unknown</option><option>yes</option><option>no</option></select>
            <span>{q.gate && <Badge tone="warn">MUST</Badge>} {q.extra && <Badge tone="muted">extra</Badge>} <span className="text-gray-500">{q.section}:</span> {q.question}</span>
          </div>
        ))}
      </div>
      <button className="btn mt-3" onClick={run}>Score this vendor</button>
      {err && <p role="alert" className="text-red-600 text-sm mt-2">{err}</p>}
      {res && (
        <div className="mt-3 text-sm">
          <p className="font-medium">{res.verdict}</p>
          <p>Original checklist: {res.original_score} / {res.original_out_of} ({res.original_band}). Weighted: {res.weighted_pct}%. No: {res.no_count}. Unknown: {res.unknown_count}.</p>
          <Table head={["Section", "Yes", "Of"]} rows={res.by_section.map((s: R) => [s.section, s.yes, s.of])} />
          {res.gate_failures.length > 0 && <ul className="list-disc pl-5 mt-2">{res.gate_failures.map((g: R) => <li key={g.id}>{g.question} ({g.answer})</li>)}</ul>}
          <p className="mt-2 italic">{res.lesson}</p>
        </div>
      )}
    </div>
  );
}
