"use client";

import { CheckCircle2, XCircle } from "lucide-react";
import { useState } from "react";
import { PageShell } from "@/components/PageShell";
import { QUESTIONS, TOPICS, type QuizQuestion } from "@/lib/quizData";
import { useStoredJson } from "@/lib/useStoredJson";

type Scores = Record<string, { best: number; total: number }>;
const ALL = "All topics";

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; }
  return a;
}

export default function QuizPage() {
  const [scores, setScores] = useStoredJson<Scores>("bi-quiz-scores", {});
  const [topic, setTopic] = useState<string>(ALL);
  const [deck, setDeck] = useState<QuizQuestion[] | null>(null);
  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const [right, setRight] = useState(0);
  const [missed, setMissed] = useState<string[]>([]);

  const finished = deck !== null && idx >= deck.length;
  const q = deck && !finished ? deck[idx] : null;

  function start(questions: QuizQuestion[]) {   // shuffling happens in an event handler, never during render
    const picked10 = shuffle(questions).slice(0, 10).map((qq) => {   // also shuffle the options so the answer isn't always in the same slot
      const order = shuffle(qq.options.map((_, i) => i));
      return { ...qq, options: order.map((i) => qq.options[i]), answer: order.indexOf(qq.answer) };
    });
    setDeck(picked10); setIdx(0); setPicked(null); setRight(0); setMissed([]);
  }
  function choose(i: number) {
    if (!q || picked !== null) return;
    setPicked(i);
    if (i === q.answer) setRight((r) => r + 1); else setMissed((m) => [...m, q.id]);
  }
  function next() {
    if (!deck) return;
    const done = idx + 1 >= deck.length;
    if (done) {
      const key = topic;
      const prev = scores[key] ?? { best: 0, total: 0 };
      setScores({ ...scores, [key]: { best: Math.max(prev.best, Math.round((right / deck.length) * 100)), total: deck.length } });
    }
    setIdx(idx + 1); setPicked(null);
  }

  const pool = topic === ALL ? QUESTIONS : QUESTIONS.filter((x) => x.topic === topic);

  return (
    <PageShell title="Quiz" subtitle="Exam prep from your class topics. Ten questions per round, with an explanation after each answer.">
      {!deck && (
        <section className="card space-y-4 p-5" aria-label="Start a round">
          <label className="block text-sm font-medium">Topic
            <select className="field mt-1 block" value={topic} onChange={(e) => setTopic(e.target.value)}>
              {[ALL, ...TOPICS].map((t) => <option key={t} value={t}>{t}{scores[t] ? ` (best ${scores[t].best}%)` : ""}</option>)}
            </select>
          </label>
          <p className="text-sm text-muted">{pool.length} question{pool.length === 1 ? "" : "s"} available. Each round asks up to 10, in random order.</p>
          <button className="btn btn-primary" onClick={() => start(pool)}>Start round</button>
        </section>
      )}

      {q && deck && (
        <section className="card space-y-4 p-5" aria-label="Question">
          <div className="flex items-center justify-between text-xs text-muted">
            <span>Question {idx + 1} of {deck.length} · {q.topic}</span><span>{right} correct</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-panel2" role="progressbar" aria-valuemin={0} aria-valuemax={deck.length} aria-valuenow={idx}>
            <div className="h-1.5 rounded-full bg-accent" style={{ width: `${(idx / deck.length) * 100}%` }} />
          </div>
          <fieldset>
            <legend className="text-lg font-semibold">{q.q}</legend>
            <div className="mt-3 space-y-2">
              {q.options.map((o, i) => {
                const isAnswer = picked !== null && i === q.answer;
                const isWrong = picked === i && i !== q.answer;
                return (
                  <label key={o} className={`flex cursor-pointer items-start gap-3 rounded-lg border px-3 py-2.5 text-sm ${picked !== null ? "cursor-default" : "hover:bg-panel2"}`}
                         style={{ borderColor: isAnswer ? "var(--good)" : isWrong ? "var(--bad)" : "var(--line)", background: isAnswer ? "var(--good-bg)" : isWrong ? "var(--bad-bg)" : undefined }}>
                    <input type="radio" name={q.id} className="mt-1" checked={picked === i} disabled={picked !== null} onChange={() => choose(i)} />
                    <span className="flex-1">{o}</span>
                    {isAnswer && <CheckCircle2 className="h-4 w-4 shrink-0" style={{ color: "var(--good)" }} aria-label="correct answer" />}
                    {isWrong && <XCircle className="h-4 w-4 shrink-0" style={{ color: "var(--bad)" }} aria-label="your answer, incorrect" />}
                  </label>
                );
              })}
            </div>
          </fieldset>
          {picked !== null && (
            <div className="space-y-3">
              <p role="status" className="rounded-lg p-3 text-sm" style={{ background: "var(--info-bg)" }}>
                <b>{picked === q.answer ? "Correct. " : "Not quite. "}</b>{q.why}
              </p>
              <button className="btn btn-primary" onClick={next}>{idx + 1 >= deck.length ? "See results" : "Next question"}</button>
            </div>
          )}
        </section>
      )}

      {finished && deck && (
        <section className="card space-y-4 p-5" aria-label="Results">
          <h2 className="text-lg font-semibold">Round complete</h2>
          <div className="text-5xl font-bold tabular-nums">{right}/{deck.length}</div>
          <p className="text-sm text-muted">{Math.round((right / deck.length) * 100)}% · best for &quot;{topic}&quot;: {scores[topic]?.best ?? 0}%</p>
          {missed.length > 0 && (
            <div>
              <h3 className="text-sm font-semibold">Review these</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">
                {missed.map((id) => { const m = QUESTIONS.find((x) => x.id === id)!; return <li key={id}><b>{m.q}</b> {m.options[m.answer]}. <span className="text-muted">{m.why}</span></li>; })}
              </ul>
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button className="btn btn-primary" onClick={() => start(pool)}>Another round</button>
            {missed.length > 0 && <button className="btn" onClick={() => start(QUESTIONS.filter((x) => missed.includes(x.id)))}>Retry missed ones</button>}
            <button className="btn" onClick={() => setDeck(null)}>Change topic</button>
          </div>
        </section>
      )}
    </PageShell>
  );
}
