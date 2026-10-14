"use client";
import { useEffect, useState } from "react";

type InstallEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };

/** Registers the service worker (production build only) and offers an Install button when the browser allows it. */
export function PwaSetup({ showButton = false }: { showButton?: boolean }) {
  const [ev, setEv] = useState<InstallEvent | null>(null);
  const [done, setDone] = useState(false);
  useEffect(() => {
    if ("serviceWorker" in navigator && process.env.NODE_ENV === "production") navigator.serviceWorker.register("/sw.js").catch(() => { /* needs localhost or https; ignore */ });
    const on = (e: Event) => { e.preventDefault(); setEv(e as InstallEvent); };
    const installed = () => setDone(true);
    window.addEventListener("beforeinstallprompt", on);
    window.addEventListener("appinstalled", installed);
    return () => { window.removeEventListener("beforeinstallprompt", on); window.removeEventListener("appinstalled", installed); };
  }, []);
  if (!showButton || done || !ev) return null;
  return <button className="btn" onClick={() => { ev.prompt().then(() => ev.userChoice).then((c) => { if (c.outcome === "accepted") setDone(true); }).catch(() => {}); }}>Install as an app</button>;
}
