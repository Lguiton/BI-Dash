# Dashboard audit: what each field has, and what advanced work is still missing

Audited 2026-10-16 against what a working professional in each field is expected to know. "Have" is from the manuals, tabs and labs in the app. Build order is by what earns you money first (IT, network, security and BI work), then the rest.

## Priority 1: fields you sell
### IT Support
Have: helpdesk, fix log, repair guides (phones, laptops, appliances, board level), inventory, backup lab, event logs, checklists, capacity and RAID, A+ study, vSphere, infrastructure labs (GPO, LDIF, RBAC, load balancing), ticket coach, cloud and as-a-service lab.
Missing (advanced): Microsoft 365 and Entra ID admin (user lifecycle, licensing, Conditional Access, MFA rollout, shared mailboxes), Intune and Autopilot (MDM, device compliance), PowerShell and Bash automation lab, imaging and deployment, Windows boot and BSOD analysis (Sysinternals, memory dump basics), malware removal playbook, data recovery workflow, email authentication (SPF, DKIM, DMARC checker), Mac support (Apple Silicon, MDM, FileVault), Linux administration, printer and scanner and VoIP troubleshooting, patch management policy, ITIL (incident, problem, change, SLA, CMDB), onboarding and offboarding runbooks, RMM and remote support practice, vendor RMA and warranty tracking.

### Network
Have: subnet and VLSM, config review, packet capture, DNS and reachability, config generators, design, simulators, DHCP and DNS server, calculators.
Missing (advanced): routing protocol labs (static, OSPF, BGP basics, route redistribution), switching depth (STP tuning, LACP, port security, QoS), wireless design (channel planning, site survey method, WPA3 and 802.1X), firewall rule review, NAT and VPN design (IPsec, WireGuard), IPv6 addressing plan, SNMP, NetFlow and syslog monitoring, PoE budget and structured cabling and fiber, network automation (Netmiko, Ansible, NETCONF), SD-WAN and zero-trust access, troubleshooting by layer with TCP analysis (retransmits, windowing), CCNA and Network+ pathways.

### Security
Have: self-audit, logs, web checks, local ports, hardening, honeypot, NIST CSF, crypto, incidents, Mac and Linux audit, phishing and breach, legal and compliance library.
Missing (advanced): vulnerability management (CVSS, scanning, patch prioritization), risk assessment (qualitative and ALE), penetration-test methodology with authorization and scope templates and OWASP Top 10 labs, digital forensics (chain of custody, timelines, disk and memory basics), SIEM and detection engineering (Sigma rules, MITRE ATT&CK mapping), IDS and IPS rule reading (Suricata), identity and privileged access, cloud security posture (IAM misconfig, storage exposure), application security (dependency scanning, secure coding), malware analysis basics, security awareness and phishing simulation, compliance assessments (HIPAA security risk analysis, SOC 2 readiness, PCI SAQ), business continuity and disaster recovery, Security+ and CySA+ pathways.

### Analyst (BI)
Have: framing, tables, SQL and pandas cookbook, data trust, KPIs, charts, BI building blocks, reporting, monitoring, survey checks.
Missing (advanced): window functions and advanced SQL lab, cohort and retention and funnel analysis, dashboard design and data storytelling review, forecasting with error bars, dimensional modeling for reports, Power BI DAX and Tableau equivalents, finance analytics (margin, cash flow, unit economics) beyond the CFO persona, stakeholder interviews and requirements for dashboards, report QA checklist, data glossary and metric governance, self-service rollout.

## Priority 2: engineering and delivery
### Computer Engineer
Have: number systems, logic, circuits, cache, CPU sim, vehicle CAN and EV, electrical and HVAC, computer science, PC build, board-level repair, robotics.
Missing (advanced): digital design with Verilog and VHDL and finite state machines and timing (setup and hold), FPGA flow, embedded C (interrupts, timers, I2C, SPI, UART, RTOS), advanced architecture (pipeline hazards, branch prediction, out-of-order, virtual memory and TLB), PCB design (KiCad flow, impedance, EMI, layout rules), oscilloscope and logic analyzer use, analog design (op-amps, filters, AC and transient analysis), power electronics (buck and boost), motor control, control theory beyond PID (Bode, state space), datasheet reading, firmware security (secure boot), reliability (MTBF, derating), standards and testing (EMC, UL).

### Full-stack Engineer
Have: code workbench, generate code, API map and tester, scaffold, codebase, stack config, software engineering.
Missing (advanced): authentication (OAuth, OIDC, JWT, sessions), testing pyramid (unit, integration, end to end), CI/CD pipeline builder, containers and Docker, database migrations and ORMs, caching and performance (indexes, Core Web Vitals), accessibility audit, OWASP secure coding, observability (logs, metrics, tracing), API design (OpenAPI, GraphQL, versioning), queues and background jobs, system design exercises, git workflows and code review.

### Project Manager
Have: board, prioritisation, sprints, flow, schedule, earned value, risks, OKRs, product analytics, time, what-if, calendar, automations.
Missing (advanced): Monte Carlo schedule and cost risk, RACI and stakeholder mapping, roadmapping and product discovery, resource leveling, change management, procurement and contracts, PMBOK process groups and PMP pathway, retrospectives and facilitation, status report and executive summary generator, pricing and go-to-market, agile scaling.

### Systems Analyst
Have: problem statement, requirements, data dictionary, process analysis, sizing, cost-benefit, TELOS, traceability, integration audit, documentation audit.
Missing (advanced): UML (use case, sequence, activity, class), BPMN, user stories and acceptance criteria generator, UAT and test planning, data migration planning, enterprise architecture (TOGAF-lite), vendor selection scoring, security and privacy requirements, change impact analysis, API and integration design, business case templates.

## Priority 3: data and AI tracks (already deep)
### AI Engineer
Missing: fine-tuning and LoRA, vector databases and retrieval tuning, inference optimization (quantization, batching, caching), multimodal systems, prompt and eval versioning, AI red teaming, guardrail design, LLMOps monitoring.
### ML Engineer
Missing: deep learning architectures (CNN, RNN, transformers), computer vision and NLP projects, recommender systems, advanced time series, model explainability (SHAP), hyperparameter optimization, model serving and monitoring, reinforcement learning basics, experiment tracking at scale.
### Data Engineer
Missing: streaming (Kafka, Flink), distributed processing (Spark), orchestration (Airflow style DAGs), lakehouse table formats (Iceberg, Delta), data contracts, data observability and cost control.
### Data Scientist
Missing: Bayesian methods, causal inference and experiment design (power, A/B), survival analysis, optimization and operations research, geospatial analysis, fairness and ethics audits.

## Suggested build order
Batch 1: IT Support. Batch 2: Security. Batch 3: Network. Batch 4: Analyst. Then Computer Engineer depth, Full-stack, PM and Systems Analyst, then the data and AI tracks. Each batch adds labs and calculators, guides, quizzes, agent tools and tests, and is tested before the next one.


## Status (zip 53)
All batches in this list are built: IT Support, Security, Network, Analyst, Computer Engineer, Full-stack, PM, Systems Analyst, AI, ML, Data Engineer and Data Scientist. Items that still need a human or other software: quizzes for the new labs, and anything that depends on live data from a client's systems.
