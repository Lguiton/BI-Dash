import { API_BASE } from "@/lib/api";

/** Fetches a file from the API and saves it. Errors come back as readable text instead of a broken download. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  let res: Response;
  try { res = await fetch(`${API_BASE}${path}`); }
  catch { throw new Error(`Can't reach the analytics API at ${API_BASE}.`); }
  if (!res.ok) {
    let msg = `The download failed (${res.status}).`;
    try { const b = await res.json(); if (typeof b?.detail === "string") msg = b.detail; } catch { /* keep the generic message */ }
    throw new Error(msg);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(url);
}
