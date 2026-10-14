"""Technical field packs: DevOps, cloud architecture, DevSecOps, computer vision."""
from __future__ import annotations

import json
import re

from app.services import field_howto as fh
from app.services.fieldpacks import I, PackError, md, num, pack, rows, split, tool, txt

DEVOPS, CLOUD, DSO, CV = "DevOps", "Cloud architecture", "DevSecOps", "Computer vision"
fh.AREAS.extend([DEVOPS, CLOUD, DSO, CV])
g = fh._g

pack("devops", DEVOPS, "Full stack", "CI pipeline and Dockerfile writers, delivery metrics (DORA) and uptime budgets.", "fullstack", "e.g. deploys are scary, builds are slow", "devops ci cd pipeline docker github actions dora deploy frequency lead time mttr slo uptime error budget")
pack("cloud", CLOUD, "Cloud and design", "Cost estimate, availability maths and a disaster-recovery pattern picker, with step-by-step how-to guides.", "sysanalyst", "e.g. cloud bill too high, plan for outages", "cloud architect aws azure gcp cost estimate availability sla disaster recovery rto rpo migration landing zone")
pack("devsecops", DSO, "Cybersecurity", "Defensive checks on code and pipelines: secrets, CI workflow risks, unpinned dependencies, Dockerfile problems.", "security", "e.g. key committed by mistake, secure my pipeline", "devsecops secrets scan pipeline security github actions dependencies pinning docker lint supply chain shift left")
pack("cv", CV, "ML, NLP and deep learning", "Label-file audit, box-overlap (IoU) scorer and detection scorer for image projects.", "ml", "e.g. detector misses small objects, labels messy", "computer vision image detection yolo labels annotation iou precision recall bounding box dataset")

# ------------------------------------------------------------------ guides: DevOps
g("do-scary", DEVOPS, "Deploys are scary and rare", "deploy frequency scary release small batches rollback automation fear blue green canary", "Big, rare releases hold many changes, so each one is risky.", ["Ship smaller changes more often: even daily.", "Automate build, test and deploy so every release follows the same steps.", "Write and rehearse the rollback.", "Use a staging copy that matches production.", "Add a feature flag so unfinished work can ship switched off."], "A release can be reversed within minutes and nobody dreads it.", 120, "", "CI pipeline writer")
g("do-slowbuild", DEVOPS, "Builds and tests take too long", "slow build ci cache parallel tests speed pipeline minutes waiting", "Slow feedback means people batch changes and skip checks.", ["Time each step and find the slowest.", "Cache dependencies between runs.", "Run independent jobs in parallel.", "Run the quick tests first and fail early.", "Move rare, slow tests to a nightly run."], "The main pipeline gives feedback in under about 10 minutes.", 60, "", "CI pipeline writer")
g("do-flaky", DEVOPS, "Tests fail randomly (flaky)", "flaky tests intermittent random failure retry timing order dependent shared state", "A test that sometimes fails teaches people to ignore failures.", ["Note which tests fail and how often.", "Run the test alone and in a loop to reproduce.", "Look for timing, shared data, order dependence and network calls.", "Fix or delete: do not just retry.", "Quarantine it in a separate job until fixed."], "The suite passes 20 runs in a row.", 90)
g("do-docker", DEVOPS, "Writing a good Dockerfile", "dockerfile docker image small non root layers cache multi stage best practice", "A careless image is large, slow to build and less safe.", ["Start from a small, specific base image version.", "Copy the dependency file first and install, then copy the code, so the cache works.", "Run as a non-root user.", "Use a .dockerignore.", "Check it with the Dockerfile checker."], "The Dockerfile checker has no high findings and the image runs as a non-root user.", 40, "", "Dockerfile writer")
g("do-dora", DEVOPS, "Measuring how well delivery works", "dora metrics deployment frequency lead time change failure rate mttr performance measure", "Four numbers show speed and stability together.", ["Count deploys per week.", "Measure the median time from commit to running in production.", "Count the share of deploys that needed a fix or rollback.", "Measure median time to restore service after a failure.", "Improve the worst one first and track monthly."], "You have all four numbers and a note of the trend.", 45, "", "Delivery metrics (DORA)")
g("do-slo", DEVOPS, "How reliable does it need to be?", "slo sla uptime error budget availability downtime nines reliability target", "Higher reliability costs much more; pick the level the business needs.", ["Choose a target such as 99.9%.", "Convert it to allowed downtime per month with the uptime tool.", "Count real downtime against it.", "When the budget is used up, slow feature work and fix reliability."], "Everyone knows the target and how much budget is left.", 30, "", "Uptime budget")
g("do-alert", DEVOPS, "Alerts that nobody trusts", "alerts monitoring noise pager fatigue on call thresholds actionable runbook", "Noisy alerts get ignored, including the real ones.", ["List the alerts from the last month and mark which needed action.", "Delete or downgrade alerts that never did.", "Alert on user-visible symptoms (errors, slowness) not every cause.", "Link each alert to a short runbook."], "Most alerts that fire need a person to do something.", 60)

# ------------------------------------------------------------------ guides: cloud
g("cl-start", CLOUD, "Where do I start designing a cloud setup?", "cloud architecture start design requirements landing zone account structure basics well architected", "Start with needs, not services.", ["Write down what the system must do, how many users, and what an outage costs.", "Choose one provider and one region close to your users.", "Separate accounts or projects for production and everything else.", "Turn on billing alerts and MFA for the root login first.", "Draw the design on one page before creating anything."], "A one-page diagram and a short requirements list exist and the owner agrees.", 90, "", "Availability calculator")
g("cl-bill", CLOUD, "The cloud bill is higher than expected", "cloud cost bill expensive reduce savings idle rightsizing egress budget finops", "Most waste is idle resources, oversized machines and data leaving the cloud.", ["Set a budget alert.", "List running resources and who owns each.", "Delete idle or unused ones and shut dev systems off at night.", "Right-size machines to real usage.", "Check data transfer out and storage tiers.", "Estimate again with the cost tool."], "Next month's bill is within the budget alert.", 60, "", "Cloud cost estimator")
g("cl-dr", CLOUD, "What if the region or system goes down?", "disaster recovery rto rpo backup restore failover multi region outage plan pilot light warm standby", "Recovery time and data loss limits decide the design and cost.", ["Ask the owner: how long can it be down (RTO) and how much data can be lost (RPO)?", "Use the disaster recovery picker for the cheapest pattern that meets both.", "Back up outside the primary account or region.", "Rehearse a restore and time it.", "Write the steps down."], "A restore has been done within the RTO using only the written steps.", 120, "", "Disaster recovery picker")
g("cl-avail", CLOUD, "How many nines can this design reach?", "availability sla nines redundancy series parallel single point of failure composite uptime", "Chained parts multiply their downtime; redundant parts share it.", ["List each component and its availability.", "Group redundant copies together.", "Compute the total.", "Find the weakest single point of failure and add redundancy there."], "You know the achievable availability and its weakest link.", 30, "", "Availability calculator")
g("cl-migrate", CLOUD, "Moving an existing system to the cloud", "cloud migration lift and shift rehost replatform refactor retire repurchase six rs plan", "Not every system should move, and not the same way.", ["List the systems and who uses them.", "Use the migration helper to propose retire, retain, repurchase, replatform or rehost for each.", "Move a small, low-risk system first as a rehearsal.", "Plan data transfer and a cutover with rollback.", "Run both side by side briefly."], "The first migrated system runs in the cloud and the old one can be switched off.", 240, "", "Migration helper")
g("cl-sec", CLOUD, "Securing a cloud account", "cloud security account iam least privilege mfa logging public bucket keys root", "Most cloud breaches come from open storage and over-powerful keys.", ["Protect the root login with MFA and do not use it day to day.", "Give people and apps only the permissions they need.", "Block public storage by default.", "Turn on audit logging and keep the logs.", "Rotate keys and remove unused ones."], "No public buckets, no unused keys, logging on.", 90)
g("cl-iac", CLOUD, "Clicking in the console does not scale", "infrastructure as code terraform cloudformation repeatable environments drift version control", "Click-built setups cannot be repeated or reviewed.", ["Pick one tool (Terraform is common).", "Describe one small piece first.", "Keep the code in version control and review changes.", "Apply from a pipeline, not a laptop.", "Detect drift regularly."], "A new copy of the environment can be built from code.", 180)

# ------------------------------------------------------------------ guides: DevSecOps
g("dso-secret", DSO, "A password or key was committed to the code", "secret leaked committed key password token git history rotate revoke exposed credential", "Once pushed, assume it is public. Removing it from the files is not enough.", ["Revoke or rotate the secret right now at the provider.", "Check the provider's logs for use you did not make.", "Remove it from the code and load it from a secrets store.", "Clean the git history if the repository is shared, but still treat the secret as burned.", "Add a secrets scan to pre-commit and CI."], "The old secret no longer works, and the scan finds nothing.", 45, "Rotate first, clean later. Never paste real secrets into chat tools.", "Secrets scanner")
g("dso-pipeline", DSO, "Securing the build pipeline", "ci pipeline security github actions permissions pinned actions pull request injection supply chain workflow", "Your pipeline can deploy to production, so it is an attack target.", ["Set the pipeline's default permissions to read only.", "Pin third-party actions to a full commit.", "Never put untrusted text (titles, branch names) into shell commands.", "Do not run untrusted pull-request code with secrets.", "Run the pipeline checker on each workflow."], "The pipeline checker shows no high findings.", 45, "", "Pipeline checker")
g("dso-deps", DSO, "Dependencies that can change under you", "dependencies pinning lockfile version supply chain vulnerabilities updates audit sbom", "Unpinned versions mean builds change without a code change.", ["Use a lockfile and commit it.", "Pin versions in requirements or package files.", "Run the ecosystem's audit command in CI.", "Update on a schedule in small batches.", "Remove dependencies you do not use."], "Builds are repeatable and the audit command reports no known high issues.", 40, "", "Dependency checker")
g("dso-docker", DSO, "Container images with avoidable risk", "container image docker security root latest tag secrets scan base image minimal", "Images inherit risks from the base and from how you build.", ["Use a small, versioned base image.", "Run as non-root.", "Never copy secrets into an image.", "Scan images in CI.", "Rebuild regularly to pick up patches."], "The Dockerfile checker is clean and the scan finds no critical issues.", 40, "", "Dockerfile checker")
g("dso-shift", DSO, "Adding security without slowing everyone down", "shift left security gates pre commit sast review threat model developers friction", "Cheap checks early beat expensive findings late.", ["Start with three checks: secrets, dependencies, and a basic static scan.", "Make them fast and run them on every pull request.", "Fail the build only on high findings at first.", "Fix the top recurring problem with a shared template.", "Review the gates quarterly."], "Developers see security results on the pull request, and few are ignored.", 90, "", "Security gates checklist")
g("dso-incident", DSO, "Responding when a deployment looks compromised", "incident response compromised pipeline rollback revoke tokens logs forensics contain", "Contain first, investigate second.", ["Stop deployments and revoke pipeline tokens.", "Roll back to the last known-good build.", "Preserve logs.", "Check recent changes and who made them.", "Rotate all secrets the pipeline could reach.", "Write what happened and the fix."], "Deployments resume only from a verified clean state.", 120)

# ------------------------------------------------------------------ guides: computer vision
g("cv-small", CV, "The detector misses small objects", "small objects missed detection resolution image size tiles anchors recall", "Small objects can vanish when images are shrunk.", ["Check how many pixels the smallest object has after resizing.", "Train and run at a higher resolution, or split images into tiles.", "Add more examples of small objects.", "Check labels: are small objects labeled consistently?", "Measure recall by object size."], "Recall for small objects improves on a held-out set.", 120, "", "Detection scorer")
g("cv-labels", CV, "Labels are messy or inconsistent", "labels annotation quality boxes inconsistent audit classes yolo errors review", "A model cannot be better than its labels.", ["Run the label audit to find tiny, huge, duplicate and out-of-range boxes.", "Write labeling rules with example pictures.", "Review a random 5% by a second person.", "Fix systematic mistakes before adding more data."], "The audit shows no out-of-range or duplicate boxes, and two reviewers agree on a sample.", 90, "", "Label audit")
g("cv-eval", CV, "How good is the detector really?", "evaluation precision recall iou threshold false positives metrics held out test set map", "A score only means something on images the model never saw.", ["Keep a test set separate from training.", "Choose an IoU threshold (0.5 is common).", "Use the detection scorer for precision, recall and F1.", "Look at failures by hand.", "Test on images like real use (lighting, angles)."], "Metrics come from a held-out set that matches real use.", 60, "", "Detection scorer")
g("cv-data", CV, "How many images do I need?", "dataset size images needed augmentation transfer learning pretrained start small", "Start from a pretrained model; you often need hundreds, not millions.", ["Begin with a pretrained model.", "Collect 100 to 200 varied images per class to start.", "Label carefully and train.", "Look at errors and collect images like the failures.", "Use augmentation (flips, brightness) for variety."], "Adding data of the failure type improves the score.", 120)
g("cv-privacy", CV, "Cameras, faces and privacy", "privacy faces people cameras consent retention blur biometric law surveillance", "Images of people carry legal and ethical duties.", ["Avoid collecting faces unless you must.", "Tell people and get consent where required.", "Blur or discard what you do not need.", "Set a retention period.", "Check local laws on biometrics."], "You can say what is captured, why and how long it is kept.", 45, "General information, not legal advice.")
g("cv-deploy", CV, "Running the model on a small device", "edge deployment raspberry pi jetson speed latency quantize model size fps camera", "Small devices need small, fast models.", ["Pick the smallest model that meets accuracy.", "Measure frames per second on the device itself.", "Reduce input size or quantize.", "Skip frames when speed matters.", "Log failures for retraining."], "Speed and accuracy both meet the target on the real device.", 120)


# ------------------------------------------------------------------ helpers shared by Dockerfile tools
def docker_findings(text: str) -> list[dict]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    f = []
    froms = [ln for ln in lines if ln.upper().startswith("FROM ")]
    if not froms:
        raise PackError("No FROM line found. Paste the whole Dockerfile.")
    for ln in froms:
        img = ln.split()[1] if len(ln.split()) > 1 else ""
        if img.lower() != "scratch" and (":" not in img or img.endswith(":latest")) and "@sha256" not in img:
            f.append({"severity": "medium", "says": f"'{img}' is not pinned to a version. Builds will change without a code change; use a specific tag."})
    if not any(ln.upper().startswith("USER ") and not re.match(r"USER\s+(root|0)\b", ln, re.I) for ln in lines):
        f.append({"severity": "high", "says": "No non-root USER. The container runs as root; add a user and switch to it."})
    for ln in lines:
        u = ln.upper()
        if re.search(r"(PASSWORD|SECRET|TOKEN|API_KEY|APIKEY)\s*=\s*\S+", ln, re.I) and (u.startswith("ENV ") or u.startswith("ARG ")):
            f.append({"severity": "high", "says": f"A secret looks baked in: '{ln.split('=')[0][:40]}'. Secrets in ENV or ARG stay in the image history; pass them at run time."})
        if re.search(r"curl[^|]*\|\s*(sudo\s+)?(ba)?sh|wget[^|]*\|\s*(ba)?sh", ln, re.I):
            f.append({"severity": "high", "says": "Pipes a download straight into a shell. Download, check a checksum, then run."})
        if u.startswith("ADD ") and not re.search(r"\.(tar|tgz|gz|xz)\b", ln, re.I):
            f.append({"severity": "low", "says": "ADD does more than copy (it fetches URLs and unpacks archives). Use COPY unless you need that."})
        if "apt-get install" in ln and "--no-install-recommends" not in ln:
            f.append({"severity": "low", "says": "apt-get install without --no-install-recommends makes the image larger."})
        if "apt-get install" in ln and "rm -rf /var/lib/apt/lists" not in " ".join(lines):
            f.append({"severity": "low", "says": "Clean the apt cache (rm -rf /var/lib/apt/lists/*) in the same layer to keep the image small."})
        if re.match(r"(COPY|ADD)\s+\.\s", ln, re.I) and not any("requirements" in x or "package" in x for x in lines[:lines.index(ln)]):
            f.append({"severity": "low", "says": "Copies the whole folder before installing dependencies, so every code change reinstalls everything. Copy the dependency file first."})
    if not any(ln.upper().startswith("HEALTHCHECK") for ln in lines):
        f.append({"severity": "low", "says": "No HEALTHCHECK. Add one if your platform can use it."})
    seen, out = set(), []
    for x in f:
        if x["says"] not in seen:
            seen.add(x["says"])
            out.append(x)
    return sorted(out, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]])


def _docker_tool(pid):
    @tool(pid, "dockercheck", "Dockerfile checker", "Finds common image problems. Text only: nothing is built or run.", [I("text", "Paste the Dockerfile", "area")])
    def dockercheck(v):
        t = txt(v, "text", 20000, True)
        f = docker_findings(t)
        return {"says": f"{sum(x['severity'] == 'high' for x in f)} high and {len(f)} total finding(s)." if f else "No common problems found.", "findings": f, "caution": "A pattern check, not a full scan. Also scan the built image in CI."}


# ------------------------------------------------------------------ tools: DevOps
@tool("devops", "dora", "Delivery metrics (DORA)", "Compares your four delivery numbers with the bands in published DORA research.",
      [I("deploys", "Deploys per week", "number"), I("lead", "Median hours from commit to production", "number"), I("cfr", "Deploys needing a fix or rollback (%)", "number"), I("mttr", "Median hours to restore after a failure", "number")])
def dora(v):
    d, lead, cfr, mttr = num(v, "deploys", 0), num(v, "lead", 0), num(v, "cfr", 0, 100), num(v, "mttr", 0)

    def band(val, cuts, high_is_good=False):
        for lvl, c in zip(("elite", "high", "medium"), cuts):
            if (val >= c) if high_is_good else (val <= c):
                return lvl
        return "low"
    res = {"deploy_frequency": band(d, (7, 1, 0.25), True), "lead_time": band(lead, (24, 168, 720)), "change_failure_rate": band(cfr, (15, 30, 45)), "time_to_restore": band(mttr, (1, 24, 168))}
    order = ["low", "medium", "high", "elite"]
    weakest = min(res, key=lambda k: order.index(res[k]))
    return {"says": f"Weakest area: {weakest.replace('_', ' ')} ({res[weakest]}).", "bands": res, "notes": ["Bands are approximate and drawn from published DORA reports, which change year to year. Use them for direction, not scoring.", "Track the trend over months. Improving your own numbers matters more than a label."]}


@tool("devops", "cicd", "CI pipeline writer", "Writes a GitHub Actions workflow as text for you to paste. Nothing is run or uploaded.",
      [I("lang", "Language", "select", "python", [{"id": "python", "label": "Python"}, {"id": "node", "label": "Node"}]), I("test", "Test command", "text", ""), I("branch", "Main branch", "text", "main")])
def cicd(v):
    lang, br = txt(v, "lang", 10), txt(v, "branch", 40) or "main"
    if lang not in ("python", "node"):
        raise PackError("Language must be Python or Node.")
    if not re.fullmatch(r"[A-Za-z0-9._/\-]{1,40}", br):
        raise PackError("Branch names may only use letters, numbers and . _ / -")
    cmd = txt(v, "test", 120) or ("pytest -q" if lang == "python" else "npm test")
    if re.search(r"[;&|`$<>]", cmd):
        raise PackError("Keep the test command simple: one command without ; & | or $.")
    setup = ("      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n          cache: pip\n      - run: pip install -r requirements.txt\n" if lang == "python" else "      - uses: actions/setup-node@v4\n        with:\n          node-version: 22\n          cache: npm\n      - run: npm ci\n")
    yml = f"name: ci\non:\n  push:\n    branches: [{br}]\n  pull_request:\npermissions:\n  contents: read\njobs:\n  test:\n    runs-on: ubuntu-latest\n    timeout-minutes: 15\n    steps:\n      - uses: actions/checkout@v4\n{setup}      - run: {cmd}\n"
    return {"says": "Workflow ready: save as .github/workflows/ci.yml.", "code": yml, "notes": ["Permissions are read-only by default; widen them per job only when needed.", "For stricter supply-chain safety, pin each action to a full commit instead of a version tag.", "Check the action versions are still current before using this."]}


@tool("devops", "dockerfile", "Dockerfile writer", "Writes a Dockerfile as text with a non-root user and good layer order.", [I("lang", "Language", "select", "python", [{"id": "python", "label": "Python"}, {"id": "node", "label": "Node"}]), I("port", "Port the app listens on", "number", "8000"), I("start", "Start command (words only)", "text", "")])
def dockerfile(v):
    lang, port = txt(v, "lang", 10), int(num(v, "port", 1, 65535))
    if lang not in ("python", "node"):
        raise PackError("Language must be Python or Node.")
    start = txt(v, "start", 120) or ("uvicorn app.main:app --host 0.0.0.0 --port " + str(port) if lang == "python" else "node server.js")
    if re.search(r"[;&|`$<>\"\\]", start):
        raise PackError("Keep the start command simple: words only, no quotes, ; & | or $.")
    cmd = json.dumps(start.split())
    if lang == "python":
        d = f"FROM python:3.12-slim\nWORKDIR /app\nCOPY requirements.txt .\nRUN pip install --no-cache-dir -r requirements.txt\nCOPY . .\nRUN useradd --create-home app\nUSER app\nEXPOSE {port}\nCMD {cmd}\n"
    else:
        d = f"FROM node:22-slim\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci --omit=dev\nCOPY . .\nUSER node\nEXPOSE {port}\nCMD {cmd}\n"
    return {"says": "Dockerfile ready.", "code": d, "notes": ["Add a .dockerignore with .git, node_modules, .env and test data.", "Pin the base image to the exact version you test with.", "Run the Dockerfile checker on any change."]}


_docker_tool("devops")


@tool("devops", "slo", "Uptime budget", "Turns an availability target into allowed downtime and shows how much you have used.", [I("target", "Availability target (%)", "number", "99.9"), I("days", "Window (days)", "number", "30"), I("down", "Downtime so far in the window (minutes)", "number", "0")])
def slo(v):
    t, days, down = num(v, "target", 50, 99.99999), num(v, "days", 1, 366), num(v, "down", 0)
    allowed = days * 1440 * (1 - t / 100)
    used = down / allowed if allowed else 0
    return {"says": f"A {t:g}% target allows {allowed:.0f} minutes of downtime in {days:g} days. You have used {used:.0%}.", "allowed_downtime_minutes": round(allowed, 1), "used_pct": round(100 * used, 1), "minutes_left": round(max(allowed - down, 0), 1), "status": "over budget" if used > 1 else "watch" if used > 0.7 else "healthy",
            "notes": ["When the budget is spent, pause risky changes and fix reliability.", "Count downtime the way users feel it (errors and slowness), not only server uptime."]}


# ------------------------------------------------------------------ tools: cloud
@tool("cloud", "cost", "Cloud cost estimator", "A monthly estimate from the amounts you expect. Prices are examples you should replace with your provider's current prices.",
      [I("vms", "Number of servers", "number", "2"), I("vm_hour", "Price per server hour ($)", "number", "0.05"), I("hours", "Hours per month each runs", "number", "730"), I("storage", "Storage (GB)", "number", "200"), I("storage_gb", "Price per GB-month ($)", "number", "0.10"), I("egress", "Data out (GB per month)", "number", "100"), I("egress_gb", "Price per GB out ($)", "number", "0.09"), I("other", "Other monthly costs ($)", "number", "0"), I("discount", "Commitment discount (%)", "number", "0")])
def cost(v):
    vms, vh, hrs, st, sp, eg, ep, ot, dc = (num(v, k, 0) for k in ("vms", "vm_hour", "hours", "storage", "storage_gb", "egress", "egress_gb", "other", "discount"))
    if hrs > 744 or dc > 90:
        raise PackError("Hours per month cannot exceed 744 and the discount cannot exceed 90%.")
    parts = {"servers": vms * vh * hrs, "storage": st * sp, "data_out": eg * ep, "other": ot}
    sub = sum(parts.values())
    total = sub * (1 - dc / 100)
    return {"says": f"About ${total:,.0f} per month (${total * 12:,.0f} per year) with these inputs.", "monthly_before_discount": round(sub, 2), "monthly_total": round(total, 2), "yearly_total": round(total * 12, 2), "breakdown": [{"item": k, "monthly": round(x, 2), "share_pct": round(100 * x / sub, 1) if sub else 0} for k, x in parts.items()],
            "notes": ["Your own prices are used: there is no live price lookup. Check the provider's calculator before quoting a client.", "Often forgotten: backups, load balancers, logging, support plans, IP addresses and data transfer between zones.", "Leave a 20% margin for growth."]}


@tool("cloud", "avail", "Availability calculator", "Combines component availability: chained parts multiply, redundant copies share.", [I("parts", "Parts: name, availability %, group (copies with the same group are redundant) (one per line)", "area", "Load balancer, 99.99, lb\nApp server 1, 99.5, app\nApp server 2, 99.5, app\nDatabase, 99.9, db")])
def avail(v):
    groups: dict[str, list[tuple[str, float]]] = {}
    for i, ln in enumerate(rows(v, "parts", 60), 1):
        c = split(ln)
        if len(c) < 2:
            raise PackError(f"'{ln[:30]}' needs a name and an availability.")
        try:
            a = float(c[1].rstrip("%"))
        except ValueError:
            raise PackError(f"Availability for {c[0]} must be a number.") from None
        if not 0 < a <= 100:
            raise PackError(f"Availability for {c[0]} must be above 0 and at most 100.")
        groups.setdefault(c[2] if len(c) > 2 and c[2] else f"part{i}", []).append((c[0], a / 100))
    if not groups:
        raise PackError("Add at least one part.")
    res, total = [], 1.0
    for k, mem in groups.items():
        down = 1.0
        for _, a in mem:
            down *= 1 - a
        ga = 1 - down
        total *= ga
        res.append({"group": k, "parts": len(mem), "group_availability_pct": round(100 * ga, 4)})
    weakest = min(res, key=lambda r: r["group_availability_pct"])
    mins = (1 - total) * 525600
    return {"says": f"Overall availability {100 * total:.3f}%, about {mins / 60:.1f} hours of downtime a year. Weakest link: {weakest['group']}.", "groups": res, "overall_pct": round(100 * total, 4), "downtime_hours_per_year": round(mins / 60, 2),
            "notes": ["Assumes parts fail independently, which is optimistic: shared power, network or a bad deploy can take out copies together.", "Do not forget the pieces outside the diagram: DNS, certificates, the provider's own service level."]}


PATTERNS = [("Backup and restore", 24, 24, "lowest", "Back up data and rebuild after a failure."), ("Pilot light", 4, 1, "low", "Keep data copied and a minimal core running; scale up on failure."),
            ("Warm standby", 1, 0.25, "medium", "A scaled-down full copy always running."), ("Active-active across regions", 0.1, 0.01, "highest", "Full copies serve traffic at all times.")]


@tool("cloud", "dr", "Disaster recovery picker", "Picks the cheapest recovery pattern that meets your recovery time and data-loss limits.", [I("rto", "Longest acceptable downtime (hours)", "number", "4"), I("rpo", "Most data you can lose (hours of work)", "number", "1")])
def dr(v):
    rto, rpo = num(v, "rto", 0.01), num(v, "rpo", 0)
    ok = [p for p in PATTERNS if p[1] <= rto and p[2] <= rpo]
    table = [{"pattern": n, "typical_recovery_hours": a, "typical_data_loss_hours": b, "relative_cost": c, "meets_your_limits": (a <= rto and b <= rpo), "idea": d} for n, a, b, c, d in PATTERNS]
    if not ok:
        return {"says": "Your limits are tighter than the patterns listed: expect specialist design and the highest cost.", "patterns": table, "notes": ["Check whether the limits are really needed; each step tighter costs much more."]}
    return {"says": f"Cheapest pattern that fits: {ok[0][0]}.", "patterns": table, "notes": ["Times are rough typical figures, not guarantees. Rehearse a restore and time it.", "Keep backups in a different account or region from the live system.", "Also decide who declares a disaster and who talks to customers."]}


@tool("cloud", "migrate", "Migration helper", "Suggests retire, retain, repurchase, replatform or rehost for each system.", [I("apps", "Systems: name, in use? (yes/no), software-as-a-service alternative exists? (yes/no), can change code? (yes/no), blocker for cloud? (yes/no) (one per line)", "area", "Old intranet, no, no, no, no\nAccounting, yes, yes, no, no\nOrder app, yes, no, yes, no\nLab controller, yes, no, no, yes\nFile server, yes, no, no, no")])
def migrate(v):
    out = []
    yn = lambda s: s.strip().lower() in ("yes", "y", "true")  # noqa: E731
    for ln in rows(v, "apps", 80):
        c = split(ln) + [""] * 5
        n, use, saas, chg, blk = c[:5]
        if not n:
            continue
        if not yn(use):
            r, why = "Retire", "Not in use: switch it off instead of moving it."
        elif yn(blk):
            r, why = "Retain", "Something blocks the cloud (hardware, licence, latency). Leave it where it is for now."
        elif yn(saas):
            r, why = "Repurchase", "A hosted service already does this: move the data and stop running your own."
        elif yn(chg):
            r, why = "Replatform", "Small code changes let it use managed services (database, storage)."
        else:
            r, why = "Rehost", "Move it as it is (lift and shift), then improve later."
        out.append({"system": n, "suggestion": r, "why": why})
    if not out:
        raise PackError("Add at least one system.")
    return {"says": f"{len(out)} systems reviewed.", "plan": out, "notes": ["Start with the lowest-risk system as a rehearsal.", "These are rule-of-thumb suggestions. Check dependencies between systems before moving any of them."]}


# ------------------------------------------------------------------ tools: DevSecOps
SECRET_PATTERNS = [("AWS access key id", r"\bAKIA[0-9A-Z]{16}\b", "high"), ("Private key block", r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY", "high"), ("GitHub token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b", "high"), ("Slack token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}", "high"),
                   ("Stripe live key", r"\b[sr]k_live_[A-Za-z0-9]{16,}", "high"), ("Google API key", r"\bAIza[0-9A-Za-z_\-]{35}\b", "high"), ("JSON web token", r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}", "medium"),
                   ("Password or secret assigned in text", r"(?i)\b(?:password|passwd|secret|api[_-]?key|token)\b\s*[:=]\s*['\"][^'\"\s]{8,}['\"]", "medium")]


def _mask(s: str) -> str:
    return (s[:4] + "…" + f"({len(s)} characters)") if len(s) > 8 else "…"


@tool("devsecops", "secrets", "Secrets scanner", "Looks for keys and passwords in pasted text and shows them masked. Nothing is stored or sent.", [I("text", "Paste code or config (do not paste anything you cannot afford to expose)", "area")])
def secrets(v):
    t = txt(v, "text", 200000, True)
    f = []
    for ln_no, ln in enumerate(t.splitlines(), 1):
        for name, pat, sev in SECRET_PATTERNS:
            for m in re.finditer(pat, ln):
                f.append({"severity": sev, "line": ln_no, "says": f"{name} on line {ln_no}: {_mask(m.group(0))}. Revoke or rotate it, then load it from a secrets store."})
    return {"says": f"{len(f)} possible secret(s) found." if f else "No known secret patterns found.", "findings": f[:100], "caution": "Pattern matching only: it misses secrets that do not look like these and can flag harmless text. A clean result is not proof. If a real secret was ever exposed, rotate it."}


@tool("devsecops", "pipeline", "Pipeline checker", "Checks a GitHub Actions workflow for common security mistakes. Text only.", [I("text", "Paste the workflow YAML", "area")])
def pipeline(v):
    t = txt(v, "text", 60000, True)
    f = []
    if not re.search(r"^\s*permissions\s*:", t, re.M):
        f.append({"severity": "medium", "says": "No 'permissions:' block, so the token may have broad default rights. Add 'permissions: contents: read' and widen per job."})
    if re.search(r"pull_request_target", t):
        f.append({"severity": "high", "says": "Uses pull_request_target, which runs with secrets. Never check out or run code from the pull request in this mode."})
    for m in re.finditer(r"uses:\s*([^\s@]+)@([^\s#]+)", t):
        name, ref = m.group(1), m.group(2)
        if name.startswith("./"):
            continue
        if not re.fullmatch(r"[0-9a-f]{40}", ref):
            third = not name.startswith(("actions/", "github/"))
            f.append({"severity": "medium" if third else "low", "says": f"{name}@{ref} is not pinned to a full commit. {'Third-party actions can change under you: pin to a commit.' if third else 'Tags can move; pin for the strictest setups.'}"})
    if re.search(r"\$\{\{\s*github\.(event\.(issue|pull_request|comment|review|head_commit|commits)[^}]*|head_ref)\s*\}\}", t) and re.search(r"run:", t):
        f.append({"severity": "high", "says": "Puts attacker-controlled text (titles, bodies, branch names) into an expression that may reach a shell. Pass it through an environment variable instead."})
    if re.search(r"curl[^\n|]*\|\s*(sudo\s+)?(ba)?sh", t):
        f.append({"severity": "high", "says": "Pipes a download straight into a shell."})
    if re.search(r"echo\s+[^\n]*\$\{\{\s*secrets\.", t):
        f.append({"severity": "high", "says": "Echoes a secret into the log."})
    if re.search(r"secrets:\s*inherit", t):
        f.append({"severity": "low", "says": "'secrets: inherit' passes every secret to the called workflow. Pass only what is needed."})
    if "continue-on-error: true" in t:
        f.append({"severity": "low", "says": "continue-on-error hides failures. Make sure a failing security step still blocks."})
    f.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]])
    return {"says": f"{sum(x['severity'] == 'high' for x in f)} high and {len(f)} total finding(s)." if f else "No common problems found.", "findings": f, "caution": "A pattern check on one file. It cannot see repository settings such as branch protection or who can approve workflows."}


@tool("devsecops", "deps", "Dependency checker", "Flags dependencies that are not pinned. Handles requirements.txt and package.json text.", [I("text", "Paste requirements.txt or package.json", "area")])
def deps(v):
    t = txt(v, "text", 100000, True)
    out = []
    if t.lstrip().startswith("{"):
        try:
            d = json.loads(t)
        except json.JSONDecodeError:
            raise PackError("That looks like JSON but is not valid.") from None
        for sect in ("dependencies", "devDependencies"):
            for n, ver in (d.get(sect) or {}).items():
                ver = str(ver)
                lvl = "exact" if re.fullmatch(r"\d+\.\d+\.\d+", ver) else "loose" if ver[:1] in "^~" else "unpinned"
                out.append({"package": n, "version": ver, "pinning": lvl})
    else:
        for ln in t.splitlines():
            ln = ln.split("#")[0].strip()
            if not ln or ln.startswith(("-", "git+", "http")):
                continue
            m = re.match(r"([A-Za-z0-9_.\-\[\]]+)\s*(==|>=|<=|~=|>|<|!=)?\s*([^\s;,]*)", ln)
            if m:
                out.append({"package": m.group(1), "version": (m.group(2) or "") + (m.group(3) or "") or "none", "pinning": "exact" if m.group(2) == "==" else "unpinned" if not m.group(2) else "loose"})
    if not out:
        raise PackError("No dependencies found in that text.")
    bad = [o for o in out if o["pinning"] != "exact"]
    return {"says": f"{len(bad)} of {len(out)} dependencies are not pinned exactly.", "dependencies": out[:200], "notes": ["Use a lockfile so installs are repeatable even if the file shows ranges.", "This checks pinning only. Run your ecosystem's audit command (for example pip-audit or npm audit) for known vulnerabilities."]}


_docker_tool("devsecops")


@tool("devsecops", "gates", "Security gates checklist", "A short, staged list of checks to add to your delivery pipeline.", [I("stage", "Where are you now?", "select", "start", [{"id": "start", "label": "Nothing yet"}, {"id": "some", "label": "Tests and a pipeline, little security"}, {"id": "mature", "label": "Some checks, want to tighten"}])])
def gates(v):
    s = txt(v, "stage", 10)
    steps = {"start": [("This week", ["Turn on secrets scanning and push protection in your code host", "Require pull requests and a review for the main branch", "Use MFA for everyone"]), ("This month", ["Pin dependencies and use a lockfile", "Run your ecosystem's audit command in CI", "Make pipeline permissions read-only by default"])],
             "some": [("Next", ["Add secrets scanning to CI", "Add a dependency audit that fails on high issues", "Scan container images", "Run the pipeline checker on every workflow"]), ("Then", ["Add a basic static analysis scan", "Pin third-party actions to commits"])],
             "mature": [("Tighten", ["Sign build artifacts and keep a software bill of materials", "Separate deploy credentials per environment with short-lived tokens", "Require approval for production deploys", "Review gates quarterly and track findings fixed per month"])]}.get(s)
    if not steps:
        raise PackError("Choose where you are now.")
    return {"says": "Checklist ready.", "markdown": md("Security gates", steps), "notes": ["Fail builds only on high findings at first, then tighten as the team catches up."]}


# ------------------------------------------------------------------ tools: computer vision
@tool("cv", "labels", "Label audit", "Checks YOLO-format label lines for common problems. Text only.", [I("names", "Class names in order (comma separated)", "text", "car, person"), I("labels", "Label lines: class x_center y_center width height (values 0 to 1)", "area", "0 0.5 0.5 0.2 0.3\n1 0.3 0.4 0.05 0.1\n1 0.3 0.4 0.05 0.1")])
def labels(v):
    names = [n.strip() for n in str(v.get("names") or "").split(",") if n.strip()]
    rs = rows(v, "labels", 20000)
    if not rs:
        raise PackError("Paste at least one label line.")
    cnt, areas, f, seen = {}, [], [], set()
    bad = tiny = huge = dup = unk = 0
    for i, ln in enumerate(rs, 1):
        c = ln.split()
        if len(c) != 5:
            bad += 1
            continue
        try:
            k, x, y, w, h = int(c[0]), *(float(a) for a in c[1:])
        except ValueError:
            bad += 1
            continue
        if not (0 <= x <= 1 and 0 <= y <= 1 and 0 < w <= 1 and 0 < h <= 1) or x - w / 2 < -1e-6 or x + w / 2 > 1 + 1e-6 or y - h / 2 < -1e-6 or y + h / 2 > 1 + 1e-6:
            bad += 1
            continue
        if names and not 0 <= k < len(names):
            unk += 1
        key = (k, round(x, 4), round(y, 4), round(w, 4), round(h, 4))
        if key in seen:
            dup += 1
        seen.add(key)
        cnt[k] = cnt.get(k, 0) + 1
        a = w * h
        areas.append(a)
        tiny += a < 0.0005
        huge += a > 0.8
    if bad:
        f.append({"severity": "high", "says": f"{bad} line(s) are malformed or outside the 0 to 1 range or the image edges."})
    if unk:
        f.append({"severity": "high", "says": f"{unk} label(s) use a class number that is not in your class list."})
    if dup:
        f.append({"severity": "medium", "says": f"{dup} duplicate box(es): the same box appears twice."})
    if tiny:
        f.append({"severity": "low", "says": f"{tiny} very small box(es) (under 0.05% of the image). Check they are real and not mis-clicks."})
    if huge:
        f.append({"severity": "low", "says": f"{huge} box(es) cover more than 80% of the image."})
    if cnt and max(cnt.values()) > 10 * max(min(cnt.values()), 1):
        f.append({"severity": "medium", "says": "One class has more than 10 times as many boxes as another. Rare classes will be learned poorly."})
    classes = [{"class": names[k] if names and 0 <= k < len(names) else str(k), "boxes": n} for k, n in sorted(cnt.items())]
    return {"says": f"{len(rs)} lines checked, {len(f)} issue type(s) found.", "classes": classes, "mean_box_area_pct": round(100 * sum(areas) / len(areas), 2) if areas else None, "findings": f, "caution": "Checks the files, not whether the boxes are in the right place. Review a random sample by eye."}


def _iou(a, b) -> float:
    ix1, iy1, ix2, iy2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def _box(c, i, what):
    try:
        b = [float(x) for x in c]
    except ValueError:
        raise PackError(f"{what} {i}: box numbers must be numbers.") from None
    if b[2] <= b[0] or b[3] <= b[1]:
        raise PackError(f"{what} {i}: the box needs x2 greater than x1 and y2 greater than y1.")
    return b


@tool("cv", "iou", "Box overlap (IoU)", "How much two boxes overlap, as a number from 0 to 1.", [I("a", "Box A: x1, y1, x2, y2", "text", "10, 10, 110, 110"), I("b", "Box B: x1, y1, x2, y2", "text", "50, 50, 150, 150")])
def iou(v):
    a, b = split(txt(v, "a", 80, True)), split(txt(v, "b", 80, True))
    if len(a) != 4 or len(b) != 4:
        raise PackError("Each box needs four numbers: x1, y1, x2, y2.")
    r = _iou(_box(a, 1, "Box"), _box(b, 2, "Box"))
    return {"says": f"IoU is {r:.3f}. {'Counts as a match' if r >= 0.5 else 'Does not count as a match'} at the common 0.5 threshold.", "iou": round(r, 4), "notes": ["IoU is intersection area divided by union area. 1 means identical boxes and 0 means no overlap."]}


@tool("cv", "detect", "Detection scorer", "Scores predicted boxes against true boxes: matches, misses, false alarms, precision and recall.",
      [I("truth", "True boxes: image, class, x1, y1, x2, y2 (one per line)", "area", "img1, cat, 10, 10, 110, 110\nimg1, dog, 200, 50, 300, 150\nimg2, cat, 20, 20, 80, 90"), I("pred", "Predictions: image, class, x1, y1, x2, y2, confidence", "area", "img1, cat, 12, 8, 108, 112, 0.9\nimg1, cat, 400, 400, 450, 450, 0.6\nimg2, cat, 100, 100, 160, 170, 0.8"), I("thr", "IoU needed for a match", "number", "0.5")])
def detect(v):
    thr = num(v, "thr", 0.05, 0.99)
    truth, pred = [], []
    for i, ln in enumerate(rows(v, "truth", 5000), 1):
        c = split(ln)
        if len(c) != 6:
            raise PackError(f"True box {i} needs image, class and four numbers.")
        truth.append((c[0], c[1], _box(c[2:], i, "True box")))
    for i, ln in enumerate(rows(v, "pred", 5000), 1):
        c = split(ln)
        if len(c) != 7:
            raise PackError(f"Prediction {i} needs image, class, four numbers and a confidence.")
        try:
            conf = float(c[6])
        except ValueError:
            raise PackError(f"Prediction {i}: confidence must be a number.") from None
        pred.append((c[0], c[1], _box(c[2:6], i, "Prediction"), conf))
    if not truth:
        raise PackError("Add at least one true box.")
    used, per = set(), {}
    for img, cls, b, conf in sorted(pred, key=lambda p: -p[3]):
        best, bi = 0.0, None
        for j, (ti, tc, tb) in enumerate(truth):
            if ti == img and tc == cls and j not in used:
                o = _iou(b, tb)
                if o > best:
                    best, bi = o, j
        s = per.setdefault(cls, {"tp": 0, "fp": 0, "fn": 0})
        if bi is not None and best >= thr:
            used.add(bi)
            s["tp"] += 1
        else:
            s["fp"] += 1
    for j, (_, tc, _) in enumerate(truth):
        if j not in used:
            per.setdefault(tc, {"tp": 0, "fp": 0, "fn": 0})["fn"] += 1
    rowsout, T = [], {"tp": 0, "fp": 0, "fn": 0}
    for cls, s in sorted(per.items()):
        for k in T:
            T[k] += s[k]
        p = s["tp"] / (s["tp"] + s["fp"]) if s["tp"] + s["fp"] else None
        r = s["tp"] / (s["tp"] + s["fn"]) if s["tp"] + s["fn"] else None
        rowsout.append({"class": cls, **s, "precision": round(p, 3) if p is not None else None, "recall": round(r, 3) if r is not None else None})
    P = T["tp"] / (T["tp"] + T["fp"]) if T["tp"] + T["fp"] else 0.0
    R = T["tp"] / (T["tp"] + T["fn"]) if T["tp"] + T["fn"] else 0.0
    F = 2 * P * R / (P + R) if P + R else 0.0
    return {"says": f"Found {T['tp']} of {T['tp'] + T['fn']} true objects with {T['fp']} false alarm(s): precision {P:.2f}, recall {R:.2f}, F1 {F:.2f} at IoU {thr:g}.", "per_class": rowsout, "precision": round(P, 3), "recall": round(R, 3), "f1": round(F, 3),
            "notes": ["Each true box can be matched once; predictions are taken from the most confident down.", "This is a single-threshold score, not the full average-precision curve. Use many varied test images before trusting it."]}
