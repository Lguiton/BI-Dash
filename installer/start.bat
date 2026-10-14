@echo off
REM Starts the dashboard on THIS computer only (127.0.0.1). Close the two windows to stop it, or run stop.bat.
REM Your Real data is backed up automatically once a day while the app is running (and right after it starts, if the computer was off).
cd /d "%~dp0\.."
if not exist .venv\Scripts\activate.bat (
  echo Not installed yet. Run installer\install.bat first.
  pause
  exit /b 1
)
call .venv\Scripts\activate.bat
REM Already running? Just open it.
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8020/health -TimeoutSec 2) | Out-Null; exit 0 } catch { exit 1 }"
if %errorlevel%==0 (
  echo The dashboard is already running. Opening it.
  start http://localhost:3012
  exit /b 0
)
start "BI backend" cmd /k "call .venv\Scripts\activate.bat && cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8020"
start "BI dashboard" cmd /k "cd frontend && npx next start -H 127.0.0.1 -p 3012"
timeout /t 7 >nul
python scripts\security_check.py
start http://localhost:3012
