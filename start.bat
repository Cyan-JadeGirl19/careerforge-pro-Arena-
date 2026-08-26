@echo off
REM ============================================================
REM  CareerForge Pro - one-click local launcher (Windows).
REM  Double-click this file. On first run it creates the API
REM  virtualenv and installs the web dependencies, then starts
REM  both servers in their own windows.
REM
REM  App:  http://localhost:3000
REM  API:  http://localhost:8001  (docs at /docs)
REM  Close the two server windows (or Ctrl-C) to stop.
REM ============================================================
setlocal
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo ERROR: Python not found. Install Python 3.11+ from https://python.org and re-run.
  pause
  exit /b 1
)
where node >nul 2>nul
if errorlevel 1 (
  echo ERROR: Node not found. Install Node 18+ from https://nodejs.org and re-run.
  pause
  exit /b 1
)

REM --- API virtualenv (one-time) ---
if not exist "apps\api\.venv\Scripts\python.exe" (
  echo First run: creating the API virtualenv...
  python -m venv apps\api\.venv
)
if not exist "apps\api\.venv\.cf-installed" (
  echo First run: installing API dependencies (one-time, ~1-2 min)...
  apps\api\.venv\Scripts\pip install --quiet -e "apps/api[dev]"
  echo ok> "apps\api\.venv\.cf-installed"
)

REM --- Web dependencies (one-time) ---
if not exist "apps\web\node_modules" (
  echo First run: installing web dependencies (one-time)...
  pushd apps\web
  call npm install --no-audit --no-fund
  popd
)

echo.
echo Starting CareerForge Pro in two new windows...
echo   App:  http://localhost:3000
echo   API:  http://localhost:8001  (docs at /docs)
echo Give each about 20-30 seconds to start, then open the App URL.
echo Close the two server windows to stop.
echo.

start "CareerForge API" /D "%~dp0apps\api" cmd /k ".venv\Scripts\uvicorn app.main:app --host 127.0.0.1 --port 8001"
start "CareerForge Web" /D "%~dp0apps\web" cmd /k "npm run dev"

timeout /t 4 >nul
endlocal
