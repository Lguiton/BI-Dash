@echo off
REM Stops the dashboard (the backend on port 8020 and the screen on port 3012).
for %%P in (8020 3012) do (
  for /f "tokens=5" %%I in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do taskkill /PID %%I /F >nul 2>nul
)
echo Stopped.
timeout /t 2 >nul
