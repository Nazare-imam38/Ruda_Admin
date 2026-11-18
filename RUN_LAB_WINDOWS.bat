@echo off
setlocal
cd /d "%~dp0"
title GIS Automation Lab - Run (No Docker)
if not exist "backend\.venv\Scripts\python.exe" goto SETUP
if not exist "backend\.env" goto SETUP
if not exist "frontend\node_modules\vite" goto SETUP
goto START
:SETUP
echo First use detected. Running one-time local setup (no Docker)...
call "%~dp0SETUP_WINDOWS.bat"
if errorlevel 1 (
  echo Setup did not complete. Fix the error shown above, then run again.
  pause
  exit /b 1
)
:START
REM Apply new migrations on EVERY launch, including after replacing old code.
if exist "backend\.venv\Scripts\python.exe" (
  pushd backend
  ".venv\Scripts\python.exe" manage.py migrate --noinput
  if errorlevel 1 (
    popd
    echo Migration failed. Review database settings and Django errors.
    pause
    exit /b 1
  )
  popd
)
call "%~dp0START_LAB_WINDOWS.bat"
