"""IT infrastructure practice tools: directory services, Group Policy and access control.

  gpo_resolve  - work out which Group Policy settings win for one user or computer (Local, Site, Domain, OU order,
                 link order, Enforced, Block Inheritance, security filtering) and why the losers lost
  ldif_check   - parse and validate LDIF text (add, modify, delete, moddn) before it touches a directory
  ldif_build   - build a correct LDIF entry for a user, group or OU, with escaping and base64 where needed
  rbac_check   - audit a role-based access model: inheritance cycles, separation-of-duties conflicts, wide roles,
                 direct grants and orphans

Honest limits: this is a model of the rules, not Active Directory or OpenLDAP. It never connects to a server. The
Group Policy resolver covers precedence only (no WMI filters beyond a pass/fail flag, no loopback processing, no
slow-link or security-permission details); the LDIF checker knows a few common object classes, not your schema.
"""
from __future__ import annotations

import base64
import re


class InfraError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


LEVELS = ("local", "site", "domain", "ou")


# ------------------------------------------------------------------ Group Policy resolution
def gpo_resolve(obj, chain) -> dict:
    """obj: {name, groups[]}. chain: containers from least to most specific, each
    {level: local|site|domain|ou, name, block_inheritance?, gpos:[{name, link_order, enforced?, enabled?, wmi_pass?, filter?[], settings{}}]}"""
    if not isinstance(obj, dict) or not str(obj.get("name", "")).strip():
        raise InfraError("Give the user or computer a name.")
    if not isinstance(chain, list) or not 1 <= len(chain) <= 14:
        raise InfraError("Give between 1 and 14 containers, from Local down to the most specific OU.")
    principals = {str(obj["name"]).lower(), "authenticated users"} | {str(g).lower() for g in (obj.get("groups") or [])}
    order_in_chain = []
    for ci, c in enumerate(chain):
        if not isinstance(c, dict) or c.get("level") not in LEVELS:
            raise InfraError(f"Container {ci + 1}: level must be one of {', '.join(LEVELS)}.")
        if not str(c.get("name", "")).strip():
            raise InfraError(f"Container {ci + 1} needs a name.")
        gp = c.get("gpos") or []
        if not isinstance(gp, list) or len(gp) > 20:
            raise InfraError(f"Container '{c['name']}': give up to 20 GPOs.")
        for g in gp:
            if not isinstance(g, dict) or not str(g.get("name", "")).strip():
                raise InfraError(f"Container '{c['name']}': every GPO needs a name.")
            if not isinstance(g.get("settings", {}), dict) or len(g.get("settings", {})) > 60:
                raise InfraError(f"GPO '{g['name']}': settings must be an object of up to 60 entries.")
            lo = g.get("link_order", 1)
            if isinstance(lo, bool) or not isinstance(lo, int) or lo < 1:
                raise InfraError(f"GPO '{g['name']}': link_order must be 1 or more.")
    ranks = [LEVELS.index(c["level"]) for c in chain]
    if ranks != sorted(ranks):
        raise InfraError("Containers must run Local, Site, Domain, then OUs from parent to child.")
    if sum(1 for c in chain if c["level"] == "local") > 1:
        raise InfraError("Only one Local container.")
    skipped, normal, enforced = [], [], []
    block_at = None
    for ci, c in enumerate(chain):
        if c.get("block_inheritance") and c["level"] in ("site", "domain", "ou"):
            block_at = ci
    for ci, c in enumerate(chain):
        blocked_here = any(chain[k].get("block_inheritance") for k in range(ci + 1, len(chain)) if chain[k]["level"] != "local")
        ordered = sorted(c.get("gpos") or [], key=lambda g: -int(g.get("link_order", 1)))
        for g in ordered:
            tag = {"gpo": g["name"], "container": c["name"], "level": c["level"], "link_order": int(g.get("link_order", 1))}
            if g.get("enabled", True) is False:
                skipped.append({**tag, "why": "link is disabled"}); continue
            flt = [str(x).lower() for x in (g.get("filter") or ["Authenticated Users"])]
            if not (set(flt) & principals):
                skipped.append({**tag, "why": f"security filtering: {obj['name']} is not in {', '.join(g.get('filter') or [])}"}); continue
            if g.get("wmi_pass", True) is False:
                skipped.append({**tag, "why": "WMI filter did not match"}); continue
            is_enf = bool(g.get("enforced")) and c["level"] != "local"
            if blocked_here and not is_enf and c["level"] != "local":
                skipped.append({**tag, "why": "Block Inheritance on a lower OU (not Enforced)"}); continue
            entry = {**tag, "enforced": is_enf, "settings": dict(g.get("settings") or {}), "depth": ci}
            (enforced if is_enf else normal).append(entry)
    # enforced GPOs are applied last, from the most specific container up, so the highest Enforced GPO wins
    enforced.sort(key=lambda e: (-e["depth"], -e["link_order"]))
    applied = normal + enforced
    final: dict[str, dict] = {}
    history: dict[str, list] = {}
    for e in applied:
        for k, v in e["settings"].items():
            history.setdefault(k, []).append({"gpo": e["gpo"], "container": e["container"], "value": v, "enforced": e["enforced"]})
            final[k] = {"value": v, "winner": e["gpo"], "container": e["container"], "enforced": e["enforced"]}
    settings = []
    for k, f in final.items():
        h = history[k]
        settings.append({"setting": k, "value": f["value"], "winning_gpo": f["winner"], "from": f["container"], "enforced": f["enforced"],
                         "conflict": len(h) > 1 and len({str(x["value"]) for x in h}) > 1,
                         "overridden": [f"{x['gpo']} ({x['container']}) = {x['value']}" for x in h[:-1] if str(x["value"]) != str(f["value"])]})
    settings.sort(key=lambda s: (not s["conflict"], s["setting"]))
    warnings = []
    if any(s["enforced"] and s["conflict"] for s in settings):
        warnings.append("An Enforced GPO is overriding a lower setting. That is by design, but it is the usual reason 'my OU setting is ignored'.")
    if block_at is not None and not any(e["enforced"] for e in applied):
        warnings.append("Block Inheritance is on and nothing is Enforced: confirm the block is not also cutting off your baseline security policy.")
    if any(c["level"] == "site" for c in chain):
        warnings.append("Site links apply to every object whose computer is in that AD site, wherever its OU is.")
    return {"object": obj["name"], "order_applied": [{"step": i + 1, "gpo": e["gpo"], "container": e["container"], "level": e["level"], "link_order": e["link_order"], "enforced": e["enforced"]} for i, e in enumerate(applied)],
            "settings": settings, "skipped": skipped, "conflicts": sum(1 for s in settings if s["conflict"]), "warnings": warnings,
            "lesson": "GPOs apply Local, Site, Domain, then each OU from parent to child (LSDOU). The LAST one to touch a setting wins, so the most specific container wins. Inside one container, link order 1 is applied last and wins. "
                      "Enforced flips it: a higher Enforced GPO beats everything below it, and Block Inheritance cannot stop it. Security filtering and WMI filters decide whether a GPO applies at all.",
            "limit": "Models precedence only. Real processing also depends on replication, permissions to read the GPO, loopback processing, slow links and Client-Side Extension quirks. Confirm on the real machine with gpresult /r or the Group Policy Results wizard."}


GPO_SAMPLE = {"object": {"name": "EMMETTPC01", "groups": ["Sales Computers"]},
              "chain": [{"level": "local", "name": "Local policy", "gpos": [{"name": "Local", "settings": {"Wallpaper": "default.jpg"}}]},
                        {"level": "site", "name": "India site", "gpos": []},
                        {"level": "domain", "name": "example.com", "gpos": [{"name": "Domain baseline", "link_order": 1, "settings": {"Wallpaper": "corp.jpg", "Excel macros": "Disabled", "Password length": 12}},
                                                                            {"name": "Security lockdown", "link_order": 2, "enforced": True, "settings": {"Password length": 14}}]},
                        {"level": "ou", "name": "Sales computers", "gpos": [{"name": "Network drives", "link_order": 1, "settings": {"Mapped drive": "S:"}}, {"name": "Printers", "link_order": 2, "settings": {"Default printer": "Sales-01", "Mapped drive": "none"}},
                                                                             {"name": "Relax macros", "link_order": 3, "settings": {"Excel macros": "Signed only", "Password length": 8}}]}]}


# ------------------------------------------------------------------ LDIF
_ATTR = re.compile(r"^[A-Za-z][A-Za-z0-9-]*(;[A-Za-z0-9-]+)*$|^\d+(\.\d+)+$")
MUST = {"person": ["cn", "sn"], "inetorgperson": ["cn", "sn"], "organizationalperson": ["cn", "sn"], "organizationalunit": ["ou"], "groupofnames": ["cn", "member"],
        "groupofuniquenames": ["cn", "uniquemember"], "posixaccount": ["cn", "uid", "uidnumber", "gidnumber", "homedirectory"], "posixgroup": ["cn", "gidnumber"],
        "organization": ["o"], "dcobject": ["dc"], "domain": ["dc"], "country": ["c"], "locality": ["l"]}
MAX_LDIF = 400_000


def _split_dn(dn: str):
    parts, cur, esc = [], "", False
    for ch in dn:
        if esc:
            cur += ch; esc = False
        elif ch == "\\":
            cur += ch; esc = True
        elif ch == ",":
            parts.append(cur); cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def dn_problems(dn: str) -> list[str]:
    out = []
    if not dn.strip():
        return ["the DN is empty"]
    for rdn in _split_dn(dn):
        for av in re.split(r"(?<!\\)\+", rdn):
            if "=" not in av:
                out.append(f"'{av.strip()}' is not attribute=value"); continue
            a, v = av.split("=", 1)
            if not _ATTR.match(a.strip()):
                out.append(f"'{a.strip()}' is not a valid attribute name")
            if not v.strip():
                out.append(f"'{a.strip()}' has an empty value")
    if dn != dn.strip():
        out.append("leading or trailing space around the DN")
    return out


def _unfold(text):
    lines = []
    for n, raw in enumerate(text.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        if raw.startswith(" ") and lines and lines[-1][1].strip():
            lines[-1] = (lines[-1][0], lines[-1][1] + raw[1:])
        else:
            lines.append((n, raw))
    return lines


def ldif_check(text) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise InfraError("Paste some LDIF.")
    if len(text) > MAX_LDIF:
        raise InfraError(f"Keep it under {MAX_LDIF:,} characters.")
    lines = _unfold(text)
    blocks, cur = [], []
    for n, l in lines:
        if l.startswith("#"):
            continue
        if not l.strip():
            if cur:
                blocks.append(cur); cur = []
        else:
            cur.append((n, l))
    if cur:
        blocks.append(cur)
    records, seen, problems = [], {}, []
    version_ok = None
    for bi, blk in enumerate(blocks):
        if bi == 0 and blk[0][1].lower().startswith("version:"):
            version_ok = blk[0][1].split(":", 1)[1].strip() == "1"
            if not version_ok:
                problems.append({"line": blk[0][0], "level": "error", "issue": "version must be 1"})
            blk = blk[1:]
            if not blk:
                continue
        rec = {"dn": None, "changetype": "add", "attrs": {}, "mods": [], "line": blk[0][0], "errors": [], "warnings": []}

        def err(m, n=None, rec=rec):
            rec["errors"].append(m); problems.append({"line": n or rec["line"], "level": "error", "issue": f"{rec['dn'] or 'record at line ' + str(rec['line'])}: {m}"})

        def warn(m, n=None, rec=rec):
            rec["warnings"].append(m); problems.append({"line": n or rec["line"], "level": "warn", "issue": f"{rec['dn'] or '?'}: {m}"})

        def parse(n, l):
            if ":" not in l:
                return None, None, None
            k, rest = l.split(":", 1)
            mode = "plain"
            if rest.startswith(":"):
                mode, rest = "b64", rest[1:]
            elif rest.startswith("<"):
                mode, rest = "url", rest[1:]
            v = rest[1:] if rest.startswith(" ") else rest
            if mode == "b64":
                try:
                    v = base64.b64decode(v.strip(), validate=True).decode("utf-8")
                except Exception:
                    err(f"line {n}: '{k}::' is not valid base64 UTF-8", n); v = ""
            elif mode == "url":
                warn(f"line {n}: '{k}:<' reads a file or URL; check where it points", n)
            else:
                if not v.isascii():
                    err(f"line {n}: non-ASCII text in '{k}' must be base64 encoded with '::'", n)
                if v != v.rstrip():
                    warn(f"line {n}: '{k}' value ends with a space, which is usually unintended", n)
            return k.strip(), v, mode
        first = blk[0]
        k, v, _ = parse(*first)
        if (k or "").lower() != "dn":
            err("the first line of a record must be dn:", first[0]); records.append(rec); continue
        rec["dn"] = v
        for p in dn_problems(v):
            err(f"DN: {p}", first[0])
        rest = blk[1:]
        if rest and rest[0][1].lower().startswith("changetype:"):
            rec["changetype"] = rest[0][1].split(":", 1)[1].strip().lower(); rest = rest[1:]
            if rec["changetype"] not in ("add", "modify", "delete", "modrdn", "moddn"):
                err(f"unknown changetype '{rec['changetype']}'", first[0])
        ct = rec["changetype"]
        if ct not in ("modify", "delete", "modrdn", "moddn"):
            for n, l in rest:
                k, v, _ = parse(n, l)
                if k is None:
                    err(f"line {n}: not an attribute: value line ('{l[:30]}')", n); continue
                if not _ATTR.match(k):
                    err(f"line {n}: '{k}' is not a valid attribute name", n)
                rec["attrs"].setdefault(k.lower(), []).append(v)
            oc = [x.lower() for x in rec["attrs"].get("objectclass", [])]
            if not oc:
                err("no objectClass: an entry cannot be added without one")
            else:
                for c in oc:
                    for m in MUST.get(c, []):
                        if m not in rec["attrs"]:
                            err(f"objectClass {c} requires '{m}'")
            rdn_first = _split_dn(rec["dn"])[0] if rec["dn"] else ""
            for av in re.split(r"(?<!\\)\+", rdn_first):
                if "=" in av:
                    a, val = av.split("=", 1)
                    a = a.strip().lower(); val = val.strip().replace("\\", "")
                    if a not in rec["attrs"]:
                        err(f"the RDN uses '{a}' but the entry has no '{a}' attribute")
                    elif val.lower() not in [x.lower() for x in rec["attrs"][a]]:
                        err(f"the RDN says {a}={val} but the {a} attribute holds {', '.join(rec['attrs'][a])[:60]}")
            for pw in rec["attrs"].get("userpassword", []):
                if not pw.startswith("{"):
                    warn("userPassword looks like plain text; store a hash such as {SSHA} (made with slappasswd)")
        elif ct == "modify":
            op, attr, vals = None, None, []
            for n, l in rest:
                if l.strip() == "-":
                    if op:
                        rec["mods"].append({"op": op, "attr": attr, "values": vals})
                    op, attr, vals = None, None, []; continue
                k, v, _ = parse(n, l)
                if k is None:
                    err(f"line {n}: not an attribute: value line", n); continue
                if k.lower() in ("add", "replace", "delete") and op is None:
                    op, attr, vals = k.lower(), v, []
                elif op and k.lower() == (attr or "").lower():
                    vals.append(v)
                else:
                    err(f"line {n}: '{k}' does not belong to the '{op or 'start'}' operation; each operation ends with a line containing only '-'", n)
            if op:
                rec["mods"].append({"op": op, "attr": attr, "values": vals})
                warn("the last modify operation has no closing '-' line (RFC 2849 asks for one; OpenLDAP tools usually accept its absence, but add it)")
            if not rec["mods"]:
                err("a modify record has no operations")
            for m in rec["mods"]:
                if m["op"] in ("add", "replace") and not m["values"] and m["op"] == "add":
                    err(f"add {m['attr']} has no values")
                if m["attr"].lower() == "objectclass" and m["op"] == "replace":
                    warn("replacing objectClass can drop required attributes; add or delete the single class instead")
        elif ct == "delete":
            if rest:
                err("a delete record must contain only the dn and changetype")
            warn("delete is permanent; take a backup (slapcat) first and confirm the entry has no children")
        else:
            kv = {}
            for n, l in rest:
                k, v, _ = parse(n, l)
                if k:
                    kv[k.lower()] = v
            if "newrdn" not in kv:
                err("moddn needs newrdn")
            if "deleteoldrdn" not in kv or kv.get("deleteoldrdn") not in ("0", "1"):
                err("moddn needs deleteoldrdn: 0 or 1")
        key = (rec["dn"] or "").lower().replace(", ", ",")
        if rec["dn"]:
            if key in seen and ct == "add" and seen[key][1] == "add":
                err(f"duplicate DN (already added on line {seen[key][0]})")
            seen.setdefault(key, (rec["line"], ct))
        records.append(rec)
    adds = {(r["dn"] or "").lower().replace(", ", ",") for r in records if r["changetype"] == "add" and r["dn"]}
    for r in records:
        if r["changetype"] == "add" and r["dn"] and len(_split_dn(r["dn"])) > 1:
            parent = ",".join(_split_dn(r["dn"])[1:]).lower().replace(", ", ",")
            if parent not in adds:
                msg = f"parent '{','.join(_split_dn(r['dn'])[1:])}' is not created earlier in this file, so it must already exist in the directory"
                r["warnings"].append(msg); problems.append({"line": r["line"], "level": "warn", "issue": f"{r['dn']}: {msg}"})
    flat = []
    for r in records:
        main = r["attrs"].get("cn") or r["attrs"].get("ou") or r["attrs"].get("uid") or r["attrs"].get("o") or r["attrs"].get("dc") or [""]
        flat.append({"line": r["line"], "dn": r["dn"], "action": r["changetype"], "name": main[0], "object_classes": ", ".join(r["attrs"].get("objectclass", [])),
                     "errors": len(r["errors"]), "warnings": len(r["warnings"])})
    errs = sum(1 for p in problems if p["level"] == "error")
    has_change = any(r["changetype"] != "add" for r in records)
    return {"records": len(records), "entries": flat, "problems": problems[:100], "problem_count": len(problems), "errors": errs,
            "verdict": "Do not load this yet: fix the errors." if errs else ("Looks loadable; read the warnings." if problems else "Looks loadable."),
            "command": ("ldapmodify -x -D \"cn=admin,dc=example,dc=com\" -W -f file.ldif" if has_change else "ldapadd -x -D \"cn=admin,dc=example,dc=com\" -W -f file.ldif"),
            "lesson": "LDIF is plain text: one 'attribute: value' per line, a blank line between entries, a dn first, and a changetype for anything that is not a plain add. Non-ASCII values and values starting with a space, colon or < need base64 (attribute:: value). "
                      "Create parents before children, and test on a copy.",
            "limit": "Checks syntax and a few common object classes' required attributes. It cannot know your schema, existing entries, access controls or whether a DN is already in the directory. Never run LDIF against production you have not backed up."}


LDIF_SAMPLE = """dn: ou=People,dc=example,dc=com
objectClass: organizationalUnit
ou: People

dn: cn=Jordan Lee,ou=People,dc=example,dc=com
objectClass: inetOrgPerson
cn: Jordan Lee
sn: Lee
mail: jordan@example.com
userPassword: Welcome1

dn: cn=Ana Pérez,ou=People,dc=example,dc=com
objectClass: inetOrgPerson
cn: Ana Pérez
sn: Pérez

dn: cn=Staff,ou=Groups,dc=example,dc=com
objectClass: groupOfNames
cn: Staff

dn: cn=Jordan Lee,ou=People,dc=example,dc=com
changetype: modify
replace: mail
mail: jordan.lee@example.com
"""


def _b64_if_needed(v: str) -> str:
    if v == "" or not v.isascii() or v[0] in " :<" or v[-1] == " " or "\n" in v:
        return ":: " + base64.b64encode(v.encode()).decode()
    return ": " + v


def dn_escape(v: str) -> str:
    v = re.sub(r'([,+"\\<>;=])', r"\\\1", v)
    if v.startswith(("#", " ")):
        v = "\\" + v
    if v.endswith(" "):
        v = v[:-1] + "\\ "
    return v


def ldif_build(kind, f) -> dict:
    if not isinstance(f, dict):
        raise InfraError("Fields must be an object.")
    base = str(f.get("base_dn", "")).strip()
    probs = dn_problems(base) if base else ["Give a base DN such as dc=example,dc=com."]
    if probs:
        raise InfraError("Base DN: " + "; ".join(probs))
    out = []
    if kind == "user":
        given, sn = str(f.get("given", "")).strip(), str(f.get("sn", "")).strip()
        uid = str(f.get("uid", "")).strip(); ou = str(f.get("ou", "People")).strip() or "People"
        if not sn or not uid:
            raise InfraError("A user needs at least a surname and a uid.")
        if not re.fullmatch(r"[a-z][a-z0-9._-]{0,31}", uid):
            raise InfraError("uid should be lower-case letters, digits, dot, dash or underscore (start with a letter, up to 32).")
        cn = f"{given} {sn}".strip()
        out = [f"dn: cn={dn_escape(cn)},ou={dn_escape(ou)},{base}", "objectClass: inetOrgPerson", f"cn{_b64_if_needed(cn)}", f"sn{_b64_if_needed(sn)}", f"uid: {uid}"]
        if given:
            out.insert(4, f"givenName{_b64_if_needed(given)}")
        if f.get("mail"):
            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(f["mail"])):
                raise InfraError("That email address does not look valid.")
            out.append(f"mail: {f['mail']}")
        out.append("# userPassword: add a HASH here; generate one with: slappasswd -h {SSHA}")
    elif kind == "group":
        name = str(f.get("name", "")).strip(); ou = str(f.get("ou", "Groups")).strip() or "Groups"
        members = [m.strip() for m in str(f.get("members", "")).replace(";", "\n").splitlines() if m.strip()]
        if not name:
            raise InfraError("A group needs a name.")
        if not members:
            raise InfraError("groupOfNames requires at least one member (full DNs, one per line).")
        for m in members:
            p = dn_problems(m)
            if p:
                raise InfraError(f"Member '{m[:50]}': {p[0]}")
        out = [f"dn: cn={dn_escape(name)},ou={dn_escape(ou)},{base}", "objectClass: groupOfNames", f"cn{_b64_if_needed(name)}"] + [f"member: {m}" for m in members]
    elif kind == "ou":
        name = str(f.get("name", "")).strip()
        if not name:
            raise InfraError("An OU needs a name.")
        out = [f"dn: ou={dn_escape(name)},{base}", "objectClass: organizationalUnit", f"ou{_b64_if_needed(name)}"]
    else:
        raise InfraError("Kind must be user, group or ou.")
    ldif = "\n".join(out) + "\n"
    chk = ldif_check(ldif)
    return {"ldif": ldif, "check": {"errors": chk["errors"], "verdict": chk["verdict"], "problems": chk["problems"]},
            "reminder": "Create the parent OU first. Load with ldapadd after a backup, and never put a plain-text password in the file.",
            "limit": "Builds standard inetOrgPerson, groupOfNames and organizationalUnit entries. Your directory's schema may need other classes or attributes."}


# ------------------------------------------------------------------ RBAC audit
def rbac_check(roles, users, conflicts=None, wide_limit=12) -> dict:
    """roles: {name: {permissions:[...], inherits:[...]}}. users: {name: {roles:[...], direct:[...]}}. conflicts: [[roleOrPermA, roleOrPermB]]"""
    if not isinstance(roles, dict) or not 1 <= len(roles) <= 100:
        raise InfraError("Give between 1 and 100 roles.")
    if not isinstance(users, dict) or len(users) > 500:
        raise InfraError("Give up to 500 users.")
    wide_limit = int(wide_limit) if isinstance(wide_limit, (int, float)) and 3 <= wide_limit <= 500 else 12
    clean = {}
    for r, d in roles.items():
        if not isinstance(d, dict):
            raise InfraError(f"Role '{r}' must be an object with permissions and inherits.")
        clean[str(r)] = {"permissions": [str(p) for p in (d.get("permissions") or [])], "inherits": [str(p) for p in (d.get("inherits") or [])]}
    findings = []
    for r, d in clean.items():
        for p in d["inherits"]:
            if p not in clean:
                findings.append({"level": "error", "where": r, "issue": f"inherits '{p}', which is not a defined role"})
    state: dict[str, int] = {}
    cycles = []

    def visit(n, stack):
        if state.get(n) == 2:
            return
        if state.get(n) == 1:
            cycles.append(stack[stack.index(n):] + [n]); return
        state[n] = 1
        for m in clean.get(n, {}).get("inherits", []):
            if m in clean:
                visit(m, stack + [n])
        state[n] = 2
    for r in clean:
        visit(r, [])
    for c in cycles[:5]:
        findings.append({"level": "error", "where": " > ".join(c), "issue": "inheritance cycle: roles inherit from each other, so permissions are undefined"})
    memo: dict[str, set] = {}

    def eff(r, seen=()):
        if r in memo:
            return memo[r]
        if r in seen or r not in clean:
            return set()
        s = set(clean[r]["permissions"])
        for p in clean[r]["inherits"]:
            s |= eff(p, seen + (r,))
        memo[r] = s
        return s
    role_rows = []
    for r in clean:
        e = eff(r)
        role_rows.append({"role": r, "own_permissions": len(clean[r]["permissions"]), "effective_permissions": len(e), "inherits": ", ".join(clean[r]["inherits"]) or "-",
                          "users": sum(1 for u in users.values() if isinstance(u, dict) and r in (u.get("roles") or []))})
        if len(e) > wide_limit:
            findings.append({"level": "warn", "where": r, "issue": f"{len(e)} effective permissions (limit {wide_limit}): split it so no single role is a master key"})
        if not e:
            findings.append({"level": "info", "where": r, "issue": "grants nothing"})
        if role_rows[-1]["users"] == 0:
            findings.append({"level": "info", "where": r, "issue": "no user holds this role; remove it or confirm it is for the future"})
    pairs = []
    for c in (conflicts or []):
        if isinstance(c, list) and len(c) == 2 and all(isinstance(x, str) for x in c):
            pairs.append((c[0], c[1]))
    user_rows = []
    for u, d in users.items():
        d = d if isinstance(d, dict) else {}
        urs = [str(x) for x in (d.get("roles") or [])]
        direct = [str(x) for x in (d.get("direct") or [])]
        for r in urs:
            if r not in clean:
                findings.append({"level": "error", "where": u, "issue": f"has role '{r}', which is not defined"})
        perms = set(direct)
        for r in urs:
            perms |= eff(r)
        if direct:
            findings.append({"level": "warn", "where": u, "issue": f"{len(direct)} permission(s) granted directly ({', '.join(direct[:3])}...): grant through a role so access can be reviewed and removed in one place"})
        for a, b in pairs:
            ha = a in urs or a in perms; hb = b in urs or b in perms
            if ha and hb:
                findings.append({"level": "error", "where": u, "issue": f"separation of duties: holds both '{a}' and '{b}' (one person could do and approve the same thing)"})
        if not urs and not direct:
            findings.append({"level": "info", "where": u, "issue": "has no roles"})
        user_rows.append({"user": u, "roles": ", ".join(urs) or "-", "effective_permissions": len(perms), "direct": len(direct)})
    order = {"error": 0, "warn": 1, "info": 2}
    findings.sort(key=lambda f: order[f["level"]])
    errs = sum(1 for f in findings if f["level"] == "error")
    return {"roles": role_rows, "users": user_rows, "findings": findings[:120], "errors": errs, "warnings": sum(1 for f in findings if f["level"] == "warn"),
            "verdict": "Fix the errors first." if errs else ("Review the warnings." if findings else "No problems found in this model."),
            "lesson": "RBAC gives people roles and roles permissions, so access is reviewed per role instead of per person. Use inheritance sparingly, forbid dangerous role pairs (separation of duties), avoid direct grants, and review who holds each role on a schedule.",
            "limit": "Audits the model you type. It does not read a real directory or application, and it only knows the conflicts you list. Least privilege still needs a human to judge whether each permission is needed."}


RBAC_SAMPLE = {"roles": {"helpdesk": {"permissions": ["reset_password", "view_tickets", "unlock_account"]}, "sysadmin": {"permissions": ["create_account", "approve_account", "edit_gpo", "restart_server"], "inherits": ["helpdesk"]},
                         "auditor": {"permissions": ["read_logs"]}, "intern": {"permissions": []}},
               "users": {"amy": {"roles": ["helpdesk"]}, "ben": {"roles": ["sysadmin", "auditor"]}, "cat": {"roles": ["helpdesk"], "direct": ["edit_gpo"]}, "dan": {"roles": ["contractor"]}},
               "conflicts": [["create_account", "approve_account"], ["sysadmin", "auditor"]]}
