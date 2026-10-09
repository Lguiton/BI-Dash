"use client";
import type { ReactNode } from "react";
import { NavBar } from "./NavBar";
import { ThemeToggle } from "./ThemeToggle";

export function PageShell({ title, subtitle, children }: { title: string; subtitle: string; children: ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-7xl space-y-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
          <p className="text-sm text-muted">{subtitle}</p>
        </div>
        <div className="flex flex-wrap gap-2"><NavBar /><ThemeToggle /></div>
      </header>
      {children}
    </div>
  );
}
