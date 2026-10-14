"use client";
import { useEffect, useRef, useState } from "react";
import { Field, Section } from "./kit";

type Shape = "box" | "round" | "decision" | "circle" | "note";
type N = { id: string; x: number; y: number; w: number; h: number; shape: Shape; label: string };
type E = { from: string; to: string; label: string };
const KEY = "bi-diagram-canvas";
const W = 900, H = 520;
const START: { n: N[]; e: E[] } = { n: [{ id: "n1", x: 60, y: 60, w: 130, h: 50, shape: "round", label: "Start" }, { id: "n2", x: 300, y: 55, w: 140, h: 60, shape: "decision", label: "Ready?" }, { id: "n3", x: 560, y: 60, w: 130, h: 50, shape: "box", label: "Do the work" }], e: [{ from: "n1", to: "n2", label: "" }, { from: "n2", to: "n3", label: "yes" }] };

function load(): { n: N[]; e: E[] } {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) { const v = JSON.parse(raw); if (Array.isArray(v.n) && Array.isArray(v.e)) return v; }
  } catch { /* storage blocked: start fresh */ }
  return START;
}

function Shape({ n, sel }: { n: N; sel: boolean }) {
  const cx = n.x + n.w / 2, cy = n.y + n.h / 2, st = { fill: n.shape === "note" ? "#fef3c7" : "var(--panel-2)", stroke: sel ? "#2563eb" : "var(--accent)", strokeWidth: sel ? 3 : 1.5 };
  return (
    <g>
      {n.shape === "decision" ? <polygon points={`${cx},${n.y} ${n.x + n.w},${cy} ${cx},${n.y + n.h} ${n.x},${cy}`} {...st} />
        : n.shape === "circle" ? <ellipse cx={cx} cy={cy} rx={n.w / 2} ry={n.h / 2} {...st} />
        : <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={n.shape === "round" ? n.h / 2 : n.shape === "note" ? 2 : 6} {...st} />}
      <text x={cx} y={cy + 4} textAnchor="middle" fontSize={12} fill={n.shape === "note" ? "#000" : "var(--fg)"}>{n.label.length > 22 ? n.label.slice(0, 21) + "…" : n.label}</text>
    </g>
  );
}

const anchor = (a: N, b: N) => {
  const ax = a.x + a.w / 2, ay = a.y + a.h / 2, bx = b.x + b.w / 2, by = b.y + b.h / 2, dx = bx - ax, dy = by - ay;
  const k = (n: N, ux: number, uy: number) => { const t = Math.min(ux ? n.w / 2 / Math.abs(ux) : 1e9, uy ? n.h / 2 / Math.abs(uy) : 1e9); return [n.x + n.w / 2 + ux * t, n.y + n.h / 2 + uy * t]; };
  return [k(a, dx, dy), k(b, -dx, -dy)];
};

export function DiagramCanvas() {
  const [init] = useState(load);
  const [nodes, setNodes] = useState<N[]>(init.n);
  const [edges, setEdges] = useState<E[]>(init.e);
  const [sel, setSel] = useState<string | null>(null);
  const [connect, setConnect] = useState(false);
  const [from, setFrom] = useState<string | null>(null);
  const [drag, setDrag] = useState<{ id: string; dx: number; dy: number } | null>(null);
  const [json, setJson] = useState("");
  const [msg, setMsg] = useState("");
  const svg = useRef<SVGSVGElement>(null);
  useEffect(() => { try { localStorage.setItem(KEY, JSON.stringify({ n: nodes, e: edges })); } catch { /* ignore */ } }, [nodes, edges]);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const selected = sel ? byId.get(sel) : undefined;
  const pt = (ev: React.PointerEvent) => { const r = svg.current!.getBoundingClientRect(); return { x: ((ev.clientX - r.left) / r.width) * W, y: ((ev.clientY - r.top) / r.height) * H }; };
  const add = (shape: Shape) => {
    const id = "n" + (Math.max(0, ...nodes.map((n) => Number(n.id.slice(1)))) + 1);
    const size = shape === "circle" ? { w: 80, h: 80 } : shape === "decision" ? { w: 140, h: 70 } : { w: 130, h: 50 };
    setNodes([...nodes, { id, x: 40 + (nodes.length % 6) * 40, y: 150 + (nodes.length % 6) * 40, ...size, shape, label: shape === "note" ? "Note" : shape === "decision" ? "Decision?" : "Step" }]);
    setSel(id);
  };
  const del = () => { if (!sel) return; setNodes(nodes.filter((n) => n.id !== sel)); setEdges(edges.filter((e) => e.from !== sel && e.to !== sel)); setSel(null); };
  const click = (id: string) => {
    if (connect) {
      if (!from) { setFrom(id); setMsg("Now click the box to connect to."); return; }
      if (from !== id && !edges.some((e) => e.from === from && e.to === id)) setEdges([...edges, { from, to: id, label: "" }]);
      setFrom(null); setMsg(""); return;
    }
    setSel(id);
  };
  const move = (id: string, dx: number, dy: number) => setNodes(nodes.map((n) => (n.id === id ? { ...n, x: Math.max(0, Math.min(W - n.w, n.x + dx)), y: Math.max(0, Math.min(H - n.h, n.y + dy)) } : n)));
  const mermaid = () => "graph TD\n" + nodes.map((n) => { const l = n.label.replace(/[[\]{}()|"]/g, " "); return `${n.id}${n.shape === "decision" ? `{${l}}` : n.shape === "round" ? `(${l})` : n.shape === "circle" ? `((${l}))` : `[${l}]`}`; }).join("\n") + "\n" + edges.map((e) => `${e.from} -->${e.label ? `|${e.label.replace(/[|]/g, " ")}|` : ""} ${e.to}`).join("\n");
  const dl = (name: string, text: string, type: string) => { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); URL.revokeObjectURL(a.href); };
  const exportSvg = () => {
    const el = svg.current!.cloneNode(true) as SVGSVGElement;
    el.setAttribute("xmlns", "http://www.w3.org/2000/svg"); el.style.cssText = "background:#fff";
    el.querySelectorAll("*").forEach((n) => n.getAttributeNames().forEach((a) => { const v = n.getAttribute(a) ?? ""; if (v.startsWith("var(")) n.setAttribute(a, v.includes("accent") ? "#2563eb" : v.includes("panel") ? "#f1f5f9" : v.includes("muted") ? "#64748b" : "#111827"); }));
    dl("diagram.svg", el.outerHTML, "image/svg+xml");
  };
  const importJson = () => {
    try { const v = JSON.parse(json); if (!Array.isArray(v.n) || !Array.isArray(v.e)) throw new Error(); setNodes(v.n); setEdges(v.e); setSel(null); setMsg("Imported."); } catch { setMsg("That is not a diagram file exported from here."); }
  };
  return (
    <Section title="Free-form canvas" note="Add shapes, drag them, and connect them. Click Connect, then click two boxes. Arrow keys nudge the selected box. Your drawing is kept in this browser; export SVG, a file, or Mermaid text to keep or share it.">
      <div className="mb-2 flex flex-wrap gap-2" role="toolbar" aria-label="Diagram tools">
        {(["box", "round", "decision", "circle", "note"] as Shape[]).map((s) => <button key={s} className="btn" onClick={() => add(s)}>Add {s}</button>)}
        <button className={`btn ${connect ? "btn-primary" : ""}`} aria-pressed={connect} onClick={() => { setConnect(!connect); setFrom(null); setMsg(connect ? "" : "Click the box to start from."); }}>Connect</button>
        <button className="btn" disabled={!sel} onClick={del}>Delete selected</button>
        <button className="btn" onClick={() => { setNodes([]); setEdges([]); setSel(null); }}>Clear</button>
      </div>
      {msg && <p className="mb-1 text-xs text-muted" role="status">{msg}</p>}
      <svg ref={svg} viewBox={`0 0 ${W} ${H}`} className="w-full rounded border border-line bg-panel" style={{ touchAction: "none" }} role="application" aria-label="Diagram canvas"
        onPointerMove={(e) => { if (drag) { const p = pt(e); setNodes((ns) => ns.map((n) => (n.id === drag.id ? { ...n, x: Math.max(0, Math.min(W - n.w, p.x - drag.dx)), y: Math.max(0, Math.min(H - n.h, p.y - drag.dy)) } : n))); } }}
        onPointerUp={() => setDrag(null)} onPointerDown={(e) => { if (e.target === svg.current) { setSel(null); setFrom(null); } }}>
        <defs><marker id="dc-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="var(--muted)" /></marker></defs>
        {edges.map((e, i) => { const a = byId.get(e.from), b = byId.get(e.to); if (!a || !b) return null; const [[x1, y1], [x2, y2]] = anchor(a, b); return <g key={i}><line x1={x1} y1={y1} x2={x2} y2={y2} stroke="var(--muted)" strokeWidth={1.5} markerEnd="url(#dc-arrow)" />{e.label && <text x={(x1 + x2) / 2} y={(y1 + y2) / 2 - 4} textAnchor="middle" fontSize={11} fill="var(--fg)" stroke="var(--bg)" strokeWidth={3} paintOrder="stroke">{e.label}</text>}</g>; })}
        {nodes.map((n) => (
          <g key={n.id} tabIndex={0} role="button" aria-label={`${n.shape}: ${n.label}`} style={{ cursor: connect ? "crosshair" : "grab", outline: "none" }}
            onPointerDown={(e) => { e.stopPropagation(); click(n.id); if (!connect) { const p = pt(e); setDrag({ id: n.id, dx: p.x - n.x, dy: p.y - n.y }); (e.currentTarget as Element).setPointerCapture(e.pointerId); } }}
            onKeyDown={(e) => { const s = e.shiftKey ? 20 : 5; if (e.key === "ArrowLeft") { e.preventDefault(); move(n.id, -s, 0); } if (e.key === "ArrowRight") { e.preventDefault(); move(n.id, s, 0); } if (e.key === "ArrowUp") { e.preventDefault(); move(n.id, 0, -s); } if (e.key === "ArrowDown") { e.preventDefault(); move(n.id, 0, s); } if (e.key === "Delete") del(); if (e.key === "Enter") click(n.id); }}>
            <Shape n={n} sel={n.id === sel || n.id === from} />
          </g>
        ))}
      </svg>
      {selected && (
        <div className="mt-2 grid gap-2 sm:grid-cols-2">
          <Field label="Label of selected box"><input className="field" value={selected.label} maxLength={80} aria-label="Label of selected box" onChange={(e) => setNodes(nodes.map((n) => (n.id === selected.id ? { ...n, label: e.target.value } : n)))} /></Field>
          <Field label="Shape"><select className="field" value={selected.shape} aria-label="Shape" onChange={(e) => setNodes(nodes.map((n) => (n.id === selected.id ? { ...n, shape: e.target.value as Shape } : n)))}>{["box", "round", "decision", "circle", "note"].map((s) => <option key={s}>{s}</option>)}</select></Field>
        </div>
      )}
      {edges.length > 0 && (
        <details className="mt-2 text-sm"><summary className="cursor-pointer">Connections ({edges.length}): labels and removal</summary>
          <ul className="mt-1 space-y-1">{edges.map((e, i) => (
            <li key={i} className="flex flex-wrap items-center gap-2"><span>{byId.get(e.from)?.label} to {byId.get(e.to)?.label}</span>
              <input className="field !w-40 !py-0.5 text-xs" placeholder="label" aria-label={`Label for connection ${i + 1}`} value={e.label} maxLength={40} onChange={(ev) => setEdges(edges.map((x, j) => (j === i ? { ...x, label: ev.target.value } : x)))} />
              <button className="btn !py-0.5 text-xs" onClick={() => setEdges(edges.filter((_, j) => j !== i))}>Remove</button></li>))}</ul></details>
      )}
      <div className="mt-3 flex flex-wrap gap-2">
        <button className="btn" onClick={exportSvg} disabled={nodes.length === 0}>Download SVG</button>
        <button className="btn" onClick={() => dl("diagram.json", JSON.stringify({ n: nodes, e: edges }), "application/json")}>Save as file</button>
        <button className="btn" onClick={() => setJson(mermaid())}>Show as Mermaid text</button>
        <button className="btn" onClick={() => setJson(JSON.stringify({ n: nodes, e: edges }))}>Show file text</button>
      </div>
      <details className="mt-2 text-sm" open={json !== ""}><summary className="cursor-pointer">Text and import</summary>
        <textarea className="field mt-1 h-28 w-full font-mono text-xs" aria-label="Diagram text or file contents" value={json} onChange={(e) => setJson(e.target.value)} />
        <button className="btn mt-1" onClick={importJson}>Import file text</button></details>
    </Section>
  );
}
