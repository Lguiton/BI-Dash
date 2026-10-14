"use client";
import type { ReactNode } from "react";
import { usePathname } from "next/navigation";
import { isLearnPath, useMode } from "@/lib/mode";
import { LearnGate } from "./LearnGate";
import { ModeToggle } from "./ModeToggle";
import { CommandPalette, SearchButton } from "./CommandPalette";
import { AskBar } from "./AskBar";
import { NavBar } from "./NavBar";
import { WebDock } from "./WebDock";
import { RealBanner, SettingsButton } from "./WorkspaceSwitcher";

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
        <div className="flex flex-wrap items-start gap-2"><NavBar /><SearchButton /><ModeToggle /><SettingsButton /></div>
      </header>
      <AskBar />
      <CommandPalette />
      <RealBanner />
      {blocked ? <LearnGate /> : children}
      <WebDock />
    </div>
  );
}
