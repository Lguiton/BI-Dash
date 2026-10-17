"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Tabs, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "check", label: "Compatibility" }, { id: "psu", label: "Power supply" }, { id: "build", label: "Build checklist" }, { id: "nopost", label: "Won't start (no POST)" }];
const FIELDS: [string, string][] = [["cpu_socket", "CPU socket"], ["board_socket", "Board socket"], ["board_ram", "Board RAM type"], ["ram_type", "RAM type"], ["board_form", "Board size"], ["case_form", "Case supports"], ["gpu_len_mm", "GPU length (mm)"], ["case_gpu_mm", "Case GPU room (mm)"], ["cooler_mm", "Cooler height (mm)"], ["case_cooler_mm", "Case cooler room (mm)"], ["cpu_tdp", "CPU power (W)"], ["gpu_tdp", "GPU power (W)"], ["psu_w", "Power supply (W)"]];

/** Plan and check a PC build, size the power supply, follow a build checklist, and diagnose a machine that will not start. */
export function PcBuildLab() {
  const [tab, setTab] = useState("check");
  const [opt, setOpt] = useState<R | null>(null);
  const [chk, setChk] = useState<R | null>(null);
  const [f, setF] = useState<Record<string, string>>({ cpu_socket: "AM5", board_socket: "AM5", board_ram: "DDR5", ram_type: "DDR5", board_form: "ATX", case_form: "ATX", gpu_len_mm: "320", case_gpu_mm: "360", cooler_mm: "155", case_cooler_mm: "165", cpu_tdp: "105", gpu_tdp: "250", psu_w: "750" });
  const [p, setP] = useState<Record<string, string>>({ cpu_w: "105", gpu_w: "250", ssd: "2", hdd: "0", fans: "4", sticks: "2" });
  const [psu, setPsu] = useState<R | null>(null);
  const [list, setList] = useState<R | null>(null);
  const [sym, setSym] = useState("fans spin but no display");
  const [dx, setDx] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    const bad = (e: unknown) => setErr(errMsg(e, "Couldn't load that."));
    if (tab === "check" && !opt) getJson<R>("/api/pcbuild/options").then(setOpt).catch(bad);
    if (tab === "build" && !list) getJson<R>("/api/pcbuild/checklist").then(setList).catch(bad);
  }, [tab, opt, list]);
  const go = async (fn: () => Promise<void>, m: string) => { setErr(null); try { await fn(); } catch (e) { setErr(errMsg(e, m)); } };
  return (
    <section className="card space-y-3 p-4" aria-label="PC build lab">
      <h2 className="text-base font-semibold">PC build lab: compatibility, power, build steps and no-start diagnosis</h2>
      <p className="text-xs text-muted">Planning aid. Always confirm against each maker&apos;s spec page and the motherboard manual.</p>
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="PC build lab" />
      {err && <ErrorBanner message={err} />}
      {tab === "check" && (
        <Section title="Will these parts work together?" note="Blank boxes are skipped. Sockets: AM4, AM5, LGA1200, LGA1700, LGA1851. Sizes: E-ATX, ATX, Micro-ATX, Mini-ITX. RAM: DDR4 or DDR5.">
          <div className="flex flex-wrap items-end gap-2">{FIELDS.map(([k, l]) => <label key={k} className="text-xs">{l}<input className="input block w-32" value={f[k] ?? ""} onChange={(e) => setF({ ...f, [k]: e.target.value })} /></label>)}</div>
          <button className="btn btn-primary mt-2" onClick={() => go(async () => setChk(await postJson<R>("/api/pcbuild/check", f)), "Couldn't check that.")}>Check</button>
          {chk && (
            <div className="mt-3 space-y-2 text-sm">
              <p className="font-semibold">{chk.verdict}</p>
              {chk.problems.map((x: string) => <p key={x}><Badge tone="bad">problem</Badge> {x}</p>)}
              {chk.warnings.map((x: string) => <p key={x}><Badge tone="warn">check</Badge> {x}</p>)}
              {chk.passes.map((x: string) => <p key={x}><Badge tone="ok">ok</Badge> {x}</p>)}
              <p className="text-xs font-semibold uppercase text-muted">Also check</p>
              <ul className="list-disc space-y-1 pl-5 text-xs">{chk.also_check.map((x: string) => <li key={x}>{x}</li>)}</ul>
            </div>
          )}
          {opt && <p className="mt-2 text-xs text-muted">{opt.note}</p>}
        </Section>
      )}
      {tab === "psu" && (
        <Section title="Power supply size" note="Adds CPU, GPU and everything else, then leaves about 40% headroom.">
          <div className="flex flex-wrap items-end gap-2">{([["cpu_w", "CPU power (W)"], ["gpu_w", "GPU power (W)"], ["ssd", "SSDs"], ["hdd", "Hard drives"], ["fans", "Fans"], ["sticks", "RAM sticks"]] as [string, string][]).map(([k, l]) => <label key={k} className="text-xs">{l}<input className="input block w-28" inputMode="numeric" value={p[k]} onChange={(e) => setP({ ...p, [k]: e.target.value })} /></label>)}</div>
          <button className="btn btn-primary mt-2" onClick={() => go(async () => setPsu(await postJson<R>("/api/pcbuild/psu", p)), "Check your numbers.")}>Size it</button>
          {psu && <div className="mt-2 space-y-1 text-sm"><p>Estimated load <b>{psu.estimated_load_w} W</b> (CPU {psu.cpu_w}, GPU {psu.gpu_w}, everything else {psu.other_w}). Recommended supply: <b>{psu.recommended_w} W</b>.</p><p className="text-xs text-muted">{psu.why}</p><ul className="list-disc space-y-1 pl-5 text-xs">{psu.buy_tips.map((t: string) => <li key={t}>{t}</li>)}</ul></div>}
        </Section>
      )}
      {tab === "build" && list && (
        <div className="space-y-3">{list.phases.map((ph: R) => <Section key={ph.phase} title={ph.phase}><ol className="list-decimal space-y-1 pl-5 text-sm">{ph.steps.map((s: string) => <li key={s}>{s}</li>)}</ol></Section>)}</div>
      )}
      {tab === "nopost" && (
        <Section title="It won't start or show a picture" note="Describe what happens at power on.">
          <div className="flex flex-wrap gap-2">
            <input className="input min-w-64 flex-1" aria-label="What the PC does" value={sym} onChange={(e) => setSym(e.target.value)} />
            <button className="btn btn-primary" onClick={() => go(async () => setDx(await postJson<R>("/api/pcbuild/diagnose", { symptom: sym })), "Describe what happens.")}>Diagnose</button>
          </div>
          {dx && (
            <div className="mt-3 space-y-2 text-sm">
              {dx.matches.map((m: R) => <div key={m.id} className="rounded border border-line p-2"><p className="font-semibold">{m.title}</p><ol className="list-decimal space-y-1 pl-5">{m.checks.map((c: string) => <li key={c}>{c}</li>)}</ol></div>)}
              <p className="text-xs"><b>Rule:</b> {dx.rule}</p><p className="text-xs text-muted">{dx.safety}</p>
            </div>
          )}
        </Section>
      )}
    </section>
  );
}
