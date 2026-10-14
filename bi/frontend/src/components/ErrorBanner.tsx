"use client";
import { AlertTriangle } from "lucide-react";

export function ErrorBanner({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-line px-4 py-3 text-sm"
         style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="flex-1">{message}</div>
      {onRetry && (
        <button className="btn" onClick={onRetry}>Retry</button>
      )}
    </div>
  );
}
