@echo off
cd /d "%~dp0\.."
python installer\make_personal_bundle.py
pause
