"use client";
import { useMemo, useRef, useState } from "react";
import { PageShell } from "@/components/PageShell";
import { Section } from "@/components/panels/kit";
import { parseDiagram, type DNode } from "@/lib/diagram";

const SAMPLES: Record<string, string> = {
  "Order process": "graph TD\nA[Order received] --> B{In stock?}\nB -->|yes| C[Pack and ship]\nB -->|no| D[Back-order]\nD --> B\nC --> E((Done))",
  "ETL pipeline": "graph LR\nSRC[(CSV files)] --> RAW[Bronze: raw]\nRAW --> CLEAN[Silver: cleaned]\nCLEAN --> GOLD[Gold: reporting]\nCLEAN -->|bad rows| Q[Quarantine]",
  "Incident response": "graph TD\nD[Detect] --> T{Real incident?}\nT -->|no| N[Close as noise]\nT -->|yes| C[Contain]\nC --> E[Preserve evidence]\nE --> R[Recover]\nR --> L[Lessons learned]",
};

function edgePath(a: DNode, b: DNode, dir: "TD" | "LR") {
  const ax = a.x + a.w / 2, ay = a.y + a.h / 2, bx = b.x + b.w / 2, by = b.y + b.h / 2;
  if (a === b) return { d: `M ${a.x + a.w} ${ay - 8} C ${a.x + a.w + 40} ${ay - 30}, ${a.x + a.w + 40} ${ay + 30}, ${a.x + a.w} ${ay + 8}`, lx: a.x + a.w + 30, ly: ay };
  if (dir === "TD") {
    const down = by > ay;
    const sx = ax, sy = down ? a.y + a.h : a.y, ex = bx, ey = down ? b.y : b.y + b.h;
    const my = (sy + ey) / 2;
    return { d: `M ${sx} ${sy} C ${sx} ${my}, ${ex} ${my}, ${ex} ${ey}`, lx: (sx + ex) / 2, ly: my };
  }
  const right = bx > ax;
  const sx = right ? a.x + a.w : a.x, sy = ay, ex = right ? b.x : b.x + b.w, ey = by;
  const mx = (sx + ex) / 2;
  return { d: `M ${sx} ${sy} C ${mx} ${sy}, ${mx} ${ey}, ${ex} ${ey}`, lx: mx, ly: (sy + ey) / 2 };
}

function Box({ n }: { n: DNode }) {
  const cx = n.x + n.w / 2, cy = n.y + n.h / 2;
  const words = n.label.length > 22 ? [n.label.slice(0, 22), n.label.slice(22, 44)] : [n.label];
  return (
    <g>
      {n.shape === "diamond" ? <polygon points={`${cx},${n.y - 6} ${n.x + n.w + 8},${cy} ${cx},${n.y + n.h + 6} ${n.x - 8},${cy}`} fill="var(--panel-2)" stroke="var(--accent)" strokeWidth="1.5" />
        : n.shape === "circle" ? <ellipse cx={cx} cy={cy} rx={n.w / 2.4} ry={n.h / 2} fill="var(--panel-2)" stroke="var(--accent)" strokeWidth="1.5" />
        : <rect x={n.x} y={n.y} width={n.w} height={n.h} rx={n.shape === "round" ? 24 : 6} fill="var(--panel-2)" stroke="var(--accent)" strokeWidth="1.5" />}
      <text x={cx} y={cy + (words.length > 1 ? -2 : 4)} textAnchor="middle" fontSize="12" fill="var(--fg)">{words.map((w, i) => <tspan key={i} x={cx} dy={i ? 14 : 0}>{w}</tspan>)}</text>
    </g>
  );
}

export default function DiagramsPage() {
  const [src, setSrc] = useState(SAMPLES["Order process"]);
  const d = useMemo(() => parseDiagram(src), [src]);
  const svg = useRef<SVGSVGElement>(null);
  const byId = new Map(d.nodes.map((n) => [n.id, n]));
  const download = () => {
    if (!svg.current) return;
    const el = svg.current.cloneNode(true) as SVGSVGElement;
    el.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    el.style.cssText = "background:#fff";
    el.querySelectorAll("*").forEach((n) => { n.getAttributeNames().forEach((a) => { const v = n.getAttribute(a) ?? ""; if (v.startsWith("var(")) n.setAttribute(a, v.includes("--bg") ? "#ffffff" : v.includes("accent") ? "#2563eb" : v.includes("panel-2") ? "#f1f5f9" : "#0f172a"); }); });
    const blob = new Blob([el.outerHTML], { type: "image/svg+xml" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "diagram.svg"; a.click();
    URL.revokeObjectURL(a.href);
  };
  return (
    <PageShell title="Diagram studio" subtitle="Type a flowchart as text and see it drawn. A free, small take on Mermaid and draw.io for process maps and pipelines.">
      <p className="rounded border border-line bg-panel2 p-3 text-xs text-muted">Honest label: this is our own small renderer for a Mermaid-style subset (graph TD / LR, boxes <code>[ ]</code>, rounded <code>( )</code>, decisions <code>{"{ }"}</code>, circles <code>(( ))</code>, arrows <code>--&gt;</code> with <code>|labels|</code>). It does not run Mermaid, so sequence diagrams, subgraphs and styling are not supported.</p>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        <Section title="Diagram text">
          <div className="mb-2 flex flex-wrap gap-2">{Object.keys(SAMPLES).map((k) => <button key={k} className="btn" onClick={() => setSrc(SAMPLES[k])}>{k}</button>)}</div>
          <textarea className="field h-72 w-full font-mono text-xs" style={{ fontVariantLigatures: "none" }} aria-label="Diagram text" value={src} spellCheck={false} onChange={(e) => setSrc(e.target.value)} />
          {d.errors.length > 0 && <ul role="alert" className="mt-2 list-disc pl-5 text-xs text-amber-600">{d.errors.map((e) => <li key={e}>{e}</li>)}</ul>}
        </Section>
        <Section title="Preview">
          {d.nodes.length === 0 ? <p className="text-sm text-muted">Nothing to draw yet. Try: <code>A[Start] --&gt; B[Finish]</code></p> : (
            <div className="overflow-auto">
              <svg ref={svg} role="img" aria-label={`Flowchart with ${d.nodes.length} boxes`} width={d.width + 60} height={d.height + 10} viewBox={`0 0 ${d.width + 60} ${d.height + 10}`}>
                <defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="var(--muted)" /></marker></defs>
                {d.edges.map((e, i) => {
                  const a = byId.get(e.from), b = byId.get(e.to);
                  if (!a || !b) return null;
                  const p = edgePath(a, b, d.dir);
                  return <g key={i}><path d={p.d} fill="none" stroke="var(--muted)" strokeWidth="1.4" strokeDasharray={e.dashed ? "5 4" : undefined} markerEnd="url(#arrow)" />
                    {e.label && <text x={p.lx} y={p.ly - 4} textAnchor="middle" fontSize="11" fill="var(--fg)" stroke="var(--bg)" strokeWidth="3" paintOrder="stroke">{e.label}</text>}</g>;
                })}
                {d.nodes.map((n) => <Box key={n.id} n={n} />)}
              </svg>
            </div>
          )}
          <button className="btn mt-3" disabled={d.nodes.length === 0} onClick={download}>Download SVG</button>
        </Section>
      </div>
    </PageShell>
  );
}
