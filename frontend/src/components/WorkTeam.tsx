"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge, errMsg } from "@/components/panels/kit";
import { getJson, postJson, putJson } from "@/lib/api";

type St = { enabled: boolean; daily_cap: number; used_today: number; remaining: number; providers_ready: Record<string, boolean>; ai_mode: string; workspace: string; note: string };
type D = { provider: string; label: string; text: string };
type Res = { key: string; text: string; judge_notes: string; judge: string; drafts: D[]; failed: string[]; mode: "work" | "advice"; warnings: string[]; workspace: string; status?: string; at: string };
type Kit = { brief: string; files: { name: string }[] } | null;
const NAMES: Record<string, string> = { google: "Gemini", openai: "OpenAI", anthropic: "Claude" };

/** Type what the job needs; three AIs each do it, Claude judges and writes one final draft for you to check. Works in Practice and Real. A draft only: nothing is sent or run. */
export function WorkTeam({ jobId, advice }: { jobId: number; advice: boolean }) {
  const [st, setSt] = useState<St | null>(null);
  const [res, setRes] = useState<Res | null>(null);
  const [kit, setKit] = useState<Kit>(null);
  const [tick, setTick] = useState(0);
  const [open, setOpen] = useState(false);
  const [ins, setIns] = useState("");
  const [mat, setMat] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [cap, setCap] = useState("3");
  const [showDrafts, setShowDrafts] = useState(false);

  useEffect(() => {
    let live = true;
    getJson<St>("/api/workteam/status").then((r) => { if (live) { setSt(r); setCap(String(r.daily_cap)); } }).catch(() => {});
    getJson<{ drafts: Record<string, Res> }>("/api/auto/prep/drafts").then((r) => { if (live) setRes(r.drafts[`team:${jobId}`] ? { ...r.drafts[`team:${jobId}`], key: `team:${jobId}` } : null); }).catch(() => {});
    getJson<{ kit: Kit }>(`/api/workteam/kit/${jobId}`).then((r) => { if (live) setKit(r.kit); }).catch(() => {});
    return () => { live = false; };
  }, [jobId, tick]);

  if (!st) return null;
  const real = st.workspace === "real";
  const run = async () => {
    setBusy(true); setErr(null);
    try { await postJson("/api/workteam/run", { job_id: jobId, instructions: ins, material: mat }); setTick((t) => t + 1); setShowDrafts(false); }
    catch (e) { setErr(errMsg(e, "The team didn't finish.")); }
    setBusy(false);
  };
  const config = async (body: unknown) => { setErr(null); try { await putJson("/api/workteam/config", body); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Couldn't save that.")); } };
  const decide = async (status: "accepted" | "discarded") => { try { await putJson(`/api/auto/prep/drafts/${encodeURIComponent(`team:${jobId}`)}`, { status }); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Couldn't save that.")); } };

  return (
    <div className="space-y-2 rounded border border-line p-2" aria-label="Work team">
      <div className="flex flex-wrap items-center gap-2">
        <button className="btn" aria-expanded={open} onClick={() => setOpen(!open)}>{open ? "Hide work team" : "Draft with the team"}</button>
        <span className="text-xs text-muted">Three AIs do the job, Claude judges. {advice ? "For this kind of job you get a checklist and advice, never “it’s fixed”." : "You get a draft to check."}</span>
        {res && <Badge tone={res.status === "accepted" ? "ok" : "warn"}>{res.status === "accepted" ? "draft accepted" : res.status === "discarded" ? "draft discarded" : "draft waiting"}</Badge>}
      </div>
      {open && (
        <div className="space-y-2 text-xs">
          {!st.enabled ? (
            <div className="flex flex-wrap items-center gap-2">
              <span>The work team is off. Each run uses up to four AI calls.</span>
              <label className="flex items-center gap-1">Runs per day <input className="input w-16" inputMode="numeric" value={cap} onChange={(e) => setCap(e.target.value)} /></label>
              <button className="btn btn-primary" onClick={() => config({ enabled: true, daily_cap: Number(cap) || 3 })}>Turn it on</button>
            </div>
          ) : (
            <>
              {st.ai_mode === "off" && <p role="alert" className="text-red-600">AI is switched off for this workspace in Settings, so the team can&apos;t run here. Change the AI access setting for this workspace first.</p>}
              {kit && <p>Practice materials for this job are on the <Link className="underline" href={`/job?id=${jobId}`}>job page</Link>. The team reads them automatically. It never sees the answer key.</p>}
              {real && <p className="text-amber-700">Real workspace: the team only sees the job title, your instructions and what you paste below, with client names and secrets removed. A pasted table is summarised on this computer first (counts and ranges, not the rows). Do not paste passwords, card numbers or anything the client hasn&apos;t agreed to share.</p>}
              <label className="flex flex-col gap-1 text-muted">What should the team do? (optional if the job title says it)
                <textarea className="input w-full" rows={2} value={ins} onChange={(e) => setIns(e.target.value)} placeholder="e.g. Build the weekly summary for the owner, three lines, plain words" />
              </label>
              <label className="flex flex-col gap-1 text-muted">{real ? "Material to include (paste text or a CSV table)" : "Extra material (optional; the practice files are included already)"}
                <textarea className="input w-full font-mono" rows={4} value={mat} onChange={(e) => setMat(e.target.value)} placeholder={advice ? "Symptoms, error messages, what you already tried (no passwords)" : "Paste the data, notes or code to work from"} />
              </label>
              <div className="flex flex-wrap items-center gap-2">
                <button className="btn btn-primary" disabled={busy || st.remaining <= 0 || st.ai_mode === "off"} onClick={run}>{busy ? "Team working… (about a minute)" : res ? "Run the team again" : "Run the team"}</button>
                <span className="text-muted">{st.remaining > 0 ? `${st.remaining} of ${st.daily_cap} runs left today` : "Daily cap reached. It resets tomorrow."}</span>
                <span className="text-muted">Ready: {Object.entries(st.providers_ready).map(([p, ok]) => `${NAMES[p]} ${ok ? "✓" : "no key"}`).join(" · ")}</span>
                <button className="underline text-muted" onClick={() => config({ enabled: false })}>Turn off</button>
              </div>
            </>
          )}
          {err && <p role="alert" className="text-red-600">{err}</p>}
        </div>
      )}
      {res && (
        <div className="space-y-2 text-xs">
          <p className="font-semibold text-muted">
            Team draft{res.judge ? ` (judged by ${res.judge})` : " (not judged)"}. It can be wrong: check it against the real files or equipment before you use it. Nothing was sent or run.
            {res.failed.length > 0 && ` No answer from: ${res.failed.join(", ")}.`}
          </p>
          {res.warnings.map((w) => <p key={w} className="text-amber-700">{w}</p>)}
          <pre className="whitespace-pre-wrap rounded bg-panel2 p-2 text-sm">{res.text}</pre>
          {res.judge_notes && <div><p className="font-semibold">Judge notes: verify these</p><pre className="whitespace-pre-wrap rounded bg-panel2 p-2">{res.judge_notes}</pre></div>}
          <div className="flex flex-wrap gap-2">
            <button className="btn" onClick={() => navigator.clipboard?.writeText(res.text)}>Copy final</button>
            <button className="btn" onClick={() => setShowDrafts(!showDrafts)}>{showDrafts ? "Hide" : "Show"} the three drafts</button>
            {res.status !== "accepted" && <button className="btn" onClick={() => decide("accepted")}>I checked it: accept</button>}
            {res.status !== "discarded" && <button className="btn" onClick={() => decide("discarded")}>Discard</button>}
            <span className="text-muted">You can also edit it on the Home screen (Assistant desk).</span>
          </div>
          {showDrafts && res.drafts.map((d) => <div key={d.provider}><p className="font-semibold">{d.label}</p><pre className="whitespace-pre-wrap rounded bg-panel2 p-2">{d.text}</pre></div>)}
        </div>
      )}
    </div>
  );
}
