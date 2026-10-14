"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { Tabs } from "@/components/panels/kit";
import { WithPacks } from "@/components/toolbox/PackTools";

const FIELDS = [
  { id: "health", label: "Health data", note: "Clinical data science, health analytics, health BI and health informatics. Use de-identified or made-up data only.", packs: [{ id: "cds", label: "Clinical data science" }, { id: "hana", label: "Health analytics" }, { id: "hbi", label: "Health BI" }, { id: "hinf", label: "Health informatics" }] },
  { id: "science", label: "Science and research", note: "Statistics, genomic data science and research methods.", packs: [{ id: "stat", label: "Statistics" }, { id: "gen", label: "Genomic data science" }, { id: "sci", label: "Science and research" }] },
  { id: "cloud", label: "Cloud and design", note: "Cloud architecture, UI/UX and graphic design, digital marketing and social media.", packs: [{ id: "cloud", label: "Cloud architecture" }, { id: "ux", label: "UI/UX and graphic design" }, { id: "mkt", label: "Digital marketing" }] },
];

function Inner() {
  const p = useSearchParams();
  const f0 = FIELDS.find((x) => x.id === p.get("f"))?.id ?? "health";
  const [f, setF] = useState(f0);
  const cur = FIELDS.find((x) => x.id === f) ?? FIELDS[0];
  return (
    <div className="grid gap-4">
      <Tabs label="Fields" value={f} onChange={setF} tabs={FIELDS.map((x) => ({ id: x.id, label: x.label }))} />
      <p className="text-sm text-muted">{cur.note}</p>
      <WithPacks key={cur.id} core={null} packs={cur.packs} initial={p.get("pack") ?? undefined} />
    </div>
  );
}

export default function FieldsPage() {
  return (
    <PageShell title="More fields" subtitle="Health data, science and research, cloud and design. Each has a search for how to do or fix things, plus calculators, checkers and document writers.">
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Inner /></Suspense>
    </PageShell>
  );
}
