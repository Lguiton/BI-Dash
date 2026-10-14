"use client";
import { PageShell } from "@/components/PageShell";
import { PipelinePanel } from "@/components/PipelinePanel";

export default function PipelinePage() {
  return (
    <PageShell title="Pipeline monitor" subtitle="Bronze → silver → gold with DuckDB and Parquet (data_engineering/medallion.py).">
      <PipelinePanel />
    </PageShell>
  );
}
