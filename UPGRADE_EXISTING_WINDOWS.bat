@echo off
setlocal
cd /d "%~dp0"
title GIS Automation Lab - Upgrade Existing Database
set "LAB_PY="
if exist "backend\venv\Scripts\python.exe" set "LAB_PY=venv\Scripts\python.exe"
if exist "backend\.venv\Scripts\python.exe" set "LAB_PY=.venv\Scripts\python.exe"
if not defined LAB_PY (
 echo No Python virtual environment found in backend\venv or backend\.venv
 echo Run SETUP_WINDOWS.bat or create and activate the environment first.
 pause
 exit /b 1
)
echo This upgrade ONLY changes the gis_automation_test database configured in backend\.env.
echo This adds GeoServer metadata without changing existing spatial tables.
echo Back up the lab database before continuing.
echo Set GeoServer connection values in backend/.env as described in README.md.
echo.
pushd backend
"%LAB_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
 popd
 pause
 exit /b 1
)
"%LAB_PY%" manage.py migrate --noinput
if errorlevel 1 (
 popd
 echo Upgrade failed. Copy the error output and review database settings.
 pause
 exit /b 1
)
"%LAB_PY%" manage.py check
if errorlevel 1 (
 popd
 pause
 exit /b 1
)
popd
echo.
echo SUCCESS. GeoServer registry migration applied. Existing test layers are preserved.
echo Start the separate GeoServer and ensure backend/.env has its credentials.
echo Restart Django and React, and refresh the browser.
pause
