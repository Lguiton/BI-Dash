"use client";
import { useEffect, useState } from "react";
import { ErrorBanner } from "@/components/ErrorBanner";
import { Badge, Section, errMsg } from "@/components/panels/kit";
import { ApiError, getJson, postFile, postJson } from "@/lib/api";
import { checkFile } from "@/lib/fileCheck";

/* eslint-disable @typescript-eslint/no-explicit-any */
type R = Record<string, any>;

function Steps({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="text-xs">
      <div className="font-semibold">{title}</div>
      <ul className="list-disc pl-5">{items.map((x, i) => <li key={i} className="select-text">{x}</li>)}</ul>
    </div>
  );
}

/** Scanned files and photos to text (Tesseract). Reads on this computer; nothing is stored or sent. */
function OcrCard() {
  const [st, setSt] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [out, setOut] = useState<R | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { getJson<R>("/api/ocr/status").then(setSt).catch((e) => setErr(errMsg(e, "Couldn't check the scanned-file reader."))); }, []);
  async function pick(f: File | undefined) {
    if (!f) return;
    setErr(null);
    setOut(null);
    const bad = checkFile(f, "anything");
    if (bad) { setErr(bad); return; }
    setBusy(true);
    try { setOut(await postFile<R>("/api/files/text", f)); } catch (e) { setErr(e instanceof ApiError ? e.message : errMsg(e, "Couldn't read that file.")); }
    setBusy(false);
  }
  return (
    <Section title="Scanned files and photos (OCR)" note="Turns a picture of a document or a scanned PDF into text. Every Upload button then accepts them. OCR is a draft: check the numbers.">
      {err && <ErrorBanner message={err} />}
      {st && (
        <div className="space-y-2 text-sm">
          <p><Badge tone={st.available ? "ok" : "warn"}>{st.available ? "Ready" : "Not installed"}</Badge> {st.available ? `${st.version}. Languages: ${(st.languages || []).join(", ") || "eng"}.` : st.message}</p>
          {!st.available && (<><Steps title="Windows" items={st.install.windows} /><Steps title="WSL or Linux (where the backend runs)" items={st.install.wsl_or_linux} /><p className="text-xs">{st.install.check}</p></>)}
          {st.available && (
            <label className="block text-xs">Try it on a photo or scan (png, jpg, tif, bmp, webp, or a scanned PDF)
              <input type="file" className="mt-1 block text-sm" accept=".png,.jpg,.jpeg,.tif,.tiff,.bmp,.webp,.pdf" onChange={(e) => { void pick(e.target.files?.[0]); e.target.value = ""; }} />
            </label>
          )}
          {busy && <p className="text-xs text-muted">Reading…</p>}
          {out && <div className="space-y-1"><p className="text-xs text-muted">{out.chars} characters. {out.note}</p><pre className="max-h-64 overflow-auto whitespace-pre-wrap rounded border border-line p-2 font-mono text-xs select-text">{out.text}</pre></div>}
        </div>
      )}
    </Section>
  );
}

/** Live capture on the backend's own computer. Headers only by default. Private networks you own or may test only. */
function CaptureCard() {
  const [st, setSt] = useState<R | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [iface, setIface] = useState("");
  const [secs, setSecs] = useState("10");
  const [count, setCount] = useState("500");
  const [flt, setFlt] = useState("");
  const [sure, setSure] = useState(false);
  const [headers, setHeaders] = useState(true);
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<R | null>(null);
  const [saved, setSaved] = useState("");
  useEffect(() => { getJson<R>("/api/capture/status").then((s) => { setSt(s); setIface(s.interfaces?.[0]?.name ?? ""); }).catch((e) => setErr(errMsg(e, "Couldn't check live capture."))); }, []);
  async function go() {
    setErr(null);
    setOut(null);
    setSaved("");
    setBusy(true);
    try { setOut(await postJson<R>("/api/capture/run", { iface, seconds: Number(secs), count: Number(count), filter: flt, confirm: sure, headers_only: headers })); } catch (e) { setErr(errMsg(e, "The capture failed.")); }
    setBusy(false);
  }
  function save() {
    if (!out) return;
    const bin = atob(out.pcap_base64);
    const bytes = Uint8Array.from(bin, (c) => c.charCodeAt(0));
    const url = URL.createObjectURL(new Blob([bytes], { type: "application/octet-stream" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `capture-${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.pcap`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
    setSaved(a.download);
  }
  const sm = out?.summary as R | undefined;
  return (
    <Section title="Live network capture" note="Listens on a network card of the computer that runs the backend, then summarises what it heard. Only capture a network you own or have written permission to test.">
      {err && <ErrorBanner message={err} />}
      {st && (
        <div className="space-y-2 text-sm">
          <p><Badge tone={st.available ? "ok" : "warn"}>{st.available ? "Cards found" : "Not ready"}</Badge> {st.message}</p>
          {!st.available && (<><Steps title="Windows" items={st.install.windows} /><Steps title="Linux" items={st.install.linux} /><p className="text-xs">{st.install.check}</p></>)}
          {st.available && (
            <div className="grid gap-2 sm:grid-cols-2">
              <label className="text-xs sm:col-span-2">Network card
                <select className="input mt-1 w-full" value={iface} onChange={(e) => setIface(e.target.value)}>{st.interfaces.map((i: R) => <option key={i.name} value={i.name}>{i.label}</option>)}</select>
              </label>
              <label className="text-xs">Seconds (1 to 60)<input className="input mt-1 w-full" value={secs} onChange={(e) => setSecs(e.target.value)} inputMode="numeric" /></label>
              <label className="text-xs">Packet limit (up to 5000)<input className="input mt-1 w-full" value={count} onChange={(e) => setCount(e.target.value)} inputMode="numeric" /></label>
              <label className="text-xs sm:col-span-2">Filter (optional), for example: tcp port 443 or host 192.168.1.10<input className="input mt-1 w-full" value={flt} onChange={(e) => setFlt(e.target.value)} /></label>
              <label className="flex items-center gap-2 text-xs sm:col-span-2"><input type="checkbox" checked={headers} onChange={(e) => setHeaders(e.target.checked)} /> Keep headers only (no passwords or page contents). Recommended.</label>
              <label className="flex items-center gap-2 text-xs sm:col-span-2"><input type="checkbox" checked={sure} onChange={(e) => setSure(e.target.checked)} /> This is a network I own or have written permission to capture.</label>
              <div className="sm:col-span-2"><button className="btn" disabled={busy || !sure || !iface} onClick={go}>{busy ? "Capturing…" : "Start capture"}</button></div>
            </div>
          )}
          {out && (
            <div className="space-y-2" role="status">
              <p className="text-xs">Captured {out.captured} packets in up to {out.seconds} s on {out.interface}. Filter: {out.filter}.</p>
              <div className="flex flex-wrap items-center gap-2"><button className="btn btn-primary" onClick={save}>Download capture (.pcap)</button>{saved && <span className="text-xs text-muted">Sent to your browser&apos;s download folder as {saved}. If nothing appears, check that the browser did not block the download.</span>}</div>
              {sm && (
                <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-xs">
                  {Object.entries(sm).filter(([, v]) => typeof v === "string" || typeof v === "number").map(([k, v]) => <div key={k} className="contents"><dt className="text-muted">{k.replace(/_/g, " ")}</dt><dd>{String(v)}</dd></div>)}
                </dl>
              )}
              {sm && Array.isArray(sm.protocols) && <p className="text-xs">Protocols: {sm.protocols.map((p: [string, number]) => `${p[0]} ${p[1]}`).join(", ")}</p>}
              {(out.notes as string[]).map((n, i) => <p key={i} className="text-xs text-muted">{n}</p>)}
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

export function ScanCapture() {
  return <div className="grid gap-4"><OcrCard /><CaptureCard /></div>;
}
