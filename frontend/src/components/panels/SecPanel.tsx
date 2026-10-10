"use client";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { ApiError, deleteJson, getJson, patchJson, postFile, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";

const TABS = [
  { id: "audit", label: "Self-audit" }, { id: "logs", label: "Log analysis" }, { id: "web", label: "Web checks" },
  { id: "ports", label: "Local ports" }, { id: "crypto", label: "Crypto labs" }, { id: "incident", label: "Incidents" },
];

export function SecPanel({ tab, onTab }: { tab: string; onTab: (t: string) => void }) {
  return (
    <div className="space-y-4">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">
        Defensive tools for things you own. Web checks only work on public sites; offensive tools are explained in the Tool map, not built.
      </p>
      <Tabs tabs={TABS} value={tab} onChange={onTab} label="Cybersecurity tools" />
      {tab === "audit" && <AuditTab />}
      {tab === "logs" && <LogsTab />}
      {tab === "web" && <WebTab />}
      {tab === "ports" && <PortsTab />}
      {tab === "crypto" && <CryptoTab />}
      {tab === "incident" && <IncidentTab />}
    </div>
  );
}

const lvl = (s: string): "ok" | "warn" | "bad" | "muted" => (s === "ok" ? "ok" : s === "warn" ? "warn" : s === "fail" ? "bad" : "muted");
const sev = (s: string): "ok" | "warn" | "bad" | "muted" => (s === "critical" || s === "high" ? "bad" : s === "medium" ? "warn" : "muted");

// ---------------------------------------------------------------- self-audit
interface AuditItem { id: string; status: string; title: string; detail: string; fix: string }
interface Audit { items: AuditItem[]; score: { ok: number; total: number; pct: number }; fails: number; warns: number; note: string }

function AuditTab() {
  const [a, setA] = useState<Audit | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  useEffect(() => {
    const ctl = new AbortController();
    getJson<Audit>("/api/security/audit", ctl.signal).then(setA).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't run the audit.")); });
    return () => ctl.abort();
  }, [ver]);
  if (!a) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Running checks…</p>;
  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Score" value={`${a.score.pct}%`} sub={`${a.score.ok} of ${a.score.total} checks passed`} />
        <Stat label="Failing" value={String(a.fails)} />
        <Stat label="To review" value={String(a.warns)} />
      </div>
      <Section title="Checks" note={a.note}>
        <ul className="space-y-2">
          {a.items.map((i) => (
            <li key={i.id} className="rounded border border-line p-2 text-sm">
              <div className="flex flex-wrap items-center gap-2"><Badge tone={lvl(i.status)}>{i.status}</Badge><span className="font-medium">{i.title}</span></div>
              {i.detail && <p className="mt-1 text-xs text-muted">{i.detail}</p>}
              {i.fix && <p className="mt-1 text-xs">Fix: <code>{i.fix}</code></p>}
            </li>
          ))}
        </ul>
        <button className="btn mt-3" onClick={() => setVer((v) => v + 1)}>Run again</button>
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- logs (also used by the /logs page)
interface Finding { id: string; severity: string; title: string; detail: string; evidence: string[]; advice: string }
interface LogResult {
  info: { lines: number; truncated: boolean; kinds: Record<string, number> }; range: string[] | null; status_classes: Record<string, number>;
  top_ips: { ip: string; events: number; failed_logins: number }[]; timeline: { hour: string; events: number; problems: number }[]; findings: Finding[]; caveat: string;
}
interface LogHit { ts: string | null; kind: string; ip: string | null; line: string }

export function LogsTab() {
  const [text, setText] = useState("");
  const [res, setRes] = useState<LogResult | null>(null);
  const [hits, setHits] = useState<LogHit[] | null>(null);
  const [q, setQ] = useState("");
  const [ip, setIp] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const analyze = async () => {
    setBusy(true); setErr(null); setHits(null);
    try { setRes(await postJson<LogResult>("/api/security/logs/analyze", { text })); } catch (e) { setErr(errMsg(e, "Couldn't analyse that log.")); } finally { setBusy(false); }
  };
  const sample = async () => {
    setErr(null);
    try { const s = await getJson<{ text: string }>("/api/security/logs/sample"); setText(s.text); setRes(null); setHits(null); } catch (e) { setErr(errMsg(e, "Couldn't load the sample.")); }
  };
  const upload = async (f: File | undefined) => {
    if (!f) return;
    setBusy(true); setErr(null); setHits(null);
    try { setRes(await postFile<LogResult>("/api/security/logs/analyze-file", f)); setText(""); } catch (e) { setErr(errMsg(e, "Couldn't read that file.")); } finally { setBusy(false); }
  };
  const search = async () => {
    setErr(null);
    try { setHits((await postJson<{ matches: LogHit[] }>("/api/security/logs/search", { text, query: q, ip, limit: 100 })).matches); } catch (e) { setErr(errMsg(e, "Search failed.")); }
  };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Paste a log" note="Understands Linux auth/syslog lines, web access logs and generic timestamped lines. Nothing is stored or sent anywhere.">
        <textarea className="field h-40 w-full font-mono text-xs" aria-label="Log text" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste log lines here…" />
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <button className="btn btn-primary" disabled={busy || !text.trim()} onClick={analyze}>{busy ? "Analysing…" : "Analyse"}</button>
          <button className="btn" onClick={sample}>Load a practice log</button>
          <label className="btn cursor-pointer">Upload a file<input type="file" className="sr-only" onChange={(e) => upload(e.target.files?.[0])} /></label>
        </div>
      </Section>
      {res && (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Stat label="Lines read" value={String(res.info.lines)} sub={Object.entries(res.info.kinds).map(([k, v]) => `${k}: ${v}`).join(", ")} />
            <Stat label="Findings" value={String(res.findings.length)} />
            <Stat label="Top address" value={res.top_ips[0]?.ip ?? "—"} sub={res.top_ips[0] ? `${res.top_ips[0].events} events` : ""} />
          </div>
          <Section title="Detections" note={res.caveat}>
            {res.findings.length === 0 && <p className="text-sm text-muted">Nothing matched the rules. That does not prove nothing happened.</p>}
            <ul className="space-y-3">
              {res.findings.map((f) => (
                <li key={f.id} className="rounded border border-line p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-2"><Badge tone={sev(f.severity)}>{f.severity}</Badge><span className="font-medium">{f.title}</span></div>
                  <p className="mt-1 text-xs text-muted">{f.detail}</p>
                  <pre className="mt-2 overflow-x-auto rounded bg-panel2 p-2 text-xs">{f.evidence.join("\n")}</pre>
                  <p className="mt-1 text-xs">What to do: {f.advice}</p>
                </li>
              ))}
            </ul>
          </Section>
          <Section title="Busiest addresses">
            <Table head={["Address", "Events", "Failed logins"]} rows={res.top_ips.map((t) => [t.ip, String(t.events), String(t.failed_logins)])} caption="Busiest addresses" />
          </Section>
        </>
      )}
      {text.trim() && (
        <Section title="Search the log">
          <div className="flex flex-wrap items-end gap-2">
            <Field label="Contains"><input className="field" value={q} onChange={(e) => setQ(e.target.value)} /></Field>
            <Field label="Address"><input className="field" value={ip} onChange={(e) => setIp(e.target.value)} /></Field>
            <button className="btn" onClick={search}>Search</button>
          </div>
          {hits && (hits.length === 0 ? <p className="mt-2 text-sm text-muted">No matching lines.</p> :
            <pre className="mt-2 max-h-64 overflow-auto rounded bg-panel2 p-2 text-xs">{hits.map((h) => h.line).join("\n")}</pre>)}
        </Section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- web checks
interface HostFinding { id: string; level: string; title: string; detail?: string; fix?: string }
interface HostReport { host: string; status?: number; error?: string; findings: HostFinding[]; score: { passed: number; total: number; pct: number }; note?: string;
  days_left?: number; issuer?: string; valid_until?: string; tls_version?: string }

function WebTab() {
  const [host, setHost] = useState("");
  const [head, setHead] = useState<HostReport | null>(null);
  const [cert, setCert] = useState<HostReport | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true); setErr(null); setHead(null); setCert(null);
    try {
      setHead(await postJson<HostReport>("/api/security/headers", { host }));
      setCert(await postJson<HostReport>("/api/security/cert", { host }));
    } catch (e) { setErr(errMsg(e, "The check failed.")); } finally { setBusy(false); }
  };
  const list = (r: HostReport) => (
    <ul className="space-y-2">
      {r.findings.map((f) => (
        <li key={f.id} className="rounded border border-line p-2 text-sm">
          <div className="flex flex-wrap items-center gap-2"><Badge tone={lvl(f.level)}>{f.level}</Badge><span>{f.title}</span></div>
          {f.detail && <p className="mt-1 text-xs text-muted">{f.detail}</p>}
          {f.fix && <p className="mt-1 text-xs">Fix: {f.fix}</p>}
        </li>
      ))}
    </ul>
  );
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Check a public website" note="Public hosts only. Addresses on your own network, localhost and cloud metadata addresses are refused. Only test sites you own or run.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Host name"><input className="field" placeholder="example.com" value={host} onChange={(e) => setHost(e.target.value)} onKeyDown={(e) => e.key === "Enter" && host.trim() && go()} /></Field>
          <button className="btn btn-primary" disabled={busy || host.trim().length < 3} onClick={go}>{busy ? "Checking…" : "Check"}</button>
        </div>
      </Section>
      {head && <Section title={`Security headers: ${head.score.pct}% (${head.score.passed}/${head.score.total})`} note={head.note}>{list(head)}</Section>}
      {cert && (
        <Section title={cert.error ? "Certificate problem" : `Certificate: ${cert.days_left} days left`} note={cert.note}>
          {cert.error && <p className="mb-2 text-sm">{cert.error}</p>}
          {!cert.error && <p className="mb-2 text-xs text-muted">Issuer {cert.issuer} · valid until {cert.valid_until} · {cert.tls_version}</p>}
          {list(cert)}
        </Section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- local ports
interface PortRes { checked: number; open: { port: number; service: string; note: string }[]; explain: string }
function PortsTab() {
  const [r, setR] = useState<PortRes | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true); setErr(null);
    try { setR(await getJson<PortRes>("/api/security/ports")); } catch (e) { setErr(errMsg(e, "Couldn't check the ports.")); } finally { setBusy(false); }
  };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Which common ports are open on this computer?" note="Checks a fixed list of ports on 127.0.0.1 only. It never scans other machines.">
        <button className="btn btn-primary" disabled={busy} onClick={run}>{busy ? "Checking…" : "Check now"}</button>
      </Section>
      {r && (
        <Section title={`${r.open.length} open of ${r.checked} checked`} note={r.explain}>
          {r.open.length === 0 ? <p className="text-sm text-muted">None of the listed ports accepted a connection.</p> :
            <Table head={["Port", "Service", "What to know"]} rows={r.open.map((p) => [String(p.port), p.service, p.note])} caption="Open ports" />}
        </Section>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- crypto labs
interface PwRes { entropy_bits: number; label: string; crack_time: string; issues: string[]; assumption: string; advice: string }
interface TotpRes { code: string; seconds_left: number; explain: string[]; verified?: boolean; note?: string }

function CryptoTab() {
  const [txt, setTxt] = useState("hello");
  const [exp, setExp] = useState("");
  const [hash, setHash] = useState<{ hashes: Record<string, string>; note: string; verify?: { match: boolean; advice: string } } | null>(null);
  const [pw, setPw] = useState("");
  const [pwr, setPwr] = useState<PwRes | null>(null);
  const [gen, setGen] = useState<{ value: string; note: string } | null>(null);
  const [secret, setSecret] = useState<{ secret: string; uri: string; note: string } | null>(null);
  const [totp, setTotp] = useState<TotpRes | null>(null);
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const wrap = async (f: () => Promise<void>, m: string) => { setErr(null); try { await f(); } catch (e) { setErr(errMsg(e, m)); } };
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Hash lab">
        <textarea className="field w-full" rows={2} aria-label="Text to hash" value={txt} onChange={(e) => setTxt(e.target.value)} />
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <Field label="Expected hash (optional, to verify)"><input className="field w-72 max-w-full" value={exp} onChange={(e) => setExp(e.target.value)} /></Field>
          <button className="btn btn-primary" onClick={() => wrap(async () => setHash(await postJson("/api/security/hash", { text: txt, algos: ["sha256", "sha1", "md5"], expected: exp || undefined })), "Couldn't hash that.")}>Hash</button>
        </div>
        {hash && (
          <div className="mt-2 space-y-1 text-xs">
            {Object.entries(hash.hashes).map(([k, v]) => <div key={k} className="break-all"><b>{k}</b> <code>{v}</code></div>)}
            {hash.verify && <p className={hash.verify.match ? "text-emerald-600" : "text-red-600"}>{hash.verify.advice}</p>}
            <p className="text-muted">{hash.note}</p>
          </div>
        )}
      </Section>
      <Section title="Password strength" note="Checked on your own machine; not logged or stored. Don't type a password you actually use into tools you don't trust.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Try a password"><input className="field" type="text" autoComplete="off" value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
          <button className="btn btn-primary" disabled={!pw} onClick={() => wrap(async () => setPwr(await postJson("/api/security/password/check", { password: pw })), "Couldn't check that.")}>Check</button>
          <button className="btn" onClick={() => wrap(async () => setGen(await getJson("/api/security/password/generate?kind=passphrase&length=6")), "Couldn't generate one.")}>Make a passphrase</button>
        </div>
        {pwr && (
          <div className="mt-2 space-y-1 text-sm">
            <p><b>{pwr.label}</b> · about {pwr.entropy_bits} bits · estimated crack time {pwr.crack_time}</p>
            {pwr.issues.length > 0 && <ul className="list-disc pl-5 text-xs">{pwr.issues.map((i) => <li key={i}>{i}</li>)}</ul>}
            <p className="text-xs text-muted">{pwr.assumption}</p>
          </div>
        )}
        {gen && <div className="mt-2 text-sm"><code className="break-all">{gen.value}</code><p className="text-xs text-muted">{gen.note}</p></div>}
      </Section>
      <Section title="Two-factor code lab (TOTP)" note="A practice secret only. Never reuse it for a real account.">
        <div className="flex flex-wrap items-end gap-2">
          <button className="btn" onClick={() => wrap(async () => { setSecret(await getJson("/api/security/totp/new")); setTotp(null); setCode(""); }, "Couldn't make a secret.")}>New practice secret</button>
          {secret && <button className="btn" onClick={() => wrap(async () => setTotp(await postJson("/api/security/totp", { secret: secret.secret })), "Couldn't compute a code.")}>Show current code</button>}
        </div>
        {secret && <p className="mt-2 break-all text-xs">Secret <code>{secret.secret}</code></p>}
        {totp && (
          <div className="mt-2 text-sm">
            <p>Current code <code className="text-lg font-bold">{totp.code}</code> ({totp.seconds_left}s left)</p>
            <ol className="mt-1 list-decimal pl-5 text-xs text-muted">{totp.explain.map((e) => <li key={e}>{e.replace(/^\d+\.\s*/, "")}</li>)}</ol>
          </div>
        )}
        {secret && (
          <div className="mt-2 flex flex-wrap items-end gap-2">
            <Field label="Check a code"><input className="field w-32" inputMode="numeric" value={code} onChange={(e) => setCode(e.target.value)} /></Field>
            <button className="btn" disabled={!code} onClick={() => wrap(async () => setTotp(await postJson("/api/security/totp", { secret: secret.secret, code })), "Couldn't check that code.")}>Check</button>
            {totp?.verified !== undefined && <Badge tone={totp.verified ? "ok" : "bad"}>{totp.verified ? "accepted" : "rejected"}</Badge>}
          </div>
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------- incidents
interface Incident { id: number; title: string; category: string; category_label: string; severity: string; status: string; detected_at: string; timeline: { at: string; text: string }[]; checklist: { text: string; done: boolean }[]; hours_to_resolve: number | null }
interface IncList { incidents: Incident[]; stats: { open: number; total: number; mean_hours_to_resolve: number | null }; categories: { id: string; label: string }[] }

function IncidentTab() {
  const [d, setD] = useState<IncList | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [ver, setVer] = useState(0);
  const [title, setTitle] = useState("");
  const [cat, setCat] = useState("credential");
  const [sevr, setSevr] = useState("medium");
  const [note, setNote] = useState<Record<number, string>>({});
  useEffect(() => {
    const ctl = new AbortController();
    getJson<IncList>("/api/security/incidents", ctl.signal).then(setD).catch((e) => { if (!ctl.signal.aborted) setErr(errMsg(e, "Couldn't load incidents.")); });
    return () => ctl.abort();
  }, [ver]);
  const act = useCallback(async (f: () => Promise<unknown>) => {
    setErr(null);
    try { await f(); setVer((v) => v + 1); } catch (e) { setErr(e instanceof ApiError || e instanceof Error ? e.message : "That didn't work."); }
  }, []);
  if (!d) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-4">
      {err && <ErrorBanner message={err} />}
      <div className="grid gap-3 sm:grid-cols-3">
        <Stat label="Open" value={String(d.stats.open)} /><Stat label="Total" value={String(d.stats.total)} />
        <Stat label="Mean hours to resolve" value={d.stats.mean_hours_to_resolve == null ? "—" : String(d.stats.mean_hours_to_resolve)} />
      </div>
      <Section title="Log an incident" note="Each category comes with a response checklist. Keep evidence before you clean up.">
        <div className="flex flex-wrap items-end gap-2">
          <Field label="Title"><input className="field w-64 max-w-full" value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
          <Field label="Category"><select className="field" value={cat} onChange={(e) => setCat(e.target.value)}>{d.categories.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}</select></Field>
          <Field label="Severity"><select className="field" value={sevr} onChange={(e) => setSevr(e.target.value)}>{["low", "medium", "high", "critical"].map((s) => <option key={s}>{s}</option>)}</select></Field>
          <button className="btn btn-primary" disabled={!title.trim()} onClick={() => act(async () => { await postJson("/api/security/incidents", { title, category: cat, severity: sevr }); setTitle(""); })}>Open incident</button>
        </div>
      </Section>
      {d.incidents.map((i) => (
        <section key={i.id} className="card p-4">
          <div className="flex flex-wrap items-center gap-2">
            <h3 className="text-sm font-semibold">{i.title}</h3><Badge tone={sev(i.severity)}>{i.severity}</Badge><Badge>{i.category_label}</Badge>
            <select className="field ml-auto" aria-label={`Status of ${i.title}`} value={i.status} onChange={(e) => act(() => patchJson(`/api/security/incidents/${i.id}`, { status: e.target.value }))}>
              {["open", "investigating", "contained", "resolved"].map((s) => <option key={s}>{s}</option>)}
            </select>
            <button className="btn" onClick={() => act(() => deleteJson(`/api/security/incidents/${i.id}`))}>Delete</button>
          </div>
          <ul className="mt-2 space-y-1 text-sm">
            {i.checklist.map((c, n) => (
              <li key={n}><label className="flex items-start gap-2"><input type="checkbox" checked={c.done} onChange={(e) => act(() => patchJson(`/api/security/incidents/${i.id}`, { tick: { index: n, done: e.target.checked } }))} /><span className={c.done ? "text-muted line-through" : ""}>{c.text}</span></label></li>
            ))}
          </ul>
          <div className="mt-2 flex flex-wrap items-end gap-2">
            <Field label="Add to the timeline"><input className="field w-72 max-w-full" value={note[i.id] ?? ""} onChange={(e) => setNote({ ...note, [i.id]: e.target.value })} /></Field>
            <button className="btn" disabled={!(note[i.id] ?? "").trim()} onClick={() => act(async () => { await patchJson(`/api/security/incidents/${i.id}`, { note: note[i.id] }); setNote({ ...note, [i.id]: "" }); })}>Add</button>
          </div>
          <details className="mt-2 text-xs"><summary className="cursor-pointer text-muted">Timeline ({i.timeline.length})</summary>
            <ul className="mt-1 space-y-0.5">{i.timeline.map((t, n) => <li key={n}><span className="text-muted">{t.at}</span> {t.text}</li>)}</ul>
          </details>
        </section>
      ))}
    </div>
  );
}
