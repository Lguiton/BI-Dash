/** A tiny flowchart renderer for a subset of Mermaid syntax. It is our own code, not Mermaid: it draws boxes and arrows
 *  from lines like  A[Start] --> B{Ready?}  and  B -->|yes| C(Done).  Anything it can't read is reported, never guessed. */
export type Shape = "box" | "round" | "diamond" | "circle";
export interface DNode { id: string; label: string; shape: Shape; layer: number; slot: number; x: number; y: number; w: number; h: number }
export interface DEdge { from: string; to: string; label: string; dashed: boolean }
export interface Diagram { dir: "TD" | "LR"; nodes: DNode[]; edges: DEdge[]; width: number; height: number; errors: string[] }

const MAX_NODES = 60;
const NODE = /^([A-Za-z_][\w-]*)(?:\[\[?(.+?)\]?\]|\((?:\()?(.+?)(?:\))?\)|\{(.+?)\}|>(.+?)\])?$/;
const ARROW = /\s*(-->|---|-\.->|==>|--)\s*(?:\|([^|]*)\|)?\s*/;

function parseNode(raw: string, nodes: Map<string, { id: string; label: string; shape: Shape }>, errors: string[], lineNo: number): string | null {
  const t = raw.trim().replace(/;$/, "");
  const m = NODE.exec(t);
  if (!m) { errors.push(`Line ${lineNo}: couldn't read "${t.slice(0, 40)}".`); return null; }
  const id = m[1];
  const label = (m[2] ?? m[3] ?? m[4] ?? m[5] ?? "").replace(/^"|"$/g, "").trim();
  const shape: Shape = m[4] !== undefined ? "diamond" : m[3] !== undefined ? (t.includes("((") ? "circle" : "round") : "box";
  const cur = nodes.get(id);
  if (!cur) { if (nodes.size >= MAX_NODES) { errors.push(`More than ${MAX_NODES} boxes; the rest are ignored.`); return null; } nodes.set(id, { id, label: label || id, shape }); }
  else if (label) { cur.label = label; cur.shape = shape; }
  return id;
}

export function parseDiagram(src: string): Diagram {
  const errors: string[] = [];
  const nodes = new Map<string, { id: string; label: string; shape: Shape }>();
  const edges: DEdge[] = [];
  let dir: "TD" | "LR" = "TD";
  src.split(/\r?\n/).forEach((line, i) => {
    const l = line.trim();
    if (!l || l.startsWith("%%")) return;
    const head = /^(?:graph|flowchart)\s+(TD|TB|BT|LR|RL)\b/i.exec(l);
    if (head) { dir = /LR|RL/i.test(head[1]) ? "LR" : "TD"; return; }
    if (/^(subgraph|end|style|classDef|class|click|linkStyle)\b/.test(l)) { errors.push(`Line ${i + 1}: "${l.split(/\s/)[0]}" isn't supported in this small renderer and was skipped.`); return; }
    // split into node, arrow, node, arrow, node ...
    const parts: string[] = []; const links: { label: string; dashed: boolean }[] = [];
    let rest = l;
    for (;;) {
      const m = ARROW.exec(rest);
      if (!m || m.index === 0) { parts.push(rest); break; }
      parts.push(rest.slice(0, m.index));
      links.push({ label: (m[2] ?? "").trim(), dashed: m[1] === "-.->" });
      rest = rest.slice(m.index + m[0].length);
    }
    const ids = parts.map((p) => parseNode(p, nodes, errors, i + 1));
    for (let k = 0; k < links.length; k++) { const a = ids[k], b = ids[k + 1]; if (a && b) edges.push({ from: a, to: b, ...links[k] }); }
  });
  // Cut cycles first: a depth-first walk marks edges that point back to a box still being visited.
  const out = new Map<string, number[]>();
  edges.forEach((e, i) => out.set(e.from, [...(out.get(e.from) ?? []), i]));
  const back = new Set<number>();
  const mark = new Map<string, 1 | 2>();
  const walk = (id: string) => {
    mark.set(id, 1);
    for (const i of out.get(id) ?? []) {
      const t = edges[i].to;
      if (mark.get(t) === 1) back.add(i);
      else if (!mark.has(t)) walk(t);
    }
    mark.set(id, 2);
  };
  nodes.forEach((_, id) => { if (!mark.has(id)) walk(id); });
  // longest-path layering over the remaining edges
  const incoming = new Map<string, string[]>();
  edges.forEach((e, i) => { if (!back.has(i)) incoming.set(e.to, [...(incoming.get(e.to) ?? []), e.from]); });
  const layer = new Map<string, number>();
  const L = (id: string): number => {
    const known = layer.get(id);
    if (known !== undefined) return known;
    const v = Math.max(-1, ...(incoming.get(id) ?? []).map(L)) + 1;
    layer.set(id, v);
    return v;
  };
  nodes.forEach((_, id) => L(id));
  const byLayer = new Map<number, string[]>();
  nodes.forEach((_, id) => { const k = layer.get(id) ?? 0; byLayer.set(k, [...(byLayer.get(k) ?? []), id]); });
  const W = 150, H = 54, GX = 40, GY = 56;
  const maxSlots = Math.max(1, ...[...byLayer.values()].map((v) => v.length));
  const placed: DNode[] = [];
  byLayer.forEach((ids, k) => ids.forEach((id, s) => {
    const n = nodes.get(id)!;
    const off = (maxSlots - ids.length) / 2;
    const slot = s + off;
    const x = dir === "TD" ? slot * (W + GX) + 20 : k * (W + GY) + 20;
    const y = dir === "TD" ? k * (H + GY) + 20 : slot * (H + GX) + 20;
    placed.push({ ...n, layer: k, slot, x, y, w: W, h: H });
  }));
  const layers = Math.max(1, byLayer.size);
  const width = dir === "TD" ? maxSlots * (W + GX) + 20 : layers * (W + GY) + 20;
  const height = dir === "TD" ? layers * (H + GY) + 20 : maxSlots * (H + GX) + 20;
  return { dir, nodes: placed, edges, width, height, errors };
}
