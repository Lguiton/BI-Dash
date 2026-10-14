"use client";
import { CheckCircle2, XCircle } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { Badge, Section, Stat, Table, errMsg } from "@/components/panels/kit";
import { getJson, postJson } from "@/lib/api";

interface Row { track: string; questions: number; seen: number; due: number; mastered: number; accuracy_pct: number | null; started: boolean }
interface Weak { track: string; step: string; step_title: string; accuracy_pct: number; attempts: number; href: string }
interface Summary { due: number; new_available: number; streak: { days: number; today_done: boolean }; tracks: Row[]; weak: Weak[]; daily: string }
interface Card { id: string; track: string; step_title: string; q: string; options: string[]; kind: "due" | "new" }
interface Result { ok: boolean; correct: number; why: string; next: string }

export default function ReviewPage() {
  const [sum, setSum] = useState<Summary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [deck, setDeck] = useState<Card[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [res, setRes] = useState<Result | null>(null);
  const [picked, setPicked] = useState<number | null>(null);
  const [right, setRight] = useState(0);
  const [n, setN] = useState("10");
  const [track, setTrack] = useState("");

  const load = useCallback(() => { getJson<Summary>("/api/review/summary").then(setSum).catch((e) => setErr(errMsg(e, "Couldn't load your review."))); }, []);
  useEffect(() => { load(); }, [load]);

  const start = () => {
    setErr(null);
    getJson<{ cards: Card[] }>(`/api/review/session?n=${Number(n)}${track ? `&track=${track}` : ""}`)
      .then((r) => { setDeck(r.cards); setIdx(0); setRes(null); setPicked(null); setRight(0); })
      .catch((e) => setErr(errMsg(e, "Couldn't start a session.")));
  };
  const choose = (i: number) => {
    if (!deck || picked !== null) return;
    setPicked(i);
    postJson<Result>("/api/review/answer", { id: deck[idx].id, picked: i })
      .then((r) => { setRes(r); if (r.ok) setRight((x) => x + 1); })
      .catch((e) => { setErr(errMsg(e, "That answer wasn't saved.")); setPicked(null); });
  };
  const next = () => { setIdx(idx + 1); setRes(null); setPicked(null); if (deck && idx + 1 >= deck.length) load(); };

  const finished = deck !== null && deck.length > 0 && idx >= deck.length;
  const q = deck && !finished ? deck[idx] : null;

  return (
    <PageShell title="Review" subtitle="Questions you miss come back soon; ones you know come back later. A few minutes a day beats a long cram.">
      {err && <ErrorBanner message={err} />}
      {!deck && sum && (
        <>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Stat label="Due now" value={String(sum.due)} />
            <Stat label="New available" value={String(sum.new_available)} />
            <Stat label="Day streak" value={String(sum.streak.days)} sub={sum.streak.today_done ? "done today" : "not yet today"} />
            <Stat label="Today" value={sum.daily} />
          </div>
          <Section title="Start a session" note="Due questions come first, then new ones from the tracks you have started.">
            <div className="flex flex-wrap items-end gap-2">
              <label className="text-sm">Questions
                <select className="field mt-1 block" value={n} onChange={(e) => setN(e.target.value)} aria-label="Questions">{["5", "10", "20", "30"].map((x) => <option key={x}>{x}</option>)}</select>
              </label>
              <label className="text-sm">Track
                <select className="field mt-1 block" value={track} onChange={(e) => setTrack(e.target.value)} aria-label="Track"><option value="">All started tracks</option>{sum.tracks.map((t) => <option key={t.track} value={t.track}>{t.track}</option>)}</select>
              </label>
              <button className="btn btn-primary" onClick={start}>Start</button>
            </div>
          </Section>
          <Section title="Weak spots" note="Manual steps where your answers keep going wrong. Re-read the step, then drill it.">
            {sum.weak.length === 0 ? <p className="text-sm text-muted">None yet. Answer a few questions and they will show up here.</p>
              : <Table head={["Track", "Step", "Accuracy", "Answers", ""]} rows={sum.weak.map((w) => [w.track, w.step_title, <Badge key="a" tone={w.accuracy_pct < 50 ? "bad" : "warn"}>{w.accuracy_pct}%</Badge>, String(w.attempts), <Link key="l" href={w.href} className="text-accent underline">Open manual</Link>])} />}
          </Section>
          <Section title="By track">
            <Table head={["Track", "Questions", "Seen", "Due", "Mastered", "Accuracy"]} rows={sum.tracks.map((t) => [t.track + (t.started ? "" : " (not started)"), String(t.questions), String(t.seen), String(t.due), String(t.mastered), t.accuracy_pct == null ? "-" : `${t.accuracy_pct}%`])} />
          </Section>
        </>
      )}
      {q && deck && (
        <section className="card space-y-4 p-5" aria-label="Question">
          <div className="flex items-center justify-between text-xs text-muted"><span>Question {idx + 1} of {deck.length} · {q.track} · {q.step_title}</span><span>{q.kind === "due" ? "Review" : "New"} · {right} correct</span></div>
          <fieldset>
            <legend className="text-lg font-semibold">{q.q}</legend>
            <div className="mt-3 space-y-2">
              {q.options.map((o, i) => {
                const isAnswer = res !== null && i === res.correct;
                const isWrong = res !== null && picked === i && i !== res.correct;
                return (
                  <label key={o} className="flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 text-sm hover:bg-panel2" style={{ borderColor: isAnswer ? "var(--good)" : isWrong ? "var(--bad)" : "var(--line)" }}>
                    <input type="radio" name={q.id} className="mt-1" checked={picked === i} disabled={picked !== null} onChange={() => choose(i)} />
                    <span className="flex-1">{o}</span>
                    {isAnswer && <CheckCircle2 className="h-4 w-4 shrink-0" aria-label="correct answer" />}
                    {isWrong && <XCircle className="h-4 w-4 shrink-0" aria-label="your answer, incorrect" />}
                  </label>
                );
              })}
            </div>
          </fieldset>
          {res && (
            <div className="space-y-3">
              <p role="status" className="rounded-lg p-3 text-sm" style={{ background: "var(--info-bg)" }}><b>{res.ok ? "Correct. " : "Not quite. "}</b>{res.why} <span className="text-muted">({res.next})</span></p>
              <button className="btn btn-primary" onClick={next}>{idx + 1 >= deck.length ? "Finish" : "Next"}</button>
            </div>
          )}
        </section>
      )}
      {finished && deck && (
        <section className="card space-y-3 p-5" aria-label="Results">
          <h2 className="text-lg font-semibold">Session complete</h2>
          <div className="text-5xl font-bold tabular-nums">{right}/{deck.length}</div>
          <p className="text-sm text-muted">Missed ones come back today; the rest return on a longer gap.</p>
          <div className="flex gap-2"><button className="btn btn-primary" onClick={start}>Another session</button><button className="btn" onClick={() => setDeck(null)}>Back to summary</button></div>
        </section>
      )}
      {deck && deck.length === 0 && <div className="space-y-2"><p className="text-sm text-muted">Nothing to review right now.</p><button className="btn" onClick={() => setDeck(null)}>Back to summary</button></div>}
    </PageShell>
  );
}
