"""Software engineering lab: the SDLC, requirements traceability, versions, testing priorities, architecture choices, production
topology checks, state and class diagrams, and pseudocode to flowchart.

Honest limits
* Advisors are rules of thumb from common practice, not measurements. Every one shows its reasons so you can disagree.
* The availability numbers in the topology check are an illustration from the per-part figure you enter, not a forecast.
* Nothing here builds, deploys or tests your software. It plans, checks and explains.
"""
from __future__ import annotations

import re

MAX_ITEMS = 60


class SeError(Exception):
    pass


def _list(v, name, max_items=MAX_ITEMS):
    if not isinstance(v, list) or not v or len(v) > max_items:
        raise SeError(f"{name}: give between 1 and {max_items} items.")
    return v


def _id(v, what):
    s = str(v or "").strip()[:60]
    if not s:
        raise SeError(f"{what} needs a name or id.")
    return s


# ---------------------------------------------------------------- versions
_V = re.compile(r"^v?(\d+(?:\.\d+){0,3})(?:-([0-9A-Za-z.-]+))?(?:\+([0-9A-Za-z.-]+))?$")


def parse_version(s) -> dict:
    m = _V.match(str(s or "").strip())
    if not m:
        raise SeError(f"'{s}' isn't a version like 1.4.2, 2.0.0-rc.1 or 1.4.2+build.7.")
    nums = [int(x) for x in m.group(1).split(".")]
    core = (nums + [0, 0, 0])[:3]
    return {"major": core[0], "minor": core[1], "patch": core[2], "extra": nums[3:], "pre": m.group(2) or "", "build": m.group(3) or "", "parts": len(nums)}


def _pre_key(pre: str):
    if not pre:
        return (1,)
    return (0, tuple((0, int(p), "") if p.isdigit() else (1, 0, p) for p in pre.split(".")))


def _key(v: dict):
    return (v["major"], v["minor"], v["patch"], tuple(v["extra"]), _pre_key(v["pre"]))


def compare(a, b) -> dict:
    va, vb = parse_version(a), parse_version(b)
    ka, kb = _key(va), _key(vb)
    r = (ka > kb) - (ka < kb)
    kind = ""
    if r != 0:
        lo, hi = (va, vb) if r < 0 else (vb, va)
        kind = "major" if hi["major"] != lo["major"] else "minor" if hi["minor"] != lo["minor"] else "patch" if hi["patch"] != lo["patch"] else "pre-release or build"
    meaning = {"major": "A major change: under semantic versioning this is where breaking changes are allowed. Read the release notes and test before upgrading.",
               "minor": "A minor change: new features that should stay backward compatible.", "patch": "A patch: bug fixes only, expected to be safe.",
               "pre-release or build": "Only a pre-release tag or build differs. Pre-releases (alpha, beta, rc) sort BELOW the final release."}.get(kind, "Same version (build metadata after + is ignored when ordering).")
    return {"a": str(a), "b": str(b), "result": r, "text": ("a is older than b" if r < 0 else "a is newer than b" if r > 0 else "a and b are the same version"), "difference": kind or "none", "meaning": meaning}


def bump(v, level) -> dict:
    p = parse_version(v)
    if level not in ("major", "minor", "patch", "prerelease"):
        raise SeError("level must be major, minor, patch or prerelease.")
    M, m, pa = p["major"], p["minor"], p["patch"]
    if level == "major":
        out = f"{M + 1}.0.0"
    elif level == "minor":
        out = f"{M}.{m + 1}.0"
    elif level == "patch":
        out = f"{M}.{m}.{pa + 1}"
    else:
        mm = re.match(r"^(.*?)(\d+)$", p["pre"] or "")
        out = f"{M}.{m}.{pa}-" + (f"{mm.group(1)}{int(mm.group(2)) + 1}" if mm else "rc.1" if not p["pre"] else p["pre"] + ".1")
    return {"from": str(v), "level": level, "to": out, "when": {"major": "You broke something existing users rely on (removed or changed behavior).", "minor": "You added features without breaking anything.",
                                                                   "patch": "You fixed bugs without changing behavior users rely on.", "prerelease": "You are testing a build before the final release."}[level]}


def _atom(v, op, spec) -> bool:
    t = parse_version(spec)
    k, kt = _key({**v, "pre": v["pre"]}), _key(t)
    return {">=": k >= kt, ">": k > kt, "<=": k <= kt, "<": k < kt, "=": k == kt, "": k == kt}[op]


def satisfies(version, spec) -> dict:
    v = parse_version(version)
    s = str(spec or "").strip()
    if not s or len(s) > 80:
        raise SeError("Give a range such as ^1.2.3, ~1.2.3, >=1.0.0 <2.0.0, 1.x or *.")
    terms, why = [], ""
    if s in ("*", "x"):
        ok, why = True, "Any version matches."
    elif s[0] == "^" or s[0] == "~":
        b = parse_version(s[1:])
        if s[0] == "^":
            hi = f"{b['major'] + 1}.0.0" if b["major"] else (f"0.{b['minor'] + 1}.0" if b["minor"] else f"0.0.{b['patch'] + 1}")
            why = f"^ allows changes that keep the left-most non-zero number: >= {s[1:]} and < {hi}."
        else:
            hi = f"{b['major']}.{b['minor'] + 1}.0"
            why = f"~ allows patch-level changes: >= {s[1:]} and < {hi}."
        terms = [(">=", s[1:]), ("<", hi)]
    elif re.match(r"^\d+(\.(x|\*|\d+))?(\.(x|\*))?$", s) and re.search(r"[x*]|^\d+$|^\d+\.\d+$", s):
        parts = re.split(r"\.", s)
        nums = []
        for p in parts:
            if p in ("x", "*"):
                break
            nums.append(int(p))
        lo = ".".join(map(str, (nums + [0, 0, 0])[:3]))
        hi = f"{nums[0] + 1}.0.0" if len(nums) == 1 else f"{nums[0]}.{nums[1] + 1}.0"
        terms = [(">=", lo), ("<", hi)]
        why = f"{s} means any version from {lo} up to (not including) {hi}."
    else:
        for tok in s.split():
            m = re.match(r"^(>=|<=|>|<|=)?(.+)$", tok)
            terms.append((m.group(1) or "=", m.group(2)))
        why = "All of the listed conditions must hold."
    if terms:
        ok = all(_atom(v, op, sp) for op, sp in terms)
        if v["pre"] and not any(parse_version(sp)["pre"] for _, sp in terms):
            ok = False
            why += " Pre-release versions are skipped unless the range itself names one (the npm convention)."
    return {"version": str(version), "range": s, "matches": bool(ok), "why": why}


# ---------------------------------------------------------------- requirements
_WEAK = ["fast", "quick", "user-friendly", "easy", "simple", "flexible", "robust", "efficient", "modern", "etc", "and/or", "as appropriate", "if possible", "appropriate", "adequate", "minimal", "optimal", "seamless", "intuitive", "secure", "reliable", "scalable"]


def check_story(text) -> dict:
    t = str(text or "").strip()
    if not t or len(t) > 600:
        raise SeError("Write one user story (up to 600 characters).")
    low = t.lower()
    who = re.search(r"\bas (?:a|an|the)\s+(.+?)(?:,|\bi\b)", low)
    what = re.search(r"\bi (?:want|need|can|would like)\s+(?:to\s+)?(.+?)(?:,|\bso\b|$)", low)
    why = re.search(r"\bso (?:that\s+)?(.+)$", low)
    issues = []
    if not who:
        issues.append("Who is the user? Start with 'As a <role>'.")
    if not what:
        issues.append("What should the user be able to do? Say 'I want to <action>'.")
    if not why:
        issues.append("Why do they want it? End with 'so that <benefit>'. Without the why you can't tell if a cheaper solution would do.")
    weak = [w for w in _WEAK if re.search(rf"\b{re.escape(w)}\b", low)]
    if weak:
        issues.append("Vague words you can't test: " + ", ".join(weak) + ". Replace each with a number or an observable result (for example 'loads in under 2 seconds').")
    if len(re.findall(r"\band\b", low)) >= 3:
        issues.append("Several 'and's: this may be more than one story. Split it so each can be built and tested alone.")
    return {"who": who.group(1).strip() if who else None, "what": what.group(1).strip() if what else None, "why": why.group(1).strip() if why else None,
            "issues": issues, "ok": not issues, "lesson": "A user story answers three questions: who, what and why. User acceptance testing checks whether it was met."}


def traceability(requirements, tests) -> dict:
    reqs, tsts = _list(requirements, "Requirements"), _list(tests, "Tests")
    rid, seen = [], set()
    for r in reqs:
        i = _id(r.get("id") if isinstance(r, dict) else r, "Each requirement")
        if i in seen:
            raise SeError(f"Requirement '{i}' is listed twice.")
        seen.add(i)
        rid.append((i, (r.get("priority") if isinstance(r, dict) else None) or "must", (r.get("text") if isinstance(r, dict) else "") or ""))
    cover: dict[str, list[str]] = {i: [] for i, _, _ in rid}
    orphans = []
    for t in tsts:
        tid = _id(t.get("id") if isinstance(t, dict) else t, "Each test")
        cv = t.get("covers") if isinstance(t, dict) else []
        cv = [str(x).strip() for x in (cv if isinstance(cv, list) else str(cv).split(","))if str(x).strip()]
        if not cv:
            orphans.append({"test": tid, "problem": "covers no requirement. Either it tests something nobody asked for, or a requirement is missing."})
        for c in cv:
            if c in cover:
                cover[c].append(tid)
            else:
                orphans.append({"test": tid, "problem": f"points at '{c}', which is not a requirement you listed."})
    rows = [{"requirement": i, "priority": p, "text": tx, "tests": cover[i], "covered": bool(cover[i])} for i, p, tx in rid]
    gaps = [r for r in rows if not r["covered"]]
    return {"matrix": rows, "coverage_pct": round(100 * (len(rows) - len(gaps)) / len(rows), 1), "uncovered": gaps, "orphan_tests": orphans,
            "must_have_gaps": [r["requirement"] for r in gaps if str(r["priority"]).lower() in ("must", "must-have", "high")],
            "lesson": "A traceability matrix maps each test to the requirement it proves. A requirement with no test is untested; a test with no requirement may be wasted effort."}


# ---------------------------------------------------------------- method and testing choices
def choose_method(req_change, customer_access, regulated, fixed_contract, cadence, team_size) -> dict:
    lv = {"low": 0, "medium": 1, "high": 2}
    if req_change not in lv or customer_access not in ("rare", "sometimes", "often") or cadence not in ("years", "months", "weeks") or team_size not in ("small", "medium", "large"):
        raise SeError("Check the choices.")
    sc = {"Waterfall": 0, "V-model": 0, "Agile": 0}
    why = {k: [] for k in sc}

    def add(m, n, t):
        sc[m] += n
        why[m].append(("+" if n > 0 else "") + f"{n}: {t}")
    if req_change == "high":
        add("Agile", 3, "requirements are expected to change, and Agile replans every sprint"); add("Waterfall", -2, "all planning is done up front, so late changes are hard"); add("V-model", -3, "even more rigid than waterfall")
    elif req_change == "low":
        add("Waterfall", 2, "stable requirements suit planning everything first"); add("V-model", 2, "stable requirements let you write the tests early")
    else:
        add("Agile", 1, "some change expected")
    if customer_access == "often":
        add("Agile", 2, "the customer can react to working software every sprint")
    elif customer_access == "rare":
        add("Waterfall", 1, "little customer contact is needed once requirements are signed off"); add("Agile", -1, "Agile depends on regular feedback")
    if regulated:
        add("V-model", 3, "each build step has a matching test step, which gives the traceability regulators ask for"); add("Waterfall", 1, "documentation and sign-off at each phase")
        add("Agile", -1, "can be done, but needs extra documentation and traceability work")
    if fixed_contract:
        add("Waterfall", 2, "a fixed scope and price is easier to estimate up front"); add("V-model", 1, "same reason"); add("Agile", -1, "scope is meant to flex, which clashes with a fixed scope")
    if cadence == "weeks":
        add("Agile", 2, "short release cycles")
    elif cadence == "years":
        add("Waterfall", 1, "long intervals between releases are normal"); add("V-model", 1, "same")
    if team_size == "large":
        add("Waterfall", 1, "clear phases and roles help big teams coordinate"); add("V-model", 1, "same")
    elif team_size == "small":
        add("Agile", 1, "small teams adapt fast")
    order = sorted(sc, key=lambda k: -sc[k])
    return {"ranking": [{"method": k, "score": sc[k], "reasons": why[k]} for k in order], "pick": order[0],
            "caution": "Real teams mix methods (for example Agile delivery inside a regulated, documented process). The score is a conversation starter, not a decision."}


def prioritize_regression(cases) -> dict:
    cs = _list(cases, "Test cases")
    W = (("uses_changed_code", 4, "exercises code that just changed"), ("failed_recently", 3, "has found defects before"), ("frequently_used", 2, "covers functionality people use a lot"),
         ("complex", 1, "complex or an edge case"), ("flaky", 1, "passes and fails at random: investigate before you trust it"))
    out = []
    for c in cs:
        if not isinstance(c, dict):
            raise SeError("Each test case needs an id and some yes/no flags.")
        reasons, s = [], 0
        for k, w, t in W:
            if c.get(k):
                s += w; reasons.append(t)
        out.append({"id": _id(c.get("id"), "Each test case"), "score": s, "reasons": reasons})
    out.sort(key=lambda x: (-x["score"], x["id"]))
    for i, o in enumerate(out, 1):
        o["order"] = i
    return {"order": out, "run_all_if": "the change touches shared code, the data model or security: then run every regression test rather than a selection.", "lesson": "Regression testing checks that a change didn't break what already worked. Run the riskiest cases first."}


# ---------------------------------------------------------------- architecture
def recommend_architecture(users, team, realtime_events, decentralized, independent_deploy, strong_consistency) -> dict:
    if users not in ("hundreds", "thousands", "millions") or team not in ("solo", "small", "large"):
        raise SeError("Check the choices.")
    sc = {"2-tier (client-server)": 0, "3-tier": 1, "Event-driven": 0, "Peer-to-peer": 0, "Microservices": 0}
    why = {k: [] for k in sc}

    def add(m, n, t):
        sc[m] += n; why[m].append(("+" if n > 0 else "") + f"{n}: {t}")
    add("3-tier", 1, "the common default: presentation, business logic and data kept apart")
    if users == "hundreds" and team in ("solo", "small"):
        add("2-tier (client-server)", 2, "simple and enough when few clients connect and one team owns everything"); add("Microservices", -3, "a small team pays the full cost of many services (deployment, monitoring, network failures) for little gain")
    if users == "millions":
        add("Microservices", 1, "parts can be scaled separately"); add("3-tier", 1, "tiers scale out behind load balancers"); add("2-tier (client-server)", -2, "the server becomes the bottleneck")
    if team == "large":
        add("Microservices", 2, "many teams can own and deploy separate services")
    if realtime_events:
        add("Event-driven", 3, "many things happen in response to events (orders, rides, sensor readings)")
    if decentralized:
        add("Peer-to-peer", 4, "no central server is wanted or trusted"); add("2-tier (client-server)", -2, "a peer is both client and server, so it can't be strictly two-tier")
    if independent_deploy:
        add("Microservices", 2, "parts must be released independently")
    if strong_consistency:
        add("Microservices", -1, "data spread over services makes strict consistency harder"); add("Event-driven", -1, "events are processed after the fact (eventual consistency)"); add("3-tier", 1, "one database gives simple transactions")
    order = sorted(sc, key=lambda k: -sc[k])
    return {"ranking": [{"pattern": k, "score": sc[k], "reasons": why[k]} for k in order], "pick": order[0],
            "caution": "Patterns combine (a 3-tier system can use microservices or events). Start with the simplest that meets your non-functional needs; architecture is costly to change later."}


def topology(web_servers=2, app_servers=2, db_replicas=1, load_balancer=True, firewall=True, proxy=False, part_availability_pct=99.5) -> dict:
    def n(v, nm, hi=50):
        try:
            x = int(v)
        except (TypeError, ValueError):
            raise SeError(f"{nm} must be a whole number.") from None
        if not 0 <= x <= hi:
            raise SeError(f"{nm} must be between 0 and {hi}.")
        return x
    web, app, rep = n(web_servers, "Web servers"), n(app_servers, "Application servers"), n(db_replicas, "Database replicas")
    try:
        a = float(part_availability_pct) / 100
    except (TypeError, ValueError):
        raise SeError("Availability must be a number.") from None
    if not 0.5 <= a < 1:
        raise SeError("Availability per part must be between 50 and 99.99 percent.")
    if web < 1 or app < 0:
        raise SeError("You need at least one web server.")
    spof, lines = [], []
    tiers = []

    def par(k):
        return 1 - (1 - a) ** k
    avail = 1.0
    lines.append("Clients")
    if firewall:
        lines.append("  |\n[Firewall]"); avail *= a
        spof.append("The firewall is a single point of failure unless you run a pair.")
    else:
        spof.append("No firewall: the internal tiers are reachable from outside. Put one between clients and the servers.")
    if proxy:
        lines.append("  |\n[Proxy server: caching, filtering, load balancing]"); avail *= a
    if load_balancer:
        lines.append("  |\n[Web load balancer]"); avail *= a
        spof.append("A single load balancer is itself a single point of failure: use a pair or a managed one.")
    elif web > 1:
        spof.append(f"{web} web servers but no load balancer: nothing spreads traffic or skips a failed server.")
    lines.append(f"  |\nWeb tier: {web} server(s)"); avail *= par(web); tiers.append(("web", web))
    if app:
        lines.append("  |\n[App load balancer or proxy]" if load_balancer and app > 1 else "  |")
        lines.append(f"Application tier: {app} server(s)"); avail *= par(app); tiers.append(("application", app))
    lines.append(f"  |\nDatabase tier: 1 primary + {rep} replica(s)"); avail *= par(1 + rep)
    for t, k in tiers:
        if k == 1:
            spof.append(f"The {t} tier has one server: if it fails, the whole site is down. Run at least two.")
    if rep == 0:
        spof.append("The database has no replica: if it fails the site stops, and you recover from backup. A replica gives a fast failover but is not a backup.")
    return {"diagram": "\n".join(lines), "single_points_of_failure": spof, "illustrative_availability_pct": round(avail * 100, 3), "assumed_per_part_pct": round(a * 100, 3),
            "downtime_hours_per_year": round((1 - avail) * 8766, 1),
            "caution": "A model, not a forecast: it assumes parts fail independently and that failover works instantly. Real systems also fail through bad releases, overload and shared causes.",
            "lesson": "Production must handle load, security, reliability and scalability, so it needs more parts than a test environment: a firewall, load balancers, several web and app servers and a replicated database."}


# ---------------------------------------------------------------- diagrams
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_ -]{0,39}$")


def check_states(states, transitions, start, finals=None) -> dict:
    ss = [str(s).strip() for s in _list(states, "States", 30)]
    if len(set(ss)) != len(ss):
        raise SeError("Two states have the same name.")
    ts = _list(transitions, "Transitions", 80)
    start = str(start or "").strip()
    fin = {str(f).strip() for f in (finals or []) if str(f).strip()}
    if start not in ss:
        raise SeError("The start state must be one of your states.")
    edges, issues, seen_key = [], [], {}
    for t in ts:
        if not isinstance(t, dict):
            raise SeError("Each transition is a from, an event and a to.")
        a, e, b = (str(t.get(k) or "").strip() for k in ("from", "event", "to"))
        for s in (a, b):
            if s not in ss:
                raise SeError(f"Transition {a} -> {b} mentions '{s}', which isn't a state.")
        if not e:
            raise SeError(f"The transition {a} -> {b} needs an event that triggers it.")
        if (a, e) in seen_key and seen_key[(a, e)] != b:
            issues.append({"level": "bad", "text": f"From '{a}' the event '{e}' leads to both '{seen_key[(a, e)]}' and '{b}'. The same event must lead to one place."})
        seen_key[(a, e)] = b
        edges.append((a, e, b))
    reach, todo = {start}, [start]
    while todo:
        x = todo.pop()
        for a, _, b in edges:
            if a == x and b not in reach:
                reach.add(b); todo.append(b)
    for s in ss:
        if s not in reach:
            issues.append({"level": "bad", "text": f"'{s}' can never be reached from '{start}'."})
        elif s not in fin and not any(a == s for a, _, _ in edges):
            issues.append({"level": "warn", "text": f"'{s}' is a dead end: nothing leaves it and it isn't marked as a final state."})
    if not fin:
        issues.append({"level": "info", "text": "No final state marked. Some systems run forever, which is fine; a process with an end should have one."})
    lines = ["stateDiagram-v2", f"  [*] --> {start.replace(' ', '_')}"] + [f"  {a.replace(' ', '_')} --> {b.replace(' ', '_')} : {e}" for a, e, b in edges] + [f"  {f.replace(' ', '_')} --> [*]" for f in sorted(fin) if f in ss]
    order = {"bad": 0, "warn": 1, "info": 2}
    return {"reachable": sorted(reach), "issues": sorted(issues, key=lambda i: order[i["level"]]), "ok": not any(i["level"] == "bad" for i in issues), "mermaid": "\n".join(lines),
            "lesson": "A state transition diagram lists the states a system can be in and the events that move it between them."}


def class_diagram(classes) -> dict:
    cs = _list(classes, "Classes", 25)
    names, parents, issues = [], {}, []
    for c in cs:
        if not isinstance(c, dict):
            raise SeError("Each class needs a name.")
        n = str(c.get("name") or "").strip()
        if not _NAME.match(n):
            raise SeError(f"Class name '{n}' should start with a letter and use letters, digits, spaces, - or _.")
        if n in names:
            raise SeError(f"Class '{n}' is listed twice.")
        names.append(n)
        p = str(c.get("parent") or "").strip()
        if p:
            parents[n] = p
    for n, p in parents.items():
        if p not in names:
            raise SeError(f"'{n}' inherits from '{p}', which isn't one of your classes.")
        seen, x = {n}, p
        while x in parents:
            if x in seen:
                raise SeError(f"Inheritance loop through '{n}': a class can't be its own ancestor.")
            seen.add(x); x = parents[x]
    lines = ["classDiagram"]
    for c in cs:
        n = c["name"].strip().replace(" ", "_")
        lines.append(f"  class {n} {{")
        for a in (c.get("attributes") or [])[:20]:
            lines.append(f"    +{str(a).strip()[:40]}")
        for m in (c.get("methods") or [])[:20]:
            lines.append(f"    +{str(m).strip().rstrip('()')[:40]}()")
        lines.append("  }")
    for n, p in parents.items():
        lines.append(f"  {p.replace(' ', '_')} <|-- {n.replace(' ', '_')}")
    for c in cs:
        if not (c.get("attributes") or c.get("methods")) and not any(p == c["name"].strip() for p in parents.values()):
            issues.append(f"'{c['name']}' has no attributes or methods: a class with nothing in it usually isn't ready.")
    tree = []
    for c in cs:
        d, x = 0, c["name"].strip()
        while x in parents:
            d += 1; x = parents[x]
        tree.append(("  " * d) + c["name"].strip() + (f" (inherits {parents[c['name'].strip()]})" if c["name"].strip() in parents else ""))
    return {"mermaid": "\n".join(lines), "outline": tree, "notes": issues,
            "lesson": "A class is a blueprint; an object is one instance made from it. A subclass inherits its parent's attributes and methods and may add more."}


_OUT = re.compile(r"^(print|output|display|write|show)\b\s*(.*)$", re.I)
_IN = re.compile(r"^(input|read|get|enter)\b\s*(.*)$", re.I)


def pseudocode_to_flow(src) -> dict:
    lines = [ln.strip() for ln in str(src or "").splitlines() if ln.strip() and not ln.strip().startswith(("#", "//"))]
    if not lines or len(lines) > 120:
        raise SeError("Write between 1 and 120 lines of pseudocode.")
    nodes, edges = [], []

    def node(kind, text):
        nodes.append({"id": f"n{len(nodes) + 1}", "kind": kind, "text": text[:80]})
        return nodes[-1]["id"]
    pos = [0]

    def link(frm, to):
        for a, lab in frm:
            edges.append((a, to, lab))

    def block(stop):
        first, exits = None, []
        while pos[0] < len(lines):
            ln = lines[pos[0]]
            low = ln.lower()
            if any(low.startswith(s) for s in stop):
                break
            pos[0] += 1
            if len(nodes) > 40:
                raise SeError("That is more than 40 steps: split it into smaller pieces first.")
            m_if = re.match(r"^if\s+(.+?)\s*(?:then)?$", ln, re.I)
            m_wh = re.match(r"^while\s+(.+?)\s*(?:do)?$", ln, re.I)
            m_for = re.match(r"^for\s+(\w+)\s+(?:from|=|in)\s+(.+?)\s+to\s+(.+?)\s*(?:do)?$", ln, re.I)
            if m_if:
                d = node("decision", m_if.group(1) + "?")
                f1, x1 = block(("else", "end if", "endif"))
                x2, f2 = [], None
                if pos[0] < len(lines) and lines[pos[0]].lower() == "else":
                    pos[0] += 1
                    f2, x2 = block(("end if", "endif"))
                if pos[0] < len(lines) and lines[pos[0]].lower() in ("end if", "endif"):
                    pos[0] += 1
                else:
                    raise SeError(f"The IF '{m_if.group(1)}' has no END IF.")
                if first is None:
                    first = d
                link(exits, d)
                out = []
                if f1:
                    edges.append((d, f1, "yes")); out += x1
                else:
                    out.append((d, "yes"))
                if f2:
                    edges.append((d, f2, "no")); out += x2
                else:
                    out.append((d, "no"))
                exits = out
            elif m_wh or m_for:
                if m_for:
                    v, a, b = m_for.groups()
                    init = node("process", f"{v} = {a}")
                    d = node("decision", f"{v} <= {b}?")
                    edges.append((init, d, ""))
                    entry = init
                else:
                    d = node("decision", m_wh.group(1) + "?"); entry = d
                f1, x1 = block(("end while", "endwhile", "end for", "endfor", "next"))
                if pos[0] < len(lines) and lines[pos[0]].lower() in ("end while", "endwhile", "end for", "endfor", "next"):
                    pos[0] += 1
                else:
                    raise SeError("A loop has no END WHILE / END FOR.")
                if first is None:
                    first = entry
                link(exits, entry)
                if m_for:
                    inc = node("process", f"{v} = {v} + 1")
                    if f1:
                        link(x1, inc)
                        edges.append((d, f1, "yes"))
                    else:
                        edges.append((d, inc, "yes"))
                    edges.append((inc, d, ""))
                elif f1:
                    edges.append((d, f1, "yes")); link(x1, d)
                else:
                    edges.append((d, d, "yes"))
                exits = [(d, "no")]
            else:
                if low in ("else", "end if", "endif", "end while", "endwhile", "end for", "endfor", "next"):
                    raise SeError(f"'{ln}' has no matching IF or loop above it.")
                if low in ("start", "begin"):
                    n_ = node("terminal", "Start")
                elif low in ("end", "stop"):
                    n_ = node("terminal", "End")
                elif _IN.match(ln):
                    n_ = node("io", "Input " + _IN.match(ln).group(2))
                elif _OUT.match(ln):
                    n_ = node("io", "Output " + _OUT.match(ln).group(2))
                else:
                    n_ = node("process", re.sub(r"^(set|let)\s+", "", ln, flags=re.I).replace("<-", "="))
                if first is None:
                    first = n_
                link(exits, n_)
                exits = [(n_, "")]
        return first, exits
    first, _ = block(())
    if pos[0] < len(lines):
        raise SeError(f"Unexpected line: '{lines[pos[0]]}'. (An ELSE or END without its IF or loop?)")
    shape = {"terminal": ("([", "])"), "io": ("[/", "/]"), "process": ("[", "]"), "decision": ("{", "}")}
    out = ["flowchart TD"] + [f'  {n["id"]}{shape[n["kind"]][0]}"{n["text"].replace(chr(34), chr(39))}"{shape[n["kind"]][1]}' for n in nodes]
    out += [f'  {a} -->{"|" + lab + "|" if lab else ""} {b}' for a, b, lab in edges]
    return {"nodes": nodes, "edges": [{"from": a, "to": b, "label": lab} for a, b, lab in edges], "mermaid": "\n".join(out),
            "symbols": {"terminal": "capsule: start or end", "io": "parallelogram: input or output", "process": "rectangle: a step", "decision": "diamond: a yes/no question"},
            "lesson": "A flowchart shows an algorithm as shapes joined by arrows; pseudocode describes the same steps in plain words, independent of any language."}


# ---------------------------------------------------------------- reference
PHASES = [
    {"phase": "1. Planning", "does": "Decide scope, budget, schedule, team and risks; check the project is feasible.", "output": "Project plan, feasibility study"},
    {"phase": "2. Requirements analysis", "does": "Collect and write down what users and the business need.", "output": "SRS (software requirements specification)"},
    {"phase": "3. Design", "does": "Decide how the system will be built: architecture, data, interfaces.", "output": "Software design document (SDD), diagrams"},
    {"phase": "4. Development", "does": "Write the code and unit-test it.", "output": "Working code, unit tests"},
    {"phase": "5. Testing", "does": "Check the software against the requirements and fix defects.", "output": "Test reports, defect list"},
    {"phase": "6. Deployment and maintenance", "does": "Release it, then fix bugs, add features and keep it running.", "output": "Release, patches, updates"},
]
METHODS = [
    {"name": "Waterfall", "what": "Phases run one after another; each ends with sign-off before the next starts.", "good": "Stable, well-understood requirements; fixed scope and price.", "bad": "Changes late in the project are expensive; the customer sees working software last."},
    {"name": "V-model", "what": "Waterfall bent into a V: each build phase is paired with a test phase (requirements with acceptance testing, design with system and integration testing, code with unit testing).", "good": "Regulated work (medical, aviation, automotive) that needs traceability.", "bad": "Rigid, like waterfall; heavy documentation."},
    {"name": "Agile", "what": "Short iterations (sprints) that each deliver working software; requirements are re-prioritised every cycle.", "good": "Changing requirements, a customer who is available, frequent releases.", "bad": "Harder to fix scope, price and date together; needs discipline to keep documentation."},
    {"name": "Scrum", "what": "An Agile framework: sprints of 1 to 4 weeks, a product backlog, daily stand-ups, sprint review and retrospective; roles are product owner, scrum master and developers.", "good": "Teams that can commit to a sprint goal.", "bad": "Poor fit for unpredictable interrupt-driven work."},
    {"name": "Kanban", "what": "A board of columns (to do, doing, done) with a limit on work in progress; work flows continuously.", "good": "Support and maintenance work.", "bad": "No built-in time-box, so it needs its own cadence."},
]
TEST_LEVELS = [
    {"level": "Unit", "tests": "One function or class in isolation.", "who": "Developers", "when": "While coding"},
    {"level": "Integration", "tests": "Several units or services working together (for example the API and the database).", "who": "Developers and testers", "when": "After units pass"},
    {"level": "System", "tests": "The whole application against the requirements, in a production-like setup.", "who": "Testers", "when": "Before release"},
    {"level": "Acceptance (UAT)", "tests": "Whether the customer or users accept it: does it do what they need?", "who": "Customer or users", "when": "Last step before go-live"},
]
TEST_TYPES = [
    {"type": "Functional", "checks": "It does what it should (login works, the total is correct)."},
    {"type": "Non-functional", "checks": "How well: performance, load, security, usability, accessibility, reliability."},
    {"type": "Regression", "checks": "A change didn't break something that worked before."},
    {"type": "Smoke", "checks": "A quick check that the build starts and the main paths work, before deeper testing."},
]
DOC_TYPES = [
    {"doc": "SRS / URS / SysRS", "what": "Requirements: URS = what users need, SysRS = what the system must do, SRS = the software requirements."},
    {"doc": "SDD (design document)", "what": "Architecture, data design, interfaces and diagrams."},
    {"doc": "Test plan and test cases", "what": "What will be tested, how, by whom, and the pass criteria."},
    {"doc": "User manual and help", "what": "How to use the software."},
    {"doc": "Release notes and changelog", "what": "What changed in each version."},
    {"doc": "SOP (standard operating procedure)", "what": "A step-by-step instruction so a routine task is done the same way every time."},
    {"doc": "README and API docs", "what": "How a developer builds, runs and calls the code."},
]
TOOLS = [
    {"group": "Version control", "items": "Git (GitHub, GitLab, Bitbucket). Track changes, branch, merge, review, roll back."},
    {"group": "Build tools", "items": "Make, Maven, Gradle, npm scripts, Vite, webpack: turn source into something that runs."},
    {"group": "Package managers", "items": "pip (Python), npm and yarn (JavaScript), Maven (Java), NuGet (.NET), Cargo (Rust), apt and brew (system)."},
    {"group": "CI/CD", "items": "GitHub Actions, GitLab CI, Jenkins: on every push, build and test (continuous integration), then release (continuous delivery or deployment)."},
    {"group": "Testing", "items": "pytest, JUnit, Jest, Playwright, Selenium, Postman."},
    {"group": "Containers", "items": "Docker, Kubernetes: package an app with its dependencies so it runs the same everywhere."},
]
LIB_VS_FW = {"library": "You call it. You choose when and where (for example pandas, requests, lodash).", "framework": "It calls you. It owns the structure and flow and runs your code at set points (inversion of control; for example Django, Rails, Spring, React's rendering).",
             "note": "A framework is easiest to adopt at the start of a project, but it can be added to an existing one with effort."}
STACKS = [
    {"name": "LAMP", "parts": "Linux, Apache, MySQL, PHP", "note": "Classic web hosting stack."},
    {"name": "MEAN", "parts": "MongoDB, Express, Angular, Node.js", "note": "JavaScript end to end."},
    {"name": "MERN", "parts": "MongoDB, Express, React, Node.js", "note": "Same with React."},
    {"name": "MEVN", "parts": "MongoDB, Express, Vue, Node.js", "note": "Same with Vue."},
    {"name": "Django", "parts": "Python, Django, usually PostgreSQL", "note": "Batteries included."},
    {"name": "Rails", "parts": "Ruby on Rails, usually PostgreSQL", "note": "Convention over configuration."},
    {"name": "ASP.NET", "parts": "C#, ASP.NET, SQL Server", "note": "Microsoft stack."},
    {"name": "This dashboard", "parts": "Python FastAPI, DuckDB, Next.js, React, Tailwind", "note": "A modern Python plus React stack."},
]
LANGUAGES = [
    {"kind": "Compiled (ahead of time)", "examples": "C, C++, Go, Rust", "how": "Translated to machine code before you run it; usually fast to run."},
    {"kind": "Compiled to bytecode, then run on a VM", "examples": "Java, C#, Kotlin", "how": "A compiler makes bytecode; a runtime (JVM, .NET CLR) runs it, often with just-in-time compilation."},
    {"kind": "Interpreted or scripting", "examples": "Python, Ruby, PHP, JavaScript", "how": "Run by an interpreter or engine. Most compile to bytecode internally and JavaScript engines JIT-compile, so the line is blurry."},
    {"kind": "Query languages", "examples": "SQL, GraphQL", "how": "Describe what data you want, not how to get it."},
    {"kind": "Markup and style", "examples": "HTML, CSS, Sass, Less, Markdown", "how": "Describe structure and appearance; Sass and Less compile to CSS."},
    {"kind": "Assembly", "examples": "x86, ARM assembly", "how": "Human-readable machine instructions for one CPU family."},
]
ENVIRONMENTS = [
    {"env": "Development", "for": "Developers write and try code. Break things freely.", "data": "Fake or sample"},
    {"env": "QA / test", "for": "Testers run test plans on a build.", "data": "Test data"},
    {"env": "Staging", "for": "A copy of production for a final rehearsal and UAT.", "data": "Masked or copied production-like data"},
    {"env": "Production", "for": "Real users. Changes are controlled.", "data": "Real data"},
]
HOSTING = [
    {"name": "On-premises", "what": "Your own hardware and rooms. You manage everything."},
    {"name": "Public cloud", "what": "Rented shared infrastructure (AWS, Azure, Google Cloud)."},
    {"name": "Private cloud", "what": "Cloud-style infrastructure used by one organisation."},
    {"name": "Hybrid", "what": "A mix of on-premises and cloud."},
]
PROD_PARTS = [
    {"part": "Firewall", "does": "Allows or blocks traffic by rule."},
    {"part": "Load balancer", "does": "Spreads requests over several servers and stops sending traffic to an unhealthy one."},
    {"part": "Web server", "does": "Serves pages and static files (nginx, Apache)."},
    {"part": "Proxy / reverse proxy", "does": "Sits in front of servers: caching, TLS, hiding the servers behind it."},
    {"part": "Application server", "does": "Runs the business logic."},
    {"part": "Database server", "does": "Stores the data; replicas copy it for reads and for safety."},
]
CONCEPTS = [
    {"term": "Identifier", "what": "The name of a variable, function or class."},
    {"term": "Constant", "what": "A named value that doesn't change while the program runs."},
    {"term": "Variable", "what": "A named place that holds a value that can change."},
    {"term": "Array", "what": "An ordered collection accessed by position. Python calls it a list; C++ also has a resizable vector."},
    {"term": "Function", "what": "A named, reusable block that takes inputs and may return a result."},
    {"term": "Class and object", "what": "A class is a blueprint; an object is one instance of it. Encapsulation, inheritance and polymorphism are the OOP ideas."},
    {"term": "Algorithm", "what": "A finite list of steps that solves a problem. Pseudocode and flowcharts describe it before you code."},
]
ARCHITECTURE = [
    {"name": "2-tier", "what": "Client talks straight to a server (usually the database)."},
    {"name": "3-tier", "what": "Presentation, application (logic) and data tiers kept separate; each can be changed or scaled on its own."},
    {"name": "Peer-to-peer", "what": "Every node is both client and server; no central authority."},
    {"name": "Event-driven", "what": "Parts react to events through a broker or queue; loosely coupled."},
    {"name": "SOA", "what": "Service-oriented: reusable services with defined contracts, often through an enterprise bus."},
    {"name": "Microservices", "what": "Many small services, each owning its data and deployed on its own. Costs: network failures, monitoring, data consistency."},
]
UML = [
    {"diagram": "Class diagram", "shows": "Classes, their attributes and methods, and how they relate (structure)."},
    {"diagram": "Sequence diagram", "shows": "Messages between objects over time (behaviour)."},
    {"diagram": "State diagram", "shows": "States and the events that move between them (behaviour)."},
    {"diagram": "Use case diagram", "shows": "What users (actors) can do with the system."},
    {"diagram": "Flowchart", "shows": "The steps and decisions of an algorithm (not UML, but used alongside it)."},
]
SLIPS = [
    "The course describes 'semantic numbering' with four parts. Semantic versioning (SemVer) has three: MAJOR.MINOR.PATCH, with optional pre-release and build labels. Ubuntu's 18.04.2 is calendar versioning (year.month), not SemVer.",
    "'Interpreted for small tasks, compiled for large ones' is not a rule. It's about how a language is implemented: Python compiles to bytecode, Java and C# run on a virtual machine, and JavaScript engines compile just in time.",
    "Operating systems are not written in one language. Android is mostly C and C++ with Java and Kotlin for apps, Windows is mostly C and C++, and Excel is mainly C++.",
    "Sass stands for 'Syntactically Awesome Style Sheets' (not the SAS statistics software) and Less for 'Leaner Style Sheets'.",
    "'A framework can't be added to an existing project' overstates it. It is hard, and best done at the start, but it can be done incrementally.",
    "'A service has only one always-running instance' is wrong in practice: services usually run several instances behind a load balancer.",
    "JavaScript is multi-paradigm and prototype-based, not simply 'object-oriented' like Java.",
    "The course is inconsistent on when user acceptance testing happens (at deployment or in maintenance). Normally it comes just before go-live.",
    "'A change in one tier doesn't affect the others' only holds while the interfaces between tiers stay the same.",
    "The array and vector syntax shown is C++-specific; other languages differ.",
]
NOT_BUILT = [
    "Running your CI/CD pipeline, containers or a Kubernetes cluster: these need servers this dashboard doesn't have. The checkers here design and check; you run the tools.",
    "Load balancers, firewalls and cloud hosting are infrastructure. The topology tool draws and reasons about them but cannot create them.",
    "Availability figures are illustrative, assuming each part fails independently.",
    "Choosing a methodology or architecture is a judgment. The scores explain trade-offs; they don't decide for you.",
]
NOTE = "A guide to how software is planned, built, tested and shipped. It mirrors a software engineering fundamentals course, with the course's slips corrected on the Reference tab."


def reference() -> dict:
    return {"note": NOTE, "phases": PHASES, "methods": METHODS, "test_levels": TEST_LEVELS, "test_types": TEST_TYPES, "docs": DOC_TYPES, "tools": TOOLS, "library_vs_framework": LIB_VS_FW,
            "stacks": STACKS, "languages": LANGUAGES, "environments": ENVIRONMENTS, "hosting": HOSTING, "production": PROD_PARTS, "concepts": CONCEPTS, "architecture": ARCHITECTURE, "uml": UML,
            "slips": SLIPS, "not_built": NOT_BUILT,
            "example_pseudocode": "START\nINPUT n\nSET total = 0\nFOR i = 1 TO n\n  total = total + i\nEND FOR\nIF total > 10 THEN\n  PRINT \"big\"\nELSE\n  PRINT \"small\"\nEND IF\nEND",
            "example_states": {"states": ["Draft", "Review", "Approved", "Released"], "start": "Draft", "finals": ["Released"],
                              "transitions": [{"from": "Draft", "event": "submit", "to": "Review"}, {"from": "Review", "event": "reject", "to": "Draft"}, {"from": "Review", "event": "approve", "to": "Approved"}, {"from": "Approved", "event": "deploy", "to": "Released"}]},
            "example_classes": [{"name": "Vehicle", "attributes": ["make", "speed"], "methods": ["start", "stop"]}, {"name": "Car", "parent": "Vehicle", "attributes": ["doors"], "methods": ["openTrunk"]}]}
