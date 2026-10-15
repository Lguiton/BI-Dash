"""Fill the PRACTICE workspace with made-up test data so every field has something to show.

Run it while the backend is running:   python scripts/seed_test_data.py
Options:   --url http://127.0.0.1:8020    --real   (refuses unless you also pass --yes-real)

Everything here is invented (fake names, fake addresses, fake numbers). It uses the app's own API, so the data goes
through the same checks as anything you type. It switches to the Practice workspace first and never touches Real.
Safe to run more than once: it adds more rows; it does not delete anything."""
from __future__ import annotations

import argparse
import json
import sys
import uuid
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK, BAD = [], []


def call(base, method, path, body=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method, headers={"Content-Type": ctype} if data is not None else {})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            txt = r.read().decode("utf-8", "replace")
            return json.loads(txt) if txt[:1] in "{[" else txt
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8", "replace")[:160]
        if e.code == 409:                       # "already has data" is fine when you run this twice
            return {"already": msg}
        raise RuntimeError(f"{e.code} {msg}") from None


def step(label, fn):
    try:
        out = fn()
        OK.append(label)
        print("  ok   ", label)
        return out
    except Exception as e:  # noqa: BLE001 - report and keep going
        BAD.append((label, str(e)))
        print("  FAIL ", label, "->", e)
        return None


def csv_upload(base, path: Path, mode="append"):
    b = uuid.uuid4().hex
    body = (f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\nContent-Type: text/csv\r\n\r\n").encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
    return call(base, "POST", f"/api/ingest/csv?mode={mode}", raw=body, ctype=f"multipart/form-data; boundary={b}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8020")
    ap.add_argument("--real", action="store_true")
    ap.add_argument("--yes-real", action="store_true")
    a = ap.parse_args()
    base = a.url.rstrip("/")
    target = "real" if a.real else "practice"
    if target == "real" and not a.yes_real:
        sys.exit("Refusing to write test data into Real. Add --yes-real only if you truly want that.")
    try:
        call(base, "GET", "/api/workspaces")
    except Exception as e:  # noqa: BLE001
        sys.exit(f"Can't reach the backend at {base}: {e}\nStart it first (uvicorn app.main:app --port 8020).")
    print(f"Seeding the {target} workspace at {base}\n")
    step(f"switch to {target}", lambda: call(base, "POST", "/api/workspaces/active", {"name": target}))
    today = date.today()
    d = lambda n: (today + timedelta(days=n)).isoformat()  # noqa: E731

    print("\nData and dashboards")
    step("operations data (clean sample CSV)", lambda: csv_upload(base, ROOT / "data_samples" / "operations_clean.csv"))
    step("business dashboard packs (all samples)", lambda: call(base, "POST", "/api/biz-packs/samples"))

    print("\nClients, jobs, time, invoices")
    people = [("Desert Dental Group", "Maria Lopez", "maria@desertdental.example", "Wants a weekly revenue dashboard."),
              ("Silver State Plumbing", "Tom Reyes", "tom@silverplumbing.example", "Laptops slow, shared printer drops off Wi-Fi."),
              ("Henderson Yoga Studio", "Ava Kim", "ava@hendersonyoga.example", "Booking site and email setup."),
              ("Mesa Logistics LLC", "Dwayne Ellis", "dwayne@mesalogistics.example", "Route cost analysis and a small network.")]
    cids = []
    for n, c, e, note in people:
        r = step(f"client: {n}", lambda n=n, c=c, e=e, note=note: call(base, "POST", "/api/clients", {"name": n, "contact": c, "email": e, "notes": note}))
        if r:
            cids.append(r.get("id") or (r.get("client") or {}).get("id"))
    cids = [c for c in cids if c]
    jobs = [(0, "Weekly revenue dashboard", "active", 1800, 75, 10), (0, "Clean up patient-visit export", "done", 450, 70, -5),
            (1, "Laptop tune-up x4", "done", 320, 75, -3), (1, "Fix printer Wi-Fi drops", "active", 150, 85, 2),
            (2, "Email and domain setup", "quoted", 400, 75, 14), (2, "Booking site security check", "lead", 600, 90, 21),
            (3, "Route cost analysis", "active", 2200, 85, 12), (3, "Office network and VLAN plan", "quoted", 1500, 85, 30)]
    jids = []
    for ci, title, st, quote, rate, due in jobs:
        if ci >= len(cids):
            continue
        r = step(f"job: {title}", lambda ci=ci, title=title, st=st, quote=quote, rate=rate, due=due: call(base, "POST", "/api/clients/jobs/add", {"client_id": cids[ci], "title": title, "status": st, "quote": quote, "rate": rate, "due": d(due)}))
        if r:
            jids.append(r.get("id") or (r.get("job") or {}).get("id"))
    for k, jid in enumerate([j for j in jids if j][:6]):
        step(f"time entry {k + 1}", lambda jid=jid, k=k: call(base, "POST", "/api/clients/time/add", {"job_id": jid, "date": d(-k - 1), "hours": [1.5, 2, 0.75, 3, 1, 2.5][k], "note": "Test entry", "billable": True}))
    for k, ci in enumerate(cids[:3]):
        step(f"follow-up {k + 1}", lambda ci=ci, k=k: call(base, "POST", "/api/clients/followups/add", {"client_id": ci, "due": d(k), "note": ["Send the quote", "Ask about payment", "Book a check-in call"][k]}))
    if cids:
        inv = step("invoice from unbilled time", lambda: call(base, "POST", "/api/clients/invoices/create", {"client_id": cids[1] if len(cids) > 1 else cids[0], "extra": [{"desc": "Replacement SSD (test)", "qty": 1, "rate": 89}]}))
        if inv and (inv.get("id") or (inv.get("invoice") or {}).get("id")):
            step("mark invoice sent", lambda: call(base, "PUT", f"/api/clients/invoices/{inv.get('id') or inv['invoice']['id']}", {"status": "sent"}))

    print("\nWork log (the list on the home screen)")
    for t, c, st, dd in [("Fix printer Wi-Fi drops", "Silver State Plumbing", "doing", 2), ("Send revenue dashboard draft", "Desert Dental Group", "todo", 0),
                         ("Waiting on router login from client", "Mesa Logistics LLC", "waiting", 5), ("Quote email setup", "Henderson Yoga Studio", "todo", -1)]:
        step(f"work item: {t}", lambda t=t, c=c, st=st, dd=dd: call(base, "POST", "/api/worklog", {"title": t, "client": c, "status": st, "due": d(dd)}))

    print("\nFix log: IT repair, Cybersecurity, Network")
    fixes = [
        ("it", "Laptop boots to black screen after Windows update", "Windows", "Dell Latitude 5420", "Black screen with cursor after login", "Corrupt display driver after update",
         ["Boot to safe mode (hold Shift while restarting)", "Open Device Manager, uninstall the display adapter", "Restart and let Windows reinstall the driver", "Check Windows Update for the vendor driver"], "fixed", 35, "Safe mode, Device Manager", "Pause driver updates on older laptops", "Silver State Plumbing", ["windows", "display", "driver"]),
        ("it", "Printer shows offline on Wi-Fi", "Printing", "HP LaserJet M404", "Printer goes offline every few hours", "Printer got a new IP from DHCP",
         ["Print the network config page", "Reserve the printer's IP in the router", "Re-add the printer by IP", "Print a test page the next day"], "fixed", 25, "Router admin page", "Reserve IPs for shared devices", "Silver State Plumbing", ["printer", "wifi", "dhcp"]),
        ("it", "Outlook keeps asking for password", "Email", "Surface Pro 8", "Repeated sign-in prompts", "Stale cached credentials",
         ["Close Outlook", "Remove the entries from Credential Manager", "Reopen and sign in once"], "fixed", 15, "Credential Manager", "", "Henderson Yoga Studio", ["outlook", "credentials"]),
        ("it", "Slow desktop, disk at 100 percent", "Performance", "Custom desktop", "Everything freezes for minutes", "Failing hard drive (reallocated sectors rising)",
         ["Check SMART data", "Back up the data first", "Clone to a new SSD", "Verify boot from the SSD"], "workaround", 120, "SMART tool, clone tool", "Replace old HDDs, keep backups", "Mesa Logistics LLC", ["disk", "ssd", "smart"]),
        ("security", "Phishing email with fake invoice link", "Phishing", "", "Staff received an invoice email from an unknown sender", "Credential-harvest link",
         ["Do not click; report to the owner", "Check the sender and link domain", "Block the sender", "Reset the password of anyone who clicked", "Turn on multi-factor sign-in"], "fixed", 45, "Email headers, MFA", "Run a short phishing awareness talk", "Desert Dental Group", ["phishing", "mfa"]),
        ("security", "Router admin page open to the internet", "Exposure", "Consumer router", "Remote admin enabled with the default password", "Remote management left on",
         ["Turn off remote management", "Change the admin password", "Update the firmware", "Confirm the port is closed from outside"], "fixed", 30, "Router admin page", "Review router settings every quarter", "Henderson Yoga Studio", ["router", "exposure", "firmware"]),
        ("security", "Suspicious sign-in alerts on the shared mailbox", "Account", "", "Sign-ins from another country", "Reused password found in a breach list",
         ["Force sign-out everywhere", "Reset the password", "Enable MFA", "Review forwarding rules"], "fixed", 40, "Admin console", "Use a password manager", "Desert Dental Group", ["account", "mfa", "breach"]),
        ("network", "Wi-Fi drops in the back office", "Wi-Fi", "Mesh node", "Weak signal and drops past one wall", "Access point on a crowded channel",
         ["Walk the area with a Wi-Fi analyzer", "Move the node closer to the middle", "Set a fixed channel", "Retest the speed in the back office"], "fixed", 50, "Wi-Fi analyzer", "Plan coverage before install", "Mesa Logistics LLC", ["wifi", "channel", "coverage"]),
        ("network", "Two devices share one IP", "IP conflict", "", "Intermittent connection loss on two PCs", "A static IP inside the DHCP range",
         ["Find the duplicate with arp", "Move the static IP outside the DHCP pool", "Renew the leases"], "fixed", 20, "arp, ipconfig", "Keep static IPs outside the pool", "Mesa Logistics LLC", ["ip", "dhcp"]),
        ("network", "Guest Wi-Fi can reach the office printer", "Segmentation", "", "Visitors could see internal devices", "No separation between guest and office networks",
         ["Create a guest VLAN", "Block guest to office traffic", "Test from a guest phone"], "workaround", 90, "Router and switch config", "Isolate guests from day one", "Mesa Logistics LLC", ["vlan", "guest", "segmentation"]),
    ]
    for area, title, cat, dev, sym, cause, steps, res, mins, tools, prev, cl, tags in fixes:
        step(f"fix [{area}]: {title[:48]}", lambda area=area, title=title, cat=cat, dev=dev, sym=sym, cause=cause, steps=steps, res=res, mins=mins, tools=tools, prev=prev, cl=cl, tags=tags: call(
            base, "POST", "/api/fixlog", {"area": area, "title": title, "category": cat, "device": dev, "symptoms": sym, "cause": cause, "steps": steps, "result": res, "minutes": mins, "tools": tools, "prevention": prev, "client": cl, "tags": tags}))
    step("secret blanking works (fake key in notes)", lambda: call(base, "POST", "/api/fixlog", {"area": "it", "title": "Test: fake key is blanked", "steps": ["Set password: hunter2hunter2", "key AKIA" + "ABCDEFGHIJKLMNOP"], "result": "fixed"}))

    print("\nProject management and product")
    step("PM example project", lambda: call(base, "POST", "/api/pm/example"))
    step("PM scenario (website project)", lambda: call(base, "POST", "/api/pm/scenarios/practice/load", {"kind": "website", "seed": 1}))

    print("\nEvery tool in every field pack, run with its own sample inputs")
    packs = (call(base, "GET", "/api/fieldpacks") or {}).get("packs", [])
    for pk in packs:
        sch = call(base, "GET", f"/api/fieldpacks/{pk['id']}")
        good = 0
        for t in sch.get("tools", []):
            vals = {i["name"]: i.get("default", "") for i in t.get("inputs", [])}
            try:
                call(base, "POST", f"/api/fieldpacks/{pk['id']}/{t['id']}", vals)
                good += 1
            except Exception as e:  # noqa: BLE001
                BAD.append((f"{pk['id']}/{t['id']}", str(e)))
                print("  FAIL ", f"{pk['id']}/{t['id']}", "->", e)
        OK.append(pk["id"])
        print(f"  ok    {pk['label']}: {good}/{len(sch.get('tools', []))} tools ran")

    print("\nChecks (read-back)")
    step("clients overview", lambda: call(base, "GET", "/api/clients/overview"))
    step("open jobs", lambda: call(base, "GET", "/api/clients/open-jobs"))
    step("fix log search 'printer offline'", lambda: call(base, "GET", "/api/fixlog/search?q=printer%20offline"))
    step("price list", lambda: call(base, "GET", "/api/service-list/price-list"))
    step("KPIs", lambda: call(base, "GET", "/api/kpis"))
    print(f"\nDone: {len(OK)} steps ok, {len(BAD)} failed.")
    for label, err in BAD:
        print("  -", label, "->", err)
    sys.exit(1 if BAD else 0)


if __name__ == "__main__":
    main()
