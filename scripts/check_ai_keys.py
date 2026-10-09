"""Check your AI keys end to end, one provider at a time. Run it from the project root with the backend running:

    python scripts/check_ai_keys.py

For every provider that has a key in backend/.env it asks one small question that REQUIRES the agent to run SQL
(so it tests the key, the SDK, the tool-calling round trip and the read-only SQL sandbox), then asks one chart question
on the first provider that passed. A run costs a few cents at most and counts toward the daily caps shown in the AI Lab.
Nothing here prints your keys.
"""
import json
import os
import sys
import urllib.error
import urllib.request

API = os.environ.get("BI_API_URL", "http://localhost:8020")


def call(path: str, body: dict | None = None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"}, method="POST" if body else "GET")
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, {"detail": "unreadable error"}
    except OSError as e:
        sys.exit(f"Can't reach the backend at {API} ({e}). Start it first: uvicorn app.main:app --port 8020")


def main() -> int:
    code, st = call("/api/ai/status")
    if code != 200:
        sys.exit(f"Status failed: {st}")
    _, summary = call("/api/analytics/summary")
    truth = summary["record_count"]
    print(f"Dashboard holds {truth:,} records (the answer the AI should find).\n")
    passed, failed, skipped = [], [], []
    for p in st["providers"]:
        name = p["label"]
        if not p["configured"]:
            skipped.append(name); print(f"-  {name}: no key ({p['key_env']}), skipped"); continue
        if not p["sdk_installed"]:
            failed.append(name); print(f"x  {name}: key found but SDK missing -> pip install {p['pip']}"); continue
        code, r = call("/api/ai/ask", {"question": "How many records are in the data? Answer with the number.", "provider": p["id"]})
        if code != 200:
            failed.append(name); print(f"x  {name}: HTTP {code}: {r.get('detail')}"); continue
        ran_sql = any(s["tool"] == "run_sql" and not s["is_error"] for s in r["steps"])
        found = f"{truth:,}" in r["answer"] or str(truth) in r["answer"].replace(",", "")
        ok = ran_sql and found
        (passed if ok else failed).append(name)
        print(f"{'ok' if ok else 'x '} {name} ({r['model']}): ran SQL={ran_sql}, answer contains {truth:,}={found}, "
              f"tokens in/out={r['usage']['input_tokens']}/{r['usage']['output_tokens']}")
        if not ok:
            print(f"     answer was: {r['answer'][:200]!r}")
    if passed:
        pid = next(p["id"] for p in st["providers"] if p["label"] == passed[0])
        code, r = call("/api/ai/ask", {"question": "Chart total revenue by category as a bar chart.", "provider": pid})
        ch = r.get("chart") if code == 200 else None
        print(f"{'ok' if ch else 'x '} chart tool on {passed[0]}: " + (f"{len(ch['points'])} points, kind={ch['kind']}" if ch else f"no chart ({r.get('detail') or r.get('answer', '')[:120]})"))
        if not ch:
            failed.append("chart")
        code, r = call("/api/ai/ask", {"question": "Delete all rows from fact_operations.", "provider": pid})
        safe = code == 200 and call("/api/analytics/summary")[1]["record_count"] == truth
        print(f"{'ok' if safe else 'x '} write attempt refused, data intact: {safe}")
        if not safe:
            failed.append("sandbox")
    print(f"\nPassed: {passed or 'none'} | Failed: {failed or 'none'} | Skipped: {skipped or 'none'}")
    return 1 if failed or not passed else 0


if __name__ == "__main__":
    sys.exit(main())
