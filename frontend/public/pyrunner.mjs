// Runs pasted Python inside the browser (Pyodide, bundled in /pyodide, no internet needed). Standard library only.
// This worker has its own strict policy: it cannot reach the dashboard's API or the internet, and has no access to the page.
let py = null;
const post = (type, text) => self.postMessage({ type, text });
async function boot() {
  if (py) return py;
  const { loadPyodide } = await import("/pyodide/pyodide.mjs");
  py = await loadPyodide({ indexURL: "/pyodide/", stdout: (t) => post("out", t), stderr: (t) => post("err", t) });
  return py;
}
self.onmessage = async (e) => {
  const { code } = e.data || {};
  try {
    post("status", "Starting Python (first run takes a few seconds)…");
    const p = await boot();
    post("status", "Running…");
    const r = await p.runPythonAsync(String(code ?? ""));
    if (r !== undefined && r !== null) post("out", String(r));
    self.postMessage({ type: "done" });
  } catch (err) {
    post("err", String(err && err.message ? err.message : err));
    self.postMessage({ type: "done", failed: true });
  }
};
