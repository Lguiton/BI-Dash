"use client";
import { useCallback, useEffect, useState } from "react";
import { API_BASE, apiFetch } from "@/lib/api";

type St = "loading" | "open" | "login" | "down";

/** Shows a one-password sign-in when the server has login turned on (BI_AUTH=1). With login off it does nothing. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const [st, setSt] = useState<St>("loading");
  const [enabled, setEnabled] = useState(false);
  const [pw, setPw] = useState("");
  const [err, setErr] = useState("");
  const check = useCallback(async () => {
    try {
      const r = await apiFetch(`${API_BASE}/api/auth/status`);
      const j = await r.json();
      setEnabled(!!j.enabled);
      setSt(j.authenticated ? "open" : "login");
    } catch { setSt("down"); }
  }, []);
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- async fetch of external auth state on mount
    void check();
    const on = () => setSt("login");
    window.addEventListener("bi-auth-required", on);
    return () => window.removeEventListener("bi-auth-required", on);
  }, [check]);
  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr("");
    const r = await apiFetch(`${API_BASE}/api/auth/login`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password: pw }) });
    if (r.ok) { setPw(""); setSt("open"); return; }
    const j = await r.json().catch(() => ({}));
    setErr(typeof j.detail === "string" ? j.detail : "Could not sign in.");
  }
  async function out() { await apiFetch(`${API_BASE}/api/auth/logout`, { method: "POST" }); setSt("login"); }
  if (st === "loading") return <p className="p-6 text-sm text-muted">Loading...</p>;
  if (st === "login") {
    return (
      <main className="mx-auto mt-24 w-full max-w-sm px-4">
        <form onSubmit={submit} className="card space-y-3 p-5">
          <h1 className="text-lg font-semibold">Sign in</h1>
          <p className="text-xs text-muted">This dashboard is private. Enter the owner password.</p>
          <label className="block text-sm">Password<input className="field mt-1 w-full" type="password" autoComplete="current-password" autoFocus value={pw} onChange={(e) => setPw(e.target.value)} aria-label="Password" /></label>
          {err && <p role="alert" className="text-sm" style={{ color: "var(--bad)" }}>{err}</p>}
          <button className="btn btn-primary w-full" disabled={!pw}>Sign in</button>
        </form>
      </main>
    );
  }
  return (
    <>
      {children}
      {enabled && st === "open" && <button className="btn fixed bottom-3 right-3 z-50 text-xs opacity-80 hover:opacity-100" onClick={out}>Sign out</button>}
    </>
  );
}
