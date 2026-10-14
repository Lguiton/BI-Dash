@echo off
REM Makes a backup of your Real data right now (works whether or not the app is running).
cd /d "%~dp0\.."
call .venv\Scripts\activate.bat
python scripts\backup_now.py
echo.
echo Backups are in backend\data\backups\real. Copy that folder to a USB drive or another disk now and then.
pause
