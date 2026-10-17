"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Tabs, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "email", label: "Email authentication" }, { id: "m365", label: "Microsoft 365 and Intune" }, { id: "people", label: "Onboarding and offboarding" }, { id: "scripts", label: "Scripts" }, { id: "itil", label: "Priority, SLA and change" }, { id: "stop", label: "Blue screen codes" }, { id: "patch", label: "Patch policy" }];

function Copy({ text }: { text: string }) {
  const [d, setD] = useState(false);
  return <button className="btn" onClick={async () => { try { await navigator.clipboard.writeText(text); setD(true); setTimeout(() => setD(false), 2000); } catch { /* select instead */ } }}>{d ? "Copied" : "Copy"}</button>;
}
const tone = (s: string) => (s === "high" ? "bad" : s === "medium" ? "warn" : "muted") as "bad" | "warn" | "muted";

/** Advanced IT admin helpers: email authentication check, Microsoft 365 and Intune guidance, runbooks, script review, ITIL helpers, stop codes. Reference and local checks only. */
export function ItAdminLab() {
  const [tab, setTab] = useState("email");
  const [ref, setRef] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [out, setOut] = useState<R | null>(null);
  const [f, setF] = useState<Record<string, string>>({ spf: "v=spf1 include:spf.protection.outlook.com ~all", dmarc: "v=DMARC1; p=none", dkim: "", name: "", role: "", extras: "", script: 'Get-ChildItem C:\\Temp -Recurse | Remove-Item -Recurse -Force', impact: "medium", urgency: "medium", pct: "99.9", days: "30", code: "irql not less" });
  const [kind, setKind] = useState("onboard");
  const s = (k: string) => (v: string) => setF((x) => ({ ...x, [k]: v }));
  useEffect(() => { if (["m365", "scripts", "itil", "patch"].includes(tab) && !ref) getJson<R>("/api/itadmin/reference").then(setRef).catch((e) => setErr(errMsg(e, "Couldn't load the reference."))); }, [tab, ref]);
  const run = async (path: string, body: unknown) => { setErr(null); try { setOut(await postJson<R>(`/api/itadmin/${path}`, body)); } catch (e) { setOut(null); setErr(errMsg(e, "Check what you entered.")); } };
  return (
    <section className="card space-y-3 p-4" aria-label="IT admin lab">
      <h2 className="text-base font-semibold">IT administration: email security, Microsoft 365, Intune, scripts, ITIL and blue screens</h2>
      <p className="text-xs text-muted">Reference and local checks. Nothing connects to a client&apos;s tenant, runs a script or sends mail. Never paste passwords.</p>
      <Tabs tabs={TABS} value={tab} onChange={(t) => { setTab(t); setOut(null); setErr(null); }} label="IT admin lab" />
      {err && <ErrorBanner message={err} />}

      {tab === "email" && (
        <Section title="Check SPF, DKIM and DMARC records" note="Paste the TXT records from your DNS host or nslookup. Nothing is looked up online.">
          <div className="grid gap-2">
            <label className="text-xs">SPF (starts v=spf1)<input className="input block w-full font-mono" value={f.spf} onChange={(e) => s("spf")(e.target.value)} /></label>
            <label className="text-xs">DMARC (_dmarc record, starts v=DMARC1)<input className="input block w-full font-mono" value={f.dmarc} onChange={(e) => s("dmarc")(e.target.value)} /></label>
            <label className="text-xs">DKIM (selector record, starts v=DKIM1)<input className="input block w-full font-mono" value={f.dkim} onChange={(e) => s("dkim")(e.target.value)} /></label>
          </div>
          <button className="btn btn-primary mt-2" onClick={() => run("email-auth", { spf: f.spf, dmarc: f.dmarc, dkim: f.dkim })}>Check</button>
          {out?.findings && (
            <div className="mt-3 space-y-2 text-sm">
              {out.findings.map((x: R, i: number) => <div key={i} className="rounded border border-line p-2"><Badge tone={tone(x.severity)}>{x.severity}</Badge> {x.problem}<p className="text-xs"><b>Fix:</b> {x.fix}</p></div>)}
              {out.good.map((x: string) => <p key={x} className="text-xs"><Badge tone="ok">ok</Badge> {x}</p>)}
              <ol className="list-decimal space-y-1 pl-5 text-xs">{out.steps.map((x: string) => <li key={x}>{x}</li>)}</ol>
            </div>
          )}
        </Section>
      )}

      {tab === "m365" && ref && (
        <div className="space-y-4">
          <Section title="Secure baseline for a small tenant"><ol className="list-decimal space-y-1 pl-5 text-sm">{ref.m365.baseline.map((x: string) => <li key={x}>{x}</li>)}</ol></Section>
          <Section title="Which plan"><ul className="space-y-1 text-sm">{ref.m365.licensing.map((p: R) => <li key={p.plan}><b>{p.plan}</b>: {p.for}. <span className="text-muted">{p.note}</span></li>)}</ul></Section>
          <Section title="Common tasks"><ul className="space-y-1 text-sm">{ref.m365.common_tasks.map((p: R) => <li key={p.task}><b>{p.task}:</b> {p.how}</li>)}</ul></Section>
          <Section title="Intune and device management"><ol className="list-decimal space-y-1 pl-5 text-sm">{ref.m365.intune.map((x: string) => <li key={x}>{x}</li>)}</ol></Section>
        </div>
      )}

      {tab === "people" && (
        <Section title="Onboarding and offboarding runbook" note="Generates a checklist you can copy into the job notes.">
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-xs">Type<select className="input block w-36" value={kind} onChange={(e) => setKind(e.target.value)}><option value="onboard">Onboard</option><option value="offboard">Offboard</option></select></label>
            <label className="text-xs">Name<input className="input block w-40" value={f.name} onChange={(e) => s("name")(e.target.value)} /></label>
            <label className="text-xs">Role<input className="input block w-40" value={f.role} onChange={(e) => s("role")(e.target.value)} /></label>
            <label className="text-xs">Extra item<input className="input block w-56" value={f.extras} onChange={(e) => s("extras")(e.target.value)} /></label>
            <button className="btn btn-primary" onClick={() => run("lifecycle", { kind, name: f.name, role: f.role, extras: f.extras })}>Create checklist</button>
          </div>
          {out?.steps && !out.findings && out.kind && (
            <div className="mt-3 space-y-2 text-sm"><ol className="list-decimal space-y-1 pl-5">{out.steps.map((x: string) => <li key={x}>{x}</li>)}</ol><p className="text-xs text-muted">{out.caution}</p><Copy text={out.steps.map((x: string, i: number) => `${i + 1}. ${x}`).join("\n")} /></div>
          )}
        </Section>
      )}

      {tab === "scripts" && ref && (
        <div className="space-y-4">
          <Section title="Review a script before you run it" note="Paste PowerShell, Bash or batch. It flags risky patterns. The text is never run.">
            <textarea className="field h-32 w-full font-mono text-xs" aria-label="Script to review" value={f.script} onChange={(e) => s("script")(e.target.value)} />
            <button className="btn btn-primary mt-2" onClick={() => run("script-review", { text: f.script })}>Review</button>
            {out?.findings && out.habits && (
              <div className="mt-3 space-y-2 text-sm">
                <p className="text-xs">High {out.counts.high} · Medium {out.counts.medium} · Low {out.counts.low}</p>
                {out.findings.map((x: R, i: number) => <div key={i} className="rounded border border-line p-2"><Badge tone={tone(x.severity)}>{x.severity}</Badge> line {x.line}: {x.problem}<p className="font-mono text-xs text-muted">{x.snippet}</p><p className="text-xs"><b>Fix:</b> {x.fix}</p></div>)}
                <ul className="list-disc space-y-1 pl-5 text-xs">{out.habits.map((x: string) => <li key={x}>{x}</li>)}</ul><p className="text-xs text-muted">{out.caveat}</p>
              </div>
            )}
          </Section>
          <Section title="Snippet library" note="Read-only ones are safe to run for looking. Anything marked as changing something needs a backup and approval.">
            <div className="space-y-2">{ref.snippets.map((x: R) => (
              <div key={x.title} className="rounded border border-line p-2"><div className="flex items-center justify-between gap-2"><span className="text-sm font-semibold">{x.title}</span><span className="flex items-center gap-2"><Badge tone={x.safe.startsWith("Read") ? "ok" : "warn"}>{x.safe.split(":")[0]}</Badge><Copy text={x.text} /></span></div>
                <pre className="mt-1 overflow-auto whitespace-pre rounded bg-panel2 p-2 text-xs">{x.text}</pre>{!x.safe.startsWith("Read") && <p className="text-xs text-muted">{x.safe}</p>}</div>
            ))}</div>
          </Section>
        </div>
      )}

      {tab === "itil" && ref && (
        <div className="space-y-4">
          <Section title="Ticket priority" note="Impact is how many people or how much money. Urgency is how soon.">
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-xs">Impact<select className="input block w-28" value={f.impact} onChange={(e) => s("impact")(e.target.value)}><option>high</option><option>medium</option><option>low</option></select></label>
              <label className="text-xs">Urgency<select className="input block w-28" value={f.urgency} onChange={(e) => s("urgency")(e.target.value)}><option>high</option><option>medium</option><option>low</option></select></label>
              <button className="btn btn-primary" onClick={() => run("priority", { impact: f.impact, urgency: f.urgency })}>Get priority</button>
            </div>
            {out?.priority && <p className="mt-2 text-sm"><b>{out.priority}</b>: respond within {out.respond_within}, resolve within {out.resolve_within}. <span className="text-xs text-muted">{out.how}</span></p>}
          </Section>
          <Section title="How much downtime does an SLA allow?">
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-xs">Availability %<input className="input block w-28" inputMode="decimal" value={f.pct} onChange={(e) => s("pct")(e.target.value)} /></label>
              <label className="text-xs">Days<input className="input block w-24" inputMode="numeric" value={f.days} onChange={(e) => s("days")(e.target.value)} /></label>
              <button className="btn btn-primary" onClick={() => run("sla", { available_pct: f.pct, window_days: f.days })}>Calculate</button>
            </div>
            {out?.allowed_downtime_minutes !== undefined && <p className="mt-2 text-sm">{out.allowed_downtime_minutes} minutes ({out.allowed_downtime_hours} hours) of downtime allowed. <span className="text-xs text-muted">{out.note}</span></p>}
          </Section>
          <Section title="Change request template"><pre className="overflow-auto whitespace-pre rounded bg-panel2 p-2 text-xs">{ref.change_template}</pre><div className="mt-2"><Copy text={ref.change_template} /></div></Section>
        </div>
      )}

      {tab === "stop" && (
        <Section title="Blue screen stop code lookup" note="Type a stop code or part of it, like IRQL or CRITICAL_PROCESS.">
          <div className="flex flex-wrap gap-2"><input className="input min-w-64 flex-1" aria-label="Stop code" value={f.code} onChange={(e) => s("code")(e.target.value)} /><button className="btn btn-primary" onClick={() => run("stop-code", { code: f.code })}>Look up</button></div>
          {out?.advice && (
            <div className="mt-3 space-y-2 text-sm">
              {out.matches.map((m: R) => <div key={m.code} className="rounded border border-line p-2"><p className="font-semibold">{m.code}</p><p>{m.meaning}</p><p className="text-xs"><b>Usual causes:</b> {m.usual_causes}</p><p className="text-xs"><b>First steps:</b> {m.first_steps}</p></div>)}
              <p className="text-xs text-muted">{out.advice}</p>
            </div>
          )}
        </Section>
      )}

      {tab === "patch" && ref && <Section title="Patch management policy for a small client"><ol className="list-decimal space-y-1 pl-5 text-sm">{ref.patch_policy.map((x: string) => <li key={x}>{x}</li>)}</ol></Section>}
    </section>
  );
}
