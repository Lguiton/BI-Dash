"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { deleteJson, getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, Stat, Table, Tabs, errMsg } from "./kit";
import { Lesson, Warn } from "./analysisKit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;
const TABS = [{ id: "map", label: "Objectives" }, { id: "quiz", label: "Practice quiz" }, { id: "drill", label: "Flashcards" }, { id: "sym", label: "Symptom finder" }, { id: "ref", label: "Reference" }, { id: "tools", label: "Tools" }];
const tone = (l: string) => (l === "bad" ? "bad" : l === "warn" ? "warn" : "ok");

function useCall<T = R>() {
  const [res, setRes] = useState<T | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const run = (path: string, body?: unknown, method: "post" | "get" = "post") => {
    setErr(null);
    (method === "get" ? getJson<T>(path) : postJson<T>(path, body)).then(setRes).catch((e) => { setRes(null); setErr(errMsg(e, "That didn't work.")); });
  };
  return { res, err, run };
}
const Out = ({ c }: { c: { err: string | null } }) => (c.err ? <ErrorBanner message={c.err} /> : null);
const In = ({ label, v, set, mode = "decimal" }: { label: string; v: string; set: (s: string) => void; mode?: "decimal" | "text" }) => <Field label={label}><input className="field" inputMode={mode} value={v} onChange={(e) => set(e.target.value)} /></Field>;

export function AplusTab() {
  const [tab, setTab] = useState("map");
  const [data, setData] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const load = () => getJson<R>("/api/aplus").then(setData).catch((e) => setErr(errMsg(e, "Couldn't load the A+ study area.")));
  useEffect(() => { load(); }, []);
  if (!data) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading CompTIA A+…</p>;
  return (
    <section className="card space-y-4 p-4" aria-label="CompTIA A+ study area">
      <h2 className="text-base font-semibold">CompTIA A+ study area (Core 1 220-1201 and Core 2 220-1202)</h2>
      <Lesson text="Rate each objective, practise with scenario questions, drill acronyms and ports, then use the tools. Content is written for this dashboard from the public objectives; it is not CompTIA's exam or a question dump." />
      <Warn items={[data.fine_print]} />
      <Tabs tabs={TABS} value={tab} onChange={setTab} label="A+ study area" />
      {tab === "map" && <MapTab data={data} reload={load} />}
      {tab === "quiz" && <QuizTab data={data} reload={load} />}
      {tab === "drill" && <Drill />}
      {tab === "sym" && <Symptoms method={data.method} />}
      {tab === "ref" && <Reference />}
      {tab === "tools" && <Tools />}
    </section>
  );
}

function MapTab({ data, reload }: { data: R; reload: () => void }) {
  const [exam, setExam] = useState("1");
  const [err, setErr] = useState<string | null>(null);
  const ex = data.exams.find((e: R) => e.exam === exam);
  const objs = data.objectives.filter((o: R) => o.exam === exam);
  const set = (id: string, level: number) => postJson("/api/aplus/level", { objective: id, level }).then(reload).catch((e) => setErr(errMsg(e, "Couldn't save.")));
  return (
    <div className="space-y-3">
      <div className="flex gap-2">{data.exams.map((e: R) => <button key={e.exam} className={`btn ${e.exam === exam ? "btn-primary" : ""}`} onClick={() => setExam(e.exam)}>{e.name} {e.code}: {e.readiness_pct}%</button>)}</div>
      {err && <ErrorBanner message={err} />}
      {ex && <>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Stat label="Readiness" value={`${ex.readiness_pct}%`} />
          <Stat label="Study next" value={ex.study_next} />
          <Stat label="Exam" value={`${ex.questions} Q, ${ex.minutes} min`} />
          <Stat label="Passing" value={ex.pass} />
        </div>
        <Table head={["Domain", "Weight", "Objectives", "Self-rating", "Practice"]} rows={ex.domains.map((d: R) => [d.label, `${d.weight}%`, d.objectives, `${d.self_pct}%`, d.practice_pct === null ? "no answers yet" : `${d.practice_pct}% of ${d.practice_answered}`])} />
        <p className="text-xs text-muted">{data.note}</p>
      </>}
      <Section title="Objectives" note="Rate yourself 0 to 3. The tag says whether the dashboard has a tool for it or it needs real hardware.">
        <Table head={["#", "Objective", "Kind", "Aid", "Q", "Level"]} rows={objs.map((o: R) => [o.number, o.title, o.kind_label, o.aid, o.questions,
          <select key={o.id} className="field" aria-label={`Level for ${o.number}`} value={o.level} onChange={(e) => set(o.id, Number(e.target.value))}>{Object.entries(data.levels).map(([k, v]) => <option key={k} value={k}>{k}: {String(v)}</option>)}</select>])} />
      </Section>
    </div>
  );
}

function QuizTab({ data, reload }: { data: R; reload: () => void }) {
  const [exam, setExam] = useState(""); const [domain, setDomain] = useState(""); const [n, setN] = useState("10");
  const [qs, setQs] = useState<R | null>(null); const [ans, setAns] = useState<Record<string, number>>({});
  const [g, setG] = useState<R | null>(null); const [err, setErr] = useState<string | null>(null);
  const doms = data.exams.filter((e: R) => !exam || e.exam === exam).flatMap((e: R) => e.domains.map((d: R) => ({ ...d, exam: e.exam, name: e.name })));
  const start = () => { setErr(null); setG(null); setAns({}); getJson<R>(`/api/aplus/quiz?exam=${exam}&domain=${domain}&n=${Number(n) || 10}`).then(setQs).catch((e) => setErr(errMsg(e, "Couldn't load questions."))); };
  const grade = () => postJson<R>("/api/aplus/quiz/grade", { answers: ans }).then((r) => { setG(r); reload(); }).catch((e) => setErr(errMsg(e, "Couldn't grade.")));
  const reset = () => deleteJson("/api/aplus/quiz/results").then(reload).catch((e) => setErr(errMsg(e, "Couldn't reset.")));
  const byId: R = {}; (g?.results || []).forEach((r: R) => { byId[r.id] = r; });
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-4">
        <Field label="Exam"><select className="field" value={exam} onChange={(e) => { setExam(e.target.value); setDomain(""); }}><option value="">Both</option>{data.exams.map((e: R) => <option key={e.exam} value={e.exam}>{e.name} {e.code}</option>)}</select></Field>
        <Field label="Domain"><select className="field" value={domain} onChange={(e) => setDomain(e.target.value)}><option value="">All</option>{doms.map((d: R) => <option key={`${d.exam}${d.key}`} value={d.key}>{d.label}</option>)}</select></Field>
        <In label="Questions" v={n} set={setN} />
        <div className="flex items-end gap-2"><button className="btn btn-primary" onClick={start}>New quiz</button><button className="btn" onClick={reset}>Reset results</button></div>
      </div>
      {err && <ErrorBanner message={err} />}
      {qs && <p className="text-xs text-muted">{qs.note} ({qs.available} in this pool)</p>}
      {qs?.questions.map((q: R, i: number) => {
        const r = byId[q.id];
        return (
          <fieldset key={q.id} className="rounded border border-line p-3">
            <legend className="px-1 text-sm font-medium">{i + 1}. {q.q}</legend>
            {q.options.map((o: string, k: number) => (
              <label key={k} className={`flex items-start gap-2 py-1 text-sm ${r && k === r.answer ? "font-semibold" : ""}`}>
                <input type="radio" name={q.id} disabled={!!g} checked={ans[q.id] === k} onChange={() => setAns({ ...ans, [q.id]: k })} /> {o}
              </label>
            ))}
            {r && <p className="mt-1 text-xs">{r.ok ? <Badge tone="ok">right</Badge> : <Badge tone="bad">missed</Badge>} {r.ok ? "" : `Answer: ${r.correct}. `}{r.why} (objective {r.obj})</p>}
          </fieldset>
        );
      })}
      {qs && !g && <button className="btn btn-primary" disabled={Object.keys(ans).length === 0} onClick={grade}>Grade ({Object.keys(ans).length} answered)</button>}
      {g && <p className="text-sm"><b>{g.right} of {g.total} ({g.pct}%).</b> {g.message}</p>}
    </div>
  );
}

function Drill() {
  const [kind, setKind] = useState("acronyms"); const [exam, setExam] = useState("");
  const [d, setD] = useState<R | null>(null); const [i, setI] = useState(0); const [flip, setFlip] = useState(false); const [err, setErr] = useState<string | null>(null);
  const deal = () => { setErr(null); getJson<R>(`/api/aplus/cards?kind=${kind}&n=20&exam=${exam}`).then((r) => { setD(r); setI(0); setFlip(false); }).catch((e) => setErr(errMsg(e, "Couldn't load cards."))); };
  const c = d?.cards[i];
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-4">
        <Field label="Deck"><select className="field" value={kind} onChange={(e) => setKind(e.target.value)}><option value="acronyms">Acronyms</option><option value="ports">Ports</option></select></Field>
        <Field label="Exam"><select className="field" value={exam} onChange={(e) => setExam(e.target.value)}><option value="">Both</option><option value="1">Core 1</option><option value="2">Core 2</option></select></Field>
        <div className="flex items-end"><button className="btn btn-primary" onClick={deal}>Deal 20 cards</button></div>
      </div>
      {err && <ErrorBanner message={err} />}
      {d && c && <>
        <button className="card w-full p-6 text-center text-lg" onClick={() => setFlip(!flip)} aria-label="Flip card">{flip ? c.back : c.front}</button>
        <div className="flex items-center gap-2"><button className="btn" disabled={i === 0} onClick={() => { setI(i - 1); setFlip(false); }}>Back</button><span className="text-sm">{i + 1} of {d.cards.length}</span><button className="btn" disabled={i >= d.cards.length - 1} onClick={() => { setI(i + 1); setFlip(false); }}>Next</button></div>
        <p className="text-xs text-muted">{d.note} ({d.available} cards in this deck)</p>
      </>}
    </div>
  );
}

function Symptoms({ method }: { method: string[] }) {
  const [q, setQ] = useState(""); const [r, setR] = useState<R | null>(null); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>(`/api/aplus/symptoms?q=${encodeURIComponent(q)}`).then(setR).catch((e) => setErr(errMsg(e, "Couldn't search."))); }, [q]);
  return (
    <div className="space-y-3">
      <Section title="The troubleshooting method" note="CompTIA's six steps; the order is tested.">
        <ol className="list-decimal pl-5 text-sm">{method.map((m) => <li key={m}>{m}</li>)}</ol>
      </Section>
      <In label="Search a symptom (for example: no boot, slow, printer)" v={q} set={setQ} mode="text" />
      {err && <ErrorBanner message={err} />}
      {r && <p className="text-xs text-muted">{r.note}</p>}
      {r?.results.length === 0 && <p className="text-sm text-muted">Nothing matches. Try one word.</p>}
      {r?.results.map((s: R, i: number) => (
        <div key={i} className="rounded border border-line p-3 text-sm">
          <p className="font-medium">{s.symptom} <span className="text-xs text-muted">Core {s.exam}, objective {s.obj}</span></p>
          <p className="mt-1"><b>Likely causes:</b> {s.causes.join("; ")}</p>
          <p><b>Check:</b> {s.checks.join("; ")}</p>
        </div>
      ))}
    </div>
  );
}

function Reference() {
  const [r, setR] = useState<R | null>(null); const [topic, setTopic] = useState("network"); const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>("/api/aplus/reference").then(setR).catch((e) => setErr(errMsg(e, "Couldn't load the reference."))); }, []);
  if (!r) return err ? <ErrorBanner message={err} /> : <p className="text-sm text-muted">Loading…</p>;
  return (
    <div className="space-y-3">
      <Field label="Topic"><select className="field" value={topic} onChange={(e) => setTopic(e.target.value)}>{r.topics.map((t: string) => <option key={t}>{t}</option>)}</select></Field>
      {(r.sections[topic] || []).map((s: R) => <Section key={s.title} title={s.title}><Table head={["Item", "What to know"]} rows={s.rows} /></Section>)}
      <Section title="Common ports" note="Ports are the most-tested list on Core 1."><Table head={["Port", "Service", "Transport", "Note"]} rows={r.ports.map((p: R) => [p.port, p.service, p.transport, p.note])} /></Section>
    </div>
  );
}

function Findings({ items }: { items: R[] }) {
  return <ul className="space-y-1 text-sm">{items.map((f, i) => <li key={i}><Badge tone={tone(f.level)}>{f.level}</Badge> {f.message || f.finding}{f.fix ? ` Fix: ${f.fix}` : ""}{f.advice ? ` ${f.advice}` : ""}</li>)}</ul>;
}

function Tools() {
  const [which, setWhich] = useState("ip");
  const opts = [["ip", "IP check"], ["dhcp", "DHCP scope"], ["mail", "Mail records"], ["display", "Display"], ["psu", "Power supply"], ["backup", "Backup plan"], ["script", "Script reviewer"]];
  return (
    <div className="space-y-3">
      <Tabs tabs={opts.map(([id, label]) => ({ id, label }))} value={which} onChange={setWhich} label="A+ tools" />
      {which === "ip" && <IpTool />}{which === "dhcp" && <DhcpTool />}{which === "mail" && <TextTool kind="mail" label="Paste your SPF, DKIM or DMARC TXT records" />}
      {which === "display" && <DisplayTool />}{which === "psu" && <PsuTool />}{which === "backup" && <BackupTool />}{which === "script" && <TextTool kind="script" label="Paste a script to review (it is never run)" />}
    </div>
  );
}

function IpTool() {
  const [a, setA] = useState("169.254.10.5"); const [m, setM] = useState("255.255.255.0"); const [g, setG] = useState("192.168.1.1"); const c = useCall();
  return (
    <Section title="IP address check" note="Tells you what kind of address it is and whether the mask and gateway fit.">
      <div className="grid gap-2 sm:grid-cols-3"><In label="Address" v={a} set={setA} mode="text" /><In label="Mask (optional)" v={m} set={setM} mode="text" /><In label="Gateway (optional)" v={g} set={setG} mode="text" /></div>
      <button className="btn btn-primary mt-2" onClick={() => c.run("/api/aplus/ip", { address: a, mask: m, gateway: g })}>Check</button><Out c={c} />
      {c.res && <div className="mt-2 space-y-1 text-sm"><p>Version {c.res.version}, <b>{c.res.kind}</b>{c.res.network ? `, network ${c.res.network}, ${c.res.usable_hosts} usable hosts, broadcast ${c.res.broadcast}` : ""}</p><ul className="list-disc pl-5">{c.res.notes.map((n: string) => <li key={n}>{n}</li>)}</ul></div>}
    </Section>
  );
}

function DhcpTool() {
  const [net, setNet] = useState("192.168.1.0/24"); const [s, setS] = useState("192.168.1.100"); const [e, setE] = useState("192.168.1.150"); const [ex, setEx] = useState("");
  const [r, setR] = useState("2"); const [d, setD] = useState("40"); const [l, setL] = useState("24"); const c = useCall();
  return (
    <Section title="DHCP scope planner" note="Checks whether the pool is big enough for your devices.">
      <div className="grid gap-2 sm:grid-cols-3"><In label="Network" v={net} set={setNet} mode="text" /><In label="Pool start" v={s} set={setS} mode="text" /><In label="Pool end" v={e} set={setE} mode="text" /><In label="Excluded addresses (comma separated)" v={ex} set={setEx} mode="text" /><In label="Reservations" v={r} set={setR} /><In label="Devices" v={d} set={setD} /><In label="Lease hours" v={l} set={setL} /></div>
      <button className="btn btn-primary mt-2" onClick={() => c.run("/api/aplus/dhcp", { network: net, start: s, end: e, exclusions: ex.split(",").map((x) => x.trim()).filter(Boolean), reservations: Number(r) || 0, devices: Number(d) || 0, lease_hours: Number(l) || 24 })}>Plan</button><Out c={c} />
      {c.res && <div className="mt-2 space-y-1 text-sm"><p>Pool {c.res.pool}, excluded {c.res.excluded}, reserved {c.res.reserved}, <b>{c.res.available} available</b> (mask {c.res.mask}).</p><ul className="list-disc pl-5">{c.res.notes.map((n: string) => <li key={n}>{n}</li>)}</ul><Warn items={[c.res.limit]} /></div>}
    </Section>
  );
}

function TextTool({ kind, label }: { kind: "mail" | "script"; label: string }) {
  const [t, setT] = useState(""); const c = useCall();
  return (
    <Section title={kind === "mail" ? "Mail records checker" : "Script reviewer"} note={kind === "mail" ? "Reads pasted text only; it does not look up live DNS." : "A pattern scan. It never runs the script."}>
      <Field label={label}><textarea className="field min-h-32 font-mono text-xs" value={t} onChange={(e) => setT(e.target.value)} /></Field>
      <button className="btn btn-primary mt-2" disabled={!t.trim()} onClick={() => c.run(`/api/aplus/${kind}`, { text: t })}>Review</button><Out c={c} />
      {c.res && kind === "mail" && <div className="mt-2 space-y-2">{c.res.records.map((r: R, i: number) => <div key={i}><p className="text-sm font-medium">{r.type}</p><p className="break-all font-mono text-xs">{r.record}</p><Findings items={r.findings} /></div>)}<Lesson text={c.res.lesson} /><Warn items={[c.res.limit]} /></div>}
      {c.res && kind === "script" && <div className="mt-2 space-y-2"><p className="text-sm"><b>{c.res.type}</b>, {c.res.lines} lines: {c.res.verdict}</p>{c.res.findings.length > 0 && <Findings items={c.res.findings.map((f: R) => ({ level: f.level, message: `Line ${f.line}: ${f.finding}.`, advice: f.advice }))} />}<ul className="list-disc pl-5 text-sm">{c.res.habits.map((h: string) => <li key={h}>{h}</li>)}</ul><Warn items={[c.res.limit]} /></div>}
    </Section>
  );
}

function DisplayTool() {
  const [w, setW] = useState("2560"); const [h, setH] = useState("1440"); const [dg, setDg] = useState("27"); const [hz, setHz] = useState("144"); const c = useCall();
  return (
    <Section title="Display calculator" note="Pixel density and the cable bandwidth a mode needs.">
      <div className="grid gap-2 sm:grid-cols-4"><In label="Width (px)" v={w} set={setW} /><In label="Height (px)" v={h} set={setH} /><In label="Diagonal (in)" v={dg} set={setDg} /><In label="Refresh (Hz)" v={hz} set={setHz} /></div>
      <button className="btn btn-primary mt-2" onClick={() => c.run("/api/aplus/display", { width_px: Number(w), height_px: Number(h), diagonal_in: Number(dg), refresh_hz: Number(hz) })}>Calculate</button><Out c={c} />
      {c.res && <div className="mt-2 space-y-2"><div className="grid grid-cols-2 gap-2 sm:grid-cols-4"><Stat label="Pixels per inch" value={String(c.res.pixel_density_ppi)} /><Stat label="Megapixels" value={String(c.res.megapixels)} /><Stat label="Aspect" value={c.res.aspect_ratio} /><Stat label="Needs (Gbps)" value={String(c.res.uncompressed_gbps)} /></div><p className="text-sm">{c.res.name ? `${c.res.name}. ` : ""}{c.res.reading}</p><p className="text-xs text-muted">{c.res.cable_note}</p><Lesson text={c.res.lesson} /></div>}
    </Section>
  );
}

function PsuTool() {
  const [v, setV] = useState({ cpu_w: "65", gpu_w: "0", drives: "1", fans: "3", ram_sticks: "2", other_w: "20", headroom_pct: "30" }); const c = useCall();
  const labels: Record<string, string> = { cpu_w: "CPU watts", gpu_w: "Graphics card watts", drives: "Drives", fans: "Fans", ram_sticks: "Memory sticks", other_w: "Other watts", headroom_pct: "Headroom %" };
  return (
    <Section title="Power supply sizer" note="Add up the parts, add headroom, pick the next common size.">
      <div className="grid gap-2 sm:grid-cols-4">{Object.keys(v).map((k) => <In key={k} label={labels[k]} v={(v as R)[k]} set={(s) => setV({ ...v, [k]: s })} />)}</div>
      <button className="btn btn-primary mt-2" onClick={() => c.run("/api/aplus/psu", Object.fromEntries(Object.entries(v).map(([k, x]) => [k, Number(x) || 0])))}>Size it</button><Out c={c} />
      {c.res && <div className="mt-2 space-y-2"><div className="grid grid-cols-3 gap-2"><Stat label="Load" value={`${c.res.load_w} W`} /><Stat label="With headroom" value={`${c.res.with_headroom_w} W`} /><Stat label="Suggested supply" value={c.res.suggested_psu_w ? `${c.res.suggested_psu_w} W` : "check parts"} /></div><p className="text-xs text-muted">{c.res.note}</p><Lesson text={c.res.lesson} /><ul className="list-disc pl-5 text-sm">{c.res.also_check.map((x: string) => <li key={x}>{x}</li>)}</ul></div>}
    </Section>
  );
}

function BackupTool() {
  const [v, setV] = useState({ full_gb: "500", daily_change_gb: "20", days: "28", full_every_days: "7", copies: "2", media_types: "1", offsite: "0" }); const c = useCall();
  const labels: Record<string, string> = { full_gb: "Full backup (GB)", daily_change_gb: "Changed per day (GB)", days: "Days kept", full_every_days: "Full every (days)", copies: "Copies", media_types: "Media types", offsite: "Offsite copies" };
  return (
    <Section title="Backup planner" note="Compares full, incremental, differential and synthetic, and checks the 3-2-1 rule.">
      <div className="grid gap-2 sm:grid-cols-4">{Object.keys(v).map((k) => <In key={k} label={labels[k]} v={(v as R)[k]} set={(s) => setV({ ...v, [k]: s })} />)}</div>
      <button className="btn btn-primary mt-2" onClick={() => c.run("/api/aplus/backup", Object.fromEntries(Object.entries(v).map(([k, x]) => [k, Number(x) || 0])))}>Compare</button><Out c={c} />
      {c.res && <div className="mt-2 space-y-2"><Table head={["Scheme", "Stored (GB)", "Sets to restore", "Note"]} rows={c.res.schemes.map((s: R) => [s.scheme, s.stored_gb, s.restore_sets, s.note])} /><p className="text-sm">{c.res.rule_3_2_1.meets ? <Badge tone="ok">3-2-1 met</Badge> : <Badge tone="warn">3-2-1 not met</Badge>} {c.res.rule_3_2_1.message}</p><p className="text-xs text-muted">{c.res.rotation}</p><Lesson text={c.res.lesson} /><Warn items={[c.res.limit]} /></div>}
    </Section>
  );
}
