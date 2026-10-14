"""Practice shell: a simulated Linux terminal over a made-up in-memory file tree.
Nothing here touches the real operating system: commands are parsed and acted on in a dict."""
from __future__ import annotations

import json
import re
import shlex

from app.services import state, workspaces


class ShellError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.message, self.status = message, status


HOME = "/home/student"
USERS = {"student": ["student", "staff"], "bob": ["bob", "staff"], "root": ["root"]}


def _ws() -> str:
    try:
        return workspaces.active()
    except Exception:  # noqa: BLE001
        return "default"


def _f(content="", mode=0o644, owner="student", group="student"):
    return {"t": "f", "c": content, "m": mode, "o": owner, "g": group}


def _d(mode=0o755, owner="student", group="student"):
    return {"t": "d", "m": mode, "o": owner, "g": group}


def fresh() -> dict:
    fs = {
        "/": _d(owner="root", group="root"),
        "/home": _d(owner="root", group="root"), HOME: _d(0o755), "/var": _d(owner="root", group="root"), "/var/log": _d(owner="root", group="root"),
        "/var/log/app.log": _f("INFO started\nERROR disk almost full\nINFO request ok\nERROR timeout talking to db\nINFO request ok\nWARN slow query\nERROR disk almost full\n", 0o644, "root", "root"),
        "/etc": _d(owner="root", group="root"), "/etc/hosts": _f("127.0.0.1 localhost\n", 0o644, "root", "root"),
        "/tmp": _d(0o777, "root", "root"),
        HOME + "/data.txt": _f("alpha\nbeta\ngamma\n"), HOME + "/draft.txt": _f("first version\n"),
        HOME + "/secret.txt": _f("api-key=12345\n", 0o644), HOME + "/deploy.sh": _f("#!/bin/sh\necho deploying\n", 0o644),
        HOME + "/shared.txt": _f("team notes\n", 0o664), HOME + "/team": _d(0o775),
        HOME + "/old": _d(), HOME + "/old/a.log": _f("x\n"), HOME + "/old/b.log": _f("y\n"),
        HOME + "/users.csv": _f("id,name\n1,ana\n2,ben\n3,cy\n4,dee\n5,eli\n"),
    }
    return {"fs": fs, "cwd": HOME, "user": "student", "out": [], "hist": [], "done": []}


def _load() -> dict:
    raw = state.kv_get(f"itshell:{_ws()}")
    if raw:
        try:
            d = json.loads(raw)
            if "fs" in d:
                return d
        except ValueError:
            pass
    return fresh()


def _save(d: dict) -> None:
    d["hist"] = d["hist"][-200:]
    d["out"] = d["out"][-50:]
    state.kv_set(f"itshell:{_ws()}", json.dumps(d))


# ---------------------------------------------------------------- paths and permission
def _norm(cwd: str, p: str) -> str:
    if p.startswith("~"):
        p = HOME + p[1:]
    full = p if p.startswith("/") else cwd.rstrip("/") + "/" + p
    parts: list[str] = []
    for seg in full.split("/"):
        if seg in ("", "."):
            continue
        if seg == "..":
            if parts:
                parts.pop()
        else:
            parts.append(seg)
    return "/" + "/".join(parts)


def _parent(p: str) -> str:
    return p.rsplit("/", 1)[0] or "/"


def _can(n: dict, user: str, bit: int, sudo: bool) -> bool:
    if sudo or user == "root":
        return True
    if n["o"] == user:
        who = (n["m"] >> 6) & 7
    elif n["g"] in USERS.get(user, []):
        who = (n["m"] >> 3) & 7
    else:
        who = n["m"] & 7
    return bool(who & bit)


def _sym(n: dict) -> str:
    m = n["m"]
    s = ""
    for sh in (6, 3, 0):
        b = (m >> sh) & 7
        s += ("r" if b & 4 else "-") + ("w" if b & 2 else "-") + ("x" if b & 1 else "-")
    if m & 0o4000:
        s = s[:2] + ("s" if s[2] == "x" else "S") + s[3:]
    if m & 0o2000:
        s = s[:5] + ("s" if s[5] == "x" else "S") + s[6:]
    if m & 0o1000:
        s = s[:8] + ("t" if s[8] == "x" else "T")
    return ("d" if n["t"] == "d" else "-") + s


def _children(fs: dict, d: str) -> list[str]:
    pre = d.rstrip("/") + "/"
    return sorted(k for k in fs if k != d and k.startswith(pre) and "/" not in k[len(pre):])


def _need(fs: dict, st: dict, p: str, want: str | None = None) -> dict:
    n = fs.get(p)
    if n is None:
        raise ShellError(f"{p}: No such file or directory")
    if want == "f" and n["t"] == "d":
        raise ShellError(f"{p}: Is a directory")
    return n


# ---------------------------------------------------------------- commands
def _ls(fs, st, args, sudo, stdin):
    flags = "".join(a[1:] for a in args if a.startswith("-"))
    targets = [a for a in args if not a.startswith("-")] or ["."]
    out = []
    for t in targets:
        p = _norm(st["cwd"], t)
        n = _need(fs, st, p)
        if n["t"] == "d" and "d" not in flags:
            if not _can(n, st["user"], 4, sudo):
                raise ShellError(f"ls: cannot open directory '{t}': Permission denied")
            names = _children(fs, p)
        else:
            names = [p]
        for k in names:
            base = k.rsplit("/", 1)[-1]
            if base.startswith(".") and "a" not in flags:
                continue
            c = fs[k]
            if "l" in flags:
                size = len(c.get("c", "")) if c["t"] == "f" else 4096
                out.append(f"{_sym(c)} {c['o']} {c['g']} {size:>5} {base}")
            else:
                out.append(base + ("/" if c["t"] == "d" else ""))
    return "\n".join(out) if "l" in flags else "  ".join(out)


def _cd(fs, st, args, sudo, stdin):
    p = _norm(st["cwd"], args[0] if args else "~")
    n = _need(fs, st, p)
    if n["t"] != "d":
        raise ShellError(f"cd: {args[0]}: Not a directory")
    if not _can(n, st["user"], 1, sudo):
        raise ShellError(f"cd: {args[0]}: Permission denied")
    st["cwd"] = p
    return ""


def _mkdir(fs, st, args, sudo, stdin):
    parents = "-p" in args
    names = [a for a in args if not a.startswith("-")]
    if not names:
        raise ShellError("mkdir: missing operand")
    for a in names:
        p = _norm(st["cwd"], a)
        if p in fs:
            if parents:
                continue
            raise ShellError(f"mkdir: cannot create directory '{a}': File exists")
        par = _parent(p)
        if par not in fs:
            if not parents:
                raise ShellError(f"mkdir: cannot create directory '{a}': No such file or directory")
            chain, q = [], p
            while q not in fs and q != "/":
                chain.append(q)
                q = _parent(q)
            for c in reversed(chain):
                fs[c] = _d(0o755, st["user"], st["user"])
            continue
        if not _can(fs[par], st["user"], 2, sudo):
            raise ShellError(f"mkdir: cannot create directory '{a}': Permission denied")
        fs[p] = _d(0o755, st["user"], st["user"])
    return ""


def _write(fs, st, path, text, append, sudo):
    p = _norm(st["cwd"], path)
    n = fs.get(p)
    if n is not None:
        if n["t"] == "d":
            raise ShellError(f"{path}: Is a directory")
        if not _can(n, st["user"], 2, sudo):
            raise ShellError(f"{path}: Permission denied")
        n["c"] = (n["c"] if append else "") + text
        return
    par = _parent(p)
    if par not in fs:
        raise ShellError(f"{path}: No such file or directory")
    if not _can(fs[par], st["user"], 2, sudo):
        raise ShellError(f"{path}: Permission denied")
    fs[p] = _f(text, 0o644, st["user"], st["user"])


def _touch(fs, st, args, sudo, stdin):
    for a in args:
        p = _norm(st["cwd"], a)
        if p not in fs:
            _write(fs, st, a, "", False, sudo)
    return ""


def _cat(fs, st, args, sudo, stdin):
    if not args:
        return stdin or ""
    out = []
    for a in args:
        p = _norm(st["cwd"], a)
        n = _need(fs, st, p, "f")
        if not _can(n, st["user"], 4, sudo):
            raise ShellError(f"cat: {a}: Permission denied")
        out.append(n["c"].rstrip("\n"))
    return "\n".join(out)


def _echo(fs, st, args, sudo, stdin):
    return " ".join(args)


def _copy(fs, st, args, sudo, stdin, move=False):
    rec = any(a in ("-r", "-R", "-a") for a in args)
    pos = [a for a in args if not a.startswith("-")]
    if len(pos) < 2:
        raise ShellError(("mv" if move else "cp") + ": missing file operand")
    *srcs, dst = pos
    dp = _norm(st["cwd"], dst)
    dn = fs.get(dp)
    for s in srcs:
        sp = _norm(st["cwd"], s)
        n = _need(fs, st, sp)
        tgt = dp + "/" + sp.rsplit("/", 1)[-1] if dn and dn["t"] == "d" else dp
        if len(srcs) > 1 and not (dn and dn["t"] == "d"):
            raise ShellError(f"target '{dst}' is not a directory")
        if n["t"] == "d" and not (rec or move):
            raise ShellError(f"cp: -r not specified; omitting directory '{s}'")
        if tgt == sp or tgt.startswith(sp + "/"):
            raise ShellError(f"cannot copy '{s}' into itself")
        if not _can(n, st["user"], 4, sudo):
            raise ShellError(f"cannot open '{s}': Permission denied")
        if not _can(fs[_parent(tgt)] if _parent(tgt) in fs else fs["/"], st["user"], 2, sudo):
            raise ShellError(f"cannot create '{dst}': Permission denied")
        if _parent(tgt) not in fs:
            raise ShellError(f"cannot create '{dst}': No such file or directory")
        moved = {k: v for k, v in fs.items() if k == sp or k.startswith(sp + "/")}
        for k, v in moved.items():
            nk = tgt + k[len(sp):]
            fs[nk] = dict(v) if move else dict(v, o=st["user"], g=st["user"])
        if move:
            for k in moved:
                del fs[k]
    return ""


def _rm(fs, st, args, sudo, stdin):
    rec = any(a.startswith("-") and ("r" in a or "R" in a) for a in args)
    force = any(a.startswith("-") and "f" in a for a in args)
    for a in [x for x in args if not x.startswith("-")]:
        p = _norm(st["cwd"], a)
        if p in ("/", HOME, "/home", "/etc", "/var"):
            raise ShellError(f"rm: refusing to remove '{a}': this practice shell protects system folders")
        n = fs.get(p)
        if n is None:
            if force:
                continue
            raise ShellError(f"rm: cannot remove '{a}': No such file or directory")
        if n["t"] == "d" and not rec:
            raise ShellError(f"rm: cannot remove '{a}': Is a directory (use -r)")
        if not _can(fs[_parent(p)], st["user"], 2, sudo):
            raise ShellError(f"rm: cannot remove '{a}': Permission denied")
        for k in [k for k in fs if k == p or k.startswith(p + "/")]:
            del fs[k]
    return ""


def _rmdir(fs, st, args, sudo, stdin):
    for a in args:
        p = _norm(st["cwd"], a)
        n = _need(fs, st, p)
        if n["t"] != "d":
            raise ShellError(f"rmdir: failed to remove '{a}': Not a directory")
        if _children(fs, p):
            raise ShellError(f"rmdir: failed to remove '{a}': Directory not empty")
        del fs[p]
    return ""


def _grep(fs, st, args, sudo, stdin):
    fl = "".join(a[1:] for a in args if re.fullmatch(r"-[incr]+", a))
    ic, num, cnt = "i" in fl, "n" in fl, "c" in fl
    pos = [a for a in args if not re.fullmatch(r"-[incr]+", a)]
    if not pos:
        raise ShellError("grep: usage: grep [-i] [-n] [-c] pattern [file...]")
    pat, files = pos[0], pos[1:]
    try:
        rx = re.compile(re.escape(pat) if not re.search(r"[\[\]\^\$\.\*\+\?\|\(\)]", pat) else pat, re.I if ic else 0)
    except re.error:
        raise ShellError("grep: invalid pattern") from None
    srcs = [(None, stdin or "")] if not files else []
    for a in files:
        p = _norm(st["cwd"], a)
        n = _need(fs, st, p, "f")
        if not _can(n, st["user"], 4, sudo):
            raise ShellError(f"grep: {a}: Permission denied")
        srcs.append((a if len(files) > 1 else None, n["c"]))
    out, total = [], 0
    for name, text in srcs:
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                total += 1
                out.append((f"{name}:" if name else "") + (f"{i}:" if num else "") + line)
    return str(total) if cnt else "\n".join(out)


def _wc(fs, st, args, sudo, stdin):
    files = [a for a in args if not a.startswith("-")]
    text = stdin or ""
    if files:
        n = _need(fs, st, _norm(st["cwd"], files[0]), "f")
        if not _can(n, st["user"], 4, sudo):
            raise ShellError(f"wc: {files[0]}: Permission denied")
        text = n["c"]
    lines = len(text.splitlines())
    if "-l" in args:
        return str(lines) + (f" {files[0]}" if files else "")
    return f"{lines} {len(text.split())} {len(text)}" + (f" {files[0]}" if files else "")


def _head(fs, st, args, sudo, stdin, tail=False):
    n_ = 10
    rest = []
    it = iter(args)
    for a in it:
        if a == "-n":
            try:
                n_ = int(next(it))
            except (StopIteration, ValueError):
                raise ShellError("invalid line count") from None
        elif re.fullmatch(r"-\d+", a):
            n_ = int(a[1:])
        else:
            rest.append(a)
    text = stdin or ""
    if rest:
        nd = _need(fs, st, _norm(st["cwd"], rest[0]), "f")
        if not _can(nd, st["user"], 4, sudo):
            raise ShellError(f"{rest[0]}: Permission denied")
        text = nd["c"]
    ls = text.splitlines()
    return "\n".join(ls[-n_:] if tail else ls[:n_])


def _sort(fs, st, args, sudo, stdin):
    ls = (stdin or "").splitlines()
    ls.sort(reverse="-r" in args)
    if "-u" in args:
        ls = sorted(set(ls), reverse="-r" in args)
    return "\n".join(ls)


def _uniq(fs, st, args, sudo, stdin):
    out, prev = [], None
    for l in (stdin or "").splitlines():
        if l != prev:
            out.append(l)
        prev = l
    return "\n".join(out)


def _mode_apply(old: int, spec: str, is_dir: bool) -> int:
    if re.fullmatch(r"[0-7]{3,4}", spec):
        return int(spec, 8)
    m = old
    for clause in spec.split(","):
        mt = re.fullmatch(r"([ugoa]*)([+\-=])([rwxst]*)", clause)
        if not mt:
            raise ShellError(f"chmod: invalid mode: '{spec}'")
        who, op, perms = mt.groups()
        who = who or "a"
        masks = 0
        sets = {"u": 0o700, "g": 0o070, "o": 0o007}
        targets = "ugo" if "a" in who else who
        bits = 0
        for t in targets:
            sh = {"u": 6, "g": 3, "o": 0}[t]
            for ch, v in (("r", 4), ("w", 2), ("x", 1)):
                if ch in perms:
                    bits |= v << sh
            masks |= sets[t]
        sp = 0
        if "t" in perms:
            sp |= 0o1000
        if "s" in perms:
            sp |= (0o4000 if "u" in targets else 0) | (0o2000 if "g" in targets else 0)
        if op == "+":
            m |= bits | sp
        elif op == "-":
            m &= ~(bits | sp)
        else:
            m = (m & ~masks) | bits
    return m


def _chmod(fs, st, args, sudo, stdin):
    rec = "-R" in args
    pos = [a for a in args if a != "-R"]
    if len(pos) < 2:
        raise ShellError("chmod: missing operand. Usage: chmod MODE FILE (for example chmod 640 file or chmod u+x file)")
    spec, files = pos[0], pos[1:]
    for a in files:
        p = _norm(st["cwd"], a)
        n = _need(fs, st, p)
        if not (sudo or st["user"] in ("root", n["o"])):
            raise ShellError(f"chmod: changing permissions of '{a}': Operation not permitted")
        for k in [k for k in fs if k == p or (rec and k.startswith(p + "/"))]:
            fs[k]["m"] = _mode_apply(fs[k]["m"], spec, fs[k]["t"] == "d")
    return ""


def _chown(fs, st, args, sudo, stdin):
    if not (sudo or st["user"] == "root"):
        raise ShellError("chown: changing ownership: Operation not permitted (use sudo)")
    pos = [a for a in args if not a.startswith("-")]
    if len(pos) < 2:
        raise ShellError("chown: usage: chown OWNER[:GROUP] FILE")
    own, files = pos[0], pos[1:]
    u, _, g = own.partition(":")
    if u and u not in USERS:
        raise ShellError(f"chown: invalid user: '{u}'")
    for a in files:
        p = _norm(st["cwd"], a)
        n = _need(fs, st, p)
        if u:
            n["o"] = u
        if g:
            n["g"] = g
    return ""


def _simple(text):
    return lambda fs, st, args, sudo, stdin: text(st) if callable(text) else text


CMDS = {
    "ls": _ls, "cd": _cd, "mkdir": _mkdir, "touch": _touch, "cat": _cat, "echo": _echo,
    "cp": _copy, "mv": lambda *a: _copy(*a, move=True), "rm": _rm, "rmdir": _rmdir, "grep": _grep, "wc": _wc,
    "head": _head, "tail": lambda *a: _head(*a, tail=True), "sort": _sort, "uniq": _uniq, "chmod": _chmod, "chown": _chown,
    "pwd": _simple(lambda st: st["cwd"]), "whoami": _simple(lambda st: st["user"]),
    "id": _simple(lambda st: f"uid({st['user']}) groups=" + ",".join(USERS.get(st["user"], []))),
    "history": _simple(lambda st: "\n".join(f"{i + 1:>4}  {h}" for i, h in enumerate(st["hist"]))),
    "clear": _simple(""),
}
NOT_HERE = {"useradd", "adduser", "apt", "ssh", "curl", "wget", "python", "bash", "sh"}
HELP = ["ls [-l] [-a] [-d] [path]", "cd path", "pwd", "mkdir [-p] name", "touch file", "cat file", "echo text > file (or >> to append)", "cp [-r] from to", "mv from to", "rm [-r] [-f] path", "rmdir dir",
        "grep [-i] [-n] [-c] pattern file", "wc [-l] file", "head / tail [-n N] file", "sort, uniq (after a pipe)", "chmod mode file (640 or u+x)", "chown user[:group] file (needs sudo)", "whoami, id, history",
        "pipe with |, redirect with > and >>, prefix with sudo for admin actions"]


# ---------------------------------------------------------------- tasks
def _t_mkdir(fs, o): return fs.get(HOME + "/reports", {}).get("t") == "d"
def _t_hello(fs, o): n = fs.get(HOME + "/notes.txt"); return bool(n and n["t"] == "f" and "hello" in n["c"].lower())
def _t_copy(fs, o): n, b = fs.get(HOME + "/data.txt"), fs.get(HOME + "/data-backup.txt"); return bool(n and b and b["t"] == "f" and b["c"] == n["c"] and n["c"])
def _t_600(fs, o): n = fs.get(HOME + "/secret.txt"); return bool(n and n["m"] & 0o7777 == 0o600)
def _t_x(fs, o): n = fs.get(HOME + "/deploy.sh"); return bool(n and n["m"] & 0o7777 == 0o744)
def _t_errors(fs, o):
    n = fs.get(HOME + "/errors.txt"); src = fs["/var/log/app.log"]["c"].splitlines()
    return bool(n and n["c"].splitlines() == [l for l in src if "ERROR" in l])
def _t_old(fs, o): return HOME + "/old" not in fs and HOME + "/old/a.log" not in fs
def _t_rename(fs, o): return HOME + "/final.txt" in fs and HOME + "/draft.txt" not in fs and fs[HOME + "/final.txt"]["c"] == "first version\n"
def _t_chown(fs, o): n = fs.get(HOME + "/shared.txt"); return bool(n and n["o"] == "bob")
def _t_sticky(fs, o): n = fs.get(HOME + "/team"); return bool(n and n["m"] & 0o7777 == 0o1777)
def _t_count(fs, o): return any(x.strip().startswith("6") and "users.csv" in x or x.strip() == "6" for x in o[-8:])

TASKS = [
    ("mkdir", "Make a folder called reports in your home folder.", "mkdir reports", _t_mkdir, "Use mkdir."),
    ("hello", "Create notes.txt in your home folder containing the word hello.", "echo hello > notes.txt", _t_hello, "echo prints text; > sends it to a file."),
    ("copy", "Copy data.txt to a new file called data-backup.txt.", "cp data.txt data-backup.txt", _t_copy, "cp source destination."),
    ("rename", "Rename draft.txt to final.txt.", "mv draft.txt final.txt", _t_rename, "mv both moves and renames."),
    ("mode600", "Make secret.txt readable and writable by its owner only.", "chmod 600 secret.txt", _t_600, "6 = read+write, 0 = nothing. Three digits: owner, group, others."),
    ("exec", "Make deploy.sh executable for its owner without changing the group and others (it is 644 now).", "chmod u+x deploy.sh", _t_x, "u+x adds execute to the user (owner) only."),
    ("errors", "Save only the ERROR lines of /var/log/app.log into errors.txt in your home folder.", "grep ERROR /var/log/app.log > errors.txt", _t_errors, "grep finds lines; > saves them."),
    ("oldrm", "Delete the folder old and everything inside it.", "rm -r old", _t_old, "Folders need -r. Check the name twice before you press enter."),
    ("count", "Show how many lines users.csv has (the answer should appear on screen).", "wc -l users.csv", _t_count, "wc -l counts lines."),
    ("chown", "Make bob the owner of shared.txt.", "sudo chown bob shared.txt", _t_chown, "Changing owner needs administrator rights: sudo."),
    ("sticky", "Make the team folder a sticky shared folder: mode 1777.", "chmod 1777 team", _t_sticky, "The leading 1 is the sticky bit."),
]


def _prompt(st):
    return f"{st['user']}@practice:{st['cwd'].replace(HOME, '~', 1) if st['cwd'].startswith(HOME) else st['cwd']}$"


def view() -> dict:
    d = _load()
    return {"prompt": _prompt(d), "cwd": d["cwd"], "user": d["user"], "log": d["out"],
            "tasks": [{"id": t[0], "title": t[1], "hint": t[4], "done": t[0] in d["done"]} for t in TASKS],
            "done": len(d["done"]), "total": len(TASKS), "help": HELP,
            "limits": "This is a simulation over a made-up file tree. It teaches the commands and the permission rules, but it is not a real shell: no network, no real files, no scripts, and only the commands listed in help."}


def _split_pipes(line: str) -> list[str]:
    parts, cur, q = [], "", ""
    for ch in line:
        if q:
            cur += ch
            if ch == q:
                q = ""
        elif ch in "'\"":
            q = ch
            cur += ch
        elif ch == "|":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return parts


def run(command: str) -> dict:
    cmd = (command or "").strip()
    if not cmd or len(cmd) > 300:
        raise ShellError("Type a command (up to 300 characters).")
    d = _load()
    fs = d["fs"]
    d["hist"].append(cmd)
    outputs, err = "", None
    try:
        redir, append = None, False
        m = re.search(r"(>>|>)\s*(\S+)\s*$", cmd)
        body = cmd
        if m and not re.search(r"['\"][^'\"]*>[^'\"]*['\"]\s*$", cmd):
            redir, append, body = m.group(2), m.group(1) == ">>", cmd[:m.start()]
        stdin = None
        stages = _split_pipes(body)
        for si, stage in enumerate(stages):
            try:
                words = shlex.split(stage)
            except ValueError:
                raise ShellError("Unbalanced quote.") from None
            if not words:
                raise ShellError("Empty command in the pipe.")
            sudo = False
            if words[0] == "sudo":
                sudo, words = True, words[1:]
                if not words:
                    raise ShellError("sudo: a command is required")
            name, args = words[0], words[1:]
            if name in NOT_HERE:
                raise ShellError(f"{name}: not available in the practice shell (it only simulates the commands listed in help).")
            if name == "help":
                stdin = "\n".join(HELP)
                continue
            fn = CMDS.get(name)
            if fn is None:
                raise ShellError(f"{name}: command not found. Type help to see the commands available here.")
            stdin = fn(fs, d, args, sudo, stdin)
        outputs = stdin or ""
        if redir:
            _write(fs, d, redir, (outputs + "\n") if outputs else "", append, False)
            outputs = ""
    except ShellError as e:
        err = e.message
    d["out"].append(f"{_prompt(d)} {cmd}")
    shown = err or outputs
    if shown:
        d["out"].extend(shown.split("\n"))
    new = []
    outs = shown.split("\n") if shown else []
    for t in TASKS:
        if t[0] not in d["done"] and t[3](fs, outs):
            d["done"].append(t[0])
            new.append(t[0])
    _save(d)
    return {"output": outputs, "error": err, "prompt": _prompt(d), "cwd": d["cwd"], "newly_done": new, "done": len(d["done"]), "total": len(TASKS)}


def reset() -> dict:
    _save(fresh())
    return {"reset": True}


def solution(task_id: str) -> dict:
    for t in TASKS:
        if t[0] == task_id:
            return {"id": t[0], "command": t[2], "hint": t[4]}
    raise ShellError("No such task.", 404)
