"""Which field dashboard a job belongs to, so one click opens the right place to do the work.

Rules only (a "Field:" prefix on the title, then keyword counts); nothing is sent anywhere. The choice is a starting point:
the job bar lets you change it, and a stored choice always wins over the guess."""
from __future__ import annotations

import re

# key -> (label, dashboard path, title prefixes, keywords)
FIELDS: dict[str, tuple[str, str, tuple[str, ...], str]] = {
    "itsupport": ("IT repair", "/tracks/itsupport", ("it repair", "repair", "it support"),
                  "repair laptop phone screen battery printer tune-up cleanup virus slow computer pc mac tablet camera setup install driver windows"),
    "network": ("Networking", "/tracks/network", ("networking", "network"),
                "network wifi wi-fi router switch vlan subnet firewall dns dhcp vpn lan access point mesh cabling"),
    "security": ("Cybersecurity", "/tracks/security", ("cybersecurity", "security"),
                 "security phishing password malware ransomware breach hardening audit vulnerability mfa antivirus scam"),
    "analyst": ("Data analyst", "/tracks/analyst", ("data analyst", "analyst", "bi"),
                "dashboard report kpi sales revenue spreadsheet excel trend chart summary weekly"),
    "scientist": ("Data scientist", "/tracks/scientist", ("data scientist",),
                  "statistics hypothesis test experiment ab segment cluster regression significance"),
    "ml": ("Machine learning", "/tracks/ml", ("machine learning", "ml"), "predict forecast model train churn classification cancel"),
    "ai": ("AI engineering", "/tracks/ai", ("ai engineering", "ai"), "ai chatbot llm prompt faq assistant tokens rag"),
    "cpe": ("Engineering", "/tracks/cpe", ("engineering", "computer engineering"), "circuit power supply sensor microcontroller bracket load hardware embedded appliance hvac ac air conditioner conditioning furnace thermostat washer dryer refrigerator fridge dishwasher microwave oven electrical outlet breaker wiring"),
    "engineering": ("Data engineering", "/tracks/engineering", ("data engineering",), "pipeline etl warehouse database backup ingest"),
    "fullstack": ("Full stack", "/tracks/fullstack", ("full stack", "web", "website"), "website web app api form frontend backend deploy"),
    "pm": ("Project management", "/tracks/pm", ("project management", "pm"), "project plan schedule scope move timeline milestone"),
    "sysanalyst": ("Systems analysis", "/tracks/sysanalyst", ("systems analysis",), "requirements process map workflow check-in booking system"),
}
_TOK = re.compile(r"[a-z0-9][a-z0-9-]*")


def keys() -> list[str]:
    return list(FIELDS)


def info(key: str | None) -> dict | None:
    f = FIELDS.get(key or "")
    return {"key": key, "label": f[0], "href": f[1]} if f else None


def guess(title: str) -> str | None:
    t = (title or "").strip().lower()
    if ":" in t:
        head = t.split(":", 1)[0].strip()
        for k, f in FIELDS.items():
            if head == f[0].lower() or head in f[2]:
                return k
    words = set(_TOK.findall(t))
    best, score = None, 0
    for k, f in FIELDS.items():
        n = len(words & set(f[3].split()))
        if n > score:
            best, score = k, n
    return best


def of_job(job: dict) -> dict | None:
    """The field of a stored job: its saved choice, else a guess from the title."""
    k = job.get("field") if job.get("field") in FIELDS else guess(job.get("title", ""))
    return info(k)
