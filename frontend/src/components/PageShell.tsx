"use client";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { isLearnPath, useMode } from "@/lib/mode";
import { LearnGate } from "./LearnGate";
import { ModeToggle } from "./ModeToggle";
import { CommandPalette, SearchButton } from "./CommandPalette";
import { AskBar } from "./AskBar";
import { JobBar } from "./JobBar";
import { UploadAnything } from "./UploadAnything";
import { NavBar } from "./NavBar";
import { WebDock } from "./WebDock";
import { RealBanner, SettingsButton } from "./WorkspaceSwitcher";
import { FileDown } from "lucide-react";

export function PageShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  const path = usePathname();
  const [mode] = useMode();
  const blocked = mode === "work" && isLearnPath(path);
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="text-sm text-muted">{subtitle}</p>
        </div>
        <div className="flex flex-wrap items-start gap-2 print:hidden"><NavBar /><SearchButton /><ModeToggle /><SettingsButton />
          <button className="btn" onClick={() => window.print()} title="Opens the print window. Choose Save as PDF as the printer."><FileDown className="h-4 w-4" aria-hidden /> Save page as PDF</button></div>
      </header>
      <div className="print:hidden"><AskBar /></div>
      <UploadAnything />
      {mode === "work" && <JobBar />}
      <CommandPalette />
      <div className="print:hidden"><RealBanner /></div>
      {blocked ? <LearnGate /> : children}
      <div className="print:hidden"><WebDock /></div>
    </div>
  );
}
