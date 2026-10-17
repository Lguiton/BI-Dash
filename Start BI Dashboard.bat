@echo off
setlocal EnableExtensions
title BI Dashboard launcher
REM Double-click to start, stop or open your dashboard. Nothing here connects to the internet or sends anything.
REM Everyday mode runs the backend and the screen inside WSL (scanned-file reading works).
REM Capture mode runs the backend in Windows with administrator rights (live network capture works, scanned-file reading does not).
cd /d "%~dp0"
if /i "%~1"=="capture" goto capture

:menu
cls
echo ================================================
echo   Business Intelligence Dashboard
echo ================================================
echo.
echo   1  Start (everyday)
echo   2  Start with live network capture (administrator)
echo   3  Stop everything
echo   4  Open the dashboard in my browser
echo   5  Quit
echo.
set "CHOICE="
set /p "CHOICE=Choose 1 to 5: "
if "%CHOICE%"=="1" goto everyday
if "%CHOICE%"=="2" goto capture
if "%CHOICE%"=="3" goto stopall
if "%CHOICE%"=="4" goto openit
if "%CHOICE%"=="5" exit /b 0
goto menu

:everyday
call :isup
if "%UP%"=="1" goto alreadyup
where wsl >nul 2>nul
if errorlevel 1 (
  echo WSL was not found on this computer. Install WSL, or start the dashboard the way you did before.
  pause
  exit /b 1
)
echo Starting the backend in WSL...
start "BI backend (WSL)" wsl --cd "%~dp0backend" -e bash -lc "source ../.venv/bin/activate && python -m uvicorn app.main:app --host 127.0.0.1 --port 8020; echo; read -p 'The backend stopped. Press Enter to close this window.'"
call :startscreen
if errorlevel 1 exit /b 1
echo Waiting for the backend...
call :waitfor http://127.0.0.1:8020/health 45
echo Waiting for the screen...
call :waitfor http://127.0.0.1:3012 45
goto openit

:capture
if /i "%~2"=="elevated" goto haveadmin
fltmc >nul 2>&1
if errorlevel 1 goto elevate
:haveadmin
cd /d "%~dp0"
if not exist ".venv-win\Scripts\python.exe" (
  echo The Windows environment .venv-win was not found. It is made by running in PowerShell:
  echo   py -m venv .venv-win ^&^& .venv-win\Scripts\pip install -r backend\requirements.txt
  pause
  exit /b 1
)
call :isup
if "%UP%"=="1" (
  echo A backend is already running on port 8020. Choose "Stop everything" first, then start capture mode.
  pause
  exit /b 1
)
echo Starting the Windows backend with administrator rights...
start "BI backend (Windows, capture)" /d "%~dp0backend" cmd /k "..\.venv-win\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8020"
call :startscreen
if errorlevel 1 exit /b 1
echo Waiting for the backend...
call :waitfor http://127.0.0.1:8020/health 45
echo Waiting for the screen...
call :waitfor http://127.0.0.1:3012 45
goto openit

:elevate
echo Windows will ask for permission. Choose Yes so live capture can read the network card.
powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList 'capture elevated' -Verb RunAs"
exit /b 0

:alreadyup
echo The dashboard is already running.
call :isscreen
if not "%SCREEN%"=="1" call :startscreen
goto openit

:openit
echo.
echo Opening http://localhost:3012
start "" http://localhost:3012
echo You can close this window. The server windows keep the dashboard running.
echo To stop it, run this file again and choose 3.
pause
exit /b 0

:stopall
echo Stopping the dashboard...
where wsl >nul 2>nul
if not errorlevel 1 wsl -e bash -lc "pkill -f '[u]vicorn app.main'; pkill -f '[n]ext start'; pkill -f '[n]ext-server'; true"
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8020,3012 -State Listen -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }"
timeout /t 2 /nobreak >nul
call :isup
if "%UP%"=="1" (
  echo The backend is still answering. If you used capture mode, close its window or run this file as administrator and choose 3 again.
) else (
  echo Stopped.
)
pause
exit /b 0

REM ---------------------------------------------------------------- helpers
:isup
set "UP=0"
curl.exe -s -f -o nul --max-time 3 http://127.0.0.1:8020/health && set "UP=1"
goto :eof

:isscreen
set "SCREEN=0"
curl.exe -s -o nul --max-time 3 http://127.0.0.1:3012 && set "SCREEN=1"
goto :eof

:startscreen
where wsl >nul 2>nul
if errorlevel 1 (
  echo WSL was not found, so the screen cannot start. Install WSL, or start the screen the way you did before.
  pause
  exit /b 1
)
wsl --cd "%~dp0frontend" -e bash -lc "test -f .next/BUILD_ID"
if errorlevel 1 (
  echo The screen has not been built yet. Building it now, this takes a minute or two...
  wsl --cd "%~dp0frontend" -e bash -lc "npm run build"
  if errorlevel 1 (
    echo The build failed. Scroll up to read why, fix it, then try again.
    pause
    exit /b 1
  )
)
echo Starting the screen in WSL...
start "BI screen (WSL)" wsl --cd "%~dp0frontend" -e bash -lc "npx next start -H 127.0.0.1 -p 3012; echo; read -p 'The screen stopped. Press Enter to close this window.'"
exit /b 0

:waitfor
set /a TRIES=0
:waitloop
curl.exe -s -o nul --max-time 3 %1 && goto :eof
set /a TRIES+=1
if %TRIES% geq %2 (
  echo Still not answering after a while: %1
  goto :eof
)
timeout /t 2 /nobreak >nul
goto waitloop
