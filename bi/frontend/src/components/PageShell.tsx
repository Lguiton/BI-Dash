"use client";
import type { ReactNode } from "react";
import { CommandPalette, SearchButton } from "./CommandPalette";
import { NavBar } from "./NavBar";
import { WebDock } from "./WebDock";
import { ThemeToggle } from "./ThemeToggle";
import { RealBanner, WorkspaceSwitcher } from "./WorkspaceSwitcher";

export function PageShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="text-sm text-muted">{subtitle}</p>
        </div>
        <div className="flex flex-wrap items-start gap-2"><NavBar /><SearchButton /><WorkspaceSwitcher /><ThemeToggle /></div>
      </header>
      <CommandPalette />
      <RealBanner />
      {children}
      <WebDock />
    </div>
  );
}
