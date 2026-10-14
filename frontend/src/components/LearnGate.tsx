"use client";
import Link from "next/link";
import { GraduationCap } from "lucide-react";
import { useMode } from "@/lib/mode";

/** Shown in place of a learning page while Work mode is on. */
export function LearnGate() {
  const [, setMode] = useMode();
  return (
    <section className="card space-y-3 p-6" aria-label="Learning page">
      <h2 className="flex items-center gap-2 text-lg font-semibold"><GraduationCap className="h-5 w-5" aria-hidden /> This page is for learning</h2>
      <p className="text-sm text-muted">Work mode hides study and practice pages so the dashboard stays on real work. Nothing was removed. Switch to Learn mode to open it.</p>
      <div className="flex flex-wrap gap-2">
        <button className="btn btn-primary" onClick={() => setMode("learn")}>Switch to Learn mode</button>
        <Link href="/" className="btn">Back to Home</Link>
      </div>
    </section>
  );
}
