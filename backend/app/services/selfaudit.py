"""Security self-audit of THIS dashboard: the things a careful person would check before trusting it with real data.

Every item is read-only. Statuses: ok, warn, fail (fix it), info (a fact worth knowing). It never prints a secret: for keys it only says
whether one is set. The repository scan reports file and line, never the matching text.
"""
from __future__ import annotations

import ipaddress
import os
import re
import subprocess
from pathlib import Path

from app.config import cors_origins, db_path
from app.services import state, workspaces

ROOT = Path(__file__).resolve().parents[3]
SECRET_PATTERNS = [("OpenAI-style key", re.compile(r"\bsk-(?!ant-)[A-Za-z0-9_-]{20,}")), ("Anthropic key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
                   ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")), ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
                   ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")), ("Private key block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"))]
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", ".next", "__pycache__", "lake", "_out", "_work", "landing", "data", "backups"}
TEXT_EXT = {".py", ".ts", ".tsx", ".js", ".json", ".md", ".txt", ".yml", ".yaml", ".toml", ".cfg", ".ini", ".env", ".example", ".sh", ".sql", ".html", ".ipynb"}


def item(iid, status, title, detail="", fix=""):
    return {"id": iid, "status": status, "title": title, "detail": detail, "fix": fix}


def scan_secrets(root: Path = ROOT, max_files: int = 4000) -> list[dict]:
    hits, n = [], 0
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            p = Path(dp, f)
            if p.suffix.lower() not in TEXT_EXT and p.name not in (".env", ".env.example"):
                continue
            if p.name == ".env":
                continue                       # the real keys file is SUPPOSED to hold keys; the question is whether it is committed
            n += 1
            if n > max_files:
                return hits
            try:
                if p.stat().st_size > 1_000_000:
                    continue
                for ln, line in enumerate(p.read_text(errors="ignore").splitlines(), start=1):
                    for label, rx in SECRET_PATTERNS:
                        if rx.search(line):
                            hits.append({"file": str(p.relative_to(root)), "line": ln, "kind": label})
            except OSError:
                continue
    return hits


def _git(*args, cwd=ROOT) -> str | None:
    try:
        r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=5)
        return r.stdout if r.returncode == 0 else None
    except (OSError, subprocess.SubprocessError):
        return None


def run(client_host: str | None = None, root: Path = ROOT) -> dict:
    items: list[dict] = []
    env = root / "backend" / ".env"
    posix = os.name == "posix" and not str(root).startswith("/mnt/")
    if env.exists():
        items.append(item("env-exists", "ok", "Keys live in backend/.env", "AI keys and email passwords are in one file, not in the code."))
        if posix:
            mode = env.stat().st_mode & 0o777
            items.append(item("env-perms", "warn" if mode & 0o077 else "ok", "backend/.env is private to you" if not mode & 0o077 else f"backend/.env is readable by other users (mode {oct(mode)})",
                              "", "Run: chmod 600 backend/.env" if mode & 0o077 else ""))
        else:
            items.append(item("env-perms", "info", "File permissions can't be checked here", "On Windows or a mounted Windows folder, permissions work differently. Keep the folder out of shared or synced locations (OneDrive, Dropbox)."))
        gi = (root / ".gitignore")
        ignored = gi.exists() and re.search(r"^\s*(/?backend/)?\.env\s*$", gi.read_text(errors="ignore"), re.M) is not None
        items.append(item("env-ignored", "ok" if ignored else "fail", "backend/.env is listed in .gitignore" if ignored else "backend/.env is NOT in .gitignore",
                          "" if ignored else "A key file that isn't ignored will end up on GitHub.", "" if ignored else "Add a line '.env' to .gitignore, then run: git rm --cached backend/.env"))
        tracked = _git("ls-files", "--error-unmatch", "backend/.env", cwd=root)
        if tracked:
            items.append(item("env-tracked", "fail", "backend/.env is committed to git", "Anyone with access to the repository can read your keys, and git history keeps them.",
                              "Remove it from git (git rm --cached backend/.env), then REVOKE and re-create every key in it. Deleting the file isn't enough."))
    else:
        items.append(item("env-exists", "info", "No backend/.env file", "AI features and email are off until you add one."))
    hits = scan_secrets(root)
    items.append(item("secret-scan", "fail" if hits else "ok", f"{len(hits)} possible secret(s) found in project files" if hits else "No keys or private keys found in project files",
                      "; ".join(f"{h['kind']} in {h['file']}:{h['line']}" for h in hits[:6]), "Remove it, then revoke that key at its provider: assume anything committed is public." if hits else ""))
    origins = cors_origins()
    wild = "*" in origins
    remote = [o for o in origins if not re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", o) and o != "*"]
    items.append(item("cors", "fail" if wild else "warn" if remote else "ok", "Any website may call the API" if wild else ("Non-local sites may call the API: " + ", ".join(remote[:3])) if remote else "Only this computer's pages may call the API",
                      "", "Set BI_CORS_ORIGINS to just the address you open the dashboard at." if wild or remote else ""))
    if client_host:
        try:
            ip = ipaddress.ip_address(client_host)
            local = ip.is_loopback
        except ValueError:
            local = client_host in ("localhost", "testclient")
        items.append(item("reach", "ok" if local else "warn", "This request came from the same computer" if local else f"This request came from another address ({client_host})",
                          "" if local else "There is no login, so anyone who can reach this port can read and change everything.", "" if local else "Start the backend with --host 127.0.0.1, or put it behind a VPN or a reverse proxy with its own login."))
    items.append(item("no-login", "info", "There is no login, by design", "Protection comes from where it runs. Keep the backend on 127.0.0.1 (the Docker setup already does) and don't expose ports 8020 or 3000 to the internet."))
    ws = workspaces.active()
    st = workspaces.settings("real")
    items.append(item("ai-real", "ok" if st["ai_mode"] != "full" else "warn", f"AI access to Real data: {st['ai_mode']}", "'full' lets row-level data go to the AI provider you use." if st["ai_mode"] == "full" else "",
                      "In Settings choose 'summaries only' or 'off' for Real." if st["ai_mode"] == "full" else ""))
    from app.services import backups
    try:
        bl = backups.list_backups("real")
    except Exception:  # noqa: BLE001
        bl = []
    items.append(item("backups", "ok" if bl else "warn", f"{len(bl)} backup(s) of your Real data" if bl else "No backup of your Real data yet", "Backups are your protection against ransomware and mistakes.", "" if bl else "Take one on the Backups page."))
    smtp = bool(os.environ.get("BI_SMTP_PASSWORD"))
    items.append(item("smtp", "ok", "Email password is in the environment, not the code" if smtp else "Email isn't configured", "Use an app password, not your main one." if smtp else ""))
    if posix:
        loose = [p.name for p in (db_path(), db_path().with_name(f"{db_path().stem}_state.sqlite")) if p.exists() and p.stat().st_mode & 0o004]
        items.append(item("db-perms", "warn" if loose else "ok", "Database files are readable by every user on this machine" if loose else "Database files aren't world-readable", ", ".join(loose), "Run: chmod 600 on those files, or keep the folder private." if loose else ""))
    items.append(item("deps", "info", "Dependencies need a regular check", "Known-vulnerable packages are a leading cause of breaches.", "Run: pip install pip-audit && pip-audit -r backend/requirements.txt   and   cd frontend && npm audit"))
    scored = [i for i in items if i["status"] in ("ok", "warn", "fail")]
    ok = sum(1 for i in scored if i["status"] == "ok")
    return {"items": items, "score": {"ok": ok, "total": len(scored), "pct": round(100 * ok / len(scored)) if scored else 0},
            "fails": sum(1 for i in items if i["status"] == "fail"), "warns": sum(1 for i in items if i["status"] == "warn"), "workspace": ws,
            "note": "A self-audit finds common slips. It can't prove the system is secure."}
