@echo off
cd /d "%~dp0backend"
title GIS Automation Lab - Django Backend
set "LAB_PY=.venv\Scripts\python.exe"
if not exist "%LAB_PY%" set "LAB_PY=venv\Scripts\python.exe"
if not exist "%LAB_PY%" (
  echo Missing Python environment. Run SETUP_WINDOWS.bat first.
  pause
  exit /b 1
)
if not exist ".env" (
  echo Missing database configuration. Run SETUP_WINDOWS.bat first.
  pause
  exit /b 1
)
echo Django backend available at http://127.0.0.1:8100/api/health/
"%LAB_PY%" manage.py runserver 127.0.0.1:8100
if errorlevel 1 (
  echo Backend stopped with an error. Check the message above.
  pause
)
