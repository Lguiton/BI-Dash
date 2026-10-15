"use client";
import { useEffect, useState } from "react";
import { Section, errMsg } from "@/components/panels/kit";
import { getJson } from "@/lib/api";

type File = { name: string; kind: string; text: string };
type Kit = { label: string; brief: string; done: string[]; files: File[] } | null;

function save(f: File) {
  const url = URL.createObjectURL(new Blob([f.text], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url; a.download = f.name; document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}

/** Made-up materials for a practice job: the brief, the files to work on, what "done" looks like. The answer key stays hidden until you ask. Shows nothing for real jobs. */
export function JobMaterials({ jobId }: { jobId: number }) {
  const [kit, setKit] = useState<Kit>(null);
  const [ans, setAns] = useState<string[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [look, setLook] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    getJson<{ kit: Kit }>(`/api/workteam/kit/${jobId}`).then((r) => { if (live) setKit(r.kit); }).catch(() => {});
    return () => { live = false; };
  }, [jobId]);

  if (!kit) return null;
  const reveal = async () => { setErr(null); try { setAns((await getJson<{ answer: string[] }>(`/api/workteam/kit/${jobId}/answer`)).answer); } catch (e) { setErr(errMsg(e, "Couldn't load the answer key.")); } };
  return (
    <Section title="Practice materials" note={kit.label}>
      <div className="space-y-3 text-sm">
        <p><strong>The ask:</strong> {kit.brief}</p>
        <div>
          <p className="text-xs font-semibold text-muted">Files to work on</p>
          <ul className="mt-1 space-y-1">
            {kit.files.map((f) => (
              <li key={f.name} className="flex flex-wrap items-center gap-2 rounded border border-line px-2 py-1">
                <span className="font-mono text-xs">{f.name}</span>
                <button className="btn" onClick={() => save(f)}>Download</button>
                <button className="btn" onClick={() => navigator.clipboard?.writeText(f.text)}>Copy</button>
                <button className="btn" onClick={() => setLook(look === f.name ? null : f.name)}>{look === f.name ? "Hide" : "Look"}</button>
                {look === f.name && <pre className="max-h-64 w-full overflow-auto whitespace-pre-wrap rounded bg-panel2 p-2 text-xs">{f.text.length > 4000 ? f.text.slice(0, 4000) + "\n… (download for the whole file)" : f.text}</pre>}
              </li>
            ))}
          </ul>
        </div>
        <div>
          <p className="text-xs font-semibold text-muted">What done looks like</p>
          <ul className="mt-1 list-disc pl-5">{kit.done.map((d) => <li key={d}>{d}</li>)}</ul>
        </div>
        <div className="space-y-1 border-t border-line pt-2">
          {ans ? (
            <>
              <p className="text-xs font-semibold text-muted">Answer key (computed from these files). Your answer can be right and worded differently.</p>
              <ul className="list-disc pl-5">{ans.map((a) => <li key={a}>{a}</li>)}</ul>
            </>
          ) : <button className="btn" onClick={reveal}>Show the answer key (try it first)</button>}
          {err && <p role="alert" className="text-xs text-red-600">{err}</p>}
        </div>
      </div>
    </Section>
  );
}
