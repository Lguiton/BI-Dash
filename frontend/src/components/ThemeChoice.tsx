"use client";
import { Monitor, Moon, Sun } from "lucide-react";
import { useSyncExternalStore } from "react";

type Choice = "light" | "dark" | "system";

function subscribe(cb: () => void) {
  const mo = new MutationObserver(cb);
  mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => mo.disconnect();
}
function snapshot(): Choice {
  const a = document.documentElement.getAttribute("data-theme");
  return a === "light" || a === "dark" ? a : "system";
}

/** Light, dark, or follow the computer. Remembered in this browser. */
export function ThemeChoice() {
  const cur = useSyncExternalStore(subscribe, snapshot, () => "system" as Choice);
  const set = (c: Choice) => {
    if (c === "system") document.documentElement.removeAttribute("data-theme");
    else document.documentElement.setAttribute("data-theme", c);
    try { if (c === "system") localStorage.removeItem("bi-theme"); else localStorage.setItem("bi-theme", c); } catch { /* storage unavailable: the choice just won't persist */ }
  };
  const opts: [Choice, string, typeof Sun][] = [["light", "Light", Sun], ["dark", "Dark", Moon], ["system", "Match my computer", Monitor]];
  return (
    <div role="group" aria-label="Theme" className="flex flex-wrap gap-2">
      {opts.map(([c, label, I]) => (
        <button key={c} type="button" className={`btn ${cur === c ? "btn-primary" : ""}`} aria-pressed={cur === c} onClick={() => set(c)}><I className="h-4 w-4" aria-hidden /> {label}</button>
      ))}
    </div>
  );
}
