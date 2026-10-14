"use client";
import { PageShell } from "@/components/PageShell";
import { ComputerPanel } from "@/components/panels/ComputerPanel";

export default function ComputerPage() {
  return (
    <PageShell title="Computer control" subtitle="Maintenance, settings, network, accounts and security checks on this computer, with a PIN, undo and a fallback.">
      <ComputerPanel />
    </PageShell>
  );
}
