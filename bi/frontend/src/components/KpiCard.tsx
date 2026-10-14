"use client";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import type { ReactNode } from "react";
import { Line, LineChart, ResponsiveContainer } from "recharts";

interface Props {
  label: string;
  icon: ReactNode;
  value: string;
  caption?: string;
  delta?: number | null;
  deltaUnit?: "%" | " pts";
  /** Which direction is good: costs going up is bad. */
  goodWhen?: "up" | "down";
  spark?: number[];
  sparkColor?: string;
  loading?: boolean;
}

export function KpiCard({ label, icon, value, caption, delta, deltaUnit = "%", goodWhen = "up", spark, sparkColor, loading }: Props) {
  const hasDelta = delta != null && Number.isFinite(delta);
  const up = hasDelta && delta! > 0;
  const flat = hasDelta && Math.abs(delta!) < 0.05;
  const good = hasDelta && !flat && (goodWhen === "up" ? up : !up);
  const color = !hasDelta || flat ? "var(--muted)" : good ? "var(--good)" : "var(--bad)";

  return (
    <div className={`card p-4 transition-opacity ${loading ? "opacity-60" : ""}`}>
      <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wide text-muted">
        <span>{label}</span>
        <span aria-hidden>{icon}</span>
      </div>
      <div className="mt-2 text-2xl font-bold tabular-nums">{value}</div>
      <div className="mt-1 flex items-center justify-between gap-2 text-xs">
        {hasDelta ? (
          <span className="inline-flex items-center gap-0.5 font-medium" style={{ color }}>
            {flat ? <Minus className="h-3 w-3" aria-hidden /> : up ? <ArrowUpRight className="h-3 w-3" aria-hidden /> : <ArrowDownRight className="h-3 w-3" aria-hidden />}
            {flat ? "No change" : `${Math.abs(delta!).toFixed(1)}${deltaUnit}`}
            <span className="sr-only"> {flat ? "unchanged" : up ? "up" : "down"} versus previous period</span>
            <span className="ml-1 font-normal text-muted" aria-hidden>vs prev</span>
          </span>
        ) : (
          <span className="text-muted">{caption ?? ""}</span>
        )}
        {spark && spark.length > 1 && (
          <div className="h-8 w-20 shrink-0" aria-hidden>
            <ResponsiveContainer width="100%" height="100%" minWidth={20}>
              <LineChart data={spark.map((v, i) => ({ i, v }))}>
                <Line type="monotone" dataKey="v" stroke={sparkColor ?? "var(--accent)"} strokeWidth={1.75} dot={false} isAnimationActive={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
      {hasDelta && caption && <div className="mt-1 text-xs text-muted">{caption}</div>}
    </div>
  );
}
