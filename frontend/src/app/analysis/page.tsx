"use client";
import { PageShell } from "@/components/PageShell";
import { AnalysisPanel } from "@/components/panels/AnalysisPanel";

export default function AnalysisPage() {
  return (
    <PageShell title="Analysis Lab" subtitle="Descriptive, diagnostic, predictive and prescriptive analysis, with probability, time series, filtering and regression, on your own data.">
      <AnalysisPanel />
    </PageShell>
  );
}
