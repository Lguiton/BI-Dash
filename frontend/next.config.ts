import type { NextConfig } from "next";

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8020";
// Content-Security-Policy for the built app (not for `next dev`, which needs eval). The Web tab may show any https page in a frame.
const csp = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self' ${api} http://127.0.0.1:8020`,
  "frame-src https:",
  "worker-src 'self'",
  "manifest-src 'self'",
  "frame-ancestors 'none'",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
].join("; ");

// The in-browser Python runner (Code Workbench) is a Web Worker that needs WebAssembly. It gets its own policy, and can only reach this site's own files,
// so pasted code cannot call the dashboard's API on port 8020. Everything else keeps the strict policy above.
const pyCsp = "default-src 'none'; script-src 'self' 'wasm-unsafe-eval'; connect-src 'self'; worker-src 'self'; frame-ancestors 'none'; base-uri 'none'";

const nextConfig: NextConfig = {
  async headers() {
    const base = [
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "X-Frame-Options", value: "DENY" },
      { key: "Referrer-Policy", value: "no-referrer" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
    ];
    const prod = process.env.NODE_ENV === "production";
    return [
      { source: "/((?!pyodide/|pyrunner\\.mjs).*)", headers: prod ? [...base, { key: "Content-Security-Policy", value: csp }] : base },
      { source: "/pyodide/:path*", headers: prod ? [...base, { key: "Content-Security-Policy", value: pyCsp }] : base },
      { source: "/pyrunner.mjs", headers: prod ? [...base, { key: "Content-Security-Policy", value: pyCsp }] : base },
    ];
  },
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
