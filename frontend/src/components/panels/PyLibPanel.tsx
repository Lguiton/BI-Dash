"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { getJson, postJson } from "@/lib/api";
import { Badge, Section, Table, errMsg } from "./kit";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;

export function PyLibPanel() {
  const [d, setD] = useState<R | null>(null);
  const [out, setOut] = useState<Record<string, R>>({});
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { getJson<R>("/api/pylib").then(setD).catch((e) => setErr(errMsg(e, "Could not load."))); }, []);
  const run = (key: string) => { setErr(null); postJson<R>(`/api/pylib/${key}/demo`, {}).then((r) => setOut((o) => ({ ...o, [key]: r }))).catch((e) => setErr(errMsg(e, "Demo failed."))); };
  return (
    <Section title="Python libraries behind AI work" note="Each demo uses made-up data and runs offline. A library that is not installed shows its pip command. Install into your project's virtual environment.">
      {err && <ErrorBanner message={err} />}
      {!d && !err && <p className="text-sm text-muted">Loading…</p>}
      {d && (
        <div className="space-y-3">
          <p className="text-sm">{d.installed} of {d.total} installed here.</p>
          <Table caption="Python libraries" head={["Library", "Area", "Good for", "First exercise", "Here", ""]}
            rows={d.libraries.map((l: R) => [<a key="n" href={l.docs} target="_blank" rel="noreferrer" className="underline">{l.name}</a>, l.area, l.good_for, l.first_exercise,
              <Badge key="b" tone={l.installed ? "ok" : "muted"}>{l.installed ? `v${l.version}` : "not installed"}</Badge>,
              <button key="r" className="btn" aria-label={`Run ${l.name} demo`} onClick={() => run(l.key)}>Demo</button>])} />
          {Object.entries(out).map(([k, r]) => (
            <div key={k}><h4 className="text-sm font-semibold">{k}: {r.status}</h4>
              {r.output && <pre className="overflow-x-auto whitespace-pre-wrap rounded border border-line bg-panel2 p-3 text-xs">{r.output}</pre>}
              {r.install && <p className="text-xs">Install: <code>{r.install}</code></p>}{r.note && <p className="text-xs text-muted">{r.note}</p>}</div>
          ))}
          <p className="text-xs text-muted">Also worth knowing: {d.also_worth_knowing.map((x: R) => `${x.name} (${x.for})`).join(", ")}.</p>
          <div><h4 className="text-sm font-semibold">Mistakes in the source infographic</h4><ul className="list-disc pl-5 text-sm">{d.slips.map((s: string, i: number) => <li key={i}>{s}</li>)}</ul></div>
        </div>
      )}
    </Section>
  );
}
