"use client";

import Link from "next/link";
import { BookOpen, FileCode, LayoutDashboard } from "lucide-react";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { PageShell } from "@/components/PageShell";
import { ApiError, getJson } from "@/lib/api";
import type { Track, TrackStep } from "@/lib/types";

interface FileView { path: string; language: string; content: string }

export default function TracksPage() {
  const [tracks, setTracks] = useState<Track[] | null>(null);
  const [id, setId] = useState("analyst");
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<FileView | null>(null);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    const ctl = new AbortController();
    getJson<{ tracks: Track[] }>("/api/tracks", ctl.signal)
      .then((r) => { setTracks(r.tracks); setError(null); })
      .catch((e) => { if (!ctl.signal.aborted) setError(e instanceof ApiError ? e.message : "Couldn't load the tracks."); });
    return () => ctl.abort();
  }, [attempt]);

  const track = tracks?.find((t) => t.id === id);

  async function open(step: TrackStep) {
    if (!step.path) return;
    try {
      setFile(await getJson<FileView>(`/api/tracks/file?path=${encodeURIComponent(step.path)}`));
      setError(null);
    } catch (e) { setError(e instanceof ApiError ? e.message : "Couldn't open that file."); }
  }

  return (
    <PageShell title="Career tracks" subtitle="Five paths, each with real tools and a learning path through this project.">
      {error && <ErrorBanner message={error} onRetry={() => setAttempt((a) => a + 1)} />}
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="track" className="text-sm font-medium">Track</label>
        <select id="track" className="field" value={id} onChange={(e) => { setId(e.target.value); setFile(null); }}>
          {(tracks ?? [{ id: "analyst", name: "Data Analyst" }]).map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
        {track && <span className="rounded-full bg-panel2 px-3 py-1 text-xs text-muted">{track.role}</span>}
      </div>
      {!tracks && !error && <p className="text-sm text-muted">Loading…</p>}

      {track && (
        <div className="grid gap-6 lg:grid-cols-2">
          <section className="card space-y-5 p-5">
            <p className="text-sm leading-relaxed">{track.summary}</p>
            <div>
              <h2 className="mb-2 text-sm font-semibold">Real tools</h2>
              <ul className="space-y-2 text-sm">
                {track.tools.map((t) => (
                  <li key={t.name}><b>{t.name}</b><br /><code className="text-xs text-muted">{t.install}</code></li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="mb-2 text-sm font-semibold">Portfolio projects</h2>
              <ul className="list-disc space-y-1 pl-5 text-sm">{track.projects.map((p) => <li key={p}>{p}</li>)}</ul>
            </div>
          </section>

          <section className="card space-y-3 p-5">
            <h2 className="text-sm font-semibold">Learning path (in order)</h2>
            <ol className="space-y-3">
              {track.path.map((s, i) => (
                <li key={s.label} className="flex gap-3 text-sm">
                  <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-panel2 text-xs font-semibold">{i + 1}</span>
                  <div className="min-w-0">
                    {s.kind === "file" ? (
                      <button className="inline-flex items-center gap-1.5 font-medium underline decoration-dotted" onClick={() => open(s)}>
                        <FileCode className="h-4 w-4" aria-hidden /> {s.label}
                      </button>
                    ) : (
                      <Link href={s.href ?? "/"} className="inline-flex items-center gap-1.5 font-medium underline decoration-dotted">
                        {s.kind === "notebook" ? <BookOpen className="h-4 w-4" aria-hidden /> : <LayoutDashboard className="h-4 w-4" aria-hidden />}
                        {s.label}{s.kind === "notebook" ? " (notebook)" : ""}
                      </Link>
                    )}
                    <p className="text-xs text-muted">{s.why}</p>
                  </div>
                </li>
              ))}
            </ol>
          </section>

          {file && (
            <section className="card min-w-0 lg:col-span-2">
              <div className="flex items-center justify-between border-b border-line px-4 py-3 text-sm">
                <span className="font-mono text-xs">{file.path}</span>
                <button className="btn" onClick={() => setFile(null)}>Close</button>
              </div>
              <pre className="max-h-[32rem] overflow-auto p-4 text-xs leading-relaxed" tabIndex={0}><code>{file.content}</code></pre>
            </section>
          )}
        </div>
      )}
    </PageShell>
  );
}
