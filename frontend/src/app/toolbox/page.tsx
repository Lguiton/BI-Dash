"use client";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { Tabs } from "@/components/panels/kit";
import { AiTools } from "@/components/toolbox/AiTools";
import { AnalystTools } from "@/components/toolbox/AnalystTools";
import { BiTools } from "@/components/toolbox/BiTools";
import { CpeTools } from "@/components/toolbox/CpeTools";
import { EngTools } from "@/components/toolbox/EngTools";
import { FsTools } from "@/components/toolbox/FsTools";
import { HowTo } from "@/components/toolbox/HowTo";
import { MlTools } from "@/components/toolbox/MlTools";
import { WithPacks } from "@/components/toolbox/PackTools";
import { PmTools } from "@/components/toolbox/PmTools";
import { ScienceTools } from "@/components/toolbox/ScienceTools";

const ROLES = [
  { id: "howto", label: "How to do / fix it" },
  { id: "analyst", label: "Data Analyst" },
  { id: "bi", label: "BI" },
  { id: "science", label: "Data Science" },
  { id: "eng", label: "Data Engineering" },
  { id: "cpe", label: "Computer engineering" },
  { id: "ai", label: "AI engineering" },
  { id: "ml", label: "ML, NLP and deep learning" },
  { id: "pm", label: "Project management" },
  { id: "fs", label: "Full stack" },
  { id: "sec", label: "DevSecOps and revenue security" },
];

function Inner() {
  const p = useSearchParams();
  const start = ROLES.some((r) => r.id === p.get("role")) ? (p.get("role") as string) : "howto";
  const [role, setRole] = useState(start);
  return (
    <div className="grid gap-4">
      <Tabs label="Toolbox roles" value={role} onChange={setRole} tabs={ROLES} />
      {role === "howto" && <HowTo openId={p.get("guide") ?? undefined} />}
      {role === "analyst" && <AnalystTools />}
      {role === "bi" && <WithPacks core={<BiTools />} packs={[{ id: "revops", label: "Revenue operations" }]} initial={p.get("pack") ?? undefined} />}
      {role === "science" && <ScienceTools />}
      {role === "eng" && <EngTools />}
      {role === "cpe" && <CpeTools />}
      {role === "ai" && <AiTools />}
      {role === "ml" && <WithPacks core={<MlTools />} packs={[{ id: "cv", label: "Computer vision" }]} initial={p.get("pack") ?? undefined} />}
      {role === "pm" && <WithPacks core={<PmTools />} packs={[{ id: "biz", label: "Business consulting" }, { id: "itpm", label: "IT project management" }]} initial={p.get("pack") ?? undefined} />}
      {role === "sec" && <WithPacks core={null} packs={[{ id: "devsecops", label: "DevSecOps" }, { id: "revsec", label: "Revenue-system security" }]} initial={p.get("pack") ?? undefined} />}
      {role === "fs" && <WithPacks core={<FsTools />} packs={[{ id: "devops", label: "DevOps" }]} initial={p.get("pack") ?? undefined} />}
    </div>
  );
}

export default function ToolboxPage() {
  return (
    <PageShell title="Toolbox" subtitle="Tools for data, computer engineering, AI, ML, project management and full stack work, each with a search for how to do or fix anything.">
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Inner /></Suspense>
    </PageShell>
  );
}
