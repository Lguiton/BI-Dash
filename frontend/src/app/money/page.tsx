"use client";
import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { PageShell } from "@/components/PageShell";
import { BooksView, Owed, ProfitView } from "@/components/Money";
import { Tabs } from "@/components/panels/kit";

const TABS = [{ id: "owed", label: "Who owes me" }, { id: "profit", label: "Profit per job" }, { id: "books", label: "Expenses, mileage and tax" }];

function Body() {
  const sp = useSearchParams();
  const router = useRouter();
  const [tab, setTab] = useState(TABS.some((t) => t.id === sp.get("tab")) ? (sp.get("tab") as string) : "owed");
  const pick = (id: string) => { setTab(id); router.replace(`/money?tab=${id}`); };
  return (
    <div className="space-y-4">
      <Tabs tabs={TABS} value={tab} onChange={pick} label="Money" />
      {tab === "owed" && <Owed />}
      {tab === "profit" && <ProfitView />}
      {tab === "books" && <BooksView />}
    </div>
  );
}

export default function MoneyPage() {
  return (
    <PageShell title="Money" subtitle="Who owes you, what each job really earned, and your expenses, mileage and tax set-aside. Reminders are drafts you send yourself.">
      <Suspense fallback={<p className="text-sm text-muted">Loading…</p>}><Body /></Suspense>
    </PageShell>
  );
}
