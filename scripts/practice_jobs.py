"""Add 24 PRACTICE jobs: two different jobs for each of the 12 fields, each with three work items, so you can run the whole flow:
start the timer, close the job, make the invoice and the client summary.

Run while the backend is running:   python scripts/practice_jobs.py        (options: --url http://127.0.0.1:8020)
Practice workspace only. Everything is made up. Safe to run twice: it adds more jobs, it deletes nothing."""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from datetime import date, timedelta


def call(base, method, path, body=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{method} {path} failed: {e.code} {e.read().decode()[:200]}") from None


# (field, client, job title, quote, work items). Two different jobs per field, one practice client per field.
JOBS = [
 [
  "Data analyst",
  "Red Rock Cafe",
  "Weekly sales dashboard",
  240,
  [
   "Load the sales CSV and check for gaps and duplicates",
   "Build revenue by day and top items",
   "Write the 3-line summary for the owner"
  ]
 ],
 [
  "Data analyst",
  "Red Rock Cafe",
  "Find why Tuesday sales dropped",
  180,
  [
   "Compare Tuesdays to other days and weeks",
   "Split by item and by hour",
   "List what you could not check and what to ask the owner"
  ]
 ],
 [
  "Data scientist",
  "Vegas Fitness Club",
  "Does the email promo increase visits?",
  300,
  [
   "Define the question and the two groups",
   "Run the test and report the effect size and interval",
   "State what the result does and does not prove"
  ]
 ],
 [
  "Data scientist",
  "Vegas Fitness Club",
  "Group members into segments",
  260,
  [
   "Pick the features and clean them",
   "Cluster and check the groups make sense",
   "Name each segment and suggest one action per segment"
  ]
 ],
 [
  "Machine learning",
  "Desert Rentals",
  "Predict which customers will cancel",
  400,
  [
   "Check the target and class balance",
   "Train a simple baseline and a better model on a time-based split",
   "Report precision and recall, not only accuracy"
  ]
 ],
 [
  "Machine learning",
  "Desert Rentals",
  "Forecast next month's bookings",
  320,
  [
   "Plot the history and check seasonality",
   "Fit a naive forecast and a model, compare on the last 3 months",
   "Give the forecast with a range and the caveats"
  ]
 ],
 [
  "Engineering",
  "Mesa Fabrication",
  "Check shelf bracket load calculation",
  200,
  [
   "List inputs with units",
   "Calculate and sanity-check by rough estimate",
   "Write assumptions and a note that a licensed engineer must sign off"
  ]
 ],
 [
  "Engineering",
  "Mesa Fabrication",
  "Size a power supply for a small panel",
  150,
  [
   "Add up the loads and the worst case",
   "Choose a part with margin from the datasheet",
   "Document the calculation"
  ]
 ],
 [
  "AI engineering",
  "Henderson Realty",
  "Add an AI answer box to the FAQ page",
  450,
  [
   "Collect 15 real customer questions with right answers",
   "Give the model the FAQ text and tell it to say when it does not know",
   "Test the set before and after and keep it as a regression test"
  ]
 ],
 [
  "AI engineering",
  "Henderson Realty",
  "Cut AI costs for a chat feature",
  300,
  [
   "Measure tokens and calls per day",
   "Trim the prompt and cache repeats",
   "Re-test quality on the same question set"
  ]
 ],
 [
  "Project management",
  "Sunset Remodeling",
  "Plan a 6-week office move",
  350,
  [
   "List tasks, owners and dates",
   "Mark dependencies and the top 3 risks",
   "Write the weekly status format"
  ]
 ],
 [
  "Project management",
  "Sunset Remodeling",
  "Handle scope creep on a website",
  200,
  [
   "List what was agreed in writing",
   "Estimate each new request and its effect on the date",
   "Send the client the choices: add time, add cost, or swap"
  ]
 ],
 [
  "Systems analysis",
  "Valley Pediatrics",
  "Map the patient check-in process",
  300,
  [
   "Write the steps as they happen today",
   "Mark handoffs and retyping",
   "Pick the one change that removes the most waiting"
  ]
 ],
 [
  "Systems analysis",
  "Valley Pediatrics",
  "Write requirements for a booking form",
  250,
  [
   "Ask who uses it and what decision it supports",
   "Write each need as a testable statement",
   "List what is out of scope and confirm it"
  ]
 ],
 [
  "Cybersecurity",
  "Strip City Accounting",
  "Suspected phishing: employee entered a password",
  250,
  [
   "Reset the password and sign out all sessions",
   "Turn on multi-factor and check mail forwarding rules",
   "Write the incident note and the prevention step"
  ]
 ],
 [
  "Cybersecurity",
  "Strip City Accounting",
  "Basic security check-up for a 5-person office",
  300,
  [
   "List devices, accounts and backups",
   "Check updates, passwords and multi-factor",
   "Write a short prioritized fix list"
  ]
 ],
 [
  "Networking",
  "Sunrise Dental Office",
  "Fix office Wi-Fi dropping",
  150,
  [
   "Test wired vs Wi-Fi speed",
   "Check channel and router placement",
   "Write up the fix and the prevention step"
  ]
 ],
 [
  "Networking",
  "Sunrise Dental Office",
  "Set up a guest Wi-Fi separate from the office network",
  180,
  [
   "Plan the address ranges",
   "Configure the guest network and test isolation",
   "Document the settings"
  ]
 ],
 [
  "IT repair",
  "Palm Valley Bakery",
  "Laptop tune-up and cleanup",
  85,
  [
   "Back up files first",
   "Remove startup programs and run updates",
   "Check disk space and run a malware scan"
  ]
 ],
 [
  "IT repair",
  "Palm Valley Bakery",
  "Printer offline for the whole office",
  75,
  [
   "Check power, paper and link",
   "Clear the queue and restart the spooler",
   "Set a fixed address for the printer"
  ]
 ],
 [
  "Computer engineering",
  "Cactus Electronics",
  "Fix a noisy sensor reading on a microcontroller board",
  220,
  [
   "Check power and ground noise",
   "Add a capacitor and average samples",
   "Calibrate against a meter"
  ]
 ],
 [
  "Computer engineering",
  "Cactus Electronics",
  "Debug a design that works in simulation but not on hardware",
  350,
  [
   "Check clock and reset reach every part",
   "Look for unsynchronised clock crossings",
   "Add a probe at the failing point and compare"
  ]
 ],
 [
  "Full-stack",
  "Joshua Tree Tours",
  "Fix a booking form that returns an error",
  300,
  [
   "Read the status and response in the network tab",
   "Reproduce with a test and read the backend log",
   "Fix and add a test that failed before"
  ]
 ],
 [
  "Full-stack",
  "Joshua Tree Tours",
  "Review a form handler for SQL injection",
  250,
  [
   "Find where user text enters a query",
   "Switch to parameterised queries",
   "Add a test with a quote character"
  ]
 ]
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8020")
    base = ap.parse_args().url.rstrip("/")
    try:
        call(base, "GET", "/api/workspaces")
    except BaseException as e:  # noqa: BLE001
        sys.exit(f"Can't reach the backend at {base}: {e}\nStart it first (uvicorn app.main:app --port 8020).")
    call(base, "POST", "/api/workspaces/active", {"name": "practice"})
    clients: dict[str, int] = {}
    for n, (field, client, title, quote, steps) in enumerate(JOBS):
        name = f"{client} (practice)"
        if name not in clients:
            c = call(base, "POST", "/api/clients", {"name": name, "contact": "Practice contact", "email": f"practice{len(clients) + 1}@example.com", "notes": f"Practice client for {field}. Made up."})
            clients[name] = c["id"]
        j = call(base, "POST", "/api/clients/jobs/add", {"client_id": clients[name], "title": f"{field}: {title}", "status": "active", "quote": quote, "due": (date.today() + timedelta(days=3 + n)).isoformat()})
        for k, s in enumerate(steps):
            call(base, "POST", "/api/worklog", {"title": s, "client": name, "status": "doing" if k == 0 else "todo", "job_id": j["id"]})
        print(f"Added: {field}: {title} for {name} (quote ${quote})")
    print("\nOpen the dashboard: the jobs are on Home under Open jobs. Click one, start a timer on a work item, then Close job.")


main()
