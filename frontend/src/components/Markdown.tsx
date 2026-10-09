"use client";
import Link from "next/link";
import type { ReactNode } from "react";

/** A tiny, safe markdown renderer for AI replies: bold, italics, code, links, lists and headings. It never injects HTML.
 *  Links that start with "#" are in-app tab links (for example [Open backlog](#backlog)) and are handed to onTab. */
const INLINE = /(\*\*[^*\n]+\*\*|`[^`\n]+`|\[[^\]\n]+\]\([^)\s]+\)|\*[^*\n]+\*)/g;

function inline(text: string, onTab?: (tab: string, label: string) => void): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    if (!part) return null;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) return <code key={i} className="rounded bg-panel2 px-1 text-[0.85em]">{part.slice(1, -1)}</code>;
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) return <em key={i}>{part.slice(1, -1)}</em>;
    const m = /^\[([^\]]+)\]\(([^)\s]+)\)$/.exec(part);
    if (m) {
      const [, label, href] = m;
      if (href.startsWith("#")) {
        return onTab ? <button key={i} type="button" className="underline decoration-dotted" onClick={() => onTab(href.slice(1), label)}>{label}</button> : <span key={i}>{label}</span>;
      }
      if (/^\/[a-z0-9/_-]*$/i.test(href)) return <Link key={i} href={href} className="underline">{label}</Link>;
      if (/^https?:\/\//i.test(href)) return <a key={i} href={href} target="_blank" rel="noopener noreferrer" className="underline">{label}</a>;
      return <span key={i}>{label}</span>;          // anything else (javascript:, data:) is shown as plain text
    }
    return part;
  });
}

export function Markdown({ text, onTab }: { text: string; onTab?: (tab: string, label: string) => void }) {
  const blocks: ReactNode[] = [];
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }
    const ul = /^\s*[-*•]\s+/, ol = /^\s*\d+[.)]\s+/;
    if (ul.test(line) || ol.test(line)) {
      const ordered = ol.test(line), re = ordered ? ol : ul, items: string[] = [];
      while (i < lines.length && re.test(lines[i])) { items.push(lines[i].replace(re, "")); i++; }
      const li = items.map((t, k) => <li key={k}>{inline(t, onTab)}</li>);
      blocks.push(ordered ? <ol key={blocks.length} className="list-decimal space-y-0.5 pl-5">{li}</ol> : <ul key={blocks.length} className="list-disc space-y-0.5 pl-5">{li}</ul>);
      continue;
    }
    const h = /^#{1,4}\s+(.*)$/.exec(line);
    if (h) { blocks.push(<p key={blocks.length} className="font-semibold">{inline(h[1], onTab)}</p>); i++; continue; }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !ul.test(lines[i]) && !ol.test(lines[i]) && !/^#{1,4}\s/.test(lines[i])) { para.push(lines[i]); i++; }
    blocks.push(<p key={blocks.length}>{inline(para.join(" "), onTab)}</p>);
  }
  return <div className="space-y-2 break-words">{blocks}</div>;
}
