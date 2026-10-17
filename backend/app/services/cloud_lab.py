"""Cloud and "as a service" lab: service models, who manages what, a picker, Infrastructure as Code templates and a reviewer, a real-work checklist and a quiz.

Reference and a local text checker. Nothing here connects to a cloud, runs pasted code or changes anything. The checker is a first pass for you, not a security audit."""
from __future__ import annotations

import re

REVIEWED = "2026-10"
NOTE = "Plain-language reference. Prices and product names change, so check the provider's site. Never put real client data, passwords or keys into this tool."
MAX_TEXT = 20000


class CloudError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


def _m(id, name, short, what, examples, you, provider, good, watch, cost, small, kw):
    return {"id": id, "name": name, "short": short, "what": what, "examples": examples, "you_manage": you, "provider_manages": provider,
            "good_for": good, "watch_out": watch, "cost": cost, "small_business": small, "keywords": kw}


MODELS = [
    _m("iaas", "IaaS: Infrastructure as a Service", "Rent virtual servers, storage and networks", "You rent the raw building blocks: virtual machines, disks, networks. You install and run everything on top.",
       "AWS EC2, Azure Virtual Machines, Google Compute Engine, DigitalOcean Droplets", "Operating system, patches, software, firewall rules, backups, data", "Physical data center, hardware, virtualization, base network",
       "Custom setups, moving old servers off-site, test labs, full control", "You patch and secure the servers. A forgotten server still bills you.", "Pay per hour or month while it exists",
       "A client who needs one Windows or Linux server in the cloud instead of a box in a closet.", "server vm virtual machine hosting lift shift infrastructure"),
    _m("paas", "PaaS: Platform as a Service", "Upload your app; the platform runs it", "The provider manages servers and the runtime. You deploy code and set options.",
       "Azure App Service, Google App Engine, Heroku, Render, Fly.io, AWS Elastic Beanstalk", "Your application code, its settings and data", "Servers, operating system, runtime, scaling, patches",
       "Websites and APIs without server chores", "Less control; moving off a platform can mean rework; costs grow with traffic.", "Per app or per usage; often a small monthly floor",
       "A custom web app or client portal for a client, with no one to patch a server.", "web app platform deploy heroku render api hosting"),
    _m("saas", "SaaS: Software as a Service", "Use finished software in a browser", "Ready-made software that the vendor runs. You sign in and use it.",
       "Microsoft 365, Google Workspace, QuickBooks Online, Salesforce, Zoom, Slack", "Your users, settings, your data and who can access it", "Everything else: servers, app, updates, uptime",
       "Email, office tools, accounting, CRM; fastest to start", "You depend on the vendor. Check export options, backups and who owns the data.", "Per user per month",
       "Most small clients: Microsoft 365 or Google Workspace for email and files. Your work is setup, security and support.", "email office software crm accounting saas subscription 365 workspace"),
    _m("dbaas", "DBaaS: Database as a Service", "A managed database you connect to", "The provider runs the database engine, patches, backups and failover. You create tables and connect your app.",
       "Amazon RDS and Aurora, Azure SQL Database, Google Cloud SQL and Spanner, MongoDB Atlas, Supabase, Neon", "Schema, queries, users and permissions, data", "Servers, database software, patching, backups, replication",
       "Apps that need a reliable database without a database admin", "Costs rise with size and traffic. Check backup retention, region and whether it is reachable from the internet.", "Per size and usage, plus storage",
       "A client app that stores customer or booking records. Keep it private, not open to the whole internet.", "database sql postgres mysql mongodb managed db"),
    _m("faas", "FaaS and serverless: Function as a Service", "Run small pieces of code on demand", "You upload a function; it runs when triggered (a web request, a file upload, a timer) and you pay only for run time.",
       "AWS Lambda, Azure Functions, Google Cloud Functions, Cloudflare Workers", "The function code, triggers, permissions", "All servers and scaling",
       "Scheduled jobs, webhooks, light APIs, file processing", "Cold starts, time limits, harder to debug locally, and cost surprises with heavy use.", "Per run and run time; a free tier is common",
       "Small automations: a nightly report, a form that emails a summary.", "serverless function lambda trigger webhook scheduled"),
    _m("caas", "CaaS: Containers as a Service", "A managed place to run containers (not the same CaaS as communications)", "The provider runs the container platform (often Kubernetes). You bring container images.",
       "Amazon ECS and EKS, Azure Container Apps and AKS, Google Cloud Run and GKE", "Container images, configs, scaling rules", "Cluster control plane, servers, orchestration",
       "Apps already packaged in Docker, microservices", "Real learning curve. Overkill for one small app.", "Per container resources and cluster fees",
       "Rare for a small client. Good to understand for larger shops.", "container docker kubernetes k8s cluster"),
    _m("baas", "BaaS: Backend as a Service", "Ready-made backend for apps", "Hosted login, database, file storage and APIs so you build only the front end.",
       "Firebase, Supabase, AWS Amplify, Appwrite", "App front end, rules and permissions", "Auth, database, storage, servers",
       "Fast prototypes, simple mobile and web apps", "Lock-in and permissions rules are easy to get wrong, which exposes data.", "Free tier then usage based",
       "A quick client prototype. Review the access rules before real data goes in.", "backend firebase supabase auth login app mobile"),
    _m("daas-desktop", "DaaS: Desktop as a Service", "Virtual desktops you reach from anywhere", "Windows desktops run in the cloud and you connect from any device.",
       "Windows 365, Azure Virtual Desktop, Amazon WorkSpaces, Citrix", "Users, apps, images, policies", "Servers hosting the desktops",
       "Remote teams, locked-down data, shared or seasonal staff", "Needs good internet; licensing is complicated.", "Per user per month",
       "A small office that wants staff to work from home without data on laptops.", "desktop vdi remote virtual desktop windows 365 workspaces"),
    _m("daas-data", "DaaS: Data as a Service", "Buy or subscribe to data", "Access to datasets or data feeds delivered by an API or download.",
       "Weather, maps, market, company and demographic data providers", "How you use and combine the data, licensing compliance", "Collecting, cleaning and serving the data",
       "Enriching reports and dashboards", "License limits on reuse and sharing; quality varies.", "Subscription or per call",
       "Adding outside data to a BI report for a client, within the license.", "data feed api dataset subscription enrichment"),
    _m("secaas", "SECaaS: Security as a Service", "Security tools run by a provider", "Security functions delivered as a subscription: email filtering, endpoint protection, monitoring, vulnerability scans.",
       "Microsoft Defender, CrowdStrike, Proofpoint, Cloudflare, managed detection and response", "Policies, onboarding devices, responding to alerts", "Tools, updates, threat intelligence",
       "Small teams without a security staff", "Alerts still need a human. Do not assume a product replaces training and backups.", "Per user, device or month",
       "Email security and endpoint protection for a small client.", "security antivirus endpoint email filtering edr mdr"),
    _m("idaas", "IDaaS: Identity as a Service", "Cloud sign-in and access control", "Single sign-on, multi-factor authentication and user directories in the cloud.",
       "Microsoft Entra ID, Okta, Google Identity, Duo, JumpCloud", "Users, groups, access rules, MFA enrollment", "Directory servers, availability, sign-in tools",
       "Turning on MFA, one login for many apps, onboarding and offboarding", "A bad access rule locks everyone out. Keep an emergency admin account.", "Per user per month",
       "MFA and clean onboarding and offboarding for every client. Often the best security value.", "identity sso mfa login directory entra okta active directory"),
    _m("baas-backup", "BaaS: Backup as a Service", "Backups held by a provider", "Automatic backups of PCs, servers or cloud apps stored off-site.",
       "Backblaze, Veeam, Acronis, Datto, backups for Microsoft 365", "What gets backed up, retention, test restores", "Storage, scheduling, software",
       "Off-site copy that survives fire, theft and ransomware", "An untested backup is a guess. Check restore time and encryption.", "Per device or per terabyte",
       "A client with one office and no off-site backup. Test a restore.", "backup restore ransomware offsite 3-2-1"),
    _m("draas", "DRaaS: Disaster Recovery as a Service", "A standby copy you can switch on", "A cloud replica of your servers that can start if the main site fails.",
       "Azure Site Recovery, AWS Elastic Disaster Recovery, Zerto", "Recovery plan, testing, which systems come first", "Replication and failover infrastructure",
       "Businesses that cannot afford days of downtime", "Needs regular failover tests, and costs more than plain backup.", "Per protected server plus storage",
       "Only for clients where downtime is expensive. Most need good backups first.", "disaster recovery failover replica rto rpo"),
    _m("naas", "NaaS: Network as a Service", "Network gear and services as a subscription", "Managed Wi-Fi, SD-WAN and cloud-managed switches and firewalls with ongoing service.",
       "Cisco Meraki, Ubiquiti UniFi cloud, Aruba Central, managed SD-WAN", "Settings, SSIDs, policies, user support", "Controller, firmware, monitoring",
       "Offices with several sites or Wi-Fi problems", "Gear may stop working properly if the subscription lapses.", "Per device or per site per month",
       "A multi-location client who wants one place to manage Wi-Fi.", "network wifi sd-wan managed meraki unifi"),
    _m("staas", "STaaS: Storage as a Service", "Cloud file and object storage", "Shared file storage or bulk storage that you pay for by the gigabyte.",
       "OneDrive, Dropbox, Google Drive, AWS S3, Azure Blob, Backblaze B2", "Folders, sharing settings, retention", "Disks, redundancy, availability",
       "File sharing, archives, website assets", "Public sharing links and open buckets are a top cause of leaks.", "Per user or per GB, sometimes plus download fees",
       "Replacing a file server in a closet. Review who can share links outside the company.", "storage files s3 bucket onedrive dropbox sharepoint"),
    _m("ccaas", "CaaS (Communications), UCaaS and CCaaS: phones, video, chat", "Cloud phone, video and chat systems. Not the same CaaS as containers", "Voice, video, chat and call-center features delivered from the cloud.",
       "RingCentral, Microsoft Teams, Zoom, 8x8, Twilio", "Extensions, call flows, devices, user support", "Phone network, servers, updates",
       "Replacing an old phone system, remote staff", "Needs solid internet and QoS; emergency calling (911) must be set up correctly.", "Per user per month",
       "A client replacing a landline PBX. Confirm 911 address setup.", "phone voip ucaas ccaas communications calls teams zoom contact center chat video"),
    _m("aiaas", "AIaaS and MLaaS: AI as a Service", "Use AI models through an API", "Hosted AI and machine learning: text, vision, speech and prediction models you call or train online.",
       "Anthropic, OpenAI and Google APIs, Azure AI, Amazon Bedrock, SageMaker", "Prompts, data you send, checking the output", "Models, servers, scaling",
       "Adding AI to a workflow without building models", "Data you send leaves your control; check the provider's data terms. Output can be wrong.", "Per token or per call",
       "Summaries and drafting for a client, with their data rules in mind.", "ai ml machine learning llm api model"),
    _m("maas", "Monitoring and management as a Service (RMM and MSP)", "A provider watches and manages your IT", "Remote monitoring and management tools, or a managed service provider that runs a client's IT for a monthly fee.",
       "NinjaOne, Datto RMM, ConnectWise, Atera", "Scope, approvals, who is on call", "Monitoring tools, patching automation, alerts",
       "Ongoing support for small offices", "Your RMM can reach many clients, so it needs strong protection and MFA.", "Per device or per user per month",
       "Selling a monthly support plan to repeat clients instead of one-off repairs.", "monitoring rmm msp managed service provider support plan"),
    _m("xaas", "XaaS: Anything as a Service", "The general idea", "Any capability sold as a subscription instead of owned: hardware, software, security, analytics.",
       "Hardware as a Service (leased laptops), Analytics as a Service, Print as a Service", "Depends on the offer", "Depends on the offer",
       "Spreading cost, avoiding big purchases", "Read the contract: term, exit terms, price increases, who owns the data.", "Subscription",
       "Leased laptops or managed printing for a client.", "xaas hardware leasing print subscription"),
    _m("iac", "IaC: Infrastructure as Code", "Not a service: a way to build all of the above", "Describing servers, networks and settings in files that a tool applies the same way every time.",
       "Terraform, OpenTofu, Ansible, CloudFormation, Bicep, Pulumi", "The files, review, and where they run", "Nothing (it is a method, not a product)",
       "Repeatable setups, fast rebuilds, change history in Git", "Mistakes apply at scale. Preview first, keep secrets out of the files.", "The tools are mostly free; the cloud resources cost",
       "Rebuilding a client's cloud setup from files instead of memory.", "iac terraform ansible code automation cloudformation bicep"),
]

LAYERS = ["Applications", "Data", "Runtime", "Middleware", "Operating system", "Virtualization", "Servers", "Storage", "Networking"]
# who manages each layer: Y = you, P = provider. Data and who has access are always yours.
_STACK = {
    "On-premises (your own gear)": "YYYYYYYYY",
    "IaaS": "YYYYYPPPP",
    "CaaS": "YYYPPPPPP",
    "PaaS": "YYPPPPPPP",
    "FaaS (serverless)": "YYPPPPPPP",
    "SaaS": "PYPPPPPPP",
}


def responsibility() -> dict:
    rows = [{"model": k, "cells": [{"layer": LAYERS[i], "who": "you" if c == "Y" else "provider"} for i, c in enumerate(v)]} for k, v in _STACK.items()]
    return {"layers": LAYERS, "rows": rows,
            "note": "Even with SaaS, your data, your users and who can sign in are still your job. Providers secure their platform; you configure it safely. This is called the shared responsibility model."}


def reference() -> dict:
    return {"reviewed": REVIEWED, "note": NOTE, "models": [{k: v for k, v in m.items() if k != "keywords"} for m in MODELS], "responsibility": responsibility()}


def pick(need: str) -> dict:
    toks = [t for t in re.sub(r"[^a-z0-9 ]", " ", (need or "").lower()).split() if len(t) > 1]
    if not toks:
        raise CloudError("Describe what the client needs, like 'email for 8 people' or 'database for a booking app'.")
    scored = []
    for m in MODELS:
        hay = (m["name"] + " " + m["short"] + " " + m["keywords"] + " " + m["small_business"]).lower()
        s = sum(2 for t in toks if t in m["keywords"].split()) + sum(1 for t in toks if t in hay)
        if s:
            scored.append((s, m))
    scored.sort(key=lambda x: -x[0])
    out = [{"id": m["id"], "name": m["name"], "why": m["small_business"], "you_manage": m["you_manage"], "watch_out": m["watch_out"]} for _, m in scored[:3]]
    return {"matches": out, "ask_first": ["Does the client handle health, financial, student or card data? If so, check the provider will sign the right agreement (for example a HIPAA BAA).",
                                          "Who owns and can export the data if the contract ends?",
                                          "Who is the one admin, and is multi-factor sign-in on?",
                                          "What does a restore look like, and who tested it?",
                                          "What is the monthly cost at the expected size, and what happens when it grows?"],
            "note": "A starting idea from keywords, not a recommendation. Confirm with the client and the provider's current terms."}


# ------------------------------------------------------------------ templates
TEMPLATES = [
    {"id": "tf", "title": "Terraform: one small server with a firewall", "language": "hcl", "text": '''terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

variable "region" {
  default = "us-west-2"
}

variable "my_ip" {
  description = "Your public IP in CIDR form, e.g. 203.0.113.7/32"
  type        = string
}

resource "aws_security_group" "web" {
  name        = "client-web-sg"
  description = "HTTPS from anywhere, SSH only from my IP"

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "SSH from my IP only"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }
}

resource "aws_instance" "web" {
  ami                    = "ami-REPLACE-WITH-CURRENT-UBUNTU-AMI"
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.web.id]

  tags = {
    Name   = "client-web"
    Client = "REPLACE"
    Owner  = "me"
  }
}

output "server_ip" {
  value = aws_instance.web.public_ip
}
''', "note": "Run: terraform init, then terraform plan (read it), then terraform apply. terraform destroy removes everything it made. Look up a current AMI for your region."},
    {"id": "ans-linux", "title": "Ansible: baseline for a Linux machine", "language": "yaml", "text": '''---
- name: Baseline for a Linux machine
  hosts: all
  become: true
  tasks:
    - name: Install security updates
      ansible.builtin.apt:
        upgrade: safe
        update_cache: true

    - name: Make sure the firewall is installed
      ansible.builtin.apt:
        name: ufw
        state: present

    - name: Allow SSH
      community.general.ufw:
        rule: allow
        port: "22"
        proto: tcp

    - name: Turn the firewall on
      community.general.ufw:
        state: enabled
        policy: deny
''', "note": "Test first: ansible-playbook baseline.yml --check --diff. Use a key, not a password, for SSH. Confirm you will not lock yourself out before enabling the firewall."},
    {"id": "ans-win", "title": "Ansible: baseline for a Windows PC", "language": "yaml", "text": '''---
- name: Baseline for a Windows PC
  hosts: windows
  tasks:
    - name: Make sure Windows Defender real-time protection is on
      ansible.windows.win_powershell:
        script: |
          Set-MpPreference -DisableRealtimeMonitoring $false

    - name: Install Windows security updates
      ansible.windows.win_updates:
        category_names: [SecurityUpdates, CriticalUpdates]
        reboot: false

    - name: Create a folder for client tools
      ansible.windows.win_file:
        path: C:\\ClientTools
        state: directory
''', "note": "Needs WinRM or SSH set up on the PC and the client's written okay. Run with --check first. Reboot only in the agreed window."},
    {"id": "net-backup", "title": "Ansible: back up router and switch configs", "language": "yaml", "text": '''---
- name: Save network device configs
  hosts: routers
  gather_facts: false
  connection: ansible.netcommon.network_cli
  tasks:
    - name: Back up the running config
      cisco.ios.ios_config:
        backup: true
        backup_options:
          dir_path: ./config-backups
          filename: "{{ inventory_hostname }}.cfg"
''', "note": "Read-only and safe: it only saves a copy. Keep the saved configs private (they can hold passwords and keys). Change the module for other vendors."},
    {"id": "gitignore", "title": ".gitignore for IaC folders", "language": "text", "text": '''# Terraform
.terraform/
*.tfstate
*.tfstate.*
*.tfvars
crash.log

# Secrets and exports
.env
*.pem
*.key
vault-pass.txt
config-backups/
''', "note": "State files and variable files can contain secrets. Keep them out of Git."},
    {"id": "change-plan", "title": "Change plan (fill in before any real change)", "language": "text", "text": '''CHANGE PLAN
Client:
Date and window agreed:
Written approval from (name, how):
What will change (systems, settings):
Why:
Backup or snapshot taken (what, where, tested?):
Preview run (plan or --check) reviewed? Result:
Steps:
1.
2.
Rollback if it goes wrong (exact steps, time needed):
How we confirm it worked:
Who to call if it breaks:
After: what changed, what was learned, files saved where:
''', "note": "Fill in before touching a client's systems. Keep a copy with the job notes (no passwords)."},
]

CHECKLIST = [
    "Written approval from the client that names the systems, the changes and the time window.",
    "Confirm who owns the cloud account. Work in the client's account with your own named user, never a shared admin login.",
    "Use least privilege: a role that can do only this job. Turn on multi-factor sign-in.",
    "Take a backup or snapshot first and know how to restore it.",
    "Run the preview first (terraform plan, ansible --check, dry run) and read every line it says it will change or destroy.",
    "Test on a practice or non-production copy when one exists.",
    "Change one small thing at a time. Do not apply during business hours unless agreed.",
    "Keep passwords, keys, tokens and state files out of the files and out of Git. Use a secrets manager or environment variables.",
    "Tag everything with the client and an owner so it can be found, billed and removed.",
    "Set a budget alert or cost limit before building cloud resources.",
    "Know the rollback and the stop point. If the preview shows something unexpected, stop.",
    "Check compliance: if health, financial, student or card data is involved, confirm the provider agreement and region. See Settings, Legal and compliance.",
    "Document what you built, where the files are, how to rebuild or remove it, and who now owns it. Hand over credentials through the client's own process.",
    "Remove practice or temporary resources when finished so nothing bills or stays exposed.",
]

LESSON = [
    {"h": "What it is", "p": "Infrastructure as Code means describing servers, networks and settings in text files and letting a tool build them the same way every time, instead of clicking through consoles by hand."},
    {"h": "Why it helps", "p": "Repeatable builds, changes you can review and undo in Git, fast rebuilds after a failure, and a written record of what exists. It also reduces 'someone changed it by hand and nobody knows'."},
    {"h": "Two styles", "p": "Declarative: you describe the end state and the tool works out the steps (Terraform, CloudFormation, Kubernetes). Imperative: you write the steps in order (scripts, some Ansible)."},
    {"h": "It is not only AWS or cloud", "p": "Terraform and OpenTofu cover most clouds plus VMware, Proxmox, DNS, GitHub and identity tools. Ansible configures Linux and Windows machines and network gear. Container files and Kubernetes manifests are IaC too."},
    {"h": "The safe habit", "p": "Preview, read, then apply. Terraform plan and Ansible check mode show what would change before anything does. Never skip the preview on a client's systems."},
    {"h": "State and secrets", "p": "Terraform keeps a state file that can contain secrets. Store it safely, keep it out of Git, and never write passwords or keys in the code."},
]

# ------------------------------------------------------------------ IaC reviewer
RULES = [
    ("high", r"AKIA[0-9A-Z]{16}", "An AWS access key ID is written in the file.", "Remove it, rotate the key now, and use a role or environment variables."),
    ("high", r"-----BEGIN (RSA |EC |OPENSSH |DSA |)PRIVATE KEY-----", "A private key is pasted in the file.", "Remove it, replace the key, and load keys from a secrets store."),
    ("high", r"(?i)\b(password|passwd|secret|token|api[_-]?key|access[_-]?key)\b\s*[:=]\s*[\"']?(?!var\.|\$\{|\{\{|<|REPLACE|changeme\b)[A-Za-z0-9/+_\-!@#$%^&*]{6,}", "A password, token or key looks hard-coded.", "Move it to a variable, vault or secrets manager and rotate it if it was ever shared."),
    ("high", r"(?is)(from_port|port)\s*=\s*(22|3389|3306|5432|1433|445|23|5900|6379|27017)\b.{0,300}?cidr_blocks\s*=\s*\[[^\]]*(0\.0\.0\.0/0|::/0)", "A sensitive port (SSH, RDP, database or file sharing) is open to the whole internet.", "Limit it to your own IP or a VPN range, or use a bastion or the provider's secure shell service."),
    ("high", r"(?i)acl\s*=\s*[\"']public-read(-write)?[\"']", "A storage bucket is set to public.", "Make it private and share with signed links or specific access instead."),
    ("high", r"(?i)block_public_(acls|policy)\s*=\s*false|restrict_public_buckets\s*=\s*false", "Public-access blocking is turned off.", "Turn blocking on unless the bucket is intentionally a public website."),
    ("high", r"(?i)publicly_accessible\s*=\s*true", "A database is reachable from the internet.", "Keep databases private and reach them through the app network or a VPN."),
    ("high", r"(?i)(storage_encrypted|encrypted|enable_encryption)\s*=\s*false", "Encryption is turned off.", "Turn on encryption at rest."),
    ("medium", r"(?i)(validate_certs|verify_ssl|ssl_verify|insecure)\s*[:=]\s*(no|false|true)\b", "Certificate checking may be disabled.", "Leave certificate validation on."),
    ("medium", r"(?i)(curl|wget)[^\n|]*\|\s*(sudo\s+)?(ba)?sh", "A script is downloaded and run without being read.", "Download it, read it, pin a checksum, then run it."),
    ("medium", r"(?i)(chmod\s+(-R\s+)?777|mode:\s*[\"']?0?777)", "Files are made world-writable.", "Use the narrowest permissions that work, such as 0640 or 0750."),
    ("medium", r"(?i)force_destroy\s*=\s*true|rm\s+-rf\s+/", "A setting can delete data without a safety stop.", "Remove it, or protect important resources with prevent_destroy."),
    ("medium", r"(?i)ignore_errors\s*:\s*(yes|true)", "Errors are ignored, so a failed step can look like success.", "Handle the specific error instead of ignoring all of them."),
    ("medium", r"(?i)\bimage\s*[:=]\s*[\"']?[\w./-]+:latest\b|state\s*:\s*latest", "An unpinned 'latest' version can change without notice.", "Pin a version so rebuilds are repeatable."),
    ("low", r"(?i)ingress[^}]{0,200}cidr_blocks\s*=\s*\[[^\]]*0\.0\.0\.0/0", "Something is open to the whole internet. Fine for a public website port, risky for anything else.", "Confirm the port is meant to be public."),
]


def review(text: str) -> dict:
    text = text or ""
    if len(text.strip()) < 10:
        raise CloudError("Paste some Terraform, Ansible, CloudFormation or similar text to review.")
    if len(text) > MAX_TEXT:
        raise CloudError(f"Keep it under {MAX_TEXT:,} characters. Paste one file at a time.")
    finds, seen = [], set()
    for sev, pat, msg, fix in RULES:
        for m in re.finditer(pat, text):
            line = text.count("\n", 0, m.start()) + 1
            if (msg, line) in seen:
                continue
            seen.add((msg, line))
            snippet = text.splitlines()[line - 1].strip()[:90]
            if re.search(r"(?i)password|secret|token|key", snippet):
                snippet = re.sub(r"([:=]\s*[\"']?)[^\s\"']{4,}", r"\1[hidden]", snippet)
            finds.append({"severity": sev, "line": line, "problem": msg, "fix": fix, "snippet": snippet})
    notes = []
    low = text.lower()
    if "required_providers" in low and not re.search(r"version\s*=", text):
        notes.append("Pin provider versions so a rebuild next year behaves the same.")
    if ("resource \"" in low or "aws_" in low) and "tags" not in low:
        notes.append("No tags found. Tag resources with the client and an owner so they can be found, billed and removed.")
    if "terraform" in low:
        notes.append("Keep .tfstate and .tfvars files out of Git, and run terraform plan before apply.")
    if not finds:
        notes.insert(0, "No problems found by these simple checks. That does not mean it is safe: run the preview and read it.")
    order = {"high": 0, "medium": 1, "low": 2}
    finds.sort(key=lambda f: (order[f["severity"]], f["line"]))
    return {"findings": finds[:40], "counts": {s: sum(1 for f in finds if f["severity"] == s) for s in order}, "notes": notes,
            "caveat": "A short list of common mistakes found by pattern matching. It cannot understand your whole setup. Always run the tool's preview and have a second look before changing a client's systems."}


# ------------------------------------------------------------------ quiz (answers stay here)
QUIZ = [
    ("What does IaaS give you?", ["Finished software to sign in to", "Rented virtual servers and networks you manage yourself", "A managed database", "Only code hosting"], 1, "IaaS rents the building blocks. You manage the operating system and everything above it."),
    ("Which model fits 'staff just need email and office apps'?", ["IaaS", "SaaS", "FaaS", "CaaS"], 1, "SaaS such as Microsoft 365 or Google Workspace is finished software. Your job is setup, security and support."),
    ("With SaaS, who is still responsible for who can sign in and what data is in it?", ["Only the provider", "Nobody", "You and the client", "The internet provider"], 2, "Shared responsibility: the vendor secures the platform, you control accounts, access and data."),
    ("What is the safest first step before changing a client's systems with Terraform or Ansible?", ["Apply and see", "Run the preview (plan or --check) and read it", "Delete the old setup", "Skip the backup"], 1, "Preview, read, then apply, after a backup and written approval."),
    ("A database as a service is set to publicly_accessible = true. What is the concern?", ["It will be slow", "It is reachable from the whole internet", "It will not back up", "Nothing"], 1, "Keep managed databases private and reach them through the app network or a VPN."),
    ("Which belongs in Git?", ["Terraform state with real values", "Passwords in the code", "Your .tf files with secrets removed", "Private keys"], 2, "Keep code in Git. Keep state, passwords and keys out."),
    ("What is serverless (FaaS) good for?", ["Small on-demand jobs like a nightly report", "Running a desktop", "Replacing all servers always", "Storing backups"], 0, "Short event-driven functions where you pay only when they run."),
    ("A client handles patient data and wants a cloud service. What do you check?", ["Only the price", "Whether the provider will sign a HIPAA business associate agreement", "The logo", "Nothing"], 1, "Health data needs the right agreements and safeguards before it goes in a cloud service."),
]


def quiz() -> dict:
    return {"questions": [{"id": i, "q": q, "options": o} for i, (q, o, _, _) in enumerate(QUIZ)], "pass_pct": 80}


def grade(answers: dict) -> dict:
    res, ok = [], 0
    for i, (q, o, a, why) in enumerate(QUIZ):
        pick_ = answers.get(str(i), answers.get(i))
        good = pick_ == a
        ok += good
        res.append({"id": i, "correct": good, "right": a, "why": why})
    pct = round(100 * ok / len(QUIZ))
    return {"score": ok, "total": len(QUIZ), "pct": pct, "passed": pct >= 80, "results": res}
