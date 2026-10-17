"use client";
import { useEffect, useState } from "react";
import { Badge, errMsg } from "@/components/panels/kit";
import { getJson, postJson, putJson } from "@/lib/api";

type Res = { text: string; status?: string; at: string; steps?: number; failed?: string[]; judge_notes?: string; model?: string };

/** One click: the field's agent drafts the work for every open step. A draft only; it never marks anything done or sends anything. */
export function AgentWork({ jobId }: { jobId: number }) {
  const [res, setRes] = useState<Res | null>(null);
  const [tick, setTick] = useState(0);
  const [ins, setIns] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const key = `auto:${jobId}`;
  useEffect(() => {
    let live = true;
    getJson<{ drafts: Record<string, Res> }>("/api/auto/prep/drafts").then((r) => { if (live) setRes(r.drafts[key] ?? null); }).catch(() => {});
    return () => { live = false; };
  }, [key, tick]);
  const run = async () => {
    setBusy(true); setErr(null);
    try { await postJson(`/api/jobs/${jobId}/auto`, { instructions: ins }); setTick((t) => t + 1); }
    catch (e) { setErr(errMsg(e, "The agent didn't finish.")); }
    setBusy(false);
  };
  const decide = async (status: "accepted" | "discarded") => {
    try { await putJson(`/api/auto/prep/drafts/${encodeURIComponent(key)}`, { status }); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Couldn't save that.")); }
  };
  const copy = async () => { if (!res) return; try { await navigator.clipboard.writeText(res.text); setDone(true); setTimeout(() => setDone(false), 2000); } catch { /* select the text instead */ } };
  return (
    <section className="space-y-2 rounded border border-line p-3" aria-label="Agent works this job">
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn btn-primary" disabled={busy} onClick={run}>{busy ? "Agent working… (about a minute)" : res ? "Run the agent again" : "Have the agent work this job"}</button>
        <span className="text-xs text-muted">The job&apos;s agent drafts the work for each open step. You check it. It never marks steps done or sends anything.</span>
        {res && <Badge tone={res.status === "accepted" ? "ok" : "warn"}>{res.status === "accepted" ? "accepted" : res.status === "discarded" ? "discarded" : "draft waiting"}</Badge>}
      </div>
      <input className="input w-full" aria-label="Instructions for the agent" placeholder="Optional: anything it should know or focus on (no passwords)" value={ins} onChange={(e) => setIns(e.target.value)} />
      {err && <p role="alert" className="text-sm text-red-600">{err}</p>}
      {res && (
        <div className="space-y-2 text-sm">
          <p className="text-xs text-muted">{res.judge_notes} {res.steps ? `Covered ${res.steps} step${res.steps === 1 ? "" : "s"}.` : ""}</p>
          {res.failed && res.failed.length > 0 && <p className="text-xs text-amber-700">Could not do: {res.failed.join("; ")}</p>}
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2 font-sans">{res.text}</pre>
          <div className="flex flex-wrap gap-2">
            <button className="btn" onClick={copy}>{done ? "Copied" : "Copy"}</button>
            <button className="btn" onClick={() => decide("accepted")}>I checked it, accept</button>
            <button className="btn" onClick={() => decide("discarded")}>Discard</button>
          </div>
        </div>
      )}
    </section>
  );
}
