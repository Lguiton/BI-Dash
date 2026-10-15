"use client";
import { useEffect, useState } from "react";
import { errMsg } from "@/components/panels/kit";
import { deleteJson, getJson, postJson } from "@/lib/api";

type Draft = { text: string; error?: string; status?: string; at: string; model?: string; auto?: boolean; title: string };
type Prep = { enabled: boolean; used_today: number; daily_cap: number; remaining: number };

/** A first-pass AI draft for one work item or one table. You read it; it never acts. Shows nothing at all while prep drafts are switched off. */
export function PrepDraft({ draftKey, path, body, label }: { draftKey: string; path: string; body?: unknown; label: string }) {
  const [prep, setPrep] = useState<Prep | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [tick, setTick] = useState(0);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getJson<Prep>("/api/auto/prep").then((r) => { if (live) setPrep(r); }).catch(() => {});
    getJson<{ drafts: Record<string, Draft> }>("/api/auto/prep/drafts").then((r) => { if (live) setDraft(r.drafts[draftKey] ?? null); }).catch(() => {});
    return () => { live = false; };
  }, [draftKey, tick]);

  async function make() {
    setBusy(true); setErr(null);
    try { await postJson(path, body ?? {}); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "The draft didn't work.")); }
    setBusy(false);
  }
  async function remove() {
    try { await deleteJson(`/api/auto/prep/drafts/${encodeURIComponent(draftKey)}`); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "Couldn't delete it.")); }
  }
  if (!prep?.enabled && !draft) return null;
  return (
    <div className="space-y-1 rounded border border-line p-2 text-xs" aria-label="AI first pass">
      {prep?.enabled && <div className="flex flex-wrap items-center gap-2">
        <button className="btn" disabled={busy || prep.remaining <= 0} onClick={make}>{busy ? "Drafting…" : draft ? `Redo: ${label}` : label}</button>
        <span className="text-muted">{prep.remaining > 0 ? `${prep.remaining} of ${prep.daily_cap} left today` : "Daily cap reached. It resets tomorrow."}</span>
      </div>}
      {err && <p role="alert" className="text-red-600">{err}</p>}
      {draft && !draft.error && (
        <div>
          <p className="font-semibold text-muted">AI first pass{draft.auto ? " (automatic)" : ""}. It can be wrong. Check it before you use it. {draft.status === "accepted" ? "Accepted." : draft.status === "discarded" ? "Discarded." : "Waiting for you on the Home screen (Assistant desk)."}</p>
          <pre className="whitespace-pre-wrap rounded bg-panel2 p-2">{draft.text}</pre>
          <button className="text-red-600 underline" onClick={remove}>Delete this draft</button>
        </div>
      )}
      {draft?.error && <p className="text-muted">The automatic draft didn&apos;t work: {draft.error} <button className="underline" onClick={remove}>Dismiss</button></p>}
    </div>
  );
}
