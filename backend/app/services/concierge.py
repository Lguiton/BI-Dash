"""The 'type what you need' bar: turns a plain sentence into the best places to go (dashboards, labs, agents, tools).

Rules and keyword scoring over what the app actually contains, so it works offline, is predictable and sends nothing anywhere.
It only chooses where to go; the destination does the work. It never reads your records, only the names of your dashboards."""
from __future__ import annotations

import re
from urllib.parse import quote

from app.services import nlp_dl_studio

# (href, title, what it does, keywords, kind)
DEST = [
    ("/nlp-dl", "Language and Deep Learning agents", "Classify text, find themes, sentiment, similar cases, anomalies, neural nets and forecasts on your data",
     "nlp text language sentiment classify tickets reviews notes themes topics keywords summarize similar neural deep learning anomaly unusual outlier fraud autoencoder forecast words messages emails comments feedback", "Agents"),
    ("/design", "Systems Design", "Describe a system and get components, tables, API calls, a diagram, capacity and monthly cost with the arithmetic, trade-offs, and a design review", "system design architecture diagram capacity cost servers scale load database tables api components trade-off review uptime backup design interview url shortener booking chat", "Agents"),
    ("/toolbox", "Data Toolbox", "Analyst, BI, data science and data engineering tools: question builder, pivot, A/B test, survey, notebook, client report designer, scheduled reports, alert rules, KPI dictionary, forecast studio, model card, drift check, customer segments, schema change detector, dedupe and merge, data contracts, volume estimator", "toolbox analyst analytics bi forecast pivot ab test survey notebook scheduled report alert kpi dictionary model card drift segmentation schema change dedupe merge contract estimator data engineering data science", "Data"),
    ("/toolbox?role=howto", "How to do or fix data problems", "Search guides for data problems: totals doubled after a join, duplicates, dates read wrong, model no better than guessing, leakage, column renamed, contract failed, slow loads", "how to fix data problem join explosion duplicates dates average of ratios leakage baseline drift schema renamed contract slow guide help", "Data"),
    ("/toolbox?role=cpe", "Computer engineering tools", "Parts list checker (pins, current, voltage mismatch), battery runtime estimator, sensor sketch writer, test plan, and a how-to/fix search", "computer engineering parts list pins current level shifter battery life runtime arduino esp32 raspberry pi sketch sensor test plan hardware", "Data"),
    ("/toolbox?role=ai", "AI engineering tools", "Eval runner for assistants, prompt library with versions, LLM cost estimator, AI risk register, handoff pack, and a how-to/fix search", "ai engineering evals test prompts regression cost tokens risk register hallucination prompt injection handoff assistant llm", "Data"),
    ("/toolbox?role=ml", "ML, NLP and deep learning tools", "Text classifier with honest accuracy report, labeling workbench, extraction tester, experiment tracker, and a how-to/fix search", "machine learning nlp text classifier labeling extraction regex experiment tracking overfitting deep learning tickets sort documents", "Data"),
    ("/toolbox?role=pm", "Project management tools", "Proposal and SOW writer, status report, three-point estimator, user-story writer, roadmap, decision and retro log, and a how-to/fix search", "project management sow proposal scope creep status report estimate user stories roadmap prioritize decision log retro late project", "Business"),
    ("/toolbox?role=fs", "Full stack tools", "Scaffold writer (table, API, form), API contract writer, code review report, deploy runbook, quote helper, and a how-to/fix search", "full stack scaffold api contract openapi code review deploy runbook hosting quote login sql injection bug web app", "Data"),
    ("/clients", "Clients and invoices", "Track clients, jobs, hours worked, invoices, who owes you, follow-ups, and build a handoff pack to give a paying client", "client clients customer freelance invoice invoices bill billing hours time tracking quote job jobs paid owe overdue follow up followup handoff pack deliver deliverable report", "Business"),
    ("/tracks/security?view=tools&tab=fix", "How to fix a security finding", "Search the fix guides: step-by-step fixes with a check that it worked, and the Cybersecurity agent to walk you through them", "fix how to fix security finding vulnerability hardening smb rdp firewall bitlocker 2fa mfa backup phishing clicked password certificate headers hacked breach remediate steps guide", "Security"),
    ("/tracks/security?view=tools&tab=report", "Security checkup report", "Combine PC audits, website checks, logs and a checklist into one client-ready report with a fix order", "security checkup report audit client assessment hardening review findings", "Security"),
    ("/intake", "Data Intake workflow", "Upload a file and the security, engineering, analyst, science, ML and BI agents process it in order with a supervisor", "upload intake file ingest workflow pipeline automatic process clean structure unstructured raw messy new data run everything orchestrator supervisor end to end", "Agents"),
    ("/studio", "Model Studio", "Pick a table and a column; it compares boosting, forests, SVM, neural nets and more, tunes, and tells you if it beats guessing", "model predict prediction train build compare boosting forest svm neural tune accuracy churn probability classification regression machine learning score batch cutoff threshold", "Lab"),
    ("/mlhand", "ML by hand", "Step through regression, KNN, trees, forests and error metrics, check them against a library", "machine learning by hand regression knn tree forest metrics worked example calculate teach", "Lab"),
    ("/ml", "ML Lab", "Train and compare predictive models on your operations data", "machine learning model train predict baseline experiment accuracy features", "Lab"),
    ("/packs", "Business dashboards", "Ready-made dashboards for repair jobs, sales, inventory and more, with import and Explain this number", "dashboard business pack sales inventory repair jobs invoices customers kpi explain import csv industry", "Dashboard"),
    ("/services", "Services and quotes", "Your service list, rates and a quote builder for BI, data science, computer and network engineering and repair", "service services price quote rate hourly clients customers offer sell freelance packages", "Business"),
    ("/tracks/itsupport", "IT repair guides and agent", "Search 78 repair guides for laptops, phones, printers, routers, mesh wifi, e-bikes, cameras and more", "repair fix broken laptop phone screen battery wifi mesh router printer cctv alarm ebike scooter dash cam car audio won't turn on slow virus", "Agent"),
    ("/tracks/network", "Network engineering", "Network design, troubleshooting and the network agent", "network wifi lan vlan subnet router switch firewall dns dhcp vpn ping latency ip", "Agent"),
    ("/tracks/pm?view=tools&tab=scenarios", "Project & product what-if scenarios", "Slip a task, lose capacity, add scope, simulate 1,000 schedules, re-rank features, and practice cases with hidden answers", "what if scenario simulate simulation slip delay deadline schedule critical path monte carlo risk capacity roadmap prioritize rice practice case project product plan", "Agents"),
    ("/tracks/analyst", "Business analyst", "KPIs, reports and the analyst agent", "analyst report kpi metric trend revenue profit margin insight analysis", "Agent"),
    ("/tracks/scientist", "Data scientist", "Statistics, modelling and the data-science agent", "data science statistics hypothesis regression experiment modelling scientist", "Agent"),
    ("/tracks/engineering", "Data engineering", "Pipelines, warehouses, backups and restore drills", "pipeline etl warehouse database backup restore engineer ingest schedule", "Agent"),
    ("/tracks/ml", "ML engineer agent", "The machine-learning agent that can run models and explain them", "machine learning agent mlops deploy model drift train", "Agent"),
    ("/tracks/security", "Security", "Security checks, logs and the security agent", "security password vulnerable threat phishing malware hardening audit", "Agent"),
    ("/tracks/cpe", "Computer engineering", "Hardware, circuits, embedded and computer-engineering agent", "computer engineering hardware circuit embedded cpu memory microcontroller", "Agent"),
    ("/lab", "SQL Lab", "Write and run SQL on your data", "sql query select join group database duckdb table", "Lab"),
    ("/python", "Python notebooks", "Practice pandas and python", "python pandas notebook script code", "Lab"),
    ("/analysis", "Analysis Lab", "Statistical analysis of your data", "analysis statistics correlation distribution outliers stats", "Lab"),
    ("/data", "My data", "Import, browse and explore your tables", "import upload csv excel file data table explore load", "Data"),
    ("/kpis", "KPIs", "Targets and red/amber/green status", "kpi target goal status red amber green", "Data"),
    ("/quality", "Data quality", "Checks for blanks, duplicates and bad values", "quality clean duplicates nulls validation errors missing", "Data"),
    ("/bi", "Dashboard", "Revenue, cost, profit and margin charts", "revenue cost profit margin chart sales overview", "Dashboard"),
    ("/company", "Company plan", "Engagement plan and deliverables", "company plan deliverable engagement consultant brief", "Business"),
    ("/settings", "Settings and backups", "Password, briefing, backups, laptop checklist", "settings password backup restore briefing email laptop travel security health", "Manage"),
    ("/activity", "Activity log and health check", "Audit trail, verify it, run the security health check", "audit log activity history verify health check tamper", "Manage"),
    ("/knowledge", "Knowledge search", "Search the manuals and docs", "docs manual help search guide how to", "Lab"),
    ("/glossary", "Glossary", "Definitions of metrics and terms", "glossary definition meaning term formula what is", "Lab"),
    ("/", "Home", "Overview of all your dashboards and what needs you", "home overview briefing today needs attention", "Page"),
]
STOP = set("a an the of to for my me i we you our your and or is are be do does can how what show find get give make want need please with on in at it this that these those from into about by all any some".split())
SYN = {"wi-fi": "wifi", "tickets": "text", "reviews": "text", "feedback": "text", "mood": "sentiment", "weird": "unusual", "suspicious": "unusual", "cost": "price", "money": "revenue", "fix": "repair", "broke": "broken", "slowdown": "slow"}

def _pack_dests() -> list[tuple]:
    from app.services import fieldpacks
    return [(x["href"], x["label"] + " tools", x["blurb"], x["keywords"] + " " + x["examples"], "Data") for x in fieldpacks.listing()]


DEST += [
    ("/tracks/itsupport?view=tools&tab=fixlog", "IT fix log", "Find what you did last time for a repair problem, write each fix down with steps and result, and print a client copy",
     "fix log history past fixed before again same problem repeat document write down steps taken knowledge base notes ticket resolution", "IT"),
    ("/tracks/security?view=tools&tab=fixlog", "Cybersecurity fix log", "Record each incident or finding fix with the steps taken, search past fixes, and print a write-up",
     "fix log incident history past fixed before again same problem document write down steps taken knowledge base security response remediation", "Security"),
]
DEST += _pack_dests()
DEST.append(("/fields", "More fields: health data, science, cloud and design", "Health data (clinical, analytics, BI, informatics), statistics, genomics, research, cloud, UI/UX and marketing tools", "fields health clinical genomic statistics research cloud ux marketing hl7 fhir kpi hospital nursing", "Data"))



def _toks(s: str) -> list[str]:
    out = []
    for t in re.findall(r"[a-z0-9'+-]+", (s or "").lower()):
        t = SYN.get(t, t)
        if t not in STOP and len(t) > 1:
            out.append(t)
    return out


def _stem(t: str) -> str:
    for suf in ("ing", "ies", "es", "s", "ed"):
        if t.endswith(suf) and len(t) - len(suf) >= 4:
            return t[: -len(suf)]
    return t


def _packs() -> list[dict]:
    try:
        from app.services import biz_packs
        return [{"id": p["id"], "title": p["title"], "industry": p["industry"], "dept": p.get("dept", ""), "words": " ".join([p["title"], p["industry"], p.get("dept", ""), p.get("about", ""), " ".join(p["dims"]), " ".join(p["nums"])]).lower().replace("_", " ")} for p in biz_packs.all_packs()]
    except Exception:  # noqa: BLE001
        return []


def route(text: str, limit: int = 5) -> dict:
    q = (text or "").strip()
    if not q:
        return {"query": "", "results": [], "primary": None, "tip": "Type what you need, e.g. 'sort my tickets by category', 'why did repair profit drop', 'quote a network install'."}
    toks = [_stem(t) for t in _toks(q)]
    res = []
    for href, title, what, keys, kind in DEST:
        kw = {_stem(k) for k in keys.split()} | {_stem(t) for t in _toks(title)}
        hit = [t for t in toks if t in kw or any(t == k[:len(t)] and len(t) >= 4 for k in kw)]
        if not hit:
            continue
        score = len(set(hit)) * 3 + (2 if any(_stem(t) in {_stem(x) for x in _toks(title)} for t in hit) else 0)
        res.append({"href": href, "title": title, "what": what, "kind": kind, "score": score, "why": "matches " + ", ".join(sorted(set(hit))[:4])})
    for p in _packs():
        w = {_stem(x) for x in _toks(p["words"])}
        hit = [t for t in toks if t in w]
        if len(set(hit)) >= 1 and any(t in {_stem(x) for x in _toks(p["title"] + " " + p["industry"])} for t in hit):
            res.append({"href": f"/packs?pid={quote(p['id'])}", "title": p["title"], "what": f"{p['industry']} dashboard ({p['dept']})", "kind": "Dashboard", "score": len(set(hit)) * 4 + 2, "why": "your dashboard matches " + ", ".join(sorted(set(hit))[:4])})
    # the language / deep-learning agents get the actual sentence so they can start working right away
    nd = nlp_dl_studio
    w = set(re.findall(r"[a-z0-9']+", q.lower()))
    if w & (nd.DL_WORDS | nd.TEXT_HINT | {"classify", "categorize", "categorise", "similar", "themes", "topics", "unusual", "anomaly", "forecast"}):
        for r in res:
            if r["href"] == "/nlp-dl":
                r["score"] += 4
                r["href"] = "/nlp-dl?ask=" + quote(q[:300])
                r["why"] += "; the agents start as soon as you open it"
    res.sort(key=lambda r: -r["score"])
    res = res[:limit]
    return {"query": q, "results": res, "primary": res[0] if res else None,
            "tip": None if res else "Nothing matched. Try other words, or ask an agent: " + "/tracks/analyst?view=agent"}
