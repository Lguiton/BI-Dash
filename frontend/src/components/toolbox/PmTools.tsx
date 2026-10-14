"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { API_BASE, apiFetch, deleteJson, getJson, postJson } from "@/lib/api";
import { Section, Tabs, errMsg } from "@/components/panels/kit";
import { fetchText, HtmlFrame, Pick } from "./common";
import { FieldHowTo, Out, TA, TI, lines, cols, useRun } from "./fieldcommon";

const TABS = [{ id: "how", label: "How to do / fix" }, { id: "sow", label: "Proposal / SOW" }, { id: "status", label: "Status report" }, { id: "est", label: "Estimator" }, { id: "stories", label: "User stories" }, { id: "road", label: "Roadmap" }, { id: "log", label: "Decision and retro log" }];

export function PmTools() {
  const [tab, setTab] = useState("how");
  return (
    <div className="grid gap-4">
      <Tabs label="Project management tools" value={tab} onChange={setTab} tabs={TABS} />
      {tab === "how" && <FieldHowTo area="Project management" agent="pm" examples="e.g. client keeps adding things, project is late" />}
      {tab === "sow" && <Sow />}
      {tab === "status" && <Status />}
      {tab === "est" && <Estimator />}
      {tab === "stories" && <Stories />}
      {tab === "road" && <Roadmap />}
      {tab === "log" && <Log />}
    </div>
  );
}

function Sow() {
  const [f, setF] = useState({ client: "", project: "", objectives: "", deliverables: "", exclusions: "", assumptions: "", price_model: "fixed", price: "", rate: "", weeks: "", revisions: "2" });
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const set = (k: keyof typeof f) => (x: string) => setF({ ...f, [k]: x });
  return (
    <Section title="Proposal and statement of work" note="A plain scope document. It is a starting draft, not legal advice: have a lawyer review contracts you rely on.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2">
        <div className="flex flex-wrap gap-2"><TI label="Client" value={f.client} onChange={set("client")} w="w-56" /><TI label="Project" value={f.project} onChange={set("project")} w="w-64" /></div>
        <TA label="Objectives (one per line)" value={f.objectives} onChange={set("objectives")} rows={2} />
        <TA label="Deliverables (one per line, required)" value={f.deliverables} onChange={set("deliverables")} rows={3} />
        <TA label="Not included (one per line, optional)" value={f.exclusions} onChange={set("exclusions")} rows={2} />
        <TA label="Assumptions (one per line, optional)" value={f.assumptions} onChange={set("assumptions")} rows={2} />
        <div className="flex flex-wrap items-end gap-2">
          <Pick label="Pricing" value={f.price_model} onChange={set("price_model")} options={[{ id: "fixed", label: "Fixed price" }, { id: "hourly", label: "Hourly" }]} blank="Pricing" />
          {f.price_model === "fixed" ? <TI label="Price" value={f.price} onChange={set("price")} w="w-32" /> : <TI label="Hourly rate" value={f.rate} onChange={set("rate")} w="w-32" />}
          <TI label="Weeks" value={f.weeks} onChange={set("weeks")} w="w-24" /><TI label="Rounds of changes" value={f.revisions} onChange={set("revisions")} w="w-32" />
        </div>
        <div><button className="btn" onClick={async () => { setErr(null); try { setHtml(await fetchText("/api/fieldbox/pm/sow", { ...f, objectives: lines(f.objectives), deliverables: lines(f.deliverables), exclusions: lines(f.exclusions), assumptions: lines(f.assumptions) })); } catch (e) { setErr(e instanceof Error ? e.message : "Failed."); setHtml(null); } }}>Write the SOW</button></div>
      </div>
      {html && <HtmlFrame html={html} name="statement-of-work.html" />}
    </Section>
  );
}

function Status() {
  const [project, setProject] = useState("");
  const [client, setClient] = useState("");
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  return (
    <Section title="Weekly status report" note="Built from the work items on your Project track board, so it only works once the board has items.">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-end gap-2">
        <TI label="Project name" value={project} onChange={setProject} w="w-64" /><TI label="Client" value={client} onChange={setClient} w="w-48" />
        <button className="btn" onClick={async () => { setErr(null); try { setHtml(await fetchText("/api/fieldbox/pm/status", { project, client })); } catch (e) { setErr(e instanceof Error ? e.message : "Failed."); setHtml(null); } }}>Build report</button>
      </div>
      {html && <HtmlFrame html={html} name="status-report.html" />}
    </Section>
  );
}

function Estimator() {
  const [t, setT] = useState("Design screens, 4, 8, 16\nBuild forms, 6, 10, 20\nTesting, 3, 5, 12");
  const r = useRun<Record<string, unknown>>();
  return (
    <Section title="Three-point estimator" note="Best case, likely and worst case in hours for each task. Quote near the 80% figure, not the average.">
      {r.err && <ErrorBanner message={r.err} />}
      <TA label="Tasks: name, best, likely, worst" value={t} onChange={setT} rows={5} />
      <button className="btn mt-2" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/pm/estimate", { tasks: lines(t).map((l) => { const c = cols(l); return { name: c[0], optimistic: Number(c[1]), likely: Number(c[2]), pessimistic: Number(c[3]) }; }) }), "Could not estimate.")}>Estimate</button>
      <Out data={r.res} />
    </Section>
  );
}

function Stories() {
  const [t, setT] = useState("owner, see this week's sales, decide what to reorder");
  const r = useRun<Record<string, unknown>>();
  return (
    <Section title="User-story writer" note="Turns each need into a story with criteria a tester can pass or fail, and flags vague words.">
      {r.err && <ErrorBanner message={r.err} />}
      <TA label="One per line: who, what they want, why" value={t} onChange={setT} rows={5} />
      <button className="btn mt-2" disabled={r.busy} onClick={() => r.run(() => postJson("/api/fieldbox/pm/stories", { items: lines(t).map((l) => { const c = cols(l); return { role: c[0], want: c[1], benefit: c[2] }; }) }), "Could not write the stories.")}>Write stories</button>
      <Out data={r.res} />
    </Section>
  );
}

type Item = { id: string; title: string; lane: string; why: string; owner: string };
const LANES = ["now", "next", "later"];
function Roadmap() {
  const [items, setItems] = useState<Item[]>([]);
  const [tick, setTick] = useState(0);
  const [title, setTitle] = useState("");
  const [lane, setLane] = useState("next");
  const [why, setWhy] = useState("");
  const [html, setHtml] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    getJson<{ items: Item[] }>("/api/fieldbox/pm/roadmap").then((r) => { if (live) setItems(r.items); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load the roadmap.")); });
    return () => { live = false; };
  }, [tick]);
  const act = async (fn: () => Promise<unknown>) => { setErr(null); try { await fn(); setTick((x) => x + 1); } catch (e) { setErr(errMsg(e, "That did not work.")); } };
  return (
    <Section title="Roadmap builder" note="Now, next, later. A direction and an order, not a promise of dates.">
      {err && <ErrorBanner message={err} />}
      <div className="flex flex-wrap items-end gap-2">
        <TI label="Item" value={title} onChange={setTitle} w="w-64" /><Pick label="Lane" value={lane} onChange={setLane} options={LANES.map((l) => ({ id: l, label: l }))} blank="Lane" /><TI label="Why it matters" value={why} onChange={setWhy} w="w-72" />
        <button className="btn" disabled={!title.trim()} onClick={() => act(async () => { await postJson("/api/fieldbox/pm/roadmap", { title, lane, why }); setTitle(""); setWhy(""); })}>Add item</button>
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-3">
        {LANES.map((l) => (
          <div key={l} className="rounded border border-line p-2"><h4 className="text-xs font-medium uppercase text-muted">{l}</h4>
            <ul className="mt-1 grid gap-2 text-sm">{items.filter((i) => i.lane === l).map((i) => (
              <li key={i.id}><b>{i.title}</b>{i.why && <span className="block text-xs text-muted">{i.why}</span>}
                <span className="flex flex-wrap gap-1">{LANES.filter((x) => x !== l).map((x) => <button key={x} className="btn" aria-label={`Move ${i.title} to ${x}`} onClick={() => act(() => postJson(`/api/fieldbox/pm/roadmap/${i.id}/move`, { lane: x }))}>→ {x}</button>)}<button className="btn" aria-label={`Remove ${i.title}`} onClick={() => act(() => deleteJson(`/api/fieldbox/pm/roadmap/${i.id}`))}>Remove</button></span></li>
            ))}</ul></div>
        ))}
      </div>
      <button className="btn mt-3" onClick={async () => { setErr(null); try { const r = await apiFetch(`${API_BASE}/api/fieldbox/pm/roadmap.html`); setHtml(await r.text()); } catch (e) { setErr(errMsg(e, "Could not build the page.")); } }}>Make a shareable page</button>
      {html && <HtmlFrame html={html} name="roadmap.html" />}
    </Section>
  );
}

type Entry = { id: string; kind: string; at: string; decision?: string; context?: string; owner?: string; revisit?: string; went_well?: string; improve?: string; actions?: string };
function Log() {
  const [items, setItems] = useState<Entry[]>([]);
  const [tick, setTick] = useState(0);
  const [kind, setKind] = useState("decision");
  const [f, setF] = useState({ decision: "", context: "", owner: "", revisit: "", went_well: "", improve: "", actions: "" });
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    getJson<{ entries: Entry[] }>("/api/fieldbox/pm/log").then((r) => { if (live) setItems(r.entries); }).catch((e) => { if (live) setErr(errMsg(e, "Could not load the log.")); });
    return () => { live = false; };
  }, [tick]);
  const set = (k: keyof typeof f) => (x: string) => setF({ ...f, [k]: x });
  async function md() {
    try { const r = await apiFetch(`${API_BASE}/api/fieldbox/pm/log.md`); const u = URL.createObjectURL(await r.blob()); const a = document.createElement("a"); a.href = u; a.download = "decision-log.md"; a.click(); setTimeout(() => URL.revokeObjectURL(u), 2000); } catch (e) { setErr(errMsg(e, "Could not download.")); }
  }
  return (
    <Section title="Decision and retro log" note="Write down what was decided and why, so it is not argued again. Retros record what went well and what to change.">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-2">
        <Pick label="Entry type" value={kind} onChange={setKind} options={[{ id: "decision", label: "Decision" }, { id: "retro", label: "Retro" }]} blank="Type" />
        {kind === "decision" ? (<>
          <TI label="What was decided" value={f.decision} onChange={set("decision")} w="w-96" /><TI label="Why, and what else was considered" value={f.context} onChange={set("context")} w="w-96" />
          <div className="flex gap-2"><TI label="Decided by" value={f.owner} onChange={set("owner")} w="w-40" /><TI label="Revisit on (date)" value={f.revisit} onChange={set("revisit")} w="w-40" /></div>
        </>) : (<>
          <TA label="What went well" value={f.went_well} onChange={set("went_well")} rows={2} /><TA label="What to change" value={f.improve} onChange={set("improve")} rows={2} /><TA label="Actions and who owns them" value={f.actions} onChange={set("actions")} rows={2} />
        </>)}
        <div className="flex gap-2">
          <button className="btn" onClick={async () => { setErr(null); try { await postJson("/api/fieldbox/pm/log", { kind, ...f }); setF({ decision: "", context: "", owner: "", revisit: "", went_well: "", improve: "", actions: "" }); setTick((x) => x + 1); } catch (e) { setErr(errMsg(e, "Could not save the entry.")); } }}>Add entry</button>
          {items.length > 0 && <button className="btn" onClick={md}>Download as Markdown</button>}
        </div>
      </div>
      {items.length > 0 && <ul className="mt-3 grid gap-2 text-sm">{items.map((e) => (
        <li key={e.id} className="rounded border border-line p-2"><span className="text-xs text-muted">{e.at} · {e.kind}</span><br />
          {e.kind === "decision" ? <><b>{e.decision}</b>{e.context && <span className="block">{e.context}</span>}{(e.owner || e.revisit) && <span className="block text-xs text-muted">{e.owner} {e.revisit && `· revisit ${e.revisit}`}</span>}</> : <>{e.went_well && <span className="block">Went well: {e.went_well}</span>}{e.improve && <span className="block">Change: {e.improve}</span>}{e.actions && <span className="block">Actions: {e.actions}</span>}</>}
          <button className="btn mt-1" aria-label="Delete entry" onClick={async () => { try { await deleteJson(`/api/fieldbox/pm/log/${e.id}`); setTick((x) => x + 1); } catch (x) { setErr(errMsg(x, "Could not delete.")); } }}>Delete</button></li>
      ))}</ul>}
    </Section>
  );
}
