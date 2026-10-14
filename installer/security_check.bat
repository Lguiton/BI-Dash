@echo off
REM Checks your setup: secrets, login, whether other devices can reach the dashboard, and how old your newest backup is. Changes nothing.
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python scripts\security_check.py
echo.
pause
