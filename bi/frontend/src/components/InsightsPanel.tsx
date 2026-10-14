"use client";
import { AlertTriangle, CheckCircle2, Info, Sparkles } from "lucide-react";
import { useState } from "react";
import type { AnalyticsType, Insight } from "@/lib/types";

const STYLE = {
  positive: { bg: "var(--good-bg)", fg: "var(--good)", Icon: CheckCircle2, label: "Positive" },
  warning: { bg: "var(--warn-bg)", fg: "var(--fg)", Icon: AlertTriangle, label: "Needs attention" },
  info: { bg: "var(--info-bg)", fg: "var(--fg)", Icon: Info, label: "Note" },
} as const;

// The four BI analytics types, each answering one progressive question.
const GROUPS: { type: AnalyticsType; title: string; question: string }[] = [
  { type: "descriptive", title: "Descriptive", question: "What happened?" },
  { type: "diagnostic", title: "Diagnostic", question: "Why did it happen?" },
  { type: "predictive", title: "Predictive", question: "What is likely to happen?" },
  { type: "prescriptive", title: "Prescriptive", question: "What should we do?" },
];

const PER_GROUP = 3;

export function InsightsPanel({ insights, loading }: { insights: Insight[]; loading: boolean }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  return (
    <section className={`card p-5 transition-opacity ${loading ? "opacity-60" : ""}`} aria-label="Insights">
      <h2 className="flex items-center gap-2 text-sm font-semibold uppercase tracking-wide">
        <Sparkles className="h-4 w-4 text-accent" aria-hidden /> Insights
      </h2>
      <p className="mt-0.5 text-xs text-muted">Calculated from your data for the current filters. No guesses.</p>
      {insights.length === 0 && <p className="mt-4 text-sm text-muted">Loading…</p>}
      {GROUPS.map((g) => {
        const all = insights.filter((i) => i.analytics_type === g.type);
        if (!all.length) return null;
        const open = !!expanded[g.type];
        const items = open ? all : all.slice(0, PER_GROUP);
        return (
          <div key={g.type} className="mt-5">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-muted">
              {g.title} <span className="font-normal normal-case">· {g.question}</span>
            </h3>
            <ul className="mt-2 space-y-2">
              {items.map((i, idx) => {
                const s = STYLE[i.severity];
                return (
                  <li key={`${i.type}-${idx}`} className="flex gap-3 rounded-lg p-3" style={{ background: s.bg }}>
                    <s.Icon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: s.fg }} aria-label={s.label} />
                    <div>
                      <div className="text-sm font-semibold">{i.title}</div>
                      <div className="mt-0.5 text-xs text-muted">{i.detail}</div>
                    </div>
                  </li>
                );
              })}
            </ul>
            {all.length > PER_GROUP && (
              <button className="btn mt-2 text-xs" aria-expanded={open} onClick={() => setExpanded({ ...expanded, [g.type]: !open })}>
                {open ? "Show fewer" : `Show ${all.length - PER_GROUP} more`}
              </button>
            )}
          </div>
        );
      })}
    </section>
  );
}
