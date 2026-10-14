"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, errMsg } from "./kit";
import { Lesson } from "./analysisKit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;

export function HoneypotTab() {
  const [t, setT] = useState(""); const [res, setRes] = useState<R | null>(null); const [ref, setRef] = useState<R | null>(null); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>("/api/honeypot/reference").then(setRef).catch(() => undefined); }, []);
  const go = () => { setErr(null); postJson<R>("/api/honeypot/analyze", { text: t }).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "Could not read that log.")); }); };
  const top = (rows: R[] | undefined, label: string) => <Table head={[label, "Count"]} rows={(rows ?? []).map((x) => [x.value, x.count])} caption={label} />;
  return (
    <div className="space-y-4">
      <Section title="Honeypot log reader (Cowrie)" note="Paste cowrie.json lines (best) or cowrie.log text. Nothing is run, fetched or looked up; URLs are shown defanged so they can't be clicked by accident. Use your own honeypot's logs.">
        <div className="mb-2"><button className="btn" onClick={() => setT(ref?.sample ?? "")}>Load sample log</button></div>
        <Field label="Log text"><textarea className="field font-mono" rows={8} value={t} onChange={(e) => setT(e.target.value)} aria-label="Cowrie log text" /></Field>
        <div className="mt-2"><button className="btn btn-primary" onClick={go}>Analyse log</button></div>
        {err && <ErrorBanner message={err} />}
        {res && <div className="mt-3 space-y-3">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5"><Stat label="Events" value={String(res.events)} /><Stat label="Login attempts" value={String(res.login_attempts)} /><Stat label="Succeeded" value={String(res.logins_succeeded)} /><Stat label="Unique IPs" value={String(res.unique_ips)} /><Stat label="Format" value={res.format} /></div>
          {(res.findings as R[]).map((f) => <p key={f.title} className="rounded border border-line px-3 py-2 text-sm"><Badge tone={f.severity === "high" ? "bad" : f.severity === "medium" ? "warn" : "muted"}>{f.severity}</Badge> <strong>{f.title}</strong>. {f.detail}</p>)}
          <div className="grid gap-3 md:grid-cols-2">{top(res.top_ips, "Top source IPs")}{top(res.top_usernames, "Top usernames")}{top(res.top_passwords, "Top passwords")}{top(res.top_pairs, "Top user/password pairs")}</div>
          <Table head={["Command", "Count", "Classes"]} rows={(res.top_commands as R[]).map((x) => [<code key={x.value}>{x.value}</code>, x.count, (x.classes as string[]).join(", ") || "-"])} caption="Commands typed" />
          {(res.command_classes as R[]).length > 0 && <Table head={["Class", "Seen", "Meaning"]} rows={(res.command_classes as R[]).map((x) => [x.class, x.count, x.meaning])} caption="Command classes" />}
          {(res.urls_defanged as R[]).length > 0 && <Table head={["URL (defanged)", "Count"]} rows={(res.urls_defanged as R[]).map((x) => [<code key={x.value}>{x.value}</code>, x.count])} caption="URLs" />}
          {(res.by_hour as R[]).length > 0 && <p className="text-sm">Events by hour: {(res.by_hour as R[]).map((x) => `${x.hour}h ${x.count}`).join(", ")}.</p>}
          <Lesson text={res.lesson} /><p className="text-xs text-muted">{res.limit}</p>
        </div>}
      </Section>
      {ref && <Section title="Cowrie files, safety and slips in the posters">
        <Table head={["File", "What"]} rows={(ref.files as R[]).map((x) => [<code key={x.file}>{x.file}</code>, x.what])} caption="Cowrie files" />
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{(ref.safety as string[]).map((x) => <li key={x}>{x}</li>)}</ul>
        <h4 className="mt-3 text-sm font-semibold">Mistakes seen in the source posters</h4>
        <ul className="list-disc space-y-1 pl-5 text-sm">{(ref.slips as string[]).map((x) => <li key={x}>{x}</li>)}</ul>
        <p className="mt-2 text-xs text-muted">Not built: {(ref.not_built as string[]).join(" ")}</p>
      </Section>}
    </div>
  );
}
