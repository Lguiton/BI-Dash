@echo off
REM One-time setup on Windows. Needs Python 3.11+ and Node 20+ already installed.
cd /d "%~dp0\.."
where python >nul 2>nul || (echo Python 3.11+ is required: https://www.python.org/downloads/ & pause & exit /b 1)
where node >nul 2>nul || (echo Node 20+ is required: https://nodejs.org/ & pause & exit /b 1)
if not exist .venv python -m venv .venv
call .venv\Scripts\activate.bat
python -m pip install -q --upgrade pip
pip install -r backend\requirements.txt || (pause & exit /b 1)
if not exist backend\.env if exist backend\.env.example copy backend\.env.example backend\.env >nul
cd frontend
call npm install || (pause & exit /b 1)
call npm run build || (pause & exit /b 1)
echo.
echo Done. Double-click installer\start.bat, then open http://localhost:3012
pause
