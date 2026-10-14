"use client";
import { Briefcase, GraduationCap } from "lucide-react";
import { useMode } from "@/lib/mode";

/** One switch: Work mode (default, only what earns money) or Learn mode (study and practice). Nothing is deleted either way. */
export function ModeToggle() {
  const [mode, setMode] = useMode();
  const next = mode === "work" ? "learn" : "work";
  return (
    <button type="button" className="btn" onClick={() => setMode(next)} aria-label={`Switch to ${next === "learn" ? "Learn" : "Work"} mode`} title={mode === "work" ? "Work mode: only what you use to earn money. Click for Learn mode." : "Learn mode: study and practice. Click for Work mode."}>
      {mode === "work" ? <Briefcase className="h-4 w-4" aria-hidden /> : <GraduationCap className="h-4 w-4" aria-hidden />}
      <span>{mode === "work" ? "Work mode" : "Learn mode"}</span>
    </button>
  );
}
