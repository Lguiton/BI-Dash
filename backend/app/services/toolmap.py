"""Tool map: for the tools people name in job ads, what this app has, what it replaces, and what it deliberately doesn't embed.

Status
  built         a working feature in this app does the same job at personal scale
  partial       covers the core idea only; the note says what is missing
  taught        explained in a manual, but not embedded (offensive or dual-use, or needs a lab)
  not_embedded  cloud, paid or too large to embed here; the note says the free route
"""
from __future__ import annotations

S = lambda tool, status, where, note, href=None: {"tool": tool, "status": status, "where": where, "note": note, "href": href}  # noqa: E731

MAP = {
    "Data science and ML": [
        S("Python, pandas, scikit-learn, Jupyter", "built", "Notebooks page; optional Jupyter in Docker (profile notebooks)", "Real libraries, run in the backend. Jupyter needs the notebooks profile.", "/python"),
        S("MLflow (experiment tracking)", "built", "ML Lab: run tracker, copy to MLflow", "Our tracker stars, notes and compares runs. 'Copy to MLflow' writes them to a local MLflow store if mlflow is installed.", "/ml"),
        S("AutoML (model comparison)", "partial", "ML Lab: compare models", "Ranks several model types on the same split. No automated feature search or hyper-parameter tuning.", "/ml"),
        S("Neural networks (TensorFlow/PyTorch)", "partial", "ML Lab: neural net (MLP)", "A small scikit-learn MLP. No GPUs, convolution or transformers.", "/ml"),
        S("KNIME / Alteryx (visual workflows)", "built", "Workflow builder", "Filter, select, derive, aggregate, sort, limit; shows the SQL and pandas equivalent.", "/workflow"),
        S("Model serving (FastAPI, BentoML)", "built", "ML Lab: model registry and predict", "Versioned models with stages and a predict endpoint. Single process; no autoscaling.", "/ml"),
        S("Evidently (drift monitoring)", "partial", "Model registry: drift check", "Population stability on inputs only. Doesn't see label drift or performance drift.", "/ml"),
        S("R, SAS, SPSS, MATLAB", "not_embedded", "-", "R and SAS are skipped on purpose. Python covers the same ground; R can run on its own in RStudio."),
    ],
    "Data engineering": [
        S("SQL, DuckDB, PostgreSQL", "built", "SQL Lab, Postgres lab (Docker)", "DuckDB in the app; Postgres via docker-compose.", "/lab"),
        S("Airflow / Prefect (orchestration)", "built", "Pipelines page", "Tasks with dependencies, retries, schedule and run history. Runs in-process, one at a time; not distributed.", "/pipelines"),
        S("Great Expectations / dbt tests", "built", "Data quality rules", "Not-null, unique, range, in-set, pattern, row count, freshness; history and alerts.", "/hub"),
        S("Data catalogue (DataHub, Amundsen)", "built", "Dataset hub and governance tabs", "Notes, tags, health grade, owners, classification, lineage.", "/hub"),
        S("Kafka / Spark / Flink", "taught", "Apache lab", "Concepts and small exercises, not a cluster.", "/apache"),
        S("Fivetran / Airbyte (connectors)", "partial", "Data sources", "File, URL, database query and web table connectors with schedules. A handful, not hundreds.", "/sources"),
        S("Snowflake, Databricks, BigQuery, Redshift", "not_embedded", "-", "Cloud warehouses. DuckDB and Postgres teach the same SQL."),
        S("AWS, Azure, GCP, Terraform, Kubernetes", "not_embedded", "-", "Cloud and infrastructure tools are out of scope here."),
        S("Docker", "built", "docker-compose.yml", "Backend, frontend, Postgres and optional Jupyter profiles.", None),
    ],
    "Analytics and BI": [
        S("Excel / Google Sheets", "partial", "Import, export and the Records page", "Excel export of any table. No formula engine.", "/data"),
        S("Power BI / Tableau / Looker", "partial", "Dashboards, KPI builder, charts", "KPI cards, filters, chart gallery, PDF/Excel reports. No drag-and-drop canvas or semantic model.", "/kpis"),
        S("dbt / semantic layer", "partial", "Star schema page and views", "Documented model and views; no dbt-style compile step.", "/schema"),
        S("Web scraping (Power Query 'From Web')", "built", "Sources: Table on a web page", "One table from a public https page. No JavaScript rendering.", "/sources"),
        S("Statistics (SPSS, Minitab)", "built", "Data Scientist track", "Tests with effect sizes and intervals.", "/tracks/scientist"),
    ],
    "Full stack and AI engineering": [
        S("Postman / Insomnia", "built", "Full Stack track: API map & tester", "Tests this app's own endpoints only.", "/tracks/fullstack"),
        S("Git and GitHub, CI", "built", "Repo and .github/workflows/ci.yml", "Five CI jobs on every push.", None),
        S("Prometheus and Grafana", "partial", "Ops page and /metrics", "A Prometheus-format /metrics endpoint plus a built-in summary. Point your own Prometheus at it for Grafana.", "/ops"),
        S("LangSmith / Langfuse (LLM monitoring)", "partial", "Ops page: AI calls", "Latency, errors, calls per provider; cost only if you set prices.", "/ops"),
        S("LangChain / agents / evals", "built", "AI Engineering track, agents and evals", "Tool-using agents with guardrails and structural evals.", "/tracks/ai"),
        S("Vector database / RAG", "partial", "Knowledge search", "Keyword (TF-IDF) search over docs and manuals. Not semantic.", "/knowledge"),
        S("Swagger / OpenAPI", "built", "Backend /docs", "FastAPI generates it.", None),
    ],
    "Systems analysis and project management": [
        S("Jira / Trello / Asana", "built", "Project & Product track: board, sprints, calendar", "Board, sprints, flow metrics, calendar and simple rules. Single user.", "/tracks/pm"),
        S("MS Project / Gantt", "partial", "Schedule tab: critical path", "Dependencies and critical path; no drag-to-resize Gantt.", "/tracks/pm"),
        S("Lucidchart / Visio / draw.io", "partial", "Diagram studio", "Text-to-diagram for flowcharts. No free-form canvas.", "/diagrams"),
        S("Zapier / Make (automation)", "partial", "PM automations", "A few if-this-then-that rules on your own board. No external apps.", "/tracks/pm"),
        S("Splunk / ELK (log analysis)", "partial", "Log explorer", "Paste or upload one file; detections and search. No indexing of live streams.", "/logs"),
    ],
    "Cybersecurity": [
        S("Self-audit / hardening checklists", "built", "Cybersecurity track: Self-audit", "Common slips in your own setup.", "/tracks/security"),
        S("SIEM (Splunk, Elastic Security)", "partial", "Log explorer and detections", "Rules for brute force, probing and injection patterns on a file you give it.", "/logs"),
        S("SOAR / incident response", "partial", "Incident tracker with playbook checklists", "Checklists and a timeline; no automatic actions.", "/tracks/security"),
        S("Header and TLS checkers (SSL Labs, securityheaders)", "built", "Web checks", "Public hosts only.", "/tracks/security"),
        S("Password managers and 2FA", "partial", "Crypto labs", "Strength estimator, passphrase generator and a TOTP lab for learning. Use a real password manager for real passwords.", "/tracks/security"),
        S("Dependency scanners (pip-audit, Dependabot)", "taught", "Cybersecurity manual", "Run pip-audit yourself; enable Dependabot in GitHub."),
        S("Wireshark", "taught", "Cybersecurity track", "Packet capture needs system privileges; learn it in a lab you own."),
        S("Nmap", "taught", "Cybersecurity track", "Scanning other machines is not built. Our port check looks at this computer only."),
        S("Burp Suite / OWASP ZAP", "taught", "Cybersecurity track", "Web app testing proxies. Use them on deliberately vulnerable apps (DVWA, Juice Shop) you run yourself."),
        S("Metasploit, C2 frameworks, fuzzers, exploit kits", "not_embedded", "-", "Offensive tools are not built or wrapped here, by design."),
        S("Kali Linux", "taught", "Cybersecurity track", "A VM image; practise on targets you own."),
        S("CrowdStrike, Okta, Splunk Cloud and other paid platforms", "not_embedded", "-", "Paid or cloud services."),
    ],
    "Network engineering": [
        S("Subnet calculators (ipcalc, subnetting tools)", "built", "Network track: Subnet and VLSM", "Subnet, split, VLSM plan, overlap check and route summarisation. Exact arithmetic.", "/tracks/network"),
        S("Cisco IOS / network config review", "partial", "Network track: Config review", "Pattern checks on pasted text. Not a CIS benchmark audit and not live devices.", "/tracks/network"),
        S("Wireshark / tcpdump (packet analysis)", "partial", "Network track: Packet capture reader", "Reads tcpdump -nn text you paste. It does not capture packets.", "/tracks/network"),
        S("dig / nslookup / Test-NetConnection", "partial", "Network track: DNS and reachability", "A/AAAA lookups and a one-port TCP test against public hosts only.", "/tracks/network"),
        S("iperf3 (throughput testing)", "taught", "Network track", "Run it between two machines you control. The calculators explain what to expect."),
        S("Cisco Packet Tracer, GNS3, EVE-NG", "taught", "Network track", "Free virtual labs for routing and VLANs; not embedded."),
        S("Zabbix, Nagios, PRTG, Prometheus + Grafana (monitoring)", "taught", "Network track", "This app exposes /metrics for Prometheus; the monitoring stack itself isn't embedded."),
        S("Ansible, Netmiko, NAPALM (network automation)", "taught", "Network track", "Learn the idea in the config review; automation tools aren't embedded."),
        S("pfSense / OPNsense (firewalls)", "taught", "Network track", "Run them in a VM. Not embedded."),
        S("Nmap and other scanners", "taught", "Network track", "Scanning isn't built here: the TCP check tests one port on a public host at a time."),
        S("Cloud networking (VPC, transit gateway, SD-WAN) and Cisco DNA / Meraki dashboards", "not_embedded", "-", "Cloud and paid platforms are out of scope."),
    ],
    "IT support and administration": [
        S("Helpdesk systems (osTicket, GLPI, Zendesk)", "partial", "IT track: Helpdesk", "Tickets, category checklists, timeline and SLA clock. No email intake or user portal.", "/tracks/itsupport"),
        S("Asset management (Snipe-IT, GLPI inventory)", "partial", "IT track: Inventory", "Manual entries with warranty flags. No automatic discovery.", "/tracks/itsupport"),
        S("Windows Event Viewer / SIEM log review", "partial", "IT track: Event log reader", "Reads an export you paste; names well-known event IDs and flags patterns.", "/tracks/itsupport"),
        S("Onboarding / offboarding runbooks", "built", "IT track: Checklists", "Tickable checklists you can adapt.", "/tracks/itsupport"),
        S("Capacity planning and RAID calculators", "built", "IT track: Capacity and RAID", "Straight-line forecast, availability to downtime, RAID usable space.", "/tracks/itsupport"),
        S("PowerShell, Bash, Python scripting", "taught", "IT track: Cheat sheets", "Starter commands; Python runs in the notebooks."),
        S("Active Directory, Group Policy, Windows Server", "taught", "IT track", "Practise in a Windows Server evaluation VM. Not embedded."),
        S("VirtualBox, Hyper-V, Proxmox (virtualisation)", "taught", "IT track", "Safe places to break things; not embedded."),
        S("Backup software (Veeam, restic, rsync)", "partial", "Settings and backups", "This app backs up its own database. The 3-2-1 rule is explained; other backup tools aren't embedded.", "/settings"),
        S("Intune, Entra ID, Microsoft 365 / Google Workspace admin, ServiceNow, Jira Service Management", "not_embedded", "-", "Cloud and paid services are out of scope."),
    ],
}


def tool_map() -> dict:
    cats = [{"category": c, "tools": t} for c, t in MAP.items()]
    counts: dict[str, int] = {}
    for c in cats:
        for t in c["tools"]:
            counts[t["status"]] = counts.get(t["status"], 0) + 1
    return {"categories": cats, "counts": counts,
            "legend": {"built": "A working feature does the same job at personal scale", "partial": "Covers the core idea; the note says what is missing",
                       "taught": "Explained, not embedded", "not_embedded": "Cloud, paid or offensive: not built here"}}
