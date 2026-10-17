"""Lets each field's AI agent use the same calculators as that dashboard's Tools tab, and read the job you have pinned.

One tool ("use_tool") with a short list of names per field keeps the prompt small. Everything here is local, pure computation on the numbers or
pasted text the agent supplies: nothing touches another computer (no DNS, port or website checks), nothing is saved, nothing is sent to a client.
A job is read-only. Practice kit files are included for practice jobs, never the answer key."""
from __future__ import annotations

import json

from app.services import (ai_eng_lab, bi_calc, clients, cpe_sim, cs_lab, elec_calc, dax_lab, data_calc, data_dbt, data_flow, experience, inference_lab, itlab, jobfield, ml_build,
                          ml_concepts, netlab, nn_lab, practice_kits, seclogs, sysanalysis, veh_decode, workspaces)

MAX_OUT = 3500
JOB_CHARS = 6000


def _t(**props) -> dict:
    return {"type": "object", "properties": props}


# name -> (one-line help shown to the model, handler(args) -> dict). Help lists the argument names so the model needs no other schema.
NETWORK = {
    "fiber_budget": ("length_km, wavelength?, connectors?, splices?, tx_dbm?, rx_sensitivity_dbm?", lambda a: __import__("app.services.net_pro", fromlist=["x"]).calc("fiber", dict(a))),
    "poe_budget": ("switch_watts, devices = lines of: name, watts or class (af/at/bt3/bt4), qty", lambda a: __import__("app.services.net_pro", fromlist=["x"]).calc("poe", dict(a))),
    "ipv6_plan": ("prefix, subnet_prefix?, count?", lambda a: __import__("app.services.net_pro", fromlist=["x"]).calc("ipv6", dict(a))),
    "firewall_review": ("text = pasted firewall or access list rules", lambda a: __import__("app.services.net_pro", fromlist=["x"]).firewall_review(str(a["text"]))),
    "tcp_limit": ("rtt_ms, loss_pct, mss_bytes?", lambda a: __import__("app.services.net_pro", fromlist=["x"]).calc("tcp", dict(a))),
    "subnet": ("cidr", lambda a: netlab.subnet(str(a["cidr"]))),
    "vlsm": ("base, needs=[{name, hosts}]", lambda a: netlab.vlsm(str(a["base"]), a["needs"])),
    "summarize": ("cidrs=[...]", lambda a: netlab.summarize(list(a["cidrs"]))),
    "overlaps": ("cidrs=[...]", lambda a: netlab.overlaps(list(a["cidrs"]))),
    "contains": ("cidr, ip", lambda a: netlab.contains(str(a["cidr"]), str(a["ip"]))),
    "split": ("cidr, new_prefix", lambda a: netlab.split(str(a["cidr"]), int(a["new_prefix"]))),
    "transfer_time": ("size_gb, mbps, efficiency_pct?", lambda a: netlab.transfer_time(float(a["size_gb"]), float(a["mbps"]), float(a.get("efficiency_pct", 85)))),
    "bdp": ("mbps, rtt_ms, window_kb?", lambda a: netlab.bdp(float(a["mbps"]), float(a["rtt_ms"]), float(a.get("window_kb", 64)))),
    "config_audit": ("text = pasted router or switch config", lambda a: netlab.audit_config(str(a["text"]))),
    "capture_read": ("text = pasted packet-capture text", lambda a: netlab.read_capture(str(a["text"]))),
    "iac_review": ("text = pasted Terraform, Ansible or similar", lambda a: _iac_review(a)),
}

def _compliance(a):
    """Look up privacy and security rules (HIPAA, GDPR, CCPA, FTC, Nevada and more) from the built-in library."""
    from app.services import compliance
    q = str(a.get("q") or "").strip()
    if len(q) < 2:
        raise ValueError("Give a topic or law, like HIPAA, breach notice or email marketing.")
    r = compliance.search(q, 3)
    top = compliance.get(r["results"][0]["id"]) if r["results"] else None
    out = {"matches": r["results"], "glossary": r.get("glossary", [])}
    if top:
        out["best"] = {k: top[k] for k in ("name", "applies", "duties", "penalties", "freelancer", "links")}
    out["note"] = compliance.NOTE
    return out


def _iac_review(a):
    """Check pasted Terraform, Ansible or similar text for common risky settings (open ports, hard-coded secrets, public storage)."""
    from app.services import cloud_lab
    return cloud_lab.review(str(a.get("text") or ""))


def _cloud_pick(a):
    """Suggest as-a-service models (SaaS, IaaS, PaaS, DBaaS, FaaS and more) for a described need, with what to ask first."""
    from app.services import cloud_lab
    return cloud_lab.pick(str(a.get("need") or a.get("q") or ""))


def _pc_check(a):
    """Check PC parts for compatibility (socket, RAM type, case size, GPU and cooler clearance, power supply)."""
    from app.services import pc_build
    return pc_build.check(dict(a))


def _pc_psu(a):
    from app.services import pc_build
    return pc_build.recommend_psu(a.get("cpu_w"), a.get("gpu_w"), int(a.get("ssd", 1)), int(a.get("hdd", 0)), int(a.get("fans", 4)), int(a.get("sticks", 2)))


def _pc_nopost(a):
    from app.services import pc_build
    return pc_build.diagnose(str(a.get("symptom") or a.get("q") or ""))


def _robot(a):
    """Robotics calculators: drive, gearbox, battery, servo, pid, arm_fk, arm_ik, diff_drive, encoder, ultrasonic."""
    from app.services import robotics
    return robotics.calc(str(a.get("kind") or ""), dict(a.get("args") or {}))


def _repair_guide(a):
    """Search the built-in repair guides (the How to repair tab) and return the best match with steps, tools, safety and when to escalate."""
    from app.services import it_repair, repair_search
    q = str(a.get("q") or a.get("symptom") or "").strip()
    if len(q) < 2:
        raise ValueError("Give a symptom to search, like 'no power' or 'beeps no display'.")
    hits = repair_search.search(q[:200], 3)["results"]
    if not hits:
        return {"matches": [], "note": "No guide matched. Use the six-step repair method: identify, theory, test, plan, fix and verify, then document."}
    by = {g["id"]: g for g in it_repair.sheet()["guides"]}
    top = by.get(hits[0]["id"])
    out = {"matches": [{"id": h["id"], "title": h["title"], "area": h["area"]} for h in hits]}
    if top:
        out["best"] = {k: top.get(k) for k in ("title", "symptoms", "causes", "steps", "tools", "safety", "escalate")}
    out["note"] = "Built-in guide. Walk the user through one step at a time, state the safety note before risky steps, and have them verify before calling it fixed."
    return out




IT = {
    "email_auth": ("spf, dmarc, dkim = the TXT records pasted (any may be blank)", lambda a: __import__("app.services.it_admin", fromlist=["x"]).email_auth(str(a.get("domain", "")), str(a.get("spf", "")), str(a.get("dmarc", "")), str(a.get("dkim", "")))),
    "script_review": ("text = a PowerShell or shell script to check for risky commands", lambda a: __import__("app.services.it_admin", fromlist=["x"]).review_script(str(a["text"]))),
    "stop_code": ("code = a Windows stop code or part of it, e.g. IRQL_NOT_LESS_OR_EQUAL", lambda a: __import__("app.services.it_admin", fromlist=["x"]).stop_code(str(a["code"]))),
    "capacity": ("used_gb, total_gb, growth_gb_per_month, warn_pct?", lambda a: itlab.capacity(float(a["used_gb"]), float(a["total_gb"]), float(a["growth_gb_per_month"]), float(a.get("warn_pct", 80)))),
    "availability": ("pct (e.g. 99.9)", lambda a: itlab.availability(float(a["pct"]))),
    "raid": ("level, disks, size_tb", lambda a: itlab.raid(str(a["level"]), int(a["disks"]), float(a["size_tb"]))),
    "read_events": ("text = pasted Windows/system event log text", lambda a: itlab.read_events(str(a["text"]))),
    "repair_guide": ("q = symptom, e.g. no power, beeps no display, overheating", _repair_guide),
    "pc_check": ("cpu_socket?, board_socket?, board_ram?, ram_type?, board_form?, case_form?, gpu_len_mm?, case_gpu_mm?, psu_w?", _pc_check),
    "pc_psu": ("cpu_w, gpu_w, ssd?, hdd?, fans?, sticks?", _pc_psu),
    "pc_nopost": ("symptom = what the PC does at power on", _pc_nopost),
    "compliance": ("q = law or topic, e.g. HIPAA, PII, breach notice, email marketing", _compliance),
    "iac_review": ("text = pasted Terraform, Ansible, CloudFormation or similar", _iac_review),
    "cloud_pick": ("need = what the client needs, e.g. email for 8 people, database for a booking app", _cloud_pick),
}
SECURITY = {
    "cvss": ("vector = CVSS 3.1 base vector like AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H", lambda a: __import__("app.services.sec_pro", fromlist=["x"]).cvss(str(a.get("vector", "")))),
    "risk_ale": ("asset_value, exposure_pct, incidents_per_year, control_cost_per_year?, risk_reduction_pct?", lambda a: __import__("app.services.sec_pro", fromlist=["x"]).ale(a["asset_value"], a["exposure_pct"], a["incidents_per_year"], a.get("control_cost_per_year", 0), a.get("risk_reduction_pct", 0))),
    "rule_explain": ("rule = a Suricata or Snort rule to explain", lambda a: __import__("app.services.sec_pro", fromlist=["x"]).explain_rule(str(a["rule"]))),
    "analyze_logs": ("text = pasted log lines, year?", lambda a: seclogs.analyze(str(a["text"]), a.get("year"))),
    "search_logs": ("text, query?, level?, ip?", lambda a: seclogs.search(str(a["text"]), str(a.get("query", "")), str(a.get("level", "")), str(a.get("ip", "")), 40, a.get("year"))),
    "compliance": ("q = law or topic, e.g. HIPAA, breach notice, CFAA scope", _compliance),
    "iac_review": ("text = pasted Terraform, Ansible, CloudFormation or similar", _iac_review),
    "cloud_pick": ("need = what the client needs, e.g. email for 8 people, database for a booking app", _cloud_pick),
}
BI = {
    "forecast_range": ("values = numbers oldest first (pasted), season?, horizon?, width?", lambda a: __import__("app.services.analyst_pro", fromlist=["x"]).forecast(a.get("values") or a.get("text") or "", a.get("season", 12), a.get("horizon", 3), a.get("width", 2))),
    "cohort": ("text = lines of: customer_id, date", lambda a: __import__("app.services.analyst_pro", fromlist=["x"]).cohort(str(a["text"]))),
    "funnel": ("text = lines of: step name, count", lambda a: __import__("app.services.analyst_pro", fromlist=["x"]).funnel(str(a["text"]))),
    "unit_economics": ("monthly_revenue_per_customer, gross_margin_pct, monthly_churn_pct, cac", lambda a: __import__("app.services.analyst_pro", fromlist=["x"]).unit_econ(a["monthly_revenue_per_customer"], a["gross_margin_pct"], a["monthly_churn_pct"], a["cac"])),
    "breakeven": ("fixed_costs, price, variable_cost, target_profit?", lambda a: __import__("app.services.analyst_pro", fromlist=["x"]).breakeven(a["fixed_costs"], a["price"], a["variable_cost"], a.get("target_profit", 0))),
    "ab_test": ("a_visitors, a_conversions, b_visitors, b_conversions", lambda a: __import__("app.services.analyst_pro", fromlist=["x"]).ab_test(a["a_visitors"], a["a_conversions"], a["b_visitors"], a["b_conversions"])),
    "forecast": ("values=[numbers, 8+], horizon?, holdout?, season?", lambda a: bi_calc.forecast_compare(a["values"], int(a.get("horizon", 6)), a.get("holdout"), int(a.get("season", 0)), a.get("alpha"))),
    "variance": ("rows=[{name, budget, actual}], threshold_pct?", lambda a: bi_calc.variance(a["rows"], float(a.get("threshold_pct", 10)))),
    "profit_scenario": ("price, volume, unit_cost, fixed_cost?, shock_pct?", lambda a: bi_calc.scenario(float(a["price"]), float(a["volume"]), float(a["unit_cost"]), float(a.get("fixed_cost", 0)), None, float(a.get("shock_pct", 10)))),
    "dist_fit": ("values=[numbers]", lambda a: bi_calc.dist_fit(a["values"])),
    "dax": ("measures=[{name, formula}], group_by?, csv_text?", lambda a: dax_lab.run(a["measures"], a.get("group_by") or [], a.get("csv_text"))),
}
def _f(a, k, d=None):
    return float(a[k]) if k in a and a[k] is not None else d


AI = {
    "estimate_tokens": ("text", lambda a: ai_eng_lab.estimate_tokens(str(a["text"]))),
    "prompt_lint": ("text = a prompt to check", lambda a: ai_eng_lab.prompt_lint(str(a["text"]))),
    "context_fit": ("prompt_tokens, window_tokens, output_tokens?, safety_pct?", lambda a: ai_eng_lab.context_fit(int(a["prompt_tokens"]), int(a["window_tokens"]), int(a.get("output_tokens", 1000)), float(a.get("safety_pct", 10)))),
    "chunk_plan": ("doc_tokens, chunk_tokens?, overlap_tokens?, top_k?, queries_per_day?, price_in_per_million?", lambda a: ai_eng_lab.chunk_plan(int(a["doc_tokens"]), int(a.get("chunk_tokens", 300)), int(a.get("overlap_tokens", 40)), int(a.get("top_k", 3)), int(a.get("queries_per_day", 100)), float(a.get("price_in_per_million", 0)))),
    "cost_plan": ("requests_per_day, input_tokens, output_tokens, price_in_per_million, price_out_per_million, cache_hit_pct?, cheap_share_pct?, cheap_price_in?, cheap_price_out?, days?",
                  lambda a: ai_eng_lab.cost_plan(int(a["requests_per_day"]), int(a["input_tokens"]), int(a["output_tokens"]), float(a["price_in_per_million"]), float(a["price_out_per_million"]), float(a.get("cache_hit_pct", 0)), float(a.get("cache_discount_pct", 90)), float(a.get("cheap_share_pct", 0)), float(a.get("cheap_price_in", 0)), float(a.get("cheap_price_out", 0)), int(a.get("days", 30)))),
    "tool_safety": ("tools=[{name, ...}] the agent's proposed tools", lambda a: ai_eng_lab.tool_safety(a["tools"])),
    "inference_fit": ("params_b, precision?, gpu?, n_gpus?", lambda a: inference_lab.fit(a["params_b"], str(a.get("precision", "fp16")), str(a.get("gpu", "h100")), a.get("n_gpus", 1))),
}
ML = {
    "drift": ("reference = numbers or labels as text, current = same, kind? numeric|category", lambda a: ml_build.drift(str(a["reference"]), str(a["current"]), str(a.get("kind", "numeric")))),
    "perf_drift": ("rows = text lines of model performance over time", lambda a: ml_build.perf_drift(str(a["rows"]))),
    "automl": ("csv_text, target, max_features?", lambda a: ml_build.automl(str(a["csv_text"]), str(a["target"]), int(a.get("max_features", 6)))),
    "split_sizes": ("n, train?, val?, test?", lambda a: ml_concepts.split_sizes(int(a["n"]), int(a.get("train", 60)), int(a.get("val", 20)), int(a.get("test", 20)))),
    "param_count": ("layers=[sizes]", lambda a: nn_lab.parameter_count(a["layers"])),
    "forecast": BI["forecast"],
    "dist_fit": BI["dist_fit"],
}
ENGINEERING = {
    "dbt": ("seeds = text, models = text, tests?", lambda a: data_dbt.run(str(a["seeds"]), str(a["models"]), str(a.get("tests", "")))),
    "formulas": ("cells = text of spreadsheet-style cells", lambda a: data_calc.evaluate(str(a["cells"]))),
    "dag": ("tasks = text of tasks and dependencies, workers?", lambda a: data_flow.dag(str(a["tasks"]), int(a.get("workers", 2)))),
    "cron": ("expr, start?, count?", lambda a: data_flow.cron(str(a["expr"]), str(a.get("start", "")), int(a.get("count", 5)))),
    "capacity": ("load, cap, growth_pct, headroom_pct?", lambda a: sysanalysis.capacity(float(a["load"]), float(a["cap"]), float(a["growth_pct"]), float(a.get("headroom_pct", 80)))),
}
SYSANALYST = {
    "queue": ("lam = arrivals per time, mu = service rate per server, servers, target_wait?", lambda a: sysanalysis.queue(float(a["lam"]), float(a["mu"]), int(a.get("servers", 1)), _f(a, "target_wait"))),
    "availability": ("slo, window_days?, used_minutes?, parts=[pct]?, mode? serial|parallel", lambda a: sysanalysis.availability(float(a.get("slo", 99.9)), float(a.get("window_days", 30)), float(a.get("used_minutes", 0)), a.get("parts"), str(a.get("mode", "serial")))),
    "cost_benefit": ("initial, annual_benefit, annual_cost, years, rate_pct", lambda a: sysanalysis.cost_benefit(float(a["initial"]), float(a["annual_benefit"]), float(a.get("annual_cost", 0)), int(a["years"]), float(a.get("rate_pct", 10)))),
    "capacity": ("load, cap, growth_pct, headroom_pct?", lambda a: sysanalysis.capacity(float(a["load"]), float(a["cap"]), float(a["growth_pct"]), float(a.get("headroom_pct", 80)))),
}
CPE = {
    "logic_circuit": ("netlist, stimulus, cycles?", lambda a: cpe_sim.logic_circuit(str(a["netlist"]), str(a["stimulus"]), int(a.get("cycles", 8)))),
    "cpu_run": ("source = tiny-CPU assembly, max_steps?", lambda a: cpe_sim.cpu_run(str(a["source"]), int(a.get("max_steps", 500)))),
    "circuit_dc": ("net = circuit netlist text", lambda a: cpe_sim.circuit_dc(str(a["net"]))),
    "cache_trace": ("trace, cache_bytes, block_bytes, ways, policy?", lambda a: cpe_sim.cache_trace(str(a["trace"]), int(a["cache_bytes"]), int(a["block_bytes"]), int(a["ways"]), str(a.get("policy", "LRU")))),
    "can_signals": ("data_hex, signals", lambda a: veh_decode.can_signals(str(a["data_hex"]), str(a["signals"]))),
    "j1939": ("can_id_hex, data_hex?", lambda a: veh_decode.j1939(str(a["can_id_hex"]), str(a.get("data_hex", "")))),
    "dtc": ("code e.g. P0301", lambda a: veh_decode.dtc(str(a["code"]))),
    "obd_pid": ("pid, data_hex", lambda a: veh_decode.obd_pid(str(a["pid"]), str(a["data_hex"]))),
    "repair_guide": ("q = symptom, e.g. no power, no display, battery not charging, drive clicking", _repair_guide),
    "pc_check": ("cpu_socket?, board_socket?, board_ram?, ram_type?, board_form?, case_form?, gpu_len_mm?, case_gpu_mm?, cooler_mm?, case_cooler_mm?, cpu_tdp?, gpu_tdp?, psu_w?", _pc_check),
    "pc_psu": ("cpu_w, gpu_w, ssd?, hdd?, fans?, sticks?", _pc_psu),
    "pc_nopost": ("symptom = what the PC does at power on", _pc_nopost),
    "robot_calc": ("kind = drive|gearbox|battery|servo|pid|arm_fk|arm_ik|diff_drive|encoder|ultrasonic, args = numbers for it", _robot),
    "voltage_drop": ("amps, length_ft (one way), awg?, volts?", lambda a: elec_calc.voltage_drop(a["amps"], a["length_ft"], a.get("awg", 12), a.get("volts", 120))),
    "circuit_load": ("volts?, breaker_amps, loads = lines 'name, watts', continuous?", lambda a: elec_calc.circuit_load(a.get("volts", 120), a["breaker_amps"], a["loads"], bool(a.get("continuous")))),
    "energy_cost": ("watts, hours_per_day, rate_per_kwh?, days?", lambda a: elec_calc.energy_cost(a["watts"], a["hours_per_day"], a.get("rate_per_kwh", 0.13), a.get("days", 30))),
    "hvac_size": ("sqft, ceiling_ft?, sun?, insulation?, people?, kitchen?", lambda a: elec_calc.hvac_size(a["sqft"], a.get("ceiling_ft", 8), a.get("sun", "average"), a.get("insulation", "average"), a.get("people", 2), bool(a.get("kitchen")))),
    "ohm": ("give exactly two of volts, amps, ohms, watts", lambda a: elec_calc.ohm(a.get("volts"), a.get("amps"), a.get("ohms"), a.get("watts"))),
    "delta_t": ("supply_f, return_f (AC air temperature split)", lambda a: elec_calc.delta_t(a["supply_f"], a["return_f"])),
    "big_o": ("code = pasted Python (or other) code; estimates Big-O without running it", lambda a: cs_lab.complexity(str(a["code"]))),
    "sort_steps": ("algorithm = bubble|insertion|selection|merge|quick, data = numbers", lambda a: cs_lab.sort_steps(str(a["algorithm"]), a["data"])),
    "search_steps": ("algorithm = linear|binary, data = numbers, target", lambda a: cs_lab.search_steps(str(a["algorithm"]), a["data"], a["target"])),
}


def _pm_overview(a):
    from app.services import pm
    return pm.overview(None)


def _pm_analytics(a):
    from app.services import pm
    return pm.product_analytics()


def _fs_tables(a):
    from app.services import fullstack
    return {"tables": fullstack.scaffold_tables()}


def _fs_scaffold(a):
    from app.services import fullstack
    return fullstack.scaffold(str(a["table"]), bool(a.get("with_ui", True)))


def _fs_stack(a):
    from app.services import fullstack
    return fullstack.stack()


def _fs_codebase(a):
    from app.services import fullstack
    return fullstack.codebase()


PM = {"pm_overview": ("(no args) the project board summary, read-only", _pm_overview), "pm_analytics": ("(no args) product analytics, read-only", _pm_analytics)}
FULLSTACK = {
    "scaffold_tables": ("(no args) tables you can scaffold", _fs_tables),
    "scaffold": ("table, with_ui? generates API and screen code as text; nothing is written to disk", _fs_scaffold),
    "stack": ("(no args) the stack and settings summary", _fs_stack),
    "codebase": ("(no args) size and layout of this project's code", _fs_codebase),
}
BY_TRACK = {"ai": AI, "ml": ML, "engineering": ENGINEERING, "sysanalyst": SYSANALYST, "cpe": CPE, "pm": PM, "fullstack": FULLSTACK, "network": NETWORK, "itsupport": IT, "security": SECURITY, "analyst": BI, "scientist": BI}
TITLE = {"ai": "AI engineering tools", "ml": "ML tools", "engineering": "data engineering tools", "sysanalyst": "systems analysis calculators", "cpe": "computer engineering simulators", "pm": "project board views", "fullstack": "full-stack tools", "network": "Networking tools", "itsupport": "IT tools", "security": "Security log tools", "analyst": "BI toolkit", "scientist": "BI toolkit"}


def has_tools(track: str) -> bool:
    return track in BY_TRACK


def tool_def(track: str) -> dict:
    reg = BY_TRACK[track]
    listing = "; ".join(f"{k}({v[0]})" for k, v in reg.items())
    return {"name": "use_tool",
            "description": f"Run one of this dashboard's {TITLE[track]} for the user, exactly as its Tools tab does. Local calculation only; nothing is saved or sent. Tools and their args: {listing}. "
                           "Use it instead of doing this arithmetic yourself, and quote the result.",
            "input_schema": {"type": "object", "properties": {"tool": {"type": "string", "enum": list(reg)}, "args": {"type": "object"}}, "required": ["tool", "args"], "additionalProperties": False}}


def run_tool(track: str, args: dict) -> tuple[str, bool]:
    reg = BY_TRACK.get(track)
    if not reg:
        return "This agent has no dashboard tools.", True
    name = str((args or {}).get("tool", ""))
    if name not in reg:
        return f"Unknown tool '{name}'. Use one of: {', '.join(reg)}.", True
    try:
        out = reg[name][1]((args or {}).get("args") or {})
    except KeyError as e:
        return f"Missing argument {e}. {name} needs: {reg[name][0]}.", True
    except Exception as e:  # noqa: BLE001 - a bad argument or a tool's own validation message must come back as text, not crash the chat
        return f"{name} could not run: {getattr(e, 'message', None) or e}", True
    s = json.dumps(out, default=str)
    return (s if len(s) <= MAX_OUT else s[:MAX_OUT] + " ...(cut)"), False


# ------------------------------------------------------------------ the pinned job
TOOL_JOB = {"name": "get_job", "description": "Read the job the user has open: title, field, status, steps with their notes, and (practice jobs only) the practice files. Read-only. Call it before answering about 'this job' or 'my work'.",
            "input_schema": {"type": "object", "properties": {}, "additionalProperties": False}}


def job_text(jid: int) -> str:
    from app.services import jobpage, worklog
    o = jobpage.overview(int(jid))
    j = o["job"]
    lines = [f"Job: {j['title']} (status {j['status']}; field {(j.get('field_info') or {}).get('label', 'not set')}; {o['hours']} h recorded)"]
    if (j.get("notes") or "").strip():
        lines.append("Notes: " + j["notes"].strip()[:600])
    for it in o["work_items"]:
        manual = [x["text"] for x in it["log"] if not x["text"].startswith(jobpage.SYSTEM_LOG)]
        lines.append(f"- [{it['status_label']}] {it['title']}" + (": " + "; ".join(manual[:4]) if manual else ""))
    if not clients.sample():
        lines.append("(Real job: only the title, steps and your notes are shown here, with client names and secrets removed.)")
    else:
        kit = practice_kits.for_title(j["title"])
        if kit:
            from app.services import workteam
            lines.append(f"Brief: {kit['brief']}")
            for f in kit["files"]:
                ft = workteam.facts(f["text"]) if f["kind"] == "csv" else ""
                lines.append(f"FILE {f['name']}:\n" + ((ft + "\nFirst rows:\n" + "\n".join(f["text"].splitlines()[:20])) if ft else f["text"][:2500]))
    return experience.scrub("\n".join(lines))[:JOB_CHARS]


def job_for_agent(jid) -> tuple[str, bool]:
    if jid is None:
        return "No job is open. Ask the user to pin a job in the job bar.", True
    try:
        return job_text(int(jid)), False
    except Exception:  # noqa: BLE001 - a deleted or unknown job is a message, not a crash
        return "That job could not be found in this workspace.", True


def valid_job(jid) -> bool:
    try:
        return jid is not None and bool(clients.job_totals(int(jid)))
    except Exception:  # noqa: BLE001
        return False


def _attach_prolab() -> None:
    """Every advanced-lab calculator also becomes an agent tool for its field."""
    from app.services import prolab, prolab_all  # noqa: F401
    prolab.attach(BY_TRACK)


_attach_prolab()
