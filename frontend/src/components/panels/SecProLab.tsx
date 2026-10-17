"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Tabs, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "cvss", label: "CVSS score" }, { id: "risk", label: "Risk assessment" }, { id: "scope", label: "Test authorization" }, { id: "owasp", label: "OWASP Top 10" }, { id: "attack", label: "Attack stages" }, { id: "time", label: "Forensic timeline" }, { id: "rule", label: "IDS rule explainer" }, { id: "check", label: "Assessment checklists" }];
const OPT: Record<string, [string, string][]> = {
  AV: [["N", "Network"], ["A", "Adjacent"], ["L", "Local"], ["P", "Physical"]], AC: [["L", "Low"], ["H", "High"]], PR: [["N", "None"], ["L", "Low"], ["H", "High"]], UI: [["N", "None"], ["R", "Required"]],
  S: [["U", "Unchanged"], ["C", "Changed"]], C: [["H", "High"], ["L", "Low"], ["N", "None"]], I: [["H", "High"], ["L", "Low"], ["N", "None"]], A: [["H", "High"], ["L", "Low"], ["N", "None"]],
};
const LBL: Record<string, string> = { AV: "Attack vector", AC: "Complexity", PR: "Privileges needed", UI: "User interaction", S: "Scope", C: "Confidentiality", I: "Integrity", A: "Availability" };
const LEVELS = ["rare", "unlikely", "possible", "likely", "almost certain"];
const IMPACTS = ["minor", "moderate", "significant", "major", "severe"];

function Copy({ text }: { text: string }) {
  const [d, setD] = useState(false);
  return <button className="btn" onClick={async () => { try { await navigator.clipboard.writeText(text); setD(true); setTimeout(() => setD(false), 2000); } catch { /* select instead */ } }}>{d ? "Copied" : "Copy"}</button>;
}

/** Advanced security: scoring, risk, authorization, references, forensic timeline, IDS rules and assessment checklists. Reference and local calculation only. It never scans or tests anything. */
export function SecProLab() {
  const [tab, setTab] = useState("cvss");
  const [ref, setRef] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [out, setOut] = useState<R | null>(null);
  const [cv, setCv] = useState<Record<string, string>>({ AV: "N", AC: "L", PR: "N", UI: "N", S: "U", C: "H", I: "H", A: "H" });
  const [f, setF] = useState<Record<string, string>>({ value: "10000", exposure: "50", per_year: "2", ctrl: "1000", reduction: "80", lik: "possible", imp: "major", client: "", systems: "", start: "", end: "", testing: "", excl: "", log: "2026-10-16 14:00:00 login ok\n2026-10-16 14:02:11 admin account created\nOct 16 16:30:00 backup deleted", rule: 'alert tcp $HOME_NET any -> $EXTERNAL_NET 443 (msg:"Possible beacon"; content:"abc"; nocase; sid:1000001; rev:1;)' });
  const [kind, setKind] = useState("hipaa");
  const s = (k: string) => (v: string) => setF((x) => ({ ...x, [k]: v }));
  useEffect(() => { if (["owasp", "attack", "check", "risk"].includes(tab) && !ref) getJson<R>("/api/secpro/reference").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load the reference."))); }, [tab, ref]);
  const run = async (path: string, body: unknown) => { setErr(null); try { setOut(await postJson<R>(`/api/secpro/${path}`, body)); } catch (e) { setOut(null); setErr(errMsg(e, "Check what you entered.")); } };
  const load = async () => { setErr(null); try { setOut(await getJson<R>(`/api/secpro/checklist/${kind}`)); } catch (e) { setErr(errMsg(e, "Couldn't load that.")); } };
  return (
    <section className="card space-y-3 p-4" aria-label="Advanced security lab">
      <h2 className="text-base font-semibold">Advanced security: scoring, risk, authorization, forensics and assessments</h2>
      <p className="rounded border border-line p-2 text-xs"><Badge tone="warn">Authorization first</Badge> Nothing here scans or tests a system. Testing someone else&apos;s system needs their written authorization. Practice only in your own lab.</p>
      <Tabs tabs={TABS} value={tab} onChange={(t) => { setTab(t); setOut(null); setErr(null); }} label="Advanced security lab" />
      {err && <ErrorBanner message={err} />}

      {tab === "cvss" && (
        <Section title="CVSS 3.1 base score" note="Pick the values from the vulnerability's advisory. The score rates the flaw, not your risk.">
          <div className="flex flex-wrap items-end gap-2">{Object.keys(OPT).map((k) => <label key={k} className="text-xs">{LBL[k]}<select className="input block w-32" value={cv[k]} onChange={(e) => setCv({ ...cv, [k]: e.target.value })}>{OPT[k].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>)}
            <button className="btn btn-primary" onClick={() => run("cvss", cv)}>Score</button></div>
          {out?.score !== undefined && out.vector && <div className="mt-3 space-y-1 text-sm"><p><b>{out.score}</b> <Badge tone={out.severity === "Critical" || out.severity === "High" ? "bad" : out.severity === "Medium" ? "warn" : "muted"}>{out.severity}</Badge> <span className="font-mono text-xs">{out.vector}</span></p><p>{out.triage}</p><p className="text-xs text-muted">{out.caveat}</p></div>}
        </Section>
      )}

      {tab === "risk" && (
        <div className="space-y-4">
          <Section title="Qualitative risk" note="Likelihood times impact on a 1 to 5 scale.">
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-xs">Likelihood<select className="input block w-36" value={f.lik} onChange={(e) => s("lik")(e.target.value)}>{LEVELS.map((x) => <option key={x}>{x}</option>)}</select></label>
              <label className="text-xs">Impact<select className="input block w-36" value={f.imp} onChange={(e) => s("imp")(e.target.value)}>{IMPACTS.map((x) => <option key={x}>{x}</option>)}</select></label>
              <button className="btn btn-primary" onClick={() => run("risk", { likelihood: f.lik, impact: f.imp })}>Rate</button>
            </div>
            {out?.level && <div className="mt-2 text-sm"><p><b>{out.level}</b> (score {out.score}). {out.treat}</p><ul className="list-disc pl-5 text-xs">{out.options.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
          </Section>
          <Section title="Is a control worth its cost? (annual loss expectancy)" note="Estimates only. Show ranges to the client.">
            <div className="flex flex-wrap items-end gap-2">{([["value", "Asset value ($)"], ["exposure", "Loss per incident (%)"], ["per_year", "Incidents per year"], ["ctrl", "Control cost per year ($)"], ["reduction", "Risk reduced (%)"]] as [string, string][]).map(([k, l]) => <label key={k} className="text-xs">{l}<input className="input block w-32" inputMode="decimal" value={f[k]} onChange={(e) => s(k)(e.target.value)} /></label>)}
              <button className="btn btn-primary" onClick={() => run("ale", { asset_value: f.value, exposure_pct: f.exposure, incidents_per_year: f.per_year, control_cost_per_year: f.ctrl, risk_reduction_pct: f.reduction })}>Calculate</button></div>
            {out?.annual_loss_expectancy !== undefined && <div className="mt-2 space-y-1 text-sm"><p>Single loss ${out.single_loss}. Yearly loss ${out.annual_loss_expectancy}, after the control ${out.ale_after_control}. Net benefit per year <b>${out.net_benefit_per_year}</b> {out.worth_it ? <Badge tone="ok">worth it</Badge> : <Badge tone="warn">not clearly worth it</Badge>}</p><p className="text-xs text-muted">{out.how}</p></div>}
          </Section>
          {ref && <Section title="Risk register template"><pre className="overflow-auto whitespace-pre rounded bg-panel2 p-2 text-xs">{ref.register}</pre><div className="mt-2"><Copy text={ref.register} /></div></Section>}
        </div>
      )}

      {tab === "scope" && (
        <Section title="Penetration test authorization and scope" note="Fills a template to review with the client and a lawyer. Never test before it is signed.">
          <div className="grid gap-2 sm:grid-cols-2">{([["client", "Client name"], ["start", "Start date and time"], ["end", "End date and time"]] as [string, string][]).map(([k, l]) => <label key={k} className="text-xs">{l}<input className="input block w-full" value={f[k]} onChange={(e) => s(k)(e.target.value)} /></label>)}</div>
          {([["systems", "Systems in scope (exact IPs, hostnames, apps)"], ["testing", "Testing allowed"], ["excl", "Out of scope"]] as [string, string][]).map(([k, l]) => <label key={k} className="mt-2 block text-xs">{l}<textarea className="field block h-16 w-full" value={f[k]} onChange={(e) => s(k)(e.target.value)} /></label>)}
          <button className="btn btn-primary mt-2" onClick={() => run("scope", { client: f.client, systems: f.systems, start: f.start, end: f.end, testing: f.testing, exclusions: f.excl })}>Fill the template</button>
          {out?.text && <div className="mt-3 space-y-2"><p className="text-xs text-red-600">{out.warning}</p><pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2 text-xs">{out.text}</pre><Copy text={out.text} /><ul className="list-disc space-y-1 pl-5 text-xs">{out.checks.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
        </Section>
      )}

      {tab === "owasp" && ref && <Section title="OWASP Top 10 web risks" note={ref.owasp_note}><ul className="space-y-2 text-sm">{ref.owasp.map((o: R) => <li key={o.id} className="rounded border border-line p-2"><b>{o.id} {o.name}</b>: {o.what}<p className="text-xs"><b>Check (in your own lab or an authorized test):</b> {o.test}</p><p className="text-xs"><b>Fix:</b> {o.fix}</p></li>)}</ul></Section>}
      {tab === "attack" && ref && <Section title="How attacks unfold (MITRE ATT&CK style stages)" note="Use it to place an alert in the chain and pick defenses. See attack.mitre.org for the full matrix."><ul className="space-y-2 text-sm">{ref.attack.map((o: R) => <li key={o.tactic} className="rounded border border-line p-2"><b>{o.tactic}</b>: {o.ex}<p className="text-xs"><b>Defend:</b> {o.defend}</p></li>)}</ul></Section>}

      {tab === "time" && (
        <Section title="Build a timeline from log lines" note="Paste lines with timestamps from several logs. It sorts them and shows gaps. Work on copies.">
          <textarea className="field h-32 w-full font-mono text-xs" aria-label="Log lines" value={f.log} onChange={(e) => s("log")(e.target.value)} />
          <button className="btn btn-primary mt-2" onClick={() => run("timeline", { text: f.log })}>Sort into a timeline</button>
          {out?.events && <div className="mt-3 space-y-2 text-sm"><p className="text-xs">{out.count} events over {out.span_minutes} minutes. {out.skipped_lines ? `${out.skipped_lines} lines had no readable time.` : ""}</p>{out.gaps.map((g: string) => <p key={g} className="text-xs"><Badge tone="warn">gap</Badge> {g}</p>)}
            <ol className="max-h-72 space-y-1 overflow-auto font-mono text-xs">{out.events.map((e: R, i: number) => <li key={i}>{e.time} {e.gap_s >= 60 ? `(+${Math.round(e.gap_s / 60)} min)` : ""} {e.line}</li>)}</ol>
            <ul className="list-disc space-y-1 pl-5 text-xs">{out.reminders.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
        </Section>
      )}

      {tab === "rule" && (
        <Section title="Explain an IDS rule (Suricata or Snort)" note="Paste one rule. It explains each part in plain words. Test new rules in alert-only mode.">
          <textarea className="field h-24 w-full font-mono text-xs" aria-label="Rule" value={f.rule} onChange={(e) => s("rule")(e.target.value)} />
          <button className="btn btn-primary mt-2" onClick={() => run("rule", { rule: f.rule })}>Explain</button>
          {out?.options && <div className="mt-3 space-y-2 text-sm"><p className="font-semibold">{out.summary}</p><ul className="space-y-1 text-xs">{out.options.map((o: R, i: number) => <li key={i}><span className="font-mono">{o.keyword}{o.value ? `: ${o.value}` : ""}</span> <span className="text-muted">{o.means}</span></li>)}</ul>{out.warnings.map((w: string) => <p key={w} className="text-xs"><Badge tone="warn">note</Badge> {w}</p>)}<ul className="list-disc pl-5 text-xs">{out.tuning.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
        </Section>
      )}

      {tab === "check" && ref && (
        <Section title="Assessment checklists" note="Starting lists to gather information. They are not audits or certifications.">
          <div className="flex flex-wrap items-end gap-2"><label className="text-xs">Checklist<select className="input block w-80" value={kind} onChange={(e) => setKind(e.target.value)}>{Object.entries(ref.checklists).map(([k, v]) => <option key={k} value={k}>{String(v)}</option>)}</select></label><button className="btn btn-primary" onClick={load}>Show</button></div>
          {out?.sections && <div className="mt-3 space-y-3 text-sm"><p className="text-xs text-muted">{out.caveat}</p>{out.sections.map((sec: R) => <div key={sec.h}><p className="font-semibold">{sec.h}</p><ul className="list-disc space-y-1 pl-5">{sec.items.map((i: string) => <li key={i}>{i}</li>)}</ul></div>)}<Copy text={out.sections.map((sec: R) => `${sec.h}\n${sec.items.map((i: string) => `- ${i}`).join("\n")}`).join("\n\n")} /></div>}
        </Section>
      )}
    </section>
  );
}
