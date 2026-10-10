@echo off
REM Starts the backend (8020) and the dashboard (3012) in two windows. Close the windows to stop.
cd /d "%~dp0\.."
start "BI backend" cmd /k "call .venv\Scripts\activate.bat && cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8020"
start "BI dashboard" cmd /k "cd frontend && npx next start -p 3012"
timeout /t 6 >nul
start http://localhost:3012
