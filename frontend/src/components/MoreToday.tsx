"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/panels/kit";
import { getJson } from "@/lib/api";

type Item = { text: string; href: string; tone: "muted" | "ok" | "warn" | "bad" };
type T = { todo: Item[] };

/** Extra things for today that the main Today panel doesn't cover: leads, unbilled work, drafts, quotes waiting, thank-yous and the business backup. */
export function MoreToday() {
  const [t, setT] = useState<T | null>(null);
  useEffect(() => {
    let live = true;
    getJson<T>("/api/today").then((r) => { if (live) setT(r); }).catch(() => { if (live) setT(null); });
    return () => { live = false; };
  }, []);
  if (!t || t.todo.length === 0) return null;
  return (
    <section className="card space-y-2 p-4" aria-label="Also worth doing">
      <h2 className="text-sm font-semibold">Also worth doing</h2>
      <ul className="space-y-1 text-sm">
        {t.todo.map((i) => <li key={i.text}><Badge tone={i.tone}>{i.tone === "muted" ? "when you can" : i.tone === "bad" ? "now" : "soon"}</Badge> <Link href={i.href} className="underline">{i.text}</Link></li>)}
      </ul>
    </section>
  );
}
