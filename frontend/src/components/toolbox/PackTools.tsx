"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Section, Tabs, errMsg } from "@/components/panels/kit";
import { HtmlFrame, Pick } from "./common";
import { FieldHowTo, Out } from "./fieldcommon";

type Input = { name: string; label: string; kind: string; default: string; options: { id: string; label: string }[]; help: string };
type ToolDef = { id: string; title: string; note: string; inputs: Input[] };
type PackDef = { id: string; label: string; blurb: string; agent: string; examples: string; tools: ToolDef[] };
type Result = Record<string, unknown>;

function ToolForm({ pack, tool }: { pack: string; tool: ToolDef }) {
  const [vals, setVals] = useState<Record<string, string>>(() => Object.fromEntries(tool.inputs.map((i) => [i.name, i.default ?? ""])));
  const [res, setRes] = useState<Result | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (x: string) => setVals((v) => ({ ...v, [k]: x }));
  async function go() {
    setErr(null); setBusy(true);
    try { setRes(await postJson<Result>(`/api/fieldpacks/${pack}/${tool.id}`, vals)); } catch (e) { setErr(errMsg(e, "That did not work.")); setRes(null); } finally { setBusy(false); }
  }
  const html = typeof res?.html === "string" ? res.html : null;
  const link = typeof res?.link === "string" ? res.link : null;
  return (
    <Section title={tool.title} note={tool.note}>
      {err && <ErrorBanner message={err} />}
      {tool.inputs.some((i) => i.default) && <p className="mb-2 text-xs text-muted">Made-up example values are filled in so you can see how it works. Replace them with your own.</p>}
      <div className="grid gap-2">
        <div className="flex flex-wrap items-end gap-2">
          {tool.inputs.filter((i) => i.kind !== "area").map((i) => i.kind === "select"
            ? <Pick key={i.name} label={i.label} value={vals[i.name]} onChange={set(i.name)} options={i.options} blank="Choose…" />
            : <label key={i.name} className="grid gap-1 text-xs text-muted">{i.label}<input aria-label={i.label} className="input w-64 max-w-full" inputMode={i.kind === "number" ? "decimal" : undefined} value={vals[i.name]} onChange={(e) => set(i.name)(e.target.value)} /></label>)}
        </div>
        {tool.inputs.filter((i) => i.kind === "area").map((i) => (
          <label key={i.name} className="grid gap-1 text-xs text-muted">{i.label}<textarea aria-label={i.label} className="input font-mono text-sm" rows={5} value={vals[i.name]} onChange={(e) => set(i.name)(e.target.value)} /></label>
        ))}
        <div><button className="btn" disabled={busy} onClick={go}>{busy ? "Working…" : tool.inputs.length ? "Run" : "Show"}</button></div>
      </div>
      <Out data={res} hide={["html", "link"]} />
      {link && <p className="mt-2 break-all rounded bg-panel2 p-2 text-sm" aria-label="Link">{link}</p>}
      {html && <HtmlFrame html={html} name={`${pack}-${tool.id}.html`} />}
    </Section>
  );
}

/** One field: a how-to search bar plus each of its tools. */
export function PackTools({ pack }: { pack: string }) {
  const [def, setDef] = useState<PackDef | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [want, setTab] = useState("how");
  useEffect(() => {
    let live = true;
    getJson<PackDef>(`/api/fieldpacks/${pack}`).then((r) => { if (live) { setDef(r); setTab("how"); } }).catch((e) => { if (live) setErr(errMsg(e, "Could not load this field.")); });
    return () => { live = false; };
  }, [pack]);
  if (err) return <ErrorBanner message={err} />;
  if (!def) return <p className="text-sm text-muted">Loading…</p>;
  const work = true; // every field dashboard has its own fix-it panel, so the tool tabs skip the how-to tab
  const tab = work && (want === "how" || !def.tools.some((t) => t.id === want)) ? def.tools[0]?.id ?? "how" : want;
  const cur = def.tools.find((t) => t.id === tab);
  return (
    <div className="grid gap-4">
      <p className="text-sm text-muted">{def.blurb}</p>
      <Tabs label={`${def.label} tools`} value={tab} onChange={setTab} tabs={[...(work ? [] : [{ id: "how", label: "How to do / fix" }]), ...def.tools.map((t) => ({ id: t.id, label: t.title }))]} />
      {tab === "how" && <FieldHowTo area={def.label} agent={def.agent} examples={def.examples} />}
      {cur && <ToolForm key={`${pack}-${cur.id}`} pack={pack} tool={cur} />}
    </div>
  );
}

/** Core tools of an existing field, plus one or more extra packs as secondary tabs. */
export function WithPacks({ core, packs, initial, coreLabel = "Core tools" }: { core: React.ReactNode; packs: { id: string; label: string }[]; initial?: string; coreLabel?: string }) {
  const [sel, setSel] = useState(initial && packs.some((p) => p.id === initial) ? initial : core ? "core" : packs[0].id);
  const tabs = [...(core ? [{ id: "core", label: coreLabel }] : []), ...packs];
  return (
    <div className="grid gap-4">
      {tabs.length > 1 && <Tabs label="Tool sets" value={sel} onChange={setSel} tabs={tabs} />}
      {sel === "core" ? core : <PackTools pack={sel} />}
    </div>
  );
}
