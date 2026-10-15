"use client";
import { useEffect, useState } from "react";
import { Badge, errMsg } from "@/components/panels/kit";
import { deleteJson, getJson, putJson } from "@/lib/api";

type Q = { key: string; kind: "item" | "table" | "job" | "team"; title: string; text: string; auto?: boolean; edited?: boolean };
type Stats = { drafts_total: number; drafts_today: number; accepted: number; discarded: number; edited: number; examples_saved: number; used_rate: number | null };
type Role = { track: string; title: string; does: string; never: string; custom: boolean };
type Mine = { id: number; problem: string; steps: string[]; saved: string };
type Log = { at: string; kind: string; title: string };
type Desk = { roles: Role[]; stats: Stats; log: Log[]; mine: Mine[] };
const VERB: Record<string, string> = { draft: "drafted", accept: "accepted", edit: "edited", discard: "discarded", example: "saved as your example" };

/** What the assistants prepared for you: read, edit, accept or discard. Plus their job descriptions and your own saved examples. */
export function AssistantDesk() {
  const [q, setQ] = useState<Q[]>([]);
  const [desk, setDesk] = useState<Desk | null>(null);
  const [text, setText] = useState<Record<string, string>>({});
  const [roleEdit, setRoleEdit] = useState<Record<string, { does: string; never: string }>>({});
  const [tick, setTick] = useState(0);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getJson<{ queue: Q[] }>("/api/auto/queue").then((r) => { if (live) setQ(r.queue); }).catch((e) => { if (live) setErr(errMsg(e, "Couldn't load the assistant queue.")); });
    getJson<Desk>("/api/auto/assistants").then((r) => { if (live) setDesk(r); }).catch(() => {});
    return () => { live = false; };
  }, [tick]);

  async function run(fn: () => Promise<unknown>) {
    setErr(null);
    try { await fn(); setTick((t) => t + 1); } catch (e) { setErr(errMsg(e, "That didn't save.")); }
  }
  const decide = (r: Q, status: "accepted" | "discarded", save_example = false) =>
    run(() => putJson(`/api/auto/prep/drafts/${encodeURIComponent(r.key)}`, { status, save_example, ...(status === "accepted" && text[r.key] !== undefined ? { text: text[r.key] } : {}) }));
  const s = desk?.stats;
  if (!desk && !err) return null;
  return (
    <section className="card space-y-3 p-4" aria-label="Assistant desk">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold">Assistant desk{q.length ? ` (${q.length} waiting)` : ""}</h2>
        {s && s.drafts_total > 0 && <span className="text-xs text-muted">{s.drafts_today} drafted today · you used {s.used_rate === null ? "none decided yet" : `${Math.round(s.used_rate * 100)}% of decided drafts`}</span>}
      </div>
      {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
      {q.length === 0 && <p className="text-sm text-muted">Nothing waiting. When an assistant prepares a draft, it appears here for you to read, edit and accept or discard.</p>}
      <ul className="space-y-3">
        {q.map((r) => (
          <li key={r.key} className="space-y-1 rounded border border-line p-2">
            <div className="flex flex-wrap items-center gap-2 text-sm"><Badge tone="muted">{r.kind === "item" ? "work item" : r.kind === "job" ? "closing note" : r.kind === "team" ? "team draft" : "table"}</Badge><strong>{r.title}</strong>{r.auto && <Badge tone="warn">automatic</Badge>}</div>
            <p className="text-xs text-muted">AI first pass. It can be wrong. Edit it, then accept or discard.</p>
            <textarea aria-label={`Draft for ${r.title}`} className="input w-full text-xs" rows={r.kind === "team" ? 14 : 6} value={text[r.key] ?? r.text} onChange={(e) => setText({ ...text, [r.key]: e.target.value })} />
            <div className="flex flex-wrap gap-2">
              <button className="btn" onClick={() => decide(r, "accepted")}>Accept</button>
              {(r.kind === "item" || r.kind === "job") && <button className="btn" onClick={() => decide(r, "accepted", true)}>Accept and save as my example</button>}
              <button className="btn" onClick={() => decide(r, "discarded")}>Discard</button>
            </div>
          </li>
        ))}
      </ul>
      {desk && (
        <div className="space-y-2 border-t border-line pt-2 text-xs">
          <details>
            <summary className="cursor-pointer text-muted">Job descriptions ({desk.roles.length} assistants)</summary>
            <p className="mt-1 text-muted">Each assistant is shown its job description. Rewrite what it does or never does. This cannot switch off the safety rules the app already enforces.</p>
            <ul className="mt-2 space-y-2">
              {desk.roles.map((r) => {
                const e = roleEdit[r.track] ?? { does: r.does, never: r.never };
                return (
                  <li key={r.track} className="space-y-1">
                    <strong>{r.title}</strong> {r.custom && <Badge tone="ok">edited</Badge>}
                    <input aria-label={`${r.title} does`} className="input w-full" value={e.does} onChange={(x) => setRoleEdit({ ...roleEdit, [r.track]: { ...e, does: x.target.value } })} />
                    <input aria-label={`${r.title} never`} className="input w-full" value={e.never} onChange={(x) => setRoleEdit({ ...roleEdit, [r.track]: { ...e, never: x.target.value } })} />
                    <div className="flex gap-2">
                      <button className="btn" onClick={() => run(async () => { await putJson(`/api/auto/assistants/roles/${r.track}`, e); setRoleEdit((m) => { const n = { ...m }; delete n[r.track]; return n; }); })}>Save</button>
                      {r.custom && <button className="underline" onClick={() => run(async () => { await deleteJson(`/api/auto/assistants/roles/${r.track}`); setRoleEdit((m) => { const n = { ...m }; delete n[r.track]; return n; }); })}>Back to default</button>}
                    </div>
                  </li>
                );
              })}
            </ul>
          </details>
          <details>
            <summary className="cursor-pointer text-muted">My saved examples ({desk.mine.length})</summary>
            <p className="mt-1 text-muted">Your own approaches from past cases. The assistants read these first when a new case matches. Client names are removed when saved.</p>
            <ul className="mt-2 space-y-1">
              {desk.mine.map((m) => <li key={m.id} className="flex flex-wrap items-center gap-2"><span><strong>{m.problem}</strong> <span className="text-muted">({m.steps.length} steps, saved {m.saved})</span></span><button className="text-red-600 underline" onClick={() => run(() => deleteJson(`/api/auto/examples/mine/${m.id}`))}>Delete</button></li>)}
              {desk.mine.length === 0 && <li className="text-muted">None yet. Use &quot;Accept and save as my example&quot; on a draft you improved.</li>}
            </ul>
          </details>
          <details>
            <summary className="cursor-pointer text-muted">Recent activity</summary>
            <ul className="mt-2 space-y-0.5 text-muted">{desk.log.map((l, i) => <li key={i}>{l.at.slice(0, 16)} (UTC) · {l.title || "draft"} {VERB[l.kind] ?? l.kind}</li>)}{desk.log.length === 0 && <li>Nothing yet.</li>}</ul>
          </details>
        </div>
      )}
    </section>
  );
}
