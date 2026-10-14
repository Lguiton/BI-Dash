# Security and running it on your own computer

This dashboard is built to run on **your computer only**. Everything below is set up for that. Hosting it online is a separate, optional step (see the end).

## The .bat files (installer folder)
| File | What it does |
|---|---|
| `install.bat` | One-time setup (Python packages, screen build). |
| `start.bat` | Starts the backend and the screen on `127.0.0.1` only, runs the security check, opens the browser. If it is already running it just opens it. |
| `stop.bat` | Stops both. |
| `backup_now.bat` | Backs up your Real data right now, whether or not the app is running. |
| `security_check.bat` | Prints OK / WARN / FAIL for secrets, login, network exposure and backup age. Changes nothing. |

## What protects it
* **Listens on this computer only** (`127.0.0.1`). Other devices on your Wi-Fi cannot connect; `security_check` tests this by trying your network address.
* **Host check** (always on): requests whose address bar name is not `localhost` / `127.0.0.1` are refused. This stops "DNS rebinding", where a malicious web page makes your browser talk to your local app under its own name.
* **Other websites cannot change your data**: writes (POST/PUT/PATCH/DELETE) from a different site are refused and logged in the activity log.
* **Security headers** on the API and the screen (no framing, no content sniffing, no referrer, camera/mic/location off) and a **Content-Security-Policy** on the built screen (only its own scripts; the Web tab may frame https pages only).
* **Daily automatic backup of Real data**, even when you are in Practice mode. The computer is not always on, so it runs whenever the app is running, including right after it starts, at most once every 20 hours. The newest 5 or so are kept (Settings > backups).
* **Secrets** live in `backend/.env`; zips never include it (the bundle check fails the zip if it finds a key).
* **Login** (optional, for when it is hosted): `BI_AUTH=1` and `BI_OWNER_PASSWORD` (12+ characters). One owner, salted scrypt hash, HttpOnly cookie, slowed failed logins.
* **AI**: read-only SQL for agents, calculator and conversion tools run in a sandbox of whitelisted functions, tool results are treated as data, not instructions.

## Settings (backend/.env)
* `BI_ALLOWED_HOSTS=name1,name2` extra host names allowed (only when hosting).
* `BI_CORS_ORIGINS=...` the screen addresses allowed to call the API.
* `BI_TZ=America/Los_Angeles` time zone for the morning briefing.
* Morning briefing needs `BI_SMTP_HOST`, `BI_SMTP_USER`, `BI_SMTP_PASSWORD`, `BI_REPORT_TO`. It sends while the app is running; if the computer was off at your chosen hour it sends once when the app starts later that day (until 9 pm).

## Your habits matter more than any setting
1. Keep Windows and your browser updated; use a Windows account password and lock the screen (Win+L).
2. Copy `backend\data\backups` to a USB drive or other disk now and then. A backup beside the original does not survive a dead disk or ransomware.
3. Never paste API keys into the dashboard, chats or screenshots. If one leaks, rotate it at the provider.
4. Only open the dashboard at `http://localhost:3012`.

## Still to do
* Password-change screen (backend exists), login/failed-login entries in the activity log.
* Review against your security transcripts when you send them.
* Optional later: hosting online (production compose + Caddy HTTPS). It needs an account on a host you choose; it is not needed for personal use on one computer.
