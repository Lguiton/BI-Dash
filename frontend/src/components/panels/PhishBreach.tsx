"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Field, Section, errMsg } from "./kit";

type Mail = { id: string; from_name: string; from_addr: string; subject: string; body: string; links: { text: string; href: string }[]; attachment: string };
type Res = { id: string; your_answer: string; correct: boolean; was: string; explain: string[] };
type Grade = { says: string; habit: string; results: Res[] };

export function PhishBreach({ onFix }: { onFix: (id: string) => void }) {
  const [seed, setSeed] = useState(1);
  const [mails, setMails] = useState<Mail[]>([]);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [gr, setGr] = useState<Grade | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [pw, setPw] = useState("");
  const [pwr, setPwr] = useState<{ says: string; found: boolean; sent: string } | null>(null);
  const [em, setEm] = useState({ email: "", key: "" });
  const [emr, setEmr] = useState<{ says: string; found: boolean; breaches: { name: string; date: string; exposed: string[] }[] } | null>(null);

  useEffect(() => { getJson<{ mails: Mail[] }>(`/api/security/phish/deck?seed=${seed}&n=8`).then((r) => setMails(r.mails)).catch((e) => setErr(errMsg(e, "Could not load the practice emails."))); }, [seed]);
  const fail = (e: unknown, m: string) => setErr(errMsg(e, m));
  const next = () => { setSeed((s) => s + 1); setAns({}); setGr(null); };

  return (
    <div className="grid gap-4">
      {err && <ErrorBanner message={err} />}
      <Section title="Phishing practice" note="Made-up emails on reserved .example addresses that cannot reach a real site. Real phishing can look better, so learn the habit, not these examples.">
        <ul className="grid gap-3">
          {mails.map((m) => (
            <li key={m.id} className="rounded border border-line p-3 text-sm">
              <div className="text-xs text-muted">From: {m.from_name} &lt;{m.from_addr}&gt;</div><div className="font-medium">{m.subject}</div><p className="my-1">{m.body}</p>
              {m.links.map((l, i) => <div key={i} className="text-xs">Link shows <b>{l.text}</b> and goes to <code>{l.href}</code></div>)}
              {m.attachment && <div className="text-xs">Attachment: {m.attachment}</div>}
              <div className="mt-2 flex gap-4" role="radiogroup" aria-label={`Is "${m.subject}" phish or real?`}>
                {["phish", "real"].map((a) => <label key={a} className="flex items-center gap-1"><input type="radio" name={m.id} checked={ans[m.id] === a} onChange={() => setAns({ ...ans, [m.id]: a })} />{a === "phish" ? "Phish" : "Real"}</label>)}
              </div>
              {gr?.results.find((r) => r.id === m.id) && (() => { const r = gr.results.find((x) => x.id === m.id)!; return <div className="mt-2 text-xs"><Badge tone={r.correct ? "ok" : "bad"}>{r.correct ? "Correct" : "Not quite"}</Badge> It was {r.was}.<ul className="list-disc pl-5">{r.explain.map((e, i) => <li key={i}>{e}</li>)}</ul></div>; })()}
            </li>
          ))}
        </ul>
        <div className="mt-3 flex gap-2"><button className="btn" disabled={Object.keys(ans).length === 0} onClick={async () => { setErr(null); try { setGr(await postJson<Grade>("/api/security/phish/grade", { answers: ans })); } catch (e) { fail(e, "Could not grade."); } }}>Check my answers</button><button className="btn" onClick={next}>New set</button><button className="btn" onClick={() => onFix("phish-clicked")}>I clicked one: what now?</button></div>
        {gr && <p className="mt-2 text-sm"><b>{gr.says}</b> {gr.habit}</p>}
      </Section>

      <Section title="Breach exposure check" note="Passwords: only the first 5 characters of the password's hash leave this computer, never the password. Emails need your own paid Have I Been Pwned API key, used once and never stored. Both contact haveibeenpwned.com when you press the button.">
        <div className="flex flex-wrap items-end gap-2"><Field label="Password to check"><input aria-label="Password to check" type="password" autoComplete="off" className="input" value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
          <button className="btn" disabled={!pw} onClick={async () => { setErr(null); try { setPwr(await postJson("/api/security/breach/password", { password: pw })); } catch (e) { fail(e, "The check failed."); } }}>Check password</button></div>
        {pwr && <p className="mt-2 text-sm"><Badge tone={pwr.found ? "bad" : "ok"}>{pwr.found ? "Found" : "Not found"}</Badge> {pwr.says} <span className="text-xs text-muted">{pwr.sent}</span> {pwr.found && <button className="btn" onClick={() => onFix("pwned-password")}>How to fix</button>}</p>}
        <div className="mt-4 flex flex-wrap items-end gap-2"><Field label="Email address"><input aria-label="Email to check" className="input" value={em.email} onChange={(e) => setEm({ ...em, email: e.target.value })} /></Field>
          <Field label="Your HIBP API key"><input aria-label="HIBP API key" type="password" autoComplete="off" className="input" value={em.key} onChange={(e) => setEm({ ...em, key: e.target.value })} /></Field>
          <button className="btn" disabled={!em.email} onClick={async () => { setErr(null); try { setEmr(await postJson("/api/security/breach/email", { email: em.email, api_key: em.key })); } catch (e) { fail(e, "The check failed."); } }}>Check email</button></div>
        {emr && <div className="mt-2 text-sm"><p>{emr.says}</p><ul className="list-disc pl-5 text-xs">{emr.breaches.map((b) => <li key={b.name}>{b.name} ({b.date}): {b.exposed.join(", ")}</li>)}</ul></div>}
      </Section>
    </div>
  );
}
